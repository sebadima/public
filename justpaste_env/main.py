import os
import re
import json
import shutil
import subprocess
import threading
import queue
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
import uvicorn

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("justpaste")

HOST = os.getenv("JP_HOST", "127.0.0.1")
PORT = int(os.getenv("JP_PORT", "5000"))
MAX_BODY_SIZE = int(os.getenv("JP_MAX_BODY", "5242880"))  # 5MB default
PDF_TIMEOUT = int(os.getenv("JP_PDF_TIMEOUT", "60"))

BASE_DIR = Path(__file__).parent.resolve()
STYLE_FILE = BASE_DIR / "style.css"
STORAGE = Path(os.getenv("JP_STORAGE", Path.home() / "justpaste")).resolve()
AUTOSAVE_FILE = STORAGE / ".autosave.json"

# --------------------------------------------------
# BOOT CLEANUP & STORAGE PERSISTENCE
# --------------------------------------------------

def initialize_storage():
    try:
        STORAGE.mkdir(parents=True, exist_ok=True)

        # Rimuove le "porcherie" (file tmp orfani) all'avvio
        for junk in STORAGE.glob("tmp*"):
            try:
                if junk.is_file():
                    junk.unlink(missing_ok=True)
                    logger.info(f"CLEANED_ORPHAN: {junk.name}")
            except Exception as e:
                logger.warning(f"FAILED_CLEANUP {junk.name}: {e}")

    except Exception as e:
        logger.critical(f"STORAGE_INIT_ERROR: {e}")
        sys.exit(1)

initialize_storage()

# --------------------------------------------------
# JOB QUEUE (deduplicated)
# --------------------------------------------------

job_q = queue.Queue()
queued_jobs = set()
queue_lock = threading.Lock()

# --------------------------------------------------
# UTILITIES
# --------------------------------------------------

def safe_filename(name: str) -> str:
    try:
        name = (name or "untitled").strip()
        # Rimuove caratteri pericolosi e sequenze di escape
        name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
        # Previene nomi nascosti o risalita directory
        name = name.lstrip(".")

        if not name or name.lower() in ("not_found", "con", "prn", "aux", "nul"):
            name = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return name[:120]  # hard limit
    except Exception:
        return f"emergency_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def find_chrome():
    candidates = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
    for cmd in candidates:
        if p := shutil.which(cmd):
            return p
    return None

def html_to_pdf(html_path: Path, pdf_path: Path) -> Tuple[bool, str]:
    chrome = find_chrome()
    if not chrome:
        return False, "CHROME_NOT_FOUND"

    args = [
        chrome,
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--font-render-hinting=none",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path.absolute()}",
    ]

    try:
        subprocess.run(
            args,
            timeout=PDF_TIMEOUT,
            capture_output=True,
            check=True,
        )

        if pdf_path.is_file() and pdf_path.stat().st_size > 100:
            return True, "OK"

        return False, "EMPTY_OUTPUT"

    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"

    except subprocess.CalledProcessError as e:
        logger.error(f"PDF_SUBPROCESS_ERR: {e.stderr}")
        return False, "SUBPROCESS_ERROR"

    except Exception as e:
        logger.error(f"PDF_SUBPROCESS_ERR: {e}")
        return False, str(e)

# --------------------------------------------------
# WORKER
# --------------------------------------------------

def worker():
    logger.info("PDF_WORKER_READY")

    while True:
        name = job_q.get()

        if name is None:
            break

        try:
            html = (STORAGE / f"{name}.html").resolve()
            pdf = (STORAGE / f"{name}.pdf").resolve()

            # Controllo di sicurezza: il file deve essere dentro STORAGE
            if STORAGE not in html.parents:
                logger.error(f"SECURITY_VIOLATION: Attempted access to {html}")
                continue

            if not html.exists():
                continue

            ok, msg = html_to_pdf(html, pdf)
            logger.info(f"PDF_GEN {name}: {'SUCCESS' if ok else 'FAILED'} | {msg}")

        except Exception as e:
            logger.error(f"WORKER_ERROR: {e}")

        finally:
            with queue_lock:
                queued_jobs.discard(name)
            job_q.task_done()

worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()

# --------------------------------------------------
# FASTAPI
# --------------------------------------------------

app = FastAPI()

@app.get("/style.css")
def style():
    if STYLE_FILE.is_file():
        return FileResponse(STYLE_FILE)
    return HTMLResponse(content="", status_code=404)

@app.get("/favicon.svg")
def favicon():
    return RedirectResponse("https://www.robotdazero.it/favicon.svg")

@app.get("/nextname")
def nextname():
    return f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

@app.get("/", response_class=HTMLResponse)
def index():
    autosave = {"filename": "", "html": ""}

    if AUTOSAVE_FILE.is_file():
        try:
            autosave = json.loads(AUTOSAVE_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("AUTOSAVE_CORRUPTED")

    content = HTML_PAGE.replace("{{AUTOSAVE_FILENAME}}", str(autosave.get("filename", "")))
    content = content.replace("{{AUTOSAVE_HTML}}", str(autosave.get("html", "")))
    return content

@app.post("/save")
async def save(request: Request):
    try:
        name = safe_filename(request.query_params.get("name", "untitled"))
        body = await request.body()

        if not body:
            return JSONResponse(status_code=400, content={"ok": False, "err": "EMPTY_BODY"})

        if len(body) > MAX_BODY_SIZE:
            return JSONResponse(status_code=413, content={"ok": False, "err": "PAYLOAD_TOO_LARGE"})

        html_path = (STORAGE / f"{name}.html").resolve()

        if STORAGE not in html_path.parents:
            raise HTTPException(status_code=400, detail="INVALID_PATH")

        # atomic write
        tmp_path = STORAGE / f"tmp_{name}_{os.getpid()}"
        tmp_path.write_bytes(body)
        tmp_path.replace(html_path)

        # Accoda il job per il PDF (se non è già in coda lo stesso nome)
        with queue_lock:
            if name not in queued_jobs:
                queued_jobs.add(name)
                job_q.put(name)

        logger.info(f"SAVED: {name}.html")
        return {"ok": True, "file": str(html_path), "name": name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SAVE_ERR: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "err": "INTERNAL_ERROR"})

@app.post("/autosave")
async def autosave(request: Request):
    try:
        data = await request.json()

        tmp = STORAGE / ".autosave.tmp"
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(AUTOSAVE_FILE)

        return {"ok": True}

    except Exception:
        return JSONResponse(status_code=500, content={"ok": False})


HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/style.css">
<title>JustPaste</title>
</head>
<body>
<div class="sticky-header">
    <div class="header">
        NAME:
        <input type="text" id="filename" value="{{AUTOSAVE_FILENAME}}" spellcheck="false" autocomplete="off">
        <div id="status">READY</div>
    </div>
    <div class="bar">
        <button onclick="saveMaster()">[ SAVE MASTER ]</button>
        <button onclick="newDoc()">[ NEW ]</button>
    </div>
</div>
<div id="editor" contenteditable="true" spellcheck="false">{{AUTOSAVE_HTML}}</div>

<script>
async function ensureName(){
    const i = document.getElementById('filename');
    if (i.value.trim()) return;
    try {
        const r = await fetch('/nextname');
        i.value = (await r.text()).trim();
    } catch(e) { console.error("Name fetch failed"); }
}

async function saveMaster(){
    await ensureName();
    let name = document.getElementById('filename').value.trim() || 'untitled';

    const status = document.getElementById('status');
    status.innerText = "SAVING...";

    const content = document.getElementById('editor').innerHTML;

    try {
        const r = await fetch('/save?name=' + encodeURIComponent(name), {
            method: 'POST',
            body: content
        });
        const res = await r.json();
        if(res.ok) {
            status.innerText = "SAVED";
            setTimeout(() => { if(status.innerText === "SAVED") status.innerText = "READY"; }, 3000);
        } else {
            status.innerText = "ERROR";
        }
    } catch(e) {
        status.innerText = "NET_ERROR";
    }
}

async function autosave(){
    const payload = {
        filename: document.getElementById('filename').value.trim(),
        html: document.getElementById('editor').innerHTML
    };
    try {
        await fetch('/autosave', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
    } catch(e) {}
}

function newDoc(){
    if (!confirm("Cancellare tutto?")) return;
    document.getElementById('editor').innerHTML = '';
    document.getElementById('filename').value = '';
    ensureName();
}

document.getElementById('editor').addEventListener('paste', function(e) {
    e.preventDefault();
    const items = e.clipboardData.items;
    let handledImage = false;

    for (let item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
            handledImage = true;
            const blob = item.getAsFile();
            const reader = new FileReader();
            reader.onload = function(event) {
                const img = document.createElement('img');
                img.src = event.target.result;
                img.style.maxWidth = '100%';
                img.style.display = 'block';
                img.style.margin = '10px 0';
                document.getElementById('editor').appendChild(img);
            };
            reader.readAsDataURL(blob);
        }
    }

    if (!handledImage) {
        const text = e.clipboardData.getData('text/plain') || '';
        document.execCommand('insertText', false, text);
    }
});

window.onload = () => {
    ensureName();
    setInterval(autosave, 60000);
};
</script>
</body>
</html>
"""

# --------------------------------------------------
# SHUTDOWN
# --------------------------------------------------

def signal_handler(sig, frame):
    logger.info("SHUTTING_DOWN...")
    job_q.put(None)
    worker_thread.join(timeout=5)
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not find_chrome():
        logger.warning("PDF_DISABLED: Chrome/Chromium non trovato.")

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",
        proxy_headers=True,
    )
    
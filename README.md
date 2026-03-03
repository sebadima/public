# L'HUB di robotdazero: i progetti Open-Source di https://www.robotdazero.it/

Repository centrale dei nostri progetti IoT e Python, sviluppati con enfasi su "autonomia" e costruzione "da zero". Qui non troverai framework colossali o dipendenze cloud non necessarie: solo controllo totale sull'hardware e sul bit.

## 🛠 Manifesto Operativo

Seguiamo regole precise per garantire l'integrità tecnica dei nostri progetti:

1. **Controllo > Comodità**: Preferiamo tool CLI minimali e script Python/Bash singoli a software pesanti o framework astratti.
2. **Niente HW fallato o amatoriale**: Per i nodi critici, utilizziamo memorie FRAM e architetture Django per evitare fallimenti hardware (addio SD card e HW wconomico).
3. **Toolchain Minimale**: Vim, Bash, Python RAW. IDE e plugin pesanti sono banditi dal workflow di sviluppo.

## 📦 Progetti Correnti

| Progetto | Descrizione | Tech Stack |
| :--- | :--- | :--- |
| **JustPaste Clone** | Alternativa privata ai paste-bin. Zero DB, solo filesystem. | FastAPI, Chromium Headless |
| **Sentinel Node** | Monitoraggio IoT avanzato senza dipendenze da SD card. | Ubuntu LTS, FRAM, Django |

## 🚀 Filosofia di Deploy

Tutto il codice in questo HUB è pensato per essere:

1. **Copiabile con un click**: Utilizziamo i Gist di GitHub per garantire l'integrità del codice.
2. **Senza Attrito**: Se disponibile, usa sempre il "Download ZIP" dai Gist per inziare velocemente.
3. **GitHub Repo**: Puoi sempre usare il classico comando `git clone https://github.com/sebadima/public.git` per scaricare l'intero ecosistema dei nostri progetti.


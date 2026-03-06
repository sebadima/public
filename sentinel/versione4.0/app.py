import sqlite3
import csv
import io
from flask import Flask, request, jsonify, Response, render_template_string
from datetime import datetime, timedelta

app = Flask(__name__)
DB_FILE = "haccp_monitor.db"

def query_db(query, args=(), one=False):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, args)
        rv = cur.fetchall()
        return (rv[0] if rv else None) if one else rv

@app.route('/ingest', methods=['POST'])
def ingest():
    data = request.json
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                "INSERT INTO haccp_log (temp_cella_1, temp_cella_2, umidita_relativa, pressione_pa) VALUES (?, ?, ?, ?)",
                (data['t1'], data['t2'], data['hum'], data['pres'])
            )
        return jsonify({"status": "OK"}), 201
    except Exception as e:
        return jsonify({"status": "ERROR", "msg": str(e)}), 500

@app.route('/export/<period>')
def export_csv(period):
    days = {"24h": 1, "week": 7, "month": 30}.get(period, 1)
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    rows = query_db("SELECT * FROM haccp_log WHERE timestamp > ? ORDER BY timestamp ASC", (since,))
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'TIMESTAMP', 'TEMP_CELLA_1', 'TEMP_CELLA_2', 'UMIDITA_REL', 'PRESSIONE_PA'])
    for row in rows:
        writer.writerow([row['id'], row['timestamp'], row['temp_cella_1'], row['temp_cella_2'], row['umidita_relativa'], row['pressione_pa']])
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=haccp_report_{period}.csv"}
    )

@app.route('/')
def index():
    data = query_db("SELECT * FROM haccp_log ORDER BY timestamp DESC LIMIT 100")
    data_list = [dict(row) for row in data]
    return render_template_string(HTML_UI, data=data_list)

HTML_UI = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>HACCP_MONITOR_RAW</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .header { border-bottom: 1px solid #0f0; padding-bottom: 10px; margin-bottom: 20px; }
        .btns { margin-bottom: 30px; display: flex; gap: 10px; }
        button { 
            background: transparent; border: 1px solid #0f0; color: #0f0; 
            padding: 10px 20px; cursor: pointer; font-weight: bold;
        }
        button:hover { background: #0f0; color: #000; }
        .chart-container { background: #050505; border: 1px solid #222; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>[ HACCP_MONITORING_SYSTEM_v1.0 ]</h2>
            <p>SISTEMA: CRITICAL_CONTROL_POINTS | DB: haccp_monitor.db</p>
        </div>
        
        <div class="btns">
            <button onclick="location.href='/export/24h'">LOG_24H</button>
            <button onclick="location.href='/export/week'">LOG_SETTIMANA</button>
            <button onclick="location.href='/export/month'">REPOR_MENSILE</button>
        </div>

        <div class="chart-container">
            <canvas id="haccpChart"></canvas>
        </div>
    </div>

    <script>
        const rawData = {{ data|tojson }};
        const ctx = document.getElementById('haccpChart').getContext('2d');
        
        const labels = rawData.map(r => r.timestamp).reverse();
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Cella 1 (°C)', data: rawData.map(r => r.temp_cella_1).reverse(), borderColor: '#f00', tension: 0.1 },
                    { label: 'Cella 2 (°C)', data: rawData.map(r => r.temp_cella_2).reverse(), borderColor: '#ff0', tension: 0.1 },
                    { label: 'Umidità (%)', data: rawData.map(r => r.umidita_relativa).reverse(), borderColor: '#00f', tension: 0.1 },
                    { label: 'Pressione (Pa)', data: rawData.map(r => r.pressione_pa).reverse(), borderColor: '#fff', tension: 0.1 }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    x: { ticks: { color: '#0f0' }, grid: { color: '#111' } },
                    y: { ticks: { color: '#0f0' }, grid: { color: '#111' } }
                },
                plugins: { legend: { labels: { color: '#0f0' } } }
            }
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5040, debug=False)

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
        ts = data.get('timestamp')
        with sqlite3.connect(DB_FILE) as conn:
            if ts:
                conn.execute(
                    "INSERT INTO haccp_log (timestamp, temp_cella_1, temp_cella_2, umidita_relativa, pressione_pa) VALUES (?, ?, ?, ?, ?)",
                    (ts, data['t1'], data['t2'], data['hum'], data['pres'])
                )
            else:
                conn.execute(
                    "INSERT INTO haccp_log (temp_cella_1, temp_cella_2, umidita_relativa, pressione_pa) VALUES (?, ?, ?, ?)",
                    (data['t1'], data['t2'], data['hum'], data['pres'])
                )
        return jsonify({"status": "OK"}), 201
    except Exception as e:
        return jsonify({"status": "ERROR", "msg": str(e)}), 500

@app.route('/data')
def get_data():
    # Endpoint tecnico per il refresh AJAX del grafico
    data = query_db("SELECT * FROM haccp_log ORDER BY timestamp DESC LIMIT 100")
    return jsonify([dict(row) for row in data])

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
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=haccp_report_{period}.csv"})

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
    <title>HACCP_LIVE_MONITOR</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { border-bottom: 1px solid #0f0; padding-bottom: 10px; margin-bottom: 20px; }
        .btns { margin-bottom: 30px; display: flex; gap: 10px; }
        button { background: transparent; border: 1px solid #0f0; color: #0f0; padding: 10px 20px; cursor: pointer; font-weight: bold;}
        button:hover { background: #0f0; color: #000; }
        .chart-container { background: #050505; border: 1px solid #222; padding: 20px; height: 500px; position: relative; }
        .status-led { color: #0f0; font-size: 0.8em; float: right; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="status-led" id="sync-status">SYNC: OK</span>
            <h2>[ HACCP_MONITORING_SYSTEM_v1.4 ]</h2>
            <p>SISTEMA: TEMPERATURE_CORE | REFRESH: AUTO (15s)</p>
        </div>
        <div class="btns">
            <button onclick="location.href='/export/24h'">LOG_24H</button>
            <button onclick="location.href='/export/week'">LOG_SETTIMANA</button>
            <button onclick="location.href='/export/month'">REPORT_MENSILE</button>
        </div>
        <div class="chart-container">
            <canvas id="haccpChart"></canvas>
        </div>
    </div>
    <script>
        let haccpChart;
        const ctx = document.getElementById('haccpChart').getContext('2d');

        function initChart(initialData) {
            const labels = initialData.map(r => r.timestamp).reverse();
            haccpChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        { 
                            label: 'Cella 1 (°C)', 
                            data: initialData.map(r => r.temp_cella_1).reverse(), 
                            borderColor: '#f00', 
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 2
                        },
                        { 
                            label: 'Cella 2 (°C)', 
                            data: initialData.map(r => r.temp_cella_2).reverse(), 
                            borderColor: '#ff0', 
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 2
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    scales: {
                        x: { ticks: { color: '#0f0', maxRotation: 45 }, grid: { color: '#111' } },
                        y: { ticks: { color: '#0f0' }, grid: { color: '#222' } }
                    },
                    plugins: { legend: { labels: { color: '#0f0' } } }
                }
            });
        }

        async function refreshData() {
            try {
                const response = await fetch('/data');
                const newData = await response.json();
                const labels = newData.map(r => r.timestamp).reverse();
                
                haccpChart.data.labels = labels;
                haccpChart.data.datasets[0].data = newData.map(r => r.temp_cella_1).reverse();
                haccpChart.data.datasets[1].data = newData.map(r => r.temp_cella_2).reverse();
                haccpChart.update('none');
                
                document.getElementById('sync-status').innerText = "LAST_SYNC: " + new Date().toLocaleTimeString();
            } catch (e) {
                document.getElementById('sync-status').innerText = "SYNC: ERROR";
            }
        }

        // Avvio
        const initialData = {{ data|tojson }};
        initChart(initialData);
        
        // Refresh ogni 15 secondi (allineato al timer 0x68)
        setInterval(refreshData, 15000);
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5040, debug=False)

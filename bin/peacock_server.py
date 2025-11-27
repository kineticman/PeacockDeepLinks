#!/usr/bin/env python3
"""
peacock_server.py - Web server with scheduled refreshes and deeplink API
"""

import os, logging, subprocess, sys, json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from flask import Flask, send_file, jsonify, render_template_string, redirect
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Configuration
PORT = int(os.getenv("PEACOCK_PORT", "6655"))
DB_PATH = os.getenv("PEACOCK_DB_PATH", "/data/peacock_events.db")
LANES_XML_PATH = os.getenv("PEACOCK_LANES_XML_PATH", "/data/peacock_lanes.xml")
LANES_M3U_PATH = os.getenv("PEACOCK_LANES_M3U_PATH", "/data/peacock_lanes.m3u")
CHROME_M3U_PATH = os.getenv("PEACOCK_CHROME_M3U_PATH", "/data/peacock_lanes_chrome.m3u")
DIRECT_XML_PATH = os.getenv("PEACOCK_DIRECT_XML_PATH", "/data/peacock_direct.xml")
DIRECT_M3U_PATH = os.getenv("PEACOCK_DIRECT_M3U_PATH", "/data/peacock_direct.m3u")
REFRESH_CRON = os.getenv("PEACOCK_REFRESH_CRON", "15 3 * * *")
LANES = int(os.getenv("PEACOCK_LANES", "10"))
DAYS_AHEAD = int(os.getenv("PEACOCK_DAYS_AHEAD", "7"))
SLUG = os.getenv("PEACOCK_SLUG", "/sports/live-and-upcoming")

# Server URL construction
def get_server_url():
    """Build server URL from host and port"""
    # Try new style first (separate host and port)
    server_host = os.getenv("PEACOCK_SERVER_HOST")
    if server_host:
        # Remove http:// or https:// if present
        server_host = server_host.replace("http://", "").replace("https://", "")
        return f"http://{server_host}:{PORT}"
    
    # Fall back to old style (full URL)
    server_url = os.getenv("PEACOCK_SERVER_URL")
    if server_url:
        return server_url
    
    # Default
    return f"http://localhost:{PORT}"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# State tracking
refresh_lock = Lock()
last_refresh = {
    "status": "never",
    "start_time": None,
    "end_time": None,
    "duration_seconds": None,
    "error": None,
    "events_count": 0,
    "lanes_count": 0,
    "direct_channels_count": 0,
}

def get_script_dir():
    return Path(__file__).resolve().parent

def get_current_lane_deeplink(lane_id: int) -> str:
    """Get the deeplink URL for the currently playing event in a lane"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Find current event in this lane
        cur.execute("""
            SELECT e.pvid
            FROM lane_events le
            JOIN events e ON le.event_id = e.id
            WHERE le.lane_id = ?
              AND le.is_placeholder = 0
              AND le.start_utc <= ?
              AND le.end_utc > ?
              AND e.pvid IS NOT NULL
            ORDER BY le.start_utc DESC
            LIMIT 1
        """, (lane_id, now, now))
        
        row = cur.fetchone()
        conn.close()
        
        if not row or not row["pvid"]:
            # No current event, find next upcoming
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            cur.execute("""
                SELECT e.pvid
                FROM lane_events le
                JOIN events e ON le.event_id = e.id
                WHERE le.lane_id = ?
                  AND le.is_placeholder = 0
                  AND le.start_utc > ?
                  AND e.pvid IS NOT NULL
                ORDER BY le.start_utc ASC
                LIMIT 1
            """, (lane_id, now))
            
            row = cur.fetchone()
            conn.close()
            
            if not row or not row["pvid"]:
                return None
        
        pvid = row["pvid"]
        
        # Build deeplink
        import urllib.parse
        deeplink_payload = {"pvid": pvid, "type": "PROGRAMME", "action": "PLAY"}
        deeplink_json = json.dumps(deeplink_payload, separators=(",", ":"))
        deeplink_url = f"https://www.peacocktv.com/deeplink?deeplinkData={urllib.parse.quote(deeplink_json, safe='')}"
        
        return deeplink_url
        
    except Exception as e:
        logger.error(f"Error getting deeplink for lane {lane_id}: {e}")
        return None

def run_refresh():
    """Run the complete refresh process"""
    global last_refresh
    
    if not refresh_lock.acquire(blocking=False):
        logger.warning("Refresh already in progress, skipping")
        return
    
    try:
        start_time = datetime.now(timezone.utc)
        last_refresh["status"] = "running"
        last_refresh["start_time"] = start_time.isoformat()
        last_refresh["error"] = None
        
        logger.info("Starting scheduled refresh...")
        
        script_dir = get_script_dir()
        server_url = get_server_url()
        
        # Step 1: Ingest
        logger.info("Step 1: Ingesting from Peacock API...")
        result = subprocess.run(
            [sys.executable, str(script_dir / "peacock_ingest_atom.py"),
             "--db", DB_PATH, "--slug", SLUG],
            capture_output=True, text=True, timeout=300
        )
        
        if result.returncode != 0:
            raise Exception(f"Ingest failed: {result.stderr}")
        
        logger.info("Ingest complete")
        
        # Step 2: Build lanes
        logger.info("Step 2: Building lanes...")
        result = subprocess.run(
            [sys.executable, str(script_dir / "peacock_build_lanes.py"),
             "--db", DB_PATH, "--lanes", str(LANES), "--days-ahead", str(DAYS_AHEAD)],
            capture_output=True, text=True, timeout=300
        )
        
        if result.returncode != 0:
            raise Exception(f"Build lanes failed: {result.stderr}")
        
        logger.info("Build lanes complete")
        
        # Step 3: Export (hybrid mode)
        logger.info("Step 3: Exporting XMLTV/M3U (both formats)...")
        result = subprocess.run(
            [sys.executable, str(script_dir / "peacock_export_hybrid.py"),
             "--db", DB_PATH,
             "--lanes-xml", LANES_XML_PATH, "--lanes-m3u", LANES_M3U_PATH,
             "--chrome-m3u", CHROME_M3U_PATH,
             "--direct-xml", DIRECT_XML_PATH, "--direct-m3u", DIRECT_M3U_PATH,
             "--server-url", server_url],
            capture_output=True, text=True, timeout=300
        )
        
        if result.returncode != 0:
            raise Exception(f"Export failed: {result.stderr}")
        
        logger.info("Export complete")
        
        # Get stats
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM events WHERE pvid IS NOT NULL")
            events_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM lanes")
            lanes_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT le.event_id) FROM lane_events le WHERE le.is_placeholder = 0")
            direct_count = cur.fetchone()[0]
            
            conn.close()
            
            last_refresh["events_count"] = events_count
            last_refresh["lanes_count"] = lanes_count
            last_refresh["direct_channels_count"] = direct_count
        except Exception as e:
            logger.warning(f"Could not get stats: {e}")
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        last_refresh["status"] = "success"
        last_refresh["end_time"] = end_time.isoformat()
        last_refresh["duration_seconds"] = duration
        
        logger.info(f"Refresh completed successfully in {duration:.1f}s")
        
    except Exception as e:
        logger.error(f"Refresh failed: {e}")
        last_refresh["status"] = "failed"
        last_refresh["error"] = str(e)
        last_refresh["end_time"] = datetime.now(timezone.utc).isoformat()
    
    finally:
        refresh_lock.release()

# HTML Dashboard Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Peacock TV Scraper</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a; color: #e2e8f0; padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { 
            font-size: 2rem; margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .subtitle { color: #94a3b8; margin-bottom: 2rem; }
        .card { 
            background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem;
            border: 1px solid #334155;
        }
        .card h2 { font-size: 1.25rem; margin-bottom: 1rem; color: #f1f5f9; }
        .status-badge {
            display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px;
            font-size: 0.875rem; font-weight: 600;
        }
        .status-success { background: #10b981; color: white; }
        .status-failed { background: #ef4444; color: white; }
        .status-running { background: #f59e0b; color: white; }
        .status-never { background: #64748b; color: white; }
        .stat-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem; margin-top: 1rem;
        }
        .stat { background: #0f172a; padding: 1rem; border-radius: 6px; border: 1px solid #334155; }
        .stat-label { font-size: 0.875rem; color: #94a3b8; margin-bottom: 0.5rem; }
        .stat-value { font-size: 1.5rem; font-weight: 700; color: #f1f5f9; }
        .link-section { margin-bottom: 1.5rem; }
        .link-section h3 { font-size: 1rem; color: #94a3b8; margin-bottom: 0.75rem; }
        .link-list { list-style: none; }
        .link-list li { margin-bottom: 0.75rem; }
        .link-list a { 
            color: #60a5fa; text-decoration: none; display: inline-flex;
            align-items: center; gap: 0.5rem;
        }
        .link-list a:hover { color: #93c5fd; }
        button {
            background: #3b82f6; color: white; border: none; padding: 0.75rem 1.5rem;
            border-radius: 6px; font-size: 1rem; cursor: pointer; font-weight: 600;
        }
        button:hover { background: #2563eb; }
        button:disabled { background: #64748b; cursor: not-allowed; }
        .error { 
            background: #7f1d1d; color: #fecaca; padding: 1rem; border-radius: 6px;
            margin-top: 1rem; font-family: monospace; font-size: 0.875rem;
        }
        .info-grid { display: grid; gap: 0.5rem; margin-top: 1rem; }
        .info-row {
            display: flex; justify-content: space-between; padding: 0.5rem 0;
            border-bottom: 1px solid #334155;
        }
        .info-label { color: #94a3b8; }
        .info-value { color: #f1f5f9; font-weight: 500; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🦚 Peacock TV Scraper</h1>
        <p class="subtitle">Hybrid mode: Lane-based (ADBTuner) + Direct deeplinks</p>
        
        <div class="card">
            <h2>Status</h2>
            <div>Last Refresh: <span class="status-badge status-{{ status }}">{{ status|upper }}</span></div>
            
            {% if last_refresh.start_time %}
            <div class="info-grid">
                <div class="info-row">
                    <span class="info-label">Started:</span>
                    <span class="info-value">{{ last_refresh.start_time }}</span>
                </div>
                {% if last_refresh.end_time %}
                <div class="info-row">
                    <span class="info-label">Completed:</span>
                    <span class="info-value">{{ last_refresh.end_time }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Duration:</span>
                    <span class="info-value">{{ last_refresh.duration_seconds }}s</span>
                </div>
                {% endif %}
            </div>
            {% endif %}
            
            {% if last_refresh.error %}
            <div class="error">{{ last_refresh.error }}</div>
            {% endif %}
            
            <div style="margin-top: 1.5rem;">
                <button onclick="refresh()" id="refreshBtn">🔄 Refresh Now</button>
            </div>
        </div>
        
        <div class="card">
            <h2>Statistics</h2>
            <div class="stat-grid">
                <div class="stat">
                    <div class="stat-label">Total Events</div>
                    <div class="stat-value">{{ last_refresh.events_count or 0 }}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Lanes</div>
                    <div class="stat-value">{{ last_refresh.lanes_count or 0 }}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Direct Channels</div>
                    <div class="stat-value">{{ last_refresh.direct_channels_count or 0 }}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Next Refresh</div>
                    <div class="stat-value" style="font-size: 1rem;">{{ next_run or 'Not scheduled' }}</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Downloads</h2>
            
            <div class="link-section">
                <h3>🎮 For ADBTuner (Lane-based with API)</h3>
                <ul class="link-list">
                    <li><a href="/lanes/xmltv">📺 XMLTV EPG (peacock_lanes.xml)</a></li>
                    <li><a href="/lanes/m3u">📡 M3U Playlist (peacock_lanes.m3u)</a></li>
                </ul>
            </div>
            
            <div class="link-section">
                <h3>🌐 For Chrome Capture (Lane-based with deeplinks)</h3>
                <ul class="link-list">
                    <li><a href="/chrome/m3u">📡 M3U Playlist (peacock_lanes_chrome.m3u)</a></li>
                    <li style="font-size: 0.875rem; color: #94a3b8;">Uses same XMLTV as ADBTuner: <a href="/lanes/xmltv">peacock_lanes.xml</a></li>
                </ul>
            </div>
            
            <div class="link-section">
                <h3>🔗 For Direct Deeplinks (One channel per event)</h3>
                <ul class="link-list">
                    <li><a href="/direct/xmltv">📺 XMLTV EPG (peacock_direct.xml)</a></li>
                    <li><a href="/direct/m3u">📡 M3U Playlist (peacock_direct.m3u)</a></li>
                </ul>
            </div>
            
            <div class="link-section">
                <h3>🔌 API Endpoints</h3>
                <ul class="link-list">
                    <li><a href="/api/status">Status (JSON)</a></li>
                    <li><a href="/api/lane/1/deeplink">Lane 1 Current Deeplink</a></li>
                </ul>
            </div>
        </div>
        
        <div class="card">
            <h2>Configuration</h2>
            <div class="info-grid">
                <div class="info-row">
                    <span class="info-label">Server URL:</span>
                    <span class="info-value">{{ config.server_url }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Lanes:</span>
                    <span class="info-value">{{ config.lanes }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Days Ahead:</span>
                    <span class="info-value">{{ config.days_ahead }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Schedule:</span>
                    <span class="info-value">{{ config.refresh_cron }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Port:</span>
                    <span class="info-value">{{ config.port }}</span>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function refresh() {
            const btn = document.getElementById('refreshBtn');
            btn.disabled = true;
            btn.textContent = '⏳ Refreshing...';
            
            fetch('/api/refresh', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    setTimeout(() => window.location.reload(), 2000);
                })
                .catch(err => {
                    alert('Error: ' + err);
                    btn.disabled = false;
                    btn.textContent = '🔄 Refresh Now';
                });
        }
    </script>
</body>
</html>
"""

# Routes
@app.route('/')
def dashboard():
    next_run = None
    if scheduler:
        jobs = scheduler.get_jobs()
        if jobs:
            next_run_dt = jobs[0].next_run_time
            if next_run_dt:
                next_run = next_run_dt.strftime('%Y-%m-%d %H:%M:%S %Z')
    
    return render_template_string(
        DASHBOARD_HTML,
        status=last_refresh["status"],
        last_refresh=last_refresh,
        next_run=next_run,
        config={
            "server_url": get_server_url(),
            "lanes": LANES,
            "days_ahead": DAYS_AHEAD,
            "refresh_cron": REFRESH_CRON,
            "port": PORT
        }
    )

# Lane-based files (for ADBTuner)
@app.route('/lanes/xmltv')
@app.route('/xmltv')
def serve_lanes_xmltv():
    if not Path(LANES_XML_PATH).exists():
        return jsonify({"error": "Lanes XMLTV not found. Run refresh first."}), 404
    return send_file(LANES_XML_PATH, mimetype='application/xml', as_attachment=False, download_name='peacock_lanes.xml')

@app.route('/lanes/m3u')
@app.route('/m3u')
def serve_lanes_m3u():
    if not Path(LANES_M3U_PATH).exists():
        return jsonify({"error": "Lanes M3U not found. Run refresh first."}), 404
    return send_file(LANES_M3U_PATH, mimetype='audio/x-mpegurl', as_attachment=False, download_name='peacock_lanes.m3u')

@app.route('/chrome/m3u')
def serve_chrome_m3u():
    if not Path(CHROME_M3U_PATH).exists():
        return jsonify({"error": "Chrome M3U not found. Run refresh first."}), 404
    return send_file(CHROME_M3U_PATH, mimetype='audio/x-mpegurl', as_attachment=False, download_name='peacock_lanes_chrome.m3u')

# Direct deeplink files
@app.route('/direct/xmltv')
def serve_direct_xmltv():
    if not Path(DIRECT_XML_PATH).exists():
        return jsonify({"error": "Direct XMLTV not found. Run refresh first."}), 404
    return send_file(DIRECT_XML_PATH, mimetype='application/xml', as_attachment=False, download_name='peacock_direct.xml')

@app.route('/direct/m3u')
def serve_direct_m3u():
    if not Path(DIRECT_M3U_PATH).exists():
        return jsonify({"error": "Direct M3U not found. Run refresh first."}), 404
    return send_file(DIRECT_M3U_PATH, mimetype='audio/x-mpegurl', as_attachment=False, download_name='peacock_direct.m3u')

# API
@app.route('/api/lane/<int:lane_id>/deeplink')
def api_lane_deeplink(lane_id):
    """Get deeplink for current event in lane
    
    Query params:
        ?format=redirect - Redirect to deeplink (default, for ADBTuner)
        ?format=json     - Return JSON with deeplink URL
        ?format=text     - Return plain text deeplink URL
    
    Legacy params:
        ?redirect=true   - Same as format=redirect
        ?redirect=false  - Same as format=json
    """
    deeplink = get_current_lane_deeplink(lane_id)
    if not deeplink:
        if request.args.get('format') == 'text':
            return "No current or upcoming event", 404
        return jsonify({"error": f"No current or upcoming event for lane {lane_id}"}), 404
    
    # Check format
    from flask import request
    fmt = request.args.get('format', '').lower()
    
    # Legacy redirect parameter support
    if not fmt:
        redirect_mode = request.args.get('redirect', 'true').lower() == 'true'
        fmt = 'redirect' if redirect_mode else 'json'
    
    if fmt == 'text':
        # Plain text mode - just return the URL
        return deeplink, 200, {'Content-Type': 'text/plain'}
    elif fmt == 'json':
        # JSON mode
        return jsonify({
            "lane_id": lane_id,
            "deeplink": deeplink,
            "deeplink_url": deeplink
        })
    else:
        # Redirect mode (default for ADBTuner)
        return redirect(deeplink, code=302)

@app.route('/api/status')
def api_status():
    return jsonify({
        "status": "ok",
        "last_refresh": last_refresh,
        "config": {
            "server_url": get_server_url(),
            "lanes": LANES,
            "days_ahead": DAYS_AHEAD,
            "refresh_cron": REFRESH_CRON,
            "port": PORT
        },
        "files": {
            "lanes_xmltv_exists": Path(LANES_XML_PATH).exists(),
            "lanes_m3u_exists": Path(LANES_M3U_PATH).exists(),
            "chrome_m3u_exists": Path(CHROME_M3U_PATH).exists(),
            "direct_xmltv_exists": Path(DIRECT_XML_PATH).exists(),
            "direct_m3u_exists": Path(DIRECT_M3U_PATH).exists(),
            "db_exists": Path(DB_PATH).exists(),
        }
    })

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    if refresh_lock.locked():
        return jsonify({"error": "Refresh already in progress"}), 409
    
    import threading
    thread = threading.Thread(target=run_refresh)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Refresh started"}), 202

# Scheduler
scheduler = None

def init_scheduler():
    global scheduler
    scheduler = BackgroundScheduler(timezone="UTC")
    parts = REFRESH_CRON.split()
    if len(parts) == 5:
        trigger = CronTrigger(
            minute=parts[0], hour=parts[1], day=parts[2],
            month=parts[3], day_of_week=parts[4], timezone="UTC"
        )
        scheduler.add_job(run_refresh, trigger, id='daily_refresh')
        logger.info(f"Scheduled refresh: {REFRESH_CRON} (UTC)")
    else:
        logger.warning(f"Invalid cron expression: {REFRESH_CRON}")
    scheduler.start()
    logger.info("Scheduler started")

def main():
    logger.info("="*60)
    logger.info("Peacock TV Scraper Server (Hybrid Mode)")
    logger.info("="*60)
    logger.info(f"Port: {PORT}")
    logger.info(f"Server URL: {get_server_url()}")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Lanes XMLTV: {LANES_XML_PATH}")
    logger.info(f"Lanes M3U: {LANES_M3U_PATH}")
    logger.info(f"Chrome M3U: {CHROME_M3U_PATH}")
    logger.info(f"Direct XMLTV: {DIRECT_XML_PATH}")
    logger.info(f"Direct M3U: {DIRECT_M3U_PATH}")
    logger.info(f"Lanes: {LANES}")
    logger.info(f"Days ahead: {DAYS_AHEAD}")
    logger.info(f"Refresh schedule: {REFRESH_CRON}")
    logger.info("="*60)
    
    for path in [DB_PATH, LANES_XML_PATH, DIRECT_XML_PATH]:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    init_scheduler()
    
    if not Path(LANES_XML_PATH).exists() or not Path(DIRECT_XML_PATH).exists():
        logger.info("No existing files found, running initial refresh...")
        run_refresh()
    
    logger.info(f"Starting web server on port {PORT}...")
    logger.info(f"Dashboard: http://localhost:{PORT}/")
    app.run(host='0.0.0.0', port=PORT, debug=False)

if __name__ == "__main__":
    main()

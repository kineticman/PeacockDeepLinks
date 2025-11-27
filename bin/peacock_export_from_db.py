#!/usr/bin/env python3
"""peacock_export_from_db.py - Export lanes to XMLTV and M3U"""
import os, argparse, json, sqlite3, urllib.parse
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def check_tables(conn: sqlite3.Connection, required: List[str]) -> Tuple[bool, List[str]]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing = {row["name"] for row in cur.fetchall()}
    missing = [t for t in required if t not in existing]
    return (len(missing) == 0, missing)

def get_lanes(conn: sqlite3.Connection) -> List[Tuple[int, str, int]]:
    cur = conn.cursor()
    cur.execute("SELECT lane_id, name, logical_number FROM lanes ORDER BY lane_id")
    return [(row["lane_id"], row["name"], row["logical_number"]) for row in cur.fetchall()]

def get_lane_events(conn: sqlite3.Connection) -> List[Dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT le.lane_id, le.event_id, le.is_placeholder, le.start_utc, le.end_utc, le.title,
               e.pvid, e.slug, e.title AS event_title, e.channel_name,
               e.synopsis, e.synopsis_brief, e.genres_json
        FROM lane_events le
        LEFT JOIN events e ON le.event_id = e.id
        ORDER BY le.lane_id, le.start_utc
    """)
    return [dict(row) for row in cur.fetchall()]

def parse_iso(dt_str: str) -> datetime:
    if not dt_str:
        return datetime.max.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def xmltv_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S +0000")

def get_event_images(conn: sqlite3.Connection, event_id: str, preferred_types: List[str]) -> Optional[str]:
    if not event_id:
        return None
    cur = conn.cursor()
    for img_type in preferred_types:
        cur.execute("SELECT url FROM event_images WHERE event_id=? AND img_type=? LIMIT 1", (event_id, img_type))
        row = cur.fetchone()
        if row:
            return row["url"]
    cur.execute("SELECT url FROM event_images WHERE event_id=? LIMIT 1", (event_id,))
    row = cur.fetchone()
    return row["url"] if row else None

def build_xmltv(conn: sqlite3.Connection, xml_path: str):
    lanes = get_lanes(conn)
    lane_events = get_lane_events(conn)
    print(f"XMLTV: {len(lanes)} lanes, {len(lane_events)} events")
    
    events_by_lane: Dict[int, List[Dict]] = {}
    for row in lane_events:
        events_by_lane.setdefault(row["lane_id"], []).append(row)
    
    tv = ET.Element("tv")
    
    for lane_id, name, logical_number in lanes:
        chan = ET.SubElement(tv, "channel", id=f"peacock.lane.{lane_id}")
        dn = ET.SubElement(chan, "display-name")
        dn.text = f"{name} ({logical_number})"
    
    for lane_id, name, logical_number in lanes:
        rows = events_by_lane.get(lane_id, [])
        if not rows:
            continue
        
        for row in rows:
            start = parse_iso(row["start_utc"])
            stop = parse_iso(row["end_utc"])
            if stop <= start:
                stop = start + timedelta(minutes=1)
            
            prog = ET.SubElement(
                tv, "programme",
                channel=f"peacock.lane.{lane_id}",
                start=xmltv_time(start),
                stop=xmltv_time(stop)
            )
            
            is_placeholder = bool(row["is_placeholder"])
            
            # Title
            if is_placeholder:
                title_text = "Nothing Scheduled"
            else:
                title_text = row.get("event_title") or row.get("title") or "Peacock Sports"
            
            title_el = ET.SubElement(prog, "title")
            title_el.text = title_text
            
            # Description (rich synopsis)
            if not is_placeholder:
                desc_text = row.get("synopsis") or row.get("synopsis_brief")
                if desc_text:
                    desc_el = ET.SubElement(prog, "desc")
                    desc_el.text = desc_text
            
            # Categories
            if not is_placeholder:
                cat1 = ET.SubElement(prog, "category")
                cat1.text = "Sports"
                
                cat2 = ET.SubElement(prog, "category")
                cat2.text = "Sports event"
                
                # Add genres from JSON
                genres_json = row.get("genres_json")
                if genres_json:
                    try:
                        genres = json.loads(genres_json)
                        if isinstance(genres, list):
                            for g in genres:
                                if g:
                                    cat_el = ET.SubElement(prog, "category")
                                    cat_el.text = str(g)
                    except:
                        pass
                
                # Add channel as category if available
                if row.get("channel_name"):
                    cat_ch = ET.SubElement(prog, "category")
                    cat_ch.text = row["channel_name"]
            
            # Icon/Image
            if not is_placeholder and row.get("event_id"):
                img_url = get_event_images(
                    conn,
                    row["event_id"],
                    ["landscape", "scene169", "titleArt169", "scene34"]
                )
                if img_url:
                    icon = ET.SubElement(prog, "icon")
                    icon.set("src", img_url)
            
            # Live flag
            if not is_placeholder:
                live = ET.SubElement(prog, "live")
                live.text = "1"
    
    xml_str = minidom.parseString(ET.tostring(tv)).toprettyxml(indent="  ")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"Wrote XMLTV: {xml_path}")

def build_m3u(conn: sqlite3.Connection, m3u_path: str):
    lanes = get_lanes(conn)
    lane_events = get_lane_events(conn)
    print(f"M3U: {len(lanes)} lanes, {len(lane_events)} events")
    
    events_by_lane: Dict[int, List[Dict]] = {}
    for row in lane_events:
        events_by_lane.setdefault(row["lane_id"], []).append(row)
    
    now = datetime.now(timezone.utc)
    all_rows = [row for rows in events_by_lane.values() for row in rows]
    real_rows = [r for r in all_rows if not r["is_placeholder"] and r.get("pvid")]
    real_rows_sorted = sorted(real_rows, key=lambda r: parse_iso(r.get("start_utc") or ""))
    
    global_upcoming = None
    for r in real_rows_sorted:
        start_dt = parse_iso(r.get("start_utc") or "")
        if start_dt >= now:
            global_upcoming = r
            break
    if not global_upcoming and real_rows_sorted:
        global_upcoming = real_rows_sorted[0]
    
    if not global_upcoming:
        print("M3U: no real events found")
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
        return
    
    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for lane_id, name, logical_number in lanes:
            rows = events_by_lane.get(lane_id, [])
            upcoming_real = None
            if rows:
                for row in rows:
                    if row["is_placeholder"]:
                        continue
                    start_iso = row["start_utc"]
                    if start_iso and parse_iso(start_iso) >= now:
                        upcoming_real = row
                        break
                if not upcoming_real:
                    for row in rows:
                        if not row["is_placeholder"]:
                            upcoming_real = row
                            break
            if not upcoming_real:
                upcoming_real = global_upcoming
            
            if not upcoming_real:
                continue
            
            pvid = upcoming_real.get("pvid")
            if not pvid:
                continue
            
            deeplink_payload = {"pvid": pvid, "type": "PROGRAMME", "action": "PLAY"}
            deeplink_json = json.dumps(deeplink_payload, separators=(",", ":"))
            deeplink_url = f"https://www.peacocktv.com/deeplink?deeplinkData={urllib.parse.quote(deeplink_json, safe='')}"
            
            f.write(
                f'#EXTINF:-1 tvg-id="peacock.lane.{lane_id}" '
                f'tvg-name="{name}" '
                f'tvg-chno="{logical_number}" '
                f'group-title="Peacock Lanes" tvg-logo="",{name}\n'
            )
            f.write(f"{deeplink_url}\n\n")
    
    print(f"Wrote M3U: {m3u_path}")

def main():
    script_dir = Path(__file__).resolve().parent
    if script_dir.name == 'bin':
        repo_root = script_dir.parent
        default_db = str(repo_root / 'data' / 'peacock_events.db')
        default_xml = str(repo_root / 'out' / 'peacock_lanes.xml')
        default_m3u = str(repo_root / 'out' / 'peacock_lanes.m3u')
    else:
        default_db = "peacock_events.db"
        default_xml = "peacock_lanes.xml"
        default_m3u = "peacock_lanes.m3u"
    
    env_db = os.getenv("PEACOCK_DB_PATH")
    env_xml = os.getenv("PEACOCK_XML_PATH")
    env_m3u = os.getenv("PEACOCK_M3U_PATH")
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=env_db or default_db)
    ap.add_argument("--xml", default=env_xml or default_xml)
    ap.add_argument("--m3u", default=env_m3u or default_m3u)
    args = ap.parse_args()
    
    Path(args.xml).parent.mkdir(parents=True, exist_ok=True)
    Path(args.m3u).parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Using DB: {args.db}")
    print(f"XMLTV out: {args.xml}")
    print(f"M3U out: {args.m3u}")
    
    conn = get_conn(args.db)
    ok, missing = check_tables(conn, ["lanes", "lane_events", "events"])
    if not ok:
        print(f"\nERROR: Missing tables: {', '.join(missing)}")
        print("\nRun: ./bin/peacock_refresh_all.py")
        return 1
    
    build_xmltv(conn, args.xml)
    build_m3u(conn, args.m3u)
    conn.close()
    print("Export complete")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

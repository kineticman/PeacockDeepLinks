#!/usr/bin/env python3
"""peacock_refresh_all.py - Complete refresh: ingest → build → export"""
import os, argparse, subprocess, sys
from pathlib import Path

def find_script_dir() -> Path:
    script_path = Path(__file__).resolve()
    return script_path.parent if script_path.parent.name == 'bin' else Path.cwd()

def find_repo_root() -> Path:
    script_dir = find_script_dir()
    return script_dir.parent if script_dir.name == 'bin' else script_dir

def run_command(cmd: list, description: str) -> int:
    print(f"\n{'='*80}\n{description}\n{'='*80}")
    print(f"Running: {' '.join(cmd)}\n")
    try:
        proc = subprocess.run(cmd, check=False)
        return proc.returncode
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 1

def main():
    repo_root = find_repo_root()
    script_dir = find_script_dir()

    default_db = repo_root / "data" / "peacock_events.db"
    default_xml = repo_root / "out" / "peacock_lanes.xml"
    default_m3u = repo_root / "out" / "peacock_lanes.m3u"

    env_db = os.getenv("PEACOCK_DB_PATH")
    env_slug = os.getenv("PEACOCK_SLUG")
    env_lanes = os.getenv("PEACOCK_LANES")
    env_days = os.getenv("PEACOCK_DAYS_AHEAD")
    env_xml = os.getenv("PEACOCK_XML_PATH")
    env_m3u = os.getenv("PEACOCK_M3U_PATH")
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(env_db or default_db))
    ap.add_argument("--slug", default=env_slug or "/sports/live-and-upcoming")
    ap.add_argument("--lanes", type=int, default=int(env_lanes) if env_lanes else 10)
    ap.add_argument("--days-ahead", type=int, default=int(env_days) if env_days else 7)
    ap.add_argument("--xml", default=str(env_xml or default_xml))
    ap.add_argument("--m3u", default=str(env_m3u or default_m3u))
    ap.add_argument("--skip-ingest", action="store_true")
    args = ap.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    
    print("="*80)
    print("PEACOCK LANES COMPLETE REFRESH")
    print("="*80)
    print(f"Repository: {repo_root}")
    print(f"Database: {args.db}")
    print(f"Lanes: {args.lanes}")
    print(f"Days ahead: {args.days_ahead}")
    print(f"Output: {args.xml}, {args.m3u}")
    
    if not args.skip_ingest:
        if run_command(
            [sys.executable, str(script_dir / "peacock_ingest_atom.py"), "--db", args.db, "--slug", args.slug],
            "STEP 1: Ingest from Peacock API",
        ) != 0:
            return 1
    else:
        print("\n⚠ Skipping API ingest")
    
    if run_command(
        [
            sys.executable,
            str(script_dir / "peacock_build_lanes.py"),
            "--db",
            args.db,
            "--lanes",
            str(args.lanes),
            "--days-ahead",
            str(args.days_ahead),
        ],
        "STEP 2: Build lanes",
    ) != 0:
        return 1
    
    if run_command(
        [
            sys.executable,
            str(script_dir / "peacock_export_from_db.py"),
            "--db",
            args.db,
            "--xml",
            args.xml,
            "--m3u",
            args.m3u,
        ],
        "STEP 3: Export XMLTV/M3U",
    ) != 0:
        return 1
    
    print("\n" + "="*80)
    print("✓ COMPLETE REFRESH SUCCESSFUL")
    print("="*80)
    print(f"\nGenerated:\n  - {args.xml}\n  - {args.m3u}")
    print(f"\nDatabase: {args.db}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

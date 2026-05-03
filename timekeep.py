#!/usr/bin/env python3
import sqlite3
import argparse
from datetime import datetime
import sys
import os
import shutil
import glob

DB_PATH = os.path.expanduser("~/.local/share/timekeep/timekeep.sqlite")
BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), "backups")
BACKUP_KEEP = 30  # number of backups to retain

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def backup_db():
    """Back up the database, keeping only the most recent BACKUP_KEEP copies."""
    if not os.path.exists(DB_PATH):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"timekeep_{timestamp}.sqlite")
    shutil.copy2(DB_PATH, backup_path)

    # Prune old backups
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "timekeep_*.sqlite")))
    for old in backups[:-BACKUP_KEEP]:
        os.remove(old)


def init_db():
    """Initialize SQLite database with required table"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS time_entries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  label TEXT NOT NULL,
                  start_time TIMESTAMP,
                  end_time TIMESTAMP)"""
    )
    conn.commit()
    conn.close()


def get_status():
    """Show all active timers and their elapsed time"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get all active sessions (where end_time is NULL)
    c.execute(
        """
        SELECT label, start_time
        FROM time_entries
        WHERE end_time IS NULL
    """
    )

    active_sessions = c.fetchall()
    conn.close()

    if not active_sessions:
        print("No active timers")
        return

    print("\nActive timers:")
    print("-" * 50)
    current_time = datetime.now()

    for label, start_time_str in active_sessions:
        start_time = datetime.fromisoformat(start_time_str)
        elapsed = current_time - start_time
        hours = elapsed.total_seconds() / 3600
        print(
            f"{label}: running for {hours:.2f} hours (started at {start_time.strftime('%Y-%m-%d %H:%M:%S')})"
        )


def start_time(label):
    """Start timing for a given label"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check if there's already an active session
    c.execute(
        "SELECT id FROM time_entries WHERE label = ? AND end_time IS NULL", (label,)
    )
    if c.fetchone():
        print(f"Error: Active session already exists for label '{label}'")
        conn.close()
        return

    current_time = datetime.now().isoformat()
    c.execute(
        "INSERT INTO time_entries (label, start_time) VALUES (?, ?)",
        (label, current_time),
    )
    conn.commit()
    conn.close()
    print(f"Started timing for '{label}'")


def stop_time(label):
    """Stop timing for a given label"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    current_time = datetime.now().isoformat()

    # Find the active session and update it
    c.execute(
        """UPDATE time_entries
                 SET end_time = ?
                 WHERE label = ?
                 AND end_time IS NULL""",
        (current_time, label),
    )

    if c.rowcount == 0:
        print(f"Error: No active session found for label '{label}'")
    else:
        print(f"Stopped timing for '{label}'.")

    conn.commit()
    conn.close()


def get_hours(month, sek_per_hour):
    """Get total hours for a given month"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        SELECT label,
               SUM((julianday(end_time) - julianday(start_time)) * 24) as hours
        FROM time_entries
        WHERE strftime('%m', start_time) = ?
        AND end_time IS NOT NULL
        GROUP BY label
    """,
        (str(month).zfill(2),),
    )

    results = c.fetchall()
    conn.close()

    if not results:
        print(f"No entries found for month {month}")
        return

    print(f"\nHours for month {month}:")
    print("-" * 30)
    for label, hours in results:
        netto_sek = int(hours * sek_per_hour * 0.75 * 0.7)
        print(f"{label}: {hours:.2f} hours = {netto_sek} SEK")


def main():
    parser = argparse.ArgumentParser(description="Time tracking tool")
    parser.add_argument(
        "action", choices=["start", "stop", "hours", "status"], help="Action to perform"
    )
    parser.add_argument(
        "-l", "--label", help="Label for the time entry", default="work"
    )
    parser.add_argument(
        "-m",
        "--month",
        type=int,
        default=datetime.now().month,
        help="Month number (1-12)",
    )
    parser.add_argument(
        "--sek-per-hour",
        "--sek",
        type=int,
        default=350,
        help="SEK per hour",
    )

    args = parser.parse_args()

    # Initialize database and back it up
    init_db()
    backup_db()

    if args.action == "start":
        if not args.label:
            print("Error: Label (-l) is required for start action")
            sys.exit(1)
        start_time(args.label)

    elif args.action == "stop":
        if not args.label:
            print("Error: Label (-l) is required for stop action")
            sys.exit(1)
        stop_time(args.label)

    elif args.action == "hours":
        if not args.month or not (1 <= args.month <= 12):
            print("Error: Valid month (-m) is required for hours action")
            sys.exit(1)
        get_hours(args.month, args.sek_per_hour)

    elif args.action == "status":
        get_status()


if __name__ == "__main__":
    main()


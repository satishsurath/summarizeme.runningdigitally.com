#!/usr/bin/env python3
"""Database backup utility for SummarizeMe.

Backs up the PostgreSQL database to a timestamped SQL file.
Supports local and remote databases.

Usage:
    python backup_database.py                          # Backup to ./backups/
    python backup_database.py --output /path/to/       # Custom output directory
    python backup_database.py --compress               # Compress with gzip
    python backup_database.py --retention 30           # Keep 30 days of backups
    python backup_database.py --dry-run                # Show what would be done

Environment variables:
    DATABASE_URL      PostgreSQL connection string (required)
    BACKUP_DIR        Backup output directory (default: ./backups)
    BACKUP_RETENTION  Days to keep backups (default: 30)
"""

import argparse
import gzip
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def get_backup_dir() -> Path:
    """Get the backup directory, creating it if necessary."""
    backup_dir = Path(os.getenv("BACKUP_DIR", "./backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_database_url() -> str:
    """Get the database URL from environment."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable is not set.")
        sys.exit(1)
    return db_url


def parse_database_url(db_url: str) -> dict:
    """Parse a PostgreSQL connection string into components."""
    # Format: postgresql://user:password@host:port/database
    import re

    match = re.match(r"postgresql://(?:(.*):(.*)@)?([^:]+)(?::(\d+))?/(.+)", db_url)
    if not match:
        print(f"ERROR: Invalid DATABASE_URL format: {db_url}")
        sys.exit(1)

    user, password, host, port, database = match.groups()
    return {
        "user": user or "summarizeme",
        "password": password or "",
        "host": host or "localhost",
        "port": port or "5432",
        "database": database or "summarizeme",
    }


def create_backup(
    output_dir: Path,
    compress: bool = False,
    dry_run: bool = False,
) -> Path:
    """Create a database backup."""
    db_url = get_database_url()
    db_info = parse_database_url(db_url)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"summarizeme_{timestamp}.sql"
    if compress:
        filename += ".gz"

    output_path = output_dir / filename

    if dry_run:
        print(f"Would create backup: {output_path}")
        return output_path

    print(f"Backing up database '{db_info['database']}' on {db_info['host']}...")

    # Build pg_dump command
    env = os.environ.copy()
    if db_info["password"]:
        env["PGPASSWORD"] = db_info["password"]

    cmd = [
        "pg_dump",
        "-h",
        db_info["host"],
        "-p",
        db_info["port"],
        "-U",
        db_info["user"],
        "-d",
        db_info["database"],
        "--no-owner",
        "--no-privileges",
        "--clean",
        "--if-exists",
    ]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            print(f"ERROR: pg_dump failed: {result.stderr}")
            sys.exit(1)

        sql_content = result.stdout

        if compress:
            output_path.write_bytes(gzip.compress(sql_content.encode()))
            print(f"Backup created (compressed): {output_path}")
            print(f"Size: {output_path.stat().st_size:,} bytes")
        else:
            output_path.write_text(sql_content)
            print(f"Backup created: {output_path}")
            print(f"Size: {output_path.stat().st_size:,} bytes")

        return output_path

    except subprocess.TimeoutExpired:
        print("ERROR: pg_dump timed out after 5 minutes.")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: pg_dump not found. Install PostgreSQL client tools.")
        print("  macOS: brew install postgresql")
        print("  Ubuntu: sudo apt-get install postgresql-client")
        sys.exit(1)


def cleanup_old_backups(
    output_dir: Path,
    retention_days: int = 30,
    dry_run: bool = False,
) -> int:
    """Remove backups older than retention_days."""
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0

    for backup_file in sorted(output_dir.glob("summarizeme_*.sql*")):
        # Parse timestamp from filename
        try:
            ts_str = backup_file.stem.replace("summarizeme_", "")
            backup_date = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            if backup_date < cutoff:
                if dry_run:
                    print(f"Would remove: {backup_file}")
                else:
                    backup_file.unlink()
                    print(f"Removed: {backup_file}")
                removed += 1
        except ValueError:
            # Skip files that don't match the expected format
            continue

    if dry_run:
        print(f"\nDry run: {removed} backup(s) would be removed.")
    else:
        print(f"\nCleaned up {removed} old backup(s).")

    return removed


def main():
    parser = argparse.ArgumentParser(description="SummarizeMe database backup utility")
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Compress backup with gzip",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output directory (default: ./backups)",
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=30,
        help="Days to keep backups (default: 30)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Also clean up old backups",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Only clean up old backups, skip creating new backup",
    )

    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else get_backup_dir()

    if not args.no_backup:
        create_backup(output_dir, args.compress, args.dry_run)

    if args.cleanup or args.dry_run:
        cleanup_old_backups(output_dir, args.retention, args.dry_run)


if __name__ == "__main__":
    main()

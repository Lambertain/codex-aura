#!/usr/bin/env python3
"""
Neo4j Backup Script
Creates a backup of the Neo4j database using neo4j-admin dump.
"""

import os
import sys
import subprocess
import datetime
from pathlib import Path


def run_backup(container_name: str = "codex-aura-neo4j-1", backup_dir: str = "./backups"):
    """Run Neo4j backup using docker exec."""
    try:
        # Create backup directory if it doesn't exist
        Path(backup_dir).mkdir(exist_ok=True)

        # Generate timestamp for backup file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"neo4j_backup_{timestamp}.dump"
        backup_path = f"{backup_dir}/{backup_file}"

        # Run neo4j-admin dump inside the container
        cmd = [
            "docker", "exec", container_name,
            "neo4j-admin", "database", "dump", "neo4j",
            "--to-path", f"/backups/{backup_file}"
        ]

        print(f"🚀 Starting Neo4j backup to {backup_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ Backup completed successfully: {backup_path}")
            return True
        else:
            print(f"❌ Backup failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Backup error: {e}")
        return False


def main():
    """Main function to run backup."""
    container_name = os.getenv("NEO4J_CONTAINER", "codex-aura-neo4j-1")
    backup_dir = os.getenv("BACKUP_DIR", "./backups")

    success = run_backup(container_name, backup_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Neo4j Restore Script
Restores a Neo4j database from a backup dump using neo4j-admin load.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_restore(backup_file: str, container_name: str = "codex-aura-neo4j-1"):
    """Run Neo4j restore using docker exec."""
    try:
        # Check if backup file exists
        if not Path(backup_file).exists():
            print(f"❌ Backup file not found: {backup_file}")
            return False

        # Get backup filename
        backup_filename = Path(backup_file).name

        # Copy backup file to container
        print(f"📋 Copying backup file to container...")
        copy_cmd = ["docker", "cp", backup_file, f"{container_name}:/backups/{backup_filename}"]
        result = subprocess.run(copy_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Failed to copy backup file: {result.stderr}")
            return False

        # Stop Neo4j before restore
        print("🛑 Stopping Neo4j...")
        stop_cmd = ["docker", "exec", container_name, "neo4j", "stop"]
        subprocess.run(stop_cmd, capture_output=True)

        # Run neo4j-admin load
        print(f"🔄 Restoring from backup: {backup_filename}")
        restore_cmd = [
            "docker", "exec", container_name,
            "neo4j-admin", "database", "load", "neo4j",
            "--from-path", f"/backups/{backup_filename}",
            "--overwrite-destination=true"
        ]

        result = subprocess.run(restore_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Restore failed: {result.stderr}")
            return False

        # Start Neo4j after restore
        print("▶️ Starting Neo4j...")
        start_cmd = ["docker", "exec", container_name, "neo4j", "start"]
        subprocess.run(start_cmd, capture_output=True)

        print("✅ Restore completed successfully")
        return True

    except Exception as e:
        print(f"❌ Restore error: {e}")
        return False


def main():
    """Main function to run restore."""
    parser = argparse.ArgumentParser(description="Restore Neo4j database from backup")
    parser.add_argument("backup_file", help="Path to the backup dump file")
    parser.add_argument("--container", default=os.getenv("NEO4J_CONTAINER", "codex-aura-neo4j-1"),
                       help="Docker container name")

    args = parser.parse_args()

    success = run_restore(args.backup_file, args.container)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
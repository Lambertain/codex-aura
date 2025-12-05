"""Health check functionality for codex-aura."""

import os
import time
import psutil
from typing import Dict, Any
from pathlib import Path

from .storage.sqlite import SQLiteStorage
from .analyzer.python import PythonAnalyzer
from .metrics import HEALTH_CHECKS_TOTAL


class HealthChecker:
    """Health checker for various system components."""

    def __init__(self):
        self.start_time = time.time()
        self.storage = SQLiteStorage()

    def get_uptime_seconds(self) -> int:
        """Get service uptime in seconds."""
        return int(time.time() - self.start_time)

    def check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            # Try to list graphs as a connectivity test
            graphs = self.storage.list_graphs()
            return {"status": "ok", "graphs_count": len(graphs)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def check_analyzer(self) -> Dict[str, Any]:
        """Check analyzer functionality."""
        try:
            analyzer = PythonAnalyzer()
            # Simple test - check if analyzer can be instantiated
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def check_disk_space(self) -> Dict[str, Any]:
        """Check disk space availability."""
        try:
            # Check current directory disk usage
            current_path = Path.cwd()
            stat = os.statvfs(current_path)
            total = stat.f_bsize * stat.f_blocks
            free = stat.f_bsize * stat.f_bavail
            used_percent = ((total - free) / total) * 100

            # Consider unhealthy if less than 10% free space
            if used_percent > 90:
                return {
                    "status": "error",
                    "total_gb": round(total / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "used_percent": round(used_percent, 2),
                    "error": "Low disk space"
                }

            return {
                "status": "ok",
                "total_gb": round(total / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "used_percent": round(used_percent, 2)
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def check_memory(self) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            return {
                "status": "ok",
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_percent": round(memory.percent, 2)
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def quick_health(self) -> Dict[str, Any]:
        """Quick health check - just basic service status."""
        HEALTH_CHECKS_TOTAL.labels(endpoint="quick", status="ok").inc()
        return {
            "status": "healthy",
            "version": "0.1.0",
            "uptime_seconds": self.get_uptime_seconds()
        }

    def readiness_health(self) -> Dict[str, Any]:
        """Readiness check - verify service can handle requests."""
        checks = {
            "database": self.check_database(),
            "analyzer": self.check_analyzer()
        }

        all_ok = all(check.get("status") == "ok" for check in checks.values())

        HEALTH_CHECKS_TOTAL.labels(endpoint="ready", status="ok" if all_ok else "error").inc()

        return {
            "status": "ready" if all_ok else "not_ready",
            "version": "0.1.0",
            "uptime_seconds": self.get_uptime_seconds(),
            "checks": checks
        }

    def deep_health(self) -> Dict[str, Any]:
        """Deep health check - comprehensive system analysis."""
        checks = {
            "database": self.check_database(),
            "analyzer": self.check_analyzer(),
            "disk_space": self.check_disk_space(),
            "memory": self.check_memory()
        }

        all_ok = all(check.get("status") == "ok" for check in checks.values())

        HEALTH_CHECKS_TOTAL.labels(endpoint="deep", status="ok" if all_ok else "error").inc()

        return {
            "status": "healthy" if all_ok else "unhealthy",
            "version": "0.1.0",
            "uptime_seconds": self.get_uptime_seconds(),
            "checks": checks
        }


# Global health checker instance
health_checker = HealthChecker()
#!/usr/bin/env python3
"""
Neo4j Health Check Script
Checks if Neo4j database is accessible and responding.
"""

import os
import sys
import asyncio
from neo4j import AsyncGraphDatabase


async def check_neo4j_health(uri: str, user: str, password: str) -> bool:
    """Check Neo4j health by running a simple query."""
    try:
        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            if record and record["test"] == 1:
                print("✅ Neo4j is healthy")
                return True
            else:
                print("❌ Neo4j health check failed: unexpected result")
                return False
    except Exception as e:
        print(f"❌ Neo4j health check failed: {e}")
        return False
    finally:
        await driver.close()


def main():
    """Main function to run health check."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    success = asyncio.run(check_neo4j_health(uri, user, password))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
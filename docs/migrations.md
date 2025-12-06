# Database Migrations

This document describes the migration process from SQLite to Neo4j for graph storage.

## Overview

Codex Aura supports multiple storage backends. The migration process allows moving existing graphs from SQLite storage to Neo4j for improved performance and scalability.

## Schema Design

### Node Types
- **File**: Represents source code files
  - `path`: Unique file path (used as FQN)
  - `repo_id`: Repository identifier for indexing
- **Class**: Represents class definitions
  - `fqn`: Fully qualified name (unique identifier)
- **Function**: Represents function definitions
  - `fqn`: Fully qualified name (unique identifier)

All nodes inherit from base `Node` label and include additional properties like `name`, `lines`, `docstring`, etc.

### Edge Types
- `CONTAINS`: File contains Class/Function
- `IMPORTS`: File imports another File
- `EXTENDS`: Class extends another Class
- `CALLS`: Function calls another Function
- `HAS_METHOD`: Class has method Function

### Constraints and Indexes
- Unique constraints on `path` for Files, `fqn` for Classes and Functions
- Performance indexes on `repo_id` for Files and `name` for all Nodes

## Migration Process

### Prerequisites
1. Neo4j database running and accessible
2. Existing graphs in SQLite storage
3. Schema applied to Neo4j (see schema.cypher)

### Steps
1. **Apply Schema**: Run the schema.cypher file to create constraints and indexes
2. **Migrate Graphs**: Use the migration script to move individual graphs
3. **Verify**: Check that all nodes and edges were migrated successfully

### Usage

```bash
# Apply schema
python -c "
import asyncio
from codex_aura.storage.neo4j_client import Neo4jClient

async def apply():
    client = Neo4jClient()
    await client.apply_schema('scripts/schema.cypher')
    await client.close()

asyncio.run(apply())
"

# Migrate specific graph
python scripts/migrate_to_neo4j.py <graph_id>
```

### Batch Migration
For large-scale migrations, run the script for each graph ID:

```bash
# List all graphs in SQLite
python -c "
from codex_aura.storage.sqlite import SQLiteStorage
storage = SQLiteStorage()
graphs = storage.list_graphs()
for g in graphs:
    print(g['id'])
" | xargs -I {} python scripts/migrate_to_neo4j.py {}
```

## Verification

After migration, verify the data:

```cypher
// Count nodes by type
MATCH (n:Node)
RETURN labels(n), count(n)

// Count relationships by type
MATCH ()-[r]->()
RETURN type(r), count(r)

// Verify specific graph
MATCH (n:Node {repo_id: 'your-repo'})
RETURN count(n) as nodes
```

## Rollback

If migration fails, you can:
1. Delete migrated data from Neo4j
2. Re-run the migration script
3. Keep SQLite as backup until verification is complete

## Performance Considerations

- Migration uses batch processing (1000 items per batch)
- Large graphs may take significant time
- Monitor Neo4j memory usage during migration
- Consider running migrations during low-traffic periods
// Cypher schema for Codex Aura code graph
// This schema defines constraints and indexes for efficient graph operations

// Node type constraints - ensure uniqueness
CREATE CONSTRAINT file_path IF NOT EXISTS
FOR (f:File) REQUIRE f.path IS UNIQUE;

CREATE CONSTRAINT class_fqn IF NOT EXISTS
FOR (c:Class) REQUIRE c.fqn IS UNIQUE;

CREATE CONSTRAINT function_fqn IF NOT EXISTS
FOR (fn:Function) REQUIRE fn.fqn IS UNIQUE;

// Performance indexes
CREATE INDEX file_repo IF NOT EXISTS FOR (f:File) ON (f.repo_id);
CREATE INDEX node_name IF NOT EXISTS FOR (n:Node) ON (n.name);

// Edge types (relationships)
// File contains Class/Function
// File imports File
// Class extends Class
// Function calls Function
// Class has method Function

// Note: Relationships are created dynamically during migration
// No explicit constraints needed for relationships in this schema
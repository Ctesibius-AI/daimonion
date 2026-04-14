# Database Design

## When Active
When designing database schemas, choosing database engines, or planning data models.

## Instructions
- Start with the domain model: identify entities, relationships, and access patterns before choosing technology
- **SQL (PostgreSQL, SQLite)**: use for structured data with complex queries, transactions, referential integrity
- **NoSQL (MongoDB, Redis, DynamoDB)**: use for flexible schemas, high write throughput, key-value access patterns
- Normalize to 3NF by default; denormalize intentionally for read-heavy queries with documented trade-offs
- Every table gets: primary key (prefer UUIDs or ULID for distributed systems), created_at, updated_at timestamps
- Use foreign keys and constraints to enforce data integrity at the database level
- Index columns used in WHERE, JOIN, ORDER BY; avoid over-indexing write-heavy tables
- Design for soft deletes (deleted_at column) in production systems
- Use migrations for all schema changes; never modify schemas manually in production
- Plan for multi-tenancy early: row-level (tenant_id column) vs schema-level vs database-level
- Document enum values, status transitions, and business rules as CHECK constraints or comments
- Consider read replicas, partitioning, and sharding strategies for scale

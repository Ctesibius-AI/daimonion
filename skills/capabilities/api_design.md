# API Design

## When Active
When designing REST APIs, GraphQL schemas, or service interfaces.

## Instructions
- **REST conventions**: use nouns for resources, HTTP verbs for actions; plural endpoints (`/users`, not `/user`)
- Standard HTTP methods: GET (read), POST (create), PUT (full update), PATCH (partial update), DELETE (remove)
- Return appropriate status codes: 200 (ok), 201 (created), 204 (no content), 400 (bad request), 401 (unauthorized), 403 (forbidden), 404 (not found), 422 (validation), 429 (rate limit), 500 (server error)
- Version APIs in the URL path (`/v1/`) or Accept header; never break existing clients
- Use consistent error response format: `{ "error": { "code": "...", "message": "..." } }`
- Pagination: use cursor-based for large datasets, offset-based for simple cases; include total count and next/prev links
- Filter, sort, and field selection via query parameters: `?status=active&sort=-created_at&fields=id,name`
- Authenticate via Bearer tokens (JWT or opaque); use API keys only for server-to-server
- Rate limit all endpoints; return `X-RateLimit-*` headers
- **GraphQL**: define clear types with descriptions; avoid deeply nested queries; implement DataLoader for N+1 prevention
- Document with OpenAPI/Swagger (REST) or schema introspection (GraphQL)
- Validate all inputs at the boundary; sanitize outputs

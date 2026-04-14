# MCP Server Development

## When Active
When building, designing, or scaffolding an MCP (Model Context Protocol) server.

## Instructions
- Start with discovery, not code — understand the use case first
- Key questions: what does it connect to? Who will use it? How many actions? Need user input mid-call? What auth?
- **Deployment models** (ranked):
  - Remote streamable-HTTP (default; zero install friction, works everywhere)
  - Elicitation (structured user input, no UI code; check client capability)
  - MCP app (rich interactive UI via iframe widgets)
  - MCPB (bundled local server; only when local machine access required)
  - Local stdio (prototypes only; not for distribution)
- **Tool design patterns**:
  - <15 actions: one tool per action with tight schemas
  - Dozens+: search + execute pattern to keep context lean
  - Hybrid: promote top 3-5 actions, long tail behind search/execute
- **Frameworks**: TypeScript SDK (`@modelcontextprotocol/sdk`) or FastMCP 3.x (Python)
- Other primitives: Resources (browsable context), Prompts (canned workflows), Sampling (LLM in tool logic)

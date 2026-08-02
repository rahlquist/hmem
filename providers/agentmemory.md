# AgentMemory — Most Comprehensive MCP Memory Toolkit (53 Tools)

## End Goal
Provide the most comprehensive memory toolkit for any AI agent framework — 53 tools, 6 resources, 3 prompts, and 15 skills — with a real-time viewer and full lifecycle hooks for deep agent integration.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Server-side (configurable backend; can use SQLite, PostgreSQL, or custom) |
| **Database type** | Configurable — depends on deployment |
| **Data at rest** | Depends on backend; Docker deployment supports volume encryption |
| **Data in transit** | TLS for MCP HTTP endpoint |
| **Authentication** | API key for MCP server |
| **Encryption** | No client-side encryption specified; relies on transport + backend |
| **Compliance** | Not publicly documented |
| **Multi-tenant** | Yes — server can serve multiple connected agents |

## How It Works
AgentMemory is a standalone memory server that runs on localhost:3111. It provides the largest surface area of any memory MCP server — 53 distinct tools covering every aspect of memory management. It supports both MCP tool-calling mode (for Hermes and other agents) and a deeper 6-hook integration mode (pre-LLM context injection, turn capture, MEMORY.md mirroring, system prompt block) for Hermes specifically. The system includes a real-time web viewer at port 3113 for monitoring memory operations.

## Hermes Integration
- **MCP server**: Primary integration — connects via `mcp_servers` in `~/.hermes/config.yaml`
- **6-hook plugin**: Deeper integration via `~/.hermes/plugins/agentmemory/` — pre-LLM context injection, turn capture, MEMORY.md mirroring, system prompt block
- **Config**:
  ```yaml
  mcp_servers:
    agentmemory:
      command: npx
      args: ["-y", "@agentmemory/mcp"]
  memory:
    provider: agentmemory
  ```
- **Health check**: `curl http://localhost:3111/agentmemory/health`
- **Viewer**: http://localhost:3113

## Install Type
- **Standalone MCP server** (primary) + Hermes 6-hook plugin (deeper integration)
- Server runs as a separate process; multiple Hermes instances can connect to the same server
- **Interconnects instances**: The server is a shared memory layer — all connected agents share the same memory store
- Docker deployment supported

## Overflow / Retention
- Server manages its own storage backend
- 6-hook mode captures memory automatically at multiple lifecycle points
- Real-time viewer (port 3113) provides visibility into all memory operations
- Configurable retention via server settings

## Unique Features
- **53 tools**: The most comprehensive MCP memory toolkit for any agent
- **6 resources + 3 prompts + 15 skills**: Richest surface area of any memory provider
- **Real-time viewer**: Web UI at port 3113 for monitoring memory operations
- **6-hook integration**: Pre-LLM context injection, turn capture, MEMORY.md mirroring, system prompt block — deeper than standard MCP
- **Docker deployment**: One-command setup via Docker Compose
- **Worker extensibility**: Add workers for pubsub, cron consolidation, queue, observability, sandbox, database
- **Health endpoint**: Standard HTTP health check
- **Cross-framework**: Works with Claude Code, Codex, Cursor, Gemini CLI, Copilot CLI, Hermes

## Compatible Agents
Hermes, Claude Code, Codex, Cursor, Gemini CLI, Copilot CLI — any MCP-compatible agent

## Pricing
- **Free**: Self-hosted, open-source
- **No cloud tier**: Local server only
- **Infrastructure costs**: Self-hosted

## Public Metrics
- GitHub: ★ not prominently listed on hermesatlas (check repo directly)
- 53 tools is the most comprehensive toolkit among memory providers
- Weekly growth: Not tracked on hermesatlas

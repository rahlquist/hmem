# Honcho — User Modeling with Dialectic Reasoning

## End Goal
Build persistent user models for AI agents that understand each user's preferences, working style, and communication patterns — enabling genuinely personalized interactions that improve over months of use.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Honcho Cloud (PostgreSQL) or self-hosted instance |
| **Database type** | Relational (PostgreSQL) |
| **Data at rest** | Encrypted by PostgreSQL on self-hosted; cloud encryption managed by Honcho |
| **Data in transit** | TLS for all API calls |
| **Authentication** | OAuth + API key from [app.honcho.dev](https://app.honcho.dev/) |
| **Encryption** | No client-side encryption; relies on transport + DB-level |
| **Compliance** | Not publicly documented |
| **Multi-tenant** | Yes — cloud supports multiple users/agents |

## How It Works
Honcho is a memory library focused on building a persistent, structured model of each user. It uses **dialectic reasoning** — a structured debate-like process where the agent surfaces and tests its understanding of the user against new evidence. The system maintains "peer cards" (representations of other agents or users) and "session summaries" that give the agent awareness of what has already been discussed. Unlike fact-storage systems, Honcho's primary output is a **user model** — a dynamic representation of preferences, tendencies, and working patterns.

## Hermes Integration
- **Native plugin**: `memory.provider: honcho` in `~/.hermes/config.yaml`
- **Setup**: `hermes memory setup` → select "honcho"
- **Legacy**: `hermes honcho setup` (older command still works)
- **Config**: Honcho Cloud account or self-hosted instance
- **Auth**: API key from [app.honcho.dev](https://app.honcho.dev/)
- **Tools**: User model management, session-scoped context injection, semantic search

## Install Type
- **Hermes native plugin** (primary) + MCP server (alternative)
- Cloud-synced user models across instances (when using Honcho Cloud)
- Self-hosted: isolated per instance

## Overflow / Retention
- Cloud tier: managed retention policies
- Self-hosted: bounded by your infrastructure
- User model has a finite representation size — older signals are naturally deprioritized by the dialectic reasoning engine
- Session-scoped context injection prevents unbounded growth

## Unique Features
- **Dialectic reasoning**: Structured debate-like process tests and refines user understanding
- **User model building**: Not just storing facts — building a persistent representation of the user
- **Peer cards**: Multi-agent awareness — each agent has its own view of the user
- **Session summaries**: Agent knows what was already discussed in prior sessions
- **Cross-session context injection**: User model is automatically injected into system prompts
- **Self-hosted option**: Free self-hosted instance available

## Compatible Agents
Hermes, Claude, any MCP-compatible agent

## Pricing
- **Self-hosted**: Free (open-source)
- **Cloud**: Honcho pricing (see app.honcho.dev)
- **Free credits**: $100 free credits for cloud tier

## Public Metrics
- GitHub: ★ 6.4K (plastic-labs/honcho)
- Weekly growth: +142 stars/wk
- Primary use case: Multi-agent systems with cross-session user modeling

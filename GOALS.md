hmem — Project Goals
====================

Project: hmem (Hermes Memory Provider Comparison)
Repository: /home/rahlquist/hmem
Created: 2026-07-31

## Goal

Build a comprehensive, community-maintained comparison of memory add-ons and providers compatible with Hermes Agent. The repository serves as a reference for selecting, configuring, and evaluating memory systems for Hermes-based AI agents.

## Scope

- Catalogue all known memory providers and add-ons for Hermes Agent
- Include both MCP servers and native Hermes memory provider plugins
- Cover free and commercial options; include pricing where applicable
- Document features that differentiate providers (not just basic "saves things")
- Include public metrics (GitHub stars, benchmark scores, weekly growth)
- Document cross-agent compatibility (Claude, Codex, Cursor, Hermes, OpenClaw, Gemini, etc.)

## Repository Structure

- `README.md` — Common comparison table with all providers side-by-side
- `providers/<name>.md` — Individual specification page per provider
  - End goal, how it works, Hermes integration, install type (mono vs singlet)
  - Storage backend, security posture, overflow/retention behavior
  - Unique features, compatible agents, pricing, public metrics
- `.scan/` — Nightly scanner infrastructure
  - `scanner.py` — Script to check GitHub topics, HermesAtlas, and awesome-hermes-agent for new providers
  - `.scan_cache/` — Cached scan results and diff log

## Key Design Decisions

1. Only one external memory provider can be active at a time in Hermes (built-in MEMORY.md/USER.md is always active alongside it)
2. Each provider spec page covers storage and security details — these are critical differentiators
3. The comparison table includes columns for: Storage type, Security posture, Install type, Cost, Compatible agents, and Key differentiator
4. The nightly cron job scans for new providers and updates the chart

## Future Work

- Push to GitHub as a public repo (remote already configured, repo needs to be created)
- Add benchmark comparison data where available
- Add user-submitted reviews/ratings per provider
- Expand the scanner to also check for security advisories on existing providers
- Add a "getting started" guide for each install type (mono vs singlet)

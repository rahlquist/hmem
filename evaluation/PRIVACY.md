# hmem Pilot — Privacy Rules (Public-Safety Policy)

**Policy version:** 1.0.0  
**Applies to:** everything under `evaluation/` and every artifact produced by the pilot runner.

These rules make the pilot corpus publishable without carrying private or licensed material. They are enforced by the validator (`tools/validate_fixtures.py`, public-safety scan) and by the integration task's git-diff review.

---

## Rules

| ID | Rule |
|---|---|
| PRIV-01 | **Synthetic content only.** All scenario fixtures use invented entities, hosts, projects, values, and conversations. No real persons, addresses, credentials, file paths, hostnames, or machine identifiers. The fictional universe of each scenario is declared in its `world` block. |
| PRIV-02 | **No real conversation material.** Nothing from actual Hermes sessions may be copied into fixtures or reports. Real-world interaction *shapes* (categories, event structures) may inspire scenarios; content is rewritten with invented names and facts. |
| PRIV-03 | **No documents, binaries, or extracted text.** PDFs, DOCX files, archives, and extracted plain text from `memorypapers/` (or anywhere else) must never be committed to the repository. Public documentation cites stable DOI, arXiv, or publisher URLs only. |
| PRIV-04 | **Private seeds stay private.** Committed fixtures and manifests contain public seeds only. Private seeds are referenced by pointer (e.g. `seeds/private/<name>` outside the repo) and never by value. |
| PRIV-05 | **Credentials are synthetic and flagged.** Any invented credential-like value (API key, password, token) is clearly fictional, prefixed to be obviously synthetic (e.g. `hlab-...`), and marked `privacy.contains_credentials: true`. |
| PRIV-06 | **Redacted configs.** Run manifests record `provider.config_redacted` as a human-readable summary with secrets removed. Raw configs, tokens, and keys never appear in committed artifacts. |
| PRIV-07 | **Raw logs stay local.** Raw provider dumps and conversation logs referenced by results (`provenance.raw_log_uri`) are local-only, never committed, and subject to the operator's retention policy. |
| PRIV-08 | **Held-out cases are frozen but public.** Pilot v1 held-out scenarios are synthetic and published; "held-out" means excluded from the development/tuning loop, not hidden. Future rotating challenge sets that contain private or licensed material will be kept out of the public repository. |
| PRIV-09 | **Licensed adaptation requires citation.** Any scenario adapted from a public benchmark cites the stable source (`origin.source_ref`) and declares its license. Local copies of the source are not committed. |
| PRIV-10 | **Scan before commit.** Every fixture, manifest, and result must pass the public-safety substring scan in `tools/validate_fixtures.py` (forbidden real identifiers, local paths, and private markers) before it is committed or published. |

---

## Forbidden markers (scan list, non-exhaustive)

The validator scans fixture content for: the real repository owner's home paths (`/home/rahlquist`), local hostnames used in this environment (e.g. `hermesvm01`), real profile identifiers (e.g. `loco-bot`, `senna`), and any marker listed in the validator's `FORBIDDEN` set. The scan is a guard, not a substitute for review: a human must still review the git diff before publishing.

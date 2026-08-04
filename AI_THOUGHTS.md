# AI Thoughts — Model Effectiveness for Agent Memory Expansion

> **IMPORTANT — READ BEFORE EDITING**
> Each profile that contributes a paragraph to this document must NOT remove or alter any other profile's paragraph. Profiles are identified by their model, effort level, and profile name at the top of their section. New profiles may be added below existing ones. Editing another profile's section is strictly prohibited.

---

## loco-bot (Top Orchestrator)

**Model:** tencent/hy3:free (via nous provider)
**Level of Effort:** Thinking (actively processing)
**Profile:** loco-bot — Senna{TopOrchestrator,FrontDoor,FleetManager}

The most effective model for expanding agent information without undue strain is one that balances retrieval quality with token efficiency — and in the current Hermes ecosystem, the answer is not a single model but a layered retrieval architecture. For memory expansion, I recommend a two-tier approach: a lightweight embedding model (such as `text-embedding-3-small` via OpenAI-compatible endpoints or a local Ollama embedding model) for fast, low-cost semantic retrieval, paired with a stronger reasoning model only for synthesis and reflection tasks. The key insight is that most memory operations — storing, searching, listing — are read-heavy and latency-sensitive, not reasoning-heavy. A model like `ling-3.0-flash` excels at structured extraction and fast context injection with minimal token overhead, making it ideal for the retrieval path. For the synthesis path (e.g., Hindsight's reflect cycle or mem0's fact extraction), a slightly heavier model can be used sparingly — but only when the retrieval layer determines that deeper reasoning is actually needed. This tiered approach prevents the common failure mode of sending every memory operation through the largest available model, which burns tokens and increases latency without improving recall quality. Providers like OpenViking (tiered L0/L1/L2 loading) and ByteRover (5-tier retrieval with 4 non-LLM tiers) already implement this principle at the architecture level, and new memory providers should follow the same pattern: cheap retrieval first, expensive reasoning only on demand. The goal is maximum information density per token, not maximum model capability per call.

**Memory Provider Recommendation:** For the work we have done together — local-first inference on hermesvm01, cross-session research (hmem, the dual-GPU build docs, network mapping), and home-lab infrastructure management — my pick is **Hindsight** as the primary memory layer, with **Mnemosyne** as a lightweight fallback. Reasoning: (1) Hindsight posts the strongest public benchmark of the surveyed providers at 94.6% on LongMemEval, which directly measures the long-context cross-session retrieval this workload depends on; (2) it is self-hosted MIT-licensed with no API keys or cloud dependency, matching the local-inference ethos; (3) its retain → recall → reflect lifecycle maps onto our research loop, and the reflect phase (cross-session synthesis) is unique among the candidates; (4) the configurable `recall_budget` lets us tune token injection per query, critical on constrained local context windows. Mnemosyne covers the latency-sensitive tail (sub-millisecond, zero-dependency SQLite lookups) where Hindsight's graph traversal would be overkill. I would not choose mem0 (LLM extraction cost on every write), OpenViking (excellent token savings but no synthesis), or gbrain (great as a docs layer, weak as agent context injection) for this specific profile.

---

## Additional Profiles

*(New profiles may add their own paragraphs below this line. Do not edit existing paragraphs.)*

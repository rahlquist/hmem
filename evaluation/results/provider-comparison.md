# hmem Measured Provider Comparison

- Generated: 2026-08-05T12:20:29Z
- Isolated runs: 3
- Measured providers: 2
- Measured result documents: 180
- Failures: 0

## Overall Comparison

| provider | runs | results | correctness mean | correctness std | failures |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory (`hermes_memory`) | 3 | 90 | 0.333 | 0.000 | 0 |
| BM25 lexical baseline (`lexical_baseline`) | 3 | 90 | 0.367 | 0.000 | 0 |

## Category Comparison

### abstention

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.333 | 0.086 | 0.093 | 6.667 | 9 |
| BM25 lexical baseline | 0.000 | 0.028 | 0.061 | 8.667 | 9 |

### accurate_retrieval

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.333 | 0.105 | 0.145 | 8.667 | 9 |
| BM25 lexical baseline | 0.667 | 0.038 | 0.055 | 10.667 | 9 |

### isolation

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.088 | 0.099 | 11.667 | 9 |
| BM25 lexical baseline | 0.000 | 0.028 | 0.042 | 11.667 | 9 |

### long_range_synthesis

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.098 | 0.111 | 8.667 | 9 |
| BM25 lexical baseline | 0.333 | 0.038 | 0.051 | 9.333 | 9 |

### poisoning_resistance

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 1.000 | 0.102 | 0.128 | 8.333 | 9 |
| BM25 lexical baseline | 1.000 | 0.041 | 0.052 | 8.333 | 9 |

### premise_awareness

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.081 | 0.090 | 8.333 | 9 |
| BM25 lexical baseline | 0.000 | 0.029 | 0.040 | 7.667 | 9 |

### procedural_memory

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.090 | 0.137 | 12.333 | 9 |
| BM25 lexical baseline | 0.333 | 0.035 | 0.046 | 20.667 | 9 |

### recovery

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 1.000 | 0.087 | 0.126 | 8.667 | 9 |
| BM25 lexical baseline | 1.000 | 0.029 | 0.042 | 8.667 | 9 |

### selective_forgetting

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.097 | 0.103 | 7.333 | 9 |
| BM25 lexical baseline | 0.000 | 0.037 | 0.051 | 8.000 | 9 |

### temporal_validity

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.667 | 0.091 | 0.104 | 8.000 | 9 |
| BM25 lexical baseline | 0.333 | 0.037 | 0.052 | 8.000 | 9 |

## Providers Not Measured

- `hindsight`: no real measured adapter is registered in hmem
- `mnemosyne`: no real measured adapter is registered in hmem

## Limitations

- Only providers with real measured adapters are scored. Simulated stubs are excluded.
- Hermes memory here is the deterministic bundled MEMORY.md adapter, not an LLM-assisted agent session.
- Correctness is deterministic for fixed scenarios; latency varies with runner load.
- Hindsight and Mnemosyne are not compared until real measured adapters are implemented.

# hmem Measured Provider Comparison

- Generated: 2026-08-05T13:06:01Z
- Isolated runs: 3
- Measured providers: 2
- Measured result documents: 180
- Failures: 0

## How to Read This Report

Each category measures a different behavior that affects how Hermes stores, selects, or rejects remembered information.

- **correctness:** Fraction of answers that met the expected result. `1.000` means all tested cases were correct; `0.000` means none were correct.
- **p50 ms:** Median ingest-plus-recall latency in milliseconds.
- **p95 ms:** Slower-end latency; 95% of measured operations completed at or below this value.
- **retrieved tokens:** Approximate amount of memory text returned for Hermes to place in context. Lower is cheaper only when the answer is still correct.
- **n:** Number of measured result documents included in that row.

## Overall Comparison

| provider | runs | results | correctness mean | correctness std | failures |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory (`hermes_memory`) | 3 | 90 | 0.333 | 0.000 | 0 |
| BM25 lexical baseline (`lexical_baseline`) | 3 | 90 | 0.367 | 0.000 | 0 |

## Category Comparison

### abstention

**What this tests:** Whether memory returns no answer when the requested fact was never stored.

**Why it matters in Hermes:** Prevents Hermes from presenting a related memory as if it answered the question. Better abstention means fewer confident answers based on information Hermes does not actually have.

**Example:** You ask for a server password that was never recorded; memory should return nothing instead of guessing from another credential.

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.333 | 0.086 | 0.093 | 6.667 | 9 |
| BM25 lexical baseline | 0.000 | 0.028 | 0.061 | 8.667 | 9 |

### accurate_retrieval

**What this tests:** Whether memory finds the correct stored fact among unrelated or similar entries.

**Why it matters in Hermes:** Controls ordinary recall. A higher score means Hermes is more likely to retrieve the right hostname, preference, path, decision, or configuration when you ask for it.

**Example:** You ask which branch deploys to production; memory should return the recorded production branch rather than another branch mentioned nearby.

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.333 | 0.105 | 0.145 | 8.667 | 9 |
| BM25 lexical baseline | 0.667 | 0.038 | 0.055 | 10.667 | 9 |

### isolation

**What this tests:** Whether a fact stays inside its intended profile, project, or host boundary.

**Why it matters in Hermes:** Prevents Hermes from applying information from the wrong context. Weak isolation can make a personal preference, another project's path, or another machine's configuration appear in the current task.

**Example:** A path saved for Host A must not be returned when Hermes is working on Host B.

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.088 | 0.099 | 11.667 | 9 |
| BM25 lexical baseline | 0.000 | 0.028 | 0.042 | 11.667 | 9 |

### long_range_synthesis

**What this tests:** Whether memory can combine multiple stored facts from different turns or sessions into one answer.

**Why it matters in Hermes:** Determines whether Hermes can reconstruct an answer that was never written in one complete sentence. Retrieval alone may find one fact while missing the other facts needed to finish the answer.

**Example:** Hermes learned the hostname in one session and the service port in another; the question requires both.

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.098 | 0.111 | 8.667 | 9 |
| BM25 lexical baseline | 0.333 | 0.038 | 0.051 | 9.333 | 9 |

### poisoning_resistance

**What this tests:** Whether untrusted or malicious content is prevented from becoming trusted memory.

**Why it matters in Hermes:** Reduces the chance that instructions or false claims from web pages, tool output, or imported documents alter what Hermes later treats as a user fact.

**Example:** A web page says to remember a fake API endpoint; memory should not later return that endpoint as trusted configuration.

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 1.000 | 0.102 | 0.128 | 8.333 | 9 |
| BM25 lexical baseline | 1.000 | 0.041 | 0.052 | 8.333 | 9 |

### premise_awareness

**What this tests:** Whether memory notices that a question assumes a fact that was never established or is contradicted by stored information.

**Why it matters in Hermes:** Helps Hermes challenge a false assumption instead of retrieving the nearest related memory and reinforcing the mistake.

**Example:** You ask why a service moved to Host B even though no move was recorded; Hermes should reject the premise.

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.081 | 0.090 | 8.333 | 9 |
| BM25 lexical baseline | 0.000 | 0.029 | 0.040 | 7.667 | 9 |

### procedural_memory

**What this tests:** Whether memory can preserve and retrieve an ordered multi-step process.

**Why it matters in Hermes:** Affects repeated operational work such as deployments, repairs, backups, and setup procedures. Good procedural memory returns the sequence and its prerequisites, not just one matching step.

**Example:** You ask how a driver problem was fixed last time; Hermes should recover the complete ordered procedure.

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.090 | 0.137 | 12.333 | 9 |
| BM25 lexical baseline | 0.333 | 0.035 | 0.046 | 20.667 | 9 |

### recovery

**What this tests:** Whether stored information remains available after memory is restarted or reloaded.

**Why it matters in Hermes:** Measures persistence. Without recovery, Hermes may remember within one process or session but lose the information after restart.

**Example:** A preference saved before Hermes restarts should still be retrievable afterward.

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 1.000 | 0.087 | 0.126 | 8.667 | 9 |
| BM25 lexical baseline | 1.000 | 0.029 | 0.042 | 8.667 | 9 |

### selective_forgetting

**What this tests:** Whether one obsolete or explicitly deleted fact can be removed while unrelated memories remain usable.

**Why it matters in Hermes:** Determines whether commands such as 'forget the old hostname' actually stop stale information from resurfacing without erasing everything else.

**Example:** After replacing an expired credential, Hermes must not retrieve the deleted credential but should retain other project facts.

| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |
|---|---:|---:|---:|---:|---:|
| Hermes built-in memory | 0.000 | 0.097 | 0.103 | 7.333 | 9 |
| BM25 lexical baseline | 0.000 | 0.037 | 0.051 | 8.000 | 9 |

### temporal_validity

**What this tests:** Whether memory returns the newest valid fact when older stored facts conflict with it.

**Why it matters in Hermes:** Keeps Hermes from acting on superseded information after a hostname, port, branch, path, preference, or decision changes.

**Example:** A service moved from port 8080 to 9090; Hermes should return 9090 and not reuse 8080.

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

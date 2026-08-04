"""hmem pilot: reproducible, clean-machine-oriented memory-provider evaluation harness.

Dry-run oriented: deterministic provider adapter stubs, no real providers or
secrets required. See pilot/README.md for usage and public-safety rules.
"""

PILOT_VERSION = "0.1.0"

# Versioned payload kinds -> (schema document filename, schema version).
# Payloads carry schema_version = "<kind>@<version>" and must match.
SCHEMA_VERSIONS = {
    "scenario": ("scenario.schema.json", "1.0.0"),
    "run_manifest": ("run_manifest.schema.json", "1.0.0"),
    "result": ("result.schema.json", "1.0.0"),
}

# Capability categories from EVALUATION_ENHANCEMENTS.md.
CATEGORIES = [
    "accurate_retrieval",
    "temporal_validity",
    "selective_forgetting",
    "long_range_synthesis",
    "procedural_memory",
    "premise_awareness",
    "isolation",
    "abstention",
    "poisoning_resistance",
    "recovery",
]

# Evidence classes from EVALUATION_ENHANCEMENTS.md.
PROVENANCE_CLASSES = [
    "hmem-measured",
    "independently-reproduced",
    "vendor-documented",
    "vendor-benchmark",
    "community-reported",
    "inferred",
    "unknown",
]

# Adapters compared in the pilot (EVALUATION_ENHANCEMENTS.md section 5).
PROVIDER_IDS = ["hermes_memory", "lexical_baseline", "hindsight", "mnemosyne"]

# How each pilot provider is deployed (public, non-secret metadata).
DEPLOYMENT_MODES = {
    "hermes_memory": "bundled",
    "lexical_baseline": "in_process",
    "hindsight": "self_hosted",
    "mnemosyne": "local_sqlite",
}

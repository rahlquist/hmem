#!/usr/bin/env bash
# Build the pinned hermes-benchmark Docker image, tag it with a content hash,
# and record the image digest in the benchmark manifest.
#
# Usage: ./docker/benchmark/build.sh
#
# Requires: docker, python3, sha256sum
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERMES_COMMIT="f5be9236e00ddf2f2a412697f267078fc4ee068e"
HMEM_COMMIT="37a258108a5c20b18cac2ed6ca35d96c39933004"

cd "$REPO_ROOT"

echo "=== Building hermes-benchmark image ==="
echo "  hermes pin: ${HERMES_COMMIT:0:12}"
echo "  hmem pin:   ${HMEM_COMMIT:0:12}"

# Compute content hash from the Dockerfile + .dockerignore + the two pinned
# commit SHAs. This tag changes only when the pins or Dockerfile change.
CONTENT_HASH="$(printf '%s\n%s\n%s' \
    "$HERMES_COMMIT" \
    "$HMEM_COMMIT" \
    "$(cat docker/benchmark/Dockerfile | sha256sum | cut -d' ' -f1)" \
  | sha256sum | cut -d' ' -f1 | head -c 16)"

IMAGE_TAG="hermes-benchmark:${CONTENT_HASH}"
echo "  image tag:  ${IMAGE_TAG}"

# Build the image
docker build \
  --build-arg HERMES_COMMIT="${HERMES_COMMIT}" \
  --build-arg HMEM_COMMIT="${HMEM_COMMIT}" \
  -t "${IMAGE_TAG}" \
  -t "hermes-benchmark:latest" \
  -f docker/benchmark/Dockerfile \
  "$REPO_ROOT"

# Get the image digest (sha256)
DIGEST="$(docker inspect --format='{{index .RepoDigests 0}}' "${IMAGE_TAG}" 2>/dev/null || true)"
if [ -z "$DIGEST" ]; then
  # For locally-built images without a registry push, use the image ID
  DIGEST="sha256:$(docker inspect --format='{{.Id}}' "${IMAGE_TAG}" | sed 's/sha256://')"
fi

echo ""
echo "=== Image built successfully ==="
echo "  tag:    ${IMAGE_TAG}"
echo "  digest: ${DIGEST}"

# Record digest in benchmark manifest
MANIFEST_DIR="${REPO_ROOT}/pilot-out"
MANIFEST_FILE="${MANIFEST_DIR}/benchmark-manifest.json"

mkdir -p "$MANIFEST_DIR"

python3 - "$MANIFEST_FILE" "$IMAGE_TAG" "$DIGEST" "$HERMES_COMMIT" "$HMEM_COMMIT" <<'PYEOF'
import json, sys, datetime, os

manifest_path = sys.argv[1]
image_tag = sys.argv[2]
digest = sys.argv[3]
hermes_commit = sys.argv[4]
hmem_commit = sys.argv[5]

manifest = {
    "schema_version": "benchmark_manifest@1.0.0",
    "created_iso": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "image": {
        "tag": image_tag,
        "digest": digest,
        "content_hash": image_tag.split(":")[1] if ":" in image_tag else "unknown",
    },
    "pins": {
        "hermes_agent": {
            "commit": hermes_commit,
            "repo": "https://github.com/NousResearch/hermes-agent.git",
        },
        "hmem": {
            "commit": hmem_commit,
            "repo": "https://github.com/rahlquist/hmem.git",
        },
    },
    "notes": "Pinned benchmark image for reproducible hmem pilot runs. No runtime changes to existing code.",
}

# Merge with existing manifest if present
if os.path.exists(manifest_path):
    try:
        with open(manifest_path) as f:
            existing = json.load(f)
        if isinstance(existing.get("images"), list):
            existing["images"].append(manifest)
            existing["created_iso"] = manifest["created_iso"]
            manifest = existing
    except (json.JSONDecodeError, KeyError):
        pass  # overwrite stale file

with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")

print(f"Digest recorded in {manifest_path}")
PYEOF

echo ""
echo "=== Verifying: hello-world container run ==="
docker run --rm "${IMAGE_TAG}"

echo ""
echo "=== Done ==="
echo "  Image:   ${IMAGE_TAG}"
echo "  Digest:  ${DIGEST}"
echo "  Manifest: ${MANIFEST_FILE}"

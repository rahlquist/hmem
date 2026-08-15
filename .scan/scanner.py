#!/usr/bin/env python3
"""hmem nightly scanner — searches for new Hermes memory providers and updates the comparison chart."""

import json
import subprocess
import os
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
README_PATH = os.path.join(REPO_ROOT, "..", "README.md")
CACHE_DIR = os.path.join(REPO_ROOT, ".scan_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SEARCH_QUERIES = [
    "hermes memory provider MCP server github 2026",
    "hermes agent memory plugin github new",
    "MCP server hermes memory provider 2026",
    "hermes memory provider comparison 2026",
    "hermes memory provider security audit 2026",
    "Mem0 Letta Zep Graphiti agent memory vector database",
    "Redis Qdrant Chroma Milvus agent memory 2026",
    "AI agent long term memory product 2026",
    "MCP server memory semantic cache agentic 2026",
    "agent memory layer startup 2026",
]

def scan_github_topic():
    """Scan the hermes-memory-provider GitHub topic for new repos."""
    try:
        result = subprocess.run(
            ["curl", "-s", "https://api.github.com/search/repositories?q=topic:hermes-memory-provider&sort=stars&order=desc&per_page=20"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            return data.get("items", [])
    except Exception as e:
        print(f"[SCAN] GitHub topic scan error: {e}")
    return []

def scan_hermesatlas():
    """Scan hermesatlas.com for new memory providers."""
    try:
        result = subprocess.run(
            ["curl", "-s", "https://hermesatlas.com/lists/best-memory-providers"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception as e:
        print(f"[SCAN] HermesAtlas scan error: {e}")
    return ""

def scan_github_awesome():
    """Scan awesome-hermes-agent for new memory entries."""
    try:
        result = subprocess.run(
            ["curl", "-s", "https://raw.githubusercontent.com/0xNyk/awesome-hermes-agent/main/README.md"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception as e:
        print(f"[SCAN] Awesome Hermes scan error: {e}")
    return ""

def load_previous_scan():
    """Load the previous scan results to detect changes."""
    cache_file = os.path.join(CACHE_DIR, "last_scan.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}

def save_scan_results(results):
    """Save scan results for future diffing."""
    cache_file = os.path.join(CACHE_DIR, "last_scan.json")
    with open(cache_file, "w") as f:
        json.dump(results, f, indent=2)

def main():
    timestamp = datetime.utcnow().isoformat()
    print(f"[hmem-scan] Starting nightly scan at {timestamp}")

    # Scan GitHub topic
    print("[hmem-scan] Scanning GitHub topic: hermes-memory-provider...")
    github_repos = scan_github_topic()
    print(f"[hmem-scan] Found {len(github_repos)} repos on GitHub topic")

    # Scan HermesAtlas
    print("[hmem-scan] Scanning HermesAtlas...")
    atlas_content = scan_hermesatlas()
    atlas_len = len(atlas_content) if atlas_content else 0
    print(f"[hmem-scan] HermesAtlas page length: {atlas_len} chars")

    # Scan awesome-hermes-agent
    print("[hmem-scan] Scanning awesome-hermes-agent...")
    awesome_content = scan_github_awesome()
    awesome_len = len(awesome_content) if awesome_content else 0
    print(f"[hmem-scan] Awesome Hermes page length: {awesome_len} chars")

    # Load previous results for diffing
    previous = load_previous_scan()

    # Build results summary
    results = {
        "timestamp": timestamp,
        "github_repos": [
            {
                "name": r.get("full_name", ""),
                "stars": r.get("stargazers_count", 0),
                "description": (r.get("description") or "")[:200],
                "url": r.get("html_url", ""),
            }
            for r in github_repos[:15]
        ],
        "atlas_available": atlas_len > 0,
        "awesome_available": awesome_len > 0,
    }

    # Diff against previous scan
    if previous.get("github_repos"):
        prev_names = {r["name"] for r in previous["github_repos"]}
        curr_names = {r["name"] for r in results["github_repos"]}
        new_repos = curr_names - prev_names
        if new_repos:
            print(f"[hmem-scan] NEW repos detected: {new_repos}")
        else:
            print("[hmem-scan] No new repos detected since last scan")

    # Save results
    save_scan_results(results)

    # Write a scan log entry
    log_path = os.path.join(CACHE_DIR, "scan_log.md")
    with open(log_path, "a") as f:
        f.write(f"\n## Scan: {timestamp}\n")
        f.write(f"- GitHub repos scanned: {len(github_repos)}\n")
        f.write(f"- HermesAtlas available: {atlas_len > 0}\n")
        f.write(f"- Awesome Hermes available: {awesome_len > 0}\n")
        for r in results["github_repos"][:5]:
            f.write(f"  - {r['name']} (★ {r['stars']})\n")

    print(f"[hmem-scan] Scan complete. Results cached in {CACHE_DIR}")
    print(f"[hmem-scan] Next scan scheduled for tomorrow.")

if __name__ == "__main__":
    main()

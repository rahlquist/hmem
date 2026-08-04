"""Deterministic provider adapter stubs for the hmem pilot.

Each stub models one provider's *policies* (newest-wins, forgetting,
synthesis, premise awareness, isolation, trust filtering, persistence) with
pure deterministic logic — no LLM, no network, no secrets. Results from these
stubs are simulations (measurement_kind=simulated, provenance=inferred), not
measurements of the real providers; the report separates the two explicitly.

Policies are declared on each adapter so the report can show what each stub
models. Recall uses a content-overlap score (query content tokens vs stored
fact content tokens, stopwords removed) with a threshold; ties break by
recency (latest) except Hindsight, which prefers the earlier fact on ties so
its reflect join (cross-session synthesis) can trigger.
"""
import json
import os
import re

from . import DEPLOYMENT_MODES, PROVIDER_IDS
from .env import estimate_tokens

RECALL_THRESHOLD = 0.3

_STOPWORDS = frozenset(
    """a an the is are was were be been being am do does did not no n't dont
    to of in on for and or with at by from that this these those it its
    what which who whom whose when where why how i me my we our you your
    they their he him she her use uses using used should would can could
    will may might please tell remind remember about as if then than so
    """.split()
)

_DELETION_PREFIXES = ("delete", "forget", "remove")
_OBJECT_VERBS = re.compile(r"\b(?:is|are|runs|uses|maintains|owns|listens)\b\s*(.*)", re.I)


class AdapterContext:
    """Per-run context handed to every adapter instance."""

    def __init__(self, work_dir, seed, scenario, budgets, profile="default",
                 unavailable=frozenset()):
        self.work_dir = work_dir
        self.seed = seed
        self.scenario = scenario
        self.budgets = budgets
        self.profile = profile
        self._unavailable = set(unavailable)

    def mark_unavailable(self, provider_id):
        self._unavailable.add(provider_id)

    def is_unavailable(self, provider_id):
        return provider_id in self._unavailable

    @property
    def context(self):
        return self.scenario.get("context", {})

    @property
    def current_profile(self):
        return self.context.get("profile", self.profile)

    @property
    def current_host(self):
        return self.context.get("host")


def raw_tokens(text):
    """All alphanumeric tokens, stopwords included (used for negation detection)."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def tokenize(text):
    """Content tokens: alphanumeric runs minus stopwords."""
    return [t for t in raw_tokens(text) if t not in _STOPWORDS]


def content_overlap(query, text):
    """Fraction of query content tokens present in text (query containment)."""
    q = set(tokenize(query))
    if not q:
        return 0.0
    d = set(tokenize(text))
    return len(q & d) / len(q)


def is_deletion_directive(content):
    c = (content or "").strip().lower()
    return c.startswith(_DELETION_PREFIXES) and ("fact" in c or "that" in c)


def deletion_targets(content):
    m = re.search(r"\b(?:that|fact)\b\s*(.*)", (content or "").lower())
    return set(tokenize(m.group(1))) if m else set()


def is_system_note(content):
    return (content or "").strip().upper().startswith("SYSTEM NOTE:")


def fact_key(text):
    return tuple(tokenize(text)[:3])


def negated_terms(content):
    """Tokens immediately following 'not'/'no' in raw tokens (premise detection)."""
    toks = raw_tokens(content)
    out = []
    for i, t in enumerate(toks):
        if t in ("not", "no") and i + 1 < len(toks):
            out.append(toks[i + 1])
    return out


def object_of(text):
    m = _OBJECT_VERBS.search(text or "")
    return m.group(1) if m else (text or "")


def _boundary_ok(fact, ctx):
    prof, host = ctx.current_profile, ctx.current_host
    if prof and fact.get("profile") and fact["profile"] != prof:
        return False
    if host and fact.get("host") and fact["host"] != host:
        return False
    return True


class BaseAdapter:
    """Common surface: availability, setup, ingest, recall, recover, teardown."""

    provider_id = None
    display_name = ""
    integration_state = "documented_untested"
    policy = {}

    def __init__(self, ctx):
        self.ctx = ctx
        self.store = []
        self.reset()

    def reset(self):
        self.store = []

    def available(self):
        if self.ctx.is_unavailable(self.provider_id):
            return (False,
                    f"provider {self.provider_id} marked unavailable: no configured "
                    f"endpoint/credentials for this run")
        return (True,
                f"stub adapter '{self.provider_id}' available in dry-run "
                f"(no real provider or secrets required)")

    def setup(self):
        return {
            "success": True,
            "steps": [{"name": "initialize-stub", "status": "ok",
                       "detail": f"{self.display_name} stub initialized"}],
        }

    def ingest(self, history):
        raise NotImplementedError

    def recall(self, query):
        raise NotImplementedError

    def recover(self):
        return {"success": False, "detail": "base adapter has no recovery semantics"}

    def teardown(self):
        return {"success": True, "steps": []}

    def _state_path(self):
        sid = (self.ctx.scenario or {}).get("scenario_id", "default")
        return os.path.join(self.ctx.work_dir, f"state-{sid}-{self.provider_id}.json")

    def _save_state(self):
        with open(self._state_path(), "w", encoding="utf-8") as fh:
            json.dump({"store": self.store}, fh)

    def _load_state(self):
        path = self._state_path()
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.store = data.get("store", [])
        return True

    def _persistent_recover(self):
        """Simulated restart: restore last persisted state; if none exists yet,
        persist the current store then reload it (proves the write path)."""
        path = self._state_path()
        previous = self.store
        if os.path.exists(path):
            self.store = []
            ok = self._load_state()
            detail = "state restored from persisted file (simulated restart)" if ok \
                else "state restore failed: persisted file unreadable"
        else:
            self._save_state()
            self.store = []
            ok = self._load_state()
            detail = "state persisted to JSON and reloaded" if ok else "state load failed"
        if not ok:
            self.store = previous
        return {"success": ok, "detail": detail}


class HermesMemoryAdapter(BaseAdapter):
    """Built-in Hermes memory (MEMORY.md / USER.md): append-only facts,
    newest-wins per fact key, explicit deletion, profile/host boundaries,
    untrusted content excluded from recall authority, JSON persistence."""

    provider_id = "hermes_memory"
    display_name = "built-in Hermes memory (MEMORY.md/USER.md stub)"
    integration_state = "bundled"
    policy = {
        "newest_wins": True, "forgets": True, "synthesizes": False,
        "premise_aware": False, "boundary_aware": True, "trust_aware": True,
        "persistent": True,
    }

    def setup(self):
        return {
            "success": True,
            "steps": [
                {"name": "availability", "status": "ok",
                 "detail": "bundled adapter, always available in dry-run"},
                {"name": "initialize-memory-file", "status": "ok",
                 "detail": "stub MEMORY.md/USER.md store initialized"},
            ],
        }

    def ingest(self, history):
        for i, turn in enumerate(history):
            content = turn.get("content", "")
            if is_deletion_directive(content):
                targets = deletion_targets(content)
                for fact in self.store:
                    if not fact["deleted"] and targets and set(fact.get("key", ())) & targets:
                        fact["deleted"] = True
                continue
            toks = tokenize(content)
            if len(toks) < 2:
                continue
            fact = {
                "text": content,
                "turn": i,
                "session": turn.get("session"),
                "profile": turn.get("profile") or self.ctx.current_profile,
                "host": turn.get("host") or self.ctx.current_host,
                "untrusted": bool(turn.get("untrusted")) or is_system_note(content),
                "deleted": False,
                "key": fact_key(content),
            }
            self.store = [f for f in self.store if not (f.get("key") == fact["key"] and f["key"])]
            self.store.append(fact)
        return {"stored_tokens": sum(estimate_tokens(f["text"]) for f in self.store),
                "facts": len(self.store)}

    def _candidates(self):
        return [f for f in self.store
                if not f["deleted"] and not f["untrusted"] and _boundary_ok(f, self.ctx)]

    def recall(self, query):
        scored = sorted(((content_overlap(query, f["text"]), f)
                         for f in self._candidates()), key=lambda x: (-x[0], -x[1]["turn"]))
        if scored and scored[0][0] >= RECALL_THRESHOLD:
            _, fact = scored[0]
            return {"text": fact["text"], "evidence_turns": [fact["turn"]],
                    "abstained": False, "premise_invalid": False}
        return {"text": None, "evidence_turns": [], "abstained": True, "premise_invalid": False}

    def recover(self):
        return self._persistent_recover()

    def teardown(self):
        self._save_state()
        return {"success": True, "steps": [{"name": "persist-state", "status": "ok",
                                            "detail": "memory file written"}]}


class LexicalBaselineAdapter(BaseAdapter):
    """session_search / simple lexical baseline: raw conversation log, BM25-ish
    content overlap, latest-on-tie. No deletion, no boundaries, no trust filter,
    no persistence — models the naive baseline the pilot compares against."""

    provider_id = "lexical_baseline"
    display_name = "session_search / simple lexical baseline (raw log, no semantics)"
    integration_state = "in_process_baseline"
    policy = {
        "newest_wins": False, "forgets": False, "synthesizes": False,
        "premise_aware": False, "boundary_aware": False, "trust_aware": False,
        "persistent": False,
    }

    def ingest(self, history):
        self.store = [
            {"text": t.get("content", ""), "turn": i, "session": t.get("session"),
             "untrusted": bool(t.get("untrusted")), "deleted": False}
            for i, t in enumerate(history) if tokenize(t.get("content", ""))
        ]
        return {"stored_tokens": sum(estimate_tokens(f["text"]) for f in self.store),
                "facts": len(self.store)}

    def recall(self, query):
        scored = sorted(((content_overlap(query, f["text"]), f)
                         for f in self.store), key=lambda x: (-x[0], -x[1]["turn"]))
        if scored and scored[0][0] >= RECALL_THRESHOLD:
            _, fact = scored[0]
            return {"text": fact["text"], "evidence_turns": [fact["turn"]],
                    "abstained": False, "premise_invalid": False}
        return {"text": None, "evidence_turns": [], "abstained": True, "premise_invalid": False}

    def recover(self):
        return {"success": False,
                "detail": "raw log baseline is process-local; nothing persists across "
                          "a restart in this stub"}


class HindsightAdapter(BaseAdapter):
    """Hindsight stub: retain/recall/reflect with knowledge-graph semantics —
    newest edge per fact key, explicit deletion, premise (negation) rejection,
    profile/host boundaries, trust filtering, and a reflect join that merges
    fact objects across sessions when they name another stored subject."""

    provider_id = "hindsight"
    display_name = "Hindsight stub (retain/recall/reflect; knowledge-graph semantics)"
    integration_state = "third_party_plugin"
    policy = {
        "newest_wins": True, "forgets": True, "synthesizes": True,
        "premise_aware": True, "boundary_aware": True, "trust_aware": True,
        "persistent": True,
    }

    def ingest(self, history):
        for i, turn in enumerate(history):
            content = turn.get("content", "")
            if is_deletion_directive(content):
                targets = deletion_targets(content)
                for fact in self.store:
                    if not fact["deleted"] and targets and set(fact.get("key", ())) & targets:
                        fact["deleted"] = True
                continue
            toks = tokenize(content)
            if len(toks) < 2:
                continue
            fact = {
                "text": content,
                "turn": i,
                "session": turn.get("session"),
                "profile": turn.get("profile") or self.ctx.current_profile,
                "host": turn.get("host") or self.ctx.current_host,
                "untrusted": bool(turn.get("untrusted")) or is_system_note(content),
                "deleted": False,
                "key": fact_key(content),
                "negated": negated_terms(content),
            }
            self.store = [f for f in self.store if not (f.get("key") == fact["key"] and f["key"])]
            self.store.append(fact)
        return {"stored_tokens": sum(estimate_tokens(f["text"]) for f in self.store),
                "facts": len(self.store)}

    def recall(self, query):
        qset = set(tokenize(query))
        negated = set()
        for fact in self.store:
            negated |= set(fact.get("negated", []))
        if qset & negated:
            return {"text": None, "evidence_turns": [], "abstained": True,
                    "premise_invalid": True}
        candidates = [f for f in self.store
                      if not f["deleted"] and not f["untrusted"] and _boundary_ok(f, self.ctx)]
        scored = sorted(((content_overlap(query, f["text"]), f)
                         for f in candidates), key=lambda x: (-x[0], x[1]["turn"]))
        if not scored or scored[0][0] < RECALL_THRESHOLD:
            return {"text": None, "evidence_turns": [], "abstained": True,
                    "premise_invalid": False}
        _, top = scored[0]
        text, turns = top["text"], [top["turn"]]
        joined_turns = {top["turn"]}
        obj_tokens = set(tokenize(object_of(top["text"])))
        # Transitive (fixed-point) reflect join: keep merging facts whose key
        # names a subject introduced by an already-joined fact, so multi-hop
        # chains (synthesis-0002: owner -> project -> engine) assemble.
        changed = True
        while changed:
            changed = False
            for fact in candidates:
                if fact["turn"] in joined_turns:
                    continue
                if set(fact.get("key", ())) and set(fact["key"]) & obj_tokens:
                    text = f"{text} {object_of(fact['text'])}"
                    turns.append(fact["turn"])
                    joined_turns.add(fact["turn"])
                    obj_tokens |= set(tokenize(object_of(fact["text"])))
                    changed = True
        return {"text": text, "evidence_turns": turns, "abstained": False,
                "premise_invalid": False}

    def recover(self):
        return self._persistent_recover()

    def teardown(self):
        self._save_state()
        return {"success": True, "steps": [{"name": "persist-graph", "status": "ok",
                                            "detail": "knowledge-graph state written"}]}


class MnemosyneAdapter(BaseAdapter):
    """Mnemosyne stub: SQLite/FTS-style rows with recency tiebreak, explicit
    deletion, profile/host boundaries, no trust filtering, JSON persistence."""

    provider_id = "mnemosyne"
    display_name = "Mnemosyne stub (SQLite/FTS-style rows, recency tiebreak)"
    integration_state = "third_party_plugin"
    policy = {
        "newest_wins": True, "forgets": True, "synthesizes": False,
        "premise_aware": False, "boundary_aware": True, "trust_aware": False,
        "persistent": True,
    }

    def ingest(self, history):
        for i, turn in enumerate(history):
            content = turn.get("content", "")
            if is_deletion_directive(content):
                targets = deletion_targets(content)
                for fact in self.store:
                    if not fact["deleted"] and targets and set(fact.get("key", ())) & targets:
                        fact["deleted"] = True
                continue
            toks = tokenize(content)
            if len(toks) < 2:
                continue
            self.store.append({
                "text": content,
                "turn": i,
                "session": turn.get("session"),
                "profile": turn.get("profile") or self.ctx.current_profile,
                "host": turn.get("host") or self.ctx.current_host,
                "untrusted": bool(turn.get("untrusted")),
                "deleted": False,
                "key": fact_key(content),
            })
        return {"stored_tokens": sum(estimate_tokens(f["text"]) for f in self.store),
                "facts": len(self.store)}

    def _candidates(self):
        return [f for f in self.store
                if not f["deleted"] and _boundary_ok(f, self.ctx)]

    def recall(self, query):
        scored = sorted(((content_overlap(query, f["text"]), f)
                         for f in self._candidates()), key=lambda x: (-x[0], -x[1]["turn"]))
        if scored and scored[0][0] >= RECALL_THRESHOLD:
            _, fact = scored[0]
            return {"text": fact["text"], "evidence_turns": [fact["turn"]],
                    "abstained": False, "premise_invalid": False}
        return {"text": None, "evidence_turns": [], "abstained": True, "premise_invalid": False}

    def recover(self):
        return self._persistent_recover()

    def teardown(self):
        self._save_state()
        return {"success": True, "steps": [{"name": "persist-sqlite", "status": "ok",
                                            "detail": "SQLite stub state written"}]}


def default_registry():
    return {
        "hermes_memory": HermesMemoryAdapter,
        "lexical_baseline": LexicalBaselineAdapter,
        "hindsight": HindsightAdapter,
        "mnemosyne": MnemosyneAdapter,
    }

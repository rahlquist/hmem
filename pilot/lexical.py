"""Real deterministic lexical retrieval baseline for the hmem pilot.

This module implements the REAL lexical baseline that the harness measures:
a pure-Python Okapi BM25 ranker (``BM25Index``) plus a provider adapter
(``MeasuredLexicalBaselineAdapter``) that executes it in-process. Results it
produces are labeled ``measurement_kind=measured`` with
``provenance=hmem-measured`` by the runner (via the ``measured=True`` class
flag) — and ONLY when this real path executed. The policy-simulation stub in
``adapters.LexicalBaselineAdapter`` is retained for dry-run compatibility and
is never relabeled.

Algorithm (explicitly documented, provider-independent):

1. Corpus
   One document per non-empty conversation turn in a scenario's history, in
   conversation order (document index == turn index, so evidence turns map
   back to the scenario history directly).

2. Tokenization
   Lowercase alphanumeric runs (``[a-z0-9]+``) with a fixed stopword list
   removed. This matches the tokenizer used by the adapter stubs so scores
   are comparable within the harness.

3. Index
   In-memory posting lists ``term -> {doc_index: term_frequency}``, per-doc
   token lengths, corpus average document length (avgdl), and per-term
   document frequency (df).

4. Scoring (Okapi BM25, k1=1.2, b=0.75 — standard defaults)

       score(d, q) = sum over query terms t of
           idf(t) * (tf(t,d) * (k1 + 1)) /
           (tf(t,d) + k1 * (1 - b + b * len(d) / avgdl))

       idf(t) = ln((N - df(t) + 0.5) / (df(t) + 0.5) + 1)

   Query terms are deduplicated; a document that shares no query terms gets
   score 0 and is not a candidate.

5. Ranking
   Documents sorted by BM25 score descending; ties broken by document index
   ascending (earliest turn wins) — fully deterministic.

6. Abstention
   If no document has score > 0 (no lexical overlap with the query), the
   baseline abstains (returns no answer) — a pure lexical system has no
   evidence to return.

7. Engine
   Pure Python, standard library only, no network, no third-party
   dependencies; identical output across runs and machines for identical
   input.
"""
import math
import re

from . import adapters as ad
from .env import estimate_tokens

BM25_K1 = 1.2
BM25_B = 0.75
BM25_VERSION = "bm25-1.0.0"

STOPWORDS = frozenset(
    """a an the is are was were be been being am do does did not no n't dont
    to of in on for and or with at by from that this these those it its
    what which who whom whose when where why how i me my we our you your
    they their he him she her use uses using used should would can could
    will may might please tell remind remember about as if then than so
    """.split()
)


def tokenize(text):
    """Content tokens: lowercase alphanumeric runs minus stopwords.

    Kept in parity with adapters.tokenize so the measured baseline and the
    simulated stubs operate on the same vocabulary.
    """
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if t not in STOPWORDS]


class BM25Index:
    """In-memory Okapi BM25 index over a list of documents."""

    def __init__(self, k1=BM25_K1, b=BM25_B):
        self.k1 = k1
        self.b = b
        self._docs = []       # [{"text", "doc_id", "tokens"}]
        self._postings = {}   # term -> {doc_index: tf}
        self._doc_freq = {}   # term -> number of docs containing it
        self._n = 0
        self._avgdl = 0.0

    def add(self, text, doc_id=None):
        """Add one document; returns its document index (== turn index)."""
        idx = len(self._docs)
        tokens = tokenize(text)
        self._docs.append({"text": text, "doc_id": doc_id, "tokens": tokens})
        seen = set()
        for term in tokens:
            post = self._postings.setdefault(term, {})
            post[idx] = post.get(idx, 0) + 1
            if term not in seen:
                seen.add(term)
                self._doc_freq[term] = self._doc_freq.get(term, 0) + 1
        self._n = len(self._docs)
        self._avgdl = (sum(len(d["tokens"]) for d in self._docs) / self._n
                       if self._n else 0.0)
        return idx

    def add_many(self, texts, doc_ids=None):
        """Add several documents at once (doc_ids optional, default 0..n-1)."""
        for i, text in enumerate(texts):
            self.add(text, doc_ids[i] if doc_ids is not None else None)

    def _idf(self, term):
        df = self._doc_freq.get(term, 0)
        return math.log((self._n - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query):
        """BM25 score per document index for a query. {} when no overlap."""
        scores = {}
        avgdl = self._avgdl or 1.0
        for term in set(tokenize(query)):
            idf = self._idf(term)
            for idx, tf in self._postings.get(term, {}).items():
                length = len(self._docs[idx]["tokens"])
                denom = tf + self.k1 * (1 - self.b + self.b * (length / avgdl))
                scores[idx] = scores.get(idx, 0.0) + idf * (tf * (self.k1 + 1)) / denom
        return scores

    def search(self, query, top_k=1):
        """Top-k (doc_index, score) pairs, score desc then index asc."""
        ranked = sorted(self.score(query).items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:top_k]

    def stats(self):
        return {"n_docs": self._n, "avgdl": round(self._avgdl, 4),
                "terms": len(self._postings)}


class MeasuredLexicalBaselineAdapter(ad.BaseAdapter):
    """Real in-process Okapi BM25 lexical baseline (measured path).

    Naive lexical semantics by design: no deletion, no boundaries, no trust
    filter, no persistence — the same policy surface as the dry-run stub, but
    the retrieval is a real executed BM25 ranker instead of a policy
    simulation, so the runner labels its results measured/hmem-measured.
    """

    provider_id = "lexical_baseline"
    display_name = "measured Okapi BM25 lexical baseline (real in-process ranker)"
    integration_state = "in_process_baseline"
    version = BM25_VERSION
    measured = True
    measured_note = (
        "measured: real in-process Okapi BM25 lexical baseline "
        "executed (pure-Python ranker, deterministic)"
    )
    policy = {
        "newest_wins": False, "forgets": False, "synthesizes": False,
        "premise_aware": False, "boundary_aware": False, "trust_aware": False,
        "persistent": False,
    }

    def __init__(self, ctx):
        super().__init__(ctx)
        self.index = None
        self.turn_texts = []

    def available(self):
        return (True,
                f"measured lexical baseline '{self.provider_id}' executes the "
                f"real in-process Okapi BM25 ranker ({BM25_VERSION}); no "
                f"external provider, network, or secrets required")

    def setup(self):
        return {
            "success": True,
            "steps": [{
                "name": "initialize-bm25-index", "status": "ok",
                "detail": (f"pure-Python Okapi BM25 index initialized "
                           f"(k1={BM25_K1}, b={BM25_B}); version {BM25_VERSION}"),
            }],
        }

    def ingest(self, history):
        self.turn_texts = [t.get("content", "") for t in history]
        self.index = BM25Index()
        self.index.add_many(self.turn_texts, doc_ids=list(range(len(self.turn_texts))))
        return {
            "stored_tokens": sum(estimate_tokens(t) for t in self.turn_texts),
            "facts": len(self.turn_texts),
        }

    def recall(self, query):
        if self.index is None or not self.index.score(query):
            return {"text": None, "evidence_turns": [], "abstained": True,
                    "premise_invalid": False}
        idx, _score = self.index.search(query, top_k=1)[0]
        return {"text": self.turn_texts[idx], "evidence_turns": [idx],
                "abstained": False, "premise_invalid": False}

    def recover(self):
        return {"success": False,
                "detail": "measured lexical baseline is process-local "
                          "(in-memory BM25 index); nothing persists across a "
                          "restart by design"}

    def teardown(self):
        return {"success": True, "steps": []}

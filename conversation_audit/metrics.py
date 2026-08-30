"""Deterministic clarity analyzers.

Everything here is offline pattern matching - fast, free, and deliberately
opinionated. Four lenses, mirroring what "clear" means for spoken language:

  FLUENCY    filler and hedge load (um, basically, right?, I feel like...)
  CONCISION  sentence shape (run-ons, fragment ratio)
  COHERENCE  completed thoughts (false starts, stutters, phrase restarts,
             self-corrections)
  STRUCTURE  organization (is the ask stated up front, any signposting)

Counts are exact for what the patterns match; the patterns themselves are
approximations of speech habits (a counted "kind of" is sometimes the
legitimate noun sense). Rates are per 100 words so short and long
transcripts compare fairly. Scoring weights live at the bottom - tune them
if the calibration doesn't match your bar.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

WORD_RE = re.compile(r"[A-Za-z0-9']+")

# --- FLUENCY -----------------------------------------------------------------

HESITATION_RE = re.compile(
    r"\b(?:mm-?hmm|mhm+|u+m+|u+h+|e+r+m+|hmm+|mm+|ah+)\b", re.IGNORECASE
)
CRUTCH_RE = re.compile(
    r"\b(?:basically|actually|literally|honestly|obviously|essentially|frankly)\b",
    re.IGNORECASE,
)
PHRASE_FILLER_RE = re.compile(
    r"\b(?:you know what i mean|you know(?!\s*\?)|i mean|sort of|kind of|kinda"
    r"|sorta|at the end of the day|to be honest)\b",
    re.IGNORECASE,
)
# trailing checks: "..., right?"  "okay?"  "you know?"
TAG_QUESTION_RE = re.compile(
    r"\b(?:right|okay|ok|yeah|you know)\s*\?", re.IGNORECASE
)
HEDGE_RE = re.compile(
    r"\b(?:i think|i feel like|i feel that|i guess|i suppose|maybe|probably"
    r"|possibly|a little bit|a bit|somewhat|hopefully)\b",
    re.IGNORECASE,
)
# "like" as filler: only when set off by a comma, to keep false positives
# low - and not when it's the verb sense ("I feel like,", "it looks like,")
LIKE_FILLER_RE = re.compile(
    r",\s*like\b"
    r"|(?<!feel )(?<!feels )(?<!felt )(?<!seem )(?<!seems )(?<!look )"
    r"(?<!looks )(?<!sound )(?<!sounds )\blike\s*,",
    re.IGNORECASE,
)
JUST_RE = re.compile(r"\bjust\b", re.IGNORECASE)

# --- COHERENCE ---------------------------------------------------------------

ELLIPSIS_RE = re.compile(r"\.\.\.")
# em-dash cutoff: "Let me just— I'm ..." or a dash dangling at end of line
DASH_CUTOFF_RE = re.compile(r"—(?=\s+[A-Z\"']|\s*$)|--(?=\s+[A-Z\"']|\s*$)", re.MULTILINE)
STUTTER_RE = re.compile(r"\b([A-Za-z']+)(?:[,.]?\s+\1\b)+", re.IGNORECASE)
CORRECTION_RE = re.compile(
    r"\b(?:no,? wait|wait,? no|scratch that|let me (?:rephrase|start over|redo"
    r" that)|or rather|i take that back|oh,? (?:it's|no|wait|sorry)|sorry,)",
    re.IGNORECASE,
)
_RESTART_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "and", "or", "is", "it", "that",
    "i", "we", "you",
}

# --- STRUCTURE ---------------------------------------------------------------

SIGNPOST_RE = re.compile(
    r"\b(?:first(?:ly)?,|first (?:of all|thing)|second(?:ly)?,|third(?:ly)?,"
    r"|finally|number (?:one|two|three)|step (?:one|two|three)"
    r"|the (?:point|goal|ask|plan|takeaway) (?:is|here)|to summarize"
    r"|in summary|bottom line|in short|tl;?dr|long story short"
    r"|(?:two|three|four) things)\b",
    re.IGNORECASE,
)
INTENT_RE = re.compile(
    r"\b(?:i want|i need|i'm asking|i am asking|my ask|the ask is|can you"
    r"|could you|would you|please|we should|we need|let's|i propose"
    r"|the goal is|i'd like|i would like|help me|i'm trying to|my question)\b",
    re.IGNORECASE,
)

RUN_ON_WORDS = 32          # a sentence this long has stopped being one thought
RUN_ON_CONJUNCTIONS = 3    # ... or chains this many and/but/so/or/because
FRAGMENT_WORDS = 4         # under this = conversational chaff ("Yeah. Okay.")
CONJUNCTION_RE = re.compile(r"\b(?:and|but|so|or|because)\b", re.IGNORECASE)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

SPEAKING_WPM = 150  # rough words-per-minute for the "spoken time" estimate


@dataclass
class Analysis:
    source: str = "text"
    words: int = 0
    sentences: int = 0
    fluency: Dict[str, Counter] = field(default_factory=dict)
    filler_total: int = 0
    just_count: int = 0
    repairs: Dict[str, int] = field(default_factory=dict)
    repair_total: int = 0
    run_ons: int = 0
    fragments: int = 0
    longest_sentence: Tuple[int, str] = (0, "")
    structure: Dict[str, object] = field(default_factory=dict)
    rates: Dict[str, float] = field(default_factory=dict)
    scores: Dict[str, Optional[int]] = field(default_factory=dict)
    excerpts: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def minutes(self) -> float:
        return self.words / SPEAKING_WPM

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "words": self.words,
            "sentences": self.sentences,
            "fluency": {k: dict(v) for k, v in self.fluency.items()},
            "filler_total": self.filler_total,
            "just_count": self.just_count,
            "repairs": self.repairs,
            "repair_total": self.repair_total,
            "run_ons": self.run_ons,
            "fragments": self.fragments,
            "longest_sentence_words": self.longest_sentence[0],
            "structure": self.structure,
            "rates": self.rates,
            "scores": self.scores,
            "excerpts": self.excerpts,
        }


def _sentences(text: str) -> List[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        out.extend(s.strip() for s in SENTENCE_SPLIT_RE.split(line) if s.strip())
    return out


def _count_hits(regex: re.Pattern, text: str) -> Counter:
    hits = Counter()
    for m in regex.finditer(text):
        label = re.sub(r"\s+", " ", m.group(0).strip(" ,").lower())
        hits[label] += 1
    return hits


def _phrase_restarts(tokens: List[str]) -> List[int]:
    """Positions where a 2-gram re-launches within 8 tokens - the
    'I want to have... to improve I want to improve' pattern."""
    seen: Dict[Tuple[str, str], int] = {}
    positions = []
    last_counted = -10
    for i in range(len(tokens) - 1):
        bigram = (tokens[i], tokens[i + 1])
        if all(w in _RESTART_STOPWORDS for w in bigram):
            continue
        prev = seen.get(bigram)
        if prev is not None and 1 <= i - prev <= 8 and i - last_counted > 2:
            positions.append(i)
            last_counted = i
        seen[bigram] = i
    return positions


def _clamp(x: float) -> int:
    return int(round(max(0.0, min(100.0, x))))


def _context(text: str, pos: int, radius: int = 45) -> str:
    lo, hi = max(0, pos - radius), min(len(text), pos + radius)
    snippet = re.sub(r"\s+", " ", text[lo:hi]).strip()
    prefix = "..." if lo > 0 else ""
    suffix = "..." if hi < len(text) else ""
    return prefix + snippet + suffix


def analyze(text: str, source: str = "text") -> Analysis:
    a = Analysis(source=source)
    text = text.strip()
    tokens = [t.lower() for t in WORD_RE.findall(text)]
    a.words = len(tokens)
    if a.words == 0:
        raise ValueError("transcript contains no words")
    per100 = 100.0 / a.words

    # -- fluency
    a.fluency = {
        "hesitations": _count_hits(HESITATION_RE, text),
        "crutch words": _count_hits(CRUTCH_RE, text),
        "phrase fillers": _count_hits(PHRASE_FILLER_RE, text),
        "tag questions": _count_hits(TAG_QUESTION_RE, text),
        "hedges": _count_hits(HEDGE_RE, text),
        "filler 'like'": _count_hits(LIKE_FILLER_RE, text),
    }
    a.filler_total = sum(sum(c.values()) for c in a.fluency.values())
    a.just_count = len(JUST_RE.findall(text))

    # -- concision
    sentences = _sentences(text)
    a.sentences = len(sentences)
    for s in sentences:
        n = len(WORD_RE.findall(s))
        if n > a.longest_sentence[0]:
            a.longest_sentence = (n, s)
        if n < FRAGMENT_WORDS:
            a.fragments += 1
        elif n >= RUN_ON_WORDS or (
            n >= 18 and len(CONJUNCTION_RE.findall(s)) >= RUN_ON_CONJUNCTIONS
        ):
            a.run_ons += 1

    # -- coherence
    ellipses = len(ELLIPSIS_RE.findall(text.rstrip(".")))
    cutoffs = len(DASH_CUTOFF_RE.findall(text))
    stutter_matches = [
        m for m in STUTTER_RE.finditer(text)
        if not m.group(1).isdigit()
    ]
    restart_positions = _phrase_restarts(tokens)
    corrections = list(CORRECTION_RE.finditer(text))
    a.repairs = {
        "false starts": ellipses + cutoffs,
        "stutters": len(stutter_matches),
        "phrase restarts": len(restart_positions),
        "self-corrections": len(corrections),
    }
    a.repair_total = sum(a.repairs.values())

    # -- structure
    signposts = len(SIGNPOST_RE.findall(text))
    intent = INTENT_RE.search(text)
    intent_at = intent.start() / max(1, len(text)) if intent else None
    a.structure = {
        "signposts": signposts,
        "intent_position": round(intent_at, 2) if intent_at is not None else None,
        "bluf": intent_at is not None and intent_at <= 0.30,
        "buried_lead": intent_at is not None and intent_at >= 0.65,
        "judged": a.words >= 60,
    }

    # -- rates (per 100 words)
    a.rates = {
        "fillers_per_100w": round(a.filler_total * per100, 1),
        "repairs_per_100w": round(a.repair_total * per100, 1),
        "signposts_per_100w": round(signposts * per100, 2),
        "run_on_share": round(a.run_ons / max(1, a.sentences - a.fragments), 2),
        "fragment_share": round(a.fragments / max(1, a.sentences), 2),
        "avg_sentence_words": round(a.words / max(1, a.sentences), 1),
    }

    # -- scores
    fluency = _clamp(100 - 7.5 * a.filler_total * per100)
    coherence = _clamp(100 - 12 * a.repair_total * per100)
    concision = _clamp(
        100
        - 220 * a.rates["run_on_share"]
        - 50 * max(0.0, a.rates["fragment_share"] - 0.45)
    )
    structure: Optional[int] = None
    if a.structure["judged"]:
        s = 60.0
        if a.structure["bluf"]:
            s += 25
        if a.structure["buried_lead"]:
            s -= 25
        if signposts * per100 >= 0.4:
            s += 15
        structure = _clamp(s)

    weights = {"fluency": 0.30, "concision": 0.25, "coherence": 0.25,
               "structure": 0.20}
    parts = {"fluency": fluency, "concision": concision,
             "coherence": coherence, "structure": structure}
    total_w = sum(w for k, w in weights.items() if parts[k] is not None)
    overall = _clamp(
        sum(parts[k] * w for k, w in weights.items() if parts[k] is not None)
        / total_w
    )
    a.scores = {**parts, "overall": overall}

    # -- excerpts for the report
    a.excerpts = {}
    densest, densest_hits = "", 0
    for s in sentences:
        hits = sum(
            len(r.findall(s))
            for r in (HESITATION_RE, CRUTCH_RE, PHRASE_FILLER_RE,
                      TAG_QUESTION_RE, HEDGE_RE, LIKE_FILLER_RE)
        )
        if hits > densest_hits:
            densest, densest_hits = s, hits
    if densest_hits >= 2:
        a.excerpts["filler_dense"] = [densest]
    if a.longest_sentence[0] >= RUN_ON_WORDS:
        a.excerpts["run_on"] = [a.longest_sentence[1]]
    repair_examples = []
    for m in stutter_matches[:2]:
        repair_examples.append(_context(text, m.start()))
    char_positions = []
    for tok_i in restart_positions[:2]:
        # locate the token in the raw text roughly by walking word matches
        for j, m in enumerate(WORD_RE.finditer(text)):
            if j == tok_i:
                char_positions.append(m.start())
                break
    for pos in char_positions:
        repair_examples.append(_context(text, pos))
    for m in corrections[:1]:
        repair_examples.append(_context(text, m.start()))
    if repair_examples:
        a.excerpts["repairs"] = repair_examples[:3]

    return a


def band(score: int) -> str:
    if score >= 85:
        return "Crisp"
    if score >= 70:
        return "Clear"
    if score >= 50:
        return "Scattered"
    return "Foggy"


def severity(rate: float, thresholds: Tuple[float, float, float]) -> str:
    low, mid, high = thresholds
    if rate < low:
        return "low"
    if rate < mid:
        return "moderate"
    if rate < high:
        return "high"
    return "very high"

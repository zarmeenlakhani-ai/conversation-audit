"""Speaker scorecard: the levels a brilliant public speaker is judged on.

Nine dimensions in four groups, each scored 1.0-5.0 against the same levels:

    1 Distracting   2 Developing   3 Solid   4 Strong   5 Brilliant

    CONTENT    STRUCTURE   Am I structured?          openers, transitions, closers
               POINTS      Am I using bullet points? "Two things", "number one", option A
               CONCISION   Do I get to the point?    run-on sentences
    DELIVERY   FLUENCY     Do I pause, or fill it?   um/uh/hmm, filler "like", crutch
                                                     words, phrase fillers
               COMPOSURE   Am I messy?               restarts, false starts, stutters,
                                                     self-corrections, "no, no" bursts
    CERTAINTY  HEDGING     Do I hedge?               "I think", "maybe", other hedges,
                                                     "I'm not sure"
               CONFIDENCE  Do I sound sure?          tag questions, apologies, deferrals,
                                                     pre-disclaimers, offset by commitments
    EFFECT     TONE        How is my tone?           warm words against sharp ones
               IMPACT      Do my points land?        examples, asks and dates, minus
                                                     open-ended offers

The rows are mutually exclusive: every counted phrase lands in exactly one of
them (see TALLY), so "sorry, sorry" is one apology, not also a stutter and a
restart. Every score comes from an anchor table (metric value -> level) with
linear interpolation, so the same words always get the same score. The
anchors are this tool's calibration, not a published norm. A transcript
can't show voice, pace, silent pauses or body language, so none of those are
scored.

Pure listening turns ("Mm-hmm." "Yeah, okay.") are counted but excluded
before scoring, so a room where you mostly listened isn't marked down for
its acknowledgments.
"""

import bisect
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from conversation_audit import metrics

LEVELS = ("Distracting", "Developing", "Solid", "Strong", "Brilliant")

MIN_WORDS_JUDGED = 250    # below this a room is too thin to score

ACK_WORDS = {
    "mm-hmm", "mmhmm", "mhmm", "mhm", "mm", "hmm", "yeah", "yes", "yep", "yup",
    "okay", "ok", "right", "sure", "cool", "exactly", "correct", "true", "got",
    "it", "gotcha", "oh", "interesting", "perfect", "great", "awesome", "nice",
    "good", "fine", "no", "nope", "thanks", "thank", "you", "wow", "really",
    "totally", "absolutely", "understood", "makes", "sense", "i", "see", "uh",
    "huh", "ah", "alright", "all", "love", "that", "lovely", "hi", "hello", "bye",
}

# --- STRUCTURE / POINTS --------------------------------------------------------

_COUNT = r"(?:two|three|four|five|2|3|4|5)"
_ORDINAL = r"(?:one|two|three|four|five|1|2|3|4|5)"
# POINTS: content chunked into numbered points - announcing the count,
# numbering as you go, or naming options
ANNOUNCED_RE = re.compile(
    rf"\b{_COUNT} (?:things|points|options|reasons|steps|questions|cases|parts"
    r"|buckets|problems|ideas|asks|items|priorities|scenarios|pieces|pillars|challenges"
    r"|issues|concerns|goals|updates|topics|blockers|learnings|takeaways|risks"
    r"|decisions|examples|phases|stages|approaches|models|ways)\b"
    r"|\ba couple of (?:things|points|options|questions)\b",
    re.IGNORECASE,
)
ORDINAL_RE = re.compile(
    r"\bfirst(?:ly)?,|\bfirstly\b|\bsecondly\b|\bthirdly\b|\bfirst of all\b"
    r"|(?<!a )(?<!one )(?<!wait a )\bsecond,|\bthird,"
    rf"|\bnumber {_ORDINAL}\b|\bstep {_ORDINAL}\b|\bpoint {_ORDINAL}\b",
    re.IGNORECASE,
)
OPTION_RE = re.compile(r"\boption (?:a|b|c|one|two|1|2)\b", re.IGNORECASE)
ENUM_RE = re.compile("|".join(r.pattern for r in (ORDINAL_RE, ANNOUNCED_RE, OPTION_RE)),
                     re.IGNORECASE)

# STRUCTURE: opening with the point, moving between points, and closing
OPENER_RE = re.compile(
    r"\bthe (?:point|goal|ask|plan|takeaway|decision|problem|issue|agenda|priority"
    r"|context|idea|question|thing|reason|difference|challenge|risk|catch|summary)"
    r" (?:is|here is|here's)\b"
    r"|\bmy (?:ask|question|point|recommendation|proposal|suggestion) is\b"
    r"|\b(?:the|our|my) (?:goal|aim|ask|plan|idea|priority|agenda)\b(?:\s+[\w'-]+){1,6}?\s+is\b"
    r"|\bwhat i(?: am|'m)? (?:need|want|asking|suggesting|proposing) is\b"
    r"|\bhere'?s (?:the thing|what i|my)\b|\bthe agenda\b|\blet me (?:start|begin) with\b",
    re.IGNORECASE,
)
TRANSITION_RE = re.compile(
    r"\bmoving on\b|\bthe other (?:thing|point|piece|question)\b"
    r"|\b(?:one )?last (?:thing|point|question)\b|\bfinally,",
    re.IGNORECASE,
)
CLOSER_RE = re.compile(
    r"\bto (?:recap|summarize|summarise|sum up)\b|\bin summary\b|\bbottom line\b"
    r"|\bin short\b|\blong story short\b|\bnext steps?\b|\baction items?\b",
    re.IGNORECASE,
)
FRAME_RE = re.compile("|".join(r.pattern for r in (OPENER_RE, TRANSITION_RE, CLOSER_RE)),
                      re.IGNORECASE)

# --- COMPOSURE -----------------------------------------------------------------

NO_BURST_RE = re.compile(r"\bno(?:,?\s+no)+\b", re.IGNORECASE)
LONG_NO_BURST_RE = re.compile(r"\bno(?:,?\s+no){2,}\b", re.IGNORECASE)

# --- FLUENCY -------------------------------------------------------------------

SPOKEN_HESITATION_RE = re.compile(r"\b(?:u+m+|u+h+|e+r+m+|hmm+)\b", re.IGNORECASE)
UM_RE = re.compile(r"\b(?:u+m+|e+r+m+)\b", re.IGNORECASE)
UH_RE = re.compile(r"\b(?:u+h+|hmm+)\b", re.IGNORECASE)

# --- HEDGING -------------------------------------------------------------------

I_THINK_RE = re.compile(r"\bi think\b", re.IGNORECASE)
MAYBE_RE = re.compile(r"\bmaybe\b", re.IGNORECASE)
# the rest of the analyzer's hedges, so the three rows together are HEDGE_RE
OTHER_HEDGE_RE = re.compile(
    r"\b(?:i feel like|i feel that|i guess|i suppose|probably|possibly|a little bit"
    r"|a bit|somewhat|hopefully)\b",
    re.IGNORECASE,
)
UNSURE_RE = re.compile(
    r"\bi'?m not (?:super |very |too |really |a hundred percent |100% )?sure\b"
    r"|\bnot sure\b|\bi don'?t know\b|\bi'?m not certain\b",
    re.IGNORECASE,
)

# --- CONFIDENCE ----------------------------------------------------------------

RIGHT_TAG_RE = re.compile(r"\bright\s*\?", re.IGNORECASE)
OTHER_TAG_RE = re.compile(r"\b(?:okay|ok|yeah|you know)\s*\?", re.IGNORECASE)
APOLOGY_RE = re.compile(r"\b(?:sorry|i apologi[sz]e|my bad)\b", re.IGNORECASE)
# "sorry, sorry, sorry" is one apology
APOLOGY_BURST_RE = re.compile(
    r"\b(?:sorry|i apologi[sz]e|my bad)(?:[,.]?\s+sorry)*\b", re.IGNORECASE)
DEFERRAL_RE = re.compile(
    r"\bgive me (?:a )?(?:little |bit of |couple of |few )?"
    r"(?:time|minutes?|moment|sec(?:ond)?s?|days?)\b"
    r"|\blet me (?:think|revert|get back|come back|circle back)\b"
    r"|\bi'?ll (?:think|brainstorm) about\b|\bi'?ll think about it\b"
    r"|\bwe can talk about (?:this|it|that) later\b"
    r"|\blet me know if\b|\bif you want(?: me)? to\b"
    r"|\bdo you need (?:any|anything)\b|\banything (?:else )?i can do\b",
    re.IGNORECASE,
)
PREDISCLAIMER_RE = re.compile(
    r"\bmight (?:be|sound) (?:stupid|dumb|wrong|silly)\b|\bstupid (?:question|idea)\b"
    r"|\bdumb (?:question|idea)\b|\bcorrect me if\b|\bi could be wrong\b"
    r"|\bmaybe i'?m (?:biased|wrong)\b|\bthis (?:might|may) sound\b",
    re.IGNORECASE,
)
COMMIT_RE = re.compile(
    r"\b(?:i will|i'll)\s+(?!think\b|try\b|see\b|brainstorm\b|just\b|maybe\b)[a-z]+"
    r"|\b(?:we will|we'll)\s+(?!see\b|try\b|maybe\b)[a-z]+"
    r"|\b(?:i'm|we're|i am|we are) going to\b"
    r"|\blet'?s\s+(?!say\b|see\b|just\b)[a-z]+"
    r"|\bi need you to\b|\b(?:i|we) (?:recommend|propose|decided)\b"
    r"|\bmy recommendation\b|\bdone deal\b|\bthe decision is\b",
    re.IGNORECASE,
)

# --- TONE ----------------------------------------------------------------------

WARM_RE = re.compile(
    r"\bthank you\b|\bthanks\b|\bappreciate\b|\bgrateful\b"
    r"|\blove (?:that|this|it|the idea|your|how)\b|\bi like (?:that|this|the idea|it|how)\b"
    r"|\b(?:great|good|nice) (?:job|work|point|question|idea|one)\b|\bwell done\b"
    r"|\bamazing\b|\bawesome\b|\bbrilliant\b|\blovely\b|\bbeautiful\b|\bperfect\b"
    r"|\bcongrat\w*|\bglad\b|\bexcited\b|\bthat'?s fair\b|\bfair enough\b"
    r"|\bgood to (?:see|hear|know)\b|\bhow are you\b|\bhope you\b",
    re.IGNORECASE,
)
EDGE_RE = re.compile(
    r"\bthat'?s (?:wrong|not (?:true|right|what i))\b|\bnot what i (?:said|was saying|meant)\b"
    r"|\byou'?re (?:wrong|not listening|not getting it)\b|\bmakes no sense\b"
    r"|\bridiculous\b|\bannoying\b|\bfrustrat\w*|\bseriously\?"
    r"|\bi already (?:told|said|shared|mentioned|explained)\b"
    r"|\bas i (?:said|mentioned|told you)\b|\blike i said\b|\bhow many times\b",
    re.IGNORECASE,
)
WE_RE = re.compile(r"\b(?:we|us|our|ours|let'?s)\b", re.IGNORECASE)
I_RE = re.compile(r"\b(?:i|me|my|mine|i'm|i've|i'll|i'd)\b", re.IGNORECASE)

# --- IMPACT --------------------------------------------------------------------

_DAY = (r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow"
        r"|tonight|eod|end of (?:the )?(?:day|week)|next week|this week)")
EXAMPLE_RE = re.compile(
    r"\bfor example\b|\bfor instance\b|\blet'?s say\b|\bimagine\b|\blet'?s take\b"
    r"|\bas an example\b|\bcase in point\b|\b(?:two|three|2|3) cases\b",
    re.IGNORECASE,
)
ASK_RE = re.compile(
    r"\bi need you to\b"
    r"|\b(?:can|could) you (?:please )?(?:send|share|check|push|call|review|confirm"
    r"|update|add|fix|look|get|make|do|set|move|put|give|tell|ping|email|book"
    r"|create|help|show|draft|prepare|finalize|finalise)\b"
    r"|\bplease (?:send|share|check|confirm|update|add|fix|review|make|do|tell|ping)\b"
    r"|\bnext steps? (?:for|is|are|will)\b"
    r"|\b(?:i'll|i will|we'll|we will) (?:send|share|get you|fix|update|build|call|ping"
    r"|email|set up|put together|draft|follow up|confirm|talk to|circulate|schedule"
    r"|book|deliver|finish|research)\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(rf"\bby {_DAY}\b", re.IGNORECASE)
OPEN_OFFER_RE = re.compile(
    r"\blet me know if\b|\bif you want(?: me)?(?: to)?\b|\bdo you need (?:any|anything)\b"
    r"|\banything (?:else )?i can\b|\bhappy to help\b"
    r"|\bwe can talk about (?:it|this|that) later\b|\bmaybe we can\b|\bwe'?ll see\b",
    re.IGNORECASE,
)

# --- anchors: metric value -> score, linear between points --------------------
# (value, score) pairs sorted by value. For "lower is better" metrics the
# scores fall as the value rises.

ANCHORS: Dict[str, List[Tuple[float, float]]] = {
    # openers, transitions and closers per 1,000 words
    "structure": [(0.0, 1.0), (0.8, 2.0), (1.8, 3.0), (3.2, 4.0), (5.0, 5.0)],
    # numbered points (counts, ordinals, options) per 1,000 words
    "points": [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 5.0)],
    # run-on sentences per 1,000 words
    "concision": [(0.8, 5.0), (1.6, 4.0), (2.8, 3.0), (4.0, 2.0), (5.5, 1.0)],
    # filled pauses, filler "like", phrase fillers and crutch words per 100 words
    "fluency": [(0.7, 5.0), (1.3, 4.0), (2.0, 3.0), (3.0, 2.0), (4.0, 1.0)],
    # restarts + false starts + stutters + self-corrections + "no, no" bursts,
    # per 100 words
    "composure": [(0.5, 5.0), (1.0, 4.0), (1.7, 3.0), (2.5, 2.0), (3.5, 1.0)],
    # hedges ("I think", "maybe", "I'm not sure"...) per 100 words
    "hedging": [(0.3, 5.0), (0.6, 4.0), (1.0, 3.0), (1.4, 2.0), (1.9, 1.0)],
    # tag questions, apologies, deferrals and pre-disclaimers, minus half the
    # clear commitments, per 100 words
    "confidence": [(0.15, 5.0), (0.35, 4.0), (0.65, 3.0), (1.0, 2.0), (1.4, 1.0)],
    # warm words minus sharp ones, per 1,000 words
    "tone": [(-2.0, 1.0), (0.0, 2.0), (2.0, 3.0), (4.0, 4.0), (6.0, 5.0)],
    # examples + asks + dates named - open offers, per 1,000 words
    "impact": [(0.0, 1.0), (1.5, 2.0), (3.0, 3.0), (5.0, 4.0), (7.0, 5.0)],
}

DIMENSIONS: List[Tuple[str, str, str]] = [
    ("structure", "Structure", "Am I structured?"),
    ("points", "Points", "Am I using bullet points?"),
    ("concision", "Concision", "Do I get to the point?"),
    ("fluency", "Fluency", "Do I pause, or fill it?"),
    ("composure", "Composure", "Am I messy?"),
    ("hedging", "Hedging", "Do I hedge?"),
    ("confidence", "Confidence", "Do I sound sure?"),
    ("tone", "Tone", "How is my tone?"),
    ("impact", "Impact", "Do my points land?"),
]

# the four groups the dimensions fall into, in reading order
GROUPS: List[Tuple[str, str, List[str]]] = [
    ("Content", "what you said", ["structure", "points", "concision"]),
    ("Delivery", "how it came out", ["fluency", "composure"]),
    ("Certainty", "how sure you sounded", ["hedging", "confidence"]),
    ("Effect", "how it landed", ["tone", "impact"]),
]

BRILLIANT = {
    "structure": "5+ openers, transitions or closers per 1,000 words: \"The ask is...\", \"Next steps...\"",
    "points": "4+ numbered points per 1,000 words: \"Two things. One... Two...\"",
    "concision": "under one run-on sentence per 1,200 words",
    "fluency": "under one filler every 140 words",
    "composure": "a restart no more than once every 200 words",
    "hedging": "under one hedge every 330 words",
    "confidence": "under one tag question, apology or deferral every 650 words, net of commitments",
    "tone": "warm and steady: 6+ more warm words than sharp ones per 1,000",
    "impact": "7+ examples, asks or dates named per 1,000 words",
}

FIXES = {
    "structure": "open every long answer with its count and its point: \"Two things. The ask is...\"",
    "points": "when an answer runs past three sentences, number it: \"One... Two...\"",
    "concision": "one thought per sentence: end it, then start the next",
    "fluency": "leave a silent beat where the um wants to go",
    "composure": "finish the sentence you started, then improve it in the next one",
    "hedging": "drop the \"I think\": pause, then say the claim bare",
    "confidence": "end claims on a period; save one real check-question for the end",
    "tone": "in disagreement, one \"No.\" and the fact; thank people by name",
    "impact": "every offer gets a thing and a day: \"I'll send X by Y.\"",
}


def interpolate(value: float, anchors: Sequence[Tuple[float, float]]) -> float:
    """Piecewise-linear score for ``value``, clamped to the end anchors."""
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= value <= x1:
            t = (value - x0) / (x1 - x0) if x1 != x0 else 0.0
            return y0 + t * (y1 - y0)
    return anchors[-1][1]


def level(score: float) -> str:
    """Name of the level a 1-5 score rounds to (half up)."""
    idx = int(score + 0.5)
    return LEVELS[max(1, min(5, idx)) - 1]


def is_listening_turn(turn: str) -> bool:
    toks = [re.sub(r"[^\w'-]", "", w).lower() for w in turn.split()]
    toks = [t for t in toks if t]
    return bool(toks) and len(toks) <= 6 and all(t in ACK_WORDS for t in toks)


def _words(text: str) -> int:
    return len(metrics.WORD_RE.findall(text))


def _count(regex: re.Pattern, text: str) -> int:
    return sum(1 for _ in regex.finditer(text))


def _spans(regex: re.Pattern, text: str) -> List[Tuple[int, int]]:
    return [m.span() for m in regex.finditer(text)]


def _stutter_spans(text: str) -> List[Tuple[int, int]]:
    # "I, I" - not stacked acknowledgments ("yeah, yeah") and not "no, no",
    # which has its own row
    return [m.span() for m in metrics.STUTTER_RE.finditer(text)
            if m.group(1).lower() not in ACK_WORDS and not m.group(1).isdigit()]


def _restart_spans(text: str) -> List[Tuple[int, int]]:
    """The re-launched word pair of each phrase restart."""
    toks = list(metrics.WORD_RE.finditer(text))
    words = [m.group(0).lower() for m in toks]
    return [(toks[i].start(), toks[i + 1].end())
            for i in metrics._phrase_restarts(words)
            if not all(w in ACK_WORDS for w in words[i:i + 2])]


def _false_start_spans(text: str) -> List[Tuple[int, int]]:
    return (_spans(metrics.ELLIPSIS_RE, text.rstrip("."))
            + _spans(metrics.DASH_CUTOFF_RE, text))


# Every row of the scorecard, in the order rows claim words. When patterns
# overlap ("sorry, sorry" is an apology, a stutter and a restart; "let me know
# if" is a deferral and an open offer), the first row listed takes the phrase
# and later rows skip it, so each phrase is counted exactly once.
TALLY: List[Tuple[str, object]] = [
    ("no_bursts", NO_BURST_RE),
    ("apologies", APOLOGY_BURST_RE),
    ("open_offers", OPEN_OFFER_RE),
    ("predisclaimers", PREDISCLAIMER_RE),
    ("openers", OPENER_RE), ("transitions", TRANSITION_RE), ("closers", CLOSER_RE),
    ("announced", ANNOUNCED_RE), ("ordinals", ORDINAL_RE), ("options", OPTION_RE),
    ("examples", EXAMPLE_RE), ("asks", ASK_RE), ("dates", DATE_RE),
    ("right_tags", RIGHT_TAG_RE), ("other_tags", OTHER_TAG_RE),
    ("not_sure", UNSURE_RE), ("i_think", I_THINK_RE), ("maybe", MAYBE_RE),
    ("other_hedges", OTHER_HEDGE_RE),
    ("deferrals", DEFERRAL_RE), ("commitments", COMMIT_RE),
    ("sharp", EDGE_RE), ("warm", WARM_RE),
    ("um", UM_RE), ("uh", UH_RE), ("like", metrics.LIKE_FILLER_RE),
    ("phrase_fillers", metrics.PHRASE_FILLER_RE), ("crutch", metrics.CRUTCH_RE),
    ("stutters", _stutter_spans), ("self_corrections", metrics.CORRECTION_RE),
    ("restarts", _restart_spans), ("false_starts", _false_start_spans),
]


def claims(text: str) -> List[Tuple[str, int, int]]:
    """(row, start, end) for every counted phrase; no two share a character."""
    kept: List[Tuple[str, int, int]] = []
    starts: List[int] = []
    ends: List[int] = []
    for row, find in TALLY:
        spans = find(text) if callable(find) else _spans(find, text)
        for s, e in spans:
            i = bisect.bisect_left(starts, e)
            if i and ends[i - 1] > s:
                continue  # an earlier row already counted these words
            starts.insert(i, s)
            ends.insert(i, e)
            kept.append((row, s, e))
    return kept


def tally(text: str) -> Dict[str, int]:
    """Count every row, giving each overlapping phrase to the first row that claims it."""
    counts = {row: 0 for row, _ in TALLY}
    for row, _, _ in claims(text):
        counts[row] += 1
    return counts


@dataclass
class Dimension:
    key: str
    name: str
    question: str
    value: Optional[float]
    score: Optional[float]
    detail: Dict[str, float] = field(default_factory=dict)

    @property
    def level(self) -> Optional[str]:
        return None if self.score is None else level(self.score)

    def to_dict(self) -> dict:
        return {
            "key": self.key, "name": self.name, "question": self.question,
            "value": self.value, "score": self.score, "level": self.level,
            "detail": self.detail, "brilliant": BRILLIANT[self.key],
            "fix": FIXES[self.key],
        }


@dataclass
class Scorecard:
    source: str
    words: int
    turns: int
    listening_turns: int
    dimensions: List[Dimension]
    tone_label: Optional[str] = None

    @property
    def overall(self) -> Optional[float]:
        scored = [d.score for d in self.dimensions if d.score is not None]
        return round(sum(scored) / len(scored), 1) if scored else None

    @property
    def overall_level(self) -> Optional[str]:
        return None if self.overall is None else level(self.overall)

    def dimension(self, key: str) -> Dimension:
        return next(d for d in self.dimensions if d.key == key)

    def to_dict(self) -> dict:
        return {
            "source": self.source, "words": self.words, "turns": self.turns,
            "listening_turns": self.listening_turns,
            "overall": self.overall, "overall_level": self.overall_level,
            "tone_label": self.tone_label,
            "dimensions": [d.to_dict() for d in self.dimensions],
        }


def tone_label(warm_per_k: float, edge_per_k: float) -> str:
    """How the word choice reads: warmth on one axis, sharpness on the other."""
    warm = warm_per_k >= 4.0
    sharp = edge_per_k >= 1.5
    if warm and not sharp:
        return "Warm and steady"
    if warm and sharp:
        return "Warm, sharp in disagreement"
    if not sharp:
        return "Neutral, businesslike"
    return "Cool, sharp in disagreement"


def build(turns: Sequence[str], source: str = "text") -> Scorecard:
    """Score one speaker's turns (one utterance per item)."""
    turns = [t.strip() for t in turns if t and t.strip()]
    spoken = [t for t in turns if not is_listening_turn(t)]
    listening = len(turns) - len(spoken)
    text = "\n".join(spoken)
    words = _words(text)

    def scored(key: str, value: float) -> Optional[float]:
        if words < MIN_WORDS_JUDGED:
            return None
        return round(interpolate(value, ANCHORS[key]), 1)

    if words == 0:
        dims = [Dimension(k, n, q, None, None) for k, n, q in DIMENSIONS]
        return Scorecard(source, 0, len(turns), listening, dims)

    a = metrics.analyze(text, source=source)
    per100 = 100.0 / words
    perk = 1000.0 / words
    t = tally(text)

    frames = t["openers"] + t["transitions"] + t["closers"]
    enums = t["announced"] + t["ordinals"] + t["options"]
    fillers = t["um"] + t["uh"] + t["like"] + t["phrase_fillers"] + t["crutch"]
    mess = (t["restarts"] + t["false_starts"] + t["stutters"]
            + t["self_corrections"] + t["no_bursts"])
    hedges = t["i_think"] + t["maybe"] + t["other_hedges"] + t["not_sure"]
    tentative = (t["right_tags"] + t["other_tags"] + t["apologies"]
                 + t["deferrals"] + t["predisclaimers"])
    net_tentative = max(0.0, tentative - 0.5 * t["commitments"])
    warm, edge = t["warm"], t["sharp"]
    we, me = _count(WE_RE, text), _count(I_RE, text)
    impact = max(0.0, t["examples"] + t["asks"] + t["dates"] - t["open_offers"])

    names = {k: (n, q) for k, n, q in DIMENSIONS}

    def dim(key: str, value: float, detail: Dict[str, float]) -> Dimension:
        return Dimension(key, *names[key], round(value, 2), scored(key, value), detail)

    def rows(*keys: str) -> Dict[str, float]:
        return {k: t[k] for k in keys}

    dims = [
        dim("structure", frames * perk, rows("openers", "transitions", "closers")),
        dim("points", enums * perk, rows("announced", "ordinals", "options")),
        dim("concision", a.run_ons * perk,
            {"run_ons": a.run_ons, "longest": a.longest_sentence[0],
             "avg_sentence": a.rates["avg_sentence_words"]}),
        dim("fluency", fillers * per100,
            rows("um", "uh", "like", "phrase_fillers", "crutch")),
        dim("composure", mess * per100,
            rows("restarts", "false_starts", "stutters", "self_corrections", "no_bursts")),
        dim("hedging", hedges * per100, rows("i_think", "maybe", "other_hedges", "not_sure")),
        dim("confidence", net_tentative * per100,
            rows("right_tags", "other_tags", "apologies", "deferrals", "predisclaimers",
                 "commitments")),
        dim("tone", (warm - edge) * perk,
            {"warm": warm, "sharp": edge,
             "we_share": round(we / (we + me), 2) if we + me else 0.0}),
        dim("impact", impact * perk, rows("examples", "asks", "dates", "open_offers")),
    ]
    label = tone_label(warm * perk, edge * perk) if words >= MIN_WORDS_JUDGED else None
    return Scorecard(source, words, len(turns), listening, dims, label)


def render(card: Scorecard) -> str:
    """Plain-text scoreboard for the terminal."""
    if card.overall is None:
        why = (" You mostly listened." if card.listening_turns * 2 > card.turns
               else "")
        return (f"SPEAKER SCORECARD  {card.source}\n"
                f"Too little speech to score: {card.words} words"
                f" (scoring starts at {MIN_WORDS_JUDGED}).{why}")
    lines = [
        f"SPEAKER SCORECARD  {card.source}  ({card.words} words spoken)",
        f"Overall: {card.overall}/5 - {card.overall_level}",
        "",
    ]
    for d in card.dimensions:
        if d.score is None:
            continue
        filled = int(d.score + 0.5)
        bar = "#" * filled + "." * (5 - filled)
        extra = f"  [{card.tone_label}]" if d.key == "tone" and card.tone_label else ""
        lines.append(f"  {d.name:<11} {d.score:>4.1f} {bar}  {d.level:<11} {d.question}{extra}")
    weakest = min((d for d in card.dimensions if d.score is not None),
                  key=lambda d: d.score)
    lines += ["", f"Biggest lever -> {weakest.name.lower()}: {FIXES[weakest.key]}"]
    return "\n".join(lines)

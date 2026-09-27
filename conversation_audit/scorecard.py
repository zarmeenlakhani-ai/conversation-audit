"""Speaker scorecard: the levels a brilliant public speaker is judged on.

Eight dimensions, each scored 1.0-5.0 against the same five levels:

    1 Distracting   2 Developing   3 Solid   4 Strong   5 Brilliant

    STRUCTURE   Am I structured?            framing the point, transitions, closes
    POINTS      Do I speak in points?       numbered points: "Two things. One..."
    COMPOSURE   Am I messy?                 restarts, false starts, "no, no" bursts
    CONCISION   Do I get to the point?      run-on sentences
    FLUENCY     Do fillers get in the way?  um, uh, filler "like", "you know", crutch words
    CONFIDENCE  Do I sound sure?            hedges, tag questions, apologies and
                                            deferrals, offset by clear commitments
    TONE        How do I come across?       warmth versus edge in word choice
    IMPACT      Do my points land?          examples, concrete asks and dated
                                            commitments, minus open-ended offers

Every score comes from an anchor table (metric value -> level) with linear
interpolation between anchors, so the same words always get the same score.
The anchors describe what each level sounds like in speech; they are this
tool's calibration, not a published norm. A transcript can't show voice,
pace, pauses or body language, so none of those are scored.

Pure listening turns ("Mm-hmm." "Yeah, okay.") are counted but excluded
before scoring, so a room where you mostly listened isn't marked down for
its acknowledgments.
"""

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
# POINTS: content chunked into numbered points
ENUM_RE = re.compile(
    r"\bfirst(?:ly)?,|\bfirstly\b|\bsecondly\b|\bthirdly\b|\bfirst of all\b"
    r"|(?<!a )(?<!one )(?<!wait a )\bsecond,|\bthird,"
    rf"|\bnumber {_ORDINAL}\b|\bstep {_ORDINAL}\b|\bpoint {_ORDINAL}\b"
    rf"|\b{_COUNT} (?:things|points|options|reasons|steps|questions|cases|parts"
    r"|buckets|problems|ideas|asks|items|priorities|scenarios|pieces|pillars|challenges"
    r"|issues|concerns|goals|updates|topics|blockers|learnings|takeaways|risks"
    r"|decisions|examples|phases|stages|approaches|models|ways)\b"
    r"|\ba couple of (?:things|points|options|questions)\b"
    r"|\boption (?:a|b|c|one|two|1|2)\b",
    re.IGNORECASE,
)
# STRUCTURE: framing the point, moving between points, and closing
FRAME_RE = re.compile(
    r"\bthe (?:point|goal|ask|plan|takeaway|decision|problem|issue|agenda|priority"
    r"|context|idea|question|thing|reason|difference|challenge|risk|catch|summary)"
    r" (?:is|here is|here's)\b"
    r"|\bmy (?:ask|question|point|recommendation|proposal|suggestion) is\b"
    r"|\b(?:the|our|my) (?:goal|aim|ask|plan|idea|priority|agenda)\b(?:\s+[\w'-]+){1,6}?\s+is\b"
    r"|\bwhat i(?: am|'m)? (?:need|want|asking|suggesting|proposing) is\b"
    r"|\bhere'?s (?:the thing|what i|my)\b|\bthe agenda\b|\blet me (?:start|begin) with\b"
    r"|\bto (?:recap|summarize|summarise|sum up)\b|\bin summary\b|\bbottom line\b"
    r"|\bin short\b|\blong story short\b|\bnext steps?\b|\baction items?\b"
    r"|\bmoving on\b|\bthe other (?:thing|point|piece|question)\b"
    r"|\b(?:one )?last (?:thing|point|question)\b|\bfinally,",
    re.IGNORECASE,
)

# --- COMPOSURE -----------------------------------------------------------------

NO_BURST_RE = re.compile(r"\bno(?:,?\s+no)+\b", re.IGNORECASE)
LONG_NO_BURST_RE = re.compile(r"\bno(?:,?\s+no){2,}\b", re.IGNORECASE)

# --- FLUENCY -------------------------------------------------------------------

SPOKEN_HESITATION_RE = re.compile(r"\b(?:u+m+|u+h+|e+r+m+|hmm+)\b", re.IGNORECASE)

# --- CONFIDENCE ----------------------------------------------------------------

UNSURE_RE = re.compile(
    r"\bi'?m not (?:super |very |too |really |a hundred percent |100% )?sure\b"
    r"|\bnot sure\b|\bi don'?t know\b|\bi'?m not certain\b",
    re.IGNORECASE,
)
APOLOGY_RE = re.compile(r"\b(?:sorry|i apologi[sz]e|my bad)\b", re.IGNORECASE)
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
    rf"|\bnext steps? (?:for|is|are|will)\b|\bby {_DAY}\b"
    r"|\b(?:i'll|i will|we'll|we will) (?:send|share|get you|fix|update|build|call|ping"
    r"|email|set up|put together|draft|follow up|confirm|talk to|circulate|schedule"
    r"|book|deliver|finish|research)\b",
    re.IGNORECASE,
)
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
    # framing, transition and closing lines per 1,000 words
    "structure": [(0.0, 1.0), (0.8, 2.0), (1.8, 3.0), (3.2, 4.0), (5.0, 5.0)],
    # numbered points (counts, ordinals, options) per 1,000 words
    "points": [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 5.0)],
    # restarts + false starts + real stutters + self-corrections + "no, no"
    # bursts, per 100 words
    "composure": [(0.5, 5.0), (1.0, 4.0), (1.7, 3.0), (2.5, 2.0), (3.5, 1.0)],
    # run-on sentences per 1,000 words
    "concision": [(0.8, 5.0), (1.6, 4.0), (2.8, 3.0), (4.0, 2.0), (5.5, 1.0)],
    # spoken fillers per 100 words
    "fluency": [(0.7, 5.0), (1.3, 4.0), (2.0, 3.0), (3.0, 2.0), (4.0, 1.0)],
    # net tentative markers per 100 words
    "confidence": [(0.6, 5.0), (1.1, 4.0), (1.7, 3.0), (2.4, 2.0), (3.2, 1.0)],
    # warm words minus sharp ones, per 1,000 words
    "tone": [(-2.0, 1.0), (0.0, 2.0), (2.0, 3.0), (4.0, 4.0), (6.0, 5.0)],
    # examples + concrete asks/commitments - open offers, per 1,000 words
    "impact": [(0.0, 1.0), (1.5, 2.0), (3.0, 3.0), (5.0, 4.0), (7.0, 5.0)],
}

DIMENSIONS: List[Tuple[str, str, str]] = [
    ("structure", "Structure", "Am I structured?"),
    ("points", "Points", "Do I speak in points?"),
    ("composure", "Composure", "Am I messy?"),
    ("concision", "Concision", "Do I get to the point?"),
    ("fluency", "Fluency", "Do fillers get in the way?"),
    ("confidence", "Confidence", "Do I sound sure?"),
    ("tone", "Tone", "How do I come across?"),
    ("impact", "Impact", "Do my points land?"),
]

BRILLIANT = {
    "structure": "frames, signposts and closes: 5+ lines like \"The ask is...\" or \"Next steps...\" per 1,000 words",
    "points": "4+ numbered points per 1,000 words: \"Two things. One... Two...\"",
    "composure": "a restart no more than once every 200 words",
    "concision": "under one run-on sentence per 1,200 words",
    "fluency": "under one filler every 140 words",
    "confidence": "under one hedge, tag question or apology every 160 words",
    "tone": "warm and steady: 6+ more warm words than sharp ones per 1,000",
    "impact": "7+ examples, concrete asks or dated commitments per 1,000 words",
}

FIXES = {
    "structure": "open every long answer with its count: \"Two things.\"",
    "points": "when an answer runs past three sentences, number it: \"One... Two...\"",
    "composure": "finish the sentence you started, then improve it in the next one",
    "concision": "one thought per sentence: end it, then start the next",
    "fluency": "leave a silent beat where the um wants to go",
    "confidence": "say the claim bare; save one real check-question for the end",
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

    frames = _count(FRAME_RE, text)
    enums = _count(ENUM_RE, text)

    no_bursts = _count(NO_BURST_RE, text)
    real_stutters = sum(
        1 for m in metrics.STUTTER_RE.finditer(text)
        if m.group(1).lower() not in ACK_WORDS and not m.group(1).isdigit()
    )
    mess = (a.repairs["false starts"] + a.repairs["phrase restarts"]
            + a.repairs["self-corrections"] + real_stutters + no_bursts)

    hes = _count(SPOKEN_HESITATION_RE, text)
    like = _count(metrics.LIKE_FILLER_RE, text)
    phrase = _count(metrics.PHRASE_FILLER_RE, text)
    crutch = _count(metrics.CRUTCH_RE, text)
    fillers = hes + like + phrase + crutch

    hedges = _count(metrics.HEDGE_RE, text) + _count(UNSURE_RE, text)
    tags = _count(metrics.TAG_QUESTION_RE, text)
    apologies = _count(APOLOGY_RE, text)
    deferrals = _count(DEFERRAL_RE, text)
    predis = _count(PREDISCLAIMER_RE, text)
    commits = _count(COMMIT_RE, text)
    tentative = hedges + tags + apologies + deferrals + predis
    net_tentative = max(0.0, tentative - 0.5 * commits)

    warm = _count(WARM_RE, text)
    edge = _count(EDGE_RE, text) + _count(LONG_NO_BURST_RE, text)
    we = _count(WE_RE, text)
    me = _count(I_RE, text)

    examples = _count(EXAMPLE_RE, text)
    asks = _count(ASK_RE, text)
    open_offers = _count(OPEN_OFFER_RE, text)
    impact = max(0.0, examples + asks - open_offers)

    dims = [
        Dimension("structure", "Structure", "Am I structured?",
                  round(frames * perk, 2), scored("structure", frames * perk),
                  {"framing_lines": frames}),
        Dimension("points", "Points", "Do I speak in points?",
                  round(enums * perk, 2), scored("points", enums * perk),
                  {"numbered_points": enums}),
        Dimension("composure", "Composure", "Am I messy?",
                  round(mess * per100, 2), scored("composure", mess * per100),
                  {"restarts": a.repairs["phrase restarts"],
                   "false_starts": a.repairs["false starts"],
                   "stutters": real_stutters,
                   "self_corrections": a.repairs["self-corrections"],
                   "no_bursts": no_bursts}),
        Dimension("concision", "Concision", "Do I get to the point?",
                  round(a.run_ons * perk, 2), scored("concision", a.run_ons * perk),
                  {"run_ons": a.run_ons, "longest": a.longest_sentence[0]}),
        Dimension("fluency", "Fluency", "Do fillers get in the way?",
                  round(fillers * per100, 2), scored("fluency", fillers * per100),
                  {"hesitations": hes, "like": like, "phrases": phrase,
                   "crutch": crutch}),
        Dimension("confidence", "Confidence", "Do I sound sure?",
                  round(net_tentative * per100, 2),
                  scored("confidence", net_tentative * per100),
                  {"hedges": hedges, "tags": tags, "apologies": apologies,
                   "deferrals": deferrals, "predisclaimers": predis,
                   "commitments": commits}),
        Dimension("tone", "Tone", "How do I come across?",
                  round((warm - edge) * perk, 2), scored("tone", (warm - edge) * perk),
                  {"warmth": warm, "edge": edge,
                   "we_share": round(we / (we + me), 2) if we + me else 0.0}),
        Dimension("impact", "Impact", "Do my points land?",
                  round(impact * perk, 2), scored("impact", impact * perk),
                  {"examples": examples, "asks": asks, "open_offers": open_offers}),
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

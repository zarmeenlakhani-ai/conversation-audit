"""The no-essay renderer: sharp pointers with recommendations.

One header line, then 3 pointers by default (up to 10), each a single line
ending in a concrete fix, ranked by how much each issue is costing the
speaker. Built for reading on a phone right after a call.
"""

import os
from typing import List, Tuple

from conversation_audit.metrics import Analysis, band, biggest_lever

_FILLER_FIX = {
    "hesitations": "swap the um for a silent beat",
    "tag questions": "end statements with a period, not a check-in",
    "crutch words": "delete it - the sentence survives without it",
    "hedges": "state it plainly; hedges dilute the ask",
    "phrase fillers": "cut it and land the noun",
    "filler 'like'": "drop the 'like' - pause instead",
}


def _short_source(source: str) -> str:
    suffix = ""
    if " [" in source:
        source, rest = source.split(" [", 1)
        suffix = " [" + rest
    base = os.path.basename(source.rstrip("/")) or source
    return base + suffix


def _top_fillers(a: Analysis) -> List[Tuple[int, str, str]]:
    flat = []
    for cat, counter in a.fluency.items():
        for word, n in counter.items():
            flat.append((n, word, cat))
    flat.sort(reverse=True)
    return flat


def pointers(a: Analysis, limit: int = 3) -> List[str]:
    """Ranked one-line pointers, worst habit first. Empty means crisp."""
    limit = max(1, min(10, limit))
    candidates: List[Tuple[float, str]] = []

    rr = a.rates["repairs_per_100w"]
    fr = a.rates["fillers_per_100w"]

    if a.repair_total and rr >= 1.0:
        parts = ", ".join(
            f"{v} {k.rstrip('s') if v == 1 else k}"
            for k, v in a.repairs.items() if v
        )
        quote = ""
        if a.excerpts.get("repairs"):
            q = a.excerpts["repairs"][0].strip()
            if len(q) > 60:
                q = q[:60].rsplit(" ", 1)[0] + "..."
            quote = f' e.g. "{q}"'
        candidates.append((
            rr / 1.5,
            f"{a.repair_total} broken thoughts ({parts}){quote}"
            " -> finish the sentence, then upgrade it.",
        ))

    top = _top_fillers(a)
    if fr >= 3 and top:
        tics = ", ".join(f"{w} x{n}" for n, w, _ in top[:2])
        fix = _FILLER_FIX.get(top[0][2], "pause instead")
        candidates.append((
            fr / 4,
            f"{fr} fillers per 100 words ({tics} lead) -> {fix}.",
        ))

    st = a.structure
    if st["judged"]:
        if st["buried_lead"]:
            pos = int(st["intent_position"] * 100)
            candidates.append((
                1.3,
                f"Your ask landed {pos}% of the way in"
                " -> open with it: 'My ask is...'",
            ))
        elif st["intent_position"] is None:
            candidates.append((
                1.1,
                "No clear ask anywhere"
                " -> decide the one thing you want before you speak.",
            ))

    if a.run_ons:
        candidates.append((
            1.0 + 0.15 * a.run_ons,
            f"{a.run_ons} run-on sentence{'s' if a.run_ons != 1 else ''}"
            f" (longest {a.longest_sentence[0]} words)"
            " -> one thought per sentence; end it, start the next.",
        ))

    if a.rates["fragment_share"] >= 0.55 and a.words >= 80 and rr < 1.5:
        candidates.append((
            0.7,
            "Over half your sentences are under 4 words"
            " -> connect related thoughts into one full sentence.",
        ))

    candidates.sort(key=lambda c: -c[0])
    return [line for _, line in candidates[:limit]]


def render_brief(a: Analysis, limit: int = 3) -> str:
    overall = a.scores["overall"]
    lines = [
        f"{_short_source(a.source)} - Clarity {overall}/100 ({band(overall)})"
    ]
    points = pointers(a, limit)
    if not points:
        lines.append("Nothing material - this was crisp. Same pace next time.")
        return "\n".join(lines)
    for i, p in enumerate(points, 1):
        lines.append(f"{i}. {p}")
    worst, tip = biggest_lever(a)
    lines.append(f"Drill: {tip}.")
    return "\n".join(lines)

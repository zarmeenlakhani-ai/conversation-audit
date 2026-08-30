"""Render analyses for a terminal (and one-liners for notifications)."""

import os
import sys
from typing import List, Optional

from conversation_audit.metrics import Analysis, band, biggest_lever, severity

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
RED, YELLOW, GREEN, CYAN = "\033[31m", "\033[33m", "\033[32m", "\033[36m"


def use_color(flag: Optional[bool] = None) -> bool:
    if flag is not None:
        return flag
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _score_color(score: int) -> str:
    if score >= 85:
        return GREEN
    if score >= 70:
        return YELLOW
    return RED


def _quote(text: str, limit: int = 110) -> str:
    text = text.strip()
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return '"' + text + '"'


def render(a: Analysis, color: Optional[bool] = None) -> str:
    c = use_color(color)

    def paint(text: str, *codes: str) -> str:
        return "".join(codes) + text + RESET if c else text

    lines: List[str] = []
    overall = a.scores["overall"]
    lines.append(
        paint("CONVERSATION AUDIT", BOLD)
        + f"  {a.source}  "
        + paint(f"({a.words} words, ~{a.minutes:.1f} min spoken)", DIM)
    )
    lines.append(
        "Overall clarity: "
        + paint(f"{overall}/100 - {band(overall)}", BOLD, _score_color(overall))
    )
    lines.append("")

    # FLUENCY
    fr = a.rates["fillers_per_100w"]
    lines.append(
        paint(f"FLUENCY {a.scores['fluency']}/100", BOLD)
        + f"  {fr} fillers per 100 words "
        + paint(f"({severity(fr, (1.5, 4, 7))})", DIM)
    )
    top = []
    for cat, counter in a.fluency.items():
        for word, n in counter.most_common():
            top.append((n, word, cat))
    top.sort(reverse=True)
    if top:
        shown = ", ".join(f"{w} x{n}" for n, w, _ in top[:8])
        lines.append(f"  {shown}")
    if a.just_count >= 3:
        lines.append(
            paint(f"  also noticed: 'just' x{a.just_count} (unscored, worth watching)", DIM)
        )
    for ex in a.excerpts.get("filler_dense", []):
        lines.append(paint("  worst stretch: " + _quote(ex), DIM))
    lines.append("")

    # CONCISION
    lines.append(
        paint(f"CONCISION {a.scores['concision']}/100", BOLD)
        + f"  {a.run_ons} run-on sentence{'s' if a.run_ons != 1 else ''}"
        + f" / {a.fragments} fragments"
        + f" / avg {a.rates['avg_sentence_words']} words per sentence"
    )
    if a.longest_sentence[0] > 0:
        lines.append(
            paint(
                f"  longest ({a.longest_sentence[0]} words): "
                + _quote(a.longest_sentence[1]),
                DIM,
            )
        )
    lines.append("")

    # COHERENCE
    rr = a.rates["repairs_per_100w"]
    lines.append(
        paint(f"COHERENCE {a.scores['coherence']}/100", BOLD)
        + f"  {rr} broken thoughts per 100 words "
        + paint(f"({severity(rr, (0.5, 1.5, 3))})", DIM)
    )
    detail = ", ".join(f"{k}: {v}" for k, v in a.repairs.items() if v)
    if detail:
        lines.append(f"  {detail}")
    for ex in a.excerpts.get("repairs", []):
        lines.append(paint("  " + _quote(ex), DIM))
    lines.append("")

    # STRUCTURE
    if a.scores["structure"] is None:
        lines.append(
            paint("STRUCTURE -", BOLD)
            + paint("  too short to judge (needs ~60+ words)", DIM)
        )
    else:
        lines.append(
            paint(f"STRUCTURE {a.scores['structure']}/100", BOLD)
            + f"  signposts: {a.structure['signposts']}"
        )
        if a.structure["bluf"]:
            lines.append("  main ask stated up front - good")
        elif a.structure["buried_lead"]:
            pos = int(a.structure["intent_position"] * 100)
            lines.append(
                f"  buried lead: the ask first appears {pos}% of the way in"
                " - try stating it in sentence one"
            )
        elif a.structure["intent_position"] is None:
            lines.append("  no clear ask or goal detected - what should the listener do?")

    worst, tip = biggest_lever(a)
    lines.append("")
    lines.append(paint(f"Biggest lever -> {worst}: {tip}", CYAN))
    return "\n".join(lines)


def one_line(a: Analysis) -> str:
    overall = a.scores["overall"]
    return (
        f"Clarity {overall} ({band(overall)}) - "
        f"{a.rates['fillers_per_100w']} fillers/100w, "
        f"{a.repair_total} broken thoughts, {a.run_ons} run-ons"
    )


def render_coach(coach: dict, color: Optional[bool] = None) -> str:
    c = use_color(color)

    def paint(text: str, *codes: str) -> str:
        return "".join(codes) + text + RESET if c else text

    lines = ["", paint("CLAUDE COACH", BOLD, CYAN)]
    lines.append(paint("verdict", BOLD) + "  " + coach["verdict"])
    lines.append(paint("the real point", BOLD) + "  " + coach["the_real_point"])
    lines.append("")
    lines.append(paint("say it like this (BLUF rewrite):", BOLD))
    for ln in coach["bluf_rewrite"].splitlines():
        lines.append("  " + ln)
    lines.append("")
    mece = coach["mece"]
    lines.append(paint("MECE check", BOLD) + "  " + mece["verdict"])
    for o in mece.get("overlaps", []):
        lines.append("  overlap: " + o)
    for g in mece.get("gaps", []):
        lines.append("  gap: " + g)
    if coach.get("habits"):
        lines.append("")
        lines.append(paint("recurring habits", BOLD))
        for h in coach["habits"]:
            lines.append(f"  - {h['habit']}")
            lines.append(paint(f"    e.g. \"{h['quote']}\"", DIM))
            lines.append(f"    fix: {h['fix']}")
    lines.append("")
    lines.append(paint("drill for next time", BOLD) + "  " + coach["drill"])
    return "\n".join(lines)

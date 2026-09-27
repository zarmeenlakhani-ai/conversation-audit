"""The speaker scorecard as a single HTML page.

Built from scorecards (see scorecard.py) plus optional notes: a one-line
verdict, one real quote per dimension, and move overrides. Everything that
can be computed is computed here, so a week's page is reproducible from the
transcripts alone; the notes only add the human read.

    spec = week_spec(rooms, title=..., eyebrow=..., history=[...], notes={...})
    html = render(spec)
"""

import html
from typing import Dict, List, Optional, Sequence, Tuple

from conversation_audit import scorecard as sc

FONTS = ("https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800"
         "&family=Instrument+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400"
         "&family=Instrument+Serif:ital@0;1&display=swap")

# the five questions asked of the scorecard, in the order they were asked
QUESTION_ORDER = ["composure", "structure", "points", "tone", "confidence"]
QUESTION_TEXT = {
    "composure": "Am I messy?",
    "structure": "Am I structured?",
    "points": "Am I using bullet points?",
    "tone": "How is my tone?",
    "confidence": "How confident do I sound?",
}


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def _lvl(score: Optional[float]) -> int:
    return 0 if score is None else max(1, min(5, int(score + 0.5)))


def threshold_for(key: str, target: float) -> float:
    """Metric value at which ``key`` reaches ``target`` score (inverse of the anchors)."""
    anchors = sc.ANCHORS[key]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        lo, hi = min(y0, y1), max(y0, y1)
        if lo <= target <= hi and y1 != y0:
            return x0 + (target - y0) * (x1 - x0) / (y1 - y0)
    return anchors[-1][0] if target >= max(y for _, y in anchors) else anchors[0][0]


def metric_text(d: dict, tone_label: Optional[str]) -> str:
    k, v, x = d["key"], d["value"], d["detail"]
    if v is None:
        return "Not enough speech to score."
    if k == "structure":
        return (f"{x['framing_lines']} framing or closing lines (“The ask is…”,"
                f" “Next steps…”): {v:g} per 1,000 words")
    if k == "points":
        return (f"{x['numbered_points']} numbered points (“two things”, “number one”):"
                f" {v:g} per 1,000 words")
    if k == "composure":
        return (f"{v:g} restarts, false starts or “no, no” bursts per 100 words"
                f" ({x['no_bursts']} “no, no” bursts)")
    if k == "concision":
        return (f"{x['run_ons']} run-on sentences, {v:g} per 1,000 words;"
                f" longest {x['longest']} words")
    if k == "fluency":
        return (f"{v:g} fillers per 100 words: um/uh {x['hesitations']}, “like” {x['like']},"
                f" crutch words {x['crutch']}")
    if k == "confidence":
        tentative = (x["hedges"] + x["tags"] + x["apologies"] + x["deferrals"]
                     + x["predisclaimers"])
        return (f"{tentative} hedges, tag questions or apologies against {x['commitments']}"
                f" clear commitments ({v:g} net per 100 words)")
    if k == "tone":
        we = int(round(100 * x["we_share"]))
        label = f"{tone_label}: " if tone_label else ""
        return (f"{label}{x['warmth']} warm words against {x['edge']} sharp ones;"
                f" “we” is {we}% of your pronouns")
    if k == "impact":
        return (f"{x['examples']} examples and {x['asks']} concrete asks or dated commitments,"
                f" against {x['open_offers']} open-ended offers")
    return ""


def _target_text(key: str, target_score: float) -> str:
    t = threshold_for(key, target_score)
    unit = {
        "structure": ("framing lines per 1,000 words", "at least"),
        "points": ("numbered points per 1,000 words", "at least"),
        "composure": ("restarts per 100 words", "under"),
        "concision": ("run-ons per 1,000 words", "under"),
        "fluency": ("fillers per 100 words", "under"),
        "confidence": ("net hedges per 100 words", "under"),
        "tone": ("more warm than sharp words per 1,000", "at least"),
        "impact": ("examples, asks or dated commitments per 1,000 words", "at least"),
    }[key]
    return f"{unit[1]} {t:.1f} {unit[0]}"


def auto_moves(card: dict, n: int = 3) -> List[dict]:
    dims = [d for d in card["dimensions"] if d["score"] is not None]
    dims.sort(key=lambda d: d["score"])
    moves = []
    for d in dims[:n]:
        nxt = min(5, _lvl(d["score"]) + 1)
        moves.append({
            "dimension": d["name"],
            "title": d["fix"][0].upper() + d["fix"][1:],
            "target": (f"Next level ({sc.LEVELS[nxt - 1]}): "
                       f"{_target_text(d['key'], float(nxt) - 0.5 if nxt < 5 else 4.5)}"),
        })
    return moves


def week_spec(rooms: Sequence[Tuple[str, str, Sequence[str]]], *, title: str, eyebrow: str,
              week_label: str, history: Sequence[dict] = (), notes: Optional[dict] = None,
              listening_rooms: Sequence[dict] = ()) -> dict:
    """Assemble everything the page needs.

    ``rooms`` is (name, day, turns) per meeting; ``history`` is earlier weeks as
    {"label", "card"} dicts, oldest first.
    """
    notes = notes or {}
    all_turns: List[str] = []
    room_cards = []
    for name, day, turns in rooms:
        all_turns.extend(turns)
        room_cards.append({"name": name, "day": day,
                           "card": sc.build(turns, name).to_dict()})
    card = sc.build(all_turns, week_label).to_dict()
    trend = [{"label": h["label"], "card": h["card"]} for h in history]
    trend.append({"label": week_label, "card": card, "current": True})
    return {
        "title": title, "eyebrow": eyebrow, "week_label": week_label,
        "card": card, "rooms": room_cards, "trend": trend,
        "listening_rooms": list(listening_rooms),
        "verdict": notes.get("verdict"),
        "answers": notes.get("answers", {}),
        "evidence": notes.get("evidence", {}),
        "moves": notes.get("moves") or auto_moves(card),
    }


# --- rendering -----------------------------------------------------------------

CSS = """
:root {
  --page: #f5f6f8; --surface: #ffffff; --ink: #101216; --ink-2: #474c56; --ink-3: #767c87;
  --line: #e2e5ea; --line-2: #c9ced6; --track: #e7eaef; --quote: #f0f3f7;
  --accent: #1c5cab;
  --l1: #86b6ef; --l2: #5598e7; --l3: #2a78d6; --l4: #1c5cab; --l5: #104281;
  --l1-ink: #0e1a2c; --l2-ink: #0e1a2c; --l3-ink: #ffffff; --l4-ink: #ffffff; --l5-ink: #ffffff;
  --keep: #0a7a44; --fix: #b4410f;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0e1014; --surface: #16181c; --ink: #eceef2; --ink-2: #b3b9c3; --ink-3: #868d98;
    --line: #262a31; --line-2: #363b44; --track: #262a31; --quote: #1c1f25;
    --accent: #6da7ec;
    --l1: #184f95; --l2: #256abf; --l3: #3987e5; --l4: #6da7ec; --l5: #9ec5f4;
    --l1-ink: #e6edf8; --l2-ink: #ffffff; --l3-ink: #0a1320; --l4-ink: #0a1320; --l5-ink: #0a1320;
    --keep: #4dbd85; --fix: #f08a5d;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0e1014; --surface: #16181c; --ink: #eceef2; --ink-2: #b3b9c3; --ink-3: #868d98;
  --line: #262a31; --line-2: #363b44; --track: #262a31; --quote: #1c1f25;
  --accent: #6da7ec;
  --l1: #184f95; --l2: #256abf; --l3: #3987e5; --l4: #6da7ec; --l5: #9ec5f4;
  --l1-ink: #e6edf8; --l2-ink: #ffffff; --l3-ink: #0a1320; --l4-ink: #0a1320; --l5-ink: #0a1320;
  --keep: #4dbd85; --fix: #f08a5d;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font-family: "Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 16px; line-height: 1.55; }
.page { max-width: 1040px; margin: 0 auto; padding-inline: 20px; padding-block: 40px 88px; }
h1, h2, h3 { margin: 0; text-wrap: balance; }
p { margin: 0; }
.display { font-family: "Big Shoulders Display", "Arial Narrow", "Roboto Condensed", system-ui, sans-serif; }
.eyebrow { font-size: 12px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-3); }

/* hero */
.hero { display: grid; grid-template-columns: auto 1fr; gap: 8px 36px; align-items: end; margin-top: 14px; }
.big { font-family: "Big Shoulders Display", "Arial Narrow", system-ui, sans-serif; font-weight: 800;
  font-size: clamp(96px, 18vw, 168px); line-height: 0.82; letter-spacing: -0.01em; }
.big small { font-size: 0.34em; font-weight: 700; color: var(--ink-3); margin-left: 4px; }
.hero-side { padding-bottom: 6px; }
.hero-level { font-family: "Big Shoulders Display", "Arial Narrow", system-ui, sans-serif; font-weight: 800;
  font-size: 44px; line-height: 1; text-transform: uppercase; letter-spacing: 0.02em; }
.verdict { font-size: 18px; color: var(--ink-2); margin-top: 10px; max-width: 58ch; }
.verdict strong { color: var(--ink); }
@media (max-width: 640px) { .hero { grid-template-columns: 1fr; } }

/* ladder: a 1-5 meter with the five levels named under it */
.ladder { margin-top: 28px; }
.ladder .track { position: relative; height: 12px; border-radius: 6px; background: var(--track); }
.ladder .fill { position: absolute; inset: 0 auto 0 0; border-radius: 6px; }
.ladder .tick { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--surface); }
.ladder .mark { position: absolute; top: -7px; width: 4px; height: 26px; border-radius: 2px; background: var(--ink);
  transform: translateX(-2px); box-shadow: 0 0 0 2px var(--page); }
.ladder .names { position: relative; height: 18px; margin-top: 10px; font-size: 12px; color: var(--ink-3); }
.ladder .names span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
.ladder .names span:first-child { transform: none; }
.ladder .names span:last-child { transform: translateX(-100%); }
.ladder .names span.on { color: var(--ink); font-weight: 700; }

.weeks { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }
.wk { display: flex; align-items: baseline; gap: 6px; padding: 6px 10px; border: 1px solid var(--line);
  border-radius: 999px; background: var(--surface); font-size: 13px; color: var(--ink-2);
  font-variant-numeric: tabular-nums; }
.wk b { color: var(--ink); font-weight: 700; }
.wk.now { border-color: var(--ink); }

section { margin-top: 56px; }
.sec-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 6px 20px;
  border-top: 3px solid var(--ink); padding-top: 12px; margin-bottom: 18px; }
.sec-head h2 { font-family: "Big Shoulders Display", "Arial Narrow", system-ui, sans-serif; font-weight: 800;
  font-size: 34px; line-height: 1; text-transform: uppercase; letter-spacing: 0.01em; }
.sec-head p { font-size: 14px; color: var(--ink-3); }

/* the five questions */
.qa { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.qa li { display: grid; grid-template-columns: minmax(0, 15rem) 9.5rem 1fr; gap: 6px 18px; align-items: baseline;
  padding: 14px 16px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
.qa .q { font-family: "Instrument Serif", Georgia, serif; font-style: italic; font-size: 24px; line-height: 1.15; }
.qa .a { color: var(--ink-2); }
@media (max-width: 760px) { .qa li { grid-template-columns: 1fr; } }

.pill { display: inline-flex; align-items: baseline; gap: 6px; padding: 3px 10px; border-radius: 999px;
  font-size: 13px; font-weight: 700; white-space: nowrap; font-variant-numeric: tabular-nums; }
.pill.l0 { background: var(--track); color: var(--ink-3); }
.l1 { background: var(--l1); color: var(--l1-ink); } .l2 { background: var(--l2); color: var(--l2-ink); }
.l3 { background: var(--l3); color: var(--l3-ink); } .l4 { background: var(--l4); color: var(--l4-ink); }
.l5 { background: var(--l5); color: var(--l5-ink); }

/* scoreboard cards */
.cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
@media (max-width: 760px) { .cards { grid-template-columns: 1fr; } }
.dim { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 18px 18px 16px;
  display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.dim-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.dim h3 { font-family: "Big Shoulders Display", "Arial Narrow", system-ui, sans-serif; font-weight: 800;
  font-size: 26px; line-height: 1; text-transform: uppercase; letter-spacing: 0.02em; }
.dim .question { font-family: "Instrument Serif", Georgia, serif; font-style: italic; font-size: 18px;
  color: var(--ink-2); margin-top: 4px; }
.dim .score { text-align: right; }
.dim .score .n { font-family: "Big Shoulders Display", "Arial Narrow", system-ui, sans-serif; font-weight: 800;
  font-size: 44px; line-height: 0.9; font-variant-numeric: tabular-nums; }
.dim .score .pill { margin-top: 6px; }
.dim .ladder { margin-top: 0; }
.dim .ladder .track { height: 8px; }
.dim .ladder .mark { top: -6px; height: 20px; }
.metric { font-size: 14px; color: var(--ink-2); }
.trend { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: end; }
.trend .lab { font-size: 11.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3);
  padding-bottom: 16px; }
.bars { display: flex; align-items: flex-end; gap: 6px; height: 84px; padding-top: 20px; border-bottom: 1px solid var(--line-2); }
.bar { flex: 1 1 0; max-width: 34px; display: flex; flex-direction: column; justify-content: flex-end; align-items: center;
  height: 100%; position: relative; }
.bar i { display: block; width: 100%; border-radius: 3px 3px 0 0; }
.bar i.none { background: transparent; border: 1px dashed var(--line-2); border-bottom: none; height: 4px; }
.bar.now i { outline: 2px solid var(--ink); outline-offset: 1px; }
.bar em { position: absolute; left: 0; right: 0; text-align: center; font-style: normal; font-size: 11px;
  line-height: 1; color: var(--ink-3); font-variant-numeric: tabular-nums; }
.bar.now em { color: var(--ink); font-weight: 700; }
.bar-labels { display: flex; gap: 6px; margin-top: 4px; }
.bar-labels span { flex: 1 1 0; max-width: 34px; text-align: center; font-size: 10.5px; color: var(--ink-3); }
.target { font-size: 13.5px; color: var(--ink-3); }
.target b { color: var(--ink-2); }
.ev { margin: 0; padding: 12px 14px; background: var(--quote); border-radius: 8px; border-left: 3px solid var(--line-2); }
.ev.keep { border-left-color: var(--keep); } .ev.fix { border-left-color: var(--fix); }
.ev .tag { font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
.ev.keep .tag { color: var(--keep); } .ev.fix .tag { color: var(--fix); }
.ev q { display: block; font-family: "Instrument Serif", Georgia, serif; font-style: italic; font-size: 19px;
  line-height: 1.35; margin-top: 4px; quotes: "\\201C" "\\201D"; }
.ev cite { display: block; font-style: normal; font-size: 12.5px; color: var(--ink-3); margin-top: 6px; }
.fixline { font-size: 14.5px; }
.fixline b { font-weight: 700; }

/* room heatmap */
.tablewrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
table.heat { border-collapse: separate; border-spacing: 3px; width: 100%; min-width: 820px; font-size: 13.5px; padding: 8px; }
.heat th { font-size: 11.5px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-3);
  text-align: center; padding: 6px 4px; }
.heat th.room, .heat td.room { text-align: left; }
.heat td { padding: 8px 6px; text-align: center; border-radius: 5px; font-variant-numeric: tabular-nums; font-weight: 700; }
.heat td.room { font-weight: 600; min-width: 200px; }
.heat td.room small { display: block; font-weight: 400; color: var(--ink-3); font-size: 12px; }
.heat td.words { color: var(--ink-2); font-weight: 400; }
.heat td.na { color: var(--ink-3); font-weight: 400; background: var(--track); }
.heat tr.week td { border-top: 2px solid var(--ink); }
.heat tr.week td.room { font-weight: 800; }
.legend { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; margin-top: 12px; font-size: 13px; color: var(--ink-2); }
.legend .sw { display: inline-flex; align-items: center; gap: 6px; }
.legend .sw i { width: 14px; height: 14px; border-radius: 3px; display: inline-block; }
.note { font-size: 13.5px; color: var(--ink-3); margin-top: 10px; }

/* moves */
.moves { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
@media (max-width: 860px) { .moves { grid-template-columns: 1fr; } }
.moves li { background: var(--ink); color: var(--page); border-radius: 10px; padding: 18px; display: flex; flex-direction: column; gap: 8px; }
.moves .n { font-family: "Big Shoulders Display", "Arial Narrow", system-ui, sans-serif; font-weight: 800; font-size: 40px; line-height: 0.9; }
.moves .d { font-size: 11.5px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.7; }
.moves .t { font-size: 17px; font-weight: 600; line-height: 1.35; }
.moves .g { font-size: 13.5px; opacity: 0.75; }

details.method { margin-top: 56px; border-top: 1px solid var(--line-2); padding-top: 14px; }
details.method summary { cursor: pointer; font-weight: 700; font-size: 15px; }
details.method summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 4px; }
details.method .body { margin-top: 12px; font-size: 14px; color: var(--ink-2); display: grid; gap: 10px; max-width: 76ch; }
table.anchors { border-collapse: collapse; font-size: 13px; width: 100%; min-width: 640px; }
.anchors th, .anchors td { text-align: left; padding: 6px 10px 6px 0; border-bottom: 1px solid var(--line); vertical-align: top; }
.anchors th { font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-3); }
.anchors td { font-variant-numeric: tabular-nums; }
"""


def _ladder(score: Optional[float], names: bool) -> str:
    if score is None:
        return '<div class="ladder"><div class="track"></div></div>'
    pos = (score - 1.0) / 4.0 * 100.0
    lvl = _lvl(score)
    ticks = "".join(f'<i class="tick" style="left:{p}%"></i>' for p in (25, 50, 75))
    parts = [
        '<div class="ladder" role="img" aria-label="'
        + _e(f"{score:.1f} out of 5, {sc.LEVELS[lvl - 1]}") + '">',
        '<div class="track">',
        f'<div class="fill" style="width:{pos:.1f}%;background:var(--l{lvl})"></div>',
        ticks,
        f'<i class="mark" style="left:{pos:.1f}%"></i>',
        "</div>",
    ]
    if names:
        spans = "".join(
            f'<span class="{"on" if i + 1 == lvl else ""}" style="left:{i * 25}%">{i + 1} {n}</span>'
            for i, n in enumerate(sc.LEVELS)
        )
        parts.append(f'<div class="names" aria-hidden="true">{spans}</div>')
    parts.append("</div>")
    return "".join(parts)


def _pill(score: Optional[float]) -> str:
    if score is None:
        return '<span class="pill l0">Not scored</span>'
    lvl = _lvl(score)
    return f'<span class="pill l{lvl}">{sc.LEVELS[lvl - 1]} · {score:.1f}</span>'


def _trend(key: Optional[str], trend: Sequence[dict]) -> str:
    bars, labels, aria = [], [], []
    for t in trend:
        card = t["card"]
        if key is None:
            s = card["overall"]
        else:
            s = next(d["score"] for d in card["dimensions"] if d["key"] == key)
        now = " now" if t.get("current") else ""
        if s is None:
            bars.append(f'<div class="bar{now}"><i class="none"></i><em style="bottom:8px">–</em></div>')
            aria.append(f"{t['label']} not scored")
        else:
            h = s / 5.0 * 100.0
            bars.append(f'<div class="bar{now}" title="{_e(t["label"])}: {s:.1f}">'
                        f'<i style="height:{h:.0f}%;background:var(--l{_lvl(s)})"></i>'
                        f'<em style="bottom:calc({h:.0f}% + 4px)">{s:.1f}</em></div>')
            aria.append(f"{t['label']} {s:.1f}")
        labels.append(f"<span>{_e(t['label'])}</span>")
    return ('<div class="trend"><div class="lab">By week</div><div>'
            f'<div class="bars" role="img" aria-label="{_e(", ".join(aria))}">{"".join(bars)}</div>'
            f'<div class="bar-labels">{"".join(labels)}</div></div></div>')


def plain_answer(d: dict, card: dict) -> str:
    """One plain-language line answering the dimension's question."""
    k, v, x, s = d["key"], d["value"], d["detail"], d["score"]
    if s is None:
        return "Not enough speech to judge."
    lvl = _lvl(s)
    words = max(1, card["words"])
    if k == "composure":
        verdict = {1: "Yes, often", 2: "Somewhat", 3: "Now and then", 4: "Rarely", 5: "No"}[lvl]
        every = 100.0 / v if v else 0
        line = f"{verdict}: you restart or break off a sentence about once every {every:.0f} words"
        if x["no_bursts"] >= 8:
            line += f", with {x['no_bursts']} \u201cno, no\u201d bursts"
        return line + "."
    if k == "structure":
        verdict = {1: "Not yet", 2: "Not yet", 3: "Partly", 4: "Mostly", 5: "Yes"}[lvl]
        n = x["framing_lines"]
        if not n:
            return f"{verdict}: no framing lines (\u201cThe ask is\u2026\u201d, \u201cNext steps\u2026\u201d) in {words:,} words."
        return (f"{verdict}: you framed, moved between or closed a point {n} times,"
                f" about once every {words / n:,.0f} words.")
    if k == "points":
        verdict = {1: "Rarely", 2: "Sometimes", 3: "Often enough", 4: "Yes", 5: "Yes, consistently"}[lvl]
        n = x["numbered_points"]
        if not n:
            return f"{verdict}: no numbered points in {words:,} words."
        return (f"{verdict}: {n} numbered points (\u201ctwo things\u201d, \u201cnumber one\u201d),"
                f" about one every {words / n:,.0f} words.")
    if k == "tone":
        we = int(round(100 * x["we_share"]))
        return (f"{card.get('tone_label') or 'Mixed'}: {x['warmth']} warm words against"
                f" {x['edge']} sharp ones, and \u201cwe\u201d in {we}% of your pronouns.")
    if k == "confidence":
        verdict = {1: "Unsure", 2: "Often unsure", 3: "Mostly sure", 4: "Sure", 5: "Very sure"}[lvl]
        every = 100.0 / v if v else 0
        tail = f"a hedge, tag question or apology about once every {every:.0f} words" if v else "almost no hedging"
        return f"{verdict}: {tail}, with {x['commitments']} clear commitments."
    return metric_text(d, card.get("tone_label"))


def _answer(d: dict, card: dict, spec: dict) -> str:
    custom = spec["answers"].get(d["key"])
    return _e(custom if custom else plain_answer(d, card))


def render(spec: dict) -> str:
    card = spec["card"]
    dims = {d["key"]: d for d in card["dimensions"]}
    overall = card["overall"]
    out: List[str] = [
        f"<title>{_e(spec['title'])}</title>",
        f'<link rel="stylesheet" href="{FONTS}">',
        f"<style>{CSS}</style>",
        '<main class="page">',
        f'<div class="eyebrow">{_e(spec["eyebrow"])}</div>',
        '<header class="hero">',
        f'<div class="big">{overall:.1f}<small>/5</small></div>' if overall is not None
        else '<div class="big">–</div>',
        '<div class="hero-side">',
        f'<div class="hero-level">{_e(card["overall_level"] or "Not scored")}</div>',
    ]
    if spec.get("verdict"):
        out.append(f'<p class="verdict">{spec["verdict"]}</p>')
    out += ["</div>", "</header>", _ladder(overall, names=True)]

    if len(spec["trend"]) > 1:
        chips = []
        for t in spec["trend"]:
            o = t["card"]["overall"]
            cls = "wk now" if t.get("current") else "wk"
            chips.append(f'<span class="{cls}">{_e(t["label"])} <b>{"–" if o is None else f"{o:.1f}"}</b></span>')
        out.append(f'<div class="weeks" aria-label="Overall score by week">{"".join(chips)}</div>')

    # the five questions
    out += ['<section aria-labelledby="qs">',
            '<div class="sec-head"><h2 id="qs">Your five questions</h2>'
            f'<p>{card["words"]:,} words of yours scored across {len(spec["rooms"])} rooms</p></div>',
            '<ol class="qa">']
    for key in QUESTION_ORDER:
        d = dims[key]
        out.append(f'<li><span class="q">{_e(QUESTION_TEXT[key])}</span>{_pill(d["score"])}'
                   f'<span class="a">{_answer(d, card, spec)}</span></li>')
    out += ["</ol>", "</section>"]

    # scoreboard
    out += ['<section aria-labelledby="sb">',
            '<div class="sec-head"><h2 id="sb">The scoreboard</h2>'
            "<p>Eight things a brilliant speaker is judged on · 1 Distracting to 5 Brilliant</p></div>",
            '<div class="cards">']
    for key, name, question in sc.DIMENSIONS:
        d = dims[key]
        s = d["score"]
        out.append('<article class="dim">')
        out.append('<div class="dim-top"><div>'
                   f"<h3>{_e(name)}</h3><div class=\"question\">{_e(question)}</div></div>"
                   '<div class="score">'
                   + (f'<div class="n">{s:.1f}</div>' if s is not None else '<div class="n">–</div>')
                   + f"{_pill(s)}</div></div>")
        out.append(_ladder(s, names=False))
        out.append(f'<p class="metric">{_e(metric_text(d, card.get("tone_label")))}</p>')
        if len(spec["trend"]) > 1:
            out.append(_trend(key, spec["trend"]))
        out.append(f'<p class="target"><b>Brilliant looks like:</b> {_e(d["brilliant"])}</p>')
        ev = spec["evidence"].get(key)
        if ev:
            kind = ev.get("kind", "fix")
            out.append(f'<blockquote class="ev {kind}"><span class="tag">{"Keep" if kind == "keep" else "Fix"}</span>'
                       f'<q>{_e(ev["quote"])}</q><cite>{_e(ev.get("room", ""))}</cite></blockquote>')
        fix = ev.get("fix") if ev else None
        out.append(f'<p class="fixline"><b>Fix:</b> {_e(fix or d["fix"])}</p>')
        out.append("</article>")
    out += ["</div>", "</section>"]

    # rooms
    heads = "".join(f'<th scope="col" title="{_e(q)}">{_e(n)}</th>' for _, n, q in sc.DIMENSIONS)
    out += ['<section aria-labelledby="rooms">',
            '<div class="sec-head"><h2 id="rooms">Room by room</h2>'
            "<p>Where you were messy, where you were brilliant</p></div>",
            '<div class="tablewrap"><table class="heat">',
            f'<thead><tr><th scope="col" class="room">Room</th><th scope="col">Words</th>{heads}'
            '<th scope="col">Overall</th></tr></thead><tbody>']
    for r in spec["rooms"] + [{"name": "Whole week", "day": "", "card": card, "week": True}]:
        c = r["card"]
        rd = {d["key"]: d for d in c["dimensions"]}
        cls = ' class="week"' if r.get("week") else ""
        cells = []
        for key, name, _ in sc.DIMENSIONS:
            s = rd[key]["score"]
            if s is None:
                cells.append('<td class="na" title="too short to score">–</td>')
            else:
                cells.append(f'<td class="l{_lvl(s)}" title="{_e(name)}: {s:.1f} {_e(sc.LEVELS[_lvl(s) - 1])}">{s:.1f}</td>')
        o = c["overall"]
        ocell = ('<td class="na">–</td>' if o is None
                 else f'<td class="l{_lvl(o)}" title="Overall: {o:.1f} {_e(sc.LEVELS[_lvl(o) - 1])}">{o:.1f}</td>')
        day = f"<small>{_e(r['day'])}</small>" if r.get("day") else ""
        out.append(f'<tr{cls}><td class="room">{_e(r["name"])}{day}</td>'
                   f'<td class="words">{c["words"]:,}</td>{"".join(cells)}{ocell}</tr>')
    out.append("</tbody></table></div>")
    swatches = "".join(f'<span class="sw"><i class="l{i + 1}"></i>{i + 1} {n}</span>'
                       for i, n in enumerate(sc.LEVELS))
    out.append(f'<div class="legend">{swatches}<span class="sw"><i style="background:var(--track)"></i>too short to score</span></div>')
    if spec["listening_rooms"]:
        lst = "; ".join(f"{_e(x['name'])} ({_e(x['day'])}): {_e(x['note'])}" for x in spec["listening_rooms"])
        out.append(f'<p class="note">Not scored: {lst}.</p>')
    out.append("</section>")

    # moves
    out += ['<section aria-labelledby="mv">',
            '<div class="sec-head"><h2 id="mv">Three moves for next week</h2>'
            "<p>From your three lowest scores</p></div>", '<ol class="moves">']
    for i, m in enumerate(spec["moves"][:3], 1):
        out.append(f'<li><div class="n">{i}</div><div class="d">{_e(m["dimension"])}</div>'
                   f'<div class="t">{_e(m["title"])}</div><div class="g">{_e(m["target"])}</div></li>')
    out += ["</ol>", "</section>"]

    # method
    rows = []
    for key, name, _ in sc.DIMENSIONS:
        a = sc.ANCHORS[key]
        pts = " · ".join(f"{x:g} → {y:g}" for x, y in a)
        rows.append(f"<tr><td><b>{_e(name)}</b></td><td>{_e(_UNITS[key])}</td><td>{_e(pts)}</td></tr>")
    out += ['<details class="method"><summary>How this is scored</summary><div class="body">',
            "<p>Each dimension is measured from your own words in the transcript (other speakers are"
            " never scored), then placed on the same five levels: 1 Distracting, 2 Developing,"
            " 3 Solid, 4 Strong, 5 Brilliant. Scores move smoothly between the anchor points below,"
            " so the same words always get the same score. Pure listening turns (“Mm-hmm.”,"
            " “Yeah, okay.”) are set aside first, and rooms under 250 words are not scored.</p>",
            "<p>The anchors are this tool's calibration of what each level sounds like in a"
            " meeting, not a published norm. Tone is read from word choice only. Voice, pace,"
            " pauses and body language don't appear in a transcript, so they aren't scored."
            " Transcribers sometimes mishear words; quotes were checked against the transcript.</p>",
            '<div style="overflow-x:auto"><table class="anchors"><thead><tr><th>Dimension</th>'
            "<th>Measured as</th><th>Anchors (value → score)</th></tr></thead><tbody>",
            "".join(rows), "</tbody></table></div></div></details>",
            "</main>"]
    return "\n".join(out)


_UNITS = {
    "structure": "framing, transition and closing lines per 1,000 words",
    "points": "numbered points per 1,000 words",
    "composure": "restarts, false starts, real stutters, self-corrections and “no, no” bursts per 100 words (lower is better)",
    "concision": "run-on sentences per 1,000 words (lower is better)",
    "fluency": "um, uh, filler “like”, “you know” and crutch words per 100 words (lower is better)",
    "confidence": "hedges, tag questions, apologies and deferrals minus half your clear commitments, per 100 words (lower is better)",
    "tone": "warm words minus sharp ones per 1,000 words",
    "impact": "examples, concrete asks and dated commitments minus open-ended offers, per 1,000 words",
}

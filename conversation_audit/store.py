"""Append-only history of audits, so trends are visible over time.

Records live in ``~/.conversation-audit/history.jsonl`` (override the
directory with ``CONVERSATION_AUDIT_HOME``). One JSON object per line.
"""

import datetime as _dt
import json
import os
from typing import List, Optional

from conversation_audit.metrics import Analysis, band

_SPARK = "▁▂▃▄▅▆▇█"


def base_dir() -> str:
    return os.environ.get(
        "CONVERSATION_AUDIT_HOME",
        os.path.join(os.path.expanduser("~"), ".conversation-audit"),
    )


def history_path() -> str:
    return os.path.join(base_dir(), "history.jsonl")


def record(a: Analysis) -> None:
    os.makedirs(base_dir(), exist_ok=True)
    row = {
        "ts": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": os.path.basename(a.source) if a.source != "stdin" else "stdin",
        "words": a.words,
        "scores": a.scores,
        "fillers_per_100w": a.rates["fillers_per_100w"],
        "repairs_per_100w": a.rates["repairs_per_100w"],
        "run_ons": a.run_ons,
    }
    with open(history_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load(limit: int) -> List[dict]:
    path = history_path()
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def sparkline(values: List[float], invert: bool = False) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return _SPARK[3] * len(values)
    out = []
    for v in values:
        frac = (v - lo) / (hi - lo)
        if invert:
            frac = 1 - frac
        out.append(_SPARK[int(frac * (len(_SPARK) - 1))])
    return "".join(out)


def render_trends(limit: int = 12) -> Optional[str]:
    rows = load(limit)
    if not rows:
        return None
    lines = [f"Last {len(rows)} audits ({history_path()})", ""]
    header = f"{'date':<17}{'source':<26}{'clarity':<10}{'fillers/100w':<14}{'repairs/100w':<14}"
    lines.append(header)
    for r in rows:
        date = r["ts"][:16].replace("T", " ")
        source = (r["source"][:23] + "...") if len(r["source"]) > 25 else r["source"]
        overall = r["scores"]["overall"]
        lines.append(
            f"{date:<17}{source:<26}"
            f"{str(overall) + ' ' + band(overall):<10}"
            f"{r['fillers_per_100w']:<14}{r['repairs_per_100w']:<14}"
        )
    lines.append("")
    overalls = [float(r["scores"]["overall"]) for r in rows]
    fillers = [float(r["fillers_per_100w"]) for r in rows]
    repairs = [float(r["repairs_per_100w"]) for r in rows]
    lines.append(f"clarity  {sparkline(overalls)}  (up = better)")
    lines.append(f"fillers  {sparkline(fillers)}  (down = better)")
    lines.append(f"repairs  {sparkline(repairs)}  (down = better)")
    return "\n".join(lines)

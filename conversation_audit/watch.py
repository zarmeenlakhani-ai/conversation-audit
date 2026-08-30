"""Watch a folder for new transcripts and audit them as they land.

Polling watcher (no dependencies). A file is analyzed once its mtime has
been stable for one full poll interval, so half-written exports aren't
scored. Files that already exist when the watch starts are skipped - drop
new transcripts in, or touch an old one to re-audit it.
"""

import os
import platform
import subprocess
import sys
import time
from typing import Dict, Optional, Tuple

from conversation_audit import metrics, report, store
from conversation_audit.transcript import load_transcript

TRANSCRIPT_EXTENSIONS = (".txt", ".md", ".vtt", ".srt")


def _scan(directory: str) -> Dict[str, Tuple[float, int]]:
    found = {}
    for root, _dirs, files in os.walk(directory):
        for name in files:
            if not name.lower().endswith(TRANSCRIPT_EXTENSIONS):
                continue
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            found[path] = (st.st_mtime, st.st_size)
    return found


def notify(title: str, body: str) -> None:
    """Best-effort desktop notification; silently no-ops if unavailable."""
    try:
        if platform.system() == "Darwin":
            script = 'display notification "{}" with title "{}"'.format(
                body.replace('"', "'"), title.replace('"', "'")
            )
            subprocess.run(["osascript", "-e", script], capture_output=True,
                           timeout=10)
        elif platform.system() == "Linux":
            subprocess.run(["notify-send", title, body], capture_output=True,
                           timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def _audit_file(path: str, speaker: Optional[str], deep: bool,
                model: Optional[str]) -> None:
    try:
        transcript = load_transcript(path)
        # unlabeled transcripts are solo dictations - audit them whole
        if speaker and transcript.speakers:
            transcript = transcript.for_speaker(speaker)
            if not transcript.utterances:
                print(f"[watch] {path}: no lines from speaker '{speaker}',"
                      " skipped", file=sys.stderr)
                return
        analysis = metrics.analyze(transcript.text, source=path)
    except (OSError, ValueError) as e:
        print(f"[watch] skipped {path}: {e}", file=sys.stderr)
        return
    print()
    print(report.render(analysis))
    store.record(analysis)
    notify(os.path.basename(path), report.one_line(analysis))
    if deep:
        from conversation_audit import coach

        try:
            verdict = coach.deep_analysis(transcript.text, analysis, model)
            print(report.render_coach(verdict))
        except coach.CoachError as e:
            print(f"[watch] deep analysis failed: {e}", file=sys.stderr)


def watch(directory: str, interval: float = 5.0, speaker: Optional[str] = None,
          deep: bool = False, model: Optional[str] = None,
          once: bool = False) -> int:
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        print(f"not a directory: {directory}", file=sys.stderr)
        return 2

    if once:
        # analyze everything currently in the folder, then exit
        for path in sorted(_scan(directory)):
            _audit_file(path, speaker, deep, model)
        return 0

    known = _scan(directory)  # existing files are not re-audited
    pending: Dict[str, Tuple[float, int]] = {}
    print(
        f"watching {directory} for new transcripts "
        f"({', '.join(TRANSCRIPT_EXTENSIONS)}) - ctrl-c to stop"
    )
    try:
        while True:
            time.sleep(interval)
            current = _scan(directory)
            for path, sig in current.items():
                if known.get(path) == sig:
                    continue
                if pending.get(path) == sig:
                    # unchanged for a full interval - safe to read
                    _audit_file(path, speaker, deep, model)
                    known[path] = sig
                    del pending[path]
                else:
                    pending[path] = sig
            for path in list(known):
                if path not in current:
                    known.pop(path)
                    pending.pop(path, None)
    except KeyboardInterrupt:
        print("\nstopped")
        return 0

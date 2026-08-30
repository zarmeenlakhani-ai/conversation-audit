"""Load and normalize transcripts from the formats they actually arrive in.

Handles:
- plain text / markdown (a dictation, a prompt draft, raw notes)
- speaker-labeled meeting transcripts ("Zarmeen Lakhani: ...", "Me: ...",
  "Speaker 2: ...") as produced by Wispr Flow, Granola, Zoom, etc.
- WebVTT / SRT caption files (timestamps and cue numbers stripped,
  ``<v Name>`` voice tags become speaker labels)
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# "Name: said something" - name up to 40 chars, no colon inside
_LABEL_RE = re.compile(r"^\s*([A-Za-z][^:\n]{0,40}?)\s*:\s+(\S.*)$")
_VTT_TIME_RE = re.compile(r"-->")
_VTT_VOICE_RE = re.compile(r"<v(?:\.[^ >]*)?\s+([^>]+)>")
_TAG_RE = re.compile(r"</?[^>]{0,60}>")
# short stage directions: [inaudible], (laughs), [crosstalk 00:12] ...
_ANNOTATION_RE = re.compile(
    r"\[[^\]]{0,40}\]"
    r"|\((?:laughs?|laughter|inaudible|unintelligible|crosstalk|cross talk"
    r"|silence|pause|music|applause|coughs?|sighs?)[^)]{0,20}\)",
    re.IGNORECASE,
)

# curly quotes / dashes / ellipsis to plain equivalents the analyzers expect
_NORMALIZE = {
    "\u2019": "'", "\u2018": "'",
    "\u201c": '"', "\u201d": '"',
    "\u2026": "...",
    "\u00a0": " ",
}


@dataclass
class Transcript:
    source: str
    utterances: List[Tuple[Optional[str], str]]  # (speaker or None, text)
    kind: str = "plain"  # plain | labeled | vtt | srt
    speakers: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(u for _, u in self.utterances)

    @property
    def word_shares(self) -> List[Tuple[str, int]]:
        """Rough words spoken per speaker, most talkative first."""
        counts = {}
        for speaker, text in self.utterances:
            if speaker is None:
                continue
            counts[speaker] = counts.get(speaker, 0) + len(text.split())
        return sorted(counts.items(), key=lambda kv: -kv[1])

    def for_speaker(self, needle: str) -> "Transcript":
        """Keep only utterances whose speaker label contains ``needle``."""
        folded = needle.casefold()
        kept = [
            (s, t) for s, t in self.utterances
            if s is not None and folded in s.casefold()
        ]
        matched = sorted({s for s, _ in kept})
        return Transcript(
            source=self.source, utterances=kept, kind=self.kind, speakers=matched
        )


def _normalize(text: str) -> str:
    for src, dst in _NORMALIZE.items():
        text = text.replace(src, dst)
    return text


def _clean_line(line: str) -> str:
    line = _ANNOTATION_RE.sub(" ", line)
    line = _TAG_RE.sub(" ", line)
    # markdown chrome that shouldn't count as words or sentence breaks
    line = re.sub(r"^\s{0,6}(?:[#>*-]+|\d+\.)\s+", "", line)
    return re.sub(r"[ \t]{2,}", " ", line).strip()


def _is_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if s.startswith("<<<") or s.startswith("(...truncated"):
        return True  # tool markers, e.g. Wispr Flow guard lines
    if s in ("WEBVTT",) or s.startswith(("NOTE ", "NOTE\t", "STYLE", "REGION")):
        return True
    if _VTT_TIME_RE.search(s):
        return True  # cue timing line
    if re.fullmatch(r"\d{1,5}", s):
        return True  # SRT cue number
    return False


def parse_transcript(raw: str, source: str = "text") -> Transcript:
    """Parse raw transcript text into utterances, detecting the format."""
    raw = _normalize(raw)
    kind = "plain"
    if raw.lstrip().startswith("WEBVTT"):
        kind = "vtt"
    elif re.search(r"^\d{1,5}\s*\n\d\d:\d\d", raw, re.MULTILINE):
        kind = "srt"

    lines = []
    for line in raw.splitlines():
        if _is_noise(line):
            continue
        voice = _VTT_VOICE_RE.search(line)
        speaker_from_tag = voice.group(1).strip() if voice else None
        cleaned = _clean_line(line)
        if cleaned:
            lines.append((speaker_from_tag, cleaned))

    # Detect "Name: text" labeling across the cleaned lines.
    labeled = []
    has_voice_tags = False
    for tag_speaker, line in lines:
        if tag_speaker is not None:
            has_voice_tags = True
            labeled.append((tag_speaker, line))
            continue
        m = _LABEL_RE.match(line)
        # Reject label-ish lines that are prose ("Note: buy milk" stays plain
        # unless the file is consistently labeled - the ratio check below).
        labeled.append((m.group(1).strip(), m.group(2)) if m else (None, line))

    n_labeled = sum(1 for s, _ in labeled if s is not None)
    distinct = {s for s, _ in labeled if s is not None}
    # Explicit <v> tags are certain; the count/ratio check only guards
    # against prose that happens to look like a label ("Note: buy milk").
    is_labeled = has_voice_tags or (
        n_labeled >= 3
        and (len(distinct) >= 2 or n_labeled >= max(3, int(0.6 * len(labeled))))
    )

    if is_labeled:
        utterances = [(s, t) for s, t in labeled]
        speakers = []
        for s, _ in utterances:
            if s is not None and s not in speakers:
                speakers.append(s)
        return Transcript(
            source=source,
            utterances=utterances,
            kind="labeled" if kind == "plain" else kind,
            speakers=speakers,
        )

    return Transcript(
        source=source,
        utterances=[(None, t) for _, t in lines],
        kind=kind,
        speakers=[],
    )


def load_transcript(path: str) -> Transcript:
    """Read a transcript from a file path, or stdin when path is '-'."""
    if path == "-":
        import sys

        return parse_transcript(sys.stdin.read(), source="stdin")
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return parse_transcript(fh.read(), source=path)

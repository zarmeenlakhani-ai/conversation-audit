# conversation-audit

A tool that lives on your computer and tells you, every time there's a
transcript, how clear you actually were: how many fillers you used, where a
thought broke off mid-sentence, which sentences ran on, and whether you
stated your ask up front or buried it at the end.

It works on anything that is words you said or wrote: Wispr Flow dictations,
Granola / Zoom meeting transcripts, a prompt you're about to send to Claude,
`.vtt`/`.srt` caption files, or whatever is on your clipboard.

```
CONVERSATION AUDIT  standup_dictation.txt  (154 words, ~1.0 min spoken)
Overall clarity: 36/100 - Foggy

FLUENCY 17/100  11.0 fillers per 100 words (very high)
  um x3, basically x3, right? x2, like x2, you know? x1, uh x1 ...
COHERENCE 61/100  3.2 broken thoughts per 100 words (very high)
  false starts: 1, stutters: 1, phrase restarts: 2, self-corrections: 1
  "...right? So basically... what I was, what I was trying to say is..."
STRUCTURE 35/100
  buried lead: the ask first appears 85% of the way in - try stating it in sentence one

Biggest lever -> fluency: pause silently instead of filling - the silence reads as confidence
```

## Two ways to run it

**1. Fully automatic, zero install (recommended):** a Claude Routine checks
your connected meeting recorders (Wispr Flow, Granola) every half hour of
the workday, audits your lines from any meeting that just ended, and sends
3-5 sharp pointers to your phone and inbox. Nothing runs on your laptop;
the transcripts never leave the tools that already have them. The routine's
prompt lives in [`extras/routine-prompt.md`](extras/routine-prompt.md) -
anyone with the same connectors can ask Claude to recreate it. Manage or
pause it from your Routines list in Claude.

Coverage note: this covers whatever your recorder captures - Wispr Flow and
Granola both sit on top of Google Meet, Zoom, and the rest, so "any type of
transcriber" reduces to "any call your recorder was in." For transcripts
that arrive as files instead, use the watcher below.

**2. On your machine (for prompts, dictations, transcript files):**

## Install

```bash
git clone https://github.com/zarmeenlakhani-ai/conversation-audit.git
cd conversation-audit
pip install .            # core tool - zero dependencies
pip install '.[ai]'      # optional: enables --deep Claude coaching
```

No install needed to try it: `python3 -m conversation_audit samples/standup_dictation.txt`

## Use

```bash
conversation-audit notes.txt                   # audit a transcript
conversation-audit notes.txt --brief           # no essay: 3 pointers + a drill
pbpaste | conversation-audit -                 # audit whatever you just copied
conversation-audit meeting.txt --speaker "Zarmeen"   # only YOUR lines in a meeting
conversation-audit watch ~/Transcripts --brief # audit new files as they land
conversation-audit trends                      # are you improving?
conversation-audit notes.txt --deep            # + Claude coaching (see below)
```

`--brief` is the after-a-call view - one header, ranked pointers each ending
in a fix, one drill (`--pointers N` for up to 10):

```
hub71_meeting.txt [Zarmeen Lakhani] - Clarity 72/100 (Clear)
1. 11 broken thoughts (4 stutters, 7 phrase restarts) e.g. "...Yeah, yeah. I, I switched..." -> finish the sentence, then upgrade it.
2. 4.9 fillers per 100 words (uh x4, um x3 lead) -> swap the um for a silent beat.
Drill: finish each sentence before improving it - plan the thought, then say it.
```

Handy alias for checking a prompt before you send it:

```bash
alias checkme='pbpaste | conversation-audit -'
```

## The four lenses

Clarity is scored 0-100 on four lenses that are mutually exclusive and
collectively cover what "clear" means for spoken language:

| Lens | What it counts | Weight |
|---|---|---|
| **Fluency** | hesitations (um, uh), crutch words (basically, actually), phrase fillers (kind of, I mean), tag questions (right?, you know?), hedges (I feel like, maybe), filler "like" | 30% |
| **Concision** | run-on sentences (32+ words, or 3+ chained and/but/so), fragment ratio, longest sentence | 25% |
| **Coherence** | false starts (trailing "..." and cutoff dashes), stutters ("I, I switched"), phrase restarts ("I want to... I want to improve"), self-corrections | 25% |
| **Structure** | is the ask stated in the first 30% (BLUF) or after 65% (buried lead); signposting (first/second/bottom line) | 20% |

Bands: **85+ Crisp · 70+ Clear · 50+ Scattered · below 50 Foggy**. Under ~60
words the structure lens abstains and the weights renormalize.

Every audit is appended to `~/.conversation-audit/history.jsonl` (unless
`--no-store`; override the directory with `CONVERSATION_AUDIT_HOME`), which
is what `trends` reads:

```
clarity  ▂▁▃▄▄▆▇█  (up = better)
fillers  █▇▆▆▄▃▂▁  (down = better)
```

## The speaker scorecard

The clarity score answers "was that clear?". The scorecard answers the
questions a speaking coach asks — *am I messy, am I structured, do I speak in
points, how is my tone, how confident do I sound* — on eight dimensions, each
on the same five levels: **1 Distracting · 2 Developing · 3 Solid · 4 Strong
· 5 Brilliant**.

| Dimension | Question | Measured as |
|---|---|---|
| **Structure** | Am I structured? | framing, transition and closing lines per 1,000 words |
| **Points** | Do I speak in points? | enumerations ("two things", "number one", "first,") per 1,000 words |
| **Composure** | Am I messy? | restarts, false starts, stutters, self-corrections and "no, no" bursts per 100 words |
| **Concision** | Do I get to the point? | run-on sentences per 1,000 words |
| **Fluency** | Do fillers get in the way? | um/uh, filler "like", phrase fillers and crutch words per 100 words |
| **Confidence** | Do I sound sure? | hedges, tag questions, apologies, deferrals and pre-disclaimers, net of half-weighted commitments, per 100 words |
| **Tone** | How do I come across? | warm phrases minus confrontational ones per 1,000 words, plus a label ("Warm and steady", "Cool, sharp in disagreement") |
| **Impact** | Do my points land? | examples and dated asks or commitments, minus open-ended offers, per 1,000 words |

```bash
conversation-audit notes.txt --scorecard       # add the scorecard to any audit
conversation-audit scorecard mon.txt tue.txt --speaker "Zarmeen" --html week.html
```

The `--html` page answers the five questions in plain language first, then
shows the eight-dimension scoreboard, a room-by-room heatmap and the three
moves that would lift the lowest dimensions a level. Scoring is deterministic:
each rate maps onto the levels through the anchors in `ANCHORS` at the top of
`conversation_audit/scorecard.py`. Acknowledgment-only turns are set aside,
and rooms under 250 words are not scored. Voice, pace, pauses and body
language are out of reach of a transcript, so they are not scored.

## Getting transcripts in

- **Meetings (Wispr Flow, Granola, Zoom):** export or copy the transcript
  into a file inside a watched folder. Speaker labels (`Zarmeen Lakhani: ...`,
  `Me: ...`, `<v Name>` in VTT) are detected automatically - always pass
  `--speaker` so you're scored on your own voice, not your colleagues'.
- **Dictation / prompts:** copy the text, then `pbpaste | conversation-audit -`.
- **Claude connectors:** if you use the Wispr Flow or Granola connector in
  Claude, you can ask Claude to save a meeting transcript into your watched
  folder and it will be audited on arrival.

### Auto-run at login (macOS)

Save as `~/Library/LaunchAgents/com.conversation-audit.watch.plist`, then
`launchctl load` it. New transcripts dropped in the folder get audited and a
desktop notification shows the score.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.conversation-audit.watch</string>
  <key>ProgramArguments</key><array>
    <string>/usr/local/bin/conversation-audit</string>
    <string>watch</string>
    <string>/Users/YOU/Transcripts</string>
    <string>--speaker</string><string>Zarmeen</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
```

(Adjust the binary path to `which conversation-audit`.)

## Deep mode: Claude coaching

The offline metrics count what's countable. `--deep` sends the transcript to
Claude for the judgments heuristics can't make:

- **MECE check** - do your points overlap, and what's missing for the goal
- **the real point** - the one thing you were actually trying to say
- **BLUF rewrite** - your message restated in <= 4 sentences, ask first
- **recurring habits** - top 3 patterns, each with your exact quote and a fix
- **a drill** - one concrete thing to practice in the next conversation

Setup: `pip install '.[ai]'`, then either set `ANTHROPIC_API_KEY` or have an
`ant auth login` profile. Default model is `claude-opus-5` (override with
`--model` or `CONVERSATION_AUDIT_MODEL`). Server-side refusal fallbacks are
enabled, so a safety decline automatically retries on a fallback model
within the same request. Transcripts are sent to the Anthropic API only in
deep mode - the core tool is fully offline.

## Honesty about the numbers

The counts are exact for what the patterns match; the patterns are
approximations of speech habits. "Kind of" is sometimes a legitimate noun
phrase, "actually" is sometimes load-bearing, and meeting dialog naturally
has more fragments ("Yeah." "Okay, cool.") than solo dictation, which makes
concision read harsh on meetings. The structure lens is calibrated for
monologues (a dictation, an update, a prompt); on meeting chatter an early
"can you hear me?" can satisfy the ask-up-front check, so read structure on
meetings loosely - or use `--deep`, which judges it properly. Treat the score as a directional signal
and the quoted excerpts as the ground truth. `just` is counted but unscored.
Calibration constants live at the top of `conversation_audit/metrics.py` -
tune them to your bar.

## Development

```bash
python3 -m unittest discover -s tests   # 62 tests, no dependencies
```

Layout: `transcript.py` (format parsing, speaker filter) → `metrics.py`
(detectors + scoring) → `report.py` (terminal rendering) → `store.py`
(history/trends), with `scorecard.py` (the eight-dimension speaker scorecard)
and `scorepage.py` (its HTML page), `watch.py` (folder watcher +
notifications) and `coach.py` (optional Claude deep mode) on top, wired
together in `cli.py`.

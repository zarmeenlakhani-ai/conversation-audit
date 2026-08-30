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
pbpaste | conversation-audit -                 # audit whatever you just copied
conversation-audit meeting.txt --speaker "Zarmeen"   # only YOUR lines in a meeting
conversation-audit watch ~/Transcripts         # audit new files as they land
conversation-audit trends                      # are you improving?
conversation-audit notes.txt --deep            # + Claude coaching (see below)
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
python3 -m unittest discover -s tests   # 40 tests, no dependencies
```

Layout: `transcript.py` (format parsing, speaker filter) → `metrics.py`
(detectors + scoring) → `report.py` (terminal rendering) → `store.py`
(history/trends), with `watch.py` (folder watcher + notifications) and
`coach.py` (optional Claude deep mode) on top, wired together in `cli.py`.

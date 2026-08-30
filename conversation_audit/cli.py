"""Command-line interface.

    conversation-audit FILE [FILE...]      audit one or more transcripts
    conversation-audit -                   audit stdin (pbpaste | conversation-audit -)
    conversation-audit watch DIR           audit new transcripts as they land
    conversation-audit trends              your last audits, with sparklines
"""

import argparse
import json
import sys
from typing import List, Optional

from conversation_audit import __version__, metrics, report, store
from conversation_audit.transcript import load_transcript

COMMANDS = {"analyze", "watch", "trends"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conversation-audit",
        description="Audit transcripts for fillers, run-ons, broken thoughts,"
        " and structure.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="audit transcript file(s) or stdin")
    analyze.add_argument("paths", nargs="+", metavar="FILE",
                         help="transcript file(s), or - for stdin")
    analyze.add_argument("--speaker", metavar="NAME",
                         help="in speaker-labeled transcripts, audit only this"
                         " voice (substring match, e.g. 'zarmeen' or 'Me')")
    analyze.add_argument("--deep", action="store_true",
                         help="also get Claude coaching: MECE check, buried"
                         " lead, BLUF rewrite (needs Anthropic credentials)")
    analyze.add_argument("--model", help="model for --deep (default: %s)"
                         % "claude-opus-5")
    analyze.add_argument("--json", action="store_true", dest="as_json",
                         help="emit metrics as JSON instead of the report")
    analyze.add_argument("--no-store", action="store_true",
                         help="don't record this audit in history")
    analyze.add_argument("--no-color", action="store_true")

    watch = sub.add_parser("watch", help="watch a folder, audit new transcripts")
    watch.add_argument("directory")
    watch.add_argument("--interval", type=float, default=5.0,
                       help="poll interval in seconds (default 5)")
    watch.add_argument("--speaker", metavar="NAME")
    watch.add_argument("--deep", action="store_true")
    watch.add_argument("--model")
    watch.add_argument("--once", action="store_true",
                       help="audit everything already in the folder, then exit")

    trends = sub.add_parser("trends", help="show your recent audits")
    trends.add_argument("-n", type=int, default=12, metavar="N",
                        help="how many recent audits to show (default 12)")
    return parser


def _run_analyze(args: argparse.Namespace) -> int:
    color = False if args.as_json or args.no_color else None
    exit_code = 0
    results = []
    for i, path in enumerate(args.paths):
        try:
            transcript = load_transcript(path)
        except OSError as e:
            print(f"cannot read {path}: {e}", file=sys.stderr)
            exit_code = 2
            continue

        # A transcript with no labels at all is a solo dictation - it's all
        # the user's voice, so --speaker only filters labeled transcripts.
        speaker_note = None
        if args.speaker and transcript.speakers:
            filtered = transcript.for_speaker(args.speaker)
            if not filtered.utterances:
                labels = ", ".join(transcript.speakers) or "none detected"
                print(
                    f"no utterances match speaker '{args.speaker}' in {path}"
                    f" (speakers: {labels})",
                    file=sys.stderr,
                )
                exit_code = 2
                continue
            speaker_note = " + ".join(filtered.speakers)
            transcript = filtered
        try:
            analysis = metrics.analyze(
                transcript.text,
                source=transcript.source
                + (f" [{speaker_note}]" if speaker_note else ""),
            )
        except ValueError as e:
            print(f"{path}: {e}", file=sys.stderr)
            exit_code = 2
            continue

        if args.as_json:
            results.append(analysis.to_dict())
        else:
            if i > 0:
                print("\n" + "=" * 72 + "\n")
            print(report.render(analysis, color=color))
            if len(transcript.speakers) > 1 and not args.speaker:
                shares = ", ".join(
                    f"{name} ({words}w)" for name, words in transcript.word_shares
                )
                print(
                    f"\nnote: multiple speakers audited together: {shares}."
                    f" Use --speaker to audit one voice."
                )

        if not args.no_store:
            store.record(analysis)

        if args.deep:
            from conversation_audit import coach

            try:
                verdict = coach.deep_analysis(
                    transcript.text, analysis, args.model
                )
            except coach.CoachError as e:
                print(f"deep analysis failed: {e}", file=sys.stderr)
                exit_code = exit_code or 1
            else:
                if args.as_json:
                    results[-1]["coach"] = verdict
                else:
                    print(report.render_coach(verdict, color=color))

    if args.as_json and results:
        print(json.dumps(results[0] if len(results) == 1 else results,
                         indent=2, ensure_ascii=False))
    return exit_code


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # allow `conversation-audit notes.txt` without the explicit subcommand
    if argv and argv[0] not in COMMANDS and argv[0] not in ("-h", "--help",
                                                            "--version"):
        argv.insert(0, "analyze")
    args = _build_parser().parse_args(argv)

    if args.command == "analyze":
        return _run_analyze(args)
    if args.command == "watch":
        from conversation_audit.watch import watch

        return watch(args.directory, interval=args.interval,
                     speaker=args.speaker, deep=args.deep, model=args.model,
                     once=args.once)
    if args.command == "trends":
        rendered = store.render_trends(args.n)
        if rendered is None:
            print("no audits recorded yet - run one first:"
                  " conversation-audit <transcript.txt>")
            return 0
        print(rendered)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

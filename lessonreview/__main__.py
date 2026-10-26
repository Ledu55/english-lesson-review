"""Command line: python -m lessonreview <import|extract|review|build|all|status>"""
import argparse
import sys

from . import config

TERMS_WARNING = """Automated extraction is off by default.

Both platforms' terms forbid automated access:
- Cambly User Agreement, section 7: no robot, spider, scraper or other automated means to access the Platform.
- Preply Terms of Service: no viewing, copying or procuring content by automated means (scripts, bots, scrapers).
Using it can get your account suspended. The supported way is `import`: copy each lesson page yourself.

To use the automated extractor anyway, at your own risk, add --accept-terms-risk."""


def status(args, cfg):
    from . import review
    manifest = config.read_json(config.MANIFEST, {"lessons": []})["lessons"]
    raw = list(config.RAW.glob("*.md"))
    print(f"Period: {cfg['period']['from']} to {cfg['period']['to']}")
    print(f"Lessons in manifest: {len(manifest)} ({sum(l['status'] == 'done' for l in manifest)} saved)")
    print(f"Raw files: {len(raw)} · reviewed: {len(raw) - len(review.pending())} · waiting for review: {len(review.pending())}")
    print(f"Notebook: {'output/notebook.html' if (config.OUTPUT / 'notebook.html').exists() else 'not built yet'}")


def main():
    ap = argparse.ArgumentParser(prog="lessonreview", description="Cambly/Preply lessons -> error review -> practice notebook")
    sub = ap.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("import", help="import lesson pages you copied into inbox/*.txt (recommended)")
    i.add_argument("files", nargs="*", help=".txt files or folders (default inbox/)")
    i.add_argument("--platform", choices=["cambly", "preply"], help="if it can't be detected from the text")
    i.add_argument("--date", help="YYYY-MM-DD, if it can't be detected from the text")

    e = sub.add_parser("extract", help="automated extraction with Chrome (against the platforms' terms; opt-in)")
    e.add_argument("--platform", choices=["cambly", "preply"])
    e.add_argument("--limit", type=int, help="stop after N lessons")
    e.add_argument("--accept-terms-risk", action="store_true", help="confirm you accept the account risk")

    r = sub.add_parser("review", help="review lessons into analysis/")
    r.add_argument("--offline", action="store_true", help="no LLM: use the platforms' own corrections")
    r.add_argument("--limit", type=int)

    b = sub.add_parser("build", help="build output/notebook.html and output/voice_coach.md")
    b.add_argument("--data", help="errors.json to build from (default analysis/errors.json)")
    b.add_argument("--example", action="store_true", help="build from the bundled anonymized example")

    a = sub.add_parser("all", help="import from inbox/, review and build")
    a.add_argument("--offline", action="store_true")
    a.add_argument("--limit", type=int)

    sub.add_parser("status", help="show progress")
    args = ap.parse_args()
    cfg = config.load()

    if args.cmd == "import":
        from . import importer
        importer.run(args, cfg)
    elif args.cmd == "extract":
        if not args.accept_terms_risk:
            sys.exit(TERMS_WARNING)
        from . import extract
        extract.run(args, cfg)
    elif args.cmd == "review":
        from . import review
        review.main(args, cfg)
    elif args.cmd == "build":
        from . import build
        if args.example:
            args.data = str(config.REPO / "examples" / "errors.json")
        build.main(args, cfg)
    elif args.cmd == "all":
        from . import build, importer, review
        if any(importer.INBOX.glob("*.txt")):
            args.files, args.platform, args.date = [], None, None
            importer.run(args, cfg)
        review.main(args, cfg)
        args.data = None
        build.main(args, cfg)
    else:
        status(args, cfg)


if __name__ == "__main__":
    main()

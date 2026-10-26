"""Command line: python -m lessonreview <extract|review|build|all|status>"""
import argparse

from . import config


def status(args, cfg):
    from . import review
    manifest = config.read_json(config.MANIFEST, {"lessons": []})["lessons"]
    raw = list(config.RAW.glob("*.md"))
    print(f"Period: {cfg['period']['from']} to {cfg['period']['to']}")
    print(f"Lessons in manifest: {len(manifest)} ({sum(l['status'] == 'done' for l in manifest)} extracted)")
    print(f"Raw files: {len(raw)} · reviewed: {len(raw) - len(review.pending())} · waiting for review: {len(review.pending())}")
    print(f"Notebook: {'output/notebook.html' if (config.OUTPUT / 'notebook.html').exists() else 'not built yet'}")


def main():
    ap = argparse.ArgumentParser(prog="lessonreview", description="Cambly/Preply lessons -> error review -> practice notebook")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="copy lessons into raw/ (opens Chrome)")
    e.add_argument("--platform", choices=["cambly", "preply"])
    e.add_argument("--limit", type=int, help="stop after N lessons")

    r = sub.add_parser("review", help="review raw lessons into analysis/")
    r.add_argument("--offline", action="store_true", help="no LLM: use the platforms' own corrections")
    r.add_argument("--limit", type=int)

    b = sub.add_parser("build", help="build output/notebook.html and output/voice_coach.md")
    b.add_argument("--data", help="errors.json to build from (default analysis/errors.json)")
    b.add_argument("--example", action="store_true", help="build from the bundled anonymized example")

    a = sub.add_parser("all", help="extract, review and build")
    a.add_argument("--offline", action="store_true")
    a.add_argument("--platform", choices=["cambly", "preply"])
    a.add_argument("--limit", type=int)

    sub.add_parser("status", help="show progress")
    args = ap.parse_args()
    cfg = config.load()

    if args.cmd == "extract":
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
        from . import build, extract, review
        extract.run(args, cfg)
        review.main(args, cfg)
        args.data = None
        build.main(args, cfg)
    else:
        status(args, cfg)


if __name__ == "__main__":
    main()

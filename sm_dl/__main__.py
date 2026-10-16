from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .douyin import download_douyin
from .normalize import is_douyin_url, normalize_douyin_url


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m sm_dl",
        description="sm-dl Python entry (Douyin resilient strategies)",
    )
    p.add_argument("urls", nargs="+", help="URL or Douyin share paste text")
    p.add_argument("-o", "--output", default=str(Path.home() / "Downloads" / "sm-media"))
    p.add_argument("--cookies-from-browser", dest="cookies_from", default=None)
    p.add_argument("--skip-browser", action="store_true", help="skip Playwright CDN fallback")
    p.add_argument("--headed", action="store_true", help="show browser window")
    p.add_argument("--normalize-only", action="store_true", help="print canonical URL and exit")
    args = p.parse_args(argv)

    out = Path(args.output)
    rc = 0
    for raw in args.urls:
        if args.normalize_only:
            if not is_douyin_url(raw):
                print(f"not douyin: {raw}", file=sys.stderr)
                rc = 1
                continue
            print(normalize_douyin_url(raw))
            continue

        if not is_douyin_url(raw):
            print(f"skip non-douyin: {raw}", file=sys.stderr)
            rc = 1
            continue

        result = download_douyin(
            raw,
            out,
            cookies_from=args.cookies_from,
            skip_browser=args.skip_browser,
            headless=not args.headed,
        )
        if result.ok:
            print(result.path)
        else:
            print(result.detail, file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

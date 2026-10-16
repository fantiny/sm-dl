"""
Douyin download orchestrator.

Pipeline (elegant solidification of the manual recovery path):

  1. Normalize URL
       jingxuan?modal_id=… / share paste / v.douyin.com → /video/<id>
  2. lux
  3. yt-dlp  (--proxy "" + safari/chrome/firefox cookies)
  4. browser-cdn  (Playwright harvest CDN streams → ffmpeg merge)

Each step returns on success; failures are logged and the next strategy runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .normalize import is_douyin_url, normalize_douyin_url
from .strategies import BrowserCdnStrategy, LuxStrategy, YtDlpStrategy
from .strategies.base import DownloadResult, Strategy


def default_strategies(
    *,
    cookies_from: str | None = None,
    skip_browser: bool = False,
    headless: bool = True,
) -> list[Strategy]:
    strategies: list[Strategy] = [
        LuxStrategy(),
        YtDlpStrategy(cookies_from=cookies_from, disable_proxy=True),
    ]
    if not skip_browser:
        strategies.append(BrowserCdnStrategy(headless=headless))
    return strategies


def download_douyin(
    url_or_text: str,
    out_dir: Path | str,
    *,
    cookies_from: str | None = None,
    skip_browser: bool = False,
    headless: bool = True,
    resolve: bool = True,
    strategies: list[Strategy] | None = None,
) -> DownloadResult:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not is_douyin_url(url_or_text):
        return DownloadResult(False, "orchestrator", detail="not a douyin url/text")

    canonical = normalize_douyin_url(url_or_text, resolve=resolve)
    print(f"[douyin] normalize → {canonical}", file=sys.stderr)

    chain = strategies or default_strategies(
        cookies_from=cookies_from,
        skip_browser=skip_browser,
        headless=headless,
    )

    attempts: list[dict] = []
    for strategy in chain:
        print(f"[douyin] try {strategy.name}…", file=sys.stderr)
        result = strategy.try_download(canonical, out)
        attempts.append(
            {
                "strategy": result.strategy,
                "ok": result.ok,
                "detail": result.detail,
                "path": str(result.path) if result.path else None,
            }
        )
        if result.ok:
            print(
                f"[douyin] ok via {result.strategy}: {result.path}",
                file=sys.stderr,
            )
            # side-car attempt log for debugging
            log = out / f".sm-dl-douyin-{_id_hint(canonical)}.json"
            log.write_text(
                json.dumps(
                    {"url": canonical, "winner": result.strategy, "attempts": attempts},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return result
        print(f"[douyin] {strategy.name} failed: {result.detail}", file=sys.stderr)

    return DownloadResult(
        False,
        "orchestrator",
        detail="all strategies failed: "
        + " | ".join(f"{a['strategy']}: {a['detail']}" for a in attempts),
    )


def _id_hint(url: str) -> str:
    from .normalize import extract_aweme_id

    return extract_aweme_id(url) or "unknown"

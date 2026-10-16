from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from ..normalize import UA, extract_aweme_id
from .base import DownloadResult

VIDEO_RE = re.compile(r"douyinvod\.com.*media-video", re.I)
AUDIO_RE = re.compile(r"douyinvod\.com.*media-audio", re.I)

# Prefer a writable local browser cache when PLAYWRIGHT_BROWSERS_PATH points at a
# missing volume (e.g. unmounted external disk).
_DEFAULT_BROWSER_CACHE = Path.home() / ".cache" / "ms-playwright"


def _ensure_playwright_browsers_path() -> None:
    current = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if current and Path(current).exists():
        return
    _DEFAULT_BROWSER_CACHE.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_DEFAULT_BROWSER_CACHE)


class BrowserCdnStrategy:
    """
    Open the watch page in Chromium, harvest CDN media-video / media-audio
    URLs from performance entries, download, then ffmpeg-merge.

    This mirrors the manual recovery path when lux/yt-dlp get HTTP 403.
    """

    name = "browser-cdn"

    def __init__(self, *, wait_ms: int = 12_000, headless: bool = True) -> None:
        self.wait_ms = wait_ms
        self.headless = headless

    def try_download(self, url: str, out_dir: Path) -> DownloadResult:
        if not shutil.which("ffmpeg"):
            return DownloadResult(False, self.name, detail="ffmpeg not installed")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return DownloadResult(
                False,
                self.name,
                detail="playwright not installed (pip install playwright && playwright install chromium)",
            )

        out_dir.mkdir(parents=True, exist_ok=True)
        aweme_id = extract_aweme_id(url) or "douyin"

        try:
            video_url, audio_url, title = self._harvest(url)
        except Exception as exc:  # noqa: BLE001 — strategy must not raise
            return DownloadResult(False, self.name, detail=f"harvest failed: {exc}")

        if not video_url:
            return DownloadResult(False, self.name, detail="no media-video CDN url found")

        safe_title = _safe_name(title or f"douyin_{aweme_id}")
        final = out_dir / f"{safe_title}_{aweme_id}.mp4"

        with tempfile.TemporaryDirectory(prefix="sm-dl-dy-") as tmp:
            tmp_path = Path(tmp)
            v_path = tmp_path / "video.bin"
            a_path = tmp_path / "audio.bin"
            try:
                _http_download(video_url, v_path)
                if audio_url:
                    _http_download(audio_url, a_path)
                    _ffmpeg_merge(v_path, a_path, final)
                else:
                    # video-only stream — remux/copy
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", str(v_path), "-c", "copy", str(final)],
                        check=True,
                        capture_output=True,
                    )
            except Exception as exc:  # noqa: BLE001
                return DownloadResult(False, self.name, detail=f"fetch/merge failed: {exc}")

        info = out_dir / f"{safe_title}_{aweme_id}.info.txt"
        info.write_text(
            f"title: {title or ''}\n"
            f"id: {aweme_id}\n"
            f"source: {url}\n"
            f"strategy: {self.name}\n",
            encoding="utf-8",
        )
        return DownloadResult(
            True,
            self.name,
            path=final,
            detail="playwright + ffmpeg",
            artifacts=[info],
        )

    def _harvest(self, url: str) -> tuple[str | None, str | None, str | None]:
        from playwright.sync_api import sync_playwright

        _ensure_playwright_browsers_path()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=UA,
                locale="zh-CN",
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(self.wait_ms)
            # Nudge player if present
            try:
                page.locator("video").first.click(timeout=2000)
            except Exception:
                pass
            page.wait_for_timeout(2000)

            data = page.evaluate(
                """() => {
                  const urls = performance.getEntriesByType('resource').map(e => e.name);
                  const uniq = a => [...new Set(a)];
                  const video = uniq(urls.filter(u => /douyinvod\\.com.*media-video/i.test(u)));
                  const audio = uniq(urls.filter(u => /douyinvod\\.com.*media-audio/i.test(u)));
                  const mp4 = uniq(urls.filter(u => /douyinvod\\.com.*\\.mp4/i.test(u)));
                  return {
                    video,
                    audio,
                    mp4,
                    title: document.title || null,
                    hasVideo: !!document.querySelector('video'),
                  };
                }"""
            )
            browser.close()

        video = (data.get("video") or [None])[0] or (data.get("mp4") or [None])[0]
        audio = (data.get("audio") or [None])[0]
        title = data.get("title")
        if title and " - 抖音" in title:
            title = title.replace(" - 抖音", "").strip()
        return video, audio, title


def _http_download(url: str, dest: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://www.douyin.com/",
            "Origin": "https://www.douyin.com",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _ffmpeg_merge(video: Path, audio: Path, dest: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-c",
            "copy",
            str(dest),
        ],
        check=True,
        capture_output=True,
    )


def _safe_name(title: str, max_len: int = 60) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff#-]+", "_", title, flags=re.U).strip("_")
    return (cleaned or "douyin")[:max_len]

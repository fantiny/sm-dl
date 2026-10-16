from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .base import DownloadResult

# Chrome cookie decrypt often fails on macOS; Safari is tried first.
DEFAULT_BROWSERS = ("safari", "chrome", "firefox")


class YtDlpStrategy:
    """yt-dlp with local proxy disabled + multi-browser cookie fallback."""

    name = "yt-dlp"

    def __init__(
        self,
        *,
        browsers: tuple[str, ...] = DEFAULT_BROWSERS,
        disable_proxy: bool = True,
        cookies_from: str | None = None,
        timeout_sec: float = 90.0,
    ) -> None:
        self.browsers = (cookies_from,) if cookies_from else browsers
        self.disable_proxy = disable_proxy
        self.timeout_sec = timeout_sec

    def try_download(self, url: str, out_dir: Path) -> DownloadResult:
        if not shutil.which("yt-dlp"):
            return DownloadResult(False, self.name, detail="yt-dlp not installed")

        out_dir.mkdir(parents=True, exist_ok=True)
        template = str(out_dir / "%(title).80B [%(id)s].%(ext)s")
        errors: list[str] = []

        attempts: list[list[str]] = []
        # 1) no cookies
        attempts.append(self._base_args(template) + [url])
        # 2) each browser cookies
        for browser in self.browsers:
            if not browser:
                continue
            attempts.append(
                self._base_args(template)
                + ["--cookies-from-browser", browser, url]
            )

        for args in attempts:
            try:
                proc = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                )
            except subprocess.TimeoutExpired:
                errors.append(f"timeout after {self.timeout_sec:.0f}s ({_label(args)})")
                continue
            if proc.returncode == 0:
                path = self._newest_media(out_dir)
                return DownloadResult(
                    True,
                    self.name,
                    path=path,
                    detail=" ".join(args[1:6]),
                )
            err = (proc.stderr or proc.stdout or "").strip().splitlines()
            errors.append(err[-1] if err else f"exit {proc.returncode}")

        return DownloadResult(
            False,
            self.name,
            detail="; ".join(errors[-3:]),
        )

    def _base_args(self, template: str) -> list[str]:
        args = [
            "yt-dlp",
            "-o",
            template,
            "--no-mtime",
            "--embed-metadata",
            "--write-info-json",
            "--restrict-filenames",
            "--no-progress",
        ]
        if self.disable_proxy:
            # Empty proxy overrides env HTTP(S)_PROXY for this site.
            args.extend(["--proxy", ""])
        return args

    @staticmethod
    def _newest_media(out_dir: Path) -> Path | None:
        files = [
            p
            for p in out_dir.iterdir()
            if p.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}
        ]
        if not files:
            return None
        return max(files, key=lambda p: p.stat().st_mtime)


def _label(args: list[str]) -> str:
    if "--cookies-from-browser" in args:
        i = args.index("--cookies-from-browser")
        return f"cookies={args[i + 1]}" if i + 1 < len(args) else "cookies"
    return "no-cookies"

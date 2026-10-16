from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .base import DownloadResult


class LuxStrategy:
    name = "lux"

    def try_download(self, url: str, out_dir: Path) -> DownloadResult:
        if not shutil.which("lux"):
            return DownloadResult(False, self.name, detail="lux not installed")

        out_dir.mkdir(parents=True, exist_ok=True)
        before = {p.resolve() for p in out_dir.rglob("*") if p.is_file()}
        try:
            proc = subprocess.run(
                ["lux", "-o", str(out_dir), url],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return DownloadResult(False, self.name, detail="timeout after 60s")
        after = [p for p in out_dir.rglob("*") if p.is_file() and p.resolve() not in before]
        media = [
            p
            for p in after
            if p.suffix.lower() in {".mp4", ".webm", ".mkv", ".flv", ".mov"}
        ]
        if proc.returncode == 0 and media:
            return DownloadResult(True, self.name, path=media[0], detail="ok")

        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        return DownloadResult(
            False,
            self.name,
            detail=err[-1] if err else f"exit {proc.returncode}",
        )

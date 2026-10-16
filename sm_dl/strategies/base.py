from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class DownloadResult:
    ok: bool
    strategy: str
    path: Path | None = None
    detail: str = ""
    artifacts: list[Path] = field(default_factory=list)


class Strategy(Protocol):
    name: str

    def try_download(self, url: str, out_dir: Path) -> DownloadResult:
        """Attempt download; never raise for expected site failures — return ok=False."""
        ...

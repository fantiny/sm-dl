from __future__ import annotations

import unittest
from unittest.mock import patch

from sm_dl.normalize import (
    canonical_video_url,
    extract_aweme_id,
    extract_url_from_text,
    is_douyin_url,
    normalize_douyin_url,
)


class NormalizeTests(unittest.TestCase):
    def test_jingxuan_modal_id(self) -> None:
        url = "https://www.douyin.com/jingxuan?modal_id=7691219647454039296"
        self.assertEqual(extract_aweme_id(url), "7691219647454039296")
        self.assertEqual(
            normalize_douyin_url(url, resolve=False),
            "https://www.douyin.com/video/7691219647454039296",
        )

    def test_standard_video_url(self) -> None:
        url = "https://www.douyin.com/video/7691219647454039296?previous_page=web"
        self.assertEqual(
            normalize_douyin_url(url, resolve=False),
            "https://www.douyin.com/video/7691219647454039296",
        )

    def test_share_paste_text(self) -> None:
        text = (
            "1.00 :6pm sEU:/ 12/26 M@j.cn 《毛选》：懂很多却做不成事，问题在哪？ "
            "# 毛选 # 教员  https://v.douyin.com/ep9i1TxGtWg/ "
            "复制此链接，打开Dou音搜索，直接观看视频！"
        )
        self.assertTrue(is_douyin_url(text))
        self.assertEqual(
            extract_url_from_text(text),
            "https://v.douyin.com/ep9i1TxGtWg/",
        )

    def test_short_link_resolve(self) -> None:
        short = "https://v.douyin.com/ep9i1TxGtWg/"
        with patch(
            "sm_dl.normalize.resolve_redirects",
            return_value="https://www.douyin.com/video/7691219647454039296?previous_page=web",
        ):
            self.assertEqual(
                normalize_douyin_url(short, resolve=True),
                "https://www.douyin.com/video/7691219647454039296",
            )

    def test_iesdouyin_share(self) -> None:
        url = "https://www.iesdouyin.com/share/video/7691219647454039296/"
        self.assertEqual(
            normalize_douyin_url(url, resolve=False),
            canonical_video_url("7691219647454039296"),
        )


class StrategyOrderTests(unittest.TestCase):
    def test_default_chain_order(self) -> None:
        from sm_dl.douyin import default_strategies

        names = [s.name for s in default_strategies()]
        self.assertEqual(names, ["lux", "yt-dlp", "browser-cdn"])

    def test_skip_browser(self) -> None:
        from sm_dl.douyin import default_strategies

        names = [s.name for s in default_strategies(skip_browser=True)]
        self.assertEqual(names, ["lux", "yt-dlp"])

    def test_orchestrator_uses_first_success(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from sm_dl.douyin import download_douyin
        from sm_dl.strategies.base import DownloadResult

        class FakeOk:
            name = "fake-ok"

            def try_download(self, url: str, out_dir: Path) -> DownloadResult:
                p = out_dir / "ok.mp4"
                p.write_bytes(b"x")
                return DownloadResult(True, self.name, path=p)

        class FakeFail:
            name = "fake-fail"

            def try_download(self, url: str, out_dir: Path) -> DownloadResult:
                return DownloadResult(False, self.name, detail="nope")

        with TemporaryDirectory() as td:
            result = download_douyin(
                "https://www.douyin.com/jingxuan?modal_id=7691219647454039296",
                td,
                resolve=False,
                strategies=[FakeFail(), FakeOk()],
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.strategy, "fake-ok")


if __name__ == "__main__":
    unittest.main()

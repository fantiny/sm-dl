"""Normalize social / Douyin URLs before hitting download backends."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse, urlunparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

DOUYIN_HOSTS = (
    "douyin.com",
    "iesdouyin.com",
    "v.douyin.com",
)

# Share-paste blobs often bury the short link in Chinese copy.
URL_IN_TEXT = re.compile(
    r"https?://(?:v\.)?douyin\.com/[^\s\"'<>，。！？]+"
    r"|https?://www\.iesdouyin\.com/[^\s\"'<>，。！？]+"
    r"|https?://www\.douyin\.com/[^\s\"'<>，。！？]+",
    re.I,
)

AWEME_ID = re.compile(r"(?<!\d)(\d{15,21})(?!\d)")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def is_douyin_url(text: str) -> bool:
    t = text.strip().lower()
    if any(h in t for h in DOUYIN_HOSTS):
        return True
    return bool(URL_IN_TEXT.search(text))


def extract_url_from_text(text: str) -> str:
    """Pull the first Douyin URL out of a share-paste blob."""
    m = URL_IN_TEXT.search(text.strip())
    if m:
        return m.group(0).rstrip(").,，。；;")
    return text.strip()


def extract_aweme_id(url_or_text: str) -> str | None:
    """Best-effort aweme / modal id from URL path, query, or raw text."""
    raw = extract_url_from_text(url_or_text)
    parsed = urlparse(raw)
    qs = parse_qs(parsed.query)

    for key in ("modal_id", "aweme_id", "item_ids"):
        if key in qs and qs[key]:
            return qs[key][0]

    # /video/<id> or /share/video/<id>
    path_m = re.search(r"/(?:share/)?video/(\d{15,21})", parsed.path)
    if path_m:
        return path_m.group(1)

    # short path like /ep9i1TxGtWg/ — no id yet
    if re.fullmatch(r"/[A-Za-z0-9_-]+/?", parsed.path or ""):
        return None

    m = AWEME_ID.search(raw)
    return m.group(1) if m else None


def canonical_video_url(aweme_id: str) -> str:
    return f"https://www.douyin.com/video/{aweme_id}"


class _CaptureRedirects(HTTPRedirectHandler):
    def __init__(self) -> None:
        self.chain: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        self.chain.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def resolve_redirects(url: str, timeout: float = 15.0) -> str:
    """Follow redirects; return final URL (even on 4xx after redirect)."""
    cap = _CaptureRedirects()
    opener = build_opener(cap)
    req = Request(url, headers={"User-Agent": UA})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.geturl()
    except Exception:
        if cap.chain:
            return cap.chain[-1]
        return url


def normalize_douyin_url(url_or_text: str, *, resolve: bool = True) -> str:
    """
    Strategy step 1 — make a standard watch URL.

    Handles:
      - share paste text containing https://v.douyin.com/...
      - jingxuan?modal_id=... → /video/<id>
      - iesdouyin share links → /video/<id>
      - short links (optional HTTP resolve) → /video/<id>
    """
    url = extract_url_from_text(url_or_text)
    aweme_id = extract_aweme_id(url)

    if not aweme_id and resolve:
        host = (urlparse(url).hostname or "").lower()
        if host.endswith("douyin.com") or host.endswith("iesdouyin.com"):
            final = resolve_redirects(url)
            aweme_id = extract_aweme_id(final) or aweme_id
            if aweme_id:
                return canonical_video_url(aweme_id)
            return final.split("?")[0]

    if aweme_id:
        return canonical_video_url(aweme_id)

    # Already a clean path — strip tracking junk
    parsed = urlparse(url)
    return urlunparse((parsed.scheme or "https", parsed.netloc, parsed.path, "", "", ""))

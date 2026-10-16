# sm-dl

Multi-platform social media downloader wrapper for local research (video / image).

## Douyin strategy cascade

When the URL is Douyin (`douyin.com` / `v.douyin.com` / `iesdouyin.com`), `sm-dl` runs a fixed recovery pipeline — the same steps that work when `lux` / `yt-dlp` alone hit 403:

1. **Normalize URL** — share paste / `jingxuan?modal_id=` / short link → `https://www.douyin.com/video/<id>`
2. **lux**
3. **yt-dlp** — `--proxy ""` (ignore local HTTP proxy) + cookies from Safari → Chrome → Firefox
4. **browser-cdn** — Playwright opens the page, harvests `douyinvod.com` `media-video` + `media-audio` CDN URLs, downloads, `ffmpeg -c copy` merge

| Platform | Tool |
|----------|------|
| Douyin | strategy cascade above |
| Xiaohongshu / Xigua | [lux](https://github.com/iawia002/lux) (fallback [yt-dlp](https://github.com/yt-dlp/yt-dlp)) |
| Bilibili / YouTube / TikTok / X / Instagram / Facebook / Reddit / Weibo | yt-dlp |
| Image galleries (Pixiv, etc.) | [gallery-dl](https://github.com/mikf/gallery-dl) |

## Dependencies

```bash
# macOS (Homebrew)
brew install yt-dlp ffmpeg
pipx install gallery-dl
pipx inject gallery-dl yt-dlp
go install github.com/iawia002/lux@latest
# ensure lux is on PATH, e.g. ln -s "$(go env GOPATH)/bin/lux" ~/.local/bin/lux

# Douyin browser-cdn fallback (optional but recommended)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```

## Install

```bash
chmod +x sm-dl
ln -sf "$(pwd)/sm-dl" ~/.local/bin/sm-dl
```

## Usage

```bash
sm-dl "https://www.douyin.com/jingxuan?modal_id=..."
sm-dl "https://v.douyin.com/xxxx/"
sm-dl -o ~/Downloads/sm-media/batch "https://..."
sm-dl --cookies-from-browser safari "https://..."
sm-dl --skip-browser "https://..."   # lux + yt-dlp only
sm-dl --images "https://..."
sm-dl --tool lux "https://www.xiaohongshu.com/..."

# Python entry directly
.venv/bin/python -m sm_dl --normalize-only "https://www.douyin.com/jingxuan?modal_id=7691219647454039296"
.venv/bin/python -m sm_dl -o ~/Downloads/sm-media/douyin "https://v.douyin.com/ep9i1TxGtWg/"
```

Default output: `~/Downloads/sm-media` (override with `-o` or `SM_DL_OUT`).

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Notes

- Use only for content you have the right to download and research.
- Login-walled sites often need browser cookies; macOS Chrome cookie decrypt may fail — Safari is tried first.
- Respect platform Terms of Service and copyright.

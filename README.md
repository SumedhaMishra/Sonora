# Song Extractor

A web app that searches for songs on YouTube and plays them as MP3 in your browser.

## Prerequisites

- **Python 3.10+**
- **ffmpeg** — required for audio conversion to MP3
  - Windows: `winget install ffmpeg` or download from https://ffmpeg.org/download.html
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

## Setup

```bash
cd youtube_extract
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open http://localhost:5000 in your browser.

## How It Works

1. Type an artist name or song title in the search bar.
2. The app searches YouTube via `yt-dlp` and shows the top 10 results.
3. Click **Play** on any result — the audio is extracted, converted to MP3, and streamed to the built-in player.

Downloaded MP3 files are stored temporarily in the `downloads/` folder and auto-cleaned after 1 hour.

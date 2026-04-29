# Sonora

A kawaii music streaming app that searches for songs on YouTube and plays them directly in your browser.

## Prerequisites

- **Python 3.10+**

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

1. Type an artist name or song title in the search bar, or click a mood/artist on the landing page.
2. The app searches YouTube via `yt-dlp` and ranks results by official sources.
3. Click **Play** on any result — the audio stream URL is extracted and played directly in the browser. No downloading, no conversion.

## Features

- Stream songs instantly (no ffmpeg needed)
- Artist profiles with songs grouped by album
- Custom playlists saved in localStorage
- Mood-based collections (Romance, Gym, Chill, etc.)
- Kawaii pixel-art themed UI
- No cookies, no tracking

import os
import re
import uuid
import glob
import threading
import time
from flask import Flask, request, jsonify, send_from_directory, send_file

app = Flask(__name__, static_folder="static")

# Disable cookies entirely — no sessions, no tracking
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True

@app.after_request
def remove_cookies(response):
    # Strip any Set-Cookie headers Flask might add
    response.headers.pop('Set-Cookie', None)
    return response

# Auto-detect ffmpeg location (winget installs it outside PATH)
FFMPEG_DIR = None
_winget_ffmpeg = glob.glob(os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe"
))
if _winget_ffmpeg:
    FFMPEG_DIR = os.path.dirname(_winget_ffmpeg[0])

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Background cleanup: delete files older than 1 hour every 10 minutes
def cleanup_old_files():
    while True:
        time.sleep(600)
        now = time.time()
        for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*.mp3")):
            if now - os.path.getmtime(f) > 3600:
                try:
                    os.remove(f)
                except OSError:
                    pass

cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()


def sanitize_filename(name: str) -> str:
    """Remove unsafe characters from filenames."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)[:200]


@app.route("/")
def index():
    return send_file("static/index.html")


def _official_score(entry: dict, query: str) -> int:
    """Score how 'official' a result looks. Higher = more official."""
    score = 0
    channel = (entry.get("channel") or entry.get("uploader") or "").lower()
    title = (entry.get("title") or "").lower()
    q_words = [w for w in query.lower().split() if len(w) >= 3]

    # Channel signals
    if "vevo" in channel:
        score += 50
    if "- topic" in channel:  # YouTube auto-generated "Artist - Topic" channels
        score += 40
    if "official" in channel:
        score += 30
    for w in q_words:
        if w in channel:
            score += 20

    # Title signals
    if "official" in title:
        score += 15
    if "official audio" in title or "official video" in title or "official music video" in title:
        score += 10
    if "lyric" in title:
        score += 5

    # Penalty for compilations, covers, reactions
    for bad in ["cover", "reaction", "remix", "parody", "karaoke", "tutorial", "compilation", "mix"]:
        if bad in title:
            score -= 20

    return score


@app.route("/api/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    if not query or len(query) > 200:
        return jsonify({"error": "Please provide a valid search query."}), 400

    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": ["ios", "web"]}},
    }

    search_query = f"ytsearch20:{query} official"

    all_entries = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get("entries", [])
            for entry in entries:
                if not entry:
                    continue
                channel = entry.get("channel") or entry.get("uploader", "")
                all_entries.append({
                    "id": entry.get("id", ""),
                    "title": entry.get("title", "Unknown"),
                    "url": entry.get("url", ""),
                    "duration": entry.get("duration"),
                    "channel": channel or "Unknown",
                    "thumbnail": entry.get("thumbnail") or entry.get("thumbnails", [{}])[0].get("url", ""),
                    "_score": _official_score(entry, query),
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Sort by official score descending, take top 10
    all_entries.sort(key=lambda x: x["_score"], reverse=True)
    results = [{k: v for k, v in e.items() if k != "_score"} for e in all_entries[:10]]

    return jsonify({"results": results})


@app.route("/api/artist", methods=["GET"])
def artist():
    """Fetch an artist profile: top songs grouped by album."""
    name = request.args.get("name", "").strip()
    if not name or len(name) > 200:
        return jsonify({"error": "Please provide an artist name."}), 400

    import yt_dlp
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Step 1: flat search for more results
    flat_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": ["ios", "web"]}},
    }

    search_query = f"ytsearch30:{name} official audio"
    candidates = []

    try:
        with yt_dlp.YoutubeDL(flat_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            for entry in info.get("entries", []):
                if not entry:
                    continue
                candidates.append({
                    "id": entry.get("id", ""),
                    "title": entry.get("title", "Unknown"),
                    "duration": entry.get("duration"),
                    "channel": entry.get("channel") or entry.get("uploader", "Unknown"),
                    "thumbnail": entry.get("thumbnail") or "",
                    "_score": _official_score(entry, name),
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    candidates.sort(key=lambda x: x["_score"], reverse=True)
    top = candidates[:15]

    # Step 2: fetch album metadata in parallel
    detail_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": ["ios", "web"]}},
    }

    def fetch_album(entry):
        try:
            with yt_dlp.YoutubeDL(detail_opts) as ydl:
                detail = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={entry['id']}",
                    download=False,
                )
                return {**entry, "album": detail.get("album") or ""}
        except Exception:
            return {**entry, "album": ""}

    enriched = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch_album, e): e for e in top}
        for future in as_completed(futures):
            result = future.result()
            enriched.append({k: v for k, v in result.items() if k != "_score"})

    # Step 3: group by album
    albums = {}
    no_album = []
    for song in enriched:
        if song["album"]:
            albums.setdefault(song["album"], []).append(song)
        else:
            no_album.append(song)

    groups = []
    for album_name in sorted(albums, key=lambda a: len(albums[a]), reverse=True):
        groups.append({"album": album_name, "songs": albums[album_name]})
    if no_album:
        groups.append({"album": "", "songs": no_album})

    return jsonify({"artist": name, "groups": groups})


@app.route("/api/stream", methods=["POST"])
def stream():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request."}), 400

    video_id = data.get("id", "").strip()
    title = data.get("title", "audio").strip()

    # Validate video_id format (YouTube IDs are 11 chars, alphanumeric + - + _)
    if not video_id or not re.match(r'^[a-zA-Z0-9_-]{8,15}$', video_id):
        return jsonify({"error": "Invalid video ID."}), 400

    import yt_dlp

    # Try multiple client strategies to bypass YouTube bot detection on servers
    clients_to_try = [
        ["android_creator", "web"],
        ["ios", "web"],
        ["mweb"],
        ["web_creator"],
    ]

    stream_url = None
    last_error = ""

    for clients in clients_to_try:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extractor_args": {"youtube": {"player_client": clients}},
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
            },
            "geo_bypass": True,
        }

        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = info.get("url")
                if stream_url:
                    break
        except Exception as e:
            last_error = str(e)
            continue

    if not stream_url:
        return jsonify({"error": f"Stream failed: {last_error}"}), 500

    return jsonify({"stream_url": stream_url, "title": title})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

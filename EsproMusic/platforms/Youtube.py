import asyncio
import os
import re
from typing import Union
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython import VideosSearch, Playlist
import aiohttp

API_URL = os.environ.get("SHRUTI_API_URL", "https://api01.shrutibots.site")

API_KEY = os.environ.get("SHRUTI_API_KEY", "ShrutiBots7EhoL3cMjnYD3VEhQDIA") ## Get This API KEY FROM TELEGRAM BOT USERNAME: @SHRUTIAPIBOT 

DOWNLOAD_DIR = "downloads"


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))


def _extract_video_id(link: str) -> str:
    """Extract an 11-character YouTube video ID from a URL or ID."""
    from urllib.parse import urlparse, parse_qs

    value = str(link or "").strip()
    if not value:
        return ""

    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        if host in {"youtu.be", "www.youtu.be"}:
            value = parsed.path.strip("/").split("/")[0]
        elif host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
            if parsed.path == "/watch":
                value = parse_qs(parsed.query).get("v", [""])[0]
            elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
                parts = parsed.path.strip("/").split("/")
                value = parts[1] if len(parts) > 1 else ""
            else:
                value = ""
    except Exception:
        return ""

    return value if re.fullmatch(r"[A-Za-z0-9_-]{11}", value) else ""


async def _download_media(link: str, media_type: str, timeout: int):
    video_id = _extract_video_id(link)
    if not video_id:
        print(f"[YouTube API] Invalid YouTube link or video ID: {link!r}")
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    extension = "mp3" if media_type == "audio" else "mp4"
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{extension}")
    temp_path = file_path + ".part"

    if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL.rstrip('/')}/download",
                params={
                    "url": video_id,
                    "type": media_type,
                    "api_key": API_KEY,
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    body = (await resp.text())[:500]
                    print(f"[YouTube API] HTTP {resp.status}: {body}")
                    return None

                content_type = resp.headers.get("Content-Type", "").lower()
                if "json" in content_type or "text/html" in content_type:
                    body = (await resp.text())[:500]
                    print(f"[YouTube API] Unexpected response ({content_type}): {body}")
                    return None

                total = 0
                with open(temp_path, "wb") as output:
                    async for chunk in resp.content.iter_chunked(131072):
                        if chunk:
                            output.write(chunk)
                            total += len(chunk)

        if total <= 0:
            print("[YouTube API] Download returned an empty file.")
            return None

        os.replace(temp_path, file_path)
        return file_path

    except asyncio.TimeoutError:
        print(f"[YouTube API] {media_type} download timed out after {timeout}s.")
        return None
    except Exception as exc:
        print(f"[YouTube API] {media_type} download failed: {type(exc).__name__}: {exc}")
        return None
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


async def download_song(link: str) -> str:
    return await _download_media(link, "audio", 300)


async def download_video(link: str) -> str:
    return await _download_media(link, "video", 600)


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        return bool(re.search(self.regex, str(link or "")))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            text_value = message.text or message.caption or ""
            entities = list(message.entities or []) + list(message.caption_entities or [])
            for entity in entities:
                if entity.type == MessageEntityType.TEXT_LINK and getattr(entity, "url", None):
                    return entity.url
                if entity.type == MessageEntityType.URL:
                    start = entity.offset
                    end = start + entity.length
                    return text_value[start:end]
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        link = str(link).split("&")[0]
        try:
            response = await VideosSearch(link, limit=1).next()
            results = response.get("result") or []
            if not results:
                return None, None, 0, None, None
            result = results[0]
            duration_min = result.get("duration")
            duration_sec = time_to_seconds(duration_min) if duration_min else 0
            thumbnails = result.get("thumbnails") or []
            thumbnail = thumbnails[0].get("url", "").split("?")[0] if thumbnails else None
            return (
                result.get("title"),
                duration_min,
                int(duration_sec),
                thumbnail,
                result.get("id"),
            )
        except Exception as exc:
            print(f"[YouTube Search] details failed: {type(exc).__name__}: {exc}")
            return None, None, 0, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        link = str(link).split("&")[0]
        try:
            results = (await VideosSearch(link, limit=1).next()).get("result") or []
            return results[0].get("title") if results else None
        except Exception as exc:
            print(f"[YouTube Search] title failed: {type(exc).__name__}: {exc}")
            return None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        link = str(link).split("&")[0]
        try:
            results = (await VideosSearch(link, limit=1).next()).get("result") or []
            return results[0].get("duration") if results else None
        except Exception as exc:
            print(f"[YouTube Search] duration failed: {type(exc).__name__}: {exc}")
            return None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        link = str(link).split("&")[0]
        try:
            results = (await VideosSearch(link, limit=1).next()).get("result") or []
            if not results:
                return None
            thumbnails = results[0].get("thumbnails") or []
            return thumbnails[0].get("url", "").split("?")[0] if thumbnails else None
        except Exception as exc:
            print(f"[YouTube Search] thumbnail failed: {type(exc).__name__}: {exc}")
            return None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            plist = await Playlist.get(link)
        except Exception:
            return []
        videos = plist.get("videos") or []
        ids = []
        for data in videos[:limit]:
            if not data:
                continue
            vid = data.get("id")
            if not vid:
                continue
            ids.append(vid)
        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        link = str(link).split("&")[0]
        try:
            results = (await VideosSearch(link, limit=1).next()).get("result") or []
            if not results:
                return None, None
            result = results[0]
            thumbnails = result.get("thumbnails") or []
            track_details = {
                "title": result.get("title"),
                "link": result.get("link") or (self.base + result.get("id", "")),
                "vidid": result.get("id"),
                "duration_min": result.get("duration"),
                "thumb": thumbnails[0].get("url", "").split("?")[0] if thumbnails else None,
            }
            return track_details, result.get("id")
        except Exception as exc:
            print(f"[YouTube Search] track failed: {type(exc).__name__}: {exc}")
            return None, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        link = str(link).split("&")[0]
        ytdl_opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
        try:
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
            formats_available = []
            for item in (info or {}).get("formats", []):
                try:
                    if "dash" not in str(item.get("format", "")).lower():
                        formats_available.append({
                            "format": item.get("format"),
                            "filesize": item.get("filesize"),
                            "format_id": item.get("format_id"),
                            "ext": item.get("ext"),
                            "format_note": item.get("format_note"),
                            "yturl": link,
                        })
                except Exception:
                    continue
            return formats_available, link
        except Exception as exc:
            print(f"[YouTube API] formats failed: {type(exc).__name__}: {exc}")
            return [], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + str(link)
        link = str(link).split("&")[0]
        try:
            response = await VideosSearch(link, limit=10).next()
            results = response.get("result") or []
            if not isinstance(query_type, int) or query_type < 0 or query_type >= len(results):
                return None, None, None, None
            result = results[query_type]
            thumbnails = result.get("thumbnails") or []
            thumbnail = thumbnails[0].get("url", "").split("?")[0] if thumbnails else None
            return result.get("title"), result.get("duration"), thumbnail, result.get("id")
        except Exception as exc:
            print(f"[YouTube Search] slider failed: {type(exc).__name__}: {exc}")
            return None, None, None, None

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + str(link)
        try:
            downloaded_file = (
                await download_video(link) if video else await download_song(link)
            )
            if downloaded_file and os.path.isfile(downloaded_file):
                return downloaded_file, True
            return None, False
        except Exception as exc:
            print(f"[YouTube API] download method failed: {type(exc).__name__}: {exc}")
            return None, False


YouTube = YouTubeAPI()
                                  

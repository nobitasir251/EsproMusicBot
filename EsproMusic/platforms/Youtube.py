
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
                                  

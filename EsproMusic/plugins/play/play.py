
import random
import string

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InputMediaPhoto, Message
from pytgcalls.exceptions import NoActiveGroupCall

import config
from EsproMusic import Apple, Resso, SoundCloud, Spotify, Telegram, YouTube, app
from EsproMusic.core.call import Ritik
from EsproMusic.utils import seconds_to_min, time_to_seconds
from EsproMusic.utils.channelplay import get_channeplayCB
from EsproMusic.utils.decorators.language import languageCB
from EsproMusic.utils.decorators.play import PlayWrapper
from EsproMusic.utils.formatters import formats
from EsproMusic.utils.inline import (
    botplaylist_markup,
    livestream_markup,
    playlist_markup,
    slider_markup,
    track_markup,
)
from EsproMusic.utils.logger import play_logs
from EsproMusic.utils.stream.stream import stream
from config import BANNED_USERS, lyrical


# ---------------------------------------------------------
# SAFE YOUTUBE HELPERS
# ---------------------------------------------------------

async def safe_youtube_track(link, videoid=None):
    """Return valid YouTube details, or (None, None) on failure."""
    try:
        result = await YouTube.track(link, videoid)

        if not isinstance(result, (tuple, list)) or len(result) < 2:
            return None, None

        details, track_id = result[0], result[1]

        if not isinstance(details, dict) or not track_id:
            return None, None

        if not details.get("title"):
            return None, None

        details.setdefault("thumb", "")
        details.setdefault("duration_min", "")
        return details, track_id

    except Exception as e:
        print(f"YouTube track error: {type(e).__name__}: {e}")
        return None, None


def safe_duration_seconds(duration):
    """Convert a duration to seconds without crashing."""
    if not duration:
        return None

    try:
        return time_to_seconds(duration)
    except (TypeError, ValueError, IndexError):
        return None


def safe_thumbnail(details):
    if isinstance(details, dict):
        return details.get("thumb") or config.PLAYLIST_IMG_URL
    return config.PLAYLIST_IMG_URL


def safe_title(details):
    if isinstance(details, dict):
        return details.get("title") or "Unknown Title"
    return "Unknown Title"


def safe_duration(details):
    if isinstance(details, dict):
        return details.get("duration_min") or ""
    return ""


# ---------------------------------------------------------
# PLAY COMMAND
# ---------------------------------------------------------

@app.on_message(
    filters.command(
        [
            "play",
            "vplay",
            "cplay",
            "cvplay",
            "playforce",
            "vplayforce",
            "cplayforce",
            "cvplayforce",
        ]
    )
    & filters.group
    & ~BANNED_USERS
)
@PlayWrapper
async def play_commnd(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    mystic = await message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )

    plist_id = None
    slider = None
    plist_type = None
    spotify = None
    details = None
    track_id = None
    img = config.PLAYLIST_IMG_URL
    cap = ""
    streamtype = "youtube"
    query = ""

    user_id = message.from_user.id
    user_name = message.from_user.first_name

    audio_telegram = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message
        else None
    )

    video_telegram = (
        (message.reply_to_message.video or message.reply_to_message.document)
        if message.reply_to_message
        else None
    )

    # -----------------------------------------------------
    # REPLY TO TELEGRAM AUDIO
    # -----------------------------------------------------

    if audio_telegram:
        if audio_telegram.file_size > 104857600:
            return await mystic.edit_text(_["play_5"])

        duration_min = seconds_to_min(audio_telegram.duration or 0)

        if (audio_telegram.duration or 0) > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
            )

        file_path = await Telegram.get_filepath(audio=audio_telegram)

        if await Telegram.download(_, message, mystic, file_path):
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(audio_telegram, audio=True)
            dur = await Telegram.get_duration(audio_telegram, file_path)

            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }

            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="telegram",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = (
                    e
                    if ex_type == "AssistantErr"
                    else _["general_2"].format(ex_type)
                )
                return await mystic.edit_text(err)

            return await mystic.delete()

        return

    # -----------------------------------------------------
    # REPLY TO TELEGRAM VIDEO / DOCUMENT
    # -----------------------------------------------------

    elif video_telegram:
        if message.reply_to_message.document:
            try:
                ext = (video_telegram.file_name or "").split(".")[-1]
                if ext.lower() not in formats:
                    return await mystic.edit_text(
                        _["play_7"].format(" | ".join(formats))
                    )
            except Exception:
                return await mystic.edit_text(
                    _["play_7"].format(" | ".join(formats))
                )

        if video_telegram.file_size > config.TG_VIDEO_FILESIZE_LIMIT:
            return await mystic.edit_text(_["play_8"])

        file_path = await Telegram.get_filepath(video=video_telegram)

        if await Telegram.download(_, message, mystic, file_path):
            message_link = await Telegram.get_link(message)
            file_name = await Telegram.get_filename(video_telegram)
            dur = await Telegram.get_duration(video_telegram, file_path)

            details = {
                "title": file_name,
                "link": message_link,
                "path": file_path,
                "dur": dur,
            }

            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    video=True,
                    streamtype="telegram",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = (
                    e
                    if ex_type == "AssistantErr"
                    else _["general_2"].format(ex_type)
                )
                return await mystic.edit_text(err)

            return await mystic.delete()

        return

    # -----------------------------------------------------
    # URL PLAYBACK
    # -----------------------------------------------------

    elif url:
        if await YouTube.exists(url):
            if "playlist" in url.lower():
                try:
                    details = await YouTube.playlist(
                        url,
                        config.PLAYLIST_FETCH_LIMIT,
                        message.from_user.id,
                    )

                    if not details:
                        return await mystic.edit_text(_["play_3"])

                except Exception as e:
                    print(f"YouTube playlist error: {type(e).__name__}: {e}")
                    return await mystic.edit_text(_["play_3"])

                streamtype = "playlist"
                plist_type = "yt"

                try:
                    from urllib.parse import urlparse, parse_qs

                    parsed = urlparse(url)
                    params = parse_qs(parsed.query)
                    plist_id = (params.get("list") or [None])[0]

                    if not plist_id:
                        return await mystic.edit_text(_["play_3"])
                except Exception:
                    return await mystic.edit_text(_["play_3"])

                img = config.PLAYLIST_IMG_URL
                cap = _["play_9"]

            else:
                details, track_id = await safe_youtube_track(url)

                if not details:
                    return await mystic.edit_text(_["play_3"])

                streamtype = "youtube"
                img = safe_thumbnail(details)
                cap = _["play_10"].format(
                    safe_title(details),
                    safe_duration(details),
                )

        elif await Spotify.valid(url):
            spotify = True

            if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
                return await mystic.edit_text(
                    "» sᴘᴏᴛɪғʏ ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ʏᴇᴛ.\n\n"
                    "ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ."
                )

            if "track" in url:
                try:
                    details, track_id = await Spotify.track(url)
                except Exception as e:
                    print(f"Spotify track error: {type(e).__name__}: {e}")
                    return await mystic.edit_text(_["play_3"])

                if not isinstance(details, dict) or not track_id:
                    return await mystic.edit_text(_["play_3"])

                streamtype = "youtube"
                img = safe_thumbnail(details)
                cap = _["play_10"].format(
                    safe_title(details),
                    safe_duration(details),
                )

            elif "playlist" in url:
                try:
                    details, plist_id = await Spotify.playlist(url)
                except Exception as e:
                    print(f"Spotify playlist error: {type(e).__name__}: {e}")
                    return await mystic.edit_text(_["play_3"])

                if not details or not plist_id:
                    return await mystic.edit_text(_["play_3"])

                streamtype = "playlist"
                plist_type = "spplay"
                img = config.SPOTIFY_PLAYLIST_IMG_URL
                cap = _["play_11"].format(
                    app.mention, message.from_user.mention
                )

            elif "album" in url:
                try:
                    details, plist_id = await Spotify.album(url)
                except Exception as e:
                    print(f"Spotify album error: {type(e).__name__}: {e}")
                    return await mystic.edit_text(_["play_3"])

                if not details or not plist_id:
                    return await mystic.edit_text(_["play_3"])

                streamtype = "playlist"
                plist_type = "spalbum"
                img = config.SPOTIFY_ALBUM_IMG_URL
                cap = _["play_11"].format(
                    app.mention, message.from_user.mention
                )

            elif "artist" in url:
                try:
                    details, plist_id = await Spotify.artist(url)
                except Exception as e:
                    print(f"Spotify artist error: {type(e).__name__}: {e}")
                    return await mystic.edit_text(_["play_3"])

                if not details or not plist_id:
                    return await mystic.edit_text(_["play_3"])

                streamtype = "playlist"
                plist_type = "spartist"
                img = config.SPOTIFY_ARTIST_IMG_URL
                cap = _["play_11"].format(message.from_user.first_name)

            else:
                return await mystic.edit_text(_["play_15"])

        elif await Apple.valid(url):
            if "album" in url:
                try:
                    details, track_id = await Apple.track(url)
                except Exception as e:
                    print(f"Apple track error: {type(e).__name__}: {e}")
                    return await mystic.edit_text(_["play_3"])

                if not isinstance(details, dict) or not track_id:
                    return await mystic.edit_text(_["play_3"])

                streamtype = "youtube"
                img = safe_thumbnail(details)
                cap = _["play_10"].format(
                    safe_title(details),
                    safe_duration(details),
                )

            elif "playlist" in url:
                spotify = True

                try:
                    details, plist_id = await Apple.playlist(url)
                except Exception as e:
                    print(f"Apple playlist error: {type(e).__name__}: {e}")
                    return await mystic.edit_text(_["play_3"])

                if not details or not plist_id:
                    return await mystic.edit_text(_["play_3"])

                streamtype = "playlist"
                plist_type = "apple"
                cap = _["play_12"].format(
                    app.mention, message.from_user.mention
                )
                img = url

            else:
                return await mystic.edit_text(_["play_3"])

        elif await Resso.valid(url):
            try:
                details, track_id = await Resso.track(url)
            except Exception as e:
                print(f"Resso track error: {type(e).__name__}: {e}")
                return await mystic.edit_text(_["play_3"])

            if not isinstance(details, dict) or not track_id:
                return await mystic.edit_text(_["play_3"])

            streamtype = "youtube"
            img = safe_thumbnail(details)
            cap = _["play_10"].format(
                safe_title(details),
                safe_duration(details),
            )

        elif await SoundCloud.valid(url):
            try:
                details, track_path = await SoundCloud.download(url)
            except Exception as e:
                print(f"SoundCloud error: {type(e).__name__}: {e}")
                return await mystic.edit_text(_["play_3"])

            if not isinstance(details, dict):
                return await mystic.edit_text(_["play_3"])

            duration_sec = details.get("duration_sec", 0) or 0

            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        app.mention,
                    )
                )

            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="soundcloud",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = (
                    e
                    if ex_type == "AssistantErr"
                    else _["general_2"].format(ex_type)
                )
                return await mystic.edit_text(err)

            return await mystic.delete()

        else:
            try:
                await Ritik.stream_call(url)
            except NoActiveGroupCall:
                await mystic.edit_text(_["black_9"])
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=_["play_17"],
                )
            except Exception as e:
                return await mystic.edit_text(
                    _["general_2"].format(type(e).__name__)
                )

            await mystic.edit_text(_["str_2"])

            try:
                await stream(
                    _,
                    mystic,
                    message.from_user.id,
                    url,
                    chat_id,
                    message.from_user.first_name,
                    message.chat.id,
                    video=video,
                    streamtype="index",
                    forceplay=fplay,
                )
            except Exception as e:
                ex_type = type(e).__name__
                err = (
                    e
                    if ex_type == "AssistantErr"
                    else _["general_2"].format(ex_type)
                )
                return await mystic.edit_text(err)

            return await play_logs(
                message, streamtype="M3u8 or Index Link"
            )

    # -----------------------------------------------------
    # SEARCH BY TEXT
    # -----------------------------------------------------

    else:
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await mystic.edit_text(
                _["play_18"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        slider = True
        query = message.text.split(None, 1)[1]

        if "-v" in query:
            query = query.replace("-v", "").strip()

        details, track_id = await safe_youtube_track(query)

        if not details:
            return await mystic.edit_text(_["play_3"])

        streamtype = "youtube"

    # -----------------------------------------------------
    # FINAL VALIDATION
    # -----------------------------------------------------

    if not plist_type and not isinstance(details, dict):
        return await mystic.edit_text(_["play_3"])

    if str(playmode) == "Direct":
        if not plist_type:
            duration_min = safe_duration(details)

            if duration_min:
                duration_sec = safe_duration_seconds(duration_min)

                if duration_sec is None:
                    return await mystic.edit_text(_["play_3"])

                if duration_sec > config.DURATION_LIMIT:
                    return await mystic.edit_text(
                        _["play_6"].format(
                            config.DURATION_LIMIT_MIN, app.mention
                        )
                    )
            else:
                buttons = livestream_markup(
                    _,
                    track_id,
                    user_id,
                    "v" if video else "a",
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                return await mystic.edit_text(
                    _["play_13"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )

        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=video,
                streamtype=streamtype,
                spotify=spotify,
                forceplay=fplay,
            )
        except Exception as e:
            ex_type = type(e).__name__
            err = (
                e
                if ex_type == "AssistantErr"
                else _["general_2"].format(ex_type)
            )
            return await mystic.edit_text(err)

        await mystic.delete()
        return await play_logs(message, streamtype=streamtype)

    # -----------------------------------------------------
    # PLAYLIST / TRACK RESULT BUTTONS
    # -----------------------------------------------------

    else:
        if plist_type:
            ran_hash = "".join(
                random.choices(
                    string.ascii_uppercase + string.digits, k=10
                )
            )
            lyrical[ran_hash] = plist_id

            buttons = playlist_markup(
                _,
                ran_hash,
                message.from_user.id,
                plist_type,
                "c" if channel else "g",
                "f" if fplay else "d",
            )

            await mystic.delete()
            await message.reply_photo(
                photo=img,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return await play_logs(
                message, streamtype=f"Playlist : {plist_type}"
            )

        if slider:
            buttons = slider_markup(
                _,
                track_id,
                message.from_user.id,
                query,
                0,
                "c" if channel else "g",
                "f" if fplay else "d",
            )

            await mystic.delete()

            try:
                await message.reply_photo(
                    photo=safe_thumbnail(details),
                    caption=_["play_10"].format(
                        safe_title(details).title(),
                        safe_duration(details),
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
            except Exception as e:
                print(f"Search result display error: {type(e).__name__}: {e}")
                return await message.reply_text(
                    _["play_10"].format(
                        safe_title(details),
                        safe_duration(details),
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )

            return await play_logs(
                message, streamtype="Searched on Youtube"
            )

        buttons = track_markup(
            _,
            track_id,
            message.from_user.id,
            "c" if channel else "g",
            "f" if fplay else "d",
        )

        await mystic.delete()
        await message.reply_photo(
            photo=img,
            caption=cap,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return await play_logs(
            message, streamtype="URL Searched Inline"
        )


# ---------------------------------------------------------
# MUSIC STREAM CALLBACK
# ---------------------------------------------------------

@app.on_callback_query(filters.regex("MusicStream") & ~BANNED_USERS)
@languageCB
async def play_Music(client, CallbackQuery, _):
    try:
        callback_data = CallbackQuery.data.strip()
        callback_request = callback_data.split(None, 1)[1]
        vidid, user_id, mode, cplay, fplay = callback_request.split("|")
    except (IndexError, ValueError):
        return await CallbackQuery.answer(
            "Invalid request. Dobara try karo.",
            show_alert=True,
        )

    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(
                _["playcb_1"], show_alert=True
            )
        except Exception:
            return

    try:
        chat_id, channel = await get_channeplayCB(
            _, cplay, CallbackQuery
        )
    except Exception:
        return

    user_name = CallbackQuery.from_user.first_name

    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except Exception:
        pass

    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )

    details, track_id = await safe_youtube_track(vidid, True)

    if not details:
        return await mystic.edit_text(_["play_3"])

    duration_min = safe_duration(details)

    if duration_min:
        duration_sec = safe_duration_seconds(duration_min)

        if duration_sec is None:
            return await mystic.edit_text(_["play_3"])

        if duration_sec > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(
                    config.DURATION_LIMIT_MIN, app.mention
                )
            )
    else:
        buttons = livestream_markup(
            _,
            track_id,
            CallbackQuery.from_user.id,
            mode,
            "c" if cplay == "c" else "g",
            "f" if fplay == "f" else "d",
        )
        return await mystic.edit_text(
            _["play_13"],
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None

    try:
        await stream(
            _,
            mystic,
            CallbackQuery.from_user.id,
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="youtube",
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = (
            e
            if ex_type == "AssistantErr"
            else _["general_2"].format(ex_type)
        )
        return await mystic.edit_text(err)

    return await mystic.delete()


# ---------------------------------------------------------
# ADMIN HELP CALLBACK
# ---------------------------------------------------------

@app.on_callback_query(
    filters.regex("RitikmousAdmin") & ~BANNED_USERS
)
async def Ritikmous_check(client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "» ʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ :\n\n"
            "ᴏᴘᴇɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ sᴇᴛᴛɪɴɢs.\n"
            "-> ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs\n"
            "-> ᴄʟɪᴄᴋ ᴏɴ ʏᴏᴜʀ ɴᴀᴍᴇ\n"
            "-> ᴜɴᴄʜᴇᴄᴋ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.",
            show_alert=True,
        )
    except Exception:
        pass


# ---------------------------------------------------------
# PLAYLIST CALLBACK
# ---------------------------------------------------------

@app.on_callback_query(
    filters.regex("RitikPlaylists") & ~BANNED_USERS
)
@languageCB
async def play_playlists_command(client, CallbackQuery, _):
    try:
        callback_data = CallbackQuery.data.strip()
        callback_request = callback_data.split(None, 1)[1]

        (
            videoid,
            user_id,
            ptype,
            mode,
            cplay,
            fplay,
        ) = callback_request.split("|")
    except (IndexError, ValueError):
        return await CallbackQuery.answer(
            "Invalid playlist request.", show_alert=True
        )

    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(
                _["playcb_1"], show_alert=True
            )
        except Exception:
            return

    try:
        chat_id, channel = await get_channeplayCB(
            _, cplay, CallbackQuery
        )
    except Exception:
        return

    user_name = CallbackQuery.from_user.first_name

    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass

    try:
        await CallbackQuery.answer()
    except Exception:
        pass

    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )

    videoid = lyrical.get(videoid)

    if not videoid:
        return await mystic.edit_text(_["play_3"])

    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    spotify = True
    result = None

    if ptype == "yt":
        spotify = False
        try:
            result = await YouTube.playlist(
                videoid,
                config.PLAYLIST_FETCH_LIMIT,
                CallbackQuery.from_user.id,
                True,
            )
        except Exception as e:
            print(f"YouTube playlist callback error: {type(e).__name__}: {e}")
            return await mystic.edit_text(_["play_3"])

    elif ptype == "spplay":
        try:
            result, spotify_id = await Spotify.playlist(videoid)
        except Exception as e:
            print(f"Spotify playlist callback error: {type(e).__name__}: {e}")
            return await mystic.edit_text(_["play_3"])

    elif ptype == "spalbum":
        try:
            result, spotify_id = await Spotify.album(videoid)
        except Exception as e:
            print(f"Spotify album callback error: {type(e).__name__}: {e}")
            return await mystic.edit_text(_["play_3"])

    elif ptype == "spartist":
        try:
            result, spotify_id = await Spotify.artist(videoid)
        except Exception as e:
            print(f"Spotify artist callback error: {type(e).__name__}: {e}")
            return await mystic.edit_text(_["play_3"])

    elif ptype == "apple":
        try:
            result, apple_id = await Apple.playlist(videoid, True)
        except Exception as e:
            print(f"Apple playlist callback error: {type(e).__name__}: {e}")
            return await mystic.edit_text(_["play_3"])

    else:
        return await mystic.edit_text(_["play_3"])

    if not result:
        return await mystic.edit_text(_["play_3"])

    try:
        await stream(
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="playlist",
            spotify=spotify,
            forceplay=ffplay,
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = (
            e
            if ex_type == "AssistantErr"
            else _["general_2"].format(ex_type)
        )
        return await mystic.edit_text(err)

    return await mystic.delete()


# ---------------------------------------------------------
# SEARCH SLIDER CALLBACK
# ---------------------------------------------------------

@app.on_callback_query(
    filters.regex("slider") & ~BANNED_USERS
)
@languageCB
async def slider_queries(client, CallbackQuery, _):
    try:
        callback_data = CallbackQuery.data.strip()
        callback_request = callback_data.split(None, 1)[1]

        (
            what,
            rtype,
            query,
            user_id,
            cplay,
            fplay,
        ) = callback_request.split("|")
    except (IndexError, ValueError):
        return await CallbackQuery.answer(
            "Invalid search request.", show_alert=True
        )

    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(
                _["playcb_1"], show_alert=True
            )
        except Exception:
            return

    rtype = int(rtype)

    if what == "F":
        query_type = 0 if rtype == 9 else rtype + 1
    elif what == "B":
        query_type = 9 if rtype == 0 else rtype - 1
    else:
        return await CallbackQuery.answer(
            "Invalid slider action.", show_alert=True
        )

    try:
        await CallbackQuery.answer(_["playcb_2"])
    except Exception:
        pass

    try:
        result = await YouTube.slider(query, query_type)

        if not result or len(result) != 4:
            return await CallbackQuery.answer(
                "Song details nahi mile. Dobara try karo.",
                show_alert=True,
            )

        title, duration_min, thumbnail, vidid = result

        if not title or not vidid:
            return await CallbackQuery.answer(
                "Song details nahi mile. Dobara try karo.",
                show_alert=True,
            )

        thumbnail = thumbnail or config.PLAYLIST_IMG_URL
        duration_min = duration_min or "Live"

        buttons = slider_markup(
            _,
            vidid,
            user_id,
            query,
            query_type,
            cplay,
            fplay,
        )

        med = InputMediaPhoto(
            media=thumbnail,
            caption=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )

        return await CallbackQuery.edit_message_media(
            media=med,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        print(f"Slider error: {type(e).__name__}: {e}")
        try:
            return await CallbackQuery.answer(
                "Search failed. Dobara try karo.",
                show_alert=True,
            )
        except Exception:
            return

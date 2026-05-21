"""
Medya oynatma - Windows'ta YouTube, Spotify ve varsayilan muzik uygulamasi.
"""

from __future__ import annotations

import urllib.parse

from actions.browser import browser_control
from actions.open_app import open_app
from actions.windows_utils import open_url, press_key


def _play_youtube(query: str) -> str:
    return browser_control("play_youtube", query=query)


def _play_spotify(query: str, autoplay: bool = True) -> str:
    encoded_query = urllib.parse.quote(query.strip())
    search_url = f"spotify:search:{encoded_query}"
    try:
        open_url(search_url)
    except Exception as exc:
        return f"Spotify acilamadi: {exc}"

    if autoplay:
        # Spotify protokolu arama ekranini acar; Enter/Space otomasyonu best-effort.
        press_key("enter", delay=1.6)
        press_key("space", delay=0.4)
        return f"Spotify'da arama acildi ve oynatma denendi: {query}"
    return f"Spotify icinde '{query}' aramasi acildi."


def _play_windows_music(query: str, autoplay: bool = True) -> str:
    encoded_query = urllib.parse.quote(query.strip())
    try:
        open_url(f"mswindowsmusic:search?term={encoded_query}")
        return f"Windows Muzik uygulamasinda '{query}' aramasi acildi."
    except Exception:
        open_app("music")
        return f"Windows Muzik uygulamasi acildi. Arama tamamlanamazsa YouTube'u kullanabilirsin: {query}"


def play_media(query: str, provider: str = "auto", autoplay: bool = True) -> str:
    if not query or not query.strip():
        return "Calinacak icerik belirtilmedi."

    normalized_provider = (provider or "auto").strip().lower()
    if normalized_provider in {"yt", "youtube music"}:
        normalized_provider = "youtube"
    elif normalized_provider in {"music", "windows_music"}:
        normalized_provider = "windows_music"

    if normalized_provider == "spotify":
        return _play_spotify(query, autoplay=autoplay)
    if normalized_provider == "windows_music":
        return _play_windows_music(query, autoplay=autoplay)
    if normalized_provider == "youtube":
        return _play_youtube(query)

    spotify_result = _play_spotify(query, autoplay=autoplay)
    if "acilamadi" not in spotify_result.lower():
        return spotify_result
    return _play_youtube(query)

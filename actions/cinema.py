"""
Sinema ve Dizi Zekası İstihbarat Motoru.

Platformlardaki yeni yapımları (radar), ruh haline göre akıllı film/dizi tavsiyelerini 
ve kategorize edilmiş izleme listesi ile bölüm takibini (watchlist/tracker) yönetir.
"""

from __future__ import annotations

import feedparser
import time
import threading
import re
from html import unescape
from memory.memory_manager import load_memory, update_memory, delete_memory


CINEMA_FEEDS = [
    ("DonanimHaber Dizi/Film", "https://www.donanimhaber.com/rss/sinema-ve-dizi"),
    ("Beyazperde", "https://www.beyazperde.com/rss/haberler.xml"),
]

_CINEMA_CACHE = {
    "items": [],
    "last_updated": 0,
    "lock": threading.Lock()
}


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_cinema_radar() -> list[dict]:
    """
    Sinema, dizi dünyası ve platformlardaki (Netflix, Prime vb.) son gelişmeleri getirir.
    """
    now = time.time()
    with _CINEMA_CACHE["lock"]:
        if now - _CINEMA_CACHE["last_updated"] < 1200 and _CINEMA_CACHE["items"]:
            return _CINEMA_CACHE["items"]

    new_items = []
    for source_name, url in CINEMA_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                title = _clean_html(getattr(entry, 'title', ''))
                summary = _clean_html(getattr(entry, 'summary', getattr(entry, 'description', '')))
                link = getattr(entry, 'link', '')
                if not title or not link:
                    continue
                if len(summary) > 300:
                    summary = summary[:297] + "..."
                new_items.append({
                    "title": title,
                    "summary": summary,
                    "source": source_name,
                    "link": link
                })
        except Exception as e:
            print(f"[Cinema Radar] {source_name} okunamadı: {e}")

    with _CINEMA_CACHE["lock"]:
        _CINEMA_CACHE["items"] = new_items[:10]
        _CINEMA_CACHE["last_updated"] = time.time()
        return _CINEMA_CACHE["items"]


def save_tracker_item(item_name: str, item_type: str = "movie", episode_info: str = "İzlenecek") -> str:
    """
    Dizi veya filmleri kategorisiyle birlikte izleme listesine ekler.
    """
    item_key = re.sub(r'[^a-z0-9_]', '', item_name.lower().replace(' ', '_'))
    if not item_key:
        return "Film/dizi adı geçersiz."
    
    itype = "series" if "series" in item_type.lower() or "dizi" in item_type.lower() else "movie"
    if not episode_info or episode_info.strip() == "":
        episode_info = "İzlenecek"
        
    update_memory({
        "watchlist": {
            item_key: {
                "name": item_name,
                "type": itype,
                "value": episode_info
            }
        }
    })
    tr_type = "Dizi" if itype == "series" else "Film"
    return f"İzlenecekler listesine eklendi ({tr_type}): {item_name}" + (f" -> {episode_info}" if episode_info != "İzlenecek" else "")


def format_tracker_list() -> str:
    """
    İzleme listesindeki tüm dizi ve filmleri Film ve Dizi olarak kategorize edip döndürür.
    """
    mem = load_memory()
    watchlist = mem.get("watchlist", {})
    if not watchlist:
        return "İzlenecekler listemizde henüz kayıtlı film veya dizi bulunmuyor."
        
    movies = []
    series = []
    for k, v in watchlist.items():
        name = v.get("name", k)
        val = v.get("value", "İzlenecek")
        itype = v.get("type", "movie")
        
        # Eğer eski kayıtlarda type yoksa ama içinde sezon/bölüm ifadesi varsa dizi kabul et
        if "type" not in v and ("s0" in val.lower() or "sezon" in val.lower() or "bölüm" in val.lower() or "bolum" in val.lower()):
            itype = "series"
            
        entry = f"- {name}" + (f" ({val})" if val and val != "İzlenecek" else "")
        if itype == "series":
            series.append(entry)
        else:
            movies.append(entry)
            
    lines = ["[İzlenecekler ve Takip Listemiz]"]
    if movies:
        lines.append("\n[FILM KATEGORISI]:")
        lines.extend(movies)
    if series:
        lines.append("\n[DIZI KATEGORISI]:")
        lines.extend(series)
        
    if not movies and not series:
        return "İzlenecekler listesi boş."
        
    return "\n".join(lines)

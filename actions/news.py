"""
Global AI, Teknoloji ve Gündem Haberleri İstihbarat Motoru.

RSS kanallarından asenkron olarak son haberleri çeker, temizler ve önbellekler.
"""

from __future__ import annotations

import feedparser
import time
import threading
import re
import urllib.request
from html import unescape


FEEDS = {
    "ai": [
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("AI News", "https://www.artificialintelligence-news.com/feed/"),
        ("Wired Tech", "https://www.wired.com/feed/category/tech/latest/rss"),
    ],
    "tech": [
        ("DonanimHaber", "https://www.donanimhaber.com/rss/tum"),
        ("Webtekno", "https://www.webtekno.com/rss.xml"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ],
    "turkey": [
        ("TRT Haber", "https://www.trthaber.com/sondakika.rss"),
        ("Haberturk Eko", "https://www.haberturk.com/rss/ekonomi.xml"),
    ],
    "trabzonspor": [
        ("Fotomac TS", "https://www.fotomac.com.tr/rss/trabzonspor.xml"),
        ("Fanatik TS", "https://www.fanatik.com.tr/rss/trabzonspor"),
    ]
}

_NEWS_CACHE = {
    "items": {},  # "news_1": { id, title, summary, link, source, cat, timestamp }
    "last_updated": 0,
    "lock": threading.Lock(),
    "counter": 1
}


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def fetch_news_summary(category: str = "ai") -> list[dict]:
    """
    Belirli bir kategorideki son haberleri getirir. 10 dakikada bir güncellenir.
    """
    category = category.lower().strip()
    if category not in FEEDS:
        category = "ai"

    now = time.time()
    with _NEWS_CACHE["lock"]:
        cached_items = [item for item in _NEWS_CACHE["items"].values() if item["cat"] == category]
        if now - _NEWS_CACHE["last_updated"] < 600 and cached_items:
            return sorted(cached_items, key=lambda x: x["timestamp"], reverse=True)[:10]

    new_items = []
    sources = FEEDS.get(category, FEEDS["ai"])
    
    for source_name, url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:  # Her kaynaktan en yeni 6 haber
                title = _clean_html(getattr(entry, 'title', ''))
                summary = _clean_html(getattr(entry, 'summary', getattr(entry, 'description', '')))
                link = getattr(entry, 'link', '')
                
                if not title or not link:
                    continue
                if len(summary) > 400:
                    summary = summary[:397] + "..."
                    
                new_items.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": source_name,
                    "cat": category,
                    "timestamp": time.time()
                })
        except Exception as e:
            print(f"[News] {source_name} okunamadı: {e}")

    with _NEWS_CACHE["lock"]:
        # Cache'e eklerken benzersiz ID (news_1, news_2) ver
        for item in new_items:
            nid = f"news_{_NEWS_CACHE['counter']}"
            item["id"] = nid
            _NEWS_CACHE["items"][nid] = item
            _NEWS_CACHE["counter"] += 1
            
        _NEWS_CACHE["last_updated"] = time.time()
        
        all_cat_items = [item for item in _NEWS_CACHE["items"].values() if item["cat"] == category]
        return sorted(all_cat_items, key=lambda x: x["timestamp"], reverse=True)[:10]


def get_news_detail(news_id: str) -> dict:
    """
    ID'si verilen haberin linkine gidip detaylı içeriğini veya özetini getirir.
    """
    with _NEWS_CACHE["lock"]:
        item = _NEWS_CACHE["items"].get(news_id.lower().strip())
        
    if not item:
        return {"error": f"Haber ID bulunamadı: {news_id}. Lütfen geçerli bir ID (Örn: news_1) kullanın."}

    link = item["link"]
    title = item["title"]
    source = item["source"]
    summary = item["summary"]

    try:
        req = urllib.request.Request(
            link, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        # Basit body/paragraph temizliği
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
        full_text = " ".join([_clean_html(p) for p in paragraphs if len(p) > 30])
        
        if len(full_text) < 200:
            full_text = summary # Eğer sayfa dinamik (JS) ise özetini döndür
            
        if len(full_text) > 3500:
            full_text = full_text[:3500] + "..."
            
        return {
            "id": news_id,
            "title": title,
            "source": source,
            "link": link,
            "content": full_text
        }
    except Exception as e:
        print(f"[News Detail] Link okunamadı ({link}): {e}")
        return {
            "id": news_id,
            "title": title,
            "source": source,
            "link": link,
            "content": summary  # Hata olursa mevcut özeti kullan
        }

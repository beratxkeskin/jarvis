import yfinance as yf
import time
import threading

# Önbellek: Her sorguda yfinance'i yormamak için son verileri 60 saniye hafızada tutuyoruz
_MARKET_CACHE = {
    "data": {},
    "last_updated": 0,
    "lock": threading.Lock()
}

# Takip edilecek temel semboller ve okunabilir isimleri
DEFAULT_SYMBOLS = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "TRY=X":   "USD/TRY",
    "EURTRY=X":"EUR/TRY",
    "GC=F":    "Altin (Ons)",
    "XU100.IS":"BIST 100"
}

def get_live_market_summary() -> dict:
    """
    HUD arayüzündeki Market Intelligence kartı için temel sembollerin anlık fiyat ve günlük değişimlerini getirir.
    """
    now = time.time()
    with _MARKET_CACHE["lock"]:
        if now - _MARKET_CACHE["last_updated"] < 60 and _MARKET_CACHE["data"]:
            return _MARKET_CACHE["data"]
            
    res = {}
    try:
        tickers = yf.Tickers(list(DEFAULT_SYMBOLS.keys()))
        for sym, title in DEFAULT_SYMBOLS.items():
            t = tickers.tickers.get(sym)
            if not t:
                continue
            # Önce t.info'dan gerçek zamanlı veriyi deniyoruz (Özellikle BIST için history geç güncelleniyor)
            try:
                info = t.info
                cp = info.get("regularMarketPrice") or info.get("currentPrice")
                chg_pct = info.get("regularMarketChangePercent")
            except Exception:
                cp = None
                chg_pct = None
                
            if cp is not None and chg_pct is not None:
                current_close = cp
                diff_pct = chg_pct
            else:
                hist = t.history(period="5d")
                if len(hist) < 1:
                    continue
                    
                current_close = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_close
                diff_pct = ((current_close - prev_close) / prev_close) * 100.0
            
            # Fiyatı biçimlendir
            if current_close > 1000:
                price_str = f"{current_close:,.0f}"
            else:
                price_str = f"{current_close:,.2f}"
                
            prefix = "$" if ("USD" in sym or sym == "GC=F") else ("TL " if "TRY" in sym else "")
            
            res[sym] = {
                "name": title,
                "price": f"{prefix}{price_str}",
                "change_pct": diff_pct,
                "raw_price": current_close
            }
            
        if "GC=F" in res and "TRY=X" in res:
            oz_price = res["GC=F"]["raw_price"]
            usd_try = res["TRY=X"]["raw_price"]
            gram_tl = (oz_price / 31.1034768) * usd_try
            gram_chg = res["GC=F"]["change_pct"] + res["TRY=X"]["change_pct"]
            
            # Altın Ons yerine doğrudan Gram Altın (TL) gösterelim
            del res["GC=F"]
            res["GOLD-GRAM"] = {
                "name": "Altin (Gram)",
                "price": f"TL {gram_tl:,.0f}",
                "change_pct": gram_chg,
                "raw_price": gram_tl
            }
            
        with _MARKET_CACHE["lock"]:
            _MARKET_CACHE["data"] = res
            _MARKET_CACHE["last_updated"] = time.time()
            
    except Exception as e:
        print(f"[Market] Ticker çekilirken hata: {e}")
        if _MARKET_CACHE["data"]:
            return _MARKET_CACHE["data"]
            
    return res

def query_specific_asset(query_symbol: str) -> str:
    """
    Yapay zekanın spesifik bir hisse, döviz veya kripto sorması durumunda çağrılır.
    """
    query_symbol = query_symbol.upper().strip()
    
    def _fetch(sym):
        t = yf.Ticker(sym)
        info = t.info
        cp = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        nm = info.get("longName") or info.get("shortName") or sym
        cr = info.get("currency", "USD")
        if not cp:
            hist = t.history(period="1d")
            if len(hist) > 0:
                cp = hist["Close"].iloc[-1]
        return cp, nm, cr

    try:
        price, name, curr = _fetch(query_symbol)
        
        # Eğer fiyat bulunamadıysa ve sembolde .IS yoksa (Borsa İstanbul hissesi ihtimali)
        if not price and "." not in query_symbol:
            bist_sym = f"{query_symbol}.IS"
            try:
                price, name, curr = _fetch(bist_sym)
                if price:
                    query_symbol = bist_sym
            except Exception:
                pass
                
        if price:
            prefix = "TL " if curr == "TRY" else ("$" if curr == "USD" else f"{curr} ")
            return f"{name} ({query_symbol}): {prefix}{price:,.2f}."
        else:
            return f"{query_symbol} sembolü için güncel fiyat bilgisi alınamadı."
    except Exception as e:
        # Hata durumunda yine de .IS ekleyip son bir şans deneyelim
        if "." not in query_symbol:
            bist_sym = f"{query_symbol}.IS"
            try:
                price, name, curr = _fetch(bist_sym)
                if price:
                    prefix = "TL " if curr == "TRY" else ("$" if curr == "USD" else f"{curr} ")
                    return f"{name} ({bist_sym}): {prefix}{price:,.2f}."
            except Exception:
                pass
        return f"{query_symbol} sorgulanamadı. Lütfen sembolün doğru olduğundan emin olun."

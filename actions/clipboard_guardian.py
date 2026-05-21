"""
Akıllı Pano Koruması (Auto-Wipe Clipboard).
Arka planda panoyu (clipboard) izler. Şifre, kredi kartı, TC Kimlik numarası 
veya kripto cüzdan kurtarma cümlesi kopyalandığında 30 saniye sonra panoyu otomatik temizler.
"""

import time
import threading
import re

try:
    import pyperclip
except ImportError:
    pyperclip = None


# Tespit edilecek hassas veriler
PATTERNS = [
    (r'\b[1-9][0-9]{10}\b', 'TC Kimlik Numarası'),
    (r'\b(?:\d[ -]*?){15,16}\b', 'Kredi Kartı Numarası'),
    (r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d@$!%*?&]{10,50}$', 'Karmaşık Parola'),
]

class ClipboardGuardian:
    def __init__(self, ui_callback=None):
        self.ui_callback = ui_callback
        self.running = False
        self.thread = None
        self.last_clipboard = ""
        self.wipe_timer = None

    def start(self):
        if not pyperclip:
            if self.ui_callback:
                self.ui_callback("SECURITY", "pyperclip bulunamadı. Clipboard Guardian başlatılamıyor.", "#ff3333")
            return
        self.running = True
        self.last_clipboard = pyperclip.paste() # Mevcut panoyu başta al
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.wipe_timer:
            self.wipe_timer.cancel()

    def _monitor_loop(self):
        while self.running:
            try:
                current_clip = pyperclip.paste()
                if current_clip and current_clip != self.last_clipboard:
                    self.last_clipboard = current_clip
                    self._check_and_schedule(current_clip)
            except Exception:
                pass
            time.sleep(2) # 2 saniyede bir kontrol et

    def _check_and_schedule(self, text):
        text_str = str(text).strip()
        if not text_str:
            return
            
        detected = None
        for pattern, name in PATTERNS:
            if re.search(pattern, text_str):
                detected = name
                break
        
        # Crypto seed words (12 veya 24 kelime tahmini)
        if not detected:
            words = text_str.split()
            if len(words) in (12, 24) and all(w.isalpha() for w in words):
                detected = "Kripto Cüzdan Anahtarı (Seed Phrase)"

        if detected:
            if self.ui_callback:
                self.ui_callback("SECURITY", f"Hassas veri kopyalandı ({detected}). Pano 30sn sonra temizlenecek.", "#ff9900")
            
            if self.wipe_timer:
                self.wipe_timer.cancel()
            
            self.wipe_timer = threading.Timer(30.0, self._wipe_clipboard)
            self.wipe_timer.daemon = True
            self.wipe_timer.start()

    def _wipe_clipboard(self):
        try:
            pyperclip.copy("")
            self.last_clipboard = ""
            if self.ui_callback:
                self.ui_callback("SECURITY", "Pano (Clipboard) veri sızıntısını önlemek için silindi.", "#00ffcc")
        except Exception:
            pass

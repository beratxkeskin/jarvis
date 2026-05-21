#!/usr/bin/env python3
"""
JARVIS Windows - Gercek zamanli sesli yardimci cekirdegi
Windows ortamina uyarlanmis calisma akisi
"""

import asyncio
import datetime
import threading
import traceback
import os
import re
import sys
import io

# Force UTF-8 for stdout and stderr on Windows to support emojis and Turkish characters without crashes
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

from pathlib import Path
from core.wake_word import WakeWordListener

import pyaudio  # type: ignore[reportMissingModuleSource]
from google import genai  # type: ignore[reportMissingImports]
from google.genai import types  # type: ignore[reportMissingImports]

from app_config import get_app_config_value
from ui import JarvisUI
from memory.memory_manager import load_memory, update_memory, delete_memory, format_memory_for_prompt, MEMORY_FILE
from actions.open_app import open_app, close_app
from actions.sys_info  import sys_info
from actions.calendar import get_calendar_events, add_calendar_event, delete_calendar_event
from actions.reminders import get_reminders, add_reminder, delete_reminder
from actions.browser   import browser_control
from actions.shell     import shell_run
from actions.whatsapp  import send_whatsapp_message, save_whatsapp_contact
from actions.media     import play_media
from actions.weather   import get_weather_summary
from actions.screen_vision import analyze_screen
from actions.youtube_stats import get_youtube_channel_report

# PEP-8 Module Level Imports
from collections import deque
import time
import tempfile
import ctypes
from ctypes import wintypes
import psutil
import pyperclip
import subprocess

from actions.clipboard_guardian import ClipboardGuardian
from core.voice_biometrics import has_voiceprint, enroll_voiceprint
from actions.news import get_news_detail, fetch_news_summary
from actions.cinema import save_tracker_item, format_tracker_list, get_cinema_radar
from actions.market import get_live_market_summary, query_specific_asset
from actions.windows_utils import get_foreground_window_title

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"


CONTROL_TOKEN_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

# ── Model ───────────────────────────────────────────────────────────────────
LIVE_MODEL = "models/gemini-2.5-flash-native-audio-latest"

RESTRICTED_TOOLS = {
    "send_whatsapp_message",
    "read_clipboard",
    "optimize_system",
    "power_control",
    "shell_run",
    "delete_memory",
}

# ── Audio ───────────────────────────────────────────────────────────────────
FORMAT           = pyaudio.paInt16
CHANNELS         = 1
SEND_SAMPLE_RATE = 16000
RECV_SAMPLE_RATE = 24000
CHUNK_SIZE       = 1024
pya              = pyaudio.PyAudio()

from core.tools import TOOL_DECLARATIONS


def get_api_key() -> str:
    return str(get_app_config_value("gemini_api_key", "") or "")


def load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "Sen JARVIS'sin — Windows'ta calisan kişisel AI asistanı. "
            "Türkçe konuş. Kısa ve net yanıtlar ver. "
            "Araçları kullanarak görevleri tamamla, asla taklit etme."
        )


class JarvisLive:
    def __init__(self, ui: JarvisUI, wake_word=None):
        self.ui             = ui
        self.wake_word      = wake_word
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self._has_greeted   = False
        # CHUNK_SIZE=1024 (64ms). Ağ gecikmelerini ve komut öncesini kapsamak için 10 saniyelik 160 chunk.
        self.recent_audio_buffer = deque(maxlen=160)
        self.last_user_transcripts = deque(maxlen=5)
        self._session_unlocked = False
        self._unlocked_timer = None
        self._enrollment_mode = False
        self.enrollment_audio_buffer = []
        self.english_tutor_mode = False

        # Configuration Cache
        self._cached_prompt = None
        self._cached_prompt_mtime = 0
        self._cached_memory_str = None
        self._cached_memory_mtime = 0


        # Akıllı Pano Koruması (Clipboard Guardian) Başlatma
        self.clipboard_guardian = ClipboardGuardian(ui_callback=self.ui.add_neural_log)
        self.clipboard_guardian.start()

        self.ui.on_text_command  = self._on_text_command
        self.ui.on_pause_toggle  = self._on_pause_toggle
        self.ui.on_effects_state_change = self._on_effects_state_change
        self._paused             = False

    def _unlock_session_temporarily(self):
        self._session_unlocked = True
        if self._unlocked_timer:
            self._unlocked_timer.cancel()
        self._unlocked_timer = threading.Timer(300.0, self._lock_session)
        self._unlocked_timer.daemon = True
        self._unlocked_timer.start()
        self.ui.add_neural_log("SECURITY", "Session Unlocked (5 min)", "#00ffcc")

    def _lock_session(self):
        self._session_unlocked = False
        self.ui.add_neural_log("SECURITY", "Session Locked (Timeout)", "#ff3333")


    def _on_pause_toggle(self, paused: bool):
        self._paused = paused
        if self.wake_word:
            if paused:
                self.wake_word.resume_listening()
            else:
                self.wake_word.pause_listening()

    def _on_effects_state_change(self, enabled: bool):
        pass

    def _focus_ui_section_for_tool(self, tool_name: str, args: dict):
        if tool_name == "sys_info":
            query = str(args.get("query", "")).strip().lower()
            if query in {"time", "saat", "zaman", "date", "tarih"}:
                self.ui.focus_panel("time", duration_ms=5200)
            else:
                self.ui.focus_panel("system", duration_ms=5200)
        elif tool_name == "get_weather":
            self.ui.focus_panel("weather", duration_ms=5600)
        elif tool_name == "get_market_data":
            self.ui.focus_panel("market", duration_ms=6000)

    def _register_future(self, future, task_name="Mesaj gönderimi"):
        def callback(fut):
            try:
                fut.result()
            except Exception as e:
                print(f"[JARVIS] ❌ {task_name} hatası: {e}")
                self.ui.write_log(f"ERR: {task_name} başarısız oldu — {e}")
        future.add_done_callback(callback)

    def _on_text_command(self, text: str):
        if self._paused:
            return
        self.ui.write_log(f"Siz: {text}")
        if not self._loop or not self.session:
            self.ui.write_log("ERR: JARVIS bağlantısı henüz hazır değil.")
            return
        fut = asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )
        self._register_future(fut, "Metin mesajı gönderimi")

    async def _interrupt_audio(self):
        try:
            if self.audio_in_queue:
                while not self.audio_in_queue.empty():
                    try:
                        self.audio_in_queue.get_nowait()
                    except Exception:
                        break
            if self.out_queue:
                while not self.out_queue.empty():
                    try:
                        self.out_queue.get_nowait()
                    except Exception:
                        break
            if self.session:
                await self.session.send_realtime_input(audio_stream_end=True)
            self.set_speaking(False)
        except Exception:
            pass


    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        else:
            self.ui.set_state("LISTENING")

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.ui.write_debug(f"{tool_name}: {short}", level="ERROR")
        self.ui.set_state("ERROR")

    @staticmethod
    def _result_looks_like_error(result) -> bool:
        text = str(result or "").strip().lower()
        if not text:
            return False
        error_markers = (
            "hata",
            "error",
            "alinamadi",
            "alınamadı",
            "bulunamadi",
            "bulunamadı",
            "acilamadi",
            "açılamadı",
            "tamamlanamadi",
            "tamamlanamadı",
            "gecersiz",
            "geçersiz",
            "izin gerekiyor",
            "izin gerekli",
            "baglanti",
            "bağlantı",
            "gerekli.",
        )
        return any(marker in text for marker in error_markers)

    @staticmethod
    def _should_play_success_sfx(tool_name: str, args: dict, result) -> bool:
        action_tools = {
            "open_app",
            "close_app",
            "add_calendar_event",
            "add_reminder",
            "delete_calendar_event",
            "remove_calendar_event",
        }
        if tool_name in action_tools:
            return True

        if tool_name == "send_whatsapp_message":
            text = str(result or "").lower()
            if bool(args.get("send_now", False)):
                return "gönderildi" in text or "gonderildi" in text
            return False

        return False

    @staticmethod
    def _clean_transcript_text(text: str) -> tuple[str, bool]:
        raw = str(text or "")
        had_noise = False
        if CONTROL_TOKEN_RE.search(raw):
            had_noise = True
            raw = CONTROL_TOKEN_RE.sub(" ", raw)
        cleaned = []
        for ch in raw:
            if ch in "\n\r\t" or ord(ch) >= 32:
                cleaned.append(ch)
            else:
                had_noise = True
        return "".join(cleaned), had_noise

    def _build_config(self) -> types.LiveConnectConfig:
        # 1. System Prompt Cache Check
        try:
            prompt_mtime = os.path.getmtime(PROMPT_PATH)
        except Exception:
            prompt_mtime = 0

        if self._cached_prompt is None or prompt_mtime != self._cached_prompt_mtime:
            self._cached_prompt = load_system_prompt()
            self._cached_prompt_mtime = prompt_mtime

        # 2. Memory Cache Check
        try:
            memory_mtime = os.path.getmtime(MEMORY_FILE)
        except Exception:
            memory_mtime = 0

        if self._cached_memory_str is None or memory_mtime != self._cached_memory_mtime:
            memory = load_memory()
            self._cached_memory_str = format_memory_for_prompt(memory)
            self._cached_memory_mtime = memory_mtime

        now     = datetime.datetime.now()
        time_ctx = f"[ŞU ANKİ ZAMAN]\n{now.strftime('%A, %d %B %Y — %H:%M')}\n\n"

        parts = [time_ctx]
        if self._cached_memory_str:
            parts.append(self._cached_memory_str + "\n\n")
        parts.append(self._cached_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=str(get_app_config_value("voice", "Charon") or "Charon")
                    )
                )
            ),
        )

    async def _tool_enroll_voiceprint(self, args, loop):
        if getattr(self, "_just_enrolled", False) and has_voiceprint():
            return "Ses iziniz az önce başarıyla şifrelendi ve kaydedildi efendim, tekrar kayıt yapılmasına gerek yok."
            
        self.set_speaking(False)
        self._enrollment_mode = True
        self.enrollment_audio_buffer = []
        self.ui.add_neural_log("SECURITY", "Master Enrollment Mode Active", "#00ffcc")
        
        # Schedule the actual enrollment as a background task so we don't block the receive loop!
        asyncio.create_task(self._background_enrollment_routine())
        return "Ses kaydı ve biyometrik şifreleme protokolü başlatıldı efendim. Lütfen ekrandaki cümleleri sırayla okuyunuz."

    async def _background_enrollment_routine(self):
        try:
            sentences = [
                "1. Yapay zeka asistanım JARVIS, sesimi gırtlak frekansım ve anatomik tınımla biyometrik olarak analiz ediyor.",
                "2. Güvenlik protokolleri gereği hassas sistem komutlarını yalnızca benim sesimle doğrulayacak ve çalıştıracak.",
                "3. Bu sistemin tek yetkili sahibi ve yöneticisi olarak tüm komutların onayı bana aittir.",
                "4. Her gün bilgisayarımı açarak dijital asistanımla çalışmaya başlıyorum.",
                "5. Teknoloji ve yazılım alanındaki projelerimde bu sistem bana destek sağlıyor.",
                "6. Bu sistemin tüm komutları ve işlemleri yalnızca benim onayımla gerçekleştirilecek.",
                "7. Sesimin frekans analizi tamamlandığında kimlik doğrulama aktif hale gelecek.",
                "8. Mikrofon sensörü şu anda benim benzersiz ses karakterimi öğreniyor.",
                "9. Sistem güvenliği için bu kayıt işleminin doğru ve eksiksiz yapılması önemlidir.",
                "10. Kayıt tamamlandığında artık yalnızca benim sesim bu sistemde yetkili olacak.",
            ]
            print("[JARVIS] 🎙️ Ses kaydı başladı, lütfen ekrandaki cümleleri okuyun...")
            for idx, s in enumerate(sentences, 1):
                self.ui.write_log(f"🎙️ [LÜTFEN OKUYUN {idx}/10] {s}")
                await asyncio.sleep(6.0)
                
            CHUNK_BYTES = 16000 * 2 * 5  # 5 saniyelik parça
            full_audio = b"".join(self.enrollment_audio_buffer)
            chunks = [
                full_audio[i:i+CHUNK_BYTES]
                for i in range(0, len(full_audio), CHUNK_BYTES)
                if len(full_audio[i:i+CHUNK_BYTES]) >= CHUNK_BYTES // 2
            ]
            success = enroll_voiceprint(chunks)
            if success:
                self._just_enrolled = True
                self.ui.add_neural_log("SECURITY", "Master X-Vector Saved", "#00ffcc")
                msg = "[SYSTEM EVENT: ENROLLMENT SUCCESSFUL] Ses kaydı başarıyla tamamlandı. SpeechBrain ECAPA-TDNN yapay zeka sinir ağıyla 192-boyutlu Master X-Vector kaydedildi. Kullanıcıya ses izinin başarıyla şifrelendiğini ve gırtlak haritasının kilitlendiğini asil bir dille bildir."
            else:
                msg = "[SYSTEM EVENT: ENROLLMENT FAILED] Ses izi kaydedilemedi. Yeterince net konuşma verisi yakalanamadı. Kullanıcıya sessiz bir ortamda tekrar denemesini bildir."
            
            if self.session:
                await self.session.send_client_content(turns={"parts": [{"text": msg}]}, turn_complete=True)
        except Exception as e:
            print(f"[JARVIS] ❌ Biyometrik kayıt hatası: {e}")
            self.ui.write_log(f"ERR: Biyometrik kayıt sırasında hata oluştu: {e}")
        finally:
            self._enrollment_mode = False
            self.enrollment_audio_buffer.clear()
            self.ui.add_neural_log("SECURITY", "Master Enrollment Mode Inactive", "#757575")

    async def _tool_network_diagnostics(self, args, loop):
        action = args.get("action", "ping")
        target = args.get("target", "google.com")
        if not target:
            target = "google.com"
            
        self.ui.add_neural_log("NETWORK", f"Diagnosing: {action.upper()}", "#00ccff")
        
        def run_diag():
            import subprocess
            try:
                # Windows commands might have non-utf8 encodings, but text=True usually uses default locale which is fine, 
                # but we will just pass errors='ignore' if we could, but capture_output=True, text=True handles it mostly.
                if action == "ping":
                    res = subprocess.run(["ping", "-n", "4", target], capture_output=True, text=True, errors="replace")
                    return res.stdout
                elif action == "speedtest":
                    res = subprocess.run(["speedtest-cli", "--simple"], capture_output=True, text=True, errors="replace")
                    return res.stdout if res.stdout else "Hız testi başarısız veya speedtest-cli kurulu değil."
                elif action == "dns_flush":
                    subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
                    subprocess.run(["ipconfig", "/renew"], capture_output=True)
                    return "DNS önbelleği başarıyla temizlendi ve IP adresi yenilendi."
                elif action == "traceroute":
                    # Max 15 hops, no DNS resolution (-d)
                    res = subprocess.run(["tracert", "-d", "-h", "15", target], capture_output=True, text=True, errors="replace")
                    return res.stdout
                else:
                    return "Bilinmeyen ağ komutu."
            except Exception as e:
                return f"Ağ tanılama hatası: {e}"

        result = await loop.run_in_executor(None, run_diag)
        return f"Ağ Tanılama ({action}) Sonucu:\n{result}"

    async def _tool_manage_smart_notes(self, args, loop):
        action = args.get("action", "list")
        from core.smart_notes import create_note, search_notes, list_notes, delete_note

        if action == "create":
            content = args.get("content", "")
            cat = args.get("category", "general")
            tags = args.get("tags", [])
            deadline = args.get("deadline", "")
            priority = args.get("priority", "normal")
            
            note_id = await loop.run_in_executor(
                None, lambda: create_note(content, cat, tags, deadline, priority)
            )
            self.ui.add_neural_log("SYSTEM", f"Smart Note Saved: {cat.upper()}", "#00ffcc")
            return f"Not başarıyla eklendi. ID: {note_id}"
            
        elif action == "list":
            notes = await loop.run_in_executor(None, list_notes)
            if not notes:
                return "Henüz hiç akıllı not bulunmuyor."
            
            res = "Mevcut notlar:\n"
            for n in notes:
                res += f"- [{n['id']}] (Kategori: {n.get('metadata',{}).get('category')}) {n.get('body', '')[:50]}...\n"
            return res
            
        elif action == "search":
            q = args.get("content", "")
            cat = args.get("category", "")
            notes = await loop.run_in_executor(None, lambda: search_notes(q, cat))
            
            if not notes:
                return "Arama kriterlerinize uygun not bulunamadı."
                
            res = f"Arama Sonuçları ({len(notes)} adet):\n"
            for n in notes:
                res += f"- [{n['id']}] {n.get('body', '')[:100]}...\n"
            return res
            
        elif action == "delete":
            note_id = args.get("note_id", "")
            if not note_id:
                return "Silinecek notun ID'si belirtilmeli."
            success = await loop.run_in_executor(None, lambda: delete_note(note_id))
            if success:
                self.ui.add_neural_log("SYSTEM", f"Note Deleted", "#ff3333")
                return f"{note_id} kimlikli not silindi."
            return f"Hata: {note_id} kimlikli not bulunamadı."
            
        return "Bilinmeyen action parametresi."

    async def _tool_save_memory(self, args, loop):
        cat = args.get("category", "notes")
        key = args.get("key", "")
        val = args.get("value", "")
        if key and val:
            update_memory({cat: {key: {"value": val}}})
            print(f"[Memory] 💾 {cat}/{key} = {val}")
        return "ok"

    async def _tool_sleep_jarvis(self, args, loop):
        self.ui.root.after(3000, self.ui.sleep_mode)
        return "Uyku moduna geçiyorum..."

    async def _tool_shutdown_jarvis(self, args, loop):
        self.ui.root.after(3500, self.ui._shutdown)
        return "Sistem tamamen kapatılıyor..."

    async def _tool_power_control(self, args, loop):
        act = args.get("action", "shutdown")
        if act == "lockdown":
            self.ui.add_neural_log("SECURITY", "LOCKDOWN PROTOCOL INITIATED!", "#ff0000")
            os.system("rundll32.exe user32.dll,LockWorkStation")
            os.system('powershell -Command "(New-Object -ComObject Shell.Application).MinimizeAll()"')
            os.system('powershell -Command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys([char]173)"')
            return "Güvenlik protokolü devrede. Sistem kilitlendi, pencereler gizlendi ve ses kapatıldı efendim."
        elif act == "restart":
            self.ui.add_neural_log("SYSTEM", "Initiating Windows Reboot...", "#ff9900")
            self.ui.root.after(4000, lambda: os.system("shutdown /r /t 5"))
            return "Bilgisayar yeniden başlatılıyor efendim. Sistem açıldığında tekrar emrinizde olacağım."
        else:
            self.ui.add_neural_log("SYSTEM", "Initiating Windows Shutdown...", "#ff3333")
            self.ui.root.after(4000, lambda: os.system("shutdown /s /t 5"))
            return "Bilgisayar tamamen kapatılıyor efendim. Görüşmek üzere."

    async def _tool_volume_control(self, args, loop):
        act = args.get("action", "up").lower().strip()
        level = args.get("level")
        
        # Virtual key codes for volume
        VK_VOLUME_MUTE = 0xAD
        VK_VOLUME_DOWN = 0xAE
        VK_VOLUME_UP   = 0xAF
        
        def run_vol():
            if act == "mute" or act == "unmute":
                ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 2, 0)
                return "Sistem sesi kapatıldı veya tekrar açıldı."
            elif act == "up":
                # Press volume up 5 times (increases by 10%)
                for _ in range(5):
                    ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 2, 0)
                return "Sistem sesi artırıldı."
            elif act == "down":
                # Press volume down 5 times (decreases by 10%)
                for _ in range(5):
                    ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 2, 0)
                return "Sistem sesi azaltıldı."
            elif act == "set" and level is not None:
                lvl = max(0, min(100, int(level)))
                # Zero out the volume by sending 50 down presses
                for _ in range(50):
                    ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 2, 0)
                # Set desired volume (level // 2 presses)
                for _ in range(lvl // 2):
                    ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 2, 0)
                return f"Sistem sesi %{lvl} seviyesine ayarlandı."
            return "Geçersiz ses kontrol parametresi."

        r = await loop.run_in_executor(None, run_vol)
        self.ui.add_neural_log("SYSTEM", f"Volume Control: {act.upper()}", "#00ffcc")
        return r

    async def _tool_brightness_control(self, args, loop):
        act = args.get("action", "up").lower().strip()
        level = args.get("level")
        
        # WMI commands run via PowerShell to set/change brightness (robust for multi-monitor / laptops)
        def run_bright():
            try:
                if act == "set" and level is not None:
                    lvl = max(0, min(100, int(level)))
                    cmd = f"Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods | ForEach-Object {{ try {{ $_.WmiSetBrightness(1, {lvl}) }} catch {{}} }}"
                    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], capture_output=True)
                    return f"Ekran parlaklığı %{lvl} seviyesine ayarlandı."
                else:
                    # Get current brightness, safely handling list if multiple monitors exist
                    cmd_get = "$b = Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness | ForEach-Object { $_.CurrentBrightness }; if ($b -is [array]) { $b[0] } else { $b }"
                    res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd_get], capture_output=True, text=True)
                    curr_str = res.stdout.strip()
                    curr = int(curr_str) if curr_str and curr_str.isdigit() else 50
                    
                    if act == "up":
                        target = min(100, curr + 10)
                        msg = "Ekran parlaklığı artırıldı."
                    else:
                        target = max(0, curr - 10)
                        msg = "Ekran parlaklığı azaltıldı."
                        
                    cmd_set = f"Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods | ForEach-Object {{ try {{ $_.WmiSetBrightness(1, {target}) }} catch {{}} }}"
                    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd_set], capture_output=True)
                    return f"{msg} (Laptop ekranı seviyesi: %{target})"
            except Exception as e:
                return f"Ekran parlaklığı ayarlanamadı: {e}. Bu özellik yalnızca WMI destekli ekranlarda/dizüstü bilgisayarlarda çalışır."

        r = await loop.run_in_executor(None, run_bright)
        self.ui.add_neural_log("SYSTEM", f"Brightness Control: {act.upper()}", "#00ffcc")
        return r

    async def _tool_media_playback_control(self, args, loop):
        act = args.get("action", "play").lower().strip()
        
        # Virtual key codes for media control
        VK_MEDIA_NEXT_TRACK = 0xB0
        VK_MEDIA_PREV_TRACK = 0xB1
        VK_MEDIA_STOP       = 0xB2
        VK_MEDIA_PLAY_PAUSE = 0xB3
        
        def run_media():
            if act in {"play", "pause"}:
                ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 2, 0)
                return "Medya oynatması duraklatıldı veya başlatıldı."
            elif act == "next":
                ctypes.windll.user32.keybd_event(VK_MEDIA_NEXT_TRACK, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_MEDIA_NEXT_TRACK, 0, 2, 0)
                return "Bir sonraki medyaya geçildi."
            elif act == "prev":
                ctypes.windll.user32.keybd_event(VK_MEDIA_PREV_TRACK, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_MEDIA_PREV_TRACK, 0, 2, 0)
                return "Bir önceki medyaya geçildi."
            elif act == "stop":
                ctypes.windll.user32.keybd_event(VK_MEDIA_STOP, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_MEDIA_STOP, 0, 2, 0)
                return "Medya oynatması tamamen durduruldu."
            return "Geçersiz medya kontrol parametresi."

        r = await loop.run_in_executor(None, run_media)
        self.ui.add_neural_log("SYSTEM", f"Media Playback: {act.upper()}", "#00ffcc")
        return r

    async def _tool_power_profile_control(self, args, loop):
        profile_type = args.get("profile", "balanced").lower().strip()
        
        # Kelime eşleştirme eşikleri (Fuzzy Match Keywords)
        keywords = {
            "high": ["yüksek", "perform", "high", "nihai", "ultimate", "game", "oyun"],
            "save": ["tasarruf", "save", "low", "pil", "battery"],
            "balanced": ["dengeli", "balanced", "normal", "standart"]
        }
        
        # Statik Fallback GUID'leri (Eğer dinamik eşleştirme başarısız olursa)
        static_guids = {
            "high": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
            "save": "a1841308-3541-4fab-bc81-f71556f20b4a",
            "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e"
        }

        def run_power():
            try:
                # 1. Aşama: Sistemdeki tüm planları listele
                res = subprocess.run(["powercfg", "/list"], capture_output=True, text=True)
                lines = res.stdout.splitlines()
                
                # 2. Aşama: Kullanıcının talebiyle uyuşan anahtar kelimeleri belirle
                target_words = keywords.get(profile_type, keywords["balanced"])
                
                # 3. Aşama: Eşleşen satırı bul ve GUID'yi çek
                matched_guid = None
                for line in lines:
                    if any(word in line.lower() for word in target_words):
                        # Satırdan GUID'yi bul (36 karakterli standart ID)
                        import re
                        match = re.search(r"GUID:\s*([a-f0-9\-]+)", line, re.I)
                        if match:
                            matched_guid = match.group(1)
                            break
                
                # Eğer dinamik olarak bulunamadıysa statik varsayılana düş
                if not matched_guid:
                    matched_guid = static_guids.get(profile_type, static_guids["balanced"])
                
                # 4. Aşama: Güç profilini etkinleştir
                subprocess.run(["powercfg", "/setactive", matched_guid], capture_output=True)
                
                # Onay mesajı hazırla
                names = {"high": "Yüksek Performans", "save": "Güç Tasarrufu", "balanced": "Dengeli"}
                return f"Güç modu başarıyla '{names.get(profile_type, 'Dengeli')}' olarak optimize edildi efendim."
                
            except Exception as e:
                return f"Güç planı değiştirilemedi: {e}"

        r = await loop.run_in_executor(None, run_power)
        self.ui.add_neural_log("SYSTEM", f"Power Profile: {profile_type.upper()}", "#00ffcc")
        return r

    async def _tool_wallpaper_control(self, args, loop):
        query = args.get("query", "nature").lower().strip()
        
        # Curated collection of high-resolution outstanding wallpapers (direct CDN hotlinks)
        wallpapers = {
            "trabzonspor": "https://i.postimg.cc/QdjP0zQ8/trabzonspor-hd.jpg",
            "cyberpunk": "https://images.unsplash.com/photo-1578894381163-e72c17f2d45f?q=80&w=1920",
            "neon": "https://images.unsplash.com/photo-1578894381163-e72c17f2d45f?q=80&w=1920",
            "space": "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?q=80&w=1920",
            "galaxy": "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?q=80&w=1920",
            "cosmos": "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?q=80&w=1920",
            "nature": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1920",
            "beach": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1920",
            "landscape": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1920",
            "cars": "https://images.unsplash.com/photo-1617814076367-b759c7d7e738?q=80&w=1920",
            "car": "https://images.unsplash.com/photo-1617814076367-b759c7d7e738?q=80&w=1920",
            "anime": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?q=80&w=1920",
            "art": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?q=80&w=1920",
            "minimalist": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1920"
        }

        def run_wallpaper():
            try:
                import requests
                # Match query
                matched_url = None
                for k, v in wallpapers.items():
                    if k in query:
                        matched_url = v
                        break
                
                # Fallback to standard Picsum Photos (which dynamically serves a beautiful, high-res photograph)
                if not matched_url:
                    matched_url = "https://picsum.photos/1920/1080"
                
                # Fetch image data
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                r = requests.get(matched_url, headers=headers, timeout=10, allow_redirects=True)
                if r.status_code == 200:
                    filepath = os.path.join(tempfile.gettempdir(), "jarvis_wallpaper.jpg")
                    with open(filepath, "wb") as f:
                        f.write(r.content)
                    
                    # Call Windows API to apply wallpaper (20 = SPI_SETDESKWALLPAPER, 3 = SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)
                    ctypes.windll.user32.SystemParametersInfoW(20, 0, filepath, 3)
                    
                    category_name = query.upper()
                    if not any(k in query for k in wallpapers.keys()):
                        category_name = "RANDOM"
                    return f"Masaüstü duvar kağıdı başarıyla '{category_name}' temasıyla güncellendi efendim."
                else:
                    return f"Duvar kağıdı resmi indirilemedi (Hata kodu: {r.status_code})."
            except Exception as e:
                return f"Duvar kağıdı değiştirilirken bir hata oluştu: {e}"

        r = await loop.run_in_executor(None, run_wallpaper)
        self.ui.add_neural_log("SYSTEM", "Wallpaper Updated", "#00ffcc")
        return r

    async def _tool_news_intelligence(self, args, loop):
        act = args.get("action", "summary")
        if act == "detail":
            nid = args.get("news_id", "")
            detail = get_news_detail(nid)
            if "error" in detail:
                return detail["error"]
            else:
                self.ui.add_neural_log("INTELLIGENCE", f"Deep Dive: {detail['title'][:30]}...", "#00ffcc")
                return f"Haber Detayı ({detail['source']}):\nBaşlık: {detail['title']}\nLink: {detail['link']}\n\nİçerik: {detail['content']}"
        else:
            cat = args.get("category", "ai")
            items = fetch_news_summary(cat)
            self.ui.add_neural_log("INTELLIGENCE", f"Fetched {len(items)} {cat.upper()} News Items.", "#00ffff")
            if not items:
                return f"{cat.upper()} kategorisinde güncel haber bulunamadı."
            else:
                lines = [f"İşte {cat.upper()} kategorisindeki en güncel haberler:"]
                for idx, item in enumerate(items[:5], 1):
                    lines.append(f"{idx}. {item['title']} - {item['summary']} (Kaynak: {item['source']}) [ID: {item['id']}]")
                return "\n\n".join(lines)

    async def _tool_cinema_intelligence(self, args, loop):
        act = args.get("action", "recommend")
        if act == "tracker_save":
            iname = args.get("item_name", "")
            itype = args.get("item_type", "movie")
            einfo = args.get("episode_info", "İzlenecek")
            res = save_tracker_item(iname, itype, einfo)
            self.ui.add_neural_log("CINEMA", f"Tracker: {iname} ({itype}) -> {einfo}", "#ff007f")
            return res
        elif act == "tracker_get":
            self.ui.add_neural_log("CINEMA", "Tracker list formatted.", "#ff007f")
            return format_tracker_list()
        elif act == "radar":
            radar = get_cinema_radar()
            self.ui.add_neural_log("CINEMA", f"Radar: {len(radar)} news items.", "#ff007f")
            if not radar:
                return "Platformlardan yeni haber alınamadı."
            else:
                lines = ["Platformlarda ve sinema dünyasında bu hafta öne çıkanlar:"]
                for idx, item in enumerate(radar[:5], 1):
                    lines.append(f"{idx}. {item['title']} - {item['summary']} ({item['source']})")
                return "\n\n".join(lines)
        else:
            query = args.get("query", "film önerisi")
            self.ui.add_neural_log("CINEMA", f"Recommend: {query}", "#ff007f")
            return f"Kullanıcı '{query}' için film/dizi tavsiyesi istiyor. Lütfen en kaliteli 3 yapımı IMDb puanı, süresi ve platform bilgisiyle (Netflix, Prime vb.) samimi bir dille öner."

    async def _tool_delete_memory(self, args, loop):
        return delete_memory(
            args.get("category", ""),
            args.get("key", ""),
            args.get("match_text", ""),
        )

    async def _tool_toggle_english_tutor(self, args, loop):
        enabled = bool(args.get("enabled", False))
        self.english_tutor_mode = enabled
        self.ui.english_tutor_mode = enabled
        if enabled:
            self.ui.show_notification("LANGUAGE TUTOR MODE: ONLINE", "info")
            return "English Tutor Mode is now ON. You should now speak English."
        else:
            self.ui.show_notification("LANGUAGE TUTOR MODE: OFFLINE", "info")
            return "English Tutor Mode is now OFF. You can speak Turkish again."

    async def _tool_update_tutor_stats(self, args, loop):
        self.ui.english_tutor_stats["last_correction"] = args.get("last_correction", self.ui.english_tutor_stats["last_correction"])
        self.ui.english_tutor_stats["fluency"] = args.get("fluency", self.ui.english_tutor_stats["fluency"])
        new_w = args.get("new_word", "")
        if new_w:
            self.ui.english_tutor_stats["new_words"].appendleft(new_w)
        return "ok"

    async def _tool_open_app(self, args, loop):
        r = await loop.run_in_executor(
            None, lambda: open_app(args.get("app_name", "")))
        return r or f"{args.get('app_name')} açıldı."

    async def _tool_close_app(self, args, loop):
        r = await loop.run_in_executor(
            None, lambda: close_app(args.get("app_name", "")))
        return r or f"{args.get('app_name')} kapatıldı."

    async def _tool_sys_info(self, args, loop):
        self._focus_ui_section_for_tool("sys_info", args)
        r = await loop.run_in_executor(
            None, lambda: sys_info(args.get("query", "all")))
        return r or "Bilgi alındı."

    async def _tool_get_weather(self, args, loop):
        self._focus_ui_section_for_tool("get_weather", args)
        r = await loop.run_in_executor(
            None, lambda: get_weather_summary(args.get("location") or None))
        return r or "Hava durumu bilgisi alindi."

    async def _tool_get_market_data(self, args, loop):
        self._focus_ui_section_for_tool("get_market_data", args)
        sym = args.get("symbol", "").strip()
        if sym:
            r = await loop.run_in_executor(None, lambda: query_specific_asset(sym))
            return r or f"{sym} bilgisi alındı."
        else:
            r = await loop.run_in_executor(None, lambda: get_live_market_summary())
            if isinstance(r, dict):
                summary_parts = []
                for k, v in r.items():
                    summary_parts.append(f"{v['name']}: {v['price']} ({v['change_pct']:.1f}%)")
                self.ui.root.after(0, lambda: setattr(self.ui, '_market_data', r))
                return "Güncel piyasa durumu: " + ", ".join(summary_parts) + ". Lütfen bunu profesyonel bir finans danışmanı edasıyla özetle."
            else:
                return "Piyasa verisi alınamadı."

    async def _tool_get_calendar_events(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: get_calendar_events(
                args.get("query", "today"),
                int(args.get("limit", 6) or 6),
            ),
        )
        return r or "Takvim bilgisi alindi."

    async def _tool_add_calendar_event(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: add_calendar_event(
                args.get("title", ""),
                args.get("start_iso", ""),
                args.get("end_iso", ""),
                args.get("notes", ""),
                args.get("location", ""),
                args.get("calendar_name", ""),
                bool(args.get("all_day", False)),
            ),
        )
        return r or "Takvim etkinligi eklendi."

    async def _tool_delete_calendar_event(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: delete_calendar_event(
                args.get("title", ""),
                args.get("start_iso", ""),
                args.get("calendar_name", ""),
                bool(args.get("delete_all_matches", False)),
            ),
        )
        return r or "Takvim etkinligi silindi."

    async def _tool_get_reminders(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: get_reminders(
                args.get("query", "upcoming"),
                int(args.get("limit", 8) or 8),
                args.get("list_name", ""),
            ),
        )
        return r or "Animsatici bilgisi alindi."

    async def _tool_add_reminder(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: add_reminder(
                args.get("title", ""),
                args.get("due_iso", ""),
                args.get("notes", ""),
                args.get("list_name", ""),
                args.get("priority", ""),
                bool(args.get("all_day", False)),
            ),
        )
        return r or "Animsatici eklendi."

    async def _tool_delete_reminder(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: delete_reminder(args.get("title", "")),
        )
        return r or "Anımsatıcı silindi."

    async def _tool_browser_control(self, args, loop):
        r = await loop.run_in_executor(
            None, lambda: browser_control(
                args.get("action"),
                args.get("url"),
                args.get("query")
            ))
        return r or "Tamam."

    async def _tool_shell_run(self, args, loop):
        r = await loop.run_in_executor(
            None, lambda: shell_run(args.get("command", "")))
        return r or "Komut çalıştırıldı."

    async def _tool_play_media(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: play_media(
                args.get("query", ""),
                args.get("provider", "auto"),
                bool(args.get("autoplay", True)),
            ),
        )
        return r or "Medya oynatma başlatıldı."

    async def _tool_get_youtube_channel_report(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: get_youtube_channel_report(
                args.get("query", "overview"),
                args.get("handle", ""),
                int(args.get("video_limit", 6) or 6),
            ),
        )
        return r or "YouTube kanal raporu alindi."

    async def _tool_read_clipboard(self, args, loop):
        try:
            clip_text = pyperclip.paste()
            if clip_text:
                return f"Panodaki metin:\n{clip_text}"
            else:
                return "Pano şu an boş veya metin içermiyor."
        except Exception:
            try:
                clip_text = self.ui.root.clipboard_get()
                return f"Panodaki metin:\n{clip_text}"
            except Exception:
                return "Panoya erişilemedi."

    async def _tool_optimize_system(self, args, loop):
        def do_optimize():
            try:
                try:
                    ctypes.windll.psapi.EmptyWorkingSet(-1)
                except Exception:
                    pass
                
                temp_dir = tempfile.gettempdir()
                cleaned = 0
                for f_name in os.listdir(temp_dir):
                    f_path = os.path.join(temp_dir, f_name)
                    try:
                        if os.path.isfile(f_path):
                            os.remove(f_path)
                            cleaned += 1
                    except Exception:
                        pass
                return f"Sistem optimize edildi. RAM arka plan bellek blokları boşaltıldı ve {cleaned} adet geçici (temp) dosya başarıyla temizlendi."
            except Exception as e:
                return f"Optimizasyon tamamlanamadı: {e}"

        return await loop.run_in_executor(None, do_optimize)

    async def _tool_analyze_screen(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: analyze_screen(
                args.get("query", "Ekranda ne var?"),
                args.get("target", "active_window"),
            ),
        )
        return r or "Ekran analizi tamamlandi."

    async def _tool_send_whatsapp_message(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: send_whatsapp_message(
                args.get("message", ""),
                args.get("phone_number", ""),
                args.get("recipient_name", ""),
                bool(args.get("send_now", False)),
                args.get("app_target", "auto"),
            ),
        )
        return r or "WhatsApp işlemi tamamlandı."

    async def _tool_save_whatsapp_contact(self, args, loop):
        r = await loop.run_in_executor(
            None,
            lambda: save_whatsapp_contact(
                args.get("display_name", ""),
                args.get("phone_number", ""),
                args.get("aliases", ""),
            ),
        )
        return r or "WhatsApp kişisi kaydedildi."

    # ── Core Dispatcher ───────────────────────────────────────────────────────
    async def _biometric_check(self, name: str) -> tuple[bool, str]:
        """
        Kısıtlı araç çağrısından önce ses doğrulaması yapar.
        ŞU AN ASKIYA ALINDI: Kullanıcı isteği üzerine her zaman True döner.
        """
        self.ui.add_neural_log("SECURITY", f"Biometrics Suspended — {name} bypassed", "#757575")
        return True, "ok"

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})
        print(f"[JARVIS] 🔧 {name} {args}")
        self.ui.set_state("THINKING")

        loop   = asyncio.get_event_loop()
        result = "Tamam."
        had_exception = False

        try:
            # --- Kısıtlı araç ses doğrulaması ---
            authorized = True
            msg = ""
            if name in RESTRICTED_TOOLS:
                authorized, msg = await self._biometric_check(name)

            if not authorized:
                result = msg
            else:
                # Dynamic Dispatch pattern
                handler = getattr(self, f"_tool_{name}", None)
                if handler:
                    result = await handler(args, loop)
                else:
                    result = f"Bilinmeyen araç: {name}"

        except Exception as e:
            result = f"Hata: {e}"
            had_exception = True
            traceback.print_exc()
            self.speak_error(name, e)

        tool_failed = self._result_looks_like_error(result)
        if tool_failed:
            if not had_exception:
                self.ui.set_state("ERROR")
        elif self._should_play_success_sfx(name, args, result):
            self.ui.play_success_sfx()

        if not tool_failed and not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mikrofon başladı")
        while True:
            try:
                stream = await asyncio.to_thread(
                    pya.open,
                    format=FORMAT, channels=CHANNELS,
                    rate=SEND_SAMPLE_RATE, input=True,
                    frames_per_buffer=CHUNK_SIZE,
                )
                try:
                    while True:
                        data = await asyncio.to_thread(
                            stream.read, CHUNK_SIZE, exception_on_overflow=False)
                        
                        with self._speaking_lock:
                            jarvis_speaking = self._is_speaking
                            
                        if getattr(self, "_enrollment_mode", False):
                            self.enrollment_audio_buffer.append(data)
                            self.recent_audio_buffer.append(data)
                        else:
                            if not jarvis_speaking:
                                # Biometrics için sadece asistan suskunken gelen insan sesini hafızada tut
                                self.recent_audio_buffer.append(data)
                                
                            if getattr(self.ui, "_jarvis_state", "") == "LISTENING" and not self.ui.muted and not self._paused:
                                await self.out_queue.put({"data": data, "mime_type": f"audio/pcm;rate={SEND_SAMPLE_RATE}"})
                except Exception as e:
                    print(f"[JARVIS] ⚠️ Mikrofon akışı kesildi (Yeniden bağlanılıyor): {e}")
                finally:
                    stream.close()
            except Exception as e:
                print(f"[JARVIS] ⚠️ Mikrofon cihazına erişilemiyor (2 saniyede bir tekrar denenecek): {e}")
            
            await asyncio.sleep(2)

    async def _receive_audio(self):
        print("[JARVIS] 👂 Alım başladı")
        out_buf, in_buf = [], []
        output_noise = False
        output_noise_samples = []
        received_audio_chunks = 0
        try:
            while True:
                async for response in self.session.receive():
                    if response.data:
                        self.audio_in_queue.put_nowait(response.data)
                        received_audio_chunks += 1

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            self.set_speaking(True)
                            raw_txt = sc.output_transcription.text
                            if raw_txt:
                                txt, had_noise = self._clean_transcript_text(raw_txt)
                                if had_noise:
                                    output_noise = True
                                    if len(output_noise_samples) < 4:
                                        output_noise_samples.append(raw_txt)
                                if txt:
                                    out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text
                            if txt:
                                in_buf.append(txt)
                                self.ui.mark_user_activity(True)

                        if sc.turn_complete:
                            self.audio_in_queue.put_nowait(None)

                            full_in = "".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"Siz: {full_in}")
                                self.last_user_transcripts.append(full_in)
                            in_buf = []

                            full_out = "".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"JARVIS: {full_out}")
                                if output_noise_samples:
                                    self.ui.write_debug(
                                        "Kısmen filtrelenen ses transcripti: " + " | ".join(output_noise_samples),
                                        level="WARN",
                                    )
                            elif received_audio_chunks > 0:
                                self.ui.write_log("JARVIS: [Sesli Yanıt]")
                            elif output_noise:
                                self.ui.add_neural_log("CORE", "Model control tokens filtered.", "#757575")
                                
                            out_buf = []
                            output_noise = False
                            output_noise_samples = []
                            received_audio_chunks = 0


                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] 📞 {fc.name}")
                            self.ui.add_neural_log("TOOL_EXE", f"Executing {fc.name}...", "#829594")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses)

        except Exception as e:
            print(f"[JARVIS] ❌ Alım: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] 🔊 Ses çalma başladı")
        
        def open_stream():
            return pya.open(
                format=FORMAT, channels=CHANNELS,
                rate=RECV_SAMPLE_RATE, output=True,
            )
            
        stream = await asyncio.to_thread(open_stream)
        try:
            while True:
                chunk = await self.audio_in_queue.get()
                if chunk is None:
                    self.set_speaking(False)
                    continue
                    
                self.set_speaking(True)
                try:
                    await asyncio.to_thread(stream.write, chunk, exception_on_underflow=False)
                except Exception as e:
                    print(f"[JARVIS] ⚠️ Ses Çalma Hatası (Yeniden bağlanıyor...): {e}")
                    try:
                        stream.close()
                    except:
                        pass
                    stream = await asyncio.to_thread(open_stream)
                if self.audio_in_queue.empty():
                    self.set_speaking(False)
                    
        except Exception as e:
            print(f"[JARVIS] ❌ Ses Döngüsü Çöktü: {e}")
            raise
        finally:
            self.set_speaking(False)
            try:
                stream.close()
            except:
                pass

    async def _system_monitor_loop(self):
        print("[JARVIS] 👁️ Sistem Monitörü başladı")
        
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
            
        def get_idle_time():
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
                return millis / 1000.0
            return 0

        last_ram_warn = 0
        last_cpu_warn = 0
        last_battery_warn = 0
        
        was_idle = False
        
        # Focus mode tracking
        focus_app_target = ("visual studio code", "cursor", "pycharm", "intellij", "webstorm")
        focus_streak_seconds = 0
        last_focus_warn = 0
        
        while True:
            await asyncio.sleep(20)
            if not self.session or self._paused:
                continue
                
            now = time.time()
            
            # --- 1. RAM Monitor ---
            try:
                mem = psutil.virtual_memory()
                if mem.percent > 90 and (now - last_ram_warn > 1800): # 30 min cooldown
                    last_ram_warn = now
                    msg = f"[SYSTEM EVENT: CRITICAL RAM WARNING] Kullanıcının RAM kullanımı %{mem.percent} seviyesinde. Kullanıcıya sesli olarak sistem belleğinin sınırda olduğunu ve arka planda gereksiz önbelleği temizlememi isteyip istemediğini sor."
                    await self.session.send_client_content(turns={"parts": [{"text": msg}]}, turn_complete=True)
            except Exception:
                pass
                
            # --- 2. CPU Monitor ---
            try:
                cpu = await asyncio.to_thread(psutil.cpu_percent, interval=0.1)
                if cpu > 95 and (now - last_cpu_warn > 1800):
                    last_cpu_warn = now
                    msg = f"[SYSTEM EVENT: CRITICAL CPU WARNING] Kullanıcının CPU kullanımı %{cpu} seviyesine ulaştı. Sistemin yorulduğunu belirterek uyar."
                    await self.session.send_client_content(turns={"parts": [{"text": msg}]}, turn_complete=True)
            except Exception:
                pass
                
            # --- 3. Battery Monitor ---
            try:
                bat = psutil.sensors_battery()
                if bat and not bat.power_plugged and bat.percent < 20 and (now - last_battery_warn > 1800):
                    last_battery_warn = now
                    msg = f"[SYSTEM EVENT: BATTERY LOW] Laptop pili %{bat.percent} seviyesine düştü. Kullanıcıyı sesli uyar ve güç tasarrufu modu için onay iste."
                    await self.session.send_client_content(turns={"parts": [{"text": msg}]}, turn_complete=True)
            except Exception:
                pass
                
            # --- 4. Idle System Maintenance ---
            try:
                idle_sec = get_idle_time()
                if idle_sec > 900: # 15 minutes
                    if not was_idle:
                        was_idle = True
                        self.ui.add_neural_log("SYSTEM", "User AFK > 15m. Optimizing...", "#a1997e") # C_GOLD
                        try:
                            ctypes.windll.psapi.EmptyWorkingSet(-1)
                            self.ui.add_neural_log("SYSTEM", "RAM Trim successful.", "#85a393") # C_GREEN
                        except Exception:
                            pass
                else:
                    if was_idle:
                        was_idle = False
                        self.ui.add_neural_log("SYSTEM", "User returned. Resuming active state.", "#85a393")
                        msg = f"[SYSTEM EVENT: USER RETURNED] Kullanıcı 15 dakikadan uzun bir süre AFK kaldıktan sonra bilgisayarın başına geri döndü. Sadece çok kısa bir şekilde 'Hoş geldiniz efendim, siz yokken sistemin bellek önbelleklerini temizleyip optimize ettim.' diyerek karşıla."
                        await self.session.send_client_content(turns={"parts": [{"text": msg}]}, turn_complete=True)
            except Exception:
                pass

            # --- 5. Focus Mode (Pomodoro) ---
            try:
                active_win = get_foreground_window_title().lower()
                is_coding = any(app in active_win for app in focus_app_target)
                
                if is_coding and not was_idle:
                    focus_streak_seconds += 20
                else:
                    # Sadece 5 dakika (300sn) aktif pencere değişirse odak sıfırlanır
                    # Şimdilik basit tutuyoruz, kodlamadan çıkarsa streak'i yavaş yavaş azalt
                    focus_streak_seconds = max(0, focus_streak_seconds - 20)
                    
                # 7200 seconds = 2 hours
                if focus_streak_seconds > 7200 and (now - last_focus_warn > 3600):
                    last_focus_warn = now
                    msg = f"[SYSTEM EVENT: FOCUS ALERT] Kullanıcı 2 saatten uzun süredir aralıksız IDE ({active_win}) üzerinde kod yazıyor/çalışıyor. Gözlerini dinlendirmesi için çok kibar ve kısa bir mola tavsiyesi yap."
                    await self.session.send_client_content(turns={"parts": [{"text": msg}]}, turn_complete=True)
            except Exception:
                pass

    async def run(self):
        client = genai.Client(
            api_key=get_api_key(),
            http_options={"api_version": "v1alpha"}
        )

        backoff_delay = 3
        while True:
            # Duraklatılmışsa bağlanma, bekle
            if self._paused:
                await asyncio.sleep(1)
                continue

            try:
                print("[JARVIS] 🔌 Bağlanıyor...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue()

                    print("[JARVIS] ✅ Bağlandı.")
                    backoff_delay = 3  # Reset backoff on successful connection
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS hazır. Dinliyorum...")

                    if not self._has_greeted:
                        self._has_greeted = True
                        
                        if getattr(self.ui, "_is_home_setup", True):
                            try:
                                import time
                                today_str = time.strftime("%Y-%m-%d")
                                boot_record_path = os.path.join(tempfile.gettempdir(), "jarvis_last_greeting_date.txt")
                                last_greeting_date = ""
                                if os.path.exists(boot_record_path):
                                    with open(boot_record_path, "r") as f:
                                        last_greeting_date = f.read().strip()
                                        
                                is_first_boot_run = (today_str != last_greeting_date)
                                if is_first_boot_run:
                                    with open(boot_record_path, "w") as f:
                                        f.write(today_str)
                            except Exception:
                                is_first_boot_run = True
                                
                            if is_first_boot_run:
                                temp = self.ui._weather_card.get("temp", "Bilinmiyor")
                                cond = self.ui._weather_card.get("condition", "Bilinmiyor")
                                weather_info = f"{temp} ve {cond}" if temp != "Bilinmiyor" else "henüz alınamadı"
                                
                                cal_info = get_calendar_events("today", limit=5)
                                rem_info = get_reminders("today", limit=5)
                                
                                greeting_msg = (
                                    f"[SYSTEM EVENT: PROACTIVE STARTUP] "
                                    f"Kullanıcı bilgisayarı yeni açtı. Şu anki hava durumu: {weather_info}. "
                                    f"Bugünkü takvim etkinlikleri: {cal_info}. "
                                    f"Bugünkü anımsatıcılar: {rem_info}. "
                                    f"Lütfen bu bilgileri harmanlayarak son derece otonom, elit ve J.A.R.V.I.S. tarzı enerjik bir karşılama yap. "
                                    f"Örnek format: 'Günaydın efendim. Bugün takviminizde 2 toplantı var. Dünün açık kalan kodları masaüstünde. Kahve eşliğinde çalışmaya başlayalım mı?' "
                                    f"UYARI: Uygulamaları (VS Code vs.) kullanıcının isteği olmadan ASLA kendi kendine açma, sadece benden bir isteğiniz var mı diye sor. "
                                    f"Doğrudan sesli yanıt ver."
                                )
                            else:
                                greeting_msg = (
                                    f"[SYSTEM EVENT: SESSION REOPEN] "
                                    f"Kullanıcı asistanı gün içinde tekrar açtı. "
                                    f"Hava durumu veya takvim gibi uzun sabah özetlerinden KESİNLİKLE bahsetme. "
                                    f"Sadece çok kısa, elit ve karizmatik bir şekilde tekrar hoş geldin de ve komut beklediğini belirt. "
                                    f"Örnek: 'Tekrar hoş geldiniz efendim. Sistem hazır.' veya 'Sistem aktif efendim, nasıl yardımcı olabilirim?'"
                                )
                                
                            fut = asyncio.run_coroutine_threadsafe(
                                self.session.send_client_content(
                                    turns={"parts": [{"text": greeting_msg}]},
                                    turn_complete=True
                                ),
                                self._loop
                            )
                            self._register_future(fut, "Karşılama mesajı gönderimi")
                        else:
                            print("[JARVIS] 🔋 Mobil/Dış ortam tespiti: Karşılama sessize alındı, uyku modunda dinleniyor...")

                    tasks = [
                        asyncio.create_task(self._send_realtime()),
                        asyncio.create_task(self._listen_audio()),
                        asyncio.create_task(self._receive_audio()),
                        asyncio.create_task(self._play_audio()),
                        asyncio.create_task(self._system_monitor_loop())
                    ]

                    try:
                        await asyncio.gather(*tasks)
                    except Exception:
                        raise
                    finally:
                        for t in tasks:
                            t.cancel()

            except Exception as e:
                print(f"[JARVIS] ⚠️ {e}")
                traceback.print_exc()
                self.set_speaking(False)
                self.ui.write_log(f"ERR: JARVIS baglantisi kesildi — {e}")
                self.ui.set_state("ERROR")
                print(f"[JARVIS] 🔄 {backoff_delay} saniyede yeniden bağlanıyor...")
                await asyncio.sleep(backoff_delay)
                backoff_delay = min(30, backoff_delay * 2)  # Exponential backoff up to 30s


def main():
    if os.environ.get("TERM_PROGRAM") == "vscode":
        print("[JARVIS] VS Code icinden baslatildi.")

    start_hidden = "--hidden" in sys.argv
    ui = JarvisUI(start_hidden=start_hidden)

    wake_word = WakeWordListener(on_wake=ui.wake_up)
    wake_word.start()

    def terminal_kbd_listener():
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                cmd = line.strip().lower()
                if cmd in ("jarvis", "uyan", "wake", "open", "j"):
                    print("[JARVIS] ⌨️ Terminal komutu alındı: Sistem uyandırılıyor...")
                    ui.wake_up()
            except Exception:
                time.sleep(1)

    threading.Thread(target=terminal_kbd_listener, daemon=True).start()

    def runner():
        ui.wait_for_api_key()
        if wake_word and not getattr(ui, "paused", False):
            wake_word.pause_listening()
        jarvis = JarvisLive(ui, wake_word=wake_word)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\n🔴 Kapatılıyor...")
        finally:
            wake_word.stop()

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()



"""
JARVIS Windows - UI v3
Concentric teal rings · Segmented arcs
"""

import os, time, math, random, signal, threading
import subprocess
import tkinter as tk
import tkinter.font as tkFont
from collections import deque
from pathlib import Path
import psutil
from PIL import Image, ImageTk

from app_config import has_gemini_api_key, load_app_config, save_app_config
from actions.weather import get_weather_data, get_weather_summary
from actions.windows_utils import open_url

try:
    import win32api
    HAS_WIN32 = True
except Exception:
    HAS_WIN32 = False

BASE_DIR = Path(__file__).resolve().parent

SYSTEM_NAME = "J.A.R.V.I.S"
MODEL_BADGE = "VOICE CORE · Windows"

# ── Renk paleti ──────────────────────────────────────────────────────────────
C_BG      = "#020810"
C_PRI     = "#2196f3"
C_ORG     = "#ff6600"
C_ORG2    = "#ff9900"
C_MID     = "#0d47a1"
C_DIM     = "#0a2a4a"
C_DIMMER  = "#040f1c"
C_TEXT    = "#90caf9"
C_PANEL   = "#040f1c"
C_GREEN   = "#00ff88"
C_RED     = "#ff3344"
C_MUTED   = "#cc2255"
C_BLUE    = "#4488ff"
C_GOLD    = "#ffcc00"

# Orb durum renkleri
ORB_COLORS = {
    "LISTENING":    (0, 255, 136),
    "SPEAKING":     (33, 150, 243),
    "THINKING":     (255, 213, 79),
    "MUTED":        (200, 30, 80),
    "PAUSED":       (30, 60, 55),
    "ERROR":        (255, 51, 68),
    "INITIALISING": (255, 51, 68),
}

THEMES = {
    "ELECTRIC BLUE (Varsayılan)": {
        "C_BG": "#020810",
        "C_PRI": "#2196f3",
        "C_ORG": "#ff6600",
        "C_ORG2": "#ff9900",
        "C_MID": "#0d47a1",
        "C_DIM": "#0a2a4a",
        "C_DIMMER": "#040f1c",
        "C_TEXT": "#90caf9",
        "C_PANEL": "#040f1c",
        "C_GREEN": "#00ff88",
        "C_RED": "#ff3344",
        "C_GOLD": "#ffcc00",
        "ORB_LISTENING": (0, 255, 136),
        "ORB_SPEAKING": (33, 150, 243),
        "ORB_THINKING": (255, 213, 79),
    },
    "EMERALD SENTINEL (Matrix)": {
        "C_BG": "#010c0a",
        "C_PRI": "#00d4c0",
        "C_ORG": "#ff6600",
        "C_ORG2": "#ff9900",
        "C_MID": "#006a62",
        "C_DIM": "#05201c",
        "C_DIMMER": "#021210",
        "C_TEXT": "#7dfff6",
        "C_PANEL": "#021210",
        "C_GREEN": "#00ff88",
        "C_RED": "#ff3344",
        "C_GOLD": "#ffcc00",
        "ORB_LISTENING": (0, 255, 136),
        "ORB_SPEAKING": (0, 212, 192),
        "ORB_THINKING": (255, 213, 79),
    },
    "CRIMSON FIRE (Ateş Paleti)": {
        "C_BG": "#060103",
        "C_PRI": "#ff6b6b",
        "C_ORG": "#ff9f43",
        "C_ORG2": "#ff9f43",
        "C_MID": "#d94b4b",
        "C_DIM": "#5c1d24",
        "C_DIMMER": "#2b0c10",
        "C_TEXT": "#ebd3d3",
        "C_PANEL": "#0d0204",
        "C_GREEN": "#ff9f43",
        "C_RED": "#ff3344",
        "C_GOLD": "#ffcc44",
        "ORB_LISTENING": (255, 159, 67),
        "ORB_SPEAKING": (255, 107, 107),
        "ORB_THINKING": (255, 204, 0),
    }
}

# ── Boyutlar ─────────────────────────────────────────────────────────────────
W_TARGET = 2200
H_TARGET = 1320
LEFT_W_T = 360
RIGHT_W_T = 410
HDR_H    = 72
FOOTER_H = 26
INPUT_H  = 34
CONTROL_H = 146

VOICES = ["Charon", "Puck", "Aoede", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"]

# ── Font sistemi ─────────────────────────────────────────────────────────────
def _resolve_font(preferred, fallbacks):
    try:
        available = tkFont.families()
    except Exception:
        available = []
    for name in [preferred] + fallbacks:
        if name in available:
            return name
    return "TkDefaultFont"

_FONT_FALLBACKS_BODY = ["Segoe UI", "Inter", "Roboto", "Calibri", "Arial"]
_FONT_FALLBACKS_DISPLAY = ["Segoe UI Semibold", "Segoe UI", "Inter", "Roboto", "Calibri", "Arial"]
FONT_BODY_FAMILY = _resolve_font("Grift", _FONT_FALLBACKS_BODY)
FONT_DISPLAY_FAMILY = _resolve_font("Grift Extra Bold", _FONT_FALLBACKS_DISPLAY)


def font_body(size: int):
    return (FONT_BODY_FAMILY, size)


def font_body_bold(size: int):
    return (FONT_BODY_FAMILY, size, "bold")


def font_display(size: int):
    return (FONT_DISPLAY_FAMILY, size)


STATE_HEX_COLORS = {
    "LISTENING": C_GREEN,
    "SPEAKING": C_BLUE,
    "THINKING": C_GOLD,
    "INITIALISING": C_RED,
    "ERROR": C_RED,
}


# ── SoundManager ─────────────────────────────────────────────────────────────
import subprocess as _sp

def _resolve_sfx_dir() -> Path:
    return BASE_DIR / "SFX"


_SFX_DIR = _resolve_sfx_dir()
_HUD_FILE = _SFX_DIR / "HUD.mp3"
_START_FILE = _SFX_DIR / "Start.mp3"
_THINK_FILE = _SFX_DIR / "Think.mp3"
_DONE_FILE = _SFX_DIR / "Done.mp3"
_ERROR_FILE = _SFX_DIR / "Error.mp3"


class SoundManager:
    def __init__(self):
        self._enabled = True
        self._ambient_proc = None
        self._volume = 0.20
        self._ambient_stop = None
        self._ambient_thread = None
        self._foreground_proc = None
        self._foreground_stop = None
        self._foreground_thread = None
        self._foreground_tag = ""
        self._all_sound_procs = set()
        self._lock = threading.RLock()

    @staticmethod
    def _terminate_process(proc):
        if not proc:
            return
        if proc.poll() is not None:
            return
        killed_group = False
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            killed_group = True
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=0.6)
        except Exception:
            try:
                if killed_group:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                else:
                    proc.kill()
                proc.wait(timeout=0.3)
            except Exception:
                pass

    def _cleanup_dead_processes(self):
        with self._lock:
            self._all_sound_procs = {p for p in self._all_sound_procs if p.poll() is None}

    def _start_windows_audio(self, path: Path, volume: float):
        safe_path = str(path).replace("'", "''")
        win_volume = int(max(0.0, min(1.0, volume)) * 100)
        script = (
            "$p = New-Object -ComObject WMPlayer.OCX; "
            f"$p.settings.volume = {win_volume}; "
            f"$p.URL = '{safe_path}'; "
            "$p.controls.play(); "
            "while ($p.playState -ne 1) { Start-Sleep -Milliseconds 120 }; "
            "$p.close()"
        )
        proc = _sp.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
        )
        with self._lock:
            self._cleanup_dead_processes()
            self._all_sound_procs.add(proc)
        return proc

    def _forget_process(self, proc):
        if not proc:
            return
        with self._lock:
            self._cleanup_dead_processes()
            self._all_sound_procs.discard(proc)

    def start_ambient(self):
        if not _HUD_FILE.exists():
            return
        with self._lock:
            if not self._enabled:
                return
            if self._foreground_proc and self._foreground_proc.poll() is None:
                return
            if self._ambient_thread and self._ambient_thread.is_alive():
                return
            stop_event = threading.Event()
            worker = threading.Thread(
                target=self._loop_ambient,
                args=(stop_event,),
                daemon=True,
            )
            self._ambient_stop = stop_event
            self._ambient_thread = worker
        worker.start()

    def _loop_ambient(self, stop_event: threading.Event):
        while not stop_event.is_set():
            with self._lock:
                if not self._enabled or self._ambient_stop is not stop_event:
                    break
                volume = self._volume
            try:
                proc = self._start_windows_audio(_HUD_FILE, volume)
            except Exception:
                break

            with self._lock:
                if self._ambient_stop is not stop_event or not self._enabled:
                    self._terminate_process(proc)
                    self._forget_process(proc)
                    break
                self._ambient_proc = proc

            while proc.poll() is None and not stop_event.wait(0.2):
                pass

            if stop_event.is_set():
                self._terminate_process(proc)

            with self._lock:
                if self._ambient_proc is proc:
                    self._ambient_proc = None
            if proc.poll() is not None:
                self._forget_process(proc)

            if stop_event.is_set():
                break
            time.sleep(0.2)

        with self._lock:
            if self._ambient_stop is stop_event:
                self._ambient_stop = None
            if self._ambient_thread and self._ambient_thread.ident == threading.get_ident():
                self._ambient_thread = None

    def _stop_ambient(self):
        with self._lock:
            stop_event = self._ambient_stop
            proc = self._ambient_proc
            self._ambient_stop = None
            self._ambient_thread = None
            self._ambient_proc = None
        if stop_event:
            stop_event.set()
        self._terminate_process(proc)
        self._forget_process(proc)

    def _stop_foreground(self):
        with self._lock:
            stop_event = self._foreground_stop
            proc = self._foreground_proc
            self._foreground_stop = None
            self._foreground_thread = None
            self._foreground_proc = None
            self._foreground_tag = ""
        if stop_event:
            stop_event.set()
        self._terminate_process(proc)
        self._forget_process(proc)

    def _play_foreground(
        self,
        path: Path,
        tag: str,
        loop: bool = False,
        volume_factor: float = 1.0,
        pause_ambient: bool = True,
    ):
        if not path.exists():
            return
        with self._lock:
            if not self._enabled:
                return
            if loop and self._foreground_tag == tag and self._foreground_thread and self._foreground_thread.is_alive():
                return
            base_volume = self._volume
        if pause_ambient:
            self._stop_ambient()
        self._stop_foreground()

        stop_event = threading.Event()
        worker = threading.Thread(
            target=self._foreground_worker,
            args=(
                path,
                tag,
                stop_event,
                loop,
                max(0.0, min(1.0, base_volume * volume_factor)),
                pause_ambient,
            ),
            daemon=True,
        )
        with self._lock:
            self._foreground_stop = stop_event
            self._foreground_thread = worker
            self._foreground_tag = tag
        worker.start()

    def _foreground_worker(
        self,
        path: Path,
        tag: str,
        stop_event: threading.Event,
        loop: bool,
        volume: float,
        resume_ambient: bool,
    ):
        while not stop_event.is_set():
            try:
                proc = self._start_windows_audio(path, volume)
            except Exception:
                break

            with self._lock:
                if self._foreground_stop is not stop_event or not self._enabled:
                    self._terminate_process(proc)
                    self._forget_process(proc)
                    break
                self._foreground_proc = proc

            while proc.poll() is None and not stop_event.wait(0.12):
                pass

            if stop_event.is_set():
                self._terminate_process(proc)

            with self._lock:
                if self._foreground_proc is proc:
                    self._foreground_proc = None
            if proc.poll() is not None:
                self._forget_process(proc)

            if not loop or stop_event.is_set():
                break
            time.sleep(0.08)

        with self._lock:
            if self._foreground_stop is stop_event:
                self._foreground_stop = None
                self._foreground_thread = None
                self._foreground_tag = ""
            should_restart = resume_ambient and self._enabled and self._foreground_stop is None
        if should_restart:
            self.start_ambient()

    def play_startup(self):
        self._play_foreground(_START_FILE, tag="start", loop=False, volume_factor=0.95)

    def play_success(self):
        self._play_foreground(
            _DONE_FILE,
            tag="done",
            loop=False,
            volume_factor=0.68,
            pause_ambient=False,
        )

    def play_error(self):
        self._play_foreground(_ERROR_FILE, tag="error", loop=False, volume_factor=0.95)

    def start_thinking(self):
        self._play_foreground(
            _THINK_FILE,
            tag="think",
            loop=True,
            volume_factor=0.82,
            pause_ambient=False,
        )

    def stop_thinking(self):
        with self._lock:
            is_thinking = self._foreground_tag == "think"
        if is_thinking:
            self._stop_foreground()

    def toggle(self) -> bool:
        self.set_enabled(not self._enabled)
        return self._enabled

    def set_enabled(self, enabled: bool):
        enabled = bool(enabled)
        with self._lock:
            self._enabled = enabled
        if enabled:
            self.start_ambient()
        else:
            self._stop_ambient()
            self._stop_foreground()

    def set_volume(self, volume: float):
        with self._lock:
            self._volume = max(0.0, min(1.0, float(volume)))
            fg_tag = self._foreground_tag
            can_restart_ambient = self._enabled and not fg_tag
        if fg_tag == "think":
            self._stop_foreground()
            self.start_thinking()
        elif can_restart_ambient:
            self._stop_ambient()
            self.start_ambient()

    def stop_all(self):
        with self._lock:
            self._enabled = False
            ambient_stop = self._ambient_stop
            foreground_stop = self._foreground_stop
            procs = {
                proc
                for proc in (
                    self._ambient_proc,
                    self._foreground_proc,
                    *self._all_sound_procs,
                )
                if proc
            }
            self._ambient_stop = None
            self._ambient_thread = None
            self._ambient_proc = None
            self._foreground_stop = None
            self._foreground_thread = None
            self._foreground_proc = None
            self._foreground_tag = ""
            self._all_sound_procs.clear()
        if ambient_stop:
            ambient_stop.set()
        if foreground_stop:
            foreground_stop.set()
        for proc in procs:
            self._terminate_process(proc)

    def get_volume(self) -> float:
        return self._volume


# ─────────────────────────────────────────────────────────────────────────────

class JarvisUI:
    def __init__(self, start_hidden=False):
        self._start_hidden = start_hidden
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S")
        self.root.update_idletasks()

        target_x = 0
        target_y = 0
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self._is_home_setup = False
        if HAS_WIN32:
            monitors = win32api.EnumDisplayMonitors()
            if len(monitors) > 1:
                self._is_home_setup = True
                for m in monitors:
                    rect = m[2]
                    if rect[0] != 0 or rect[1] != 0:
                        target_x, target_y, right, bottom = rect
                        sw = abs(right - target_x)
                        sh = abs(bottom - target_y)
                        print(f"[JARVIS UI] Ikincil Monitor Secildi: {sw}x{sh} @ ({target_x}, {target_y})")
                        break

        if not self._is_home_setup:
            self._start_hidden = True

        margin_x = max(24, int(sw * 0.025))
        margin_y = max(54, int(sh * 0.055))
        self.W = min(max(640, sw - margin_x), sw, W_TARGET)
        self.H = min(max(520, sh - margin_y), sh, H_TARGET)
        pos_x = target_x + (sw - self.W) // 2
        pos_y = target_y + max(0, (sh - self.H) // 2 - 8)
        _geo = f"{self.W}x{self.H}+{pos_x}+{pos_y}"
        self.root.geometry(_geo)
        self.root.update()
        self.root.minsize(min(self.W, sw), min(self.H, sh))
        self.root.resizable(True, True)
        self.root.configure(bg=C_BG)
        self.root.attributes('-topmost', True)
        self.root.lift()
        self.root.focus_force()
        # Windows bazen ilk olculeri gec uygulayabilir, tekrar zorla.
        for delay in (80, 220, 600, 1200):
            self.root.after(delay, self._force_startup_size)
        # Birkaç saniye sonra topmost'u kapat (normal davranış)
        self.root.after(3000, lambda: self.root.attributes('-topmost', False))

        self._window_geometry = _geo
        self._normal_size = (self.W, self.H)
        self._fullscreen = True

        self._set_layout_metrics(self.W, self.H)

        # ── State ────────────────────────────────────────────────────────────
        self.speaking        = False
        self.user_speaking   = False
        self.muted           = False
        self.paused          = False
        self.scale           = 1.0
        self.target_scale    = 1.0
        self.halo_a          = 55.0
        self.target_halo     = 55.0
        self.last_t          = time.time()
        self.tick            = 0
        self.rings_spin      = [0.0, 45.0, 90.0, 200.0]  # 4 ayrı halka
        self.pulse_r         = []
        self.status_blink    = True
        self._jarvis_state   = "INITIALISING"
        self._user_speaking_until = 0.0

        # ── Panel data ────────────────────────────────────────────────────────
        self._market_data = {}
        self._weather_card = {
            "city": "Istanbul",
            "temp": "16°C",
            "condition": "Clear Sky",
            "feels_like": "14°",
            "humidity": "63%",
            "wind": "11 km/h",
            "aqi": "Good",
            "suggestion": "Light jacket recommended.",
        }
        self._ai_workflow_tasks = deque([
            ("[ RUNNING ]", "Realtime Voice Listener Core", C_GREEN),
            ("[ STANDBY ]", "Neural Memory & Context Sync", C_GOLD),
            ("[ READY ]", "Windows Automation Engine", C_BLUE),
            ("[ WAITING ]", "Background Telemetry Scan", C_TEXT),
        ], maxlen=4)
        
        # English Tutor State
        self.english_tutor_mode = False
        self.english_tutor_stats = {
            "level": "B2 Upper Intermediate",
            "fluency": "85%",
            "new_words": deque(maxlen=3),
            "last_correction": ""
        }
        
        self.neural_logs = deque(maxlen=8)
        self.neural_logs.append(("SYSTEM", "JARVIS UI initialized.", C_PRI))

        self._panel_focus = ""
        self._panel_focus_until = 0.0
        self._brief_refresh_busy = False
        self._started_at = time.time()
        self._error_hold_until = 0.0
        self._settings_open = False
        self._settings_tab = "settings"
        self._debug_entries = deque(maxlen=160)
        self._startup_sfx_played = False
        # ── Notifications (Toast) ─────────────────────────────────────────────
        self._notifications = deque(maxlen=5)
        # ── Mic level ─────────────────────────────────────────────────────────
        self._mic_level = 0.0
        self._settings_geometry = {
            "btn_x": 14,
            "btn_y": 12,
            "btn_w": 250,
            "btn_h": 46,
            "panel_x": 14,
            "panel_y": HDR_H + 10,
            "panel_w": 320,
            "panel_h": 340,
        }
        self.setup_frame = None
        self.api_entry = None
        self.youtube_api_entry = None
        self.youtube_handle_entry = None

        # ── Callbacks ────────────────────────────────────────────────────────
        self.on_text_command = None
        self.on_pause_toggle = None
        self.on_stop_command = None
        self.on_voice_change = None
        self.on_effects_state_change = None

        # ── Voice & Theme ────────────────────────────────────────────────────
        self._current_voice = self._load_voice()
        self._current_theme = self._load_theme_config()
        self._apply_theme(self._current_theme)

        # ── Sound ────────────────────────────────────────────────────────────
        self.sound = SoundManager()

        # ── Stats ────────────────────────────────────────────────────────────
        self._stats      = {'cpu': 0.0, 'ram': 0.0, 'disk': 0.0,
                            'battery': 100.0, 'net_up': 0.0, 'net_down': 0.0}
        self._cpu_hist   = [0.0] * 24
        self._last_net   = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._wave_jarvis = [random.randint(4, 26) for _ in range(18)]
        self._wave_user   = [random.randint(2, 10) for _ in range(18)]

        # ── Typing ───────────────────────────────────────────────────────────
        self.typing_queue = deque()
        self.is_typing    = False

        # ── Partiküller (arka plan, az sayıda) ───────────────────────────────
        self.particles = [
            {
                'x':  random.uniform(0, self.W),
                'y':  random.uniform(0, self.H),
                'vx': random.uniform(-0.15, 0.15),
                'vy': random.uniform(-0.15, 0.15),
                'r':  random.uniform(0.5, 1.8),
                'a':  random.randint(15, 70),
            }
            for _ in range(24)
        ]

        self.orb_particles = [
            {
                'angle': random.uniform(0, math.tau),
                'orbit': random.uniform(0.06, 0.98),
                'speed': random.uniform(-0.030, 0.030),
                'size': random.uniform(0.8, 2.8),
                'phase': random.uniform(0, math.tau),
                'wobble': random.uniform(0.010, 0.040),
                'depth': random.uniform(0.30, 1.00),
            }
            for _ in range(160)
        ]
        self.orb_shell_particles = [
            {
                'angle': random.uniform(0, math.tau),
                'speed': random.uniform(-0.020, 0.020),
                'size': random.uniform(1.4, 3.8),
                'phase': random.uniform(0, math.tau),
                'glow': random.uniform(0.4, 1.0),
            }
            for _ in range(84)
        ]

        # ── Canvas ───────────────────────────────────────────────────────────
        self.bg = tk.Canvas(self.root, width=self.W, height=self.H,
                            bg=C_BG, highlightthickness=0)
        self.bg.place(x=0, y=0)

        # ── Log ──────────────────────────────────────────────────────────────
        self.log_frame = tk.Frame(self.root, bg="#030e0e",
                                  highlightbackground=C_MID,
                                  highlightthickness=1)
        self.log_frame.place(x=self.CHAT_X, y=self.CHAT_Y,
                             width=self.CHAT_W, height=self.CHAT_H)
        self.log_text = tk.Text(
            self.log_frame, fg=C_TEXT, bg="#030e0e",
            insertbackground=C_TEXT, borderwidth=0,
            wrap="word", font=font_body(12), padx=12, pady=8)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        self.log_text.tag_config("you", foreground="#d0f0ee")
        self.log_text.tag_config("ai",  foreground=C_PRI)
        sys_color = "#800000" if self._current_theme == "ELECTRIC BLUE (Varsayılan)" else C_GOLD
        self.log_text.tag_config("sys", foreground=sys_color)
        self.log_text.tag_config("err", foreground=C_RED)

        self._build_input_bar(self.CHAT_W)
        self._build_mute_button()
        self._build_pause_button()
        self._build_sleep_button()
        self._build_shutdown_button()
        self._build_settings_panel()
        self._build_voice_selector(self._settings_body)
        self._build_theme_selector(self._settings_body)
        self._build_sfx_button(self._settings_body)
        self._build_api_button(self._settings_body)
        self._build_fx_slider(self._settings_body)
        self._layout_settings_controls()
        self._place_layout_widgets()

        # Orb tıklama = pause/resume
        self.bg.bind("<Button-1>", self._on_canvas_click)
        self.bg.bind("<B1-Motion>", self._on_canvas_drag)
        self.root.bind("<Configure>", self._on_window_resize)
        self.root.bind("<Map>", self._on_window_map)

        self.root.bind("<F4>",        lambda e: self._toggle_mute())
        self.root.bind("<Control-m>", lambda e: self._toggle_mute())
        self.root.bind("<Escape>",    lambda e: self._shutdown())
        self.root.bind("<F5>",        lambda e: self._toggle_pause())
        self.root.bind("<F11>",       lambda e: self._toggle_fullscreen())
        self.root.bind("<Control-f>", lambda e: self._toggle_fullscreen())

        self._api_key_ready = has_gemini_api_key()
        if not self._api_key_ready:
            self._show_setup_ui()

        self._effects_active = None
        self._sync_sound_state()
        self.root.after(180, self._play_startup_sfx_once)
        self._kick_brief_refresh()
        self.root.after(120, self._enter_fullscreen)
        self._animate()
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)
        
        if self._start_hidden:
            self.root.after(300, self.sleep_mode)

    def _force_startup_size(self):
        if self._fullscreen:
            self._enter_fullscreen()
            return
        self.root.geometry(self._window_geometry)
        self._resize_surface(*self._normal_size)
        self.root.update_idletasks()

    def _enter_fullscreen(self):
        target_x = 0
        target_y = 0
        sw = max(self.root.winfo_screenwidth(), self.root.winfo_width(), self.W)
        sh = max(self.root.winfo_screenheight(), self.root.winfo_height(), self.H)
        if HAS_WIN32:
            monitors = win32api.EnumDisplayMonitors()
            if len(monitors) > 1:
                for m in monitors:
                    rect = m[2]
                    if rect[0] != 0 or rect[1] != 0:
                        target_x, target_y, right, bottom = rect
                        sw = abs(right - target_x)
                        sh = abs(bottom - target_y)
                        break
            
        self.root.attributes("-fullscreen", False)
        self.root.overrideredirect(True)
        self.root.geometry(f"{sw}x{sh}+{target_x}+{target_y}")
        self.root.update()
        self._resize_surface(sw, sh)

    def _set_layout_metrics(self, width: int, height: int):
        self.W = int(width)
        self.H = int(height)
        self.LEFT_W = min(LEFT_W_T, int(self.W * 0.23))
        self.RIGHT_W = min(RIGHT_W_T, int(self.W * 0.25))
        center_w = self.W - self.LEFT_W - self.RIGHT_W
        orb_area_h = self.H - HDR_H - CONTROL_H - FOOTER_H - 24
        self.FCX = self.LEFT_W + center_w // 2
        self.FCY = HDR_H + orb_area_h // 2 + 6
        self.FACE = min(int(orb_area_h * 0.90), int(center_w * 0.86), 860)

        self.CENTER_X0 = self.LEFT_W
        self.CENTER_X1 = self.W - self.RIGHT_W
        self.CTRL_X = self.LEFT_W + 18
        self.CTRL_Y = HDR_H + orb_area_h + 2
        self.CTRL_W = center_w - 36
        self.CHAT_PANEL_X = self.W - self.RIGHT_W + 8
        self.CHAT_PANEL_Y = HDR_H + 8
        self.CHAT_PANEL_W = self.RIGHT_W - 14
        self.CHAT_PANEL_H = self.H - HDR_H - FOOTER_H - 16
        self.CHAT_X = self.CHAT_PANEL_X + 10
        self.CHAT_Y = self.CHAT_PANEL_Y + 34
        self.CHAT_W = self.CHAT_PANEL_W - 20
        self.CHAT_H = self.CHAT_PANEL_H - 90
        self.CHAT_INPUT_Y = self.CHAT_PANEL_Y + self.CHAT_PANEL_H - INPUT_H - 10


    # ── Voice & Theme ────────────────────────────────────────────────────────
    def _load_voice(self) -> str:
        try:
            return str(load_app_config().get("voice", "Charon") or "Charon")
        except Exception:
            return "Charon"

    def _load_theme_config(self) -> str:
        try:
            return str(load_app_config().get("theme", "ELECTRIC BLUE (Varsayılan)") or "ELECTRIC BLUE (Varsayılan)")
        except Exception:
            return "ELECTRIC BLUE (Varsayılan)"

    def _apply_theme(self, theme_name: str):
        global C_BG, C_PRI, C_ORG, C_ORG2, C_MID, C_DIM, C_DIMMER, C_TEXT, C_PANEL, C_GREEN, C_RED, C_GOLD, ORB_COLORS
        if theme_name not in THEMES:
            theme_name = "ELECTRIC BLUE (Varsayılan)"
        self._current_theme = theme_name
        t = THEMES[theme_name]
        C_BG      = t["C_BG"]
        C_PRI     = t["C_PRI"]
        C_ORG     = t["C_ORG"]
        C_ORG2    = t["C_ORG2"]
        C_MID     = t["C_MID"]
        C_DIM     = t["C_DIM"]
        C_DIMMER  = t["C_DIMMER"]
        C_TEXT    = t["C_TEXT"]
        C_PANEL   = t["C_PANEL"]
        C_GREEN   = t["C_GREEN"]
        C_RED     = t["C_RED"]
        C_GOLD    = t["C_GOLD"]
        ORB_COLORS["LISTENING"] = t["ORB_LISTENING"]
        ORB_COLORS["SPEAKING"]  = t["ORB_SPEAKING"]
        ORB_COLORS["THINKING"]  = t["ORB_THINKING"]

        if not hasattr(self, "root") or not self.root:
            return

        self.root.configure(bg=C_BG)
        if hasattr(self, "bg") and self.bg:
            self.bg.configure(bg=C_BG)

        if hasattr(self, "log_frame") and self.log_frame:
            self.log_frame.configure(bg=C_PANEL, highlightbackground=C_MID)
            self.log_text.configure(bg=C_PANEL, fg=C_TEXT, insertbackground=C_TEXT)
            self.log_text.tag_config("you", foreground="#d0f0ee")
            self.log_text.tag_config("ai", foreground=C_PRI)
            sys_color = "#800000" if theme_name == "ELECTRIC BLUE (Varsayılan)" else C_GOLD
            self.log_text.tag_config("sys", foreground=sys_color)
            self.log_text.tag_config("err", foreground=C_RED)

        if hasattr(self, "_settings_panel") and self._settings_panel:
            self._settings_panel.configure(bg=C_BG, highlightbackground=C_MID)
            self._settings_title.configure(bg=C_BG, fg=C_PRI)
            self._settings_tab_settings.configure(bg=C_BG)
            self._settings_tab_debug.configure(bg=C_BG)
            self._settings_body.configure(bg=C_BG)
            self._debug_body.configure(bg=C_BG)
            self._settings_sfx_label.configure(bg=C_BG, fg=C_MID)
            self._settings_status_primary.configure(bg=C_BG, fg=C_TEXT)
            self._settings_status_secondary.configure(bg=C_BG, fg=C_TEXT)
            self._debug_text.configure(bg=C_PANEL, highlightbackground=C_DIM)
            self._debug_text.tag_config("info", foreground=C_TEXT)
            self._debug_text.tag_config("warn", foreground=C_GOLD)
            self._debug_text.tag_config("err", foreground=C_RED)
            self._volume_label.configure(bg=C_BG, fg=C_TEXT)
            self._volume_scale.configure(bg=C_BG, fg=C_TEXT, activebackground=C_PRI, troughcolor=C_DIMMER)
            self._voice_label.configure(bg=C_BG, fg=C_MID)
            self._voice_menu.config(fg=C_PRI, bg=C_PANEL, activeforeground=C_BG, activebackground=C_PRI, highlightbackground=C_MID)
            self._voice_menu["menu"].config(fg=C_PRI, bg=C_PANEL, activeforeground=C_BG, activebackground=C_PRI)
            if hasattr(self, "_theme_label") and self._theme_label:
                self._theme_label.configure(bg=C_BG, fg=C_MID)
                self._theme_menu.config(fg=C_PRI, bg=C_PANEL, activeforeground=C_BG, activebackground=C_PRI, highlightbackground=C_MID)
                self._theme_menu["menu"].config(fg=C_PRI, bg=C_PANEL, activeforeground=C_BG, activebackground=C_PRI)
            self._draw_settings_button()
            self._draw_settings_tabs()
            self._draw_api_button()
            self._draw_sfx_button()

        if hasattr(self, "_input_entry") and self._input_entry:
            self._input_entry.configure(bg=C_PANEL, fg=C_TEXT, insertbackground=C_TEXT, highlightbackground=C_DIM, highlightcolor=C_PRI)
            self._send_btn.configure(bg=C_PANEL, fg=C_ORG, activebackground=C_ORG, highlightbackground=C_ORG)

        if hasattr(self, "_mute_canvas") and self._mute_canvas:
            self._mute_canvas.configure(bg=C_BG)
            self._pause_canvas.configure(bg=C_BG)
            self._sleep_canvas.configure(bg=C_BG)
            self._shutdown_canvas.configure(bg=C_BG)
            self._draw_mute_button()
            self._draw_pause_button()
            self._draw_sleep_button()
            self._draw_shutdown_button()

        if hasattr(self, "bg") and self.bg:
            self._draw_static_bg_grid()

        if hasattr(self, "typing_queue"):
            self.write_log(f"SYS: Tema aktif: {theme_name}")

    # ── Sleep button ─────────────────────────────────────────────────────────
    def _build_sleep_button(self):
        BW, BH = 126, 36
        self._sleep_canvas = tk.Canvas(
            self.root, width=BW, height=BH,
            bg=C_BG, highlightthickness=0, cursor="hand2")
        self._sleep_canvas.bind("<Button-1>", lambda e: self.sleep_mode())
        self._sleep_hover = False
        self._sleep_canvas.bind("<Enter>", lambda e: self._on_btn_hover("sleep", True))
        self._sleep_canvas.bind("<Leave>", lambda e: self._on_btn_hover("sleep", False))
        self._draw_sleep_button()

    def _draw_sleep_button(self):
        c = self._sleep_canvas
        BW, BH = 126, 36
        c.delete("all")
        col = "#e040fb" if self._sleep_hover else "#b388ff"
        bg = "#1a0a2a" if self._sleep_hover else C_BG
        c.create_rectangle(0, 0, BW, BH, fill=bg, outline="")
        bl = 6
        for bx, by, sx, sy in [(0, 0, 1, 1), (BW, 0, -1, 1),
                                (0, BH, 1, -1), (BW, BH, -1, -1)]:
            c.create_line(bx, by, bx+sx*bl, by, fill=col, width=2)
            c.create_line(bx, by, bx, by+sy*bl, fill=col, width=2)
        c.create_text(BW//2, BH//2, text="💤  SLEEP",
                      fill=col, font=font_body_bold(11))

    # ── Shutdown button ──────────────────────────────────────────────────────
    def _build_shutdown_button(self):
        BW, BH = 140, 36
        self._shutdown_canvas = tk.Canvas(
            self.root, width=BW, height=BH,
            bg=C_BG, highlightthickness=0, cursor="hand2")
        self._shutdown_canvas.bind("<Button-1>", lambda e: self._shutdown())
        self._shutdown_hover = False
        self._shutdown_canvas.bind("<Enter>", lambda e: self._on_btn_hover("shutdown", True))
        self._shutdown_canvas.bind("<Leave>", lambda e: self._on_btn_hover("shutdown", False))
        self._draw_shutdown_button()

    def _draw_shutdown_button(self):
        c = self._shutdown_canvas
        BW, BH = 140, 36
        c.delete("all")
        col = "#ff6666" if self._shutdown_hover else C_RED
        bg = "#1a0a0a" if self._shutdown_hover else C_BG
        c.create_rectangle(0, 0, BW, BH, fill=bg, outline="")
        bl = 8
        for bx, by, sx, sy in [(0, 0, 1, 1), (BW, 0, -1, 1),
                                (0, BH, 1, -1), (BW, BH, -1, -1)]:
            c.create_line(bx, by, bx+sx*bl, by, fill=col, width=2)
            c.create_line(bx, by, bx, by+sy*bl, fill=col, width=2)
        c.create_text(BW//2, BH//2, text="⏻  SHUTDOWN",
                      fill=col, font=font_display(11))

    def _on_btn_hover(self, btn_name, entered):
        if btn_name == "shutdown":
            self._shutdown_hover = entered
            self._draw_shutdown_button()
        elif btn_name == "sleep":
            self._sleep_hover = entered
            self._draw_sleep_button()
        elif btn_name == "mute":
            self._mute_hover = entered
            self._draw_mute_button()
        elif btn_name == "pause":
            self._pause_hover = entered
            self._draw_pause_button()

    def _build_settings_panel(self):
        geo = self._settings_geometry
        self._settings_btn_canvas = tk.Canvas(
            self.root,
            width=geo["btn_w"],
            height=geo["btn_h"],
            bg=C_BG,
            highlightthickness=0,
            cursor="hand2",
        )
        self._settings_btn_canvas.place(x=geo["btn_x"], y=geo["btn_y"])
        self._settings_btn_canvas.bind("<Button-1>", lambda e: self._toggle_settings_panel())
        self._draw_settings_button()

        self._settings_panel = tk.Frame(
            self.root,
            bg="#030a12",
            highlightbackground=C_MID,
            highlightthickness=1,
        )
        self._settings_panel.place_forget()

        self._settings_title = tk.Label(
            self._settings_panel,
            text="⚙ SYSTEM SETTINGS",
            fg=C_PRI,
            bg="#030a12",
            font=font_display(11),
        )
        self._settings_tab_settings = tk.Canvas(
            self._settings_panel,
            width=108,
            height=28,
            bg="#030a12",
            highlightthickness=0,
            cursor="hand2",
        )
        self._settings_tab_settings.bind("<Button-1>", lambda e: self._set_settings_tab("settings"))
        self._settings_tab_debug = tk.Canvas(
            self._settings_panel,
            width=96,
            height=28,
            bg="#030a12",
            highlightthickness=0,
            cursor="hand2",
        )
        self._settings_tab_debug.bind("<Button-1>", lambda e: self._set_settings_tab("debug"))
        self._settings_body = tk.Frame(self._settings_panel, bg="#030a12")
        self._debug_body = tk.Frame(self._settings_panel, bg="#030a12")
        self._settings_sfx_label = tk.Label(
            self._settings_body,
            text="SFX",
            fg=C_MID,
            bg="#030a12",
            font=font_body_bold(8),
        )
        self._settings_status_primary = tk.Label(
            self._settings_body,
            text="",
            fg=C_TEXT,
            bg="#030a12",
            font=font_body_bold(9),
            anchor="w",
            justify="left",
        )
        self._settings_status_secondary = tk.Label(
            self._settings_body,
            text="",
            fg=C_TEXT,
            bg="#030a12",
            font=font_body(9),
            anchor="w",
            justify="left",
        )
        self._debug_text = tk.Text(
            self._debug_body,
            fg=C_TEXT,
            bg="#01060c",
            insertbackground=C_TEXT,
            borderwidth=0,
            wrap="word",
            font=font_body(10),
            padx=10,
            pady=10,
            highlightthickness=1,
            highlightbackground=C_DIM,
        )
        self._debug_text.tag_config("info", foreground=C_TEXT)
        self._debug_text.tag_config("warn", foreground=C_GOLD)
        self._debug_text.tag_config("err", foreground=C_RED)
        self._debug_text.configure(state="disabled")
        self._draw_settings_tabs()
        self._render_debug_logs()
        self._refresh_settings_status()

    def _draw_settings_button(self):
        c = self._settings_btn_canvas
        bw = int(c["width"])
        bh = int(c["height"])
        c.delete("all")
        accent = C_BLUE if self._settings_open else C_PRI
        inner = "#062020" if self._settings_open else "#020810"
        c.create_rectangle(0, 0, bw, bh, fill=inner, outline="")
        bl = 9
        for bx, by, sx, sy in [(0, 0, 1, 1), (bw, 0, -1, 1), (0, bh, 1, -1), (bw, bh, -1, -1)]:
            c.create_line(bx, by, bx + sx * bl, by, fill=accent, width=2)
            c.create_line(bx, by, bx, by + sy * bl, fill=accent, width=2)
        c.create_text(14, 15, text="SYSTEM SETTINGS", fill=C_PRI, font=font_display(10), anchor="w")
        c.create_text(14, 33, text=MODEL_BADGE, fill=C_TEXT, font=font_body(9), anchor="w")
        c.create_text(bw - 14, bh // 2, text="▾" if self._settings_open else "▸",
                      fill=accent, font=font_display(14), anchor="e")

    def _toggle_settings_panel(self):
        self._settings_open = not self._settings_open
        self._draw_settings_button()
        self._place_layout_widgets()

    def _draw_settings_tabs(self):
        for key, canvas, label in (
            ("settings", self._settings_tab_settings, "SETTINGS"),
            ("debug", self._settings_tab_debug, "DEBUG"),
        ):
            active = self._settings_tab == key
            bw = int(canvas["width"])
            bh = int(canvas["height"])
            canvas.delete("all")
            outline = C_PRI if active else C_DIM
            fill = "#062020" if active else "#040a12"
            text_col = C_PRI if active else "#64b5f6"
            canvas.create_rectangle(0, 0, bw, bh, fill=fill, outline="")
            bl = 7
            for bx, by, sx, sy in [(0, 0, 1, 1), (bw, 0, -1, 1), (0, bh, 1, -1), (bw, bh, -1, -1)]:
                canvas.create_line(bx, by, bx + sx * bl, by, fill=outline, width=1)
                canvas.create_line(bx, by, bx, by + sy * bl, fill=outline, width=1)
            canvas.create_text(bw // 2, bh // 2, text=label, fill=text_col, font=font_body_bold(9))

    def _set_settings_tab(self, tab: str):
        self._settings_tab = "debug" if tab == "debug" else "settings"
        self._draw_settings_tabs()
        self._place_layout_widgets()

    def _layout_settings_controls(self):
        inner_w = self._settings_geometry["panel_w"] - 24
        self._api_canvas.place(x=0, y=2)
        self._sfx_canvas.place(x=inner_w - int(self._sfx_canvas["width"]) - 4, y=0)
        self._settings_status_primary.place(x=0, y=38, width=inner_w)
        self._settings_status_secondary.place(x=0, y=58, width=inner_w)
        self._settings_sfx_label.place(x=0, y=92)
        self._volume_label.place(x=0, y=116)
        self._volume_scale.place(x=0, y=136, width=inner_w, height=26)
        self._voice_label.place(x=0, y=178)
        self._voice_menu.place(x=88, y=172, width=inner_w - 88, height=30)
        self._theme_label.place(x=0, y=218)
        self._theme_menu.place(x=88, y=212, width=inner_w - 88, height=30)

    def _refresh_settings_status(self):
        if not hasattr(self, "_settings_status_primary"):
            return
        cfg = load_app_config()
        gemini_ready = bool(str(cfg.get("gemini_api_key", "") or "").strip())
        yt_key_ready = bool(str(cfg.get("youtube_api_key", "") or "").strip())
        yt_handle = str(cfg.get("youtube_channel_handle", "") or "").strip()

        primary = [
            "Gemini API: Aktif" if gemini_ready else "Gemini API: Eksik",
        ]
        secondary = "Model: Gemini 2.5 Flash Native Audio"

        self._settings_status_primary.configure(text="  ·  ".join(primary))
        self._settings_status_secondary.configure(text=secondary)

    def write_debug(self, text: str, level: str = "INFO"):
        clean = " ".join(str(text or "").split())
        if not clean:
            return
        self.root.after(0, self._append_debug_entry, clean, level)

    def _append_debug_entry(self, text: str, level: str = "INFO"):
        stamp = time.strftime("%H:%M:%S")
        lvl = (level or "INFO").upper()
        self._debug_entries.append((lvl, f"[{stamp}] {lvl}: {text}"))
        self._render_debug_logs()

    def _render_debug_logs(self):
        if not hasattr(self, "_debug_text"):
            return
        self._debug_text.configure(state="normal")
        self._debug_text.delete("1.0", tk.END)
        if not self._debug_entries:
            self._debug_text.insert(tk.END, "Henüz not edilebilir hata yok.\n", "info")
        else:
            for level, line in self._debug_entries:
                tag = "err" if level == "ERROR" else "warn" if level == "WARN" else "info"
                self._debug_text.insert(tk.END, line + "\n", tag)
        self._debug_text.see(tk.END)
        self._debug_text.configure(state="disabled")

    def _build_api_button(self, parent=None):
        parent = parent or self.root
        bw, bh = 154, 28
        self._api_canvas = tk.Canvas(
            parent, width=bw, height=bh,
            bg=parent.cget("bg"), highlightthickness=0, cursor="hand2")
        self._api_canvas.bind("<Button-1>", lambda e: self._open_api_settings())
        self._draw_api_button()

    def _draw_api_button(self):
        c = self._api_canvas
        bw = int(c["width"])
        bh = int(c["height"])
        c.delete("all")
        bl = 6
        for bx, by, sx, sy in [(0, 0, 1, 1), (bw, 0, -1, 1), (0, bh, 1, -1), (bw, bh, -1, -1)]:
            c.create_line(bx, by, bx + sx * bl, by, fill=C_GREEN, width=1)
            c.create_line(bx, by, bx, by + sy * bl, fill=C_GREEN, width=1)
        c.create_text(bw // 2, bh // 2, text="⌘ API SETTINGS",
                      fill=C_GREEN, font=font_body_bold(10))

    def _build_fx_slider(self, parent=None):
        parent = parent or self.root
        slider_w = 280
        self._volume_label = tk.Label(
            parent,
            text=f"FX LEVEL  {int(self.sound.get_volume() * 100)}%",
            fg=C_TEXT,
            bg=parent.cget("bg"),
            font=font_body_bold(10),
        )
        self._volume_scale = tk.Scale(
            parent,
            from_=0,
            to=100,
            orient="horizontal",
            length=slider_w,
            showvalue=False,
            resolution=1,
            troughcolor="#08121e",
            bg=parent.cget("bg"),
            fg=C_TEXT,
            activebackground=C_PRI,
            highlightthickness=0,
            borderwidth=0,
            sliderlength=18,
            width=10,
            command=self._on_volume_change,
        )
        self._volume_scale.set(int(self.sound.get_volume() * 100))

    def _on_volume_change(self, value):
        try:
            volume = max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            return
        self._volume_label.configure(text=f"FX LEVEL  {volume}%")
        self.sound.set_volume(volume / 100.0)

    def _play_startup_sfx_once(self):
        pass

    def _sync_sound_state(self):
        enabled = self._sfx_on and not self.paused
        self.sound.set_enabled(enabled)
        if enabled and self._jarvis_state == "THINKING":
            self.sound.start_thinking()
        if enabled != self._effects_active:
            self._effects_active = enabled
            if self.on_effects_state_change:
                threading.Thread(
                    target=self.on_effects_state_change,
                    args=(enabled,),
                    daemon=True,
                ).start()

    def _open_api_settings(self):
        self._show_setup_ui(edit_mode=self._api_key_ready)

    def _close_setup_ui(self):
        if self.setup_frame and self.setup_frame.winfo_exists():
            self.setup_frame.destroy()
        self.setup_frame = None
        self.api_entry = None
        self.youtube_api_entry = None
        self.youtube_handle_entry = None

    # ── SFX toggle ───────────────────────────────────────────────────────────
    def _build_sfx_button(self, parent=None):
        parent = parent or self.root
        BW, BH = 98, 36
        self._sfx_canvas = tk.Canvas(parent, width=BW, height=BH,
                                     bg=parent.cget("bg"), highlightthickness=0, cursor="hand2")
        self._sfx_canvas.bind("<Button-1>", lambda e: self._toggle_sfx())
        self._sfx_on = True
        self._draw_sfx_button()

    def _draw_sfx_button(self):
        c = self._sfx_canvas
        BW = int(c["width"])
        BH = int(c["height"])
        c.delete("all")
        col  = C_PRI if self._sfx_on else "#778899"
        text = "♪ SFX ON"  if self._sfx_on else "♪ SFX OFF"
        bl = 6
        for bx, by, sx, sy in [(0, 0, 1, 1), (BW, 0, -1, 1),
                                (0, BH, 1, -1), (BW, BH, -1, -1)]:
            c.create_line(bx, by, bx+sx*bl, by, fill=col, width=1)
            c.create_line(bx, by, bx, by+sy*bl, fill=col, width=1)
        c.create_text(BW//2, BH//2, text=text, fill=col, font=font_body_bold(9))

    def _toggle_sfx(self):
        self._sfx_on = not self._sfx_on
        self._draw_sfx_button()
        self._sync_sound_state()

    # ── Voice selector ───────────────────────────────────────────────────────
    def _build_voice_selector(self, parent=None):
        parent = parent or self.root
        self._voice_var = tk.StringVar(value=self._current_voice)
        self._voice_label = tk.Label(parent, text="VOICE", fg="#b388ff", bg=parent.cget("bg"),
                                     font=font_body_bold(8))

        self._voice_menu = tk.OptionMenu(parent, self._voice_var, *VOICES,
                                         command=self._on_voice_select)
        self._voice_menu.config(
            fg="#b388ff", bg="#040a12", activeforeground="#020810",
            activebackground="#b388ff", font=font_body(10),
            borderwidth=0, highlightthickness=1,
            highlightbackground="#7c4dff", width=12)
        self._voice_menu["menu"].config(
            fg="#b388ff", bg="#040a12", font=font_body(10),
            activeforeground="#020810", activebackground="#b388ff")

    def _on_voice_select(self, voice: str):
        self._current_voice = voice
        save_app_config({"voice": voice})
        if self.on_voice_change:
            threading.Thread(target=self.on_voice_change, args=(voice,), daemon=True).start()

    # ── Theme selector ───────────────────────────────────────────────────────
    def _build_theme_selector(self, parent=None):
        parent = parent or self.root
        self._theme_var = tk.StringVar(value=self._current_theme)
        self._theme_label = tk.Label(parent, text="THEME", fg=C_MID, bg=parent.cget("bg"),
                                     font=font_body_bold(8))

        self._theme_menu = tk.OptionMenu(parent, self._theme_var, *list(THEMES.keys()),
                                         command=self._on_theme_select)
        self._theme_menu.config(
            fg=C_PRI, bg=C_PANEL, activeforeground=C_BG,
            activebackground=C_PRI, font=font_body(10),
            borderwidth=0, highlightthickness=1,
            highlightbackground=C_MID, width=12)
        self._theme_menu["menu"].config(
            fg=C_PRI, bg=C_PANEL, font=font_body(10),
            activeforeground=C_BG, activebackground=C_PRI)

    def _on_theme_select(self, theme: str):
        save_app_config({"theme": theme})
        self._apply_theme(theme)

    # ── Mute button ──────────────────────────────────────────────────────────
    def _build_mute_button(self):
        self._mute_canvas = tk.Canvas(self.root, width=126, height=36,
                                      bg=C_BG, highlightthickness=0, cursor="hand2")
        self._mute_canvas.bind("<Button-1>", lambda e: self._toggle_mute())
        self._mute_hover = False
        self._mute_canvas.bind("<Enter>", lambda e: self._on_btn_hover("mute", True))
        self._mute_canvas.bind("<Leave>", lambda e: self._on_btn_hover("mute", False))
        self._draw_mute_button()

    def _draw_mute_button(self):
        c = self._mute_canvas
        bw = int(c["width"])
        bh = int(c["height"])
        c.delete("all")
        if self.muted:
            col, icon, lbl = C_MUTED, "🔇", " MUTED"
        else:
            col, icon, lbl = C_GREEN, "🎙", " LIVE"
        hover = getattr(self, "_mute_hover", False)
        bg = "#0a1a12" if hover else C_BG
        c.create_rectangle(0, 0, bw, bh, fill=bg, outline="")
        bl = 6
        for bx, by, sx, sy in [(0, 0, 1, 1), (bw, 0, -1, 1),
                                (0, bh, 1, -1), (bw, bh, -1, -1)]:
            c.create_line(bx, by, bx+sx*bl, by, fill=col, width=2)
            c.create_line(bx, by, bx, by+sy*bl, fill=col, width=2)
        c.create_text(bw//2, bh//2, text=f"{icon}{lbl}",
                      fill=col, font=font_body_bold(11))

    def _build_pause_button(self):
        self._pause_canvas = tk.Canvas(self.root, width=126, height=36,
                                       bg=C_BG, highlightthickness=0, cursor="hand2")
        self._pause_canvas.bind("<Button-1>", lambda e: self._toggle_pause())
        self._pause_hover = False
        self._pause_canvas.bind("<Enter>", lambda e: self._on_btn_hover("pause", True))
        self._pause_canvas.bind("<Leave>", lambda e: self._on_btn_hover("pause", False))
        self._draw_pause_button()

    def _draw_pause_button(self):
        c = self._pause_canvas
        bw = int(c["width"])
        bh = int(c["height"])
        c.delete("all")
        if self.paused:
            col, text = C_GOLD, "▶ RESUME"
        else:
            col, text = C_BLUE, "⏸ PAUSE"
        hover = getattr(self, "_pause_hover", False)
        bg = "#0a1218" if hover else C_BG
        c.create_rectangle(0, 0, bw, bh, fill=bg, outline="")
        bl = 6
        for bx, by, sx, sy in [(0, 0, 1, 1), (bw, 0, -1, 1),
                               (0, bh, 1, -1), (bw, bh, -1, -1)]:
            c.create_line(bx, by, bx+sx*bl, by, fill=col, width=2)
            c.create_line(bx, by, bx, by+sy*bl, fill=col, width=2)
        c.create_text(bw//2, bh//2, text=text, fill=col, font=font_body_bold(11))

    def _toggle_mute(self):
        self.muted = not self.muted
        self._draw_mute_button()
        if self.muted:
            self.write_log("SYS: Mikrofon kapatıldı.")
        else:
            self.write_log("SYS: Mikrofon açık.")
        self._sync_sound_state()

    # ── Orb tıklama = pause ──────────────────────────────────────────────────
    def _on_window_resize(self, event):
        if event.widget == self.root:
            w = event.width
            h = event.height
            if w >= 640 and h >= 480 and (abs(w - getattr(self, "W", 0)) > 20 or abs(h - getattr(self, "H", 0)) > 20):
                self._resize_surface(w, h)

    def _on_window_map(self, event):
        if event.widget == self.root and getattr(self, "_is_minimized", False):
            if self.root.state() == "normal":
                self._is_minimized = False
                if getattr(self, "_fullscreen", False):
                    self.root.overrideredirect(True)
                    self.root.update()

    def _minimize_window(self):
        self._is_minimized = True
        self.root.overrideredirect(False)
        self.root.state("iconic")

    def _on_canvas_click(self, event):
        W = self.W
        if event.y <= 35:
            if W-125 <= event.x <= W-90:
                self._minimize_window()
                return
            if W-85 <= event.x <= W-50:
                self._toggle_fullscreen()
                return
            if W-45 <= event.x <= W-10:
                self._shutdown()
                return

        if event.y <= HDR_H and event.x < W - 140:
            self._drag_start_x = event.x
            self._drag_start_y = event.y
            return

        dx = event.x - self.FCX
        dy = event.y - self.FCY
        if dx*dx + dy*dy <= (self.FACE * 0.40)**2:
            self._toggle_pause()

    def _on_canvas_drag(self, event):
        if hasattr(self, "_drag_start_x") and event.y <= HDR_H:
            if getattr(self, "_fullscreen", False):
                self._toggle_fullscreen()
            new_x = self.root.winfo_x() + (event.x - self._drag_start_x)
            new_y = self.root.winfo_y() + (event.y - self._drag_start_y)
            self.root.geometry(f"+{new_x}+{new_y}")

    def _toggle_pause(self):
        self.paused = not self.paused
        self._draw_pause_button()
        if self.paused:
            self.set_state("PAUSED")
            self.write_log("SYS: JARVIS duraklatıldı.")
        else:
            self.set_state("THINKING")
            self.write_log("SYS: JARVIS devam ediyor...")
        self._sync_sound_state()
        if self.on_pause_toggle:
            threading.Thread(target=self.on_pause_toggle, args=(self.paused,), daemon=True).start()

    def sleep_mode(self):
        self.paused = True
        self.muted = True
        self.set_state("PAUSED")
        self._sync_sound_state()
        if self.on_pause_toggle:
            threading.Thread(target=self.on_pause_toggle, args=(self.paused,), daemon=True).start()
        self.root.withdraw()
        
    def wake_up(self):
        self.root.deiconify()
        self.root.attributes('-topmost', True)
        self.root.lift()
        self.root.focus_force()
        if self.root.state() == "iconic":
            self.root.state("normal")
        self.paused = False
        self.muted = False
        self.set_state("LISTENING")
        self._sync_sound_state()
        if self.on_pause_toggle:
            threading.Thread(target=self.on_pause_toggle, args=(self.paused,), daemon=True).start()
        self.root.after(3000, lambda: self.root.attributes('-topmost', False))

    def _shutdown(self):
        self.sound.stop_all()
        self.write_log("SYS: JARVIS kapatılıyor...")
        self.root.after(380, os._exit, 0)

    def _toggle_fullscreen(self):
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            curr_x = self.root.winfo_x() + (self.root.winfo_width() // 2)
            curr_y = self.root.winfo_y() + (self.root.winfo_height() // 2)
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            target_left = self.root.winfo_x()
            target_top = self.root.winfo_y()
            if HAS_WIN32:
                monitors = win32api.EnumDisplayMonitors()
                for m in monitors:
                    rect = m[2]
                    left, top, right, bottom = rect
                    if left <= curr_x < right and top <= curr_y < bottom:
                        sw = abs(right - left)
                        sh = abs(bottom - top)
                        target_left = left
                        target_top = top
                        break
            self.root.attributes("-fullscreen", False)
            self.root.overrideredirect(True)
            self.root.geometry(f"{sw}x{sh}+{target_left}+{target_top}")
            self.root.update()
            self._resize_surface(sw, sh)
        else:
            self.root.overrideredirect(False)
            self.root.attributes("-fullscreen", False)
            curr_x = self.root.winfo_x()
            curr_y = self.root.winfo_y()
            win_w = min(1400, self.W)
            win_h = min(900, self.H)
            self.root.geometry(f"{win_w}x{win_h}+{curr_x}+{curr_y}")
            self.root.update()
            actual_w = max(500, self.root.winfo_width())
            actual_h = max(500, self.root.winfo_height())
            self._resize_surface(actual_w, actual_h)

    def _draw_static_bg_grid(self):
        self.bg.delete("static_grid")
        W = self.W
        H = self.H
        step = 48
        for x in range(0, W, step):
            for y in range(0, H, step):
                self.bg.create_rectangle(x, y, x+1, y+1, fill=C_DIMMER, outline="", tag="static_grid")

    def _resize_surface(self, width: int, height: int):
        self._set_layout_metrics(width, height)
        self.bg.configure(width=self.W, height=self.H)
        self.bg.place(x=0, y=0)
        self._place_layout_widgets()
        self._draw_static_bg_grid()
        for p in self.particles:
            p["x"] %= self.W
            p["y"] %= self.H

    # ── Input bar ────────────────────────────────────────────────────────────
    def _build_input_bar(self, lw: int):
        x0 = self.CHAT_X
        btn_w = 76
        gap = 8
        inp_w = lw - btn_w - gap

        self._input_var   = tk.StringVar()
        self._input_entry = tk.Entry(
            self.root, textvariable=self._input_var,
            fg=C_TEXT, bg="#041212", insertbackground=C_TEXT,
            borderwidth=0, font=font_body(11),
            highlightthickness=1, highlightbackground=C_DIM,
            highlightcolor=C_PRI)
        self._input_entry.place(
            x=x0, y=self.CHAT_INPUT_Y, width=inp_w, height=INPUT_H)
        self._input_entry.bind("<Return>",   self._on_input_submit)
        self._input_entry.bind("<KP_Enter>", self._on_input_submit)

        self._send_btn = tk.Button(
            self.root, text="SEND ▸",
            command=self._on_input_submit,
            fg=C_ORG, bg=C_PANEL,
            activeforeground=C_BG, activebackground=C_ORG,
            font=font_body_bold(10),
            borderwidth=0, cursor="hand2",
            highlightthickness=1, highlightbackground=C_ORG)
        self._send_btn.place(
            x=x0+inp_w+gap, y=self.CHAT_INPUT_Y,
            width=btn_w, height=INPUT_H)

    def _place_layout_widgets(self):
        self.log_frame.place(x=self.CHAT_X, y=self.CHAT_Y, width=self.CHAT_W, height=self.CHAT_H)
        gap = 10
        mute_w = 126
        pause_w = 126
        sleep_w = int(self._sleep_canvas["width"])
        shutdown_w = int(self._shutdown_canvas["width"])
        total = mute_w + pause_w + sleep_w + shutdown_w + gap * 3
        start_x = self.FCX - total // 2
        row1_y = self.CTRL_Y + 20

        self._mute_canvas.place(x=start_x, y=row1_y)
        self._pause_canvas.place(x=start_x + mute_w + gap, y=row1_y)
        self._sleep_canvas.place(x=start_x + mute_w + pause_w + gap * 2, y=row1_y)
        self._shutdown_canvas.place(x=start_x + mute_w + pause_w + sleep_w + gap * 3, y=row1_y)

        panel_w = min(320, max(260, self.LEFT_W - 10))
        panel_h = min(380, self.H - HDR_H - FOOTER_H - 40)
        panel_x = 14
        panel_y = HDR_H + 10
        if hasattr(self, "_settings_btn_canvas"):
            self._settings_btn_canvas.place(x=14, y=12)
        if self._settings_open:
            self._settings_panel.place(x=panel_x, y=panel_y, width=panel_w, height=panel_h)
            self._settings_panel.lift()
            self._settings_title.place(x=14, y=12)
            self._settings_tab_settings.place(x=14, y=40)
            self._settings_tab_debug.place(x=130, y=40)
            if self._settings_tab == "debug":
                self._settings_body.place_forget()
                self._debug_body.place(x=12, y=76, width=panel_w - 24, height=panel_h - 88)
                self._debug_text.place(x=0, y=0, width=panel_w - 24, height=panel_h - 88)
                self._debug_body.lift()
            else:
                self._debug_body.place_forget()
                self._settings_body.place(x=12, y=76, width=panel_w - 24, height=panel_h - 88)
                self._settings_body.lift()
        else:
            self._settings_panel.place_forget()
            self._settings_title.place_forget()
            self._settings_tab_settings.place_forget()
            self._settings_tab_debug.place_forget()
            self._settings_body.place_forget()
            self._debug_body.place_forget()

        inp_w = self.CHAT_W - 84
        self._input_entry.place(x=self.CHAT_X, y=self.CHAT_INPUT_Y, width=inp_w, height=INPUT_H)
        self._send_btn.place(x=self.CHAT_X + inp_w + 8, y=self.CHAT_INPUT_Y, width=76, height=INPUT_H)

    def _on_input_submit(self, event=None):
        text = self._input_var.get().strip()
        if not text:
            return
        if self.paused:
            self.write_log("SYS: JARVIS duraklatılmış durumda. Devam etmek için pause'u kapat.")
            return
        self._input_var.set("")
        if text.lower() in ("sus", "dur", "stop", "sessiz", "kes"):
            self.write_log("SYS: ⏹ Ses kesildi.")
            if self.on_stop_command:
                threading.Thread(target=self.on_stop_command, daemon=True).start()
            return
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(text,), daemon=True).start()

    # ── State & callbacks ────────────────────────────────────────────────────
    def set_state(self, state: str):
        previous = getattr(self, "_jarvis_state", "")
        if state != previous:
            col = C_GREEN if state == "LISTENING" else C_GOLD if state == "THINKING" else C_PRI if state == "SPEAKING" else C_RED
            self.add_neural_log("CORE", f"Status shift: {state}", col)
        self._jarvis_state = state
        self.speaking = (state == "SPEAKING")
        if state == "THINKING":
            self.sound.start_thinking()
        elif previous == "THINKING":
            self.sound.stop_thinking()
        if state == "ERROR" and previous != "ERROR":
            self.sound.play_error()

    def set_user_speaking(self, value: bool):
        self.mark_user_activity(value)

    def mark_user_activity(self, active: bool = True):
        if active and not getattr(self, "user_speaking", False):
            self.add_neural_log("MIC", "Acoustic wave detected.", C_GREEN)
        self.user_speaking = active
        self._user_speaking_until = time.time() + (0.9 if active else 0.0)

    def get_effects_volume(self) -> float:
        return self.sound.get_volume()

    def effects_enabled(self) -> bool:
        return bool(self._effects_active)

    def play_success_sfx(self):
        self.root.after(0, self.sound.play_success)

    def play_error_sfx(self):
        self.root.after(0, self.sound.play_error)

    def focus_panel(self, section: str, duration_ms: int = 4200):
        section = (section or "").strip().lower()
        if not section:
            return

        def _apply():
            self._panel_focus = section
            self._panel_focus_until = time.time() + max(0.8, duration_ms / 1000.0)

        self.root.after(0, _apply)

    def _state_color(self, state: str | None = None) -> str:
        effective = state or self._jarvis_state
        if effective == "PAUSED":
            return C_MID
        return STATE_HEX_COLORS.get(effective, C_PRI)

    @staticmethod
    def _state_badge_text(state: str) -> str:
        if state == "INITIALISING":
            return "CONNECTING"
        if state == "ERROR":
            return "ERROR"
        return "ONLINE"

    # ── Log ──────────────────────────────────────────────────────────────────
    def add_neural_log(self, tag: str, text: str, color: str = C_GREEN):
        t_str = time.strftime("%H:%M:%S")
        self.neural_logs.append((tag, f"[{t_str}] {text}", color))
        
    def write_log(self, text: str):
        self.typing_queue.append(text)
        tl = text.lower()
        if tl.startswith("siz:") or tl.startswith("you:"):
            self.mark_user_activity(True)
            self.set_state("THINKING")
        elif tl.startswith("err:") or "error" in tl:
            self._error_hold_until = time.time() + 8.0
            self.set_state("ERROR")
            self.write_debug(text, level="ERROR")
        if not self.is_typing:
            self._start_typing()

    def _start_typing(self):
        if not self.typing_queue:
            self.is_typing = False
            if self._jarvis_state == "ERROR" and time.time() < self._error_hold_until:
                return
            if not self.speaking:
                self.set_state("LISTENING")
            return
        self.is_typing = True
        text = self.typing_queue.popleft()
        tl   = text.lower()
        if   tl.startswith("siz:") or tl.startswith("you:"):   tag = "you"
        elif tl.startswith("jarvis:") or tl.startswith("ai:"): tag = "ai"
        elif tl.startswith("err:") or "error" in tl:           tag = "err"
        else:                                                    tag = "sys"
        self.log_text.configure(state="normal")
        self._type_char(text, 0, tag)

    def _type_char(self, text, i, tag):
        chunk_size = 3 if len(text) > 80 else 1
        if i < len(text):
            chunk = text[i:i+chunk_size]
            self.log_text.insert(tk.END, chunk, tag)
            self.log_text.see(tk.END)
            self.root.after(7, self._type_char, text, i+chunk_size, tag)
        else:
            self.log_text.insert(tk.END, "\n")
            self.log_text.configure(state="disabled")
            self.root.after(20, self._start_typing)

    # ── Stats ────────────────────────────────────────────────────────────────
    def _update_stats(self):
        try:
            cpu  = psutil.cpu_percent(interval=None)
            ram  = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            batt_obj = psutil.sensors_battery()
            battery = batt_obj.percent if batt_obj else 100.0
            now = time.time()
            net = psutil.net_io_counters()
            dt  = now - getattr(self, "_last_net_t", now)
            net_up = getattr(self, "_stats", {}).get('net_up', 0)
            net_down = getattr(self, "_stats", {}).get('net_down', 0)
            if dt > 0 and hasattr(self, "_last_net"):
                net_up   = max(0, (net.bytes_sent - self._last_net.bytes_sent) / dt / 1024)
                net_down = max(0, (net.bytes_recv - self._last_net.bytes_recv) / dt / 1024)
            self._last_net   = net
            self._last_net_t = now

            def _apply_stats():
                self._stats['cpu'] = cpu
                self._stats['ram'] = ram
                self._stats['disk'] = disk
                self._stats['battery'] = battery
                self._stats['net_up'] = net_up
                self._stats['net_down'] = net_down
                if len(self._cpu_hist) > 0:
                    self._cpu_hist.pop(0)
                self._cpu_hist.append(cpu)

            self.root.after(0, _apply_stats)
        except Exception:
            pass

    # ── Animation loop ───────────────────────────────────────────────────────
    def _animate(self):
        self.tick += 1
        t   = self.tick
        now = time.time()

        if self.user_speaking and now > self._user_speaking_until:
            self.user_speaking = False

        if t % 90 == 0:
            threading.Thread(target=self._update_stats, daemon=True).start()
        if t % 1800 == 1:
            self._kick_brief_refresh()

        if self.speaking and t % 3 == 0:
            self._wave_jarvis = [random.randint(6, 30) for _ in range(18)]
        if self.user_speaking and t % 3 == 0:
            self._wave_user = [random.randint(5, 24) for _ in range(18)]

        if now - self.last_t > (0.12 if self.speaking else 0.50):
            if self.paused:
                self.target_scale = random.uniform(0.58, 0.64)
                self.target_halo  = random.uniform(5, 10)
            elif self.speaking:
                self.target_scale = random.uniform(0.98, 1.10)
                self.target_halo  = random.uniform(180, 250)
            elif self.user_speaking:
                self.target_scale = random.uniform(0.88, 0.98)
                self.target_halo  = random.uniform(120, 175)
            elif self._jarvis_state in ("THINKING", "INITIALISING"):
                self.target_scale = random.uniform(0.80, 0.88)
                self.target_halo  = random.uniform(95, 145)
            else:
                self.target_scale = random.uniform(0.72, 0.80)
                self.target_halo  = random.uniform(34, 58)
            self.last_t = now

        sp          = 0.34 if self.speaking else 0.18
        self.scale  += (self.target_scale - self.scale) * sp
        self.halo_a += (self.target_halo   - self.halo_a) * sp

        if self.paused:
            spds = [0.0, 0.0, 0.0, 0.0]
        elif self.speaking:
            spds = [1.6, -1.1, 2.4, -0.7]
        else:
            spds = [0.55, -0.35, 0.90, -0.28]
        for i, spd in enumerate(spds):
            self.rings_spin[i] = (self.rings_spin[i] + spd) % 360

        # Pulse rings
        pspd  = 4.2 if self.speaking else 1.8
        limit = self.FACE * 0.68
        self.pulse_r = [r + pspd for r in self.pulse_r if r + pspd < limit]
        if len(self.pulse_r) < 3 and random.random() < (0.07 if self.speaking else 0.02):
            self.pulse_r.append(0.0)

        for p in self.particles:
            p['x'] = (p['x'] + p['vx']) % self.W
            p['y'] = (p['y'] + p['vy']) % self.H

        if t % 38 == 0:
            self.status_blink = not self.status_blink

        self._draw()
        self.root.after(33, self._animate)

    # ── Yardımcı ─────────────────────────────────────────────────────────────
    @staticmethod
    def _ac(r, g, b, a):
        f = max(0, min(255, int(a))) / 255.0
        return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"

    def _orb_rgb(self):
        state = "PAUSED" if self.paused else self._jarvis_state
        return ORB_COLORS.get(state, ORB_COLORS["LISTENING"])

    @staticmethod
    def _split_summary_lines(text: str, limit: int = 4) -> list[str]:
        raw = (text or "").strip()
        if not raw:
            return []
        raw = raw.replace(" ve ", ", ")
        parts = [part.strip(" .") for part in raw.split(",") if part.strip()]
        return parts[:limit]

    def _kick_brief_refresh(self):
        if self._brief_refresh_busy:
            return
        self._brief_refresh_busy = True
        threading.Thread(target=self._refresh_brief_cards, daemon=True).start()

    def _refresh_brief_cards(self):
        try:
            new_weather = get_weather_data("Istanbul")
            from actions.market import get_live_market_summary
            new_market = get_live_market_summary()
            
            def _apply_brief():
                if new_weather:
                    self._weather_card = new_weather
                if new_market:
                    self._market_data = new_market
                self._brief_refresh_busy = False
                
            self.root.after(0, _apply_brief)
        except Exception:
            self._brief_refresh_busy = False

    def _bar(self, c, x, y, w, h, pct, color):
        c.create_rectangle(x, y, x+w, y+h, fill="#061212", outline=C_DIM, width=1)
        fw = max(1, int(w * pct / 100))
        c.create_rectangle(x+1, y+1, x+fw, y+h-1, fill=color, outline="")

    def _sparkline(self, c, x, y, w, h, data):
        c.create_rectangle(x, y, x+w, y+h, fill="#050e0e", outline=C_DIM, width=1)
        n = len(data)
        if n < 2:
            return
        step = (w - 2) / (n - 1)
        h2   = h - 2
        coords = []
        for i, v in enumerate(data):
            coords.append(x + 1 + i * step)
            coords.append(y + h - 1 - int(h2 * v / 100))
        c.create_line(*coords, fill=C_PRI, width=1, smooth=True)

    def _bracket(self, c, x0, y0, pw, ph, col=None, bl=12):
        col = col or C_PRI
        for bx, by, sx, sy in [(x0, y0, 1, 1), (x0+pw, y0, -1, 1),
                                (x0, y0+ph, 1, -1), (x0+pw, y0+ph, -1, -1)]:
            c.create_line(bx, by, bx+sx*bl, by, fill=col, width=2)
            c.create_line(bx, by, bx, by+sy*bl, fill=col, width=2)

    def _draw_info_card(self, c, x0, y0, pw, ph, title, accent=C_PRI):
        focus = max(0.0, min(1.0, getattr(self, "_card_focus_boost", 0.0)))
        dimmed = bool(getattr(self, "_card_dimmed", False))
        glow = int(55 + 120 * focus)
        border = accent if focus > 0.08 else ("#35504d" if dimmed else self._ac(0, 120, 112, 190))
        fill = "#071111" if dimmed else "#030d0d"
        c.create_rectangle(x0, y0, x0+pw, y0+ph, fill=fill, outline="")
        if focus > 0.08:
            # Sinematik kenar parlaması (Color breathing)
            pulse_sin = math.sin(self.tick * 0.25)
            base_r, base_g, base_b = ORB_COLORS.get(self._jarvis_state, ORB_COLORS["LISTENING"])
            r = min(255, max(0, int(base_r + 40 * pulse_sin)))
            g = min(255, max(0, int(base_g + 40 * math.cos(self.tick * 0.25))))
            b = min(255, max(0, int(base_b + 40 * pulse_sin)))
            for inset in range(4):
                c.create_rectangle(
                    x0-inset*2, y0-inset*2, x0+pw+inset*2, y0+ph+inset*2,
                    outline=self._ac(r, g, b, max(10, glow - inset * 35)),
                    width=1,
                )
            # Köşelere sci-fi hedefleyici (Targeting reticles)
            tl = int(18 + 8 * math.sin(self.tick * 0.3))
            for cx, cy, sx, sy in [(x0-4, y0-4, 1, 1), (x0+pw+4, y0-4, -1, 1), (x0-4, y0+ph+4, 1, -1), (x0+pw+4, y0+ph+4, -1, -1)]:
                c.create_line(cx, cy, cx + sx * tl, cy, fill=C_TEXT, width=2)
                c.create_line(cx, cy, cx, cy + sy * tl, fill=C_TEXT, width=2)
        self._bracket(c, x0, y0, pw, ph, col=border, bl=10)
        title_fill = C_DIM if dimmed else accent
        line_fill = C_DIMMER if dimmed else C_DIM
        c.create_text(x0+14, y0+14, text=title, fill=title_fill,
                      font=font_display(10), anchor="w")
        c.create_line(x0+12, y0+28, x0+pw-12, y0+28, fill=line_fill)

    def _focus_boost_for(self, section: str) -> float:
        if self._panel_focus != section:
            return 0.0
        remaining = self._panel_focus_until - time.time()
        if remaining <= 0:
            return 0.0
        pulse = 0.65 + 0.35 * math.sin(self.tick * 0.12)
        return min(1.0, remaining / 4.0) * pulse

    # ── Health hologram compat (stub) ─────────────────────────────────────────
    def show_health_hologram(self, query: str, data_str: str):
        pass

    def add_ai_task(self, status: str, name: str, col: str = None):
        col = col or C_GREEN
        self._ai_workflow_tasks.appendleft((status, name, col))

    # ── Toast Notifications ───────────────────────────────────────────────────
    def show_notification(self, message: str, level: str = "info"):
        expire = time.time() + 4.0
        self._notifications.append({"text": message, "level": level, "expire": expire})

    def _draw_notifications(self, c):
        now = time.time()
        # Remove expired
        while self._notifications and self._notifications[0]["expire"] < now:
            self._notifications.popleft()
        if not self._notifications:
            return
        nx = self.W - self.RIGHT_W - 20
        ny = HDR_H + 14
        for notif in self._notifications:
            remaining = notif["expire"] - now
            alpha = min(1.0, remaining / 0.5) * 255
            level = notif["level"]
            accent = C_GREEN if level == "success" else C_RED if level == "error" else C_BLUE
            # Card background
            nw, nh = 320, 40
            c.create_rectangle(nx - nw, ny, nx, ny + nh, fill=C_PANEL, outline="")
            self._bracket(c, nx - nw, ny, nw, nh, col=accent, bl=6)
            c.create_text(nx - nw + 12, ny + nh // 2, text=notif["text"],
                          fill=accent, font=font_body(10), anchor="w")
            ny += nh + 8

    # ── Mic Level ─────────────────────────────────────────────────────────────
    def set_mic_level(self, level: float):
        self._mic_level = max(0.0, min(1.0, level))

    # ── Sol panel ─────────────────────────────────────────────────────────────
    def _draw_left_panel(self, c):

        x0 = 10
        y0 = HDR_H + 10
        pw = self.LEFT_W - 18
        gap = 12
        total_h = self.H - HDR_H - FOOTER_H - 20
        pad = 14
        bw = pw - 2 * pad

        cards = [
            ("time", 0.20, "TIME", C_GOLD),
            ("weather", 0.25, "WEATHER", C_BLUE),
            ("market", 0.25, "MARKET INTELLIGENCE", C_GOLD),
            ("system", 0.30, "SYSTEM STATUS", C_PRI),
        ]
        
        if getattr(self, "english_tutor_mode", False):
            cards.append(("tasks", 0.20, "ENGLISH TUTOR", C_ORG2))
            
        card_area_h = total_h - gap * (len(cards) - 1)
        any_focus_active = bool(self._panel_focus) and (self._panel_focus_until > time.time())
        weights = []
        for section, weight, _, _ in cards:
            weights.append(weight + (0.12 if self._focus_boost_for(section) > 0.08 else 0.0))
        total_weight = sum(weights)
        heights = [int(card_area_h * (weight / total_weight)) for weight in weights]
        heights[-1] += card_area_h - sum(heights)

        current_y = y0
        for (section, _, title, accent), ph in zip(cards, heights):
            focus_boost = self._focus_boost_for(section)
            dimmed = any_focus_active and focus_boost <= 0.08
            shift_x = int(14 * focus_boost)
            extra_w = int(22 * focus_boost)
            section_x = x0 + shift_x
            section_pw = pw + extra_w
            section_pad = pad + int(2 * focus_boost)
            section_bw = section_pw - 2 * section_pad
            muted_label   = C_DIM if dimmed else C_MID
            muted_text    = C_DIM if dimmed else C_TEXT
            muted_primary = C_DIM if dimmed else C_PRI
            muted_blue    = C_DIM if dimmed else C_BLUE
            muted_green   = C_DIM if dimmed else C_GREEN
            muted_gold    = C_DIM if dimmed else C_GOLD
            muted_warn    = C_DIM if dimmed else C_ORG2
            muted_red     = C_DIM if dimmed else C_RED
            self._card_focus_boost = focus_boost
            self._card_dimmed = dimmed
            self._draw_info_card(c, section_x, current_y, section_pw, ph, title, accent=accent if not dimmed else "#72807f")

            if section == "time":
                # Header Timezone (y=14)
                tz_hours = -time.timezone // 3600
                tz_str = f"UTC {'+' if tz_hours>=0 else ''}{tz_hours:02d}:00 ISTANBUL"
                c.create_text(section_x+section_pw-section_pad, current_y+14, text=tz_str,
                              fill=muted_gold, font=font_body_bold(9), anchor="e")

                # Left: Digital Clock & Date
                cy = current_y + int(ph * 0.48)
                c.create_text(section_x+section_pad, cy, text=time.strftime("%H:%M"),
                              fill=muted_primary, font=font_display(36 if focus_boost > 0.08 else 34), anchor="w")
                c.create_text(section_x+section_pad+120, cy-8, text=time.strftime(":%S"),
                              fill=muted_gold, font=font_body_bold(14), anchor="w")
                ampm = time.strftime("%p").strip() or "24H"
                c.create_text(section_x+section_pad+120, cy+10, text=ampm,
                              fill=muted_label, font=font_body_bold(10), anchor="w")

                # Date below
                dy = current_y + int(ph * 0.82)
                c.create_text(section_x+section_pad, dy, text=time.strftime("%A, %B %d").upper(),
                              fill=muted_text, font=font_body_bold(11), anchor="w")
                c.create_text(section_x+section_pw-section_pad, dy, text="● CLOCK SYNCED",
                              fill=muted_green, font=font_body_bold(9), anchor="e")

            elif section == "weather":
                # Row 1: Temp, Condition, City
                ry1 = current_y + int(ph * 0.30)
                temp_s = self._weather_card.get("temp", "16°C")
                cond_s = self._weather_card.get("condition", "Clear Sky")
                city_s = self._weather_card.get("city", "Istanbul").upper()
                
                cond_title = cond_s.title()
                if len(cond_title) > 15:
                    cond_title = cond_title[:14] + "..."
                    
                c.create_text(section_x+section_pad, ry1, text=temp_s,
                              fill=muted_primary, font=font_display(28 if focus_boost > 0.08 else 26), anchor="w")
                c.create_text(section_x+section_pad+90, ry1, text=cond_title,
                              fill=muted_blue, font=font_body_bold(13), anchor="w")
                c.create_text(section_x+section_pw-section_pad, ry1, text=city_s,
                              fill=muted_label, font=font_body_bold(10), anchor="e")

                # Row 2: Feels like, Humidity, Wind
                ry2 = current_y + int(ph * 0.52)
                fl_s = self._weather_card.get("feels_like", "14°")
                hum_s = self._weather_card.get("humidity", "63%")
                wnd_s = self._weather_card.get("wind", "11 km/h")
                details_text = f"Feels like {fl_s}   ·   Humidity {hum_s}   ·   Wind {wnd_s}"
                c.create_text(section_x+section_pad, ry2, text=details_text,
                              fill=muted_text, font=font_body(10), anchor="w")

                # Row 3: Air Quality
                ry3 = current_y + int(ph * 0.65)
                aqi_s = self._weather_card.get("aqi", "Good")
                c.create_text(section_x+section_pad, ry3, text="Air Quality:",
                              fill=muted_label, font=font_body(10), anchor="w")
                c.create_text(section_x+section_pad+76, ry3, text=aqi_s,
                              fill=muted_green, font=font_body_bold(10), anchor="w")

                # Divider line before suggestion
                div_y = current_y + int(ph * 0.75)
                c.create_line(section_x+section_pad, div_y, section_x+section_pw-section_pad, div_y, fill=C_DIM)

                # Row 4: Suggestion
                ry4 = div_y + 8  # Move slightly below the divider
                sugg_s = self._weather_card.get("suggestion", "Light jacket recommended.")
                c.create_text(section_x+section_pad, ry4, text=f"Suggestion: {sugg_s}",
                              fill=muted_gold, font=font_body_bold(10), anchor="nw",
                              width=section_pw - 2 * section_pad)

            elif section == "market":
                # Header STATUS
                m_status = "ONLINE" if self._market_data else "CONNECTING..."
                c.create_text(section_x+section_pw-section_pad, current_y+14, text=m_status,
                              fill=muted_green if self._market_data else muted_warn, font=font_body_bold(9), anchor="e")
                              
                my = current_y + int(ph * 0.24)
                step = max(15, int((ph * 0.70) / 6))
                m_items = list(self._market_data.items())[:6] if self._market_data else []
                
                if not m_items:
                    c.create_text(section_x+section_pad, my, text="Piyasa verileri alınıyor...", fill=muted_text, font=font_body(10), anchor="w")
                else:
                    for sym, info in m_items:
                        name_s = info["name"]
                        price_s = info["price"]
                        chg = info["change_pct"]
                        
                        arrow = "▲" if chg >= 0 else "▼"
                        col = C_GREEN if chg >= 0 else C_RED
                        if dimmed:
                            col = muted_green if chg >= 0 else muted_red
                            
                        # Name (e.g. Bitcoin)
                        c.create_text(section_x+section_pad, my, text=name_s, fill=muted_label, font=font_body_bold(10), anchor="w")
                        # Price + Change
                        c.create_text(section_x+section_pw-section_pad, my, text=f"{price_s}  {arrow} {abs(chg):.1f}%", fill=col, font=font_body_bold(10), anchor="e")
                        my += step

            elif section == "system":
                # Header UPTIME
                uptime = int(time.time() - self._started_at)
                up_min, up_sec = divmod(uptime, 60)
                up_hr, up_min = divmod(up_min, 60)
                c.create_text(section_x+section_pw-section_pad, current_y+14, text=f"UPTIME: {up_hr:02d}:{up_min:02d}:{up_sec:02d}",
                              fill=muted_primary, font=font_body_bold(9), anchor="e")

                # 4 Core System Metrics
                cy = current_y + int(ph * 0.22)
                sys_step = max(20, int((ph * 0.56) / 4))
                bar_off = min(12, int(sys_step * 0.45))
                for label, key, unit in [("CPU LOAD", "cpu", "%"), ("RAM USAGE", "ram", "%"), ("STORAGE", "disk", "%"), ("POWER / BATTERY", "battery", "%")]:
                    val = self._stats[key]
                    col = C_RED if val > 85 and key != "battery" else C_ORG if val > 65 and key != "battery" else (C_RED if key == "battery" and val < 20 else C_GREEN if key == "battery" else C_PRI)
                    if dimmed:
                        col = muted_red if col == C_RED else muted_warn if col == C_ORG else muted_green if col == C_GREEN else muted_primary
                    c.create_text(section_x+section_pad, cy, text=label, fill=muted_label, font=font_body_bold(10), anchor="w")
                    c.create_text(section_x+section_pw-section_pad, cy, text=f"{val:.0f}{unit}", fill=col, font=font_body_bold(10), anchor="e")
                    self._bar(c, section_x+section_pad, cy+bar_off, section_bw, 7, val, col)
                    cy += sys_step

                # Network Section Divider
                net_div = current_y + int(ph * 0.84)
                c.create_line(section_x+section_pad, net_div, section_x+section_pw-section_pad, net_div, fill=C_DIM)

                # Network Stats
                net_y = current_y + int(ph * 0.92)
                up = self._stats["net_up"]
                down = self._stats["net_down"]
                up_s = f"{up:.1f} KB/s" if up < 1000 else f"{up/1024:.1f} MB/s"
                down_s = f"{down:.1f} KB/s" if down < 1000 else f"{down/1024:.1f} MB/s"
                c.create_text(section_x+section_pad, net_y, text=f"▲ UP: {up_s}", fill=muted_warn, font=font_body_bold(10), anchor="w")
                c.create_text(section_x+section_pw//2, net_y, text="NETWORK I/O", fill=muted_label, font=font_body(9), anchor="center")
                c.create_text(section_x+section_pw-section_pad, net_y, text=f"▼ DOWN: {down_s}", fill=muted_green, font=font_body_bold(10), anchor="e")

            elif section == "tasks":
                if getattr(self, "english_tutor_mode", False):
                    lvl = self.english_tutor_stats.get("level", "B2 Upper")
                    c.create_text(section_x+section_pw-section_pad, current_y+14, text=f"LEVEL: {lvl}", fill=muted_gold, font=font_body_bold(9), anchor="e")
                    
                    # Fluency Score
                    ry1 = current_y + int(ph * 0.32)
                    fl = self.english_tutor_stats.get("fluency", "100%")
                    c.create_text(section_x+section_pad, ry1, text="Fluency Score", fill=muted_label, font=font_body(10), anchor="w")
                    c.create_text(section_x+section_pad+110, ry1, text=fl, fill=muted_green, font=font_body_bold(10), anchor="w")
                    
                    # Last correction
                    ry2 = current_y + int(ph * 0.55)
                    c.create_text(section_x+section_pad, ry2, text="Last Feedback:", fill=muted_label, font=font_body(10), anchor="w")
                    last_corr = self.english_tutor_stats.get("last_correction", "Listening...") or "Listening..."
                    if len(last_corr) > 30:
                        last_corr = last_corr[:27] + "..."
                    c.create_text(section_x+section_pad+110, ry2, text=last_corr, fill=muted_warn, font=font_body_bold(10), anchor="w")
                    
                    # New Words
                    ry3 = current_y + int(ph * 0.78)
                    c.create_text(section_x+section_pad, ry3, text="Vocab Bank:", fill=muted_label, font=font_body(10), anchor="w")
                    words = list(self.english_tutor_stats.get("new_words", []))
                    if not words:
                        words = ["- Active listening -"]
                    step_y = max(15, int((ph * 0.20) / max(1, len(words))))
                    wy = ry3
                    for w in words[:3]: # Karttan dışarı taşmaması için en güncel 3 kelimeyi al
                        c.create_text(section_x+section_pad+110, wy, text=w, fill=muted_primary, font=font_body_bold(10), anchor="w")
                        wy += step_y
                else:
                    pass
                    
            elif section == "neural_logs":
                # Kayan Matrix log akışı çizimi
                ly = current_y + ph - 24 # En alttan başla
                min_y = current_y + 40   # Başlığın altına kadar izin ver
                
                logs = list(self.neural_logs)
                
                # Yanıp sönen imleç
                cursor = "█" if int(time.time() * 2) % 2 == 0 else ""
                c.create_text(section_x+section_pad, ly, text=f"> {cursor}", fill=muted_primary, font=font_body_bold(10), anchor="w")
                ly -= 20
                
                # Logları sondan başa doğru çiz (aşağıdan yukarıya)
                for i, (tag, text, base_col) in enumerate(reversed(logs)):
                    if ly < min_y:
                        break # Kutu sınırını aştıysa gerisini çizme (Taşmayı önle)
                        
                    # Fade efekti: En sonuncu parlak, eskiler soluk
                    if dimmed:
                        col = muted_text
                        tag_col = muted_label
                    else:
                        # Ana metin rengini kısıyoruz
                        col = C_DIM if i > 1 else C_TEXT
                        tag_col = base_col
                        
                    # Önce TAG yazalım
                    tag_str = f"[{tag}]"
                    tag_id = c.create_text(section_x+section_pad, ly, text=tag_str, fill=tag_col, font=font_body_bold(9), anchor="w")
                    bbox = c.bbox(tag_id)
                    tag_w = bbox[2] - bbox[0] + 6
                    
                    # Sonra metni yazalım (Çok uzunsa kes)
                    if len(text) > 60:
                        text = text[:57] + "..."
                        
                    c.create_text(section_x+section_pad+tag_w, ly, text=text, fill=col, font=font_body(9), anchor="w")
                    ly -= 18

            current_y += ph + gap

        self._card_focus_boost = 0.0
        self._card_dimmed = False

    # ── Sağ panel ─────────────────────────────────────────────────────────────
    def _draw_right_panel(self, c):
        x0  = self.CHAT_PANEL_X
        y0  = self.CHAT_PANEL_Y
        pw  = self.CHAT_PANEL_W
        ph  = self.CHAT_PANEL_H
        pad = 10

        c.create_rectangle(x0, y0, x0+pw, y0+ph, fill=C_PANEL, outline="")
        self._bracket(c, x0, y0, pw, ph, col=C_MID)

        if self.paused:
            sc, st = C_MID, "PAUSED"
        else:
            sc, st = self._state_color(self._jarvis_state), self._jarvis_state

        c.create_text(x0+14, y0+16, text="CONVERSATION", fill=C_PRI,
                      font=font_display(11), anchor="w")
        c.create_text(x0+pw-pad, y0+16, text=st, fill=sc,
                      font=font_body_bold(10), anchor="e")
        c.create_line(x0+pad, y0+28, x0+pw-pad, y0+28, fill=C_DIM)

    # ── ORB (ana çizim) ───────────────────────────────────────────────────────
    def _draw_orb(self, c):
        state = "PAUSED" if self.paused else self._jarvis_state
        t    = self.tick
        speak_pulse = 1.0
        if self.speaking:
            speak_pulse = 1.0 + 0.12 * math.sin(t * 0.23) + 0.05 * math.sin(t * 0.11 + 1.2)
        elif self.user_speaking:
            speak_pulse = 1.0 + 0.06 * math.sin(t * 0.18 + 0.7)
        elif state in ("THINKING", "INITIALISING"):
            speak_pulse = 1.0 + 0.03 * math.sin(t * 0.10)
        else:
            speak_pulse = 1.0 + 0.01 * math.sin(t * 0.07)

        move_x = 0
        move_y = 0
        if self.user_speaking:
            move_x = int(6 * math.sin(t * 0.06))
            move_y = int(4 * math.cos(t * 0.09 + 0.5))
        elif state in ("THINKING", "INITIALISING"):
            move_x = int(3 * math.sin(t * 0.045))
            move_y = int(2 * math.cos(t * 0.05 + 0.4))

        FCX  = self.FCX + move_x
        FCY  = self.FCY + move_y
        FW   = int(self.FACE * self.scale * speak_pulse)
        R, G, B = self._orb_rgb()
        ha   = self.halo_a
        field_r = int(FW * 0.49)
        inner_r = int(FW * 0.34)
        activity = (
            0.10 if self.paused else
            1.00 if self.speaking else
            0.78 if self.user_speaking else
            0.62 if state in ("THINKING", "INITIALISING") else
            0.26
        )
        if state in ("THINKING", "INITIALISING"):
            accent_rgb = (255, 210, 72)
        elif self.speaking:
            accent_rgb = (170, 220, 255)
        elif self.user_speaking:
            accent_rgb = (118, 200, 255)
        else:
            accent_rgb = (120, 255, 185)

        # Pulse rings
        for pr in self.pulse_r:
            alpha = max(0, int(160 * (1.0 - pr / (FW * 0.70))))
            rr = int(pr + field_r * 0.96)
            c.create_oval(
                FCX-rr, FCY-rr, FCX+rr, FCY+rr,
                outline=self._ac(R, G, B, alpha),
                width=1,
            )

        # Large outer glow
        if not self.paused:
            for i in range(10, 0, -1):
                frac = i / 10
                rr = int(field_r * (1.02 + 0.045 * frac))
                alpha = int(ha * 0.10 * frac)
                if self.speaking:
                    ox = 0
                    oy = 0
                else:
                    ox = int(3 * math.sin(t * 0.010 + i))
                    oy = int(3 * math.cos(t * 0.009 + i * 1.3))
                c.create_oval(
                    FCX-rr+ox, FCY-rr+oy, FCX+rr+ox, FCY+rr+oy,
                    outline=self._ac(R, G, B, alpha),
                    width=3,
                )

        # Structural circles
        for frac, width, alpha_mult in (
            (1.00, 2, 0.34),
            (0.90, 2, 0.24),
            (0.76, 1, 0.18),
            (0.62, 1, 0.12),
        ):
            rr = int(field_r * frac)
            c.create_oval(
                FCX-rr, FCY-rr, FCX+rr, FCY+rr,
                outline=self._ac(R, G, B, int(ha * alpha_mult * (0.4 if self.paused else 1.0))),
                width=width,
            )

        speak_shell_push = 1.16 if self.speaking else 1.07 if self.user_speaking else 1.0
        # Orb shell particles
        shell_r = field_r * 0.93 * speak_shell_push
        for idx, sp in enumerate(self.orb_shell_particles):
            angle = sp['angle'] + t * sp['speed'] * (2.8 if self.speaking else 1.6 if self.user_speaking else 1.1)
            wobble = 1.0 + (0.07 if self.speaking else 0.035) * math.sin(t * 0.08 + sp['phase'])
            x = FCX + math.cos(angle) * shell_r * wobble
            y = FCY + math.sin(angle) * shell_r * wobble
            alpha = int((70 + 120 * sp['glow']) * (0.26 if self.paused else 0.52 + activity * 0.45))
            if idx % 9 == 0 and not self.paused:
                col = self._ac(accent_rgb[0], accent_rgb[1], accent_rgb[2], min(255, alpha + 30))
            else:
                col = self._ac(R, G, B, alpha)
            pr = sp['size'] * (1.0 + 0.24 * math.sin(t * 0.05 + sp['phase']))
            c.create_oval(x-pr, y-pr, x+pr, y+pr, fill=col, outline="")

        # Rotating segmented arcs
        arc_r1 = int(field_r * 0.96)
        arc_r2 = int(field_r * 0.78)
        for start, extent, width, accent in (
            (self.rings_spin[0], 52 if self.speaking else 34, 3, False),
            ((self.rings_spin[0] + 148) % 360, 26, 2, True),
            ((self.rings_spin[2] + 28) % 360, 64 if self.user_speaking else 40, 3, False),
            ((self.rings_spin[2] + 212) % 360, 18, 2, True),
        ):
            rr = arc_r1 if width == 3 else arc_r2
            if accent and not self.paused:
                col = self._ac(accent_rgb[0], accent_rgb[1], accent_rgb[2], int(120 + 80 * activity))
            else:
                col = self._ac(R, G, B, int(ha * (1.2 if width == 3 else 0.7)))
            c.create_arc(
                FCX-rr, FCY-rr, FCX+rr, FCY+rr,
                start=start, extent=extent,
                outline=col, width=width, style="arc",
            )

        # Particle orb field
        field_limit = inner_r * (
            0.82 if self.paused else
            1.36 if self.speaking else
            1.16 if self.user_speaking else
            1.0
        )
        for idx, p in enumerate(self.orb_particles):
            speed_mult = (
                0.10 if self.paused else
                3.10 if self.speaking else
                2.00 if self.user_speaking else
                1.10
            )
            angle = p['angle'] + t * p['speed'] * speed_mult
            wobble = 1.0 + (0.30 if self.speaking else 0.18) * math.sin(t * p['wobble'] + p['phase'])
            orbit = field_limit * p['orbit'] * wobble
            depth = 0.5 + 0.5 * math.sin(angle * 2.0 + t * 0.013 + p['phase'])
            y_squash = 0.62 + depth * 0.38
            drift = (8.0 if self.speaking else 5.0 if self.user_speaking else 4.0) * p['depth']
            x = FCX + math.cos(angle) * orbit + math.sin(t * 0.011 + p['phase']) * drift
            y = FCY + math.sin(angle) * orbit * y_squash + math.cos(t * 0.010 + p['phase']) * drift
            base_alpha = int((18 + 155 * p['depth']) * (0.24 + activity * 0.86) * (0.45 + depth * 0.75))
            if self.paused:
                base_alpha = int(base_alpha * 0.40)
            if idx % 11 == 0 and not self.paused:
                col = self._ac(accent_rgb[0], accent_rgb[1], accent_rgb[2], min(255, base_alpha + 25))
            elif self.user_speaking and idx % 7 == 0:
                col = self._ac(120, 205, 255, min(255, base_alpha + 20))
            else:
                col = self._ac(R, G, B, base_alpha)
            pr = p['size'] * (0.70 if self.paused else 0.90 + depth * 0.65 + 0.30 * activity * p['depth'])
            c.create_oval(x-pr, y-pr, x+pr, y+pr, fill=col, outline="")
            if idx % 18 == 0 and not self.paused:
                c.create_line(
                    FCX + (x-FCX) * 0.18,
                    FCY + (y-FCY) * 0.18,
                    x, y,
                    fill=self._ac(R, G, B, int(18 + 35 * p['depth'] * activity)),
                    width=1,
                )

        # Center void keeps the orb airy instead of lens-like.
        void_r = int(inner_r * (0.18 if self.paused else 0.12))
        if void_r > 0:
            c.create_oval(
                FCX-void_r, FCY-void_r, FCX+void_r, FCY+void_r,
                fill=C_BG,
                outline="",
            )

    # ── Ana çizim ─────────────────────────────────────────────────────────────
    def _draw(self):
        c  = self.bg
        W  = self.W
        H  = self.H
        t  = self.tick
        c.delete("!static_grid")

        # ── Arka plan ────────────────────────────────────────────────────────

        # Tarama çizgisi (yavaş, çok soluk)
        scan_y = (t * 0.7) % (H + 60) - 30
        for i in range(2):
            ly = (scan_y + i * 20) % H
            c.create_line(0, ly, W, ly+35, fill=C_DIMMER, width=1)

        # Partiküller
        R, G, B = self._orb_rgb()
        for p in self.particles:
            if self.speaking:
                col = self._ac(255, 110, 0, p['a'])
            else:
                col = self._ac(R, G, B, p['a'])
            r = p['r']
            c.create_oval(p['x']-r, p['y']-r, p['x']+r, p['y']+r,
                          fill=col, outline="")

        # ── Bölücü çizgiler (ince, soluk) ────────────────────────────────────
        c.create_line(self.LEFT_W, HDR_H, self.LEFT_W, H-FOOTER_H,
                      fill=C_DIM, width=1)
        c.create_line(W-self.RIGHT_W, HDR_H, W-self.RIGHT_W, H-FOOTER_H,
                      fill=C_DIM, width=1)

        # ── Yan paneller ──────────────────────────────────────────────────────
        self._draw_left_panel(c)
        self._draw_right_panel(c)

        # ── Orb ──────────────────────────────────────────────────────────────
        self._draw_orb(c)

        state_label = "PAUSED" if self.paused else self._jarvis_state
        state_col = self._state_color(state_label)
        # Mic level indicator under orb
        mic_bar_w = min(180, int(self.FACE * 0.35))
        mic_x = self.FCX - mic_bar_w // 2
        mic_y = self.CTRL_Y - 42
        mic_pct = self._mic_level * 100
        mic_col = C_GREEN if mic_pct < 60 else C_GOLD if mic_pct < 85 else C_RED
        c.create_text(mic_x - 24, mic_y + 4, text="🎤", fill=C_MID, font=font_body(9), anchor="w")
        self._bar(c, mic_x, mic_y, mic_bar_w, 6, mic_pct, mic_col)
        c.create_text(self.FCX, self.CTRL_Y - 20, text=f"● {state_label.title()}",
                      fill=state_col, font=font_body_bold(11))

        # ── Notifications (toast) ────────────────────────────────────────────
        self._draw_notifications(c)

        # ── HEADER ───────────────────────────────────────────────────────────
        c.create_rectangle(0, 0, W, HDR_H, fill=C_BG, outline="")
        c.create_line(0, HDR_H, W, HDR_H, fill=C_MID, width=1)
        base_r, base_g, base_b = ORB_COLORS.get(self._jarvis_state, ORB_COLORS["LISTENING"])
        for i in range(3):
            a = 60 - i * 18
            c.create_line(0, HDR_H-1-i, W, HDR_H-1-i,
                          fill=self._ac(base_r, base_g, base_b, a), width=1)

        # Sol: tarih/saat
        c.create_text(22, 22, text=time.strftime("%H:%M:%S"),
                      fill=C_PRI, font=font_display(14), anchor="w")
        c.create_text(22, 46, text=time.strftime("%d %B %Y · %A").upper(),
                      fill=C_TEXT, font=font_body(9), anchor="w")

        # Orta: başlık
        c.create_text(W//2, 24, text=SYSTEM_NAME,
                      fill=C_PRI, font=font_display(18))
        c.create_text(W//2, 48, text="Just A Rather Very Intelligent System",
                      fill=C_TEXT, font=font_body(9))

        # Sağ: durum indikatörü + pil
        indicator_state = "PAUSED" if self.paused else self._jarvis_state
        ind_col = self._state_color(indicator_state)
        indicator_text = self._state_badge_text(indicator_state)
        sym = "●" if self.status_blink else "○"
        batt = self._stats.get("battery", 100)
        batt_icon = "⚡" if batt > 80 else "🔋" if batt > 20 else "🪫"
        c.create_text(W-140, 22, text=f"{sym}  {indicator_text}",
                      fill=ind_col, font=font_body_bold(11), anchor="e")
        c.create_text(W-140, 46, text=f"{batt_icon} {batt:.0f}%  ·  {MODEL_BADGE}",
                      fill=C_TEXT, font=font_body(9), anchor="e")

        # ── PENCERE KONTROL BUTONLARI ──
        c.create_rectangle(W-125, 6, W-90, 32, fill=C_PANEL, outline=C_MID)
        c.create_text(W-107, 18, text="_", fill=C_TEXT, font=font_display(12))
        
        c.create_rectangle(W-85, 6, W-50, 32, fill=C_PANEL, outline=C_MID)
        c.create_text(W-67, 18, text="□" if not getattr(self, "_fullscreen", True) else "❐", fill=C_TEXT, font=font_display(12))
        
        c.create_rectangle(W-45, 6, W-10, 32, fill="#200505", outline=C_RED)
        c.create_text(W-27, 18, text="✕", fill=C_RED, font=font_display(12))

        # ── FOOTER ───────────────────────────────────────────────────────────
        c.create_rectangle(0, H-FOOTER_H, W, H, fill=C_BG, outline="")
        c.create_line(0, H-FOOTER_H, W, H-FOOTER_H, fill=C_DIM, width=1)
        # Sol: wake word durumu
        c.create_text(18, H-13, fill=C_GREEN, font=font_body(9),
                      text="🟢 \"Hey Jarvis\" dinleniyor", anchor="w")
        # Orta
        c.create_text(W//2, H-13, fill=C_TEXT, font=font_body(9),
                      text="JARVIS · Windows Edition · Realtime Voice Core")
        # Sağ: kısayollar
        c.create_text(W-18, H-13, fill=C_TEXT, font=font_body(9),
                      text="[F4] MUTE  [F5] PAUSE  [ESC] EXIT", anchor="e")

    def wait_for_api_key(self):
        while not self._api_key_ready:
            time.sleep(0.1)

    def _show_setup_ui(self, edit_mode: bool = False):
        self._close_setup_ui()

        self.setup_frame = tk.Frame(self.root, bg=C_PANEL,
                                    highlightbackground=C_PRI,
                                    highlightthickness=1)
        setup_w = min(760, max(560, int(self.W * 0.42)))
        setup_h = min(520, max(430, int(self.H * 0.44)))
        self.setup_frame.place(relx=0.5, rely=0.5, anchor="center", width=setup_w, height=setup_h)
        self.setup_frame.pack_propagate(False)

        title = "◈ API AYARLARI" if edit_mode else "◈ İLK KURULUM GEREKLİ"
        subtitle = (
            "Gemini yapay zeka erisim anahtarini guncelleyin."
            if edit_mode else
            "Sistemin calismasi icin Gemini API anahtarini girin."
        )
        config = load_app_config()

        tk.Label(self.setup_frame, text=title,
                 fg=C_PRI, bg="#00080d", font=font_display(20)).pack(pady=(28, 6))
        tk.Label(self.setup_frame, text=subtitle,
                 fg=C_MID, bg="#00080d", font=font_body(13)).pack(pady=(0, 24))
        tk.Label(self.setup_frame, text="GEMINI API KEY",
                 fg=C_TEXT, bg="#00080d", font=font_body(12)).pack(pady=(8, 4))

        self.api_entry = tk.Entry(
            self.setup_frame, width=60,
            fg=C_TEXT, bg="#000d12", insertbackground=C_TEXT,
            borderwidth=0, font=font_body(14), show="*")
        self.api_entry.pack(pady=(0, 24), ipady=5)

        current_key = str(config.get("gemini_api_key", "") or "")
        if current_key:
            self.api_entry.insert(0, current_key)

        self.youtube_api_entry = None
        self.youtube_handle_entry = None

        buttons = tk.Frame(self.setup_frame, bg="#00080d")
        buttons.pack(pady=14)

        tk.Button(buttons, text="▸ KAYDET",
                  command=self._save_api_key, bg=C_BG, fg=C_PRI,
                  activebackground="#003344", font=font_body_bold(13),
                  borderwidth=0, padx=24, pady=10).pack(side="left", padx=8)

        if edit_mode:
            tk.Button(buttons, text="KAPAT",
                      command=self._close_setup_ui, bg="#08111a", fg=C_TEXT,
                      activebackground="#10202b", font=font_body_bold(13),
                      borderwidth=0, padx=24, pady=10).pack(side="left", padx=8)

    def _save_api_key(self):
        was_ready = self._api_key_ready
        key = self.api_entry.get().strip() if self.api_entry else ""
        if not key:
            return
        save_app_config(
            {
                "gemini_api_key": key,
                "voice": self._current_voice,
            }
        )
        self._close_setup_ui()
        self._api_key_ready = True
        self._refresh_settings_status()
        if was_ready:
            self.write_log("SYS: API ayarlari guncellendi.")
        else:
            self.set_state("LISTENING")
            self.write_log("SYS: JARVIS hazır. Dinliyorum...")



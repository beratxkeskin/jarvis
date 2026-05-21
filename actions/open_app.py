"""
Uygulama acma - Windows Shell, App Paths ve URI protokolleri ile calisir.
"""

from __future__ import annotations

import subprocess
import psutil

from actions.windows_utils import app_path_from_registry, find_executable, open_path, open_url


APP_ALIASES = {
    "edge": {"exe": ["msedge.exe"], "uri": "microsoft-edge:"},
    "chrome": {"exe": ["chrome.exe"]},
    "firefox": {"exe": ["firefox.exe"]},
    "terminal": {"exe": ["wt.exe", "powershell.exe", "cmd.exe"]},
    "powershell": {"exe": ["powershell.exe"]},
    "cmd": {"exe": ["cmd.exe"]},
    "explorer": {"exe": ["explorer.exe"]},
    "finder": {"exe": ["explorer.exe"]},
    "spotify": {"exe": ["Spotify.exe"], "uri": "spotify:"},
    "vscode": {"exe": ["Code.exe"], "registry": "Code.exe"},
    "vs code": {"exe": ["Code.exe"], "registry": "Code.exe"},
    "code": {"exe": ["Code.exe"], "registry": "Code.exe"},
    "notion": {"exe": ["Notion.exe"]},
    "slack": {"exe": ["slack.exe"]},
    "discord": {"exe": ["Discord.exe"]},
    "whatsapp": {"exe": ["WhatsApp.exe"], "uri": "whatsapp:"},
    "telegram": {"exe": ["Telegram.exe"]},
    "zoom": {"exe": ["Zoom.exe"]},
    "mail": {"uri": "mailto:"},
    "calendar": {"uri": "outlookcal:"},
    "takvim": {"uri": "outlookcal:"},
    "notes": {"exe": ["notepad.exe"]},
    "notlar": {"exe": ["notepad.exe"]},
    "music": {"uri": "mswindowsmusic:"},
    "muzik": {"uri": "mswindowsmusic:"},
    "photos": {"uri": "ms-photos:"},
    "fotograflar": {"uri": "ms-photos:"},
    "maps": {"uri": "bingmaps:"},
    "haritalar": {"uri": "bingmaps:"},
    "calculator": {"exe": ["calc.exe"]},
    "hesap makinesi": {"exe": ["calc.exe"]},
    "settings": {"uri": "ms-settings:"},
    "ayarlar": {"uri": "ms-settings:"},
    "task manager": {"exe": ["taskmgr.exe"]},
    "gorev yoneticisi": {"exe": ["taskmgr.exe"]},
    "paint": {"exe": ["mspaint.exe"]},
    "word": {"exe": ["WINWORD.EXE"]},
    "excel": {"exe": ["EXCEL.EXE"]},
    "powerpoint": {"exe": ["POWERPNT.EXE"]},
    "figma": {"exe": ["Figma.exe"]},
    "postman": {"exe": ["Postman.exe"]},
    "docker": {"exe": ["Docker Desktop.exe"]},
    "youtube": {"uri": "https://www.youtube.com"},
    "chatgpt": {"uri": "https://chatgpt.com"},
    "github": {"uri": "https://github.com"},
    "google": {"uri": "https://www.google.com"},
    "linkedin": {"uri": "https://www.linkedin.com"},
    "twitter": {"uri": "https://x.com"},
    "x": {"uri": "https://x.com"},
    "instagram": {"uri": "https://www.instagram.com"},
    "netflix": {"uri": "https://www.netflix.com"},
    "prime video": {"uri": "https://www.primevideo.com"},
    "prime": {"uri": "https://www.primevideo.com"},
    "gemini": {"uri": "https://gemini.google.com"},
    "stackoverflow": {"uri": "https://stackoverflow.com"},
    "reddit": {"uri": "https://www.reddit.com"},
    "twitch": {"uri": "https://www.twitch.tv"},
    "steam": {"exe": ["steam.exe"], "uri": "steam://open/main"},
    "epic games": {"exe": ["EpicGamesLauncher.exe"]},
    "cs2": {"uri": "steam://rungameid/730"},
    "counter strike": {"uri": "steam://rungameid/730"},
    "dota 2": {"uri": "steam://rungameid/570"},
    "pubg": {"uri": "steam://rungameid/578080"},
    "gta 5": {"uri": "steam://rungameid/271590"},
    "cyberpunk": {"uri": "steam://rungameid/1091500"},
    "valorant": {"exe": ["VALORANT.exe", "RiotClientServices.exe"]},
    "league of legends": {"exe": ["LeagueClient.exe"]},
    "lol": {"exe": ["LeagueClient.exe"]},
}


def _launch_known(spec: dict) -> bool:
    if spec.get("uri"):
        try:
            open_url(str(spec["uri"]))
            return True
        except Exception:
            pass

    registry_name = spec.get("registry")
    if registry_name:
        path = app_path_from_registry(str(registry_name))
        if path:
            open_path(path)
            return True

    exe_names = list(spec.get("exe", []))
    if exe_names:
        registry_path = None
        for exe_name in exe_names:
            registry_path = app_path_from_registry(exe_name)
            if registry_path:
                break
        path = registry_path or find_executable(exe_names)
        if path:
            subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    return False


def open_app(app_name: str) -> str:
    if not app_name:
        return "Uygulama adi belirtilmedi."

    normalized = app_name.lower().strip()
    spec = APP_ALIASES.get(normalized)

    try:
        if spec and _launch_known(spec):
            return f"{app_name} acildi."

        if normalized.startswith("http://") or normalized.startswith("https://") or normalized.endswith(".com") or normalized.endswith(".org") or normalized.endswith(".net") or normalized.endswith(".io") or normalized.endswith(".gov") or normalized.endswith(".edu"):
            target_url = normalized if normalized.startswith("http") else f"https://{normalized}"
            open_url(target_url)
            return f"Web adresi acildi: {target_url}"

        # Son sans: Windows Shell, exe adi, kisayol veya dosya yolu olarak dene.
        direct = app_path_from_registry(app_name) or find_executable([app_name, f"{app_name}.exe"])
        if direct:
            subprocess.Popen([direct], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"{app_name} acildi."
        open_path(app_name)
        return f"{app_name} acildi."
    except Exception:
        # Eger lokalde .exe veya protokol bulunamadiysa, Google aramasina yonlendir.
        from urllib.parse import quote
        search_query = quote(app_name)
        fallback_url = f"https://www.google.com/search?q={search_query}"
        open_url(fallback_url)
        return f"'{app_name}' sistemde bulunamadi, tarayicida aratildi."


def close_app(app_name: str) -> str:
    if not app_name:
        return "Uygulama adi belirtilmedi."

    normalized = app_name.lower().strip()
    spec = APP_ALIASES.get(normalized)

    target_exes = []
    if spec:
        target_exes.extend([exe.lower() for exe in spec.get("exe", [])])
        if "calc.exe" in target_exes:
            target_exes.append("calculatorapp.exe")

    if not target_exes:
        target_exes.append(f"{normalized}.exe")
        target_exes.append(normalized)

    killed = 0
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info.get('name', '').lower()
            if not name:
                continue
            
            # Tam eslesme veya icinde gecme
            if any(t == name or t in name for t in target_exes) or normalized == name.replace('.exe', ''):
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if killed > 0:
        return f"{app_name} kapatildi."
    
    return f"'{app_name}' adinda calisan bir uygulama bulunamadi."

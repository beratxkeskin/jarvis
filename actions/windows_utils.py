"""
Windows helpers shared by JARVIS actions.

This module centralizes Windows shell, clipboard and automation calls.
It uses Windows shell integration, winreg, ctypes and
PyAutoGUI where direct automation is needed.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path


def open_url(url: str) -> None:
    if not url:
        return
    try:
        os.startfile(url)  # type: ignore[attr-defined]
    except Exception:
        webbrowser.open(url)


def open_path(path: str | Path) -> None:
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception as exc:
        raise RuntimeError(f"Acilamadi: {path}") from exc


def copy_to_clipboard(text: str) -> None:
    # Tkinter is in the stdlib and talks to the native Windows clipboard.
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.clipboard_clear()
    root.clipboard_append(text or "")
    root.update()
    root.destroy()


def send_hotkey(*keys: str, delay: float = 0.0) -> bool:
    try:
        import pyautogui

        if delay:
            time.sleep(delay)
        pyautogui.hotkey(*keys)
        return True
    except Exception:
        return False


def press_key(key: str, delay: float = 0.0) -> bool:
    try:
        import pyautogui

        if delay:
            time.sleep(delay)
        pyautogui.press(key)
        return True
    except Exception:
        return False


def type_text(text: str, delay: float = 0.0) -> bool:
    try:
        import pyautogui

        if delay:
            time.sleep(delay)
        pyautogui.write(text or "", interval=0.01)
        return True
    except Exception:
        return False


def get_foreground_window_title() -> str:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def run_powershell(script: str, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def find_executable(candidates: list[str]) -> str | None:
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    return None


def app_path_from_registry(app_name: str) -> str | None:
    try:
        import winreg
    except Exception:
        return None

    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    names = [app_name]
    if not app_name.lower().endswith(".exe"):
        names.append(f"{app_name}.exe")

    for hive, base in keys:
        for name in names:
            try:
                with winreg.OpenKey(hive, rf"{base}\{name}") as key:
                    value, _ = winreg.QueryValueEx(key, "")
                    if value and Path(value).exists():
                        return value
            except OSError:
                continue
    return None



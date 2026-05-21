"""
TTS (Text-to-Speech) - Windows SAPI kullanir.
"""

from __future__ import annotations

import threading

from actions.windows_utils import run_powershell


VOICE = ""


def speak_text(text: str, on_done=None, blocking: bool = False):
    if not text or not text.strip():
        if on_done:
            on_done()
        return

    max_len = 500
    if len(text) > max_len:
        text = text[:max_len] + "..."

    def _run():
        try:
            safe_text = (text or "").replace("'", "''")
            voice_filter = (VOICE or "").replace("'", "''")
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"if ('{voice_filter}') {{ "
                f"$v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Name -like '*{voice_filter}*' }} | Select-Object -First 1; "
                "$s.SelectVoice($v.VoiceInfo.Name) }; "
                f"$s.Speak('{safe_text}')"
            )
            run_powershell(script, timeout=40)
        except Exception:
            pass
        if on_done:
            on_done()

    if blocking:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()


def get_available_voices() -> list[str]:
    try:
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }"
        )
        result = run_powershell(script, timeout=10)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []

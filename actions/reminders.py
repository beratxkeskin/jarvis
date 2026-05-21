"""
Windows hatirlatici araci.

Windows yerel JSON tabanli hatirlatici deposu kullanir.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REMINDERS_FILE = BASE_DIR / "memory" / "windows_reminders.json"
TR_WEEKDAYS = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = ["", "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]


def _load_reminders() -> list[dict]:
    try:
        raw = json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    except Exception:
        pass
    return []


def _save_reminders(items: list[dict]) -> None:
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REMINDERS_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_query(query: str) -> tuple[str, int]:
    q = (query or "").strip().lower()
    if any(token in q for token in ("bugun", "today")):
        return "today", 8
    if any(token in q for token in ("geciken", "gecmis", "overdue")):
        return "overdue", 8
    if any(token in q for token in ("siradaki", "next")):
        return "next", 1
    if any(token in q for token in ("hepsi", "tum", "tüm", "all", "listele")):
        return "all", 10
    return "upcoming", 8


def _parse_due(due_iso: str) -> tuple[dt.datetime | None, bool]:
    raw = (due_iso or "").strip()
    if not raw:
        return None, False
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(raw).replace(tzinfo=None)
        return parsed, len(raw) == 10
    except ValueError:
        pass
    for fmt, all_day in (
        ("%Y-%m-%dT%H:%M:%S", False),
        ("%Y-%m-%dT%H:%M", False),
        ("%Y-%m-%d %H:%M:%S", False),
        ("%Y-%m-%d %H:%M", False),
        ("%d.%m.%Y %H:%M", False),
        ("%Y-%m-%d", True),
        ("%d.%m.%Y", True),
    ):
        try:
            return dt.datetime.strptime(raw, fmt), all_day
        except ValueError:
            continue
    raise ValueError("Animsatici tarihi gecersiz. due_iso icin 'YYYY-MM-DD' veya 'YYYY-MM-DDTHH:MM' kullan.")


def _day_label(when: dt.datetime, now: dt.datetime) -> str:
    if when.date() == now.date():
        return "bugun"
    if when.date() == now.date() + dt.timedelta(days=1):
        return "yarin"
    return f"{when.day} {TR_MONTHS[when.month]} {TR_WEEKDAYS[when.weekday()]}"


def _format_due(item: dict, now: dt.datetime) -> str:
    raw = item.get("due_iso", "")
    if not raw:
        return "zaman atanmamis"
    due = dt.datetime.fromisoformat(raw)
    if item.get("all_day"):
        return f"{_day_label(due, now)} tum gun"
    return f"{_day_label(due, now)} {due.strftime('%H:%M')}"


def _format_reminder_line(item: dict, now: dt.datetime) -> str:
    parts = [f"{_format_due(item, now)} - {item.get('title', 'Adsiz animsatici')}"]
    if item.get("list_name"):
        parts.append(f"[{item['list_name']}]")
    if item.get("priority") == "high":
        parts.append("(yuksek oncelik)")
    return " ".join(parts)


def get_reminders(query: str = "upcoming", limit: int = 8, list_name: str = "") -> str:
    mode, default_limit = _normalize_query(query)
    limit = max(1, min(20, int(limit or default_limit)))
    now = dt.datetime.now()
    today = now.date()
    items = [item for item in _load_reminders() if not item.get("completed")]
    if list_name:
        items = [item for item in items if str(item.get("list_name", "")).lower() == list_name.strip().lower()]

    def due_value(item: dict) -> dt.datetime | None:
        try:
            return dt.datetime.fromisoformat(item.get("due_iso", ""))
        except Exception:
            return None

    filtered = []
    for item in items:
        due = due_value(item)
        if mode == "today" and (not due or due.date() != today):
            continue
        if mode == "overdue" and (not due or due >= now):
            continue
        if mode in {"upcoming", "next"} and due and due < now:
            continue
        filtered.append(item)

    filtered.sort(key=lambda item: (not item.get("due_iso"), item.get("due_iso", ""), item.get("title", "").lower()))
    filtered = filtered[:limit]
    if not filtered:
        return {
            "today": "Bugun icin animsatici gorunmuyor.",
            "overdue": "Geciken animsatici gorunmuyor.",
            "next": "Siradaki animsaticiyi bulamadim.",
            "all": "Kayitli acik animsatici gorunmuyor.",
        }.get(mode, "Yaklasan animsatici gorunmuyor.")

    if mode == "next":
        return f"Siradaki animsatici: {_format_reminder_line(filtered[0], now)}."
    header = {
        "today": f"Bugun icin {len(filtered)} animsatici buldum:",
        "overdue": f"Gecikmis {len(filtered)} animsatici buldum:",
        "all": f"Acik {len(filtered)} animsatici buldum:",
    }.get(mode, f"Yaklasan {len(filtered)} animsatici buldum:")
    return "\n".join([header, *[f"- {_format_reminder_line(item, now)}" for item in filtered]])


def add_reminder(
    title: str,
    due_iso: str = "",
    notes: str = "",
    list_name: str = "",
    priority: str = "",
    all_day: bool = False,
) -> str:
    if not title or not title.strip():
        return "Animsatici basligi bos olamaz."
    try:
        due, inferred_all_day = _parse_due(due_iso)
    except ValueError as exc:
        return str(exc)

    item = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "due_iso": due.isoformat(timespec="minutes") if due else "",
        "notes": (notes or "").strip(),
        "list_name": (list_name or "JARVIS").strip(),
        "priority": (priority or "").strip().lower(),
        "all_day": bool(all_day or inferred_all_day),
        "completed": False,
        "created_iso": dt.datetime.now().isoformat(timespec="seconds"),
    }
    items = _load_reminders()
    items.append(item)
    _save_reminders(items)
    return f"Animsatici eklendi: {_format_due(item, dt.datetime.now())} - {item['title']}"


def delete_reminder(title: str) -> str:
    if not title or not title.strip():
        return "Silinmesini istediğiniz anımsatıcı başlığını belirtmelisiniz."
    t_clean = title.strip().lower()
    items = _load_reminders()
    remaining = []
    deleted_count = 0
    for item in items:
        if item.get("title", "").strip().lower() == t_clean or t_clean in item.get("title", "").strip().lower():
            deleted_count += 1
        else:
            remaining.append(item)
            
    if deleted_count == 0:
        return f"'{title}' adında veya içeriğinde kayıtlı bir anımsatıcı bulunamadı."
        
    _save_reminders(remaining)
    return f"'{title}' anımsatıcısı başarıyla silindi ({deleted_count} kayıt)."




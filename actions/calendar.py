"""
Windows takvim araci.

Windows yerel JSON tabanli takvim
deposu kullanir. Fonksiyon imzalari Windows surumuyle uyumludur.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CALENDAR_FILE = BASE_DIR / "memory" / "windows_calendar.json"
TR_WEEKDAYS = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = ["", "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]


def _load_events() -> list[dict]:
    try:
        raw = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [event for event in raw if isinstance(event, dict)]
    except Exception:
        pass
    return []


def _save_events(events: list[dict]) -> None:
    CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CALENDAR_FILE.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_datetime(value: str, default_duration_minutes: int = 60) -> tuple[dt.datetime, dt.datetime | None, bool]:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Tarih/saat bos olamaz.")
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(raw)
        return parsed.replace(tzinfo=None), None, len(raw) == 10
    except ValueError:
        pass
    for fmt, all_day in (
        ("%Y-%m-%d %H:%M:%S", False),
        ("%Y-%m-%d %H:%M", False),
        ("%d.%m.%Y %H:%M", False),
        ("%Y-%m-%d", True),
        ("%d.%m.%Y", True),
    ):
        try:
            parsed = dt.datetime.strptime(raw, fmt)
            end = parsed + (dt.timedelta(days=1) if all_day else dt.timedelta(minutes=default_duration_minutes))
            return parsed, end, all_day
        except ValueError:
            continue
    raise ValueError("Tarih formati gecersiz. 'YYYY-MM-DDTHH:MM' veya 'YYYY-MM-DD' kullan.")


def _month_start(value: dt.datetime) -> dt.datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(value: dt.datetime, months: int) -> dt.datetime:
    total = (value.year * 12 + (value.month - 1)) + months
    return value.replace(year=total // 12, month=total % 12 + 1, day=1)


def _window(query: str) -> tuple[dt.datetime, dt.datetime, str, str, str]:
    q = (query or "today").strip().lower()
    now = dt.datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if "gelecek ay" in q or "onumuzdeki ay" in q or "next month" in q:
        start = _add_months(_month_start(now), 1)
        return start, _add_months(start, 1), "Gelecek ay icin {count} etkinlik buldum:", "Gelecek ay takviminde etkinlik gorunmuyor.", "range"
    if "bu ay" in q or "this month" in q:
        start = _month_start(now)
        return start, _add_months(start, 1), "Bu ay icin {count} etkinlik buldum:", "Bu ay takviminde etkinlik gorunmuyor.", "range"

    month_match = re.search(r"(\d+)\s*(ay|month|months)", q)
    if month_match:
        months = max(1, min(12, int(month_match.group(1))))
        return today, _add_months(_month_start(now), months), f"Onumuzdeki {months} ay icin {{count}} etkinlik buldum:", f"Onumuzdeki {months} ayda takviminde etkinlik gorunmuyor.", "range"

    week_match = re.search(r"(\d+)\s*(hafta|week|weeks)", q)
    if week_match:
        weeks = max(1, min(12, int(week_match.group(1))))
        return today, today + dt.timedelta(days=weeks * 7), f"Onumuzdeki {weeks} hafta icin {{count}} etkinlik buldum:", f"Onumuzdeki {weeks} haftada takviminde etkinlik gorunmuyor.", "range"

    day_match = re.search(r"(\d+)\s*(gun|gün|day|days)", q)
    if day_match:
        days = max(1, min(365, int(day_match.group(1))))
        return today, today + dt.timedelta(days=days), f"Onumuzdeki {days} gun icin {{count}} etkinlik buldum:", f"Onumuzdeki {days} gunde takviminde etkinlik gorunmuyor.", "range"

    if any(token in q for token in ("yarin", "tomorrow")):
        start = today + dt.timedelta(days=1)
        return start, start + dt.timedelta(days=1), "Yarin icin {count} etkinlik buldum:", "Yarin takviminde etkinlik gorunmuyor.", "range"
    if any(token in q for token in ("hafta", "week", "7 gun")):
        return today, today + dt.timedelta(days=7), "Onumuzdeki 7 gun icin {count} etkinlik buldum:", "Onumuzdeki 7 gunde takviminde etkinlik gorunmuyor.", "range"
    if any(token in q for token in ("siradaki", "sonraki", "next")):
        return now, now + dt.timedelta(days=365), "", "Siradaki takvim etkinligini bulamadim.", "next"
    if any(token in q for token in ("ajanda", "agenda", "yaklasan", "upcoming")):
        return now, now + dt.timedelta(days=365), "Yaklasan ajandanda {count} etkinlik var:", "Yaklasan takvim etkinligi gorunmuyor.", "agenda"
    return today, today + dt.timedelta(days=1), "Bugun icin {count} etkinlik buldum:", "Bugun takviminde etkinlik gorunmuyor.", "range"


def _event_datetimes(event: dict) -> tuple[dt.datetime, dt.datetime]:
    return dt.datetime.fromisoformat(event["start_iso"]), dt.datetime.fromisoformat(event["end_iso"])


def _day_label(when: dt.datetime, now: dt.datetime) -> str:
    if when.date() == now.date():
        return "bugun"
    if when.date() == now.date() + dt.timedelta(days=1):
        return "yarin"
    return f"{when.day} {TR_MONTHS[when.month]} {TR_WEEKDAYS[when.weekday()]}"


def _format_event_line(event: dict, now: dt.datetime) -> str:
    start, end = _event_datetimes(event)
    if event.get("all_day"):
        when = f"{_day_label(start, now)} tum gun"
    else:
        when = f"{_day_label(start, now)} {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    pieces = [f"{when} - {event.get('title', 'Adsiz etkinlik')}"]
    if event.get("calendar"):
        pieces.append(f"[{event['calendar']}]")
    if event.get("location"):
        pieces.append(f"@ {event['location']}")
    return " ".join(pieces)


def get_calendar_events(query: str = "today", limit: int = 6) -> str:
    start, end, header, empty, kind = _window(query)
    limit = max(1, min(60, int(limit or 6)))
    events = []
    for event in _load_events():
        try:
            event_start, event_end = _event_datetimes(event)
        except Exception:
            continue
        if event_end >= start and event_start < end:
            events.append(event)
    events.sort(key=lambda item: item.get("start_iso", ""))

    if not events:
        return empty
    now = dt.datetime.now()
    if kind == "next":
        return f"Siradaki etkinlik: {_format_event_line(events[0], now)}."
    selected = events[:limit]
    lines = [header.format(count=len(selected))]
    lines.extend(f"- {_format_event_line(event, now)}" for event in selected)
    return "\n".join(lines)


def add_calendar_event(
    title: str,
    start_iso: str,
    end_iso: str = "",
    notes: str = "",
    location: str = "",
    calendar_name: str = "",
    all_day: bool = False,
) -> str:
    title = (title or "").strip()
    if not title:
        return "Takvime eklemek icin etkinlik basligi gerekli."
    try:
        start, inferred_end, inferred_all_day = _parse_datetime(start_iso)
        if end_iso and end_iso.strip():
            end, _, _ = _parse_datetime(end_iso)
        else:
            end = inferred_end or (start + dt.timedelta(days=1 if all_day or inferred_all_day else 0, hours=0 if all_day or inferred_all_day else 1))
    except ValueError as exc:
        return str(exc)

    event = {
        "id": str(uuid.uuid4()),
        "title": title,
        "start_iso": start.isoformat(timespec="minutes"),
        "end_iso": end.isoformat(timespec="minutes"),
        "notes": (notes or "").strip(),
        "location": (location or "").strip(),
        "calendar": (calendar_name or "JARVIS").strip(),
        "all_day": bool(all_day or inferred_all_day),
    }
    events = _load_events()
    events.append(event)
    _save_events(events)
    return f"Takvime eklendi: {_format_event_line(event, dt.datetime.now())}."


def delete_calendar_event(
    title: str,
    start_iso: str = "",
    calendar_name: str = "",
    delete_all_matches: bool = False,
) -> str:
    title_norm = (title or "").strip().lower()
    if not title_norm:
        return "Takvimden silmek icin etkinlik basligi gerekli."

    target_date = None
    if start_iso and start_iso.strip():
        try:
            target_date, _, _ = _parse_datetime(start_iso)
        except ValueError:
            target_date = None

    events = _load_events()
    matches = []
    for event in events:
        if title_norm not in str(event.get("title", "")).lower():
            continue
        if calendar_name and calendar_name.strip().lower() != str(event.get("calendar", "")).lower():
            continue
        if target_date:
            try:
                start, _end = _event_datetimes(event)
                if start.date() != target_date.date():
                    continue
            except Exception:
                continue
        matches.append(event)

    if not matches:
        return "Silinecek takvim etkinligi bulunamadi."

    delete_ids = {event["id"] for event in (matches if delete_all_matches else matches[:1])}
    _save_events([event for event in events if event.get("id") not in delete_ids])
    if delete_all_matches:
        return f"Takvimden {len(delete_ids)} etkinlik silindi."
    return f"Takvimden silindi: {_format_event_line(matches[0], dt.datetime.now())}."



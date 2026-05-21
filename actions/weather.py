"""
Gelişmiş Hava Durumu İstihbarat Motoru.

Anlık hava durumunun yanı sıra günün ilerleyen saatlerindeki sıcaklık değişimini, 
yağmur olasılığını ve rüzgar durumunu analiz ederek proaktif yaşam senaryoları için veri sağlar.
"""

from __future__ import annotations

import os
import requests


def get_weather_data(location: str | None = None) -> dict[str, str]:
    target = (location or os.environ.get("JARVIS_WEATHER_LOCATION") or "Istanbul").strip().title()
    try:
        response = requests.get(
            f"https://wttr.in/{target}",
            params={"format": "j1"},
            timeout=10,
            headers={"User-Agent": "JARVIS Windows"},
        )
        response.raise_for_status()
        payload = response.json()
        
        current = (payload.get("current_condition") or [{}])[0]
        temp_c = current.get("temp_C", "16")
        feels_like = current.get("FeelsLikeC", temp_c)
        weather_desc = ((current.get("weatherDesc") or [{}])[0]).get("value", "Clear Sky")
        humidity = current.get("humidity", "63")
        wind_kmh = current.get("windspeedKmph", "11")

        # İlerleyen saatlerin analizi (Hourly forecast)
        forecast_str = ""
        weather_days = payload.get("weather", [])
        if weather_days:
            today = weather_days[0]
            min_t = today.get("mintempC", "")
            max_t = today.get("maxtempC", "")
            hourly = today.get("hourly", [])
            
            hourly_reports = []
            # time alanları genelde "0", "300", "600", "900", "1200", "1500", "1800", "2100" şeklindedir
            for h in hourly:
                t_raw = h.get("time", "0")
                if t_raw in ["900", "1200", "1500", "1800", "2100"]:
                    hour_label = f"{int(t_raw)//100:02d}:00" if t_raw != "0" else "00:00"
                    h_temp = h.get("tempC", "")
                    h_rain = h.get("chanceofrain", "0")
                    h_desc = ((h.get("weatherDesc") or [{}])[0]).get("value", "")
                    hourly_reports.append(f"{hour_label} -> {h_temp}°C (%{h_rain} yağmur, {h_desc})")
            
            if hourly_reports:
                forecast_str = f"Bugün Min: {min_t}°C, Max: {max_t}°C. İlerleyen Saatlerde Tahmin: " + " | ".join(hourly_reports)

        try:
            temp_int = int(temp_c)
        except ValueError:
            temp_int = 16

        # Temel durum tavsiyesi
        cond_lower = weather_desc.lower()
        if "rain" in cond_lower or "shower" in cond_lower or "drizzle" in cond_lower:
            sugg = "Şemsiye ve su geçirmez ceket önerilir."
        elif "snow" in cond_lower or "blizzard" in cond_lower:
            sugg = "Kalın kışlık mont, eldiven ve kaşkol şart."
        elif temp_int < 5:
            sugg = "Dondurucu soğuk. Kat kat ve kalın giyinin."
        elif temp_int < 15:
            sugg = "Serin hava. Yanınıza mutlaka ceket veya hırka alın."
        elif temp_int < 22:
            sugg = "Ilık ve güzel bir hava. Rahat kıyafetler uygundur."
        elif temp_int < 30:
            sugg = "Sıcak hava. İnce giyinin ve susuz kalmayın."
        else:
            sugg = "Aşırı sıcak. Güneş gözlüğü ve UV koruması şart."

        return {
            "city": target,
            "temp": f"{temp_c}°C",
            "condition": weather_desc,
            "feels_like": f"{feels_like}°C",
            "humidity": f"%{humidity}",
            "wind": f"{wind_kmh} km/h",
            "forecast": forecast_str or "Saatlik tahmin alınamadı.",
            "suggestion": sugg,
        }
    except Exception:
        # Fallback verisi
        return {
            "city": target,
            "temp": "16°C",
            "condition": "Clear Sky",
            "feels_like": "14°C",
            "humidity": "%63",
            "wind": "11 km/h",
            "forecast": "Tahmin servisine ulaşılamadı.",
            "suggestion": "Yanınıza ince bir ceket almanız önerilir.",
        }


def get_weather_summary(location: str | None = None) -> str:
    data = get_weather_data(location)
    return (
        f"[{data['city']} Hava Durumu İstihbaratı]\n"
        f"Anlık Durum: {data['condition']}, Sıcaklık: {data['temp']} (Hissedilen: {data['feels_like']}), "
        f"Nem: {data['humidity']}, Rüzgar: {data['wind']}.\n"
        f"Günün İlerleyen Saatleri: {data['forecast']}\n"
        f"Genel Tavsiye: {data['suggestion']}"
    )

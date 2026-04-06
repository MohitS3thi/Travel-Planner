import json
from datetime import date, datetime, timedelta
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


_WEATHER_CODE_LABELS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

MAX_FORECAST_HORIZON_DAYS = 16


def _weather_label(code):
    return _WEATHER_CODE_LABELS.get(code, "Unknown")


def _coerce_to_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _is_rain_code(code):
    return code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}


def _is_storm_code(code):
    return code in {95, 96, 99}


def _is_snow_code(code):
    return code in {71, 73, 75, 77, 85, 86}


def _build_warning(weather_data):
    if not weather_data:
        return None

    current = weather_data.get("current") or {}
    forecast = weather_data.get("forecast") or []

    temp_now = current.get("temperature")
    code_now = current.get("weather_code")

    if isinstance(temp_now, (int, float)) and temp_now >= 35:
        return {
            "level": "high",
            "message": "Heat warning: very high temperatures expected. Schedule outdoor plans early or late.",
        }

    if isinstance(temp_now, (int, float)) and temp_now <= 0:
        return {
            "level": "high",
            "message": "Cold warning: near-freezing conditions. Prioritize layered clothing and indoor backups.",
        }

    if _is_storm_code(code_now):
        return {
            "level": "high",
            "message": "Storm warning: thunderstorms expected. Keep indoor alternatives ready.",
        }

    if _is_rain_code(code_now):
        return {
            "level": "medium",
            "message": "Rain warning: wet conditions expected. Move flexible outdoor activities to the driest day.",
        }

    if _is_snow_code(code_now):
        return {
            "level": "medium",
            "message": "Snow warning: winter weather may affect transport and walking routes.",
        }

    rainy_day = next((day for day in forecast if (day.get("precipitation_probability") or 0) >= 70), None)
    if rainy_day:
        return {
            "level": "medium",
            "message": f"High rain chance on {rainy_day.get('date')}. Keep a backup indoor plan.",
        }

    return None


def _best_outdoor_day(forecast):
    best = None
    best_score = None

    for index, day in enumerate(forecast, start=1):
        precip_prob = day.get("precipitation_probability") or 0
        tmax = day.get("temp_max")
        tmin = day.get("temp_min")
        mean_temp = None
        if isinstance(tmax, (int, float)) and isinstance(tmin, (int, float)):
            mean_temp = (tmax + tmin) / 2

        temp_penalty = 0
        if isinstance(mean_temp, (int, float)):
            if mean_temp < 10:
                temp_penalty = 20
            elif mean_temp > 32:
                temp_penalty = 25
            elif 24 <= mean_temp <= 30:
                temp_penalty = 8

        code_penalty = 0
        weather_code = day.get("weather_code")
        if _is_storm_code(weather_code):
            code_penalty = 40
        elif _is_rain_code(weather_code) or _is_snow_code(weather_code):
            code_penalty = 20

        score = precip_prob + temp_penalty + code_penalty
        if best_score is None or score < best_score:
            best_score = score
            best = {
                "day_index": index,
                "date": day.get("date"),
                "score": score,
                "precipitation_probability": precip_prob,
                "weather_label": day.get("weather_label"),
            }

    return best


def _build_trip_forecast(forecast, trip_start_date, forecast_days, today=None):
    if today is None:
        today = date.today()

    if not trip_start_date:
        return {
            "trip_forecast": forecast[:forecast_days],
            "trip_forecast_available": True,
            "trip_forecast_notice": None,
            "trip_forecast_available_from": None,
            "trip_forecast_available_in_days": 0,
        }

    last_available_date = today + timedelta(days=MAX_FORECAST_HORIZON_DAYS - 1)
    if trip_start_date > last_available_date:
        available_from = trip_start_date - timedelta(days=MAX_FORECAST_HORIZON_DAYS - 1)
        days_until_available = (available_from - today).days
        notice = (
            "Forecast for your trip start date is not available yet. "
            f"It should become available from {available_from.isoformat()}."
        )
        return {
            "trip_forecast": [],
            "trip_forecast_available": False,
            "trip_forecast_notice": notice,
            "trip_forecast_available_from": available_from.isoformat(),
            "trip_forecast_available_in_days": max(0, days_until_available),
        }

    trip_start_text = trip_start_date.isoformat()
    filtered = [day for day in forecast if day.get("date") and day["date"] >= trip_start_text]
    selected = filtered[:forecast_days]

    notice = None
    if len(selected) < forecast_days:
        notice = (
            f"Only {len(selected)} day(s) from your trip start date are currently available. "
            "Check again later for more days."
        )

    return {
        "trip_forecast": selected,
        "trip_forecast_available": bool(selected),
        "trip_forecast_notice": notice,
        "trip_forecast_available_from": None,
        "trip_forecast_available_in_days": 0,
    }


def _build_specific_date_availability(target_date, today=None):
    if today is None:
        today = date.today()

    if not target_date:
        return {
            "can_fetch": False,
            "notice": "Select a valid date to view weather.",
            "available_from": None,
            "available_in_days": 0,
        }

    days_until_target = (target_date - today).days
    if days_until_target < 0:
        return {
            "can_fetch": False,
            "notice": "Forecast is not available for past dates.",
            "available_from": None,
            "available_in_days": 0,
        }

    last_available_date = today + timedelta(days=MAX_FORECAST_HORIZON_DAYS - 1)
    if target_date > last_available_date:
        available_from = target_date - timedelta(days=MAX_FORECAST_HORIZON_DAYS - 1)
        return {
            "can_fetch": False,
            "notice": (
                "Forecast for the selected date is not available yet. "
                f"It should become available from {available_from.isoformat()}."
            ),
            "available_from": available_from.isoformat(),
            "available_in_days": (available_from - today).days,
        }

    return {
        "can_fetch": True,
        "notice": None,
        "available_from": None,
        "available_in_days": 0,
    }


def build_weather_recommendation(weather_data):
    forecast = (weather_data or {}).get("trip_forecast") or (weather_data or {}).get("forecast") or []
    if not forecast:
        return None

    best_day = _best_outdoor_day(forecast)
    if not best_day:
        return None

    if best_day["precipitation_probability"] <= 40:
        return (
            f"Move outdoor sightseeing to Day {best_day['day_index']} ({best_day['date']}) "
            f"for drier conditions."
        )

    return "Keep major sightseeing flexible and prioritize indoor activities due to unstable weather."


def _parse_weather_payload(payload):
    current_raw = payload.get("current") or {}
    daily_raw = payload.get("daily") or {}

    current_code = current_raw.get("weather_code")
    current = {
        "temperature": current_raw.get("temperature_2m"),
        "apparent_temperature": current_raw.get("apparent_temperature"),
        "humidity": current_raw.get("relative_humidity_2m"),
        "wind_speed": current_raw.get("wind_speed_10m"),
        "precipitation": current_raw.get("precipitation"),
        "weather_code": current_code,
        "weather_label": _weather_label(current_code),
        "is_day": current_raw.get("is_day"),
    }

    times = daily_raw.get("time") or []
    codes = daily_raw.get("weather_code") or []
    tmax = daily_raw.get("temperature_2m_max") or []
    tmin = daily_raw.get("temperature_2m_min") or []
    precip_probs = daily_raw.get("precipitation_probability_max") or []
    precip_sums = daily_raw.get("precipitation_sum") or []

    forecast = []
    for index, date in enumerate(times):
        code = codes[index] if index < len(codes) else None
        forecast.append(
            {
                "date": date,
                "weather_code": code,
                "weather_label": _weather_label(code),
                "temp_max": tmax[index] if index < len(tmax) else None,
                "temp_min": tmin[index] if index < len(tmin) else None,
                "precipitation_probability": precip_probs[index] if index < len(precip_probs) else None,
                "precipitation_sum": precip_sums[index] if index < len(precip_sums) else None,
            }
        )

    return {
        "current": current,
        "forecast": forecast,
    }


def get_weather_for_coordinates(latitude, longitude, forecast_days=5, trip_start_date=None):
    if latitude is None or longitude is None:
        return None

    requested_days = max(3, min(5, int(forecast_days)))
    trip_start = _coerce_to_date(trip_start_date)
    today = date.today()

    api_forecast_days = requested_days
    if trip_start:
        days_until_trip = (trip_start - today).days
        api_forecast_days = max(requested_days, days_until_trip + requested_days)
    api_forecast_days = max(3, min(MAX_FORECAST_HORIZON_DAYS, api_forecast_days))

    params = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
        "forecast_days": api_forecast_days,
        "timezone": "auto",
    }
    url = f"https://api.open-meteo.com/v1/forecast?{urlencode(params)}"

    try:
        with urlopen(url, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError):
        return None

    weather = _parse_weather_payload(payload)
    trip_forecast_info = _build_trip_forecast(weather.get("forecast") or [], trip_start, requested_days, today=today)
    weather.update(trip_forecast_info)

    weather["warning"] = _build_warning(weather)
    weather["recommendation"] = build_weather_recommendation(weather)
    return weather


def get_weather_for_place_date(latitude, longitude, target_date):
    if latitude is None or longitude is None:
        return {
            "selected_date": None,
            "forecast_day": None,
            "notice": "This place does not have coordinates yet.",
            "available_from": None,
            "available_in_days": 0,
        }

    selected_date = _coerce_to_date(target_date)
    availability = _build_specific_date_availability(selected_date)
    if not availability["can_fetch"]:
        return {
            "selected_date": selected_date.isoformat() if selected_date else None,
            "forecast_day": None,
            "notice": availability["notice"],
            "available_from": availability["available_from"],
            "available_in_days": max(0, availability["available_in_days"]),
        }

    today = date.today()
    forecast_days = (selected_date - today).days + 1

    params = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
        "forecast_days": max(1, min(MAX_FORECAST_HORIZON_DAYS, forecast_days)),
        "timezone": "auto",
    }
    url = f"https://api.open-meteo.com/v1/forecast?{urlencode(params)}"

    try:
        with urlopen(url, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError):
        return {
            "selected_date": selected_date.isoformat(),
            "forecast_day": None,
            "notice": "Weather service is currently unavailable.",
            "available_from": None,
            "available_in_days": 0,
        }

    weather = _parse_weather_payload(payload)
    selected_text = selected_date.isoformat()
    day_forecast = next((day for day in weather.get("forecast", []) if day.get("date") == selected_text), None)

    if not day_forecast:
        return {
            "selected_date": selected_text,
            "forecast_day": None,
            "notice": "Forecast for the selected date is not available yet.",
            "available_from": None,
            "available_in_days": 0,
        }

    return {
        "selected_date": selected_text,
        "forecast_day": day_forecast,
        "notice": None,
        "available_from": None,
        "available_in_days": 0,
    }

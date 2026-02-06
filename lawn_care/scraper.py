"""Soil temperature fetching from ClearAg (DTN) and forecast projection via Open-Meteo."""

import logging
import time
from datetime import date, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

CLEARAG_DAILY_SOIL_URL = "https://ag.us.clearapis.com/v1.1/daily/soil"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Calibrated from 1 year of ClearAg soil temp vs Open-Meteo air temp
# for KC area (39.2, -94.6). Soil warms faster than it cools at 0-10cm depth.
SOIL_ALPHA_RISING = 0.79   # response factor when air temp > soil temp
SOIL_ALPHA_FALLING = 0.15  # response factor when air temp < soil temp


def _date_to_unix(d: date) -> int:
    """Convert a date to Unix timestamp (midnight UTC)."""
    return int(time.mktime(d.timetuple()))


def fetch_clearag_soil(
    config: dict[str, Any],
    start: date,
    end: date,
) -> dict[str, dict] | None:
    """
    Fetch daily soil data from ClearAg for a date range.

    Returns dict keyed by "YYYY-MM-DD" with soil fields, or None on failure.
    """
    clearag = config.get("clearag", {})
    app_id = clearag.get("app_id")
    app_key = clearag.get("app_key")
    if not app_id or not app_key:
        logger.error("Missing clearag.app_id or clearag.app_key in config")
        return None

    lat = config["location"]["lat"]
    lng = config["location"]["lng"]

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "location": f"{lat},{lng}",
        "start": _date_to_unix(start),
        "end": _date_to_unix(end),
    }

    try:
        response = requests.get(CLEARAG_DAILY_SOIL_URL, params=params, timeout=15)
        if response.status_code == 429:
            logger.warning("ClearAg rate limit hit (429)")
            return None
        response.raise_for_status()
        data = response.json()

        # Response is keyed by "lat,lng" -> date -> fields
        location_key = f"{lat},{lng}"
        return data.get(location_key)

    except requests.RequestException as e:
        logger.error(f"ClearAg API request failed: {e}")
        return None
    except (ValueError, KeyError) as e:
        logger.error(f"ClearAg response parse error: {e}")
        return None


def fetch_soil_temp(config: dict[str, Any]) -> float | None:
    """
    Fetch current soil temperature (0-10cm avg) in Fahrenheit.

    Tries ClearAg API first, falls back to manual config value.
    """
    today = date.today()
    days = fetch_clearag_soil(config, today, today)

    if days:
        today_str = today.strftime("%Y-%m-%d")
        day_data = days.get(today_str)
        if day_data:
            field = day_data.get("soil_temp_0to10cm", {})
            value = field.get("value")
            if value is not None and value != "n/a":
                temp = float(value)
                logger.info(f"ClearAg soil temp: {temp}F (0-10cm avg)")
                return temp

        # Today might not be available yet; try yesterday
        yesterday = today - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        day_data = days.get(yesterday_str)
        if day_data:
            field = day_data.get("soil_temp_0to10cm", {})
            value = field.get("value")
            if value is not None and value != "n/a":
                temp = float(value)
                logger.info(f"ClearAg soil temp (yesterday): {temp}F (0-10cm avg)")
                return temp

    logger.warning("ClearAg fetch returned no usable data")

    # Fallback to manual value
    manual_temp = config.get("soil_temp_manual_f")
    if manual_temp is not None:
        logger.info(f"Using manual soil temp: {manual_temp}F")
        return float(manual_temp)

    logger.warning("No soil temperature available")
    return None


def fetch_soil_temp_history(
    config: dict[str, Any],
    days: int = 14,
) -> list[dict]:
    """
    Fetch recent soil temp history from ClearAg.

    Returns list of {"date": "YYYY-MM-DD", "temp": float} entries,
    newest first, compatible with the state soil_temp_history format.
    """
    today = date.today()
    start = today - timedelta(days=days)
    data = fetch_clearag_soil(config, start, today)

    if not data:
        return []

    history = []
    for date_str in sorted(data.keys(), reverse=True):
        day_data = data[date_str]
        field = day_data.get("soil_temp_0to10cm", {})
        value = field.get("value")
        if value is not None and value != "n/a":
            history.append({"date": date_str, "temp": float(value)})

    return history


def fetch_air_temp_forecast(config: dict[str, Any], days: int = 14) -> list[dict] | None:
    """
    Fetch daily air temperature forecast from Open-Meteo.

    Returns list of {"date": "YYYY-MM-DD", "mean": float, "min": float, "max": float}
    in chronological order (today first), or None on failure.
    Temperatures in Fahrenheit.
    """
    lat = config["location"]["lat"]
    lng = config["location"]["lng"]

    params = {
        "latitude": lat,
        "longitude": lng,
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean",
        "temperature_unit": "fahrenheit",
        "timezone": "America/Chicago",
        "forecast_days": days,
    }

    try:
        response = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        maxs = daily.get("temperature_2m_max", [])
        mins = daily.get("temperature_2m_min", [])
        means = daily.get("temperature_2m_mean", [])

        forecast = []
        for i, d in enumerate(dates):
            forecast.append({
                "date": d,
                "mean": means[i],
                "min": mins[i],
                "max": maxs[i],
            })

        logger.info(f"Open-Meteo forecast: {len(forecast)} days fetched")
        return forecast

    except requests.RequestException as e:
        logger.error(f"Open-Meteo request failed: {e}")
        return None
    except (ValueError, KeyError, IndexError) as e:
        logger.error(f"Open-Meteo response parse error: {e}")
        return None


def project_soil_temps(
    current_soil_temp: float,
    air_forecast: list[dict],
    alpha_rising: float = SOIL_ALPHA_RISING,
    alpha_falling: float = SOIL_ALPHA_FALLING,
) -> list[dict]:
    """
    Project future soil temps based on current soil temp and air temp forecast.

    Uses an asymmetric exponential lag model calibrated against 1 year of
    ClearAg actuals for KC: soil responds quickly to warming (alpha=0.79)
    but slowly to cooling (alpha=0.15). This matches the physical behavior
    of shallow soil --it absorbs heat fast but retains it.

    Expected accuracy (MAE from backtesting):
      1-day: ~2.6F | 7-day: ~4.6F | 13-day: ~5.0F

    Returns list of {"date": "YYYY-MM-DD", "projected_soil_temp": float}
    starting from tomorrow (skips today since we have actual data).
    """
    projections = []
    soil = current_soil_temp

    for day in air_forecast[1:]:  # skip today
        air_mean = day["mean"]
        diff = air_mean - soil
        alpha = alpha_rising if diff > 0 else alpha_falling
        soil = soil + alpha * diff
        projections.append({
            "date": day["date"],
            "projected_soil_temp": round(soil, 1),
        })

    return projections

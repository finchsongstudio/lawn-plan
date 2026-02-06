"""Soil temperature scraping from Greencast and other sources."""

import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)


def fetch_soil_temp_greencast(config: dict[str, Any]) -> float | None:
    """
    Fetch soil temperature from Greencast API.

    Returns 4-inch soil temperature in Fahrenheit, or None if unavailable.
    """
    lat = config["location"]["lat"]
    lng = config["location"]["lng"]

    # Greencast uses product-api.alfprod.com for their map data
    url = "https://product-api.alfprod.com/api/v1/greencast/soil-temp"
    params = {
        "lat": lat,
        "lng": lng,
        "depth": 4,  # 4-inch depth
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "temperature" in data:
                return float(data["temperature"])
    except Exception as e:
        logger.debug(f"Greencast API request failed: {e}")

    # Alternative: try the public map page and parse embedded data
    try:
        map_url = "https://www.greencastonline.com/tools/soil-temperature"
        response = requests.get(
            map_url,
            params={"lat": lat, "lng": lng},
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        if response.status_code == 200:
            match = re.search(r'"soilTemp4in":\s*([\d.]+)', response.text)
            if match:
                return float(match.group(1))
    except Exception as e:
        logger.debug(f"Greencast page scrape failed: {e}")

    return None


def fetch_soil_temp(config: dict[str, Any]) -> float | None:
    """
    Fetch current 4-inch soil temperature.

    Tries Greencast first, falls back to manual config value.
    """
    source = config.get("soil_temp_source", "greencast")

    if source == "greencast":
        temp = fetch_soil_temp_greencast(config)
        if temp is not None:
            logger.info(f"Fetched soil temp from Greencast: {temp}°F")
            return temp
        logger.warning("Greencast fetch failed, checking manual fallback")

    # Fallback to manual value
    manual_temp = config.get("soil_temp_manual_f")
    if manual_temp is not None:
        logger.info(f"Using manual soil temp: {manual_temp}°F")
        return float(manual_temp)

    logger.warning("No soil temperature available (Greencast failed, no manual value set)")
    return None

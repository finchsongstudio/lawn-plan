"""Notification formatting and sending via Ntfy."""

import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _parse_numeric_rate(rate_str: str) -> float | None:
    """Extract a leading numeric value from a rate string like '4 lbs' or '2-3 lbs product'."""
    if not rate_str:
        return None
    # Match leading number (int or float), possibly a range like "2-3" (use first value)
    m = re.match(r"([\d.]+)", str(rate_str))
    return float(m.group(1)) if m else None


def _format_product_line(product: dict, area_sqft: float | None) -> str:
    """Format a single product with rate and quantity info."""
    name = product["name"]
    ptype = product.get("type", "")
    parts = [f"    {name} ({ptype})"]

    # Determine rate string
    rate_str = product.get("rate_per_1000sqft") or ""
    rate_oz = product.get("rate_per_1000sqft_oz")

    if rate_oz is not None:
        rate_display = f"{rate_oz} oz/1k sqft"
        if area_sqft:
            total_oz = rate_oz * (area_sqft / 1000)
            parts.append(f" -- {rate_display}, {total_oz:.1f} oz total")
        else:
            parts.append(f" -- {rate_display}")
    elif rate_str:
        numeric = _parse_numeric_rate(rate_str)
        if numeric and area_sqft:
            total = numeric * (area_sqft / 1000)
            parts.append(f" -- {rate_str}/1k, {total:.1f} total")
        else:
            parts.append(f" -- {rate_str}")

    if product.get("notes"):
        parts.append(f"\n      {product['notes']}")

    return "".join(parts)


def _format_conditions(app: dict) -> list[str]:
    """Extract key conditions and spray notes to surface in the notification."""
    lines = []
    conditions = app.get("conditions", {})
    spray_notes = app.get("spray_notes", {})

    if conditions.get("water_in"):
        lines.append("  Water in after application")
    if conditions.get("water_in_asap"):
        lines.append("  Water in ASAP")
    wid = conditions.get("water_in_within_days")
    if wid:
        lines.append(f"  Water in within {wid} days")

    wait_h = spray_notes.get("wait_before_watering_hours") or conditions.get("wait_before_watering_hours")
    if wait_h:
        lines.append(f"  Do NOT water for {wait_h}h after application")

    mow_before = spray_notes.get("mow_before_days")
    mow_after = spray_notes.get("mow_after_days")
    if mow_before and mow_after:
        lines.append(f"  Mow {mow_before}d before and wait {mow_after}d after to mow")
    elif mow_before:
        lines.append(f"  Mow {mow_before}d before applying")
    elif mow_after:
        lines.append(f"  Wait {mow_after}d after to mow")

    # Temperature restrictions from conditions
    for key, val in conditions.items():
        if "air_temp_min_f" in key:
            lines.append(f"  Min air temp: {val}F")
        elif "air_temp_max_f" in key:
            lines.append(f"  Max air temp: {val}F")

    return lines


def _format_app_detail(app: dict, area_sqft: float | None) -> str:
    """Format a full app detail block (used in READY NOW and HEADS UP)."""
    lines = [app["name"]]
    lines.append(f"  {app['reason']}")

    if app.get("products"):
        lines.append("  Products:")
        for p in app["products"]:
            lines.append(_format_product_line(p, area_sqft))

    lines.extend(_format_conditions(app))

    for w in app.get("warnings", []):
        lines.append(f"  !! {w}")

    return "\n".join(lines)


def format_notification(
    apps: list[dict[str, Any]],
    soil_temp: float | None,
    projections: list[dict] | None = None,
    area_sqft: float | None = None,
) -> str:
    """Format notification message for upcoming applications."""
    lines = []

    if soil_temp is not None:
        lines.append(f"Current soil temp (4\"): {soil_temp}F")
        if projections:
            temps = [f"{p['projected_soil_temp']:.0f}" for p in projections[:7]]
            lines.append(f"  7-day soil forecast: {' > '.join(temps)}F")
        lines.append("")

    ready_apps = [a for a in apps if a["ready"]]
    heads_up_apps = [a for a in apps if a.get("heads_up")]
    upcoming_apps = [a for a in apps if not a["ready"] and not a.get("heads_up")]

    if ready_apps:
        lines.append("=== READY NOW ===")
        for app in ready_apps:
            lines.append("")
            lines.append(_format_app_detail(app, area_sqft))

    if heads_up_apps:
        lines.append("\n=== HEADS UP ===")
        for app in heads_up_apps:
            lines.append("")
            lines.append(_format_app_detail(app, area_sqft))

    if upcoming_apps:
        lines.append("\n=== COMING UP ===")
        for app in upcoming_apps[:3]:
            proj = app["projected_date"]
            proj_str = proj.strftime("%b %d") if proj else "TBD"
            lines.append(f"\n{app['name']} (target: {proj_str})")
            lines.append(f"  {app['reason']}")

    return "\n".join(lines)


def format_ready_notification(
    app: dict[str, Any],
    soil_temp: float | None,
    area_sqft: float | None = None,
) -> str:
    """Format a single READY NOW notification for one app."""
    lines = []
    if soil_temp is not None:
        lines.append(f"Soil temp (4\"): {soil_temp}F")
    lines.append("")
    lines.append(_format_app_detail(app, area_sqft))
    return "\n".join(lines)


def format_heads_up_notification(
    apps: list[dict[str, Any]],
    soil_temp: float | None,
    projections: list[dict] | None = None,
    area_sqft: float | None = None,
) -> str:
    """Format a single notification for all HEADS UP apps."""
    lines = []
    if soil_temp is not None:
        lines.append(f"Soil temp (4\"): {soil_temp}F")
        if projections:
            temps = [f"{p['projected_soil_temp']:.0f}" for p in projections[:7]]
            lines.append(f"  7-day soil forecast: {' > '.join(temps)}F")
    lines.append("")
    lines.append("=== HEADS UP - Prep these products ===")
    for app in apps:
        lines.append("")
        lines.append(_format_app_detail(app, area_sqft))
    return "\n".join(lines)


def send_ready_notification(app: dict[str, Any], message: str, config: dict[str, Any]) -> bool:
    """
    Send a READY NOW notification for a single app with a Mark Done action button.

    Returns True if successful, False otherwise.
    """
    topic = config.get("ntfy_topic", "kc-lawn-care")
    done_topic = config.get("ntfy_done_topic", "kc-lawn-care-done")
    url = f"https://ntfy.sh/{topic}"
    app_id = app["id"]

    try:
        response = requests.post(
            url,
            data=message.encode("utf-8"),
            headers={
                "Title": f"Ready: {app['name']}",
                "Priority": "high",
                "Tags": "seedling,white_check_mark",
                "Actions": f"http, Mark Done, https://ntfy.sh/{done_topic}, body={app_id}, method=POST",
            },
            timeout=10,
        )

        if response.status_code == 200:
            logger.info(f"Ready notification sent for {app_id}")
            return True
        else:
            logger.error(f"Ntfy returned status {response.status_code}: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def send_heads_up_notification(message: str, config: dict[str, Any]) -> bool:
    """
    Send a HEADS UP notification (no action button).

    Returns True if successful, False otherwise.
    """
    topic = config.get("ntfy_topic", "kc-lawn-care")
    url = f"https://ntfy.sh/{topic}"

    try:
        response = requests.post(
            url,
            data=message.encode("utf-8"),
            headers={
                "Title": "Heads Up: Lawn Care Coming Soon",
                "Priority": "default",
                "Tags": "seedling,hourglass",
            },
            timeout=10,
        )

        if response.status_code == 200:
            logger.info("Heads-up notification sent")
            return True
        else:
            logger.error(f"Ntfy returned status {response.status_code}: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def send_notification(message: str, config: dict[str, Any]) -> bool:
    """
    Send a generic notification via Ntfy (kept for backwards compatibility).

    Returns True if successful, False otherwise.
    """
    topic = config.get("ntfy_topic", "kc-lawn-care")
    url = f"https://ntfy.sh/{topic}"

    try:
        response = requests.post(
            url,
            data=message.encode("utf-8"),
            headers={
                "Title": "Lawn Care Alert",
                "Priority": "default",
                "Tags": "seedling",
            },
            timeout=10,
        )

        if response.status_code == 200:
            logger.info(f"Notification sent to ntfy.sh/{topic}")
            return True
        else:
            logger.error(f"Ntfy returned status {response.status_code}: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def poll_done_topic(config: dict[str, Any]) -> list[str]:
    """
    Poll the ntfy done topic for mark-as-done messages.

    Returns list of app_ids that were marked done.
    """
    done_topic = config.get("ntfy_done_topic", "kc-lawn-care-done")
    url = f"https://ntfy.sh/{done_topic}/json?poll=1&since=24h"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.warning(f"Done topic poll returned status {response.status_code}")
            return []

        app_ids = []
        for line in response.text.strip().split("\n"):
            if not line:
                continue
            try:
                import json
                msg = json.loads(line)
                if msg.get("event") == "message" and msg.get("message"):
                    app_ids.append(msg["message"].strip())
            except (json.JSONDecodeError, KeyError):
                continue

        return app_ids

    except Exception as e:
        logger.warning(f"Failed to poll done topic: {e}")
        return []

"""Notification formatting and sending via Ntfy."""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


def format_notification(apps: list[dict[str, Any]], soil_temp: float | None) -> str:
    """Format notification message for upcoming applications."""
    lines = []

    if soil_temp is not None:
        lines.append(f"Current soil temp (4\"): {soil_temp}°F")
        lines.append("")

    ready_apps = [a for a in apps if a["ready"]]
    upcoming_apps = [a for a in apps if not a["ready"]]

    if ready_apps:
        lines.append("=== READY NOW ===")
        for app in ready_apps:
            lines.append(f"\n{app['name']}")
            lines.append(f"  {app['reason']}")

            if app["products"]:
                product_names = [p["name"] for p in app["products"]]
                lines.append(f"  Products: {', '.join(product_names)}")

            if app["warnings"]:
                lines.append(f"  Warning: {app['warnings'][0]}")

    if upcoming_apps:
        lines.append("\n=== COMING UP ===")
        for app in upcoming_apps[:3]:
            proj = app["projected_date"]
            proj_str = proj.strftime("%b %d") if proj else "TBD"
            lines.append(f"\n{app['name']} (target: {proj_str})")
            lines.append(f"  {app['reason']}")

    return "\n".join(lines)


def send_notification(message: str, config: dict[str, Any]) -> bool:
    """
    Send notification via Ntfy.

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

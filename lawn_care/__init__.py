"""KC Lawn Care Notification System."""

from lawn_care.config import load_config, load_schedule, load_state, save_state
from lawn_care.scraper import (
    fetch_soil_temp,
    fetch_soil_temp_history,
    fetch_air_temp_forecast,
    project_soil_temps,
)
from lawn_care.triggers import get_upcoming_applications, update_soil_temp_history
from lawn_care.notify import (
    format_notification,
    format_ready_notification,
    format_heads_up_notification,
    send_notification,
    send_ready_notification,
    send_heads_up_notification,
    poll_done_topic,
)

__all__ = [
    "load_config",
    "load_schedule",
    "load_state",
    "save_state",
    "fetch_soil_temp",
    "fetch_soil_temp_history",
    "fetch_air_temp_forecast",
    "project_soil_temps",
    "get_upcoming_applications",
    "update_soil_temp_history",
    "format_notification",
    "format_ready_notification",
    "format_heads_up_notification",
    "send_notification",
    "send_ready_notification",
    "send_heads_up_notification",
    "poll_done_topic",
]

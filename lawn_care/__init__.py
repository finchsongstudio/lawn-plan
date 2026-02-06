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
)
from lawn_care.sheets import read_done_checkboxes, update_dashboard
from lawn_care.email_notify import send_ready_email, send_heads_up_email

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
    "read_done_checkboxes",
    "update_dashboard",
    "send_ready_email",
    "send_heads_up_email",
]

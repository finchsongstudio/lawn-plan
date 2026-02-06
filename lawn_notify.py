#!/usr/bin/env python3
"""
KC Lawn Care Notification System

Orchestrates soil temp fetching, trigger evaluation, Google Sheets dashboard,
and Gmail notifications.
"""

import json
import logging
from datetime import date

from lawn_care import (
    load_config,
    load_schedule,
    load_state,
    save_state,
    fetch_soil_temp,
    fetch_air_temp_forecast,
    project_soil_temps,
    get_upcoming_applications,
    update_soil_temp_history,
    format_notification,
    read_done_checkboxes,
    update_dashboard,
    send_ready_email,
    send_heads_up_email,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def process_done_checkboxes(config: dict, state: dict, schedule: dict, today: date) -> None:
    """Read Google Sheet checkboxes and mark completed apps in state."""
    try:
        done_ids = read_done_checkboxes(config)
    except Exception as e:
        logger.warning(f"Failed to read Sheet checkboxes: {e}")
        return

    if not done_ids:
        return

    valid_app_ids = {app["id"] for app in schedule.get("applications", [])}
    completed = state.setdefault("completed", {})
    sent_alerts = state.get("sent_alerts", {})
    today_str = today.strftime("%Y-%m-%d")

    for app_id in done_ids:
        if app_id not in valid_app_ids:
            logger.warning(f"Unknown app_id from Sheet checkbox: {app_id}")
            continue
        if app_id in completed:
            continue

        completed[app_id] = today_str
        if app_id in sent_alerts:
            del sent_alerts[app_id]
        logger.info(f"Marked done via Sheet: {app_id}")

    save_state(state)


def send_email_notifications(
    upcoming: list[dict],
    config: dict,
    state: dict,
    soil_temp: float | None,
    projections: list[dict] | None,
    today: date,
) -> None:
    """Send Gmail notifications for ready and heads-up apps."""
    area_sqft = config.get("area_sqft")
    today_str = today.strftime("%Y-%m-%d")
    sent_alerts = state.setdefault("sent_alerts", {})

    ready_apps = [a for a in upcoming if a["ready"]]
    heads_up_apps = [a for a in upcoming if a.get("heads_up")]

    # Send one email per ready app
    for app in ready_apps:
        if app["id"] not in sent_alerts:
            if send_ready_email(app, soil_temp, area_sqft, config):
                sent_alerts[app["id"]] = today_str
                save_state(state)

    # Send a single heads-up email for all new heads-up apps
    new_heads_up = [a for a in heads_up_apps if a["id"] not in sent_alerts]
    if new_heads_up:
        if send_heads_up_email(new_heads_up, soil_temp, projections, area_sqft, config):
            for app in new_heads_up:
                sent_alerts[app["id"]] = today_str
            save_state(state)


def main():
    """Main entry point."""
    today = date.today()
    logger.info(f"Lawn care check for {today}")

    # Load configuration and data
    try:
        config = load_config()
        schedule = load_schedule()
        state = load_state()
    except FileNotFoundError as e:
        logger.error(f"Missing required file: {e}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return 1

    # Read Sheet checkboxes before evaluating triggers
    process_done_checkboxes(config, state, schedule, today)

    # Fetch soil temperature
    soil_temp = fetch_soil_temp(config)

    # Update state with new reading
    update_soil_temp_history(state, soil_temp, today)
    save_state(state)

    # Build soil temp projections from weather forecast
    projections = None
    if soil_temp is not None:
        air_forecast = fetch_air_temp_forecast(config)
        if air_forecast:
            projections = project_soil_temps(soil_temp, air_forecast)
            if projections:
                logger.info(
                    f"Projected soil temps: today {soil_temp}F -> "
                    f"{projections[-1]['date']} {projections[-1]['projected_soil_temp']}F"
                )

    # Get ALL upcoming apps for dashboard (limit=0)
    all_upcoming = get_upcoming_applications(schedule, state, soil_temp, today, limit=0, projections=projections)

    if not all_upcoming:
        logger.info("No upcoming applications found")
        return 0

    # Update Google Sheets dashboard
    try:
        update_dashboard(config, schedule, state, all_upcoming, soil_temp, projections)
    except Exception as e:
        logger.error(f"Failed to update Sheet dashboard: {e}")

    # Get top 5 for notification evaluation and console display
    notify_upcoming = all_upcoming[:5]

    ready_apps = [a for a in notify_upcoming if a["ready"]]
    heads_up_apps = [a for a in notify_upcoming if a.get("heads_up")]

    # Format and display full summary to console
    area_sqft = config.get("area_sqft")
    message = format_notification(notify_upcoming, soil_temp, projections, area_sqft)
    print("\n" + message + "\n")

    # Send email notifications if anything is actionable
    if ready_apps or heads_up_apps:
        logger.info(f"{len(ready_apps)} ready, {len(heads_up_apps)} heads-up")
        send_email_notifications(notify_upcoming, config, state, soil_temp, projections, today)
    else:
        logger.info("No applications ready or approaching")

    return 0


if __name__ == "__main__":
    exit(main())

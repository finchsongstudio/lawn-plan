#!/usr/bin/env python3
"""
KC Lawn Care Notification System v0

Orchestrates soil temp fetching, trigger evaluation, and notifications.
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
    get_upcoming_applications,
    update_soil_temp_history,
    format_notification,
    send_notification,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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

    # Fetch soil temperature
    soil_temp = fetch_soil_temp(config)

    # Update state with new reading
    update_soil_temp_history(state, soil_temp, today)
    save_state(state)

    # Get upcoming applications
    upcoming = get_upcoming_applications(schedule, state, soil_temp, today)

    if not upcoming:
        logger.info("No upcoming applications found")
        return 0

    # Check if any applications are ready
    ready_apps = [a for a in upcoming if a["ready"]]

    # Format and display results
    message = format_notification(upcoming, soil_temp)
    print("\n" + message + "\n")

    # Send notification if applications are ready
    if ready_apps:
        logger.info(f"{len(ready_apps)} application(s) ready")
        send_notification(message, config)
    else:
        logger.info("No applications ready yet")

    return 0


if __name__ == "__main__":
    exit(main())

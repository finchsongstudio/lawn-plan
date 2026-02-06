"""Google Sheets dashboard for lawn care season tracking."""

import logging
from datetime import date
from typing import Any

from lawn_care.google_auth import get_sheets_service

logger = logging.getLogger(__name__)

# Column layout: A=Done, B=Status, C=Application, D=Month, E=Projected Date,
# F=Reason, G=Products, H=Conditions, I=Warnings, J=Completed Date, K=app_id
HEADERS = [
    "Done", "Status", "Application", "Month", "Projected Date",
    "Reason", "Products", "Conditions", "Warnings", "Completed Date", "app_id",
]
NUM_COLS = len(HEADERS)  # 11 = columns A through K


def read_done_checkboxes(config: dict[str, Any]) -> list[str]:
    """
    Read the Sheet and return app_ids where the Done checkbox (col A) is TRUE.

    Reads columns A (checkbox) and K (app_id) for all data rows.
    """
    sheet_id = config.get("google_sheet_id")
    if not sheet_id:
        logger.error("No google_sheet_id in config")
        return []

    service = get_sheets_service()
    # Read from row 3 onward (row 1=headers, row 2=soil temp summary)
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="Sheet1!A3:K",
    ).execute()

    rows = result.get("values", [])
    done_ids = []
    for row in rows:
        if len(row) >= NUM_COLS:
            checkbox_val = row[0]  # Column A
            app_id = row[NUM_COLS - 1]  # Column K
            if checkbox_val is True or str(checkbox_val).upper() == "TRUE":
                if app_id:
                    done_ids.append(app_id)

    logger.info(f"Sheet checkboxes: {len(done_ids)} marked done")
    return done_ids


def _format_product_text(products: list[dict], area_sqft: float | None) -> str:
    """Format products list for Sheet cell."""
    if not products:
        return ""
    lines = []
    for p in products:
        name = p["name"]
        ptype = p.get("type", "")
        rate_str = p.get("rate_per_1000sqft") or ""
        rate_oz = p.get("rate_per_1000sqft_oz")

        if rate_oz is not None:
            if area_sqft:
                total_oz = rate_oz * (area_sqft / 1000)
                lines.append(f"{name} ({ptype}) - {rate_oz} oz/1k, {total_oz:.1f} oz total")
            else:
                lines.append(f"{name} ({ptype}) - {rate_oz} oz/1k")
        elif rate_str:
            lines.append(f"{name} ({ptype}) - {rate_str}/1k")
        else:
            lines.append(f"{name} ({ptype})")
    return "\n".join(lines)


def _format_conditions_text(app: dict) -> str:
    """Format conditions for Sheet cell."""
    lines = []
    conditions = app.get("conditions", {})
    spray_notes = app.get("spray_notes", {})

    if conditions.get("water_in"):
        lines.append("Water in after application")
    if conditions.get("water_in_asap"):
        lines.append("Water in ASAP")
    wid = conditions.get("water_in_within_days")
    if wid:
        lines.append(f"Water in within {wid} days")

    wait_h = spray_notes.get("wait_before_watering_hours") or conditions.get("wait_before_watering_hours")
    if wait_h:
        lines.append(f"Do NOT water for {wait_h}h after")

    mow_before = spray_notes.get("mow_before_days")
    mow_after = spray_notes.get("mow_after_days")
    if mow_before and mow_after:
        lines.append(f"Mow {mow_before}d before, wait {mow_after}d after")
    elif mow_before:
        lines.append(f"Mow {mow_before}d before applying")
    elif mow_after:
        lines.append(f"Wait {mow_after}d after to mow")

    return "\n".join(lines)


def _build_app_row(app: dict, area_sqft: float | None, completed: dict) -> list:
    """Build a single row for an application."""
    app_id = app["id"]
    is_completed = app_id in completed

    if is_completed:
        status = "DONE"
        done_val = True
    elif app.get("ready"):
        status = "READY NOW"
        done_val = False
    elif app.get("heads_up"):
        status = "HEADS UP"
        done_val = False
    else:
        status = "Upcoming"
        done_val = False

    proj_date = app.get("projected_date")
    proj_str = proj_date.strftime("%b %d") if proj_date else ""

    completed_date = completed.get(app_id, "")

    return [
        done_val,                                        # A: Done checkbox
        status,                                          # B: Status
        app["name"],                                     # C: Application
        app.get("month_target", ""),                     # D: Month
        proj_str,                                        # E: Projected Date
        app.get("reason", ""),                           # F: Reason
        _format_product_text(app.get("products", []), area_sqft),  # G: Products
        _format_conditions_text(app),                    # H: Conditions
        "\n".join(app.get("warnings", [])),              # I: Warnings
        completed_date,                                  # J: Completed Date
        app_id,                                          # K: app_id
    ]


def update_dashboard(
    config: dict[str, Any],
    schedule: dict[str, Any],
    state: dict[str, Any],
    upcoming: list[dict],
    soil_temp: float | None,
    projections: list[dict] | None,
) -> None:
    """
    Clear and rewrite the Google Sheet dashboard with current season status.

    Row 1: Headers (set by _ensure_sheet_structure)
    Row 2: Soil temp + forecast summary
    Rows 3+: One row per application in schedule order
    """
    sheet_id = config.get("google_sheet_id")
    if not sheet_id:
        logger.error("No google_sheet_id in config")
        return

    service = get_sheets_service()
    area_sqft = config.get("area_sqft")
    completed = state.get("completed", {})

    # Ensure structure first
    _ensure_sheet_structure(service, sheet_id)

    # Build soil temp summary row
    soil_parts = []
    if soil_temp is not None:
        soil_parts.append(f"Soil temp (4\"): {soil_temp}F")
        if projections:
            temps = [f"{p['projected_soil_temp']:.0f}" for p in projections[:7]]
            soil_parts.append(f"7-day forecast: {' > '.join(temps)}F")
    soil_summary = ["", " | ".join(soil_parts) if soil_parts else "No soil temp data"] + [""] * (NUM_COLS - 2)

    # Build app rows - use upcoming (sorted) for non-completed, add completed at bottom
    upcoming_by_id = {a["id"]: a for a in upcoming}
    all_apps = schedule.get("applications", [])

    rows = []
    # First: all upcoming apps (in trigger-sorted order)
    for app in upcoming:
        rows.append(_build_app_row(app, area_sqft, completed))

    # Then: completed apps (in schedule order)
    for app in all_apps:
        if app["id"] in completed and app["id"] not in upcoming_by_id:
            # Completed app not in upcoming list - build a minimal row
            app_id = app["id"]
            rows.append([
                True,                           # A: Done
                "DONE",                          # B: Status
                app["name"],                     # C: Application
                app.get("month_target", ""),      # D: Month
                "",                              # E: Projected Date
                f"Completed on {completed[app_id]}",  # F: Reason
                "",                              # G: Products
                "",                              # H: Conditions
                "",                              # I: Warnings
                completed[app_id],               # J: Completed Date
                app_id,                          # K: app_id
            ])

    # Clear old data rows and write new ones
    # Clear a generous range to remove stale data
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range="Sheet1!A2:K100",
    ).execute()

    # Write soil summary + app rows
    all_rows = [soil_summary] + rows
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A2",
        valueInputOption="USER_ENTERED",
        body={"values": all_rows},
    ).execute()

    # Insert checkboxes for the data rows (rows 3 onward)
    _apply_checkboxes(service, sheet_id, num_app_rows=len(rows))

    logger.info(f"Dashboard updated: {len(rows)} applications written")


def _ensure_sheet_structure(service, sheet_id: str) -> None:
    """Idempotent setup: headers, frozen row, column widths."""
    # Write headers
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A1:K1",
        valueInputOption="USER_ENTERED",
        body={"values": [HEADERS]},
    ).execute()

    # Get sheet properties to find the sheetId (usually 0 for Sheet1)
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=sheet_id,
        fields="sheets.properties",
    ).execute()
    sid = spreadsheet["sheets"][0]["properties"]["sheetId"]

    requests_batch = [
        # Freeze header row
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        # Bold headers
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        },
        # Column widths: A=60, B=100, C=250, D=60, E=100, F=350, G=300, H=200, I=200, J=100, K=0 (hidden)
        *[
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": w},
                    "fields": "pixelSize",
                }
            }
            for i, w in enumerate([60, 100, 250, 60, 100, 350, 300, 200, 200, 100, 10])
        ],
        # Wrap text in products/conditions/warnings columns (G, H, I = indices 6, 7, 8)
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startColumnIndex": 6, "endColumnIndex": 9},
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat.wrapStrategy",
            }
        },
        # Wrap text in reason column (F = index 5)
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startColumnIndex": 5, "endColumnIndex": 6},
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat.wrapStrategy",
            }
        },
        # Conditional formatting: READY NOW rows get green background
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": sid, "startRowIndex": 2}],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": '=$B3="READY NOW"'}],
                        },
                        "format": {
                            "backgroundColor": {"red": 0.85, "green": 0.95, "blue": 0.85},
                        },
                    },
                },
                "index": 0,
            }
        },
        # HEADS UP rows get yellow background
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": sid, "startRowIndex": 2}],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": '=$B3="HEADS UP"'}],
                        },
                        "format": {
                            "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8},
                        },
                    },
                },
                "index": 1,
            }
        },
        # DONE rows get gray background
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": sid, "startRowIndex": 2}],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": '=$B3="DONE"'}],
                        },
                        "format": {
                            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                        },
                    },
                },
                "index": 2,
            }
        },
    ]

    # Clear existing conditional format rules first to avoid duplicates
    clear_requests = [
        {
            "deleteConditionalFormatRule": {"sheetId": sid, "index": 0}
        }
    ]
    # Try clearing rules; ignore errors if none exist
    try:
        # Get current rules count
        spreadsheet_full = service.spreadsheets().get(
            spreadsheetId=sheet_id,
            fields="sheets.conditionalFormats",
        ).execute()
        existing_rules = spreadsheet_full["sheets"][0].get("conditionalFormats", [])
        if existing_rules:
            # Delete all existing rules (in reverse order)
            delete_requests = [
                {"deleteConditionalFormatRule": {"sheetId": sid, "index": i}}
                for i in range(len(existing_rules) - 1, -1, -1)
            ]
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": delete_requests},
            ).execute()
    except Exception:
        pass

    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": requests_batch},
    ).execute()


def _apply_checkboxes(service, sheet_id: str, num_app_rows: int) -> None:
    """Apply checkbox data validation to column A for app rows."""
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=sheet_id,
        fields="sheets.properties",
    ).execute()
    sid = spreadsheet["sheets"][0]["properties"]["sheetId"]

    # Checkbox validation for column A, rows 3 through 3+num_app_rows
    request = {
        "setDataValidation": {
            "range": {
                "sheetId": sid,
                "startRowIndex": 2,  # row 3 (0-indexed)
                "endRowIndex": 2 + num_app_rows,
                "startColumnIndex": 0,
                "endColumnIndex": 1,
            },
            "rule": {
                "condition": {"type": "BOOLEAN"},
                "showCustomUi": True,
            },
        }
    }

    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [request]},
    ).execute()

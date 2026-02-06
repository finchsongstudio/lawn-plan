"""Google Sheets dashboard for lawn care season tracking."""

import logging
from datetime import date
from typing import Any

from lawn_care.google_auth import get_sheets_service

logger = logging.getLogger(__name__)


def _hex(color: str) -> dict:
    """Convert '#rrggbb' hex color to Sheets API RGB float dict."""
    h = color.lstrip("#")
    return {
        "red": int(h[0:2], 16) / 255.0,
        "green": int(h[2:4], 16) / 255.0,
        "blue": int(h[4:6], 16) / 255.0,
    }

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


# Brand registry: prefix -> (display_name, strip_prefix)
# Sorted longest-first at match time for greedy matching
BRAND_REGISTRY = {
    "Andersons":       ("Andersons", "Andersons "),
    "GCI N-Ext":       ("GCI / N-Ext", "GCI N-Ext "),
    "GCI Microgreene": ("GCI / N-Ext", "GCI "),
    "GCI Cal-Tide":    ("GCI / N-Ext", "GCI "),
    "GCI":             ("GCI / N-Ext", "GCI "),
    "KBG Seed":        ("Seed", ""),
    "Core Aeration":   ("Mechanical", ""),
}
_SORTED_PREFIXES = sorted(BRAND_REGISTRY.keys(), key=len, reverse=True)

INDENT = "  "

# Rich text format constants
_BRAND_FMT = {
    "bold": True,
    "fontSize": 10,
    "foregroundColorStyle": {"rgbColor": {"red": 0.173, "green": 0.173, "blue": 0.173}},
}
_PRODUCT_FMT = {
    "bold": False,
    "fontSize": 10,
    "foregroundColorStyle": {"rgbColor": {"red": 0.263, "green": 0.278, "blue": 0.302}},
}


def _format_raw_product_line(product: dict, area_sqft: float | None) -> str:
    """Format a single product dict into a raw string like 'Andersons Barricade (granular) - 4 lbs/1k'."""
    name = product["name"]
    ptype = product.get("type", "")
    rate_str = product.get("rate_per_1000sqft") or ""
    rate_oz = product.get("rate_per_1000sqft_oz")

    if rate_oz is not None:
        if area_sqft:
            total_oz = rate_oz * (area_sqft / 1000)
            return f"{name} ({ptype}) - {rate_oz} oz/1k, {total_oz:.1f} oz total"
        else:
            return f"{name} ({ptype}) - {rate_oz} oz/1k"
    elif rate_str:
        return f"{name} ({ptype}) - {rate_str}/1k"
    else:
        return f"{name} ({ptype})"


def _group_products_by_brand(raw_lines: list[str]) -> dict[str, list[str]]:
    """Group raw product strings by brand. Returns OrderedDict of brand -> [product_lines]."""
    from collections import OrderedDict
    groups: dict[str, list[str]] = OrderedDict()

    for line in raw_lines:
        brand_display = "Other"
        product_line = line

        for prefix in _SORTED_PREFIXES:
            if line.startswith(prefix):
                display_name, strip_str = BRAND_REGISTRY[prefix]
                brand_display = display_name
                if strip_str and line.startswith(strip_str):
                    product_line = line[len(strip_str):]
                break

        groups.setdefault(brand_display, []).append(product_line)

    return groups


def _build_product_cell(products: list[dict], area_sqft: float | None) -> tuple[str, list[dict]]:
    """
    Build brand-grouped product cell text and textFormatRuns.

    Returns (cell_text, format_runs) for Sheets API updateCells.
    """
    if not products:
        return "", []

    raw_lines = [_format_raw_product_line(p, area_sqft) for p in products]
    groups = _group_products_by_brand(raw_lines)

    cell_parts = []
    format_runs = []
    current_index = 0
    is_first_group = True
    brand_keys = list(groups.keys())

    for brand_name, product_lines in groups.items():
        # Blank line between groups
        if not is_first_group:
            cell_parts.append("\n")
            current_index += 1
        is_first_group = False

        # Brand header - bold
        format_runs.append({"startIndex": current_index, "format": _BRAND_FMT})
        brand_line = brand_name + "\n"
        cell_parts.append(brand_line)
        current_index += len(brand_line)

        # Product lines - normal
        for i, product in enumerate(product_lines):
            format_runs.append({"startIndex": current_index, "format": _PRODUCT_FMT})
            product_line = INDENT + product
            # Add newline unless last product of last group
            is_last = (brand_name == brand_keys[-1] and i == len(product_lines) - 1)
            if not is_last:
                product_line += "\n"
            cell_parts.append(product_line)
            current_index += len(product_line)

    return "".join(cell_parts), format_runs


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

    result = "\n".join(lines)
    return result.replace("\r\n", " ").replace("\r", " ")


def _build_app_row(app: dict, area_sqft: float | None, completed: dict) -> tuple[list, list[dict]]:
    """Build a single row for an application. Returns (row_values, product_format_runs)."""
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
    product_text, product_runs = _build_product_cell(app.get("products", []), area_sqft)

    row = [
        done_val,                                        # A: Done checkbox
        status,                                          # B: Status
        app["name"],                                     # C: Application
        app.get("month_target", ""),                     # D: Month
        proj_str,                                        # E: Projected Date
        app.get("reason", ""),                           # F: Reason
        product_text,                                    # G: Products
        _format_conditions_text(app),                    # H: Conditions
        "\n".join(app.get("warnings", [])),              # I: Warnings
        completed_date,                                  # J: Completed Date
        app_id,                                          # K: app_id
    ]
    return row, product_runs


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

    # Build soil temp summary row (A2:K2 is merged, so text goes in A2)
    soil_parts = []
    if soil_temp is not None:
        soil_parts.append(f"Soil temp (4\"): {soil_temp}F")
        if projections:
            temps = [f"{p['projected_soil_temp']:.0f}" for p in projections[:7]]
            soil_parts.append(f"7-day forecast: {' > '.join(temps)}F")
    soil_text = " | ".join(soil_parts) if soil_parts else "No soil temp data"
    soil_summary = [soil_text] + [""] * (NUM_COLS - 1)

    # Build app rows - use upcoming (sorted) for non-completed, add completed at bottom
    upcoming_by_id = {a["id"]: a for a in upcoming}
    all_apps = schedule.get("applications", [])

    rows = []
    product_runs_by_row = []  # parallel list of textFormatRuns per row
    # First: all upcoming apps (in trigger-sorted order)
    for app in upcoming:
        row, runs = _build_app_row(app, area_sqft, completed)
        rows.append(row)
        product_runs_by_row.append(runs)

    # Then: completed apps (in schedule order)
    for app in all_apps:
        if app["id"] in completed and app["id"] not in upcoming_by_id:
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
            product_runs_by_row.append([])

    # Clear old data rows and write new ones
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

    # Apply rich text (bold product names) to column G via updateCells
    _apply_product_rich_text(service, sheet_id, product_runs_by_row, rows)

    # Insert checkboxes for the data rows (rows 3 onward)
    _apply_checkboxes(service, sheet_id, num_app_rows=len(rows))

    logger.info(f"Dashboard updated: {len(rows)} applications written")


def _ensure_sheet_structure(service, sheet_id: str) -> None:
    """Idempotent setup: headers, formatting, conditional rules per formatting spec."""
    # Write headers
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A1:K1",
        valueInputOption="USER_ENTERED",
        body={"values": [HEADERS]},
    ).execute()

    # Get sheetId (usually 0 for Sheet1)
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=sheet_id,
        fields="sheets.properties",
    ).execute()
    sid = spreadsheet["sheets"][0]["properties"]["sheetId"]

    # Clear existing conditional format rules to avoid duplicates
    try:
        spreadsheet_full = service.spreadsheets().get(
            spreadsheetId=sheet_id,
            fields="sheets.conditionalFormats",
        ).execute()
        existing_rules = spreadsheet_full["sheets"][0].get("conditionalFormats", [])
        if existing_rules:
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

    # Also clear any existing banding
    try:
        spreadsheet_bands = service.spreadsheets().get(
            spreadsheetId=sheet_id,
            fields="sheets.bandedRanges",
        ).execute()
        existing_bands = spreadsheet_bands["sheets"][0].get("bandedRanges", [])
        if existing_bands:
            band_deletes = [
                {"deleteBandedRange": {"bandedRangeId": b["bandedRangeId"]}}
                for b in existing_bands
            ]
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": band_deletes},
            ).execute()
    except Exception:
        pass

    # Data rows range (row 3 onward)
    row3_plus = {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 100, "startColumnIndex": 0, "endColumnIndex": NUM_COLS}

    requests_batch = [
        # === 1. Column widths ===
        *[
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": w},
                    "fields": "pixelSize",
                }
            }
            for i, w in enumerate([50, 90, 200, 80, 160, 280, 360, 160, 280, 110, 140])
        ],

        # === 2. Row 2 merge + banner styling ===
        {
            "mergeCells": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": NUM_COLS},
                "mergeType": "MERGE_ALL",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": NUM_COLS},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _hex("#e3f2fd"),
                        "textFormat": {"italic": True, "fontSize": 10, "foregroundColor": _hex("#1565c0")},
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
        {
            "updateBorders": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": NUM_COLS},
                "bottom": {"style": "SOLID_MEDIUM", "color": _hex("#90caf9")},
            }
        },

        # === 3. Header row styling ===
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": NUM_COLS},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _hex("#1a73e8"),
                        "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": _hex("#ffffff")},
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
        {
            "updateBorders": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": NUM_COLS},
                "bottom": {"style": "SOLID_MEDIUM", "color": _hex("#1557b0")},
            }
        },

        # === 4. Freeze header + banner ===
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
                "fields": "gridProperties.frozenRowCount",
            }
        },

        # === 5. Conditional formatting (exact RGB from pass2 spec) ===
        # READY NOW - green
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [row3_plus],
                    "booleanRule": {
                        "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=$B3="READY NOW"'}]},
                        "format": {
                            "backgroundColor": {"red": 0.831, "green": 0.929, "blue": 0.855},
                            "textFormat": {"foregroundColor": {"red": 0.082, "green": 0.341, "blue": 0.141}, "bold": True},
                        },
                    },
                },
                "index": 0,
            }
        },
        # HEADS UP - amber
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [row3_plus],
                    "booleanRule": {
                        "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=$B3="HEADS UP"'}]},
                        "format": {
                            "backgroundColor": {"red": 1.0, "green": 0.953, "blue": 0.804},
                            "textFormat": {"foregroundColor": {"red": 0.522, "green": 0.392, "blue": 0.016}, "bold": True},
                        },
                    },
                },
                "index": 1,
            }
        },
        # DONE - gray + strikethrough
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [row3_plus],
                    "booleanRule": {
                        "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=$B3="DONE"'}]},
                        "format": {
                            "backgroundColor": {"red": 0.886, "green": 0.890, "blue": 0.898},
                            "textFormat": {"foregroundColor": {"red": 0.424, "green": 0.459, "blue": 0.490}, "strikethrough": True},
                        },
                    },
                },
                "index": 2,
            }
        },
        # Upcoming - white bg only (column B muted via repeatCell below)
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [row3_plus],
                    "booleanRule": {
                        "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=$B3="Upcoming"'}]},
                        "format": {
                            "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                        },
                    },
                },
                "index": 3,
            }
        },

        # === 5e. Column B default muted gray for Upcoming rows ===
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 100, "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"textFormat": {"foregroundColor": {"red": 0.424, "green": 0.459, "blue": 0.490}}}},
                "fields": "userEnteredFormat.textFormat.foregroundColor",
            }
        },

        # === 6. Cell alignment ===
        # Centered columns: A(0), B(1), D(3), J(9)
        *[
            {
                "repeatCell": {
                    "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 100, "startColumnIndex": c, "endColumnIndex": c + 1},
                    "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER", "verticalAlignment": "TOP"}},
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)",
                }
            }
            for c in [0, 1, 3, 9]
        ],
        # Left-aligned columns: C(2), E(4), F(5), G(6), H(7), I(8), K(10)
        *[
            {
                "repeatCell": {
                    "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 100, "startColumnIndex": c, "endColumnIndex": c + 1},
                    "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT", "verticalAlignment": "TOP"}},
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)",
                }
            }
            for c in [2, 4, 5, 6, 7, 8, 10]
        ],

        # === 7. Text wrapping for F, G, H, I ===
        *[
            {
                "repeatCell": {
                    "range": {"sheetId": sid, "startColumnIndex": c, "endColumnIndex": c + 1},
                    "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                    "fields": "userEnteredFormat.wrapStrategy",
                }
            }
            for c in [5, 6, 7, 8]
        ],

        # === 8. Borders — data rows ===
        {
            "updateBorders": {
                "range": row3_plus,
                "top": {"style": "SOLID", "color": {"red": 0.871, "green": 0.886, "blue": 0.898}},
                "bottom": {"style": "SOLID", "color": {"red": 0.871, "green": 0.886, "blue": 0.898}},
                "left": {"style": "SOLID", "color": {"red": 0.871, "green": 0.886, "blue": 0.898}},
                "right": {"style": "SOLID", "color": {"red": 0.871, "green": 0.886, "blue": 0.898}},
                "innerHorizontal": {"style": "SOLID", "color": {"red": 0.871, "green": 0.886, "blue": 0.898}},
                "innerVertical": {"style": "SOLID", "color": {"red": 0.871, "green": 0.886, "blue": 0.898}},
            }
        },

        # === 9. Reason column - reduced font ===
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 100, "startColumnIndex": 5, "endColumnIndex": 6},
                "cell": {"userEnteredFormat": {"textFormat": {"fontSize": 9, "foregroundColor": _hex("#495057")}}},
                "fields": "userEnteredFormat.textFormat(fontSize,foregroundColor)",
            }
        },

        # === 10. Hide app_id column (K) ===
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 10, "endIndex": 11},
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser",
            }
        },

        # === 11. Minimum row height 36px + auto-resize ===
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 2, "endIndex": 100},
                "properties": {"pixelSize": 36},
                "fields": "pixelSize",
            }
        },
        {
            "autoResizeDimensions": {
                "dimensions": {"sheetId": sid, "dimension": "ROWS", "startIndex": 2, "endIndex": 100},
            }
        },
    ]

    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": requests_batch},
    ).execute()


def _apply_product_rich_text(service, sheet_id: str, product_runs_by_row: list, rows: list) -> None:
    """Apply bold product names to column G cells using textFormatRuns."""
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=sheet_id,
        fields="sheets.properties",
    ).execute()
    sid = spreadsheet["sheets"][0]["properties"]["sheetId"]

    update_requests = []
    for i, (runs, row) in enumerate(zip(product_runs_by_row, rows)):
        if not runs:
            continue
        product_text = row[6]  # Column G
        if not product_text:
            continue
        # Row index = i + 2 (row 3 is index 2, 0-based)
        update_requests.append({
            "updateCells": {
                "rows": [{
                    "values": [{
                        "userEnteredValue": {"stringValue": product_text},
                        "textFormatRuns": runs,
                        "userEnteredFormat": {
                            "wrapStrategy": "WRAP",
                            "verticalAlignment": "TOP",
                            "padding": {"top": 4, "bottom": 4, "left": 6, "right": 6},
                        },
                    }]
                }],
                "range": {
                    "sheetId": sid,
                    "startRowIndex": i + 2,
                    "endRowIndex": i + 3,
                    "startColumnIndex": 6,  # Column G
                    "endColumnIndex": 7,
                },
                "fields": "userEnteredValue,textFormatRuns,userEnteredFormat(wrapStrategy,verticalAlignment,padding)",
            }
        })

    if update_requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": update_requests},
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

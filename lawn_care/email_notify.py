"""Gmail email notifications for lawn care alerts."""

import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from lawn_care.google_auth import get_gmail_service
from lawn_care.notify import (
    _format_app_detail,
    _format_product_line,
    _format_conditions,
)

logger = logging.getLogger(__name__)


def _html_product_line(product: dict, area_sqft: float | None) -> str:
    """Format a single product as an HTML list item."""
    name = product["name"]
    ptype = product.get("type", "")
    rate_str = product.get("rate_per_1000sqft") or ""
    rate_oz = product.get("rate_per_1000sqft_oz")

    parts = [f"<strong>{name}</strong> ({ptype})"]

    if rate_oz is not None:
        if area_sqft:
            total_oz = rate_oz * (area_sqft / 1000)
            parts.append(f" &mdash; {rate_oz} oz/1k sqft, <strong>{total_oz:.1f} oz total</strong>")
        else:
            parts.append(f" &mdash; {rate_oz} oz/1k sqft")
    elif rate_str:
        parts.append(f" &mdash; {rate_str}/1k")

    html = "".join(parts)
    if product.get("notes"):
        html += f'<br><span style="color:#666;font-size:0.9em">{product["notes"]}</span>'

    return f"<li>{html}</li>"


def _html_conditions(app: dict) -> str:
    """Format conditions as HTML list items."""
    text_lines = _format_conditions(app)
    if not text_lines:
        return ""
    items = "".join(f"<li>{line.strip()}</li>" for line in text_lines)
    return f'<ul style="margin:4px 0">{items}</ul>'


def _html_app_detail(app: dict, area_sqft: float | None) -> str:
    """Format a full application detail block as HTML."""
    html = f'<h3 style="margin:12px 0 4px">{app["name"]}</h3>'
    html += f'<p style="margin:2px 0;color:#555">{app.get("reason", "")}</p>'

    if app.get("products"):
        html += '<p style="margin:8px 0 2px"><strong>Products:</strong></p><ul style="margin:4px 0">'
        for p in app["products"]:
            html += _html_product_line(p, area_sqft)
        html += "</ul>"

    cond_html = _html_conditions(app)
    if cond_html:
        html += f'<p style="margin:8px 0 2px"><strong>Conditions:</strong></p>{cond_html}'

    for w in app.get("warnings", []):
        html += f'<p style="color:#c00;margin:2px 0"><strong>!! {w}</strong></p>'

    return html


def _send_email(subject: str, html_body: str, text_body: str) -> bool:
    """Send an email via Gmail API to the authenticated user (self-send)."""
    service = get_gmail_service()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = "me"
    msg["From"] = "me"

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        logger.info(f"Email sent: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_ready_email(
    app: dict[str, Any],
    soil_temp: float | None,
    area_sqft: float | None,
    config: dict[str, Any],
) -> bool:
    """Send a READY NOW email for a single application."""
    subject = f"Lawn Care READY: {app['name']}"

    # HTML body
    html = f"""
    <div style="font-family:sans-serif;max-width:600px">
        <div style="background:#2d7a2d;color:white;padding:12px 16px;border-radius:8px 8px 0 0">
            <h2 style="margin:0">Ready Now</h2>
        </div>
        <div style="padding:16px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px">
    """
    if soil_temp is not None:
        html += f'<p style="margin:0 0 12px"><strong>Soil temp (4"):</strong> {soil_temp}F</p>'

    html += _html_app_detail(app, area_sqft)
    html += """
        </div>
    </div>
    """

    # Plaintext fallback
    text = _format_app_detail(app, area_sqft)
    if soil_temp is not None:
        text = f'Soil temp (4"): {soil_temp}F\n\n' + text

    return _send_email(subject, html, text)


def send_heads_up_email(
    apps: list[dict[str, Any]],
    soil_temp: float | None,
    projections: list[dict] | None,
    area_sqft: float | None,
    config: dict[str, Any],
) -> bool:
    """Send a HEADS UP summary email for approaching applications."""
    names = ", ".join(a["name"] for a in apps[:3])
    subject = f"Lawn Care HEADS UP: {names}"

    # HTML body
    html = f"""
    <div style="font-family:sans-serif;max-width:600px">
        <div style="background:#b8860b;color:white;padding:12px 16px;border-radius:8px 8px 0 0">
            <h2 style="margin:0">Heads Up - Prep These Products</h2>
        </div>
        <div style="padding:16px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px">
    """

    if soil_temp is not None:
        html += f'<p style="margin:0"><strong>Soil temp (4"):</strong> {soil_temp}F</p>'
        if projections:
            temps = [f"{p['projected_soil_temp']:.0f}" for p in projections[:7]]
            html += f'<p style="margin:2px 0;color:#555">7-day soil forecast: {" &rarr; ".join(temps)}F</p>'

    for app in apps:
        html += "<hr>" + _html_app_detail(app, area_sqft)

    html += """
        </div>
    </div>
    """

    # Plaintext fallback
    text_lines = []
    if soil_temp is not None:
        text_lines.append(f'Soil temp (4"): {soil_temp}F')
        if projections:
            temps = [f"{p['projected_soil_temp']:.0f}" for p in projections[:7]]
            text_lines.append(f"  7-day soil forecast: {' > '.join(temps)}F")
    text_lines.append("")
    text_lines.append("=== HEADS UP - Prep these products ===")
    for app in apps:
        text_lines.append("")
        text_lines.append(_format_app_detail(app, area_sqft))

    return _send_email(subject, html, "\n".join(text_lines))

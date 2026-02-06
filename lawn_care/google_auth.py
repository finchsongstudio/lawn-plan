"""OAuth2 authentication for Google Sheets and Gmail APIs."""

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_credentials() -> Credentials:
    """Load or refresh OAuth2 credentials, triggering browser auth on first run."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired OAuth2 token")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"OAuth2 client config not found at {CREDENTIALS_PATH}. "
                    "Download it from Google Cloud Console."
                )
            logger.info("Starting browser OAuth2 flow")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json())
        logger.info(f"Token saved to {TOKEN_PATH}")

    return creds


def get_sheets_service():
    """Build and return a Google Sheets API service object."""
    return build("sheets", "v4", credentials=get_credentials())


def get_gmail_service():
    """Build and return a Gmail API service object."""
    return build("gmail", "v1", credentials=get_credentials())

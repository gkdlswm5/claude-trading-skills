"""Shared Google OAuth helper for the morning-trading-briefing v2.0 write path.

Both the Calendar and Drive clients authenticate through this module so a single
`token.json` (granted both scopes in one consent flow) works for both. See
`references/GOOGLE_API_SETUP.md` for the one-time Cloud Console setup.

All `google-*` imports are deferred into function bodies so this module — and the
clients that import it — stay importable (and unit-testable with fake services)
even when the Google libraries are not installed and before credentials exist.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Combined scopes requested at consent time. Keep both here so one token.json
# covers Calendar (read/write) + Drive (only files this app creates).
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.file",
]

# Default credential locations (outside the public repo). Override via env or the
# client CLIs. `~` expands per-machine; on Windows this is C:\Users\<you>\...
DEFAULT_CONFIG_DIR = Path(
    os.environ.get("MTB_CONFIG_DIR", "~/.config/morning-briefing")
).expanduser()
DEFAULT_CREDENTIALS_PATH = str(DEFAULT_CONFIG_DIR / "credentials.json")
DEFAULT_TOKEN_PATH = str(DEFAULT_CONFIG_DIR / "token.json")


def load_credentials(
    credentials_path: str,
    token_path: str,
    scopes: list[str] | None = None,
) -> Any:
    """Return valid Google credentials, running or refreshing OAuth as needed.

    Behavior:
      - If `token_path` exists and is valid, load and return it.
      - If it is expired but has a refresh token, refresh it (no browser).
      - Otherwise run the InstalledAppFlow (opens a browser once).
    The (possibly new/refreshed) token is always written back to `token_path`.

    Args:
        credentials_path: Path to credentials.json (the OAuth client secret).
        token_path: Path to token.json (created/refreshed here).
        scopes: OAuth scopes; defaults to the combined SCOPES.

    Returns:
        A google.oauth2.credentials.Credentials object.
    """
    # Deferred imports — only needed when actually authenticating.
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    scopes = scopes or SCOPES
    cred_path = Path(credentials_path).expanduser()
    tok_path = Path(token_path).expanduser()

    creds = None
    if tok_path.exists():
        creds = Credentials.from_authorized_user_file(str(tok_path), scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not cred_path.exists():
            raise FileNotFoundError(
                f"credentials.json not found at {cred_path}. Download it from the "
                "Google Cloud Console (APIs & Services -> Credentials -> your OAuth "
                "client -> Download JSON) and place it there. See "
                "references/GOOGLE_API_SETUP.md."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), scopes)
        creds = flow.run_local_server(port=0)

    tok_path.parent.mkdir(parents=True, exist_ok=True)
    tok_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_service(api: str, version: str, credentials: Any) -> Any:
    """Build a discovery client for `api`/`version` with the given credentials."""
    from googleapiclient.discovery import build

    return build(api, version, credentials=credentials, cache_discovery=False)

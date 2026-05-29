"""Direct Google Drive API client for the morning-trading-briefing.

Writes the rendered brief markdown to a Drive folder, overwriting the
canonical per-day file on rerun. Pair with google_calendar_client.py to
remove the LLM from all mechanical write operations.

The `drive.file` scope (vs the broader `drive`) limits this app to files
it created. The first run inside a folder creates the markdown; later
runs find the same file by name + folder and replace its content. The
file ID is stable across runs, so links shared from the first run still
point at the latest content.

See `references/GOOGLE_API_SETUP.md` for OAuth setup and v2.0 in
`state/HANDOFF.md` for the slice plan. Run the CLI in
google_calendar_client.py with --authenticate to mint the shared
token.json — this module never opens a browser.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Drive scope: only files this app creates. Does not expose existing Drive
# contents. The morning-trading-briefing union token includes Calendar +
# drive.file; see google_calendar_client._cli().
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

MIME_MARKDOWN = "text/markdown"


def authenticate(
    credentials_path: str | Path,
    token_path: str | Path,
    scopes: list[str] | None = None,
    interactive: bool = False,
) -> Any:
    """Return an authenticated Drive v3 service.

    Delegates the token load/refresh to google_calendar_client so both
    modules share the same OAuth state — token.json is single-file by
    design.

    Args:
        credentials_path: Path to credentials.json (Google Cloud Console).
        token_path: Path to token.json (shared with the Calendar client).
        scopes: Override scopes. Defaults to this module's SCOPES; pass the
            union when sharing token.json with google_calendar_client.
        interactive: When True, run the OAuth flow if no token exists. Cron
            callers should keep this False so failures surface loudly
            instead of hanging on a browser prompt.

    Returns:
        A googleapiclient.discovery.Resource for the Drive v3 API.
    """
    # Import inside the function so the module loads even when google-* libs
    # aren't installed (unit tests, --dry-run path).
    from googleapiclient.discovery import build

    from google_calendar_client import _load_or_refresh_credentials

    creds = _load_or_refresh_credentials(
        credentials_path, token_path, scopes or SCOPES, interactive=interactive
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def find_file_by_name(service: Any, folder_id: str, filename: str) -> str | None:
    """Return the Drive file ID for `filename` inside `folder_id`, or None.

    Only finds files this app's `drive.file` scope can see — i.e. files
    created by this app in prior runs. Hand-created files with the same
    name are invisible, which is the intended privacy guarantee.
    """
    # Drive query strings are 'mostly' SQL-ish; single quotes inside string
    # literals must be escaped with backslash. Filenames with apostrophes
    # are rare for our YYYY-MM-DD-{mode}.md pattern but cheap to handle.
    safe_name = filename.replace("\\", "\\\\").replace("'", "\\'")
    safe_folder = folder_id.replace("\\", "\\\\").replace("'", "\\'")
    q = (
        f"name = '{safe_name}' and "
        f"'{safe_folder}' in parents and "
        f"trashed = false"
    )
    resp = (
        service.files()
        .list(q=q, fields="files(id, name)", pageSize=10, spaces="drive")
        .execute()
    )
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def upsert_markdown(
    service: Any,
    folder_id: str,
    filename: str,
    content: str,
) -> dict:
    """Create or overwrite a markdown file in the Drive folder.

    Canonical naming: `YYYY-MM-DD-{morning|afternoon}.md`. Same filename +
    same folder = same file ID across reruns; content is replaced. This
    is the Drive analog of upsert_event() — deterministic by construction.

    Args:
        service: Authenticated Drive API client.
        folder_id: Target folder ID (from `drive.briefings_folder_id` in
            config.yaml).
        filename: Filename in the folder (e.g. 2026-05-27-morning.md).
        content: Full markdown body to write.

    Returns:
        The Drive file resource dict (id, name, modifiedTime, webViewLink).
    """
    from googleapiclient.http import MediaInMemoryUpload

    media = MediaInMemoryUpload(
        content.encode("utf-8"), mimetype=MIME_MARKDOWN, resumable=False
    )
    existing_id = find_file_by_name(service, folder_id, filename)
    fields = "id, name, modifiedTime, webViewLink"
    if existing_id:
        # Update content in place — file ID, share links, comments persist.
        return (
            service.files()
            .update(fileId=existing_id, media_body=media, fields=fields)
            .execute()
        )
    body = {"name": filename, "parents": [folder_id], "mimeType": MIME_MARKDOWN}
    return (
        service.files()
        .create(body=body, media_body=media, fields=fields)
        .execute()
    )


if __name__ == "__main__":
    import sys

    print(
        "Drive client has no standalone CLI — run "
        "`python3 google_calendar_client.py --authenticate` to mint the "
        "shared token.json, then use upsert_markdown() from "
        "write_brief_outputs.py.",
        file=sys.stderr,
    )
    sys.exit(1)

"""Direct Google Drive API client for the morning-trading-briefing.

Writes the rendered brief markdown to a Drive folder, overwriting the canonical
per-day file on rerun. Pair with google_calendar_client.py to remove the LLM
from all mechanical write operations.

See `references/GOOGLE_API_SETUP.md` for OAuth setup and v2.0 in
`state/HANDOFF.md` for implementation order. googleapiclient imports are
deferred so this module imports (and unit-tests with a fake service) without the
Google libraries installed.
"""

from __future__ import annotations

from typing import Any

# Drive scope: only files this app creates. Does not expose existing Drive
# contents. (Requested combined with Calendar by google_oauth.)
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

MARKDOWN_MIME = "text/markdown"


def authenticate(credentials_path: str, token_path: str) -> Any:
    """Run OAuth flow (first time) or refresh existing token.

    Returns an authenticated googleapiclient.discovery.Resource for Drive v3.
    Shares the same token.json as the Calendar client — google_oauth requests
    both scopes in a single consent flow.
    """
    from google_oauth import SCOPES as ALL_SCOPES
    from google_oauth import build_service, load_credentials

    creds = load_credentials(credentials_path, token_path, ALL_SCOPES)
    return build_service("drive", "v3", creds)


def _make_media(content: str) -> Any:
    """Build an in-memory upload body for markdown. Deferred import seam (tests
    monkeypatch this to avoid needing googleapiclient)."""
    from googleapiclient.http import MediaInMemoryUpload

    return MediaInMemoryUpload(content.encode("utf-8"), mimetype=MARKDOWN_MIME, resumable=False)


def find_file_by_name(service: Any, folder_id: str, filename: str) -> str | None:
    """Return the Drive file ID for `filename` inside `folder_id`, or None.

    Used by upsert_markdown to decide create-vs-update. Only sees files this app
    created (drive.file scope).
    """
    safe_name = filename.replace("\\", "\\\\").replace("'", "\\'")
    query = f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false"
    resp = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
            pageSize=10,
        )
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

    Canonical naming: `YYYY-MM-DD-{morning|afternoon}.md`. Same filename + same
    folder = same file ID across reruns; content is replaced in place (unlike the
    old MCP path, which could only create and so versioned duplicates).

    Args:
        service: Authenticated Drive API client.
        folder_id: Target folder ID (from `drive.briefings_folder_id`).
        filename: Filename in the folder (e.g. 2026-05-27-morning.md).
        content: Full markdown body to write.

    Returns:
        The Drive file resource dict (id, name, modifiedTime, etc.).
    """
    media = _make_media(content)
    existing_id = find_file_by_name(service, folder_id, filename)
    fields = "id, name, modifiedTime, webViewLink"

    if existing_id:
        return (
            service.files()
            .update(fileId=existing_id, media_body=media, fields=fields)
            .execute()
        )

    metadata = {"name": filename, "parents": [folder_id], "mimeType": MARKDOWN_MIME}
    return (
        service.files()
        .create(body=metadata, media_body=media, fields=fields)
        .execute()
    )


def _cli(argv: list[str]) -> int:
    import argparse

    from google_oauth import DEFAULT_CREDENTIALS_PATH, DEFAULT_TOKEN_PATH

    ap = argparse.ArgumentParser(description="Drive client OAuth + sanity check.")
    ap.add_argument(
        "--authenticate",
        action="store_true",
        help="Run/refresh the OAuth flow and write token.json.",
    )
    ap.add_argument("--credentials", default=DEFAULT_CREDENTIALS_PATH)
    ap.add_argument("--token", default=DEFAULT_TOKEN_PATH)
    args = ap.parse_args(argv)

    if not args.authenticate:
        ap.print_help()
        return 1

    authenticate(args.credentials, args.token)
    print(f"Authenticated. Token at: {args.token}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli(sys.argv[1:]))

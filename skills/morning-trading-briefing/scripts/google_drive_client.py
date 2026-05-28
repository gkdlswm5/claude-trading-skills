"""Direct Google Drive API client for the morning-trading-briefing.

Writes the rendered brief markdown to a Drive folder, overwriting the
canonical per-day file on rerun. Pair with google_calendar_client.py
to remove the LLM from all mechanical write operations.

Implementation scaffold — function bodies raise NotImplementedError.
See `references/GOOGLE_API_SETUP.md` for OAuth setup and v2.0 in
`state/HANDOFF.md` for implementation order.
"""

from __future__ import annotations

from typing import Any

# Drive scope: only files this app creates. Does not expose existing Drive
# contents.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def authenticate(credentials_path: str, token_path: str) -> Any:
    """Run OAuth flow (first time) or refresh existing token.

    Returns an authenticated googleapiclient.discovery.Resource for Drive v3.
    Typically shares the same token.json as the Calendar client when both
    scopes are requested in a single consent flow.
    """
    raise NotImplementedError("v2.0 work item — see HANDOFF.md")


def find_file_by_name(service: Any, folder_id: str, filename: str) -> str | None:
    """Return the Drive file ID for `filename` inside `folder_id`, or None.

    Used by upsert_markdown to determine create-vs-update.
    """
    raise NotImplementedError("v2.0 work item — see HANDOFF.md")


def upsert_markdown(
    service: Any,
    folder_id: str,
    filename: str,
    content: str,
) -> dict:
    """Create or overwrite a markdown file in the Drive folder.

    Canonical naming: `YYYY-MM-DD-{morning|afternoon}.md`. Same filename
    + same folder = same file ID across reruns; content is replaced.

    Args:
        service: Authenticated Drive API client.
        folder_id: Target folder ID (from `drive.briefings_folder_id` in
            config.yaml).
        filename: Filename in the folder (e.g. 2026-05-27-morning.md).
        content: Full markdown body to write.

    Returns:
        The Drive file resource dict (id, name, modifiedTime, etc.).
    """
    raise NotImplementedError("v2.0 work item — see HANDOFF.md")


if __name__ == "__main__":
    import sys

    print("v2.0 scaffold — implementation pending. See HANDOFF.md.", file=sys.stderr)
    sys.exit(1)

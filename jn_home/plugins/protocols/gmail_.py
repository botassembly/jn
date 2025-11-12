#!/usr/bin/env -S uv run --script
"""Gmail API plugin for reading Gmail messages."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-api-python-client>=2.100.0",
#   "google-auth-httplib2>=0.2.0",
#   "google-auth-oauthlib>=1.2.0",
# ]
# [tool.jn]
# matches = [
#   "^gmail://.*"
# ]
# ///

import base64
import json
import os
import sys
from pathlib import Path
from typing import Iterator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Default token path
DEFAULT_TOKEN_PATH = Path.home() / ".jn" / "gmail-token.json"


def error_record(error_type: str, message: str, **extra) -> dict:
    """Create standardized error record."""
    return {"_error": True, "type": error_type, "message": message, **extra}


def get_credentials(token_path: Path = None, credentials_path: Path = None) -> Credentials:
    """Get or create Gmail API credentials with OAuth2.

    Args:
        token_path: Path to save/load token (default: ~/.jn/gmail-token.json)
        credentials_path: Path to OAuth2 credentials.json (default: ~/.jn/gmail-credentials.json)

    Returns:
        Valid Credentials object
    """
    token_path = token_path or DEFAULT_TOKEN_PATH
    credentials_path = credentials_path or (Path.home() / ".jn" / "gmail-credentials.json")

    creds = None

    # Load existing token if it exists
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh or authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token
            creds.refresh(Request())
        else:
            # No valid token - need to authenticate
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Gmail credentials not found at {credentials_path}\n"
                    "Download OAuth2 credentials from Google Cloud Console:\n"
                    "1. Go to https://console.cloud.google.com/apis/credentials\n"
                    "2. Create OAuth 2.0 Client ID (Desktop app)\n"
                    "3. Download JSON and save to ~/.jn/gmail-credentials.json"
                )

            # Run OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future use
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return creds


def build_gmail_query(params: dict) -> str:
    """Convert parameters to Gmail query syntax.

    Args:
        params: Dict of search parameters, e.g., {"from": "user@example.com", "after": "2024/01/01"}

    Returns:
        Gmail query string, e.g., "from:user@example.com after:2024/01/01"

    Examples:
        >>> build_gmail_query({"from": "boss@company.com", "is": "unread"})
        'from:boss@company.com is:unread'

        >>> build_gmail_query({"from": ["user1@example.com", "user2@example.com"]})
        'from:user1@example.com from:user2@example.com'
    """
    query_parts = []

    for key, value in params.items():
        # Handle list values (multiple -p with same key)
        if isinstance(value, list):
            for v in value:
                query_parts.append(f"{key}:{v}")
        else:
            query_parts.append(f"{key}:{value}")

    return " ".join(query_parts)


def parse_message(msg: dict, format: str = "full") -> dict:
    """Parse Gmail message into NDJSON record.

    Args:
        msg: Gmail API message object
        format: Message format (minimal, metadata, full)

    Returns:
        Normalized message record
    """
    record = {
        "id": msg["id"],
        "thread_id": msg["threadId"],
    }

    # Add metadata if available
    if "labelIds" in msg:
        record["labels"] = msg["labelIds"]

    if "snippet" in msg:
        record["snippet"] = msg["snippet"]

    if "internalDate" in msg:
        record["internal_date"] = msg["internalDate"]
        # Convert to human-readable timestamp (milliseconds to seconds)
        import datetime
        timestamp = int(msg["internalDate"]) / 1000
        record["date"] = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).isoformat()

    # Parse headers for metadata/full format
    if "payload" in msg and "headers" in msg["payload"]:
        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}

        # Extract common headers
        record["from"] = headers.get("from")
        record["to"] = headers.get("to")
        record["cc"] = headers.get("cc")
        record["bcc"] = headers.get("bcc")
        record["subject"] = headers.get("subject")
        record["date_header"] = headers.get("date")

        # Store all headers if full format
        if format == "full":
            record["headers"] = headers

    # Parse body for full format
    if format == "full" and "payload" in msg:
        payload = msg["payload"]

        # Extract body
        body_text = None
        body_html = None

        if "body" in payload and "data" in payload["body"]:
            # Simple body
            body_text = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        elif "parts" in payload:
            # Multipart message
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                if "body" in part and "data" in part["body"]:
                    data = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

                    if mime_type == "text/plain" and not body_text:
                        body_text = data
                    elif mime_type == "text/html" and not body_html:
                        body_html = data

        record["body_text"] = body_text
        record["body_html"] = body_html

        # Extract attachments metadata
        attachments = []
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("filename"):
                    attachments.append({
                        "filename": part["filename"],
                        "mime_type": part.get("mimeType"),
                        "size": part.get("body", {}).get("size", 0),
                        "attachment_id": part.get("body", {}).get("attachmentId"),
                    })

        if attachments:
            record["attachments"] = attachments

    return record


def reads(
    user_id: str = "me",
    max_results: int = 500,
    include_spam_trash: bool = False,
    format: str = "full",
    label_ids: str = None,
    token_path: str = None,
    credentials_path: str = None,
    **params
) -> Iterator[dict]:
    """Fetch Gmail messages and yield NDJSON records.

    Args:
        user_id: Gmail user ID (default: 'me')
        max_results: Max messages per page (API limit: 500)
        include_spam_trash: Include spam/trash folders
        format: Message format - 'minimal', 'metadata', or 'full' (default: 'full')
        label_ids: Comma-separated label IDs to filter by
        token_path: Path to OAuth token file
        credentials_path: Path to OAuth credentials file
        **params: Search parameters passed via -p flags (from, to, subject, etc.)

    Yields:
        Dict records with message data
    """
    try:
        # Get credentials
        token_p = Path(token_path) if token_path else None
        creds_p = Path(credentials_path) if credentials_path else None
        creds = get_credentials(token_path=token_p, credentials_path=creds_p)

        # Build Gmail API service
        service = build("gmail", "v1", credentials=creds)

        # Build query from parameters (pushdown to API)
        query = build_gmail_query(params) if params else None

        # Parse label_ids if provided
        labels = label_ids.split(",") if label_ids else None

        # Paginate through results
        page_token = None
        message_count = 0

        while True:
            # List messages
            list_params = {
                "userId": user_id,
                "maxResults": min(max_results, 500),  # API limit
                "includeSpamTrash": include_spam_trash,
            }

            if query:
                list_params["q"] = query

            if labels:
                list_params["labelIds"] = labels

            if page_token:
                list_params["pageToken"] = page_token

            results = service.users().messages().list(**list_params).execute()

            messages = results.get("messages", [])
            if not messages:
                break

            # Fetch full message details
            for msg_ref in messages:
                try:
                    # Get full message
                    msg = service.users().messages().get(
                        userId=user_id,
                        id=msg_ref["id"],
                        format=format,
                    ).execute()

                    # Parse and yield
                    yield parse_message(msg, format=format)
                    message_count += 1

                except HttpError as e:
                    yield error_record(
                        "gmail_api_error",
                        f"Failed to fetch message {msg_ref['id']}: {str(e)}",
                        message_id=msg_ref["id"],
                    )

            # Check for next page
            page_token = results.get("nextPageToken")
            if not page_token:
                break

    except FileNotFoundError as e:
        yield error_record("credentials_not_found", str(e))

    except HttpError as e:
        yield error_record("gmail_api_error", f"Gmail API error: {str(e)}")

    except Exception as e:
        yield error_record("unexpected_error", f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gmail protocol plugin")
    parser.add_argument("--mode", choices=["read"], help="Operation mode")
    parser.add_argument("url", nargs="?", help="Gmail URL (e.g., gmail://me/messages)")
    parser.add_argument("--user-id", default="me", help="Gmail user ID")
    parser.add_argument("--max-results", type=int, default=500, help="Max results per page")
    parser.add_argument("--include-spam-trash", action="store_true", help="Include spam/trash")
    parser.add_argument(
        "--format",
        choices=["minimal", "metadata", "full"],
        default="full",
        help="Message format",
    )
    parser.add_argument("--label-ids", help="Comma-separated label IDs")
    parser.add_argument("--token-path", help="Path to OAuth token file")
    parser.add_argument("--credentials-path", help="Path to OAuth credentials file")

    # Gmail search parameters (all optional, passed through to query)
    # These will be built into the 'q' parameter
    parser.add_argument("--from", dest="from_", help="From email/name")
    parser.add_argument("--to", help="To email/name")
    parser.add_argument("--subject", help="Subject keywords")
    parser.add_argument("--cc", help="CC email/name")
    parser.add_argument("--bcc", help="BCC email/name")
    parser.add_argument("--has", help="Attachment type (attachment, drive, pdf, etc.)")
    parser.add_argument("--filename", help="Attachment filename")
    parser.add_argument("--is", help="Message status (starred, unread, important, etc.)")
    parser.add_argument("--in", dest="in_", help="Folder (inbox, spam, trash)")
    parser.add_argument("--label", help="Label name")
    parser.add_argument("--after", help="After date (YYYY/MM/DD)")
    parser.add_argument("--before", help="Before date (YYYY/MM/DD)")
    parser.add_argument("--newer-than", help="Newer than relative (7d, 1m, 1y)")
    parser.add_argument("--older-than", help="Older than relative (7d, 1m, 1y)")
    parser.add_argument("--size", help="Size in bytes")
    parser.add_argument("--larger", help="Larger than size")
    parser.add_argument("--smaller", help="Smaller than size")

    args = parser.parse_args()

    if not args.mode:
        parser.error("--mode is required")

    # Build params dict from CLI args
    params = {}
    param_mapping = {
        "from_": "from",
        "to": "to",
        "subject": "subject",
        "cc": "cc",
        "bcc": "bcc",
        "has": "has",
        "filename": "filename",
        "is": "is",
        "in_": "in",
        "label": "label",
        "after": "after",
        "before": "before",
        "newer_than": "newer_than",
        "older_than": "older_than",
        "size": "size",
        "larger": "larger",
        "smaller": "smaller",
    }

    for arg_name, param_name in param_mapping.items():
        value = getattr(args, arg_name, None)
        if value:
            params[param_name] = value

    # Call reads() and output NDJSON
    try:
        for record in reads(
            user_id=args.user_id,
            max_results=args.max_results,
            include_spam_trash=args.include_spam_trash,
            format=args.format,
            label_ids=args.label_ids,
            token_path=args.token_path,
            credentials_path=args.credentials_path,
            **params,
        ):
            print(json.dumps(record), flush=True)
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        sys.exit(0)

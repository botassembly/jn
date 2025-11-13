#!/usr/bin/env -S uv run --script
"""Gmail API plugin for reading Gmail messages.

This plugin enables reading from Gmail using:
- Gmail URLs: gmail://me/messages?from=boss&is=unread

Examples:
    # Fetch unread messages from specific sender
    jn cat "gmail://me/messages?from=boss&is=unread"

    # List available labels and folders
    jn inspect "gmail://me"
"""
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


def get_credentials(
    token_path: Path | None = None, credentials_path: Path | None = None
) -> Credentials:
    """Get or create Gmail API credentials with OAuth2.

    Args:
        token_path: Path to save/load token (default: ~/.jn/gmail-token.json)
        credentials_path: Path to OAuth2 credentials.json (default: ~/.jn/gmail-credentials.json)

    Returns:
        Valid Credentials object
    """
    token_path = token_path or DEFAULT_TOKEN_PATH
    credentials_path = credentials_path or (
        Path.home() / ".jn" / "gmail-credentials.json"
    )

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
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
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


def _walk_parts(
    part: dict, body_text: list, body_html: list, attachments: list
):
    """Recursively walk MIME parts to extract bodies and attachments.

    Args:
        part: MIME part dict
        body_text: List to collect text/plain bodies
        body_html: List to collect text/html bodies
        attachments: List to collect attachment metadata
    """
    mime_type = part.get("mimeType", "")

    # If this part has sub-parts, recurse
    if "parts" in part:
        for subpart in part["parts"]:
            _walk_parts(subpart, body_text, body_html, attachments)
        return

    # Extract body data if present
    if "body" in part and "data" in part["body"]:
        data = base64.urlsafe_b64decode(part["body"]["data"]).decode(
            "utf-8", errors="replace"
        )

        if mime_type == "text/plain":
            body_text.append(data)
        elif mime_type == "text/html":
            body_html.append(data)

    # Extract attachment metadata
    if part.get("filename"):
        attachments.append(
            {
                "filename": part["filename"],
                "mime_type": mime_type,
                "size": part.get("body", {}).get("size", 0),
                "attachment_id": part.get("body", {}).get("attachmentId"),
            }
        )


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
        record["date"] = datetime.datetime.fromtimestamp(
            timestamp, tz=datetime.timezone.utc
        ).isoformat()

    # Parse headers for metadata/full format
    if "payload" in msg and "headers" in msg["payload"]:
        headers = {
            h["name"].lower(): h["value"] for h in msg["payload"]["headers"]
        }

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

        body_text_parts = []
        body_html_parts = []
        attachments = []

        # Simple body (no multipart)
        if "body" in payload and "data" in payload["body"]:
            mime_type = payload.get("mimeType", "")
            data = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="replace"
            )
            if mime_type == "text/plain":
                body_text_parts.append(data)
            elif mime_type == "text/html":
                body_html_parts.append(data)

        # Multipart - walk recursively
        if "parts" in payload:
            for part in payload["parts"]:
                _walk_parts(
                    part, body_text_parts, body_html_parts, attachments
                )

        # Join multiple parts (some emails have multiple text/plain parts)
        record["body_text"] = (
            "\n".join(body_text_parts) if body_text_parts else None
        )
        record["body_html"] = (
            "\n".join(body_html_parts) if body_html_parts else None
        )

        if attachments:
            record["attachments"] = attachments

    return record


def reads(
    url: str,
    limit: int | None = None,
    max_results: int = 500,
    include_spam_trash: bool = False,
    format: str = "full",
    label_ids: str | None = None,
    token_path: str | None = None,
    credentials_path: str | None = None,
    **params,
) -> Iterator[dict]:
    """Fetch Gmail messages or list labels depending on URL.

    Container vs Leaf:
    - Container (gmail://me): Lists available labels with _type and _container metadata
    - Leaf (gmail://me/INBOX or ?label_ids=...): Fetches messages

    Args:
        url: Gmail URL (gmail://user_id[/label]?params)
        limit: Maximum number of records to return (optional)
        max_results: Max messages per page for API pagination (API limit: 500)
        include_spam_trash: Include spam/trash folders
        format: Message format - 'minimal', 'metadata', or 'full' (default: 'full')
        label_ids: Comma-separated label IDs to filter by
        token_path: Path to OAuth token file
        credentials_path: Path to OAuth credentials file
        **params: Search parameters (from, to, subject, etc.)

    Yields:
        Dict records with message data or label listings
    """
    from urllib.parse import urlparse

    # Parse URL
    parsed = urlparse(url)
    user_id = parsed.netloc or "me"

    # Check if this is a container (no path/label specified)
    is_container = not parsed.path or parsed.path == "/"
    is_container = is_container and not label_ids and not params.get("q")

    if is_container:
        # Container: List available labels
        try:
            token_p = Path(token_path) if token_path else None
            creds_p = Path(credentials_path) if credentials_path else None
            creds = get_credentials(token_path=token_p, credentials_path=creds_p)

            service = build("gmail", "v1", credentials=creds)

            # Get profile info
            profile = service.users().getProfile(userId=user_id).execute()

            # List all labels
            labels_result = service.users().labels().list(userId=user_id).execute()
            labels = labels_result.get("labels", [])

            # Yield labels with metadata
            count = 0
            for label in labels:
                record = {
                    "id": label["id"],
                    "name": label["name"],
                    "type": label.get("type", "user").lower(),
                    "messagesTotal": label.get("messagesTotal", 0),
                    "messagesUnread": label.get("messagesUnread", 0),
                    "email": profile.get("emailAddress"),
                    "_type": "label",
                    "_container": f"gmail://{user_id}",
                }
                yield record
                count += 1
                if limit and count >= limit:
                    return

        except FileNotFoundError as e:
            yield error_record("credentials_not_found", str(e))
            return
        except HttpError as e:
            yield error_record("gmail_api_error", f"Gmail API error: {e!s}")
            return

        return

    # Leaf: Fetch messages
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
        count = 0

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
                    msg = (
                        service.users()
                        .messages()
                        .get(
                            userId=user_id,
                            id=msg_ref["id"],
                            format=format,
                        )
                        .execute()
                    )

                    # Parse and yield
                    yield parse_message(msg, format=format)

                    # Apply limit if specified
                    count += 1
                    if limit and count >= limit:
                        return

                except HttpError as e:
                    yield error_record(
                        "gmail_api_error",
                        f"Failed to fetch message {msg_ref['id']}: {e!s}",
                        message_id=msg_ref["id"],
                    )

            # Check for next page
            page_token = results.get("nextPageToken")
            if not page_token:
                break

    except FileNotFoundError as e:
        yield error_record("credentials_not_found", str(e))

    except HttpError as e:
        yield error_record("gmail_api_error", f"Gmail API error: {e!s}")


if __name__ == "__main__":
    import argparse
    from urllib.parse import parse_qs, urlparse

    parser = argparse.ArgumentParser(description="Gmail protocol plugin")
    parser.add_argument(
        "--mode", choices=["read"], required=True, help="Operation mode"
    )
    parser.add_argument(
        "url",
        help="Gmail URL (e.g., gmail://me or gmail://me/messages?from=boss&is=unread)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Maximum number of records to return"
    )
    parser.add_argument(
        "--max-results", type=int, default=500, help="Max results per page (API pagination)"
    )
    parser.add_argument(
        "--include-spam-trash", action="store_true", help="Include spam/trash"
    )
    parser.add_argument(
        "--format",
        choices=["minimal", "metadata", "full"],
        default="full",
        help="Message format",
    )
    parser.add_argument("--token-path", help="Path to OAuth token file")
    parser.add_argument(
        "--credentials-path", help="Path to OAuth credentials file"
    )

    args = parser.parse_args()

    # Parse gmail:// URL
    # Expected format: gmail://user_id[/endpoint]?from=boss&is=unread
    parsed = urlparse(args.url)

    if parsed.scheme != "gmail":
        print(
            json.dumps(
                error_record(
                    "invalid_url",
                    f"URL must start with gmail://, got: {args.url}",
                )
            ),
            flush=True,
        )
        sys.exit(1)

    # Parse query string into params dict
    params = {}
    if parsed.query:
        parsed_params = parse_qs(parsed.query)
        for key, values in parsed_params.items():
            params[key] = values[0] if len(values) == 1 else values

    # Call reads() and output NDJSON
    try:
        for record in reads(
            url=args.url,
            limit=args.limit,
            max_results=args.max_results,
            include_spam_trash=args.include_spam_trash,
            format=args.format,
            token_path=args.token_path,
            credentials_path=args.credentials_path,
            **params,
        ):
            print(json.dumps(record), flush=True)
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        sys.exit(0)

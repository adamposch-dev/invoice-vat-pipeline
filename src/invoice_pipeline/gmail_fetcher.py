"""Gmail API OAuth2 client for fetching invoice PDF attachments."""

import base64
from pathlib import Path
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service(credentials_path: Path, token_path: Path):
    """Authenticate via OAuth2 and return a Gmail API v1 service client."""
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Missing OAuth client secrets file: {credentials_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._\-]", "_", Path(name).name)


def _iter_attachment_parts(payload: dict):
    for part in payload.get("parts", []):
        if part.get("filename"):
            yield part
        if "parts" in part:
            yield from _iter_attachment_parts(part)


def fetch_invoice_attachments(
    service,
    query: str,
    download_dir: Path,
    extensions: tuple[str, ...] = (".pdf",),
) -> list[Path]:
    """Download matching message attachments from Gmail into download_dir."""
    download_dir.mkdir(parents=True, exist_ok=True)
    response = service.users().messages().list(userId="me", q=query).execute()
    saved_paths: list[Path] = []

    for msg in response.get("messages", []):
        msg_id = msg["id"]
        detail = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        payload = detail.get("payload", {})
        for part in _iter_attachment_parts(payload):
            filename = part.get("filename", "")
            if not filename.lower().endswith(extensions):
                continue
            att_id = part.get("body", {}).get("attachmentId")
            if not att_id:
                continue
            att = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=msg_id, id=att_id)
                .execute()
            )
            raw_bytes = base64.urlsafe_b64decode(att["data"].encode("utf-8"))
            target = download_dir / f"{msg_id}_{_sanitize_filename(filename)}"
            target.write_bytes(raw_bytes)
            saved_paths.append(target)

    return saved_paths

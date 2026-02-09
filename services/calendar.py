"""Google Calendar integration helpers.

Requires:
  pip install google-auth google-auth-oauthlib google-api-python-client

Place OAuth client secrets as `credentials.json` in the project root.
This module stores user tokens to `token.json` by default.
"""
from datetime import datetime, timedelta
import os
from typing import List, Dict, Optional

SCOPES = ["https://www.googleapis.com/auth/calendar.events.readonly"]


def _ensure_google_libs():
    try:
        from google.oauth2.credentials import Credentials  # noqa: F401
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
    except Exception as e:
        raise ImportError(
            "Google API client libraries required. Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        )


def get_credentials(client_secrets_file: str = "credentials.json", token_file: str = "token.json"):
    _ensure_google_libs()
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            if not os.path.exists(client_secrets_file):
                raise FileNotFoundError(
                    f"{client_secrets_file} not found. Create OAuth client in Google Cloud and download credentials.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
            # save token
            with open(token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

    return creds


def _build_service(creds):
    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=creds)
    return service


def list_upcoming_events(
    calendar_id: str = "primary",
    time_min: Optional[datetime] = None,
    time_max: Optional[datetime] = None,
    max_results: int = 10,
    client_secrets_file: str = "credentials.json",
    token_file: str = "token.json",
) -> List[Dict]:
    """Return upcoming events as simplified dicts.

    Performs OAuth local-server flow if needed.
    """
    creds = get_credentials(client_secrets_file=client_secrets_file, token_file=token_file)
    service = _build_service(creds)

    now = datetime.utcnow()
    if time_min is None:
        time_min = now
    if time_max is None:
        time_max = now + timedelta(days=7)

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min.isoformat() + "Z",
            timeMax=time_max.isoformat() + "Z",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    items = events_result.get("items", [])
    events = []
    for ev in items:
        start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
        events.append(
            {
                "id": ev.get("id"),
                "summary": ev.get("summary", "(no title)"),
                "start": start,
                "end": end,
                "raw": ev,
            }
        )

    return events


def sync_user_schedule(user_id: int, calendar_id: str = "primary") -> List[Dict]:
    """Fetch upcoming events and return them.

    This is a thin wrapper for MVP; in future, map events to `exercise_schedules`.
    """
    events = list_upcoming_events(calendar_id=calendar_id)
    # TODO: map events to DB schedule rows or analyze conflicts
    return events

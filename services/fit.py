"""Mock Fit service: sample sleep data generator and CSV parser.

Provides utilities to generate synthetic sleep records and parse uploaded CSVs.
CSV format: start,end (ISO 8601 or %Y-%m-%d %H:%M)
"""
from datetime import datetime, timedelta
from typing import List, Dict, IO
import csv


def generate_mock_sleep(days: int = 7, end_date: datetime = None) -> List[Dict]:
    """Generate mock sleep sessions ending on end_date (default today).

    Returns list of dicts: {"start": iso, "end": iso}
    """
    if end_date is None:
        end_date = datetime.now()

    sleeps = []
    for i in range(days):
        night = end_date - timedelta(days=i)
        # assume sleep from 23:30 to 07:00 next day with small jitter
        start = datetime(night.year, night.month, night.day, 23, 30) - timedelta(minutes=(i % 3) * 10)
        end = start + timedelta(hours=7, minutes=(i % 2) * 15)
        sleeps.append({"start": start.isoformat(), "end": end.isoformat()})

    return sleeps


def parse_sleep_csv(file: IO) -> List[Dict]:
    """Parse uploaded CSV file and return list of sleep dicts ({start, end}).

    Accepts header or no header. Tries several common datetime formats.
    """
    reader = csv.reader((line.decode('utf-8') if isinstance(line, bytes) else line) for line in file)
    rows = list(reader)

    # flatten if single column with semicolon
    parsed = []
    for r in rows:
        if not r:
            continue
        # possible headers
        if any(s.lower() in ("start", "end", "sleep_start") for s in r):
            continue

        if len(r) >= 2:
            s, e = r[0].strip(), r[1].strip()
        else:
            # try split by comma inside single cell
            parts = r[0].split(',')
            if len(parts) >= 2:
                s, e = parts[0].strip(), parts[1].strip()
            else:
                continue

        # normalize to ISO if possible
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                ds = datetime.strptime(s, fmt)
                de = datetime.strptime(e, fmt)
                parsed.append({"start": ds.isoformat(), "end": de.isoformat()})
                break
            except Exception:
                continue

    return parsed

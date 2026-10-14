"""Row-level validation and transformation rules from the case study."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

NOT_AVAILABLE = -99999          # sentinel required by the case study
EXPECTED_COLUMNS = ("id", "imsi", "imei", "cell", "lac", "event_type", "event_ts")

# Order matters: day-first is the company's documented convention
# (sample "16/1/2020 7:45:43"); month-first is the fallback for files such
# as "6/15/2020 7:45:43" where day-first is impossible.
TIMESTAMP_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
)

IMSI_MAX, IMEI_LEN = 9, 14


@dataclass
class Valid:
    transaction_id: int
    imsi: str
    imei: Optional[str]
    tac: str
    snr: str
    cell: int
    lac: int
    event_type: Optional[str]
    event_ts: str               # ISO format


@dataclass
class Rejected:
    column: str
    reason: str
    tac: Optional[str] = None
    snr: Optional[str] = None


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def split_imei(imei: Optional[str]) -> tuple[str, str]:
    """TAC = first 8 chars, SNR = last 6 chars; -99999 if null or shorter than 14."""
    if imei is None or len(imei) < IMEI_LEN:
        return str(NOT_AVAILABLE), str(NOT_AVAILABLE)
    return imei[:8], imei[-6:]


def _clean(v: Optional[str]) -> Optional[str]:
    v = (v or "").strip()
    return v or None


def _to_int(v: Optional[str]) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def transform_row(fields: list[str]) -> Valid | Rejected:
    """Validate one raw CSV row. Returns Valid, or Rejected with the first failing rule."""
    if len(fields) != len(EXPECTED_COLUMNS):
        return Rejected("ROW", f"Malformed record: expected {len(EXPECTED_COLUMNS)} "
                               f"fields, found {len(fields)}")
    id_, imsi, imei, cell, lac, etype, ets = (_clean(f) for f in fields)
    tac, snr = split_imei(imei)

    def rej(col, why):
        return Rejected(col, why, tac, snr)

    # Mandatory fields (IMSI, CELL, LAC, EVENT_TS are explicit case-study rules; ID is NOT NULL)
    if id_ is None:
        return rej("ID", "ID is null")
    if _to_int(id_) is None:
        return rej("ID", "ID is not an integer")
    if imsi is None:
        return rej("IMSI", "IMSI is null")
    if len(imsi) > IMSI_MAX:
        return rej("IMSI", f"IMSI longer than {IMSI_MAX} characters")
    if cell is None:
        return rej("CELL", "CELL is null")
    if _to_int(cell) is None:
        return rej("CELL", "CELL is not an integer")
    if lac is None:
        return rej("LAC", "LAC is null")
    if _to_int(lac) is None:
        return rej("LAC", "LAC is not an integer")
    if ets is None:
        return rej("EVENT_TS", "EVENT_TS is null")
    ts = parse_timestamp(ets)
    if ts is None:
        return rej("EVENT_TS", "EVENT_TS is not a valid datetime")
    # Schema-length constraints (source contract: IMEI <= 14, EVENT_TYPE = 1 char)
    if imei is not None and len(imei) > IMEI_LEN:
        return rej("IMEI", f"IMEI longer than {IMEI_LEN} characters")
    if etype is not None and len(etype) != 1:
        return rej("EVENT_TYPE", "EVENT_TYPE must be a single character")

    return Valid(int(id_), imsi, imei, tac, snr, int(cell), int(lac), etype,
                 ts.strftime("%Y-%m-%d %H:%M:%S"))

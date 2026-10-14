"""File discovery -> extract -> transform -> load -> archive."""
from __future__ import annotations

import csv
import hashlib
import logging
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .transform import EXPECTED_COLUMNS, NOT_AVAILABLE, Rejected, transform_row

log = logging.getLogger("telecom_etl")
SCHEMA = Path(__file__).with_name("schema.sql")
DELIMITER = "|"


@dataclass
class FileResult:
    file: str
    read: int = 0
    loaded: int = 0
    rejected: int = 0
    skipped: bool = False


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text())
    return conn


def seed_imsi_reference(conn: sqlite3.Connection, ref_csv: Path) -> int:
    """Load the IMSI -> subscriber_id lookup (only if the table is empty)."""
    if conn.execute("SELECT COUNT(*) FROM dim_imsi_reference").fetchone()[0]:
        return 0
    with ref_csv.open(newline="") as fh:
        rows = [(r["imsi"], int(r["subscriber_id"])) for r in csv.DictReader(fh)]
    conn.executemany("INSERT INTO dim_imsi_reference (imsi, subscriber_id) VALUES (?, ?)", rows)
    conn.commit()
    return len(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process_file(conn: sqlite3.Connection, path: Path) -> FileResult:
    result = FileResult(path.name)
    digest = _sha256(path)
    if conn.execute("SELECT 1 FROM etl_file_log WHERE file_name=? AND file_sha256=?",
                    (path.name, digest)).fetchone():
        result.skipped = True
        return result

    lookup = dict(conn.execute("SELECT imsi, subscriber_id FROM dim_imsi_reference"))
    facts, errors = [], []

    # newline="" lets the csv module handle \r, \n and \r\n line endings (sources use CR only)
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh, delimiter=DELIMITER)
        header = next(reader, None)
        if header is None or [h.strip().lower() for h in header] != list(EXPECTED_COLUMNS):
            raise ValueError(f"{path.name}: unexpected header {header!r}")
        for fields in reader:
            if not any(f.strip() for f in fields):      # blank line
                continue
            result.read += 1
            out = transform_row(fields)
            if isinstance(out, Rejected):
                padded = (fields + [None] * 7)[:7]
                errors.append((path.name, reader.line_num, *padded, out.tac, out.snr,
                               out.column, out.reason, DELIMITER.join(fields)))
            else:
                sub = lookup.get(out.imsi, NOT_AVAILABLE)
                facts.append((out.transaction_id, out.imsi, sub, out.tac, out.snr, out.imei,
                              out.cell, out.lac, out.event_type, out.event_ts, path.name))

    # Single transaction per file: either everything is committed or nothing is.
    with conn:
        conn.executemany(
            "INSERT INTO fact_transaction (transaction_id, imsi, subscriber_id, tac, snr, imei,"
            " cell, lac, event_type, event_ts, source_file) VALUES (?,?,?,?,?,?,?,?,?,?,?)", facts)
        conn.executemany(
            "INSERT INTO error_destination_output (source_file, line_number, id, imsi, imei, cell,"
            " lac, event_type, event_ts, tac, snr, error_column, error_reason, raw_record)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", errors)
        conn.execute("INSERT INTO etl_file_log (file_name, file_sha256, rows_read, rows_loaded,"
                     " rows_rejected) VALUES (?,?,?,?,?)",
                     (path.name, digest, result.read, len(facts), len(errors)))
    result.loaded, result.rejected = len(facts), len(errors)
    return result


def archive_file(path: Path, archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / path.name
    if dest.exists():                                   # never overwrite an earlier archive
        i = 1
        while (archive_dir / f"{path.stem}.{i}{path.suffix}").exists():
            i += 1
        dest = archive_dir / f"{path.stem}.{i}{path.suffix}"
    shutil.move(str(path), dest)
    return dest


def run(db_path: Path, incoming: Path, archive: Path, ref_csv: Path) -> list[FileResult]:
    conn = connect(db_path)
    try:
        n = seed_imsi_reference(conn, ref_csv)
        if n:
            log.info("Seeded dim_imsi_reference with %d rows", n)
        results = []
        for path in sorted(incoming.glob("*.csv")):
            try:
                r = process_file(conn, path)
            except Exception as exc:                    # leave the file in place for a retry
                log.error("FAILED %s: %s (file left in %s)", path.name, exc, incoming)
                continue
            if r.skipped:
                log.warning("Skipping %s: already loaded (archiving duplicate)", path.name)
            else:
                log.info("%s: read=%d loaded=%d rejected=%d", r.file, r.read, r.loaded, r.rejected)
            archive_file(path, archive)                 # only after a successful load
            results.append(r)
        return results
    finally:
        conn.close()

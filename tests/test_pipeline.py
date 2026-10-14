import sqlite3
from pathlib import Path

from telecom_etl.pipeline import run

HEADER = "id|imsi|imei|cell|lac|event_type|event_ts"


def make_env(tmp_path, lines, newline="\r"):
    inc, arc = tmp_path / "in", tmp_path / "arc"
    inc.mkdir()
    ref = tmp_path / "ref.csv"
    ref.write_text("imsi,subscriber_id\n111111111,500\n")
    (inc / "f1.csv").write_bytes(newline.join([HEADER, *lines]).encode())
    return tmp_path / "dw.db", inc, arc, ref


def q(db, sql):
    return sqlite3.connect(db).execute(sql).fetchall()


def test_end_to_end(tmp_path):
    db, inc, arc, ref = make_env(tmp_path, [
        "1|111111111|49015420323751|10|5|1|20/12/2020 01:25",   # known IMSI
        "2|222222222||10|5||20/12/2020 01:25",                  # unknown IMSI, null IMEI
        "3||49015420323751|10|5|1|20/12/2020 01:25",            # rejected: IMSI null
        "4|111111111|49015420323751|10|5|1|garbage",            # rejected: bad ts
    ])
    results = run(db, inc, arc, ref)
    assert (results[0].read, results[0].loaded, results[0].rejected) == (4, 2, 2)
    assert q(db, "SELECT transaction_id, subscriber_id, tac, snr FROM fact_transaction ORDER BY 1") == [
        (1, 500, "49015420", "323751"), (2, -99999, "-99999", "-99999")]
    errs = q(db, "SELECT source_file, id, error_column FROM error_destination_output ORDER BY id")
    assert errs == [("f1.csv", "3", "IMSI"), ("f1.csv", "4", "EVENT_TS")]
    # processed file moved to archive
    assert not (inc / "f1.csv").exists() and (arc / "f1.csv").exists()


def test_same_file_is_not_loaded_twice(tmp_path):
    db, inc, arc, ref = make_env(tmp_path, ["1|111111111|49015420323751|10|5|1|20/12/2020 01:25"])
    run(db, inc, arc, ref)
    (inc / "f1.csv").write_bytes((arc / "f1.csv").read_bytes())   # re-delivered, identical
    results = run(db, inc, arc, ref)
    assert results[0].skipped
    assert q(db, "SELECT COUNT(*) FROM fact_transaction") == [(1,)]
    assert len(list(arc.glob("f1*.csv"))) == 2                    # duplicate archived, not overwritten


def test_bad_header_leaves_file_in_place(tmp_path):
    db, inc, arc, ref = make_env(tmp_path, [])
    (inc / "f1.csv").write_text("a|b|c\n1|2|3")
    assert run(db, inc, arc, ref) == []
    assert (inc / "f1.csv").exists()

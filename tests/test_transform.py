import pytest
from telecom_etl.transform import Rejected, Valid, parse_timestamp, split_imei, transform_row


def row(id_="1", imsi="310120265", imei="49015420323751", cell="123", lac="12",
        et="1", ts="16/1/2020 7:45:43"):
    return [id_, imsi, imei, cell, lac, et, ts]


def test_valid_row_splits_imei_and_parses_ts():
    r = transform_row(row())
    assert isinstance(r, Valid)
    assert (r.tac, r.snr, r.imei) == ("49015420", "323751", "49015420323751")
    assert r.event_ts == "2020-01-16 07:45:43"


@pytest.mark.parametrize("imei", [None, "", "1234567890123"])
def test_short_or_null_imei_gives_sentinel(imei):
    assert split_imei(imei) == ("-99999", "-99999")


def test_null_imei_is_still_loaded():
    r = transform_row(row(imei=""))
    assert isinstance(r, Valid) and r.imei is None and r.tac == "-99999"


@pytest.mark.parametrize("kwargs,col", [
    ({"imsi": ""}, "IMSI"), ({"cell": ""}, "CELL"), ({"lac": ""}, "LAC"),
    ({"ts": ""}, "EVENT_TS"), ({"ts": "31/02/2020 10:00"}, "EVENT_TS"),
    ({"ts": "not a date"}, "EVENT_TS"), ({"id_": "1@"}, "ID"),
    ({"cell": "abc"}, "CELL"), ({"imsi": "310120265624299"}, "IMSI"),
    ({"imei": "490154203237518"}, "IMEI"), ({"et": "12"}, "EVENT_TYPE"),
])
def test_rejections(kwargs, col):
    r = transform_row(row(**kwargs))
    assert isinstance(r, Rejected) and r.column == col


def test_malformed_row_rejected():
    r = transform_row(["9112", "349932947"])
    assert isinstance(r, Rejected) and r.column == "ROW"


def test_null_event_type_allowed():
    assert isinstance(transform_row(row(et="")), Valid)


@pytest.mark.parametrize("text,iso", [
    ("20/12/2020 01:25", "2020-12-20 01:25:00"),       # dd/MM/yyyy HH:mm
    ("16/1/2020 7:45:43", "2020-01-16 07:45:43"),      # case-study sample
    ("6/15/2020 7:45:43", "2020-06-15 07:45:43"),      # month-first fallback
])
def test_timestamp_formats(text, iso):
    assert parse_timestamp(text).strftime("%Y-%m-%d %H:%M:%S") == iso

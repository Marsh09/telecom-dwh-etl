"""Command line entry point:  python -m telecom_etl [--watch 300]"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from .pipeline import run

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser(prog="telecom_etl", description=__doc__)
    ap.add_argument("--incoming", type=Path, default=ROOT / "data/incoming")
    ap.add_argument("--archive", type=Path, default=ROOT / "data/archive")
    ap.add_argument("--db", type=Path, default=ROOT / "warehouse/telecom_dwh.db")
    ap.add_argument("--reference", type=Path, default=ROOT / "data/reference/dim_imsi_reference.csv")
    ap.add_argument("--watch", type=int, metavar="SECONDS", default=0,
                    help="keep running and poll the incoming folder (source drops a file every 5 min = 300)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    while True:
        results = run(args.db, args.incoming, args.archive, args.reference)
        done = [r for r in results if not r.skipped]
        logging.info("Run complete: %d file(s), loaded=%d rejected=%d", len(done),
                     sum(r.loaded for r in done), sum(r.rejected for r in done))
        if not args.watch:
            break
        time.sleep(args.watch)


if __name__ == "__main__":
    main()

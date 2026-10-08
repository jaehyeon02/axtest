"""종목 마스터(data/companies.csv) -> markets / sectors / companies 적재.

실행: cd backend && python -m scripts.load_master
CSV 를 고치고 다시 실행해도 된다 (같은 종목코드는 덮어쓴다).
"""
import csv
import logging
from pathlib import Path

from sqlalchemy import text

from app.db import SessionLocal

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "companies.csv"
log = logging.getLogger("load_master")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    count = 0
    with SessionLocal() as db, open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code, name = row["code"].strip(), row["name"].strip()
            market, sector = row["market"].strip(), row["sector"].strip()

            market_id = db.execute(
                text("SELECT market_id FROM markets WHERE name = :n"), {"n": market}
            ).scalar_one_or_none()
            if market_id is None:
                raise SystemExit(f"[{code}] markets 테이블에 없는 시장입니다: {market}")

            db.execute(text("INSERT INTO sectors (name) VALUES (:n) ON CONFLICT (name) DO NOTHING"), {"n": sector})
            sector_id = db.execute(text("SELECT sector_id FROM sectors WHERE name = :n"), {"n": sector}).scalar_one()

            db.execute(
                text(
                    """
                    INSERT INTO companies (code, name, market_id, sector_id)
                    VALUES (:code, :name, :market_id, :sector_id)
                    ON CONFLICT (code) DO UPDATE
                    SET name = EXCLUDED.name, market_id = EXCLUDED.market_id, sector_id = EXCLUDED.sector_id
                    """
                ),
                {"code": code, "name": name, "market_id": market_id, "sector_id": sector_id},
            )
            count += 1
        db.commit()
    log.info("종목 %d건 적재 완료 (%s)", count, CSV_PATH.name)


if __name__ == "__main__":
    main()

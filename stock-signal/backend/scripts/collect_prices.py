"""일별 시세 수집 -> Pandas 전처리 -> daily_prices 적재.

실행:
  cd backend
  python -m scripts.collect_prices --start 2024-01-01                # FinanceDataReader 로 수집
  python -m scripts.collect_prices --csv-dir data/prices             # 수집이 막힐 때: CSV 로 적재
  python -m scripts.collect_prices --codes 005930 000660 --start 2025-01-01

CSV 형식(--csv-dir): data/prices/005930.csv  (컬럼: Date,Open,High,Low,Close,Volume)
같은 (종목, 날짜)는 덮어쓰므로 여러 번 실행해도 중복되지 않는다.
"""
import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.db import SessionLocal

log = logging.getLogger("collect_prices")
COLS = ["Open", "High", "Low", "Close", "Volume"]

UPSERT = text(
    """
    INSERT INTO daily_prices (company_id, trade_date, open_price, high_price, low_price, close_price, volume)
    VALUES (:company_id, :trade_date, :open, :high, :low, :close, :volume)
    ON CONFLICT (company_id, trade_date) DO UPDATE
    SET open_price = EXCLUDED.open_price, high_price = EXCLUDED.high_price,
        low_price = EXCLUDED.low_price, close_price = EXCLUDED.close_price,
        volume = EXCLUDED.volume
    """
)


def fetch_fdr(code: str, start: str) -> pd.DataFrame:
    import FinanceDataReader as fdr  # 설치/네트워크 문제 시 CSV 방식을 쓸 수 있도록 지연 import

    return fdr.DataReader(code, start)


def fetch_csv(code: str, csv_dir: Path) -> pd.DataFrame | None:
    path = csv_dir / f"{code}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, parse_dates=["Date"], index_col="Date")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """전처리: 필요한 컬럼만 -> 결측 제거 -> 거래정지일 제거 -> 이상값 제거 -> 정수 변환 -> 중복 제거"""
    df = df[COLS].dropna()
    df = df[df["Volume"] > 0]  # 거래량 0 = 거래정지/휴장 (시세로 보지 않는다)
    df = df[(df[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    df = df[df["High"] >= df["Low"]]
    df = df.round().astype("int64")
    return df[~df.index.duplicated(keep="last")].sort_index()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--codes", nargs="*", help="비우면 companies 전체")
    ap.add_argument("--csv-dir", type=Path, help="FinanceDataReader 대신 CSV 폴더에서 읽기")
    args = ap.parse_args()

    with SessionLocal() as db:
        companies = db.execute(text("SELECT company_id, code, name FROM companies ORDER BY code")).all()
        if not companies:
            raise SystemExit("companies 가 비어 있습니다. 먼저 `python -m scripts.load_master` 를 실행하세요.")

        for company_id, code, name in companies:
            if args.codes and code not in args.codes:
                continue
            try:
                raw = fetch_csv(code, args.csv_dir) if args.csv_dir else fetch_fdr(code, args.start)
            except Exception as exc:  # 네트워크/소스 오류는 종목 단위로 건너뛴다
                log.warning("[skip] %s %s: 수집 실패 (%s)", code, name, exc)
                continue
            if raw is None or raw.empty:
                log.warning("[skip] %s %s: 데이터 없음", code, name)
                continue

            df = clean(raw)
            rows = [
                {
                    "company_id": company_id,
                    "trade_date": idx.date(),
                    "open": int(r["Open"]),
                    "high": int(r["High"]),
                    "low": int(r["Low"]),
                    "close": int(r["Close"]),
                    "volume": int(r["Volume"]),
                }
                for idx, r in df.iterrows()
            ]
            if rows:
                db.execute(UPSERT, rows)
                db.commit()
            log.info("[ok] %s %s: 원본 %d행 -> 적재 %d행", code, name, len(raw), len(rows))


if __name__ == "__main__":
    main()

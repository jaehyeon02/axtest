"""OpenDART 사업보고서 주요계정 -> financial_statements 적재.

실행: cd backend && python -m scripts.collect_dart --years 2022 2023 2024
필요: backend/.env 의 DART_API_KEY  (https://opendart.fss.or.kr 에서 무료 발급, 일일 호출 한도 있음)
연결재무제표(CFS)가 있으면 그것을, 없으면 개별재무제표(OFS)를 사용한다. 단위: 원.
"""
import argparse
import io
import logging
import time
import xml.etree.ElementTree as ET
import zipfile

import requests
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal

BASE = "https://opendart.fss.or.kr/api"
log = logging.getLogger("collect_dart")

ACCOUNT_TO_COLUMN = {
    "매출액": "revenue",
    "영업이익": "operating_profit",
    "당기순이익": "net_income",
    "자산총계": "total_assets",
    "부채총계": "total_liabilities",
    "자본총계": "total_equity",
}

UPSERT = text(
    """
    INSERT INTO financial_statements
        (company_id, fiscal_year, revenue, operating_profit, net_income,
         total_assets, total_liabilities, total_equity)
    VALUES
        (:company_id, :fiscal_year, :revenue, :operating_profit, :net_income,
         :total_assets, :total_liabilities, :total_equity)
    ON CONFLICT (company_id, fiscal_year) DO UPDATE
    SET revenue = EXCLUDED.revenue, operating_profit = EXCLUDED.operating_profit,
        net_income = EXCLUDED.net_income, total_assets = EXCLUDED.total_assets,
        total_liabilities = EXCLUDED.total_liabilities, total_equity = EXCLUDED.total_equity
    """
)


def load_corp_codes() -> dict[str, str]:
    """종목코드(6자리) -> DART 고유번호(corp_code)"""
    res = requests.get(f"{BASE}/corpCode.xml", params={"crtfc_key": settings.dart_api_key}, timeout=60)
    res.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        root = ET.fromstring(z.read(z.namelist()[0]))
    mapping = {}
    for item in root.iter("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        if stock_code:
            mapping[stock_code] = item.findtext("corp_code")
    return mapping


def to_int(value: str | None) -> int | None:
    value = (value or "").replace(",", "").strip()
    try:
        return int(value)
    except ValueError:
        return None


def extract(items: list[dict]) -> dict[str, int | None]:
    for fs_div in ("CFS", "OFS"):  # 연결 우선
        picked = [i for i in items if i.get("fs_div") == fs_div and i.get("account_nm") in ACCOUNT_TO_COLUMN]
        if picked:
            result = {col: None for col in ACCOUNT_TO_COLUMN.values()}
            for i in picked:
                result[ACCOUNT_TO_COLUMN[i["account_nm"]]] = to_int(i.get("thstrm_amount"))
            return result
    return {}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024])
    args = ap.parse_args()

    if not settings.dart_api_key:
        raise SystemExit("DART_API_KEY 가 backend/.env 에 없습니다.")

    corp_codes = load_corp_codes()
    with SessionLocal() as db:
        companies = db.execute(text("SELECT company_id, code, name FROM companies ORDER BY code")).all()
        if not companies:
            raise SystemExit("companies 가 비어 있습니다. 먼저 `python -m scripts.load_master` 를 실행하세요.")

        for company_id, code, name in companies:
            corp = corp_codes.get(code)
            if not corp:
                log.warning("[skip] %s %s: DART corp_code 없음", code, name)
                continue
            for year in args.years:
                res = requests.get(
                    f"{BASE}/fnlttSinglAcnt.json",
                    params={
                        "crtfc_key": settings.dart_api_key,
                        "corp_code": corp,
                        "bsns_year": str(year),
                        "reprt_code": "11011",  # 사업보고서
                    },
                    timeout=30,
                ).json()
                status = res.get("status")
                if status == "020":
                    raise SystemExit("DART 일일 호출 한도를 초과했습니다. 내일 다시 실행하세요.")
                if status != "000":
                    log.warning("[skip] %s %d: %s %s", name, year, status, res.get("message"))
                    continue

                values = extract(res.get("list", []))
                if not values:
                    log.warning("[skip] %s %d: 필요한 계정이 없습니다", name, year)
                    continue
                db.execute(UPSERT, {"company_id": company_id, "fiscal_year": year, **values})
                db.commit()
                log.info("[ok] %s %d", name, year)
                time.sleep(0.2)


if __name__ == "__main__":
    main()

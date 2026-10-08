"""수집 결과를 DB에 넣는 SQL. 모두 UPSERT(같은 키가 있으면 갱신/무시)라서 여러 번 실행해도 행이 늘어나지 않아요.
SQLite(3.24+)와 PostgreSQL 이 모두 이해하는 `INSERT ... ON CONFLICT` 문법만 써요."""
from datetime import datetime

UPSERT_SECTOR = "INSERT INTO sector(name) VALUES (:name) ON CONFLICT(name) DO NOTHING"

UPSERT_COMPANY = """
INSERT INTO company(code, name, market, sector_id, corp_code)
VALUES (:code, :name, :market, (SELECT sector_id FROM sector WHERE name = :sector), :corp_code)
ON CONFLICT(code) DO UPDATE SET name = excluded.name, market = excluded.market, sector_id = excluded.sector_id,
    corp_code = COALESCE(excluded.corp_code, company.corp_code)
"""

UPSERT_PRICE = """
INSERT INTO price_daily(company_id, trade_date, open, high, low, close, volume)
VALUES (:cid, :d, :o, :h, :l, :c, :v)
ON CONFLICT(company_id, trade_date) DO UPDATE SET open = excluded.open, high = excluded.high, low = excluded.low,
    close = excluded.close, volume = excluded.volume
"""

INSERT_FILING = """
INSERT INTO document(company_id, doc_type, title, body, source, sentiment, published_date, rcept_no, url, created_by)
VALUES (:cid, 'filing', :title, :body, 'OpenDART', 'neu', :d, :rcept, :url, NULL)
ON CONFLICT(rcept_no) DO NOTHING
"""

UPSERT_FINANCIAL = """
INSERT INTO financial_year(company_id, fiscal_year, revenue, operating_profit, net_income)
VALUES (:cid, :fy, :revenue, :operating_profit, :net_income)
ON CONFLICT(company_id, fiscal_year) DO UPDATE SET revenue = excluded.revenue,
    operating_profit = excluded.operating_profit, net_income = excluded.net_income
"""

INSERT_LOG = """
INSERT INTO ingestion_log(job, source, status, row_count, message, finished_at)
VALUES (:job, :source, :status, :n, :msg, :at)
"""

COUNT_TABLE = {"price_daily": "SELECT COUNT(*) AS n FROM price_daily", "document": "SELECT COUNT(*) AS n FROM document WHERE doc_type = 'filing'",
               "financial_year": "SELECT COUNT(*) AS n FROM financial_year"}
HAS_SAMPLE = "SELECT COUNT(*) AS n FROM ingestion_log WHERE source = 'sample'"
SELECT_COMPANIES = "SELECT company_id, code, name, corp_code FROM company ORDER BY company_id"
LAST_PRICE = "SELECT MAX(trade_date) AS d FROM price_daily WHERE company_id = :cid"


def log(write, job: str, source: str, status: str, n: int, msg: str = ""):
    write(INSERT_LOG, {"job": job, "source": source, "status": status, "n": n, "msg": msg[:300], "at": datetime.now().isoformat(sep=" ")})

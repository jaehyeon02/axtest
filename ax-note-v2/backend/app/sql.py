"""분석에 쓰는 SQL 모음. SQLite 와 PostgreSQL 모두에서 돌아가도록 표준 문법(윈도 함수, 서브쿼리)만 썼어요.
파라미터는 :이름 형태이고, SQLAlchemy text() 와 sqlite3 둘 다 같은 문장을 그대로 실행해요."""

COMPANIES = """
SELECT c.company_id, c.code, c.name, c.market, s.name AS sector
FROM company c JOIN sector s ON s.sector_id = c.sector_id
WHERE c.name LIKE :like OR c.code LIKE :like
ORDER BY c.company_id
"""

COMPANY_BY_CODE = """
SELECT c.company_id, c.code, c.name, c.market, s.name AS sector
FROM company c JOIN sector s ON s.sector_id = c.sector_id
WHERE c.code = :code
"""

# 회사마다 가장 최근 종가와 전일 종가
LATEST_ALL = """
SELECT p.company_id, p.trade_date, p.close, p.volume,
       (SELECT p2.close FROM price_daily p2
         WHERE p2.company_id = p.company_id AND p2.trade_date < p.trade_date
         ORDER BY p2.trade_date DESC LIMIT 1) AS prev_close
FROM price_daily p
WHERE p.trade_date = (SELECT MAX(trade_date) FROM price_daily WHERE company_id = p.company_id)
"""

SERIES = """
SELECT price_id, trade_date, open, high, low, close, volume
FROM price_daily
WHERE company_id = :cid AND trade_date >= :since
ORDER BY trade_date
"""

# 전일 대비 등락률이 기준(%) 이상인 날: LAG 윈도 함수로 전일 종가를 옆에 붙여서 계산
MOVERS = """
SELECT price_id, trade_date, close, prev_close, ret_pct, volume FROM (
    SELECT price_id, trade_date, close, volume,
           LAG(close) OVER (PARTITION BY company_id ORDER BY trade_date) AS prev_close,
           (close - LAG(close) OVER (PARTITION BY company_id ORDER BY trade_date)) * 100.0
               / LAG(close) OVER (PARTITION BY company_id ORDER BY trade_date) AS ret_pct
    FROM price_daily
    WHERE company_id = :cid
) t
WHERE trade_date >= :since AND ABS(ret_pct) >= :th
ORDER BY trade_date
"""

MONTHLY = """
SELECT substr(CAST(trade_date AS TEXT), 1, 7) AS ym,
       ROUND(AVG(close), 0) AS avg_close, MIN(low) AS low, MAX(high) AS high, SUM(volume) AS volume
FROM price_daily
WHERE company_id = :cid
GROUP BY substr(CAST(trade_date AS TEXT), 1, 7)
ORDER BY ym
"""

# 연간 재무 + 영업이익률 + 전년 대비 매출 성장률(LAG 윈도 함수). LIMIT 은 윈도 계산 뒤에 적용돼요.
FINANCIALS = """
SELECT fin_id, fiscal_year, revenue, operating_profit, net_income,
       ROUND(operating_profit * 100.0 / revenue, 1) AS op_margin,
       ROUND((revenue - LAG(revenue) OVER (ORDER BY fiscal_year)) * 100.0 / LAG(revenue) OVER (ORDER BY fiscal_year), 1) AS rev_growth
FROM financial_year
WHERE company_id = :cid
ORDER BY fiscal_year DESC
LIMIT :n
"""

# 같은 업종 회사들의 최신 연도 영업이익률·매출 성장률과 업종 안 순위(RANK)·평균(AVG OVER)
PEERS = """
WITH latest AS (
    SELECT company_id, MAX(fiscal_year) AS fy FROM financial_year GROUP BY company_id
), cur AS (
    SELECT c.company_id, c.code, c.name, f.fiscal_year, f.revenue, f.operating_profit,
           f.operating_profit * 100.0 / f.revenue AS op_margin,
           (f.revenue - p.revenue) * 100.0 / p.revenue AS rev_growth
    FROM company c
    JOIN latest l ON l.company_id = c.company_id
    JOIN financial_year f ON f.company_id = c.company_id AND f.fiscal_year = l.fy
    LEFT JOIN financial_year p ON p.company_id = c.company_id AND p.fiscal_year = l.fy - 1
    WHERE c.sector_id = (SELECT sector_id FROM company WHERE company_id = :cid)
)
SELECT company_id, code, name, fiscal_year, revenue, operating_profit,
       ROUND(op_margin, 1) AS op_margin, ROUND(rev_growth, 1) AS rev_growth,
       RANK() OVER (ORDER BY op_margin DESC) AS margin_rank,
       RANK() OVER (ORDER BY COALESCE(rev_growth, -1000000) DESC) AS growth_rank,
       COUNT(*) OVER () AS n,
       ROUND(AVG(op_margin) OVER (), 1) AS avg_margin,
       ROUND(AVG(rev_growth) OVER (), 1) AS avg_growth
FROM cur
ORDER BY margin_rank, company_id
"""

# 수치 분석 ①: 최근 거래일 한 줄에 기간별 과거 종가·120일 이동평균을 윈도 함수로 붙여서 가져와요.
ANALYSIS_LAST = """
SELECT * FROM (
    SELECT trade_date, close,
           LAG(close, 21)  OVER (ORDER BY trade_date) AS c21,
           LAG(close, 63)  OVER (ORDER BY trade_date) AS c63,
           LAG(close, 126) OVER (ORDER BY trade_date) AS c126,
           AVG(close) OVER (ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS ma120,
           COUNT(*)   OVER (ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS n120
    FROM price_daily
    WHERE company_id = :cid
) t
ORDER BY trade_date DESC
LIMIT 1
"""

# 수치 분석 ②: 최대 낙폭(MDD) = 지금까지의 최고가 대비 가장 크게 내려간 비율(%)
ANALYSIS_MDD = """
SELECT MIN((close - peak) * 100.0 / peak) AS mdd FROM (
    SELECT close, MAX(close) OVER (ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak
    FROM price_daily
    WHERE company_id = :cid AND trade_date >= :since
) t
"""

# 수치 분석 ③: 일별 등락률(변동성은 이 값들의 표준편차로 계산)
DAILY_RETURNS = """
SELECT trade_date, ret_pct FROM (
    SELECT trade_date,
           (close - LAG(close) OVER (ORDER BY trade_date)) * 100.0 / LAG(close) OVER (ORDER BY trade_date) AS ret_pct
    FROM price_daily
    WHERE company_id = :cid
) t
WHERE ret_pct IS NOT NULL AND trade_date >= :since
ORDER BY trade_date
"""

DOCUMENTS = """
SELECT doc_id, company_id, doc_type, title, body, source, sentiment, published_date, rcept_no, url, created_by
FROM document
WHERE company_id = :cid AND published_date >= :since
  AND (created_by IS NULL OR created_by = :client)   -- 수집 문서 + 내가 직접 추가한 문서만
ORDER BY published_date DESC, doc_id DESC
"""

DOCUMENT_BY_ID = """
SELECT doc_id, company_id, doc_type, title, body, source, sentiment, published_date, rcept_no, url, created_by
FROM document WHERE doc_id = :doc_id
"""

PRICE_BY_ID = """
SELECT price_id, company_id, trade_date, close FROM price_daily WHERE price_id = :price_id
"""

LATEST_DATE = """
SELECT MAX(trade_date) AS d FROM price_daily WHERE company_id = :cid
"""

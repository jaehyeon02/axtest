"""통계 API 가 사용하는 SQL. (sql/02_queries.sql 과 같은 내용 - 값만 파라미터로 바뀜)

SQL 을 ORM 대신 직접 보여 주는 이유: JOIN / GROUP BY / HAVING 을 눈으로 확인하기 위해서.
값은 항상 :param 으로 바인딩한다 (문자열 이어붙이기 금지 → SQL Injection 방지).
"""

SUMMARY = """
SELECT c.code, c.name,
       COUNT(*)                  AS trading_days,
       MIN(p.trade_date)         AS first_date,
       MAX(p.trade_date)         AS last_date,
       ROUND(AVG(p.close_price)) AS avg_close,
       MAX(p.close_price)        AS max_close,
       MIN(p.close_price)        AS min_close,
       ROUND(AVG(p.volume))      AS avg_volume
FROM daily_prices p
JOIN companies c ON c.company_id = p.company_id
WHERE c.code = :code
  AND (CAST(:start AS date) IS NULL OR p.trade_date >= CAST(:start AS date))
  AND (CAST(:end   AS date) IS NULL OR p.trade_date <= CAST(:end   AS date))
GROUP BY c.code, c.name
"""

MONTHLY = """
SELECT to_char(p.trade_date, 'YYYY-MM') AS month,
       COUNT(*)                  AS trading_days,
       ROUND(AVG(p.close_price)) AS avg_close,
       MAX(p.high_price)         AS high,
       MIN(p.low_price)          AS low,
       SUM(p.volume)             AS total_volume
FROM daily_prices p
JOIN companies c ON c.company_id = p.company_id
WHERE c.code = :code
  AND (CAST(:year AS int) IS NULL OR EXTRACT(YEAR FROM p.trade_date) = CAST(:year AS int))
GROUP BY to_char(p.trade_date, 'YYYY-MM')
ORDER BY month
"""

SECTORS = """
SELECT s.name AS sector,
       COUNT(DISTINCT c.company_id) AS companies,
       ROUND(AVG(v.change_pct), 2)  AS avg_change_pct,
       ROUND(AVG(v.volume))         AS avg_volume
FROM v_price_change v
JOIN companies c ON c.company_id = v.company_id
JOIN sectors   s ON s.sector_id  = c.sector_id
WHERE v.trade_date > (SELECT MAX(trade_date) FROM daily_prices) - :days
GROUP BY s.name
ORDER BY avg_change_pct DESC
"""

# {order_col}, {direction} 은 코드에서 허용 목록(whitelist)으로만 채운다. 사용자 입력을 직접 넣지 않는다.
RANKING = """
SELECT c.code, c.name, v.trade_date, v.close_price, v.change_pct, v.volume
FROM v_price_change v
JOIN companies c ON c.company_id = v.company_id
WHERE v.trade_date = COALESCE(CAST(:day AS date), (SELECT MAX(trade_date) FROM daily_prices))
  AND (CAST(:metric AS text) = 'volume' OR v.change_pct IS NOT NULL)
ORDER BY {order_col} {direction} NULLS LAST
LIMIT :limit
"""

VOLATILE = """
SELECT c.code, c.name,
       COUNT(*)                         AS move_days,
       ROUND(MAX(ABS(v.change_pct)), 2) AS max_abs_change
FROM v_price_change v
JOIN companies c ON c.company_id = v.company_id
WHERE ABS(v.change_pct) >= :threshold
  AND v.trade_date > (SELECT MAX(trade_date) FROM daily_prices) - :days
GROUP BY c.code, c.name
HAVING COUNT(*) >= :min_days
ORDER BY move_days DESC, max_abs_change DESC
"""

FINANCIAL_RATIOS = """
SELECT c.code, c.name, f.fiscal_year,
       f.revenue, f.operating_profit, f.net_income,
       ROUND(f.operating_profit  * 100.0 / NULLIF(f.revenue, 0), 2)      AS operating_margin_pct,
       ROUND(f.total_liabilities * 100.0 / NULLIF(f.total_equity, 0), 2) AS debt_ratio_pct,
       ROUND(f.net_income        * 100.0 / NULLIF(f.total_equity, 0), 2) AS roe_pct
FROM financial_statements f
JOIN companies c ON c.company_id = f.company_id
WHERE (CAST(:code AS varchar) IS NULL OR c.code = CAST(:code AS varchar))
ORDER BY c.code, f.fiscal_year
"""

-- ============================================================
-- 주요 SQL 모음 (psql / DBeaver 에서 직접 실행해 보세요)
-- API(app/queries.py)가 사용하는 쿼리와 같은 내용입니다. 값은 예시입니다.
-- ============================================================

-- 1) 종목 요약: COUNT / MIN / MAX / AVG, JOIN, GROUP BY
SELECT c.code, c.name,
       COUNT(*)                 AS trading_days,
       MIN(p.trade_date)        AS first_date,
       MAX(p.trade_date)        AS last_date,
       ROUND(AVG(p.close_price)) AS avg_close,
       MAX(p.close_price)       AS max_close,
       MIN(p.close_price)       AS min_close,
       ROUND(AVG(p.volume))     AS avg_volume
FROM daily_prices p
JOIN companies c ON c.company_id = p.company_id
WHERE c.code = '005930'
GROUP BY c.code, c.name;

-- 2) 월별 통계: GROUP BY 날짜 가공, SUM
SELECT to_char(p.trade_date, 'YYYY-MM') AS month,
       COUNT(*)              AS trading_days,
       ROUND(AVG(p.close_price)) AS avg_close,
       MAX(p.high_price)     AS high,
       MIN(p.low_price)      AS low,
       SUM(p.volume)         AS total_volume
FROM daily_prices p
JOIN companies c ON c.company_id = p.company_id
WHERE c.code = '005930'
GROUP BY to_char(p.trade_date, 'YYYY-MM')
ORDER BY month;

-- 3) 업종별 평균 등락률 (최근 30일): 3테이블 JOIN, 서브쿼리
SELECT s.name AS sector,
       COUNT(DISTINCT c.company_id) AS companies,
       ROUND(AVG(v.change_pct), 2)  AS avg_change_pct,
       ROUND(AVG(v.volume))         AS avg_volume
FROM v_price_change v
JOIN companies c ON c.company_id = v.company_id
JOIN sectors   s ON s.sector_id  = c.sector_id
WHERE v.trade_date > (SELECT MAX(trade_date) FROM daily_prices) - 30
GROUP BY s.name
ORDER BY avg_change_pct DESC;

-- 4) 최근 거래일 등락률 TOP 5: ORDER BY, LIMIT
SELECT c.code, c.name, v.trade_date, v.close_price, v.change_pct, v.volume
FROM v_price_change v
JOIN companies c ON c.company_id = v.company_id
WHERE v.trade_date = (SELECT MAX(trade_date) FROM daily_prices)
  AND v.change_pct IS NOT NULL
ORDER BY v.change_pct DESC
LIMIT 5;

-- 5) 변동성 큰 종목 (최근 180일 중 ±4% 이상 움직인 날이 3일 이상): WHERE + GROUP BY + HAVING
SELECT c.code, c.name,
       COUNT(*)                          AS move_days,
       ROUND(MAX(ABS(v.change_pct)), 2)  AS max_abs_change
FROM v_price_change v
JOIN companies c ON c.company_id = v.company_id
WHERE ABS(v.change_pct) >= 4
  AND v.trade_date > (SELECT MAX(trade_date) FROM daily_prices) - 180
GROUP BY c.code, c.name
HAVING COUNT(*) >= 3
ORDER BY move_days DESC;

-- 6) 재무 비율: 계산식 + NULLIF 로 0 나누기 방지
SELECT c.code, c.name, f.fiscal_year,
       f.revenue, f.operating_profit, f.net_income,
       ROUND(f.operating_profit * 100.0 / NULLIF(f.revenue, 0), 2)      AS operating_margin_pct,
       ROUND(f.total_liabilities * 100.0 / NULLIF(f.total_equity, 0), 2) AS debt_ratio_pct,
       ROUND(f.net_income * 100.0 / NULLIF(f.total_equity, 0), 2)        AS roe_pct
FROM financial_statements f
JOIN companies c ON c.company_id = f.company_id
ORDER BY c.code, f.fiscal_year;

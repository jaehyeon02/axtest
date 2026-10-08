-- ============================================================
-- 주요 SQL 모음 (psql / DBeaver 에서 직접 실행해 보세요)
-- API(app/queries.py)가 사용하는 쿼리와 같은 내용입니다. 값은 예시입니다.
-- 지표는 01_schema.sql 의 뷰(v_price_change, v_indicators, v_latest_signal)가 계산합니다.
-- ============================================================

-- 1) 신호등 목록: 4테이블 JOIN, 불리언 → 정수 합산
SELECT c.code, c.name, s.name AS sector, v.close_price, v.change_pct,
       v.sig_trend, v.sig_volume, v.sig_position, v.sig_momentum,
       (v.sig_trend='good')::int + (v.sig_volume='good')::int
         + (v.sig_position='good')::int + (v.sig_momentum='good')::int AS good_cnt
FROM companies c
LEFT JOIN sectors s ON s.sector_id = c.sector_id
LEFT JOIN v_latest_signal v ON v.company_id = c.company_id
ORDER BY good_cnt DESC NULLS LAST, c.code;

-- 2) 차트용 시계열: 서브쿼리로 최근 N행 → 이동평균 포함 (윈도우 함수 뷰)
SELECT t.trade_date, t.close_price, t.ma5, t.ma20, t.ma60
FROM (SELECT i.* FROM v_indicators i JOIN companies c USING (company_id)
      WHERE c.code = '005930' ORDER BY i.trade_date DESC LIMIT 120) t
ORDER BY t.trade_date;

-- 3) 1개월 수익률 TOP 5: ORDER BY + LIMIT
SELECT c.code, c.name, v.ret_1m
FROM v_latest_signal v JOIN companies c USING (company_id)
WHERE v.ret_1m IS NOT NULL
ORDER BY v.ret_1m DESC LIMIT 5;

-- 4) 업종 요약: GROUP BY + HAVING + FILTER
SELECT s.name AS sector, COUNT(*) AS companies, ROUND(AVG(v.ret_1m),2) AS avg_ret_1m,
       COUNT(*) FILTER (WHERE v.sig_trend='good') AS good_trend_cnt
FROM v_latest_signal v
JOIN companies c USING (company_id) JOIN sectors s USING (sector_id)
GROUP BY s.name HAVING COUNT(*) >= 1
ORDER BY avg_ret_1m DESC NULLS LAST;

-- 5) 종목 비교: ANY(배열)
SELECT c.code, c.name, v.ret_1m, v.ret_3m, v.pos_52w, v.sig_trend
FROM companies c LEFT JOIN v_latest_signal v USING (company_id)
WHERE c.code = ANY('{005930,000660}'::varchar[]) ORDER BY c.code;

-- 6) 관심종목 + 최신 신호등 (회원 1)
SELECT w.watch_id, c.code, c.name, v.close_price, v.change_pct, v.sig_trend
FROM watchlist w JOIN companies c USING (company_id)
LEFT JOIN v_latest_signal v USING (company_id)
WHERE w.member_id = 1 ORDER BY w.created_at DESC;

-- 7) 모의 포트폴리오: CTE(보유 수량·평균 매수가) + 최신 종가 JOIN → 평가손익
WITH pos AS (
    SELECT company_id,
           SUM(CASE WHEN side='BUY' THEN quantity ELSE -quantity END) AS qty,
           SUM(CASE WHEN side='BUY' THEN quantity*price ELSE 0 END)   AS buy_amount,
           SUM(CASE WHEN side='BUY' THEN quantity ELSE 0 END)         AS buy_qty
    FROM paper_trades WHERE member_id = 1
    GROUP BY company_id
    HAVING SUM(CASE WHEN side='BUY' THEN quantity ELSE -quantity END) > 0
)
SELECT c.code, c.name, pos.qty,
       ROUND(pos.buy_amount*1.0/pos.buy_qty) AS avg_cost, v.close_price,
       ROUND((v.close_price - pos.buy_amount*1.0/pos.buy_qty) * pos.qty) AS pnl
FROM pos JOIN companies c USING (company_id) LEFT JOIN v_latest_signal v USING (company_id);

-- 8) 인덱스 근거 확인: 종목 1개의 시계열을 읽을 때 UNIQUE 인덱스를 쓰는지 본다
EXPLAIN (ANALYZE, COSTS OFF)
SELECT * FROM daily_prices WHERE company_id = 1 ORDER BY trade_date DESC LIMIT 20;

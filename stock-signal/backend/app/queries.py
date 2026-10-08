"""통계 API 가 사용하는 SQL. (sql/02_queries.sql 과 같은 내용 - 값만 파라미터로 바뀜)

지표 계산(이동평균, 52주 위치, 신호등)은 DB 뷰(v_price_change / v_indicators / v_latest_signal)가 하고,
여기서는 그 뷰를 JOIN / GROUP BY / HAVING 으로 묶어 보여 준다.
값은 항상 :param 으로 바인딩한다 (문자열 이어붙이기 금지 → SQL Injection 방지).
{order_col} 같은 자리표시자는 코드에서 허용 목록(whitelist)으로만 채운다.
"""

# 신호등 목록: 종목 + 최신 지표 + 초록/빨강 개수 (시세가 없는 종목도 보이도록 LEFT JOIN)
SIGNALS = """
SELECT c.code, c.name, m.name AS market_name, s.name AS sector_name,
       v.trade_date, v.close_price, v.change_pct,
       v.ma5, v.ma20, v.ma60, v.volume_ratio, v.pos_52w, v.ret_1w, v.ret_1m, v.ret_3m,
       v.sig_trend, v.sig_volume, v.sig_position, v.sig_momentum,
       (v.sig_trend = 'good')::int + (v.sig_volume = 'good')::int
         + (v.sig_position = 'good')::int + (v.sig_momentum = 'good')::int      AS good_cnt,
       (v.sig_trend = 'caution')::int + (v.sig_volume = 'caution')::int
         + (v.sig_position = 'caution')::int + (v.sig_momentum = 'caution')::int AS caution_cnt
FROM companies c
JOIN markets m ON m.market_id = c.market_id
LEFT JOIN sectors s ON s.sector_id = c.sector_id
LEFT JOIN v_latest_signal v ON v.company_id = c.company_id
WHERE (CAST(:sector AS varchar) IS NULL OR s.name = CAST(:sector AS varchar))
  AND (CAST(:market AS varchar) IS NULL OR m.name = CAST(:market AS varchar))
ORDER BY {order_col} {direction} NULLS LAST, c.code
"""

SIGNAL_ONE = """
SELECT c.code, c.name, m.name AS market_name, s.name AS sector_name,
       v.trade_date, v.close_price, v.change_pct,
       v.ma5, v.ma20, v.ma60, v.volume_ratio, v.high_52w, v.low_52w, v.pos_52w,
       v.ret_1w, v.ret_1m, v.ret_3m,
       v.sig_trend, v.sig_volume, v.sig_position, v.sig_momentum
FROM companies c
JOIN markets m ON m.market_id = c.market_id
LEFT JOIN sectors s ON s.sector_id = c.sector_id
LEFT JOIN v_latest_signal v ON v.company_id = c.company_id
WHERE c.code = :code
"""

# 차트용 시계열: 최근 N거래일의 종가와 이동평균 (서브쿼리로 최근 N행을 고른 뒤 날짜 오름차순)
SERIES = """
SELECT t.trade_date, t.close_price, t.ma5, t.ma20, t.ma60, t.volume
FROM (
    SELECT i.trade_date, i.close_price, i.ma5, i.ma20, i.ma60, i.volume
    FROM v_indicators i
    JOIN companies c ON c.company_id = i.company_id
    WHERE c.code = :code
    ORDER BY i.trade_date DESC
    LIMIT :limit
) t
ORDER BY t.trade_date
"""

# 기간 수익률 순위 ({ret_col} 은 ret_1w / ret_1m / ret_3m 중 하나)
RETURNS = """
SELECT c.code, c.name, s.name AS sector_name, v.close_price, v.{ret_col} AS ret_pct
FROM v_latest_signal v
JOIN companies c ON c.company_id = v.company_id
LEFT JOIN sectors s ON s.sector_id = c.sector_id
WHERE v.{ret_col} IS NOT NULL
ORDER BY v.{ret_col} {direction}
LIMIT :limit
"""

# 업종 요약: GROUP BY + HAVING, 업종 안에서 '추세가 좋은 종목' 비율
SECTORS = """
SELECT s.name AS sector,
       COUNT(*)                                             AS companies,
       ROUND(AVG(v.ret_1m), 2)                              AS avg_ret_1m,
       COUNT(*) FILTER (WHERE v.sig_trend = 'good')         AS good_trend_cnt,
       COUNT(*) FILTER (WHERE v.sig_trend = 'caution')      AS caution_trend_cnt
FROM v_latest_signal v
JOIN companies c ON c.company_id = v.company_id
JOIN sectors   s ON s.sector_id  = c.sector_id
GROUP BY s.name
HAVING COUNT(*) >= :min_companies
ORDER BY avg_ret_1m DESC NULLS LAST
"""

# 종목 비교: 선택한 종목들을 한 표로 (:codes 는 '{005930,000660}' 형태의 문자열)
COMPARE = """
SELECT c.code, c.name, s.name AS sector_name,
       v.close_price, v.change_pct, v.ret_1w, v.ret_1m, v.ret_3m, v.pos_52w, v.volume_ratio,
       v.sig_trend, v.sig_volume, v.sig_position, v.sig_momentum
FROM companies c
LEFT JOIN sectors s ON s.sector_id = c.sector_id
LEFT JOIN v_latest_signal v ON v.company_id = c.company_id
WHERE c.code = ANY(CAST(:codes AS varchar[]))
ORDER BY c.code
"""

# 관심종목 + 최신 신호등
WATCHLIST = """
SELECT w.watch_id, w.created_at, c.code, c.name, s.name AS sector_name,
       v.close_price, v.change_pct, v.ret_1m, v.pos_52w,
       v.sig_trend, v.sig_volume, v.sig_position, v.sig_momentum
FROM watchlist w
JOIN companies c ON c.company_id = w.company_id
LEFT JOIN sectors s ON s.sector_id = c.sector_id
LEFT JOIN v_latest_signal v ON v.company_id = c.company_id
WHERE w.member_id = :member_id
ORDER BY w.created_at DESC, w.watch_id DESC
"""

# 모의 포트폴리오: 거래 기록 → 보유 수량·평균 매수가(CTE) → 최신 종가와 JOIN 해서 평가손익
# (평균 매수가 = 매수 금액 합 / 매수 수량 합. 매도해도 평균 매수가는 바뀌지 않는 단순 방식)
PORTFOLIO = """
WITH pos AS (
    SELECT t.company_id,
           SUM(CASE WHEN t.side = 'BUY' THEN t.quantity ELSE -t.quantity END)        AS qty,
           SUM(CASE WHEN t.side = 'BUY' THEN t.quantity * t.price ELSE 0 END)        AS buy_amount,
           SUM(CASE WHEN t.side = 'BUY' THEN t.quantity ELSE 0 END)                  AS buy_qty
    FROM paper_trades t
    WHERE t.member_id = :member_id
    GROUP BY t.company_id
    HAVING SUM(CASE WHEN t.side = 'BUY' THEN t.quantity ELSE -t.quantity END) > 0
)
SELECT c.code, c.name, pos.qty,
       ROUND(pos.buy_amount * 1.0 / pos.buy_qty)                                      AS avg_cost,
       v.close_price,
       pos.qty * v.close_price                                                        AS market_value,
       ROUND((v.close_price - pos.buy_amount * 1.0 / pos.buy_qty) * pos.qty)          AS pnl,
       ROUND((v.close_price * 1.0 / (pos.buy_amount * 1.0 / pos.buy_qty) - 1) * 100, 2) AS pnl_pct,
       v.sig_trend
FROM pos
JOIN companies c ON c.company_id = pos.company_id
LEFT JOIN v_latest_signal v ON v.company_id = pos.company_id
ORDER BY market_value DESC NULLS LAST
"""

# 현재 보유 수량 (SELL 등록 전에 '가진 것보다 많이 팔 수 없다'를 확인)
HELD_QTY = """
SELECT COALESCE(SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END), 0) AS qty
FROM paper_trades
WHERE member_id = :member_id AND company_id = :company_id
"""

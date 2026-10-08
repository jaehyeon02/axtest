"""정적 SQL 모음. SQLite 와 PostgreSQL 모두에서 돌아가도록 표준 문법만 썼어요. 파라미터는 :이름.
(진입 신호 SQL 은 파라미터에 따라 모양이 달라져서 strategy.signal_sql 이 만들어요.)"""

# ───────── 종목·시세 ─────────
COMPANIES = """
SELECT c.company_id, c.code, c.name, c.market, s.name AS sector
FROM company c JOIN sector s ON s.sector_id = c.sector_id
WHERE c.name LIKE :like OR c.code LIKE :like
ORDER BY c.company_id
"""
COMPANY_BY_CODE = """
SELECT c.company_id, c.code, c.name, c.market, s.name AS sector
FROM company c JOIN sector s ON s.sector_id = c.sector_id WHERE c.code = :code
"""
COMPANY_BY_ID = "SELECT company_id, code, name FROM company WHERE company_id = :cid"

# 회사마다 가장 최근 종가와 전일 종가
LATEST_ALL = """
SELECT p.company_id, p.trade_date, p.close,
       (SELECT p2.close FROM price_daily p2
         WHERE p2.company_id = p.company_id AND p2.trade_date < p.trade_date
         ORDER BY p2.trade_date DESC LIMIT 1) AS prev_close
FROM price_daily p
WHERE p.trade_date = (SELECT MAX(trade_date) FROM price_daily WHERE company_id = p.company_id)
"""
LATEST_DATE = "SELECT MAX(trade_date) AS d FROM price_daily WHERE company_id = :cid"
FIRST_DATE = "SELECT MIN(trade_date) AS d FROM price_daily WHERE company_id = :cid"
SERIES = """
SELECT trade_date AS d, open, high, low, close, volume
FROM price_daily WHERE company_id = :cid AND trade_date >= :since ORDER BY trade_date
"""
PRICE_ON = "SELECT close FROM price_daily WHERE company_id = :cid AND trade_date = :d"
HAS_SAMPLE = "SELECT COUNT(*) AS n FROM ingestion_log WHERE source = 'sample'"

# ───────── 규칙 ─────────
RULE_LIST = """
SELECT r.rule_id, r.name, r.entry_type, r.entry_param, r.take_profit_pct, r.stop_loss_pct, r.max_hold_days, r.created_at, r.updated_at,
       (SELECT COUNT(*) FROM backtest_run b WHERE b.rule_id = r.rule_id) AS run_count,
       (SELECT COUNT(*) FROM trade t WHERE t.rule_id = r.rule_id) AS trade_count
FROM rule r WHERE r.client_id = :client ORDER BY r.updated_at DESC, r.rule_id DESC
"""
RULE_GET = """
SELECT rule_id, name, entry_type, entry_param, take_profit_pct, stop_loss_pct, max_hold_days, created_at, updated_at
FROM rule WHERE rule_id = :id AND client_id = :client
"""
RULE_NAME_TAKEN = "SELECT rule_id FROM rule WHERE client_id = :client AND name = :name"
RULE_INSERT = """
INSERT INTO rule(client_id, name, entry_type, entry_param, take_profit_pct, stop_loss_pct, max_hold_days, created_at, updated_at)
VALUES (:client, :name, :entry_type, :entry_param, :take_profit_pct, :stop_loss_pct, :max_hold_days, :now, :now)
RETURNING rule_id
"""
RULE_UPDATE = """
UPDATE rule SET name = :name, entry_type = :entry_type, entry_param = :entry_param, take_profit_pct = :take_profit_pct,
       stop_loss_pct = :stop_loss_pct, max_hold_days = :max_hold_days, updated_at = :now
WHERE rule_id = :id AND client_id = :client
"""
RULE_DELETE = "DELETE FROM rule WHERE rule_id = :id AND client_id = :client"

# ───────── 백테스트 ─────────
RUN_INSERT = """
INSERT INTO backtest_run(rule_id, company_id, rule_text, start_date, end_date, trade_count, win_count, avg_return, total_return, mdd,
                         benchmark_return, avg_hold_days, created_at)
VALUES (:rule_id, :company_id, :rule_text, :start_date, :end_date, :trade_count, :win_count, :avg_return, :total_return, :mdd,
        :benchmark_return, :avg_hold_days, :now)
RETURNING run_id
"""
BT_TRADE_INSERT = """
INSERT INTO backtest_trade(run_id, entry_date, entry_price, exit_date, exit_price, exit_reason, return_pct, hold_days)
VALUES (:run_id, :entry_date, :entry_price, :exit_date, :exit_price, :exit_reason, :return_pct, :hold_days)
"""
RUN_LIST = """
SELECT b.run_id, b.rule_id, b.rule_text, b.start_date, b.end_date, b.trade_count, b.win_count, b.avg_return, b.total_return, b.mdd,
       b.benchmark_return, b.avg_hold_days, b.created_at, c.code, c.name AS company_name
FROM backtest_run b JOIN company c ON c.company_id = b.company_id
WHERE b.rule_id = :rid ORDER BY b.run_id DESC
"""
RUN_GET = """
SELECT b.run_id, b.rule_id, b.rule_text, b.start_date, b.end_date, b.trade_count, b.win_count, b.avg_return, b.total_return, b.mdd,
       b.benchmark_return, b.avg_hold_days, b.created_at, c.code, c.name AS company_name
FROM backtest_run b JOIN rule r ON r.rule_id = b.rule_id JOIN company c ON c.company_id = b.company_id
WHERE b.run_id = :id AND r.client_id = :client
"""
RUN_TRADES = """
SELECT entry_date, entry_price, exit_date, exit_price, exit_reason, return_pct, hold_days
FROM backtest_trade WHERE run_id = :id ORDER BY entry_date
"""
RUN_DELETE = """
DELETE FROM backtest_run WHERE run_id = :id AND rule_id IN (SELECT rule_id FROM rule WHERE client_id = :client)
"""
# 종목마다 "가장 최근 실행" 하나씩만 모아서 규칙의 백테스트 성적을 합쳐요 (서브쿼리 + GROUP BY)
BACKTEST_AGG = """
SELECT COUNT(*) AS n, SUM(CASE WHEN t.return_pct > 0 THEN 1 ELSE 0 END) AS wins, AVG(t.return_pct) AS avg_return
FROM backtest_trade t
WHERE t.run_id IN (SELECT MAX(run_id) FROM backtest_run WHERE rule_id = :rid GROUP BY company_id)
"""
BACKTEST_RUNS_USED = "SELECT COUNT(DISTINCT company_id) AS n FROM backtest_run WHERE rule_id = :rid"

# ───────── 계좌·거래 ─────────
ACCOUNT_LIST = """
SELECT a.account_id, a.name, a.initial_cash, a.cash, a.created_at,
       (SELECT COUNT(*) FROM trade t WHERE t.account_id = a.account_id) AS trade_count
FROM account a WHERE a.client_id = :client ORDER BY a.account_id
"""
ACCOUNT_GET = "SELECT account_id, name, initial_cash, cash, created_at FROM account WHERE account_id = :id AND client_id = :client"
ACCOUNT_NAME_TAKEN = "SELECT account_id FROM account WHERE client_id = :client AND name = :name"
ACCOUNT_INSERT = """
INSERT INTO account(client_id, name, initial_cash, cash, created_at) VALUES (:client, :name, :cash, :cash, :now)
RETURNING account_id
"""
ACCOUNT_RENAME = "UPDATE account SET name = :name WHERE account_id = :id AND client_id = :client"
ACCOUNT_SET_CASH = "UPDATE account SET cash = :cash WHERE account_id = :id"
ACCOUNT_DELETE = "DELETE FROM account WHERE account_id = :id AND client_id = :client"

TRADE_INSERT = """
INSERT INTO trade(account_id, company_id, rule_id, side, trade_date, price, qty, fee, memo)
VALUES (:account_id, :company_id, :rule_id, :side, :trade_date, :price, :qty, :fee, :memo)
RETURNING trade_id
"""
TRADES_RAW = "SELECT trade_id, company_id, rule_id, side, trade_date, price, qty, fee FROM trade WHERE account_id = :aid ORDER BY trade_date, trade_id"
TRADES_VIEW = """
SELECT t.trade_id, t.account_id, t.company_id, c.code, c.name AS company_name, t.rule_id, r.name AS rule_name,
       t.side, t.trade_date, t.price, t.qty, t.fee, t.memo
FROM trade t JOIN company c ON c.company_id = t.company_id LEFT JOIN rule r ON r.rule_id = t.rule_id
WHERE t.account_id = :aid ORDER BY t.trade_date DESC, t.trade_id DESC
"""
TRADE_ONE = TRADES_VIEW.replace("WHERE t.account_id = :aid ORDER BY t.trade_date DESC, t.trade_id DESC", "WHERE t.trade_id = :tid AND t.account_id = :aid")
TRADE_UPDATE = "UPDATE trade SET memo = :memo, rule_id = :rule_id WHERE trade_id = :tid AND account_id = :aid"
TRADE_DELETE = "DELETE FROM trade WHERE trade_id = :tid AND account_id = :aid"
# 종목별 보유 수량을 SQL 로 직접 구해요 (GROUP BY + HAVING). replay 결과와 서로 맞는지 감사에도 써요.
HOLDINGS_SQL = """
SELECT t.company_id, SUM(CASE WHEN t.side = 'buy' THEN t.qty ELSE -t.qty END) AS qty
FROM trade t WHERE t.account_id = :aid GROUP BY t.company_id
HAVING SUM(CASE WHEN t.side = 'buy' THEN t.qty ELSE -t.qty END) > 0
"""
# 거래 내역만으로 다시 계산한 현금 (계좌에 저장된 cash 와 같아야 해요)
AUDIT_CASH = """
SELECT a.cash AS cash,
       a.initial_cash + COALESCE(SUM(CASE WHEN t.side = 'sell' THEN t.price * t.qty - t.fee ELSE -(t.price * t.qty + t.fee) END), 0) AS expected
FROM account a LEFT JOIN trade t ON t.account_id = a.account_id
WHERE a.account_id = :aid GROUP BY a.account_id, a.cash, a.initial_cash
"""
# 종목 화면용: 이 종목에 대한 내 거래 전부(모든 내 계좌)
MY_TRADES_FOR_COMPANY = """
SELECT t.trade_id, t.account_id, a.name AS account_name, t.side, t.trade_date, t.price, t.qty
FROM trade t JOIN account a ON a.account_id = t.account_id
WHERE a.client_id = :client AND t.company_id = :cid ORDER BY t.trade_date, t.trade_id
"""

# ───────── 대시보드: 종목 분석 표 ─────────
# 회사마다 "가장 최근 거래일" 한 줄에 과거 종가(LAG)·이동평균·평균 거래량(윈도 함수)을 붙이고 수익률 등을 계산해요.
# 전 종목을 한 번에 계산하므로 PARTITION BY company_id 를 써요. 이 CTE 위에 종목 표(DASH_ROWS)와 업종 집계(SECTOR_AGG)를 얹어요.
DASH_CTE = """
WITH w AS (
    SELECT company_id, trade_date, close, volume,
           LAG(close, 1)   OVER (PARTITION BY company_id ORDER BY trade_date) AS c1,
           LAG(close, 21)  OVER (PARTITION BY company_id ORDER BY trade_date) AS c21,
           LAG(close, 63)  OVER (PARTITION BY company_id ORDER BY trade_date) AS c63,
           LAG(close, 126) OVER (PARTITION BY company_id ORDER BY trade_date) AS c126,
           AVG(close)      OVER (PARTITION BY company_id ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS ma120,
           COUNT(close)    OVER (PARTITION BY company_id ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS n120,
           AVG(volume)     OVER (PARTITION BY company_id ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS vavg20,
           COUNT(volume)   OVER (PARTITION BY company_id ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS nv,
           ROW_NUMBER()    OVER (PARTITION BY company_id ORDER BY trade_date DESC) AS rn
    FROM price_daily
), latest AS (
    SELECT c.company_id, c.code, c.name, s.name AS sector, w.trade_date, w.close, w.volume,
           w.close * 100.0 / w.c1 - 100   AS chg,
           w.close * 100.0 / w.c21 - 100  AS r1m,
           w.close * 100.0 / w.c63 - 100  AS r3m,
           w.close * 100.0 / w.c126 - 100 AS r6m,
           CASE WHEN w.n120 = 120 THEN w.close * 100.0 / w.ma120 - 100 END AS ma_gap,
           CASE WHEN w.nv = 20 AND w.vavg20 > 0 THEN w.volume * 1.0 / w.vavg20 END AS vol_ratio,
           f.per, f.pbr,
           y.fiscal_year, y.revenue, y.operating_profit,
           y.operating_profit * 100.0 / y.revenue AS op_margin,
           (y.revenue - p.revenue) * 100.0 / p.revenue AS rev_growth
    FROM w
    JOIN company c ON c.company_id = w.company_id
    JOIN sector s ON s.sector_id = c.sector_id
    LEFT JOIN fundamental_daily f ON f.company_id = c.company_id
         AND f.trade_date = (SELECT MAX(trade_date) FROM fundamental_daily WHERE company_id = c.company_id)
    LEFT JOIN financial_year y ON y.company_id = c.company_id
         AND y.fiscal_year = (SELECT MAX(fiscal_year) FROM financial_year WHERE company_id = c.company_id)
    LEFT JOIN financial_year p ON p.company_id = c.company_id AND p.fiscal_year = y.fiscal_year - 1
    WHERE w.rn = 1
)
"""
DASH_ROWS = DASH_CTE + "SELECT * FROM latest ORDER BY company_id"
# 업종별 집계(GROUP BY): 위 표를 업종으로 묶어 평균을 내요. AVG 는 NULL 을 건너뛰어요.
SECTOR_AGG = DASH_CTE + """
SELECT sector, COUNT(*) AS n, AVG(chg) AS avg_chg, AVG(r1m) AS avg_r1m, AVG(r3m) AS avg_r3m, AVG(per) AS avg_per, AVG(pbr) AS avg_pbr, AVG(op_margin) AS avg_margin
FROM latest GROUP BY sector ORDER BY avg_r3m DESC
"""

# ───────── 종목 상세 ─────────
FUND_SERIES = """
SELECT trade_date AS d, per, pbr, eps, bps FROM fundamental_daily
WHERE company_id = :cid AND trade_date >= :since ORDER BY trade_date
"""
# 연간 재무 + 영업이익률 + 전년 대비 매출 성장률(LAG). LIMIT 은 윈도 계산 뒤에 적용돼요.
FINANCIALS = """
SELECT fiscal_year, revenue, operating_profit, net_income,
       ROUND(operating_profit * 100.0 / revenue, 1) AS op_margin,
       ROUND((revenue - LAG(revenue) OVER (ORDER BY fiscal_year)) * 100.0 / LAG(revenue) OVER (ORDER BY fiscal_year), 1) AS rev_growth
FROM financial_year WHERE company_id = :cid ORDER BY fiscal_year DESC LIMIT :n
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
FROM cur ORDER BY margin_rank, company_id
"""
# 가격 흐름 숫자 ②: 최대 낙폭(MDD) = 지금까지의 최고가 대비 가장 크게 내려간 비율(%)
ANALYSIS_MDD = """
SELECT MIN((close - peak) * 100.0 / peak) AS mdd FROM (
    SELECT close, MAX(close) OVER (ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak
    FROM price_daily WHERE company_id = :cid AND trade_date >= :since
) t
"""
# 가격 흐름 숫자 ③: 일별 등락률(변동성은 이 값들의 표준편차)
DAILY_RETURNS = """
SELECT trade_date, ret_pct FROM (
    SELECT trade_date, (close - LAG(close) OVER (ORDER BY trade_date)) * 100.0 / LAG(close) OVER (ORDER BY trade_date) AS ret_pct
    FROM price_daily WHERE company_id = :cid
) t WHERE ret_pct IS NOT NULL AND trade_date >= :since ORDER BY trade_date
"""
MONTHLY = """
SELECT substr(CAST(trade_date AS TEXT), 1, 7) AS ym, ROUND(AVG(close), 0) AS avg_close, MIN(low) AS low, MAX(high) AS high, SUM(volume) AS volume
FROM price_daily WHERE company_id = :cid
GROUP BY substr(CAST(trade_date AS TEXT), 1, 7) ORDER BY ym
"""

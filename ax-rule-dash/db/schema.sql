-- AX 룰랩 대시보드 DB 스키마 (3정규형). SQLite 와 PostgreSQL 모두에서 실행되도록 공통 문법만 사용했어요.
-- SQLAlchemy 모델(backend/app/models.py)과 같은 구조입니다.

-- ───────── 시장 데이터 (수집) ─────────
CREATE TABLE sector (
    sector_id   INTEGER PRIMARY KEY,
    name        VARCHAR(40) NOT NULL UNIQUE
);

CREATE TABLE company (
    company_id  INTEGER PRIMARY KEY,
    code        VARCHAR(12) NOT NULL UNIQUE,      -- 종목코드
    name        VARCHAR(60) NOT NULL,
    market      VARCHAR(10) NOT NULL,             -- KOSPI / KOSDAQ
    sector_id   INTEGER NOT NULL REFERENCES sector(sector_id),
    corp_code   VARCHAR(8)                        -- OpenDART 고유번호(재무 조회에 필요, 수집 때 채워요)
);

-- 일별 시세: 회사 1 : N 시세
CREATE TABLE price_daily (
    price_id    INTEGER PRIMARY KEY,
    company_id  INTEGER NOT NULL REFERENCES company(company_id),
    trade_date  DATE NOT NULL,
    open        NUMERIC(14,2) NOT NULL,
    high        NUMERIC(14,2) NOT NULL,
    low         NUMERIC(14,2) NOT NULL,
    close       NUMERIC(14,2) NOT NULL,
    volume      BIGINT NOT NULL,
    CONSTRAINT uq_price UNIQUE (company_id, trade_date),   -- 이 제약이 (company_id, trade_date) 인덱스도 만들어 줘요
    CONSTRAINT ck_price CHECK (low <= open AND low <= close AND high >= open AND high >= close)
);

-- 일별 투자지표(PER·PBR·EPS·BPS): 회사 1 : N. pykrx 의 get_market_fundamental 에서 수집. 적자 등으로 PER 이 없으면 NULL.
CREATE TABLE fundamental_daily (
    fund_id     INTEGER PRIMARY KEY,
    company_id  INTEGER NOT NULL REFERENCES company(company_id),
    trade_date  DATE NOT NULL,
    per         NUMERIC(10,2),
    pbr         NUMERIC(10,2),
    eps         NUMERIC(14,2),
    bps         NUMERIC(14,2),
    CONSTRAINT uq_fund UNIQUE (company_id, trade_date)
);

-- 연간 재무(사업보고서, 연결 우선): 회사 1 : N 연도. 금액 단위는 억원. OpenDART 에서 수집.
CREATE TABLE financial_year (
    fin_id           INTEGER PRIMARY KEY,
    company_id       INTEGER NOT NULL REFERENCES company(company_id),
    fiscal_year      INTEGER NOT NULL CHECK (fiscal_year BETWEEN 1990 AND 2100),
    revenue          NUMERIC(16,1) NOT NULL,
    operating_profit NUMERIC(16,1) NOT NULL,
    net_income       NUMERIC(16,1),
    CONSTRAINT uq_fin UNIQUE (company_id, fiscal_year)
);

-- ───────── 투자 규칙 + 백테스트 ─────────
-- 규칙 = 진입 조건 1개 + 청산 조건 3개(익절·손절·최대 보유일). 사용자(client_id) 소유.
--   ma_cross : 종가가 N일 이동평균선을 아래→위로 뚫은 날 (entry_param = N일)
--   dip_buy  : 하루 하락률이 X% 이상인 날 (entry_param = X%)
--   breakout : 종가가 직전 N일 최고 종가를 넘은 날 (entry_param = N일)
CREATE TABLE rule (
    rule_id         INTEGER PRIMARY KEY,
    client_id       VARCHAR(64) NOT NULL,
    name            VARCHAR(60) NOT NULL,
    entry_type      VARCHAR(12) NOT NULL CHECK (entry_type IN ('ma_cross', 'dip_buy', 'breakout')),
    entry_param     NUMERIC(6,2) NOT NULL CHECK (entry_param > 0),
    take_profit_pct NUMERIC(6,2) NOT NULL CHECK (take_profit_pct > 0),
    stop_loss_pct   NUMERIC(6,2) NOT NULL CHECK (stop_loss_pct > 0),
    max_hold_days   INTEGER NOT NULL CHECK (max_hold_days BETWEEN 1 AND 250),
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL,
    CONSTRAINT uq_rule_name UNIQUE (client_id, name)
);
CREATE INDEX ix_rule_client ON rule (client_id, updated_at);

-- 백테스트 1회 실행 = 규칙 1개 × 종목 1개 × 기간. 실행 당시의 규칙 설명(rule_text)을 같이 저장해 둬요
-- (나중에 규칙을 고쳐도 옛 결과가 어떤 규칙이었는지 알 수 있게 — 일부러 한 비정규화).
CREATE TABLE backtest_run (
    run_id           INTEGER PRIMARY KEY,
    rule_id          INTEGER NOT NULL REFERENCES rule(rule_id) ON DELETE CASCADE,
    company_id       INTEGER NOT NULL REFERENCES company(company_id),
    rule_text        VARCHAR(200) NOT NULL,
    start_date       DATE NOT NULL,
    end_date         DATE NOT NULL,
    trade_count      INTEGER NOT NULL CHECK (trade_count >= 0),
    win_count        INTEGER NOT NULL CHECK (win_count >= 0 AND win_count <= trade_count),
    avg_return       NUMERIC(10,2),               -- 거래당 평균 수익률(%, 수수료 반영)
    total_return     NUMERIC(10,2),               -- 거래 순서대로 복리로 이어 붙인 수익률(%)
    mdd              NUMERIC(10,2),               -- 거래 기준 최대 낙폭(%)
    benchmark_return NUMERIC(10,2),               -- 같은 기간 그냥 들고 있었을 때(%)
    avg_hold_days    NUMERIC(8,1),
    created_at       TIMESTAMP NOT NULL
);
CREATE INDEX ix_run_rule ON backtest_run (rule_id, company_id);

CREATE TABLE backtest_trade (
    bt_id        INTEGER PRIMARY KEY,
    run_id       INTEGER NOT NULL REFERENCES backtest_run(run_id) ON DELETE CASCADE,
    entry_date   DATE NOT NULL,
    entry_price  NUMERIC(14,2) NOT NULL,
    exit_date    DATE NOT NULL,
    exit_price   NUMERIC(14,2) NOT NULL,
    exit_reason  VARCHAR(8) NOT NULL CHECK (exit_reason IN ('tp', 'sl', 'time', 'end')),
    return_pct   NUMERIC(10,2) NOT NULL,
    hold_days    INTEGER NOT NULL CHECK (hold_days >= 0),
    CONSTRAINT ck_bt_dates CHECK (exit_date >= entry_date)
);
CREATE INDEX ix_bt_run ON backtest_trade (run_id);

-- ───────── 가상 계좌 + 거래 장부 ─────────
-- cash 는 거래 때마다 같이 갱신하는 잔고이고, CHECK(cash >= 0)이 "잔고 부족 매수"를 DB 수준에서 막아요.
-- 거래 내역(trade)으로 다시 계산한 값과 항상 같아야 해요(테스트·감사 쿼리로 확인).
CREATE TABLE account (
    account_id   INTEGER PRIMARY KEY,
    client_id    VARCHAR(64) NOT NULL,
    name         VARCHAR(40) NOT NULL,
    initial_cash NUMERIC(16,0) NOT NULL CHECK (initial_cash > 0),
    cash         NUMERIC(16,2) NOT NULL CHECK (cash >= 0),
    created_at   TIMESTAMP NOT NULL,
    CONSTRAINT uq_account_name UNIQUE (client_id, name)
);
CREATE INDEX ix_account_client ON account (client_id);

-- 거래 가격은 그날의 종가(price_daily)로 서버가 채워요(사용자가 마음대로 쓰지 못해요).
-- 보유 수량·평균단가는 이 표에서 SQL/재계산으로 구하고, 따로 저장하지 않아요.
CREATE TABLE trade (
    trade_id    INTEGER PRIMARY KEY,
    account_id  INTEGER NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
    company_id  INTEGER NOT NULL REFERENCES company(company_id),
    rule_id     INTEGER REFERENCES rule(rule_id) ON DELETE SET NULL,   -- 어떤 규칙에 따라 한 거래인지(선택)
    side        VARCHAR(4) NOT NULL CHECK (side IN ('buy', 'sell')),
    trade_date  DATE NOT NULL,
    price       NUMERIC(14,2) NOT NULL CHECK (price > 0),
    qty         INTEGER NOT NULL CHECK (qty > 0),
    fee         NUMERIC(14,2) NOT NULL CHECK (fee >= 0),
    memo        VARCHAR(200) NOT NULL DEFAULT ''
);
CREATE INDEX ix_trade_account ON trade (account_id, trade_date, trade_id);
CREATE INDEX ix_trade_rule ON trade (rule_id);

-- ───────── 수집 기록 ─────────
CREATE TABLE ingestion_log (
    log_id      INTEGER PRIMARY KEY,
    job         VARCHAR(20) NOT NULL,
    source      VARCHAR(20) NOT NULL,
    status      VARCHAR(10) NOT NULL CHECK (status IN ('ok', 'fail')),
    row_count   INTEGER NOT NULL DEFAULT 0,
    message     VARCHAR(300) NOT NULL DEFAULT '',
    finished_at TIMESTAMP NOT NULL
);

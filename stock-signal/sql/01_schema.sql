-- ============================================================
-- 종목 신호등 서비스 - DB 생성 스크립트 (PostgreSQL 16)
-- docker compose 최초 기동 시 자동 실행됩니다.
-- 다시 만들려면: docker compose down -v && docker compose up -d
--
-- 이 프로젝트의 핵심: "지표는 저장하지 않고 SQL(윈도우 함수 뷰)로 계산한다."
--   저장하는 것 : 종목, 일별 시세, 회원, 관심종목, 모의 거래
--   계산하는 것 : 등락률, 이동평균, 52주 위치, 기간 수익률, 신호등, 보유 수량·평가손익
-- ============================================================

-- 시장 (KOSPI, KOSDAQ ...)
CREATE TABLE markets (
    market_id   SMALLSERIAL PRIMARY KEY,
    name        VARCHAR(20) NOT NULL UNIQUE
);

-- 업종 (반도체, 자동차 ...)
CREATE TABLE sectors (
    sector_id   SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE
);

-- 종목
CREATE TABLE companies (
    company_id  SERIAL PRIMARY KEY,
    code        CHAR(6)      NOT NULL UNIQUE,          -- 종목코드 (예: 005930)
    name        VARCHAR(100) NOT NULL,
    market_id   SMALLINT     NOT NULL REFERENCES markets(market_id),
    sector_id   INT          REFERENCES sectors(sector_id),
    created_at  TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE INDEX idx_companies_market ON companies(market_id);
CREATE INDEX idx_companies_sector ON companies(sector_id);

-- 일별 시세 (종목 1 : N 시세)
CREATE TABLE daily_prices (
    price_id     BIGSERIAL PRIMARY KEY,
    company_id   INT    NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    trade_date   DATE   NOT NULL,
    open_price   INT    NOT NULL CHECK (open_price  >= 0),
    high_price   INT    NOT NULL CHECK (high_price  >= 0),
    low_price    INT    NOT NULL CHECK (low_price   >= 0),
    close_price  INT    NOT NULL CHECK (close_price >= 0),
    volume       BIGINT NOT NULL CHECK (volume      >= 0),
    CONSTRAINT uq_price_company_date UNIQUE (company_id, trade_date),
    CONSTRAINT ck_price_high_low CHECK (high_price >= low_price)
);
-- (company_id, trade_date) UNIQUE 인덱스가 종목별 시계열 조회와 윈도우 함수 정렬을 커버한다.
CREATE INDEX idx_prices_trade_date ON daily_prices(trade_date);

-- 회원 (로그인은 이번 범위가 아니므로 닉네임만 구분한다)
CREATE TABLE members (
    member_id   SERIAL PRIMARY KEY,
    nickname    VARCHAR(30) NOT NULL UNIQUE,
    created_at  TIMESTAMP   NOT NULL DEFAULT now()
);

-- 관심종목 (회원 N : M 종목 을 풀어 놓은 연결 테이블)
CREATE TABLE watchlist (
    watch_id    SERIAL PRIMARY KEY,
    member_id   INT       NOT NULL REFERENCES members(member_id)   ON DELETE CASCADE,
    company_id  INT       NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT uq_watch_member_company UNIQUE (member_id, company_id)
);
CREATE INDEX idx_watch_company ON watchlist(company_id);

-- 모의 거래 기록 (실제 주문이 아니라 "만약 샀다면" 연습용 기록)
-- 보유 수량·평균 매수가·평가손익은 이 표에서 계산한다 (저장하지 않음 → 3NF).
CREATE TABLE paper_trades (
    trade_id    BIGSERIAL PRIMARY KEY,
    member_id   INT         NOT NULL REFERENCES members(member_id)   ON DELETE CASCADE,
    company_id  INT         NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    trade_date  DATE        NOT NULL,
    side        VARCHAR(4)  NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity    INT         NOT NULL CHECK (quantity > 0),
    price       INT         NOT NULL CHECK (price >= 0),
    memo        VARCHAR(200),
    created_at  TIMESTAMP   NOT NULL DEFAULT now()
);
CREATE INDEX idx_trades_member_company ON paper_trades(member_id, company_id);

-- ------------------------------------------------------------
-- 뷰 1) 등락률
-- 등락률은 close_price 로부터 계산할 수 있는 '파생값'이므로 테이블에 저장하지 않는다.
-- (저장하면 시세를 수정할 때 등락률이 어긋난다 → 갱신 이상)
-- ------------------------------------------------------------
CREATE VIEW v_price_change AS
SELECT
    p.price_id,
    p.company_id,
    p.trade_date,
    p.close_price,
    p.volume,
    LAG(p.close_price) OVER w AS prev_close,
    ROUND(
        (p.close_price - LAG(p.close_price) OVER w) * 100.0
        / NULLIF(LAG(p.close_price) OVER w, 0),
        2
    ) AS change_pct
FROM daily_prices p
WINDOW w AS (PARTITION BY p.company_id ORDER BY p.trade_date);

-- ------------------------------------------------------------
-- 뷰 2) 지표: 이동평균 / 거래량 배수 / 52주(252거래일) 범위 / 기간 수익률
-- 윈도우 프레임을 "행 개수(ROWS)"로 잡는다 = 거래일 기준 (휴장일은 행이 없으므로 자동 제외).
-- 데이터가 모자라면 NULL (예: 60일 평균은 60행이 쌓이기 전까지 NULL).
-- ------------------------------------------------------------
CREATE VIEW v_indicators AS
SELECT
    p.company_id,
    p.trade_date,
    p.close_price,
    p.volume,
    COUNT(*) OVER w60 AS n_rows,
    CASE WHEN COUNT(*) OVER w5  = 5  THEN ROUND(AVG(p.close_price) OVER w5)  END AS ma5,
    CASE WHEN COUNT(*) OVER w20 = 20 THEN ROUND(AVG(p.close_price) OVER w20) END AS ma20,
    CASE WHEN COUNT(*) OVER w60 = 60 THEN ROUND(AVG(p.close_price) OVER w60) END AS ma60,
    -- 거래량 배수: 오늘 거래량 / 직전 20거래일 평균 (오늘 제외)
    ROUND(
        p.volume * 1.0 / NULLIF(AVG(p.volume) OVER (
            PARTITION BY p.company_id ORDER BY p.trade_date
            ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING), 0),
        2
    ) AS volume_ratio,
    MAX(p.high_price) OVER w252 AS high_52w,
    MIN(p.low_price)  OVER w252 AS low_52w,
    -- 52주 범위 안에서의 위치 (0=최저, 100=최고)
    -- (최소 60거래일이 쌓이기 전에는 범위가 너무 좁아 의미가 없으므로 NULL)
    CASE WHEN COUNT(*) OVER w252 >= 60 THEN ROUND(
        (p.close_price - MIN(p.low_price) OVER w252) * 100.0
        / NULLIF(MAX(p.high_price) OVER w252 - MIN(p.low_price) OVER w252, 0),
        1
    ) END AS pos_52w,
    -- 기간 수익률 (N거래일 전 종가 대비)
    ROUND((p.close_price - LAG(p.close_price, 5)  OVER w) * 100.0 / NULLIF(LAG(p.close_price, 5)  OVER w, 0), 2) AS ret_1w,
    ROUND((p.close_price - LAG(p.close_price, 21) OVER w) * 100.0 / NULLIF(LAG(p.close_price, 21) OVER w, 0), 2) AS ret_1m,
    ROUND((p.close_price - LAG(p.close_price, 63) OVER w) * 100.0 / NULLIF(LAG(p.close_price, 63) OVER w, 0), 2) AS ret_3m
FROM daily_prices p
WINDOW
    w    AS (PARTITION BY p.company_id ORDER BY p.trade_date),
    w5   AS (PARTITION BY p.company_id ORDER BY p.trade_date ROWS BETWEEN 4   PRECEDING AND CURRENT ROW),
    w20  AS (PARTITION BY p.company_id ORDER BY p.trade_date ROWS BETWEEN 19  PRECEDING AND CURRENT ROW),
    w60  AS (PARTITION BY p.company_id ORDER BY p.trade_date ROWS BETWEEN 59  PRECEDING AND CURRENT ROW),
    w252 AS (PARTITION BY p.company_id ORDER BY p.trade_date ROWS BETWEEN 251 PRECEDING AND CURRENT ROW);

-- ------------------------------------------------------------
-- 뷰 3) 종목별 "가장 최근 거래일"의 신호등
-- 신호는 'good'(초록) / 'normal'(노랑) / 'caution'(빨강) / 'na'(데이터 부족) 네 값.
--   추세     : 5일 > 20일 > 60일 평균 = good, 5일 < 20일 < 60일 = caution, 그 외 normal
--   거래량   : 20일 평균의 1.5배 이상 = good, 0.7배 이하 = caution, 그 외 normal
--   가격위치 : 52주 범위의 하위 30% 이하 = good(싼 구간), 80% 이상 = caution(비싼 구간), 그 외 normal
--   단기흐름 : 1주 수익률 +3% 이상 = good, -3% 이하 = caution, 그 외 normal
-- (투자 추천이 아니라 "숫자를 쉬운 말로 바꾸는" 규칙이다. 기준 숫자는 문서 05 참고)
-- ------------------------------------------------------------
CREATE VIEW v_latest_signal AS
SELECT DISTINCT ON (i.company_id)
    i.company_id,
    i.trade_date,
    i.close_price,
    i.volume,
    pc.change_pct,
    i.ma5, i.ma20, i.ma60,
    i.volume_ratio, i.high_52w, i.low_52w, i.pos_52w,
    i.ret_1w, i.ret_1m, i.ret_3m,
    CASE WHEN i.ma60 IS NULL THEN 'na'
         WHEN i.ma5 > i.ma20 AND i.ma20 > i.ma60 THEN 'good'
         WHEN i.ma5 < i.ma20 AND i.ma20 < i.ma60 THEN 'caution'
         ELSE 'normal' END AS sig_trend,
    CASE WHEN i.volume_ratio IS NULL THEN 'na'
         WHEN i.volume_ratio >= 1.5 THEN 'good'
         WHEN i.volume_ratio <= 0.7 THEN 'caution'
         ELSE 'normal' END AS sig_volume,
    CASE WHEN i.pos_52w IS NULL THEN 'na'
         WHEN i.pos_52w <= 30 THEN 'good'
         WHEN i.pos_52w >= 80 THEN 'caution'
         ELSE 'normal' END AS sig_position,
    CASE WHEN i.ret_1w IS NULL THEN 'na'
         WHEN i.ret_1w >= 3  THEN 'good'
         WHEN i.ret_1w <= -3 THEN 'caution'
         ELSE 'normal' END AS sig_momentum
FROM v_indicators i
JOIN v_price_change pc ON pc.company_id = i.company_id AND pc.trade_date = i.trade_date
ORDER BY i.company_id, i.trade_date DESC;

-- 시장 기본 데이터
INSERT INTO markets (name) VALUES ('KOSPI'), ('KOSDAQ');

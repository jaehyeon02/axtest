-- ============================================================
-- 주식 종목 분석 데이터 서비스 - DB 생성 스크립트 (PostgreSQL 16)
-- docker compose 최초 기동 시 자동 실행됩니다.
-- 다시 만들려면: docker compose down -v && docker compose up -d
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
-- (company_id, trade_date) UNIQUE 인덱스가 종목별 조회를 이미 커버한다.
-- 날짜 단독 조회(특정 일자 랭킹, 최근 N일 집계)를 위한 인덱스:
CREATE INDEX idx_prices_trade_date ON daily_prices(trade_date);

-- 연도별 재무 (종목 1 : N 재무) - OpenDART 사업보고서 주요계정, 단위: 원
CREATE TABLE financial_statements (
    statement_id       BIGSERIAL PRIMARY KEY,
    company_id         INT      NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    fiscal_year        SMALLINT NOT NULL,
    revenue            BIGINT,   -- 매출액
    operating_profit   BIGINT,   -- 영업이익
    net_income         BIGINT,   -- 당기순이익
    total_assets       BIGINT,   -- 자산총계
    total_liabilities  BIGINT,   -- 부채총계
    total_equity       BIGINT,   -- 자본총계
    CONSTRAINT uq_fin_company_year UNIQUE (company_id, fiscal_year)
);

-- 종목 메모 (사용자가 직접 등록하는 데이터: CRUD 실습용)
CREATE TABLE notes (
    note_id     SERIAL PRIMARY KEY,
    company_id  INT          NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    title       VARCHAR(100) NOT NULL,
    content     TEXT         NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE INDEX idx_notes_company ON notes(company_id);

-- ------------------------------------------------------------
-- 등락률 뷰
-- 등락률은 close_price 로부터 계산할 수 있는 '파생값'이므로 테이블에 저장하지 않는다.
-- (저장하면 시세를 수정할 때 등락률이 어긋난다 → 3NF 위반 + 갱신 이상)
-- 전일 종가는 윈도우 함수 LAG 로 구한다.
-- ------------------------------------------------------------
CREATE VIEW v_price_change AS
SELECT
    p.price_id,
    p.company_id,
    p.trade_date,
    p.open_price,
    p.high_price,
    p.low_price,
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

-- 시장 기본 데이터
INSERT INTO markets (name) VALUES ('KOSPI'), ('KOSDAQ');

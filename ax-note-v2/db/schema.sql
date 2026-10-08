-- AX 근거노트 v2 DB 스키마 (3정규형). SQLite 와 PostgreSQL 모두에서 실행되도록 공통 문법만 사용했어요.
-- SQLAlchemy 모델(backend/app/models.py)과 같은 구조입니다.

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
    corp_code   VARCHAR(8)                        -- OpenDART 고유번호(공시·재무 조회에 필요, 수집 때 채워요)
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
    CONSTRAINT uq_price UNIQUE (company_id, trade_date),
    CONSTRAINT ck_price CHECK (low <= open AND low <= close AND high >= open AND high >= close)
);
CREATE INDEX ix_price_company_date ON price_daily (company_id, trade_date);

-- 연간 재무(사업보고서 연결 기준): 회사 1 : N 연도 (금액 단위: 억원)
CREATE TABLE financial_year (
    fin_id           INTEGER PRIMARY KEY,
    company_id       INTEGER NOT NULL REFERENCES company(company_id),
    fiscal_year      INTEGER NOT NULL CHECK (fiscal_year BETWEEN 1990 AND 2100),
    revenue          NUMERIC(16,1) NOT NULL,
    operating_profit NUMERIC(16,1) NOT NULL,
    net_income       NUMERIC(16,1),
    CONSTRAINT uq_fin UNIQUE (company_id, fiscal_year)
);

-- 공시 + 내 자료: 회사 1 : N 문서.
--   filing = OpenDART 에서 수집한 공시(rcept_no 가 있고 수정 불가)
--   news   = 사용자가 직접 붙인 기사·메모(created_by 가 있고 본인만 보임)
CREATE TABLE document (
    doc_id         INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES company(company_id),
    doc_type       VARCHAR(10) NOT NULL CHECK (doc_type IN ('news', 'filing')),
    title          VARCHAR(200) NOT NULL,
    body           TEXT NOT NULL DEFAULT '',
    source         VARCHAR(60) NOT NULL,
    sentiment      VARCHAR(8) NOT NULL DEFAULT 'neu' CHECK (sentiment IN ('pos', 'neg', 'neu')),  -- 내 자료에서만 사용자가 표시
    published_date DATE NOT NULL,
    rcept_no       VARCHAR(20),                   -- DART 접수번호(중복 적재 방지용, 수집 문서만)
    url            VARCHAR(300),
    created_by     VARCHAR(64),                   -- 사용자가 직접 추가한 문서면 client_id, 수집 문서는 NULL
    CONSTRAINT ck_doc_owner CHECK ((doc_type = 'filing' AND created_by IS NULL) OR (doc_type = 'news' AND created_by IS NOT NULL))
);
CREATE UNIQUE INDEX ux_doc_rcept ON document (rcept_no);
CREATE INDEX ix_doc_company_date ON document (company_id, published_date);

-- 사용자 분석 노트: 회사 1 : N 노트
CREATE TABLE note (
    note_id     INTEGER PRIMARY KEY,
    client_id   VARCHAR(64) NOT NULL,             -- 로그인이 없어서 브라우저가 만든 임시 ID로 구분
    company_id  INTEGER NOT NULL REFERENCES company(company_id),
    title       VARCHAR(120) NOT NULL,
    memo        TEXT NOT NULL DEFAULT '',
    stance      VARCHAR(8) NOT NULL DEFAULT 'neu' CHECK (stance IN ('pos', 'neg', 'neu')),
    created_at  TIMESTAMP NOT NULL,
    updated_at  TIMESTAMP NOT NULL
);
CREATE INDEX ix_note_client ON note (client_id, updated_at);

-- 노트에 담은 근거: 문서 또는 주가 변동일 중 정확히 하나
CREATE TABLE note_evidence (
    evidence_id INTEGER PRIMARY KEY,
    note_id     INTEGER NOT NULL REFERENCES note(note_id) ON DELETE CASCADE,
    doc_id      INTEGER REFERENCES document(doc_id) ON DELETE CASCADE,
    price_id    INTEGER REFERENCES price_daily(price_id) ON DELETE CASCADE,
    comment     VARCHAR(300) NOT NULL DEFAULT '',
    CONSTRAINT ck_evidence_one CHECK (
        (doc_id IS NOT NULL AND price_id IS NULL) OR (doc_id IS NULL AND price_id IS NOT NULL)
    )
);
CREATE INDEX ix_evidence_note ON note_evidence (note_id);

-- 관심종목: 사용자 1 : N 종목 (같은 종목 중복 방지)
CREATE TABLE watchlist (
    watch_id    INTEGER PRIMARY KEY,
    client_id   VARCHAR(64) NOT NULL,
    company_id  INTEGER NOT NULL REFERENCES company(company_id),
    created_at  TIMESTAMP NOT NULL,
    CONSTRAINT uq_watch UNIQUE (client_id, company_id)
);

-- 데이터 수집 기록: 어떤 소스에서 언제 몇 행을 넣었는지(화면의 "데이터 출처" 표시에도 써요)
CREATE TABLE ingestion_log (
    log_id      INTEGER PRIMARY KEY,
    job         VARCHAR(20) NOT NULL,             -- prices / filings / financials / sample
    source      VARCHAR(20) NOT NULL,             -- pykrx / opendart / sample
    status      VARCHAR(10) NOT NULL CHECK (status IN ('ok', 'fail')),
    row_count   INTEGER NOT NULL DEFAULT 0,
    message     VARCHAR(300) NOT NULL DEFAULT '',
    finished_at TIMESTAMP NOT NULL
);

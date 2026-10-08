# 주식 종목 데이터 서비스 (1차 세미프로젝트 — DB 중심)

주가·재무 데이터를 **PostgreSQL** 에 구축하고, **FastAPI** 로 등록·조회·수정·삭제(CRUD)와 **SQL 통계**를 제공합니다.
(과정 문서 「프로젝트 절차 및 문서화」의 1차 세미프로젝트 범위: 실제 데이터 + Python + DB 모델링 + SQL + FastAPI. React·LLM·RAG 는 제외)

```
FinanceDataReader / CSV ─┐
OpenDART ────────────────┼→ Python(Pandas 전처리) → PostgreSQL → SQLAlchemy/SQL → FastAPI → Swagger(/docs)
종목 마스터 CSV ──────────┘
```

## 폴더 구조

```
stock-db/
├─ docker-compose.yml          # PostgreSQL (최초 기동 시 sql/01_schema.sql 자동 실행)
├─ sql/
│  ├─ 01_schema.sql            # 테이블 6개 + 뷰 1개 (DB 생성 스크립트)
│  └─ 02_queries.sql           # 주요 SQL 6개 (직접 실행해 보기)
├─ backend/
│  ├─ app/                     # FastAPI (models, schemas, routers, queries, errors ...)
│  │  └─ static/               # 대시보드 화면 (index.html, style.css, app.js — 외부 라이브러리 없음)
│  ├─ scripts/                 # 데이터 적재: load_master / collect_prices / collect_dart
│  ├─ data/companies.csv       # 종목 마스터 (12종목, 업종은 팀 분류 - 자유롭게 수정)
│  └─ tests/test_api.py        # 기능 테스트 19개
└─ docs/                       # 제출 문서 8종 (기획서 ~ 최종결과보고서)
```

## 실행 순서

```bash
# 1) DB 기동 (Docker 필요)
docker compose up -d

# 2) 백엔드 준비 (Python 3.10+)
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                      # DART 키는 collect_dart 에만 필요

# 3) 데이터 적재 (backend 폴더에서, 순서대로)
python -m scripts.load_master                             # 종목 마스터
python -m scripts.collect_prices --start 2024-01-01       # 주가 (막히면 --csv-dir data/prices)
python -m scripts.collect_dart --years 2022 2023 2024     # 재무 (DART_API_KEY 필요)

# 4) API 서버
uvicorn app.main:app --reload --port 8000
#   → 대시보드(화면): http://localhost:8000/   (자동으로 /dashboard/ 로 이동)
#   → Swagger(API):   http://localhost:8000/docs

# 5) 테스트
pytest -v
```

스키마를 바꾼 뒤 DB 를 다시 만들려면: `docker compose down -v && docker compose up -d` (데이터도 함께 삭제됨)

## 대시보드 화면

서버를 켜고 `http://localhost:8000/` 을 열면 바로 화면이 나옵니다. (HTML/CSS/JS 만 사용, 인터넷 연결 없이 동작)

- 종목·기간 선택 → KPI 카드, 종가 차트(+거래량, 마우스 올리면 값 표시)
- 월별 통계, 업종별 평균 등락률, 상승률/하락률/거래량 순위(행 클릭 시 종목 전환), 변동성 큰 종목, 재무 비율
- 시세 등록·삭제, 종목별 메모 등록·수정·삭제
- 데이터를 적재하기 전에는 "데이터가 없습니다" 안내가 보입니다. 먼저 3) 데이터 적재를 해 주세요.

## 문서와 코드의 대응

| 문서 | 대응하는 파일 |
|---|---|
| 05 ERD·DB 설계서 | `sql/01_schema.sql`, `backend/app/models.py` |
| 06 기능/API 정의서 | `backend/app/routers/*.py` |
| 03 데이터 조사·정의서 | `backend/scripts/*.py`, `backend/data/companies.csv` |
| 07 테스트 결과서 | `backend/tests/test_api.py` |
| 주요 SQL | `sql/02_queries.sql`, `backend/app/queries.py` |

## 확인된 것과 아직 확인되지 않은 것

작성자 환경에서 **실제 PostgreSQL 16으로 확인한 것**
- `01_schema.sql` 실행, 뷰 동작, 제약조건(UNIQUE / FK / CHECK / CASCADE) 오류 코드
- `02_queries.sql` 6개와 API 가 쓰는 SQL(`queries.py`) 전체 (선택 파라미터 NULL 경우 포함)
- 적재 스크립트의 전처리·UPSERT·재실행 시 중복 방지, 재무 계정 추출 (합성 데이터 사용, 외부 API 호출 없이)
- Pydantic 입력 검증 규칙
- 대시보드 화면: 같은 SQL·같은 JSON 형태로 응답하는 임시 서버에 붙여 헤드리스 브라우저로 확인 (차트, 순위 탭, 메모/시세 CRUD, 오류 메시지, 모바일 폭, 다크모드)

**이 환경에서 실행하지 못한 것** (PyPI 접속 불가로 FastAPI·SQLAlchemy 를 설치할 수 없었음)
- FastAPI 서버 기동(실제 서버에 붙인 대시보드 포함)과 `pytest` 19개, FinanceDataReader·OpenDART 실제 호출
→ 위 순서대로 처음 실행할 때 오류가 나면 오류 메시지를 그대로 알려 주세요.

## 알아 둘 점
- **ORM 사용 범위**: 문서에 "SQLAlchemy ORM 은 2차 프로젝트부터"라는 메모와, 1차 아키텍처에 SQLAlchemy 가 포함된 그림이 함께 있어 서로 엇갈립니다. 이 프로젝트는 CRUD 는 SQLAlchemy ORM, 통계는 직접 SQL(`text()`)로 구성했습니다. 강사님 기준이 다르면 알려 주세요.
- 업종 분류는 **팀이 단순화한 분류**입니다 (`data/companies.csv`).
- 시세는 가공 없이 저장한 원본 가격이며, 등락률은 저장하지 않고 뷰(`v_price_change`)로 계산합니다.
- 이전에 만든 `stock-insight`(React + RAG) 뼈대는 이 문서 기준으로는 **3차(AI 통합) 프로젝트용**입니다.

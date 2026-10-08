# 종목 신호등 서비스 (1차 세미프로젝트 — DB 중심, 대안 버전)

주가를 **PostgreSQL** 에 구축하고, 이동평균·52주 위치·수익률·신호등을 **SQL 뷰(윈도우 함수)** 로 계산해
관심종목·모의 거래와 함께 **FastAPI** 로 제공합니다.
(과정 문서 「프로젝트 절차 및 문서화」의 1차 범위: 실제 데이터 + Python + DB 모델링 + SQL + FastAPI. React·LLM·RAG 는 제외, HTML 화면은 선택 사항)

> 같은 주제의 다른 버전 `stock-db`(재무 비율·메모 중심)와 **접근이 다릅니다.**
> 이 버전은 "파생값을 저장하지 않고 뷰로 계산한다"와 "회원–종목 N:M 관계"가 설계의 중심입니다.

```
FinanceDataReader / CSV ─┐
종목 마스터 CSV ─────────┴→ Python(Pandas 전처리) → PostgreSQL ─ 뷰(v_price_change → v_indicators → v_latest_signal)
                                                       ↑ SQLAlchemy(CRUD) / SQL(통계) ← FastAPI ← Swagger(/docs), 화면(/)
```

## 핵심 설계 한 장 요약
| 저장하는 것 (6+1) | 계산하는 것 (뷰/쿼리) |
|---|---|
| markets, sectors, companies, daily_prices, members, watchlist, paper_trades | 등락률, 5/20/60일 이동평균, 거래량 배수, 52주 위치, 1주/1개월/3개월 수익률, 4가지 신호, 보유 수량·평균 매수가·평가손익 |

## 폴더 구조
```
stock-signal/
├─ docker-compose.yml          # PostgreSQL (최초 기동 시 sql/01_schema.sql 자동 실행)
├─ sql/
│  ├─ 01_schema.sql            # 테이블 7개 + 뷰 3개 + 제약조건 + 인덱스
│  └─ 02_queries.sql           # 주요 SQL 8개 (직접 실행해 보기)
├─ backend/
│  ├─ app/                     # FastAPI (models, schemas, routers, queries, errors)
│  │  └─ static/               # 선택: HTML 대시보드 (외부 라이브러리 없음)
│  ├─ scripts/                 # 데이터 적재: load_master / collect_prices
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
cp .env.example .env

# 3) 데이터 적재 (backend 폴더에서, 순서대로)
python -m scripts.load_master                             # 종목 마스터
python -m scripts.collect_prices --start 2024-01-01       # 주가 (막히면 --csv-dir data/prices)
#   ※ 지표가 의미 있으려면 시세가 최소 60거래일(3개월 수익률은 64일), 가능하면 1년 이상 필요

# 4) API 서버
uvicorn app.main:app --reload --port 8000
#   → 화면:    http://localhost:8000/   (자동으로 /dashboard/ 로 이동)
#   → Swagger: http://localhost:8000/docs

# 5) 테스트
pytest -v
```
스키마를 바꾼 뒤 DB 를 다시 만들려면: `docker compose down -v && docker compose up -d` (데이터도 함께 삭제됨)

## 화면에서 할 수 있는 것
1. 위쪽에서 닉네임으로 회원을 만들고 선택 (로그인 없음)
2. **신호등 표**: 종목별 추세·거래량·가격 위치·단기 흐름. 행을 누르면 쉬운 말 설명과 종가·이동평균 차트
3. ☆ 로 관심종목 담기/해제, **모의 포트폴리오**에 매수·매도 기록 → 평가손익 확인 (보유보다 많이 팔면 오류)
4. 수익률 순위(1주/1개월/3개월), 업종 요약

## 문서와 코드의 대응
| 문서 | 대응하는 파일 |
|---|---|
| 05 ERD·DB 설계서 | `sql/01_schema.sql`, `backend/app/models.py` |
| 06 기능/API 정의서 | `backend/app/routers/*.py`, `backend/app/queries.py` |
| 03 데이터 조사·정의서 | `backend/scripts/*.py`, `backend/data/companies.csv` |
| 07 테스트 결과서 | `backend/tests/test_api.py` |
| 주요 SQL | `sql/02_queries.sql` |

## 확인된 것과 아직 확인되지 않은 것
작성자 환경에서 **실제 PostgreSQL 16 으로 확인한 것** (합성 데이터 사용, 외부 API 호출 없이)
- `01_schema.sql` 실행, 뷰 3개 동작, 제약조건(UNIQUE / CHECK / CASCADE) 오류
- 이동평균·1주 수익률을 `AVG`/수기 계산과 대조해 일치, 포트폴리오 평가손익을 손계산과 대조해 일치
- `02_queries.sql` 8개와 API 가 쓰는 SQL(`queries.py`) 전체, 시세 60일 미만·시세 없는 종목의 처리
- Pydantic 입력 검증 규칙
- 대시보드 화면: 같은 SQL·같은 JSON 형태로 응답하는 임시 서버에 붙여 헤드리스 브라우저로 27개 항목 점검 (신호등·차트·관심종목·모의 거래·오류 메시지·모바일 폭)

**이 환경에서 실행하지 못한 것** (PyPI 접속 불가로 FastAPI·SQLAlchemy 를 설치할 수 없었음)
- FastAPI 서버 기동(실제 서버에 붙인 화면 포함), `pytest` 19개, 이 버전에서의 적재 스크립트 재실행, FinanceDataReader 실제 호출
→ 위 순서대로 처음 실행할 때 오류가 나면 오류 메시지를 그대로 알려 주세요.

## 알아 둘 점
- 신호 기준 숫자(1.5배, 30%/80%, ±3%)는 **팀이 정한 값**이며 투자 성과를 검증한 것이 아닙니다. 투자 추천이 아닙니다 (`docs/05` 의 기준표, 바꾸려면 뷰 한 곳만 수정).
- 평균 매수가는 단순 평균입니다 (`docs/06`). 실제 증권사의 이동평균법과 다를 수 있습니다.
- ORM 사용 범위: 문서에 "SQLAlchemy ORM 은 2차부터"라는 메모와 1차 아키텍처에 SQLAlchemy 가 포함된 그림이 엇갈립니다. CRUD 는 SQLAlchemy ORM, 통계는 직접 SQL(`text()`)로 구성했습니다. 강사님 기준이 다르면 알려 주세요.
- 업종 분류는 팀이 단순화한 분류입니다 (`data/companies.csv`).

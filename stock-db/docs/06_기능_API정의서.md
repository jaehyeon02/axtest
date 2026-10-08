# 06. 기능/API 정의서

기본 주소: `http://localhost:8000` · Swagger UI: `/docs`
요청 흐름: `사용자 요청 → FastAPI(라우터) → SQLAlchemy / SQL → PostgreSQL → JSON 응답`

## 1. API 목록

| Method | URL | 기능 | 성공 | 주요 오류 |
|---|---|---|:---:|---|
| GET | `/health` | 서버·DB 연결 확인 | 200 | |
| GET | `/markets` | 시장 목록 | 200 | |
| GET | `/sectors` | 업종 목록 | 200 | |
| POST | `/sectors` | 업종 등록 | 201 | 409 이름 중복 |
| GET | `/companies?q=&market_id=&sector_id=&limit=&offset=` | 종목 검색·목록 | 200 | |
| GET | `/companies/{company_id}` | 종목 상세 | 200 | 404 |
| POST | `/companies` | 종목 등록 | 201 | 409 코드 중복·없는 시장/업종, 422 형식 오류 |
| PUT | `/companies/{company_id}` | 종목 수정 (보낸 항목만) | 200 | 404, 422 |
| DELETE | `/companies/{company_id}` | 종목 삭제 (시세·재무·메모 포함) | 204 | 404 |
| GET | `/prices?code=&start=&end=&limit=&offset=` | 시세 조회 (최신순) | 200 | |
| GET | `/prices/{price_id}` | 시세 1건 | 200 | 404 |
| POST | `/prices` | 시세 등록 | 201 | 404 없는 종목, 409 날짜 중복, 422 값 오류 |
| PUT | `/prices/{price_id}` | 시세 수정 (보낸 항목만) | 200 | 404, 422 |
| DELETE | `/prices/{price_id}` | 시세 삭제 | 204 | 404 |
| GET | `/financials?code=&year=` | 연도별 재무 조회 | 200 | |
| GET | `/notes?company_id=&limit=` | 메모 목록 | 200 | |
| GET | `/notes/{note_id}` | 메모 1건 | 200 | 404 |
| POST | `/notes` | 메모 등록 | 201 | 404 없는 종목, 422 빈 제목/내용 |
| PUT | `/notes/{note_id}` | 메모 수정 | 200 | 404, 422 |
| DELETE | `/notes/{note_id}` | 메모 삭제 | 204 | 404 |
| GET | `/statistics/summary?code=&start=&end=` | 종목 요약 | 200 | 404 데이터 없음 |
| GET | `/statistics/monthly?code=&year=` | 월별 통계 | 200 | 404 데이터 없음 |
| GET | `/statistics/sectors?days=30` | 업종별 평균 등락률 | 200 | |
| GET | `/statistics/ranking?metric=change\|volume&order=desc\|asc&day=&limit=` | 일자별 TOP N | 200 | 422 잘못된 metric |
| GET | `/statistics/volatile?threshold=4&days=180&min_days=3` | 변동성 큰 종목 | 200 | |
| GET | `/statistics/financial-ratios?code=` | 재무 비율 | 200 | |

## 2. 요청/응답 예시

### 시세 등록 `POST /prices`
```json
{
  "company_id": 1,
  "trade_date": "2026-10-02",
  "open_price": 71000,
  "high_price": 72500,
  "low_price": 70800,
  "close_price": 72000,
  "volume": 12345678
}
```
응답 `201`
```json
{ "price_id": 501, "company_id": 1, "trade_date": "2026-10-02", "open_price": 71000,
  "high_price": 72500, "low_price": 70800, "close_price": 72000, "volume": 12345678 }
```

### 시세 수정 `PUT /prices/501` (보낸 항목만 바뀜)
```json
{ "close_price": 72100 }
```

### 오류 응답 형식
```json
{ "detail": "이미 존재하는 데이터입니다." }
```

### 종목 요약 `GET /statistics/summary?code=005930`
```json
{ "code": "005930", "name": "삼성전자", "trading_days": 20,
  "first_date": "2026-09-01", "last_date": "2026-09-30",
  "avg_close": 70000, "max_close": 72000, "min_close": 68000, "avg_volume": 1000000 }
```
> 위 값은 응답 **형식**을 보여 주기 위한 가짜 예시다. 실제 값은 적재한 데이터에 따라 달라진다.

## 3. 오류 처리 규칙

| 상황 | 상태코드 | 처리 위치 |
|---|:---:|---|
| 형식/범위 오류 (종목코드 형식, 음수, 고가<저가, 빈 제목 ...) | 422 | Pydantic (`schemas.py`) |
| 존재하지 않는 ID | 404 | 라우터 |
| UNIQUE / FK 위반 | 409 | `errors.py` (PostgreSQL 오류코드 변환) |
| CHECK / NOT NULL 위반 | 422 | `errors.py` |
| 그 외 DB 오류 | 500 | `errors.py` (스택트레이스는 로그에만 기록) |

## 4. 통계 API 와 SQL 의 대응
각 통계 API 가 쓰는 SQL 은 `backend/app/queries.py` 에 있고, 같은 내용을 `sql/02_queries.sql` 에서 직접 실행해 볼 수 있다.

| API | 사용한 SQL 개념 |
|---|---|
| summary | JOIN, WHERE, GROUP BY, COUNT/MIN/MAX/AVG |
| monthly | GROUP BY (날짜 가공 `to_char`), SUM |
| sectors | 3테이블 JOIN, 서브쿼리, 뷰, GROUP BY, ORDER BY |
| ranking | 뷰, 서브쿼리, ORDER BY, LIMIT |
| volatile | WHERE + GROUP BY + **HAVING** |
| financial-ratios | 계산식, `NULLIF` (0으로 나누기 방지) |

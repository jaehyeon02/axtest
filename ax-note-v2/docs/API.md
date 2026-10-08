# API 정의 (`/docs` 에서 자동 문서도 볼 수 있어요)

내 노트·관심종목·내 자료 관련 요청은 `X-Client-Id` 헤더가 필요해요 (없으면 400).

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /api/status | 데이터 출처(sample / pykrx+opendart), 최신 시세일, 표별 행 수, 최근 수집 기록 |
| GET | /api/companies?q= | 종목 목록·검색 (최신가·등락률 포함) |
| GET | /api/companies/{code} | 종목 1개 |
| GET | /api/companies/{code}/prices?days= | 일봉 |
| GET | /api/companies/{code}/events?threshold= | 급등락일 + 연결된 공시·내 자료 |
| GET | /api/companies/{code}/monthly | 월별 통계 (GROUP BY) |
| GET | /api/companies/{code}/financials | 최근 5개년 재무 (성장률 LAG) |
| GET | /api/companies/{code}/analysis | 수익률·120일선 괴리·MDD·변동성 |
| GET | /api/companies/{code}/peers | 같은 업종 비교 (RANK, 평균) |
| GET | /api/companies/{code}/documents | 공시 + 내 자료 |
| POST/PUT/DELETE | /api/documents[/{id}] | 내 자료 CRUD (남의 것은 403, 공시는 수정·삭제 불가, 링크는 http(s)만) |
| GET/POST | /api/notes | 내 노트 목록 / 만들기 |
| GET/PUT/DELETE | /api/notes/{id} | 노트 조회 / 수정 / 삭제 |
| POST | /api/notes/{id}/evidence | 근거 담기 (`doc_id` 또는 `price_id` 하나만. 중복 409) |
| PUT/DELETE | /api/notes/{id}/evidence/{eid} | 코멘트 수정 / 빼기 |
| GET | /api/watchlist | 내 관심종목 |
| PUT/DELETE | /api/watchlist/{code} | 담기(여러 번 해도 하나) / 빼기 |

# API 정의 (`/docs` 에서 자동 문서도 볼 수 있어요)

규칙·계좌·거래 관련 요청은 `X-Client-Id` 헤더가 필요해요(없으면 400). 오류는 `{"detail": "한국어 메시지"}`.
`409` = 장부 규칙 위반/이름 중복, `422` = 입력값 오류, `404` = 없거나 남의 것.

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /api/status | 데이터 출처(sample / pykrx), 최신 시세일, 표별 행 수, 최근 수집 기록 |
| GET | /api/companies?q= | 종목 목록·검색 (최신가·등락률) |
| GET | /api/companies/{code} · /prices?days= | 종목 1개 · 일봉 |
| GET | /api/companies/{code}/my-trades | 이 종목에 대한 내 거래(차트 표시용) |
| GET/POST | /api/rules | 내 규칙 목록 / 만들기 |
| GET/PUT/DELETE | /api/rules/{id} | 조회 / 수정 / 삭제 (백테스트도 같이 삭제) |
| GET | /api/rules/{id}/signals | 오늘 진입 조건이 맞은 종목 |
| GET | /api/signals | 내 모든 규칙의 오늘 신호 |
| GET/POST | /api/rules/{id}/backtests | 실행 기록 / 백테스트 실행 `{company_code, period: 6m\|1y\|all}` |
| GET/DELETE | /api/backtests/{run_id} | 결과 + 거래 목록 / 삭제 |
| GET | /api/rules/{id}/report | 백테스트 성적 vs 실제 모의투자 성적 |
| GET/POST | /api/accounts | 내 계좌 목록 / 만들기 `{name, initial_cash}` |
| GET/PUT/DELETE | /api/accounts/{id} | 현금·보유·평가손익·실현손익·장부 감사 / 이름 변경 / 삭제 |
| GET/POST | /api/accounts/{id}/trades | 거래 내역 / 주문 `{code, side, trade_date, qty, rule_id?, memo?}` |
| PUT/DELETE | /api/accounts/{id}/trades/{tid} | 메모·규칙만 수정 / 삭제(이후 거래가 깨지면 409) |

응답은 `service.py` 가 돌려주는 딕셔너리를 그대로 JSON 으로 보내요(별도 응답 스키마 없음).

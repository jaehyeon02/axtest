# 인덱스와 EXPLAIN 결과

`python scripts/explain.py` 로 직접 재현할 수 있어요. 시세 5만 행(200개 회사 × 250일), 공시 2만 행짜리 메모리 SQLite 에서 쟀어요.
(PostgreSQL 에서는 같은 쿼리 앞에 `EXPLAIN ANALYZE` 를 붙이면 돼요. 이 환경에서는 PostgreSQL 을 돌리지 못해 SQLite 로만 확인했어요.)

| 쿼리 | 인덱스 없음 | 인덱스 있음 |
|---|---|---|
| 종목 1년 시세 `SERIES` | SEARCH … `sqlite_autoindex_price_daily_1` (0.19 ms) | SEARCH … `ix_price_company_date` (0.19 ms) |
| 종목 공시 목록 `DOCUMENTS` | **SCAN document** + TEMP B-TREE 정렬 (0.67 ms) | **SEARCH … `ix_doc_company_date`** (0.15 ms) |
| 접수번호 조회(중복 방지) | **SCAN document** (0.80 ms) | **SEARCH … COVERING INDEX `ux_doc_rcept`** (≈0.00 ms) |

## 읽는 법
- `SCAN` 은 표 전체를 읽는다는 뜻, `SEARCH … USING INDEX` 는 인덱스로 필요한 곳만 찾아간다는 뜻이에요.
- `document` 는 인덱스를 만들자 풀스캔이 사라지고 약 4배 빨라졌고, 정렬용 임시 구조(TEMP B-TREE)도 없어졌어요 (인덱스가 `company_id, published_date` 순이라 이미 정렬돼 있어서).
- 접수번호(`rcept_no`)의 UNIQUE 인덱스는 속도뿐 아니라 **같은 공시를 두 번 저장하지 않게 하는 장치**(`ON CONFLICT DO NOTHING`)예요.

## 솔직한 발견
`price_daily` 는 `UNIQUE(company_id, trade_date)` 제약이 이미 같은 모양의 인덱스를 자동으로 만들기 때문에, 따로 만든 `ix_price_company_date` 는 **중복**이에요 (그래서 위 표에서 속도가 같아요). 공부용으로 일부러 남겨 두었고, 운영에서는 지워도 돼요.

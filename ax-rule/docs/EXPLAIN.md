# 인덱스와 EXPLAIN 결과

`python scripts/explain.py` 로 재현해요. 시세 6만 행, 거래 6만 행, 규칙 1,500개, 백테스트 실행 6천 건·거래 4.8만 건짜리 메모리 SQLite 에서 쟀어요.
(PostgreSQL 에서는 쿼리 앞에 `EXPLAIN ANALYZE` 를 붙이면 돼요. 이 환경에서는 PostgreSQL 을 돌리지 못해 SQLite 로만 확인했어요.)

| 쿼리 | 인덱스 없음 | 인덱스 있음 |
|---|---|---|
| 종목 시세 `SERIES` | SEARCH `sqlite_autoindex_price_daily_1` (0.14 ms) | 같음 (0.14 ms) |
| 계좌 거래 내역 `TRADES_VIEW` | **SCAN t** + TEMP B-TREE 정렬 (2.01 ms) | **SEARCH `ix_trade_account`** (0.23 ms) |
| 규칙으로 한 거래 수 | **SCAN trade** (1.95 ms) | **COVERING INDEX `ix_trade_rule`** (≈0 ms) |
| 백테스트 거래 목록 `RUN_TRADES` | **SCAN backtest_trade** (1.36 ms) | **SEARCH `ix_bt_run`** (0.01 ms) |
| 규칙 성적 합산 `BACKTEST_AGG` | SCAN t + 서브쿼리 SCAN (2.75 ms) | SEARCH `ix_bt_run` + COVERING `ix_run_rule` (0.01 ms) |

## 읽는 법
- `SCAN` 은 표 전체를 읽는다는 뜻, `SEARCH … USING INDEX` 는 인덱스로 필요한 곳만 찾아간다는 뜻이에요.
- `ix_trade_account (account_id, trade_date, trade_id)` 는 정렬 순서까지 인덱스에 들어 있어서 TEMP B-TREE 정렬이 사라졌어요.
- `ix_trade_rule`, `ix_bt_run` 은 **외래키 컬럼 인덱스**예요. 규칙을 지울 때(`ON DELETE CASCADE/SET NULL`) DB 가 자식 행을 찾는 데도 쓰여서, 없으면 규칙 하나 지울 때마다 거래·백테스트 표를 통째로 읽어요.

## 솔직한 발견
- `price_daily` 는 `UNIQUE(company_id, trade_date)` 제약이 같은 모양의 인덱스를 자동으로 만들어 줘서 따로 인덱스를 만들지 않았어요(그래서 위 표에서 차이가 없어요).
- 이 데이터 크기에서는 "없음" 도 몇 ms 라서 체감 차이는 작아요. 차이는 데이터가 커질수록 벌어지는 것이고, 여기서는 **계획이 SCAN → SEARCH 로 바뀐 것**이 핵심 증거예요.

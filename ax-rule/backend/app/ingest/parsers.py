"""외부 응답 → 우리 테이블 모양으로 바꾸는 순수 함수. 네트워크가 없어도 테스트할 수 있어요."""
import re
from datetime import date

_KO_COLS = {"open": "시가", "high": "고가", "low": "저가", "close": "종가", "volume": "거래량"}


def _to_date(v) -> date:
    if hasattr(v, "date"):
        return v.date()
    if isinstance(v, date):
        return v
    s = re.sub(r"\D", "", str(v))[:8]
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def parse_ohlcv(records: list) -> tuple:
    """pykrx 일봉(DataFrame.reset_index().to_dict('records'))을 (행 목록, 건너뛴 수)로.
    거래정지일(거래량 0)이나 high/low 가 맞지 않는 이상한 행은 DB 제약조건에 걸리기 전에 여기서 걸러요."""
    rows, skipped = [], 0
    for r in records:
        date_key = next((k for k in r if k not in _KO_COLS.values()), None)
        try:
            o, h, l, c, v = (float(r[_KO_COLS[k]]) for k in ("open", "high", "low", "close", "volume"))
            d = _to_date(r[date_key])
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        if v <= 0 or min(o, h, l, c) <= 0 or l > min(o, c) or h < max(o, c):
            skipped += 1
            continue
        rows.append({"d": d.isoformat(), "o": o, "h": h, "l": l, "c": c, "v": int(v)})
    return rows, skipped

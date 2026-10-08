"""외부 응답 → 우리 테이블 모양으로 바꾸는 순수 함수들. 네트워크가 없어도 테스트할 수 있어요."""
import re
import xml.etree.ElementTree as ET
from datetime import date

from .universe import EXCLUDE_TITLE_WORDS

DART_VIEW = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"
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


def parse_corp_codes(xml_bytes: bytes) -> dict:
    """OpenDART corpCode.xml → {종목코드: 고유번호}. 상장사(종목코드가 있는 것)만."""
    out = {}
    for el in ET.fromstring(xml_bytes).iter("list"):
        stock = (el.findtext("stock_code") or "").strip()
        if stock:
            out[stock] = (el.findtext("corp_code") or "").strip()
    return out


def parse_filings(payload: dict) -> list:
    """OpenDART list.json 의 'list' → document 행. 소유상황보고서 같은 잡음 공시는 뺍니다."""
    rows = []
    for it in payload.get("list") or []:
        title = (it.get("report_nm") or "").strip()
        if not title or any(w in title for w in EXCLUDE_TITLE_WORDS):
            continue
        rcept = (it.get("rcept_no") or "").strip()
        body = f"제출인: {(it.get('flr_nm') or '').strip()}"
        if (it.get("rm") or "").strip():
            body += f" · 비고: {it['rm'].strip()}"
        rows.append({"title": title[:200], "body": body, "d": _to_date(it["rcept_dt"]).isoformat(), "rcept": rcept, "url": DART_VIEW.format(rcept)})
    return rows


_REVENUE = ({"ifrs-full_Revenue", "ifrs_Revenue"}, ("매출액", "수익(매출액)", "영업수익", "매출"))
_OPERATING = ({"dart_OperatingIncomeLoss"}, ("영업이익", "영업이익(손실)"))
_NET = ({"ifrs-full_ProfitLoss", "ifrs_ProfitLoss"}, ("당기순이익", "당기순이익(손실)", "연결당기순이익", "연결당기순이익(손실)", "분기순이익"))


def _amount_eok(s):
    s = (s or "").replace(",", "").strip()
    if not s or s == "-":
        return None
    try:
        return round(float(s) / 1e8, 1)  # 원 → 억원
    except ValueError:
        return None


def parse_financial(payload: dict):
    """OpenDART fnlttSinglAcntAll.json → {revenue, operating_profit, net_income}(억원). 매출·영업이익을 못 찾으면 None."""
    items = [i for i in payload.get("list") or [] if i.get("sj_div") in ("IS", "CIS")]

    def pick(ids, names):
        for it in items:
            if it.get("account_id") in ids:
                v = _amount_eok(it.get("thstrm_amount"))
                if v is not None:
                    return v
        for it in items:
            if (it.get("account_nm") or "").strip() in names:
                v = _amount_eok(it.get("thstrm_amount"))
                if v is not None:
                    return v
        return None

    rev, op, net = pick(*_REVENUE), pick(*_OPERATING), pick(*_NET)
    if rev is None or op is None or rev <= 0:
        return None
    return {"revenue": rev, "operating_profit": op, "net_income": net}

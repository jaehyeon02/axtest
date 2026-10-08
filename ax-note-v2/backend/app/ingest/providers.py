"""외부 데이터 가져오기. 시세는 pykrx, 공시·재무는 OpenDART(표준 라이브러리 urllib 만 사용).

⚠️ 이 파일은 실제 네트워크가 필요해서 작성 환경에서는 실행해 보지 못했어요(파싱 로직은 parsers.py 테스트로 확인).
처음 실행할 때 응답 형식이 다르면 parsers.py 만 고치면 돼요.
"""
import io
import json
import os
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date

from . import parsers

DART = "https://opendart.fss.or.kr/api"
MIN_INTERVAL = 0.7  # OpenDART 는 분당 호출 한도가 있어서 호출 사이를 띄워요(약 85회/분)


class DartError(RuntimeError):
    pass


class LiveProvider:
    def __init__(self, api_key: str | None = None):
        self.key = api_key or os.getenv("DART_API_KEY", "")
        self._last = 0.0

    # ── OpenDART ──
    def _get(self, endpoint: str, **params) -> bytes:
        if not self.key:
            raise DartError("DART_API_KEY 가 없어요. https://opendart.fss.or.kr 에서 인증키를 발급받아 환경변수로 넣어 주세요.")
        wait = MIN_INTERVAL - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        url = f"{DART}/{endpoint}?" + urllib.parse.urlencode({"crtfc_key": self.key, **params})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=30) as res:
                    self._last = time.monotonic()
                    return res.read()
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))

    def _json(self, endpoint: str, **params) -> dict:
        data = json.loads(self._get(endpoint, **params))
        status = data.get("status")
        if status not in ("000", "013"):  # 013 = 조회된 데이터 없음(정상)
            raise DartError(f"OpenDART 오류 {status}: {data.get('message')}")
        return data

    def corp_codes(self) -> dict:
        raw = self._get("corpCode.xml")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            return parsers.parse_corp_codes(z.read(z.namelist()[0]))

    def filings(self, corp_code: str, start: date, end: date) -> list:
        rows, page = [], 1
        while True:
            data = self._json("list.json", corp_code=corp_code, bgn_de=start.strftime("%Y%m%d"), end_de=end.strftime("%Y%m%d"), page_no=page, page_count=100)
            rows += parsers.parse_filings(data)
            if page >= int(data.get("total_page") or 1):
                return rows
            page += 1

    def financial(self, corp_code: str, year: int):
        for fs_div in ("CFS", "OFS"):  # 연결 재무제표가 없으면 별도 재무제표
            data = self._json("fnlttSinglAcntAll.json", corp_code=corp_code, bsns_year=year, reprt_code="11011", fs_div=fs_div)
            got = parsers.parse_financial(data)
            if got:
                return got
        return None

    # ── pykrx ──
    def prices(self, code: str, start: date, end: date):
        from pykrx import stock  # 설치: pip install pykrx

        df = stock.get_market_ohlcv(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code)
        return parsers.parse_ohlcv(df.reset_index().to_dict("records"))

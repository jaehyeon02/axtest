"""외부 데이터 가져오기: 일봉 시세는 pykrx(KRX 데이터).

⚠️ 이 파일은 실제 네트워크가 필요해서 작성 환경에서는 실행해 보지 못했어요(파싱 로직은 parsers.py 테스트로 확인).
pykrx 반환 형식이 다르면 parsers.py 만 고치면 돼요.  설치: pip install pykrx
"""
from datetime import date

from . import parsers


class LiveProvider:
    def prices(self, code: str, start: date, end: date):
        from pykrx import stock

        df = stock.get_market_ohlcv(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code)
        return parsers.parse_ohlcv(df.reset_index().to_dict("records"))

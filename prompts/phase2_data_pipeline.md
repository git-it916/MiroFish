# Phase 2: 데이터 파이프라인 (수집 + 저장 + 제공)

CLAUDE.md를 읽고 Phase 2를 진행해줘. 에이전트가 실제 시장 데이터를 기반으로 의사결정하기 위한 데이터 인프라를 구축한다.

## 운영 방식

- **일 1회 시뮬레이션**: 매일 아침 전일 마감 데이터 수집 → 에이전트 의사결정 → 당일 종가로 체결
- **모든 데이터는 무료 소스**에서 가져옴

## 1. backend/app/services/data_collector.py (신규)

매일 데이터를 수집하여 로컬에 저장하는 파이프라인.

```python
class DataCollector:
    """매일 06:30 실행. 전일 마감 데이터를 수집하여 data/ 디렉토리에 저장"""

    def collect_all(self, date: str) -> dict:
        """전체 데이터 수집 오케스트레이션"""

    # 개별 수집기
    def collect_kr_stocks(self, date: str) -> pd.DataFrame:
        """FinanceDataReader로 KOSPI/KOSDAQ 전 종목 OHLCV 수집"""

    def collect_kr_financials(self, date: str) -> pd.DataFrame:
        """DART OpenAPI로 재무제표 수집 (PER, PBR, ROE, 영업이익 등)
        - 분기 실적 기준, 최신 공시 데이터
        - DART API키는 .env의 DART_API_KEY에서 로드"""

    def collect_global_prices(self, date: str) -> pd.DataFrame:
        """yfinance로 해외 자산 수집:
        - 지수: ^GSPC (S&P500), ^IXIC (나스닥), ^DJI (다우)
        - 선물: GC=F (금), CL=F (원유), HG=F (구리), ES=F (S&P선물), NQ=F (나스닥선물)
        - ETF: SPY, QQQ, IWM, EEM, TLT, GLD, USO 등 주요 해외 ETF
        - 국내 ETF도 yfinance 가능한 것은 여기서 수집"""

    def collect_fx_rates(self, date: str) -> pd.DataFrame:
        """yfinance로 환율 수집: KRW=X (USD/KRW), JPY=X, EUR=X, CNY=X"""

    def collect_volatility_indices(self, date: str) -> pd.DataFrame:
        """VIX (^VIX), VKOSPI는 FinanceDataReader에서 수집"""

    def collect_us_macro(self, date: str) -> pd.DataFrame:
        """FRED API로 미국 매크로:
        - DFF (연방기금금리), DGS10 (10년 국채금리), DGS2 (2년 국채금리)
        - CPIAUCSL (CPI), UNRATE (실업률), PAYEMS (비농업고용)
        - FRED API키는 .env의 FRED_API_KEY에서 로드"""

    def collect_fear_greed(self, date: str) -> dict:
        """CNN Fear & Greed Index 크롤링 또는 대체 API.
        반환: {score: 25, label: "Extreme Fear", components: {...}}"""

    def collect_kr_events(self, date: str) -> List[dict]:
        """DART에서 보호예수 해제 일정, 주요 공시 수집"""
```

### 저장 구조

```
backend/data/
├── daily/
│   └── 2026-03-29/
│       ├── kr_stocks.parquet       # 한국 주식 OHLCV
│       ├── kr_financials.parquet   # 재무제표
│       ├── global_prices.parquet   # 해외 자산 가격
│       ├── fx_rates.parquet        # 환율
│       ├── volatility.parquet      # VIX, VKOSPI
│       ├── us_macro.parquet        # 미국 매크로
│       ├── fear_greed.json         # 공포탐욕 지수
│       └── kr_events.json          # 공시/이벤트
├── historical/
│   ├── kr_stocks_60d.parquet       # 최근 60일 (이동평균 계산용)
│   └── global_prices_60d.parquet   # 최근 60일
└── universe/
    ├── kospi_list.parquet          # KOSPI 종목 리스트
    └── kosdaq_list.parquet         # KOSDAQ 종목 리스트
```

- `daily/` 하위에 날짜별 디렉토리로 저장
- `historical/` 에는 이동평균, 변동성 계산을 위한 최근 60거래일 데이터 유지
- 포맷은 parquet (빠르고 가벼움), 메타데이터는 json

## 2. backend/app/services/market_data_provider.py (신규)

수집된 데이터를 에이전트가 소비하기 쉬운 형태로 제공하는 인터페이스.

```python
class MarketDataProvider:
    """에이전트에게 시장 데이터를 제공하는 인터페이스"""

    def __init__(self, data_dir: str = "backend/data"):
        self.data_dir = data_dir

    # === 가격 데이터 ===
    def get_kr_stock_price(self, ticker: str, date: str) -> dict:
        """한국 주식 당일 OHLCV. 반환: {open, high, low, close, volume, change_pct}"""

    def get_kr_stock_history(self, ticker: str, days: int = 60) -> pd.DataFrame:
        """최근 N일 가격 히스토리 (이동평균 계산용)"""

    def get_global_price(self, ticker: str, date: str) -> dict:
        """해외 자산 당일 가격"""

    # === 기술적 지표 ===
    def get_moving_average(self, ticker: str, window: int = 10) -> float:
        """N일 이동평균. 팀장/과장의 10일선 매도 규칙에 사용"""

    def is_below_ma(self, ticker: str, window: int = 10) -> bool:
        """현재가가 N일 이동평균 아래인지. True면 매도 시그널"""

    def get_price_change_from_entry(self, ticker: str, entry_price: float) -> float:
        """진입가 대비 현재 수익률. 과장의 -10% 손절 규칙에 사용"""

    # === 펀더멘탈 ===
    def get_financials(self, ticker: str) -> dict:
        """재무제표. 반환: {per, pbr, roe, operating_profit, yoy_growth, debt_ratio, ...}"""

    def screen_stocks(self, filters: dict) -> pd.DataFrame:
        """멀티팩터 스크리닝. 리서치가 팀장에게 턴어라운드 후보 제공 시 사용
        filters 예시: {per_max: 15, pbr_max: 1.0, profit_yoy_growth_min: 0.2}"""

    # === 매크로/센티먼트 ===
    def get_macro_snapshot(self, date: str) -> dict:
        """매크로 스냅샷. 반환: {us_10y, us_2y, fed_rate, usd_krw, vix, fear_greed, ...}"""

    def get_fear_greed(self, date: str) -> dict:
        """공포탐욕 지수. 반환: {score, label, components}"""

    def get_us_kr_decoupling(self, days: int = 60) -> dict:
        """미국-한국 디커플링 이격도. 반환: {spread, zscore, is_abnormal}"""

    # === 이벤트 ===
    def get_lockup_expirations(self, date: str, days_ahead: int = 30) -> List[dict]:
        """보호예수 해제 예정 종목. 팀장용"""

    def get_upcoming_events(self, date: str, days_ahead: int = 7) -> List[dict]:
        """향후 7일 이벤트 (FOMC, CPI, 실적 발표 등). 리서치/대리용"""

    # === 유니버스 ===
    def get_universe(self, asset_type: str) -> List[str]:
        """종목 유니버스. asset_type: 'kospi', 'kosdaq', 'us_etf', 'futures'"""
```

## 3. .env 업데이트

`.env.example`에 아래 키 추가:

```env
# 시장 데이터 API 키
DART_API_KEY=your_dart_api_key
FRED_API_KEY=your_fred_api_key
# ECOS_API_KEY=your_ecos_api_key  # 선택
```

## 4. requirements.txt 업데이트

`backend/requirements.txt`에 추가:

```
yfinance>=0.2.0
finance-datareader>=0.9.0
fredapi>=0.5.0
pyarrow>=14.0.0       # parquet 지원
opendartreader>=0.2.0  # DART API 래퍼 (선택, 직접 호출도 가능)
```

## 주의사항

- 데이터 수집 실패 시 graceful하게 처리 (API 일시 장애 등). 실패한 항목은 로그 남기고 나머지는 계속 진행
- yfinance는 비공식 API라 가끔 실패함 → 재시도 로직 포함 (최대 3회)
- 한국 주식 데이터는 장이 안 열리는 날(주말/공휴일) 수집 스킵
- 모든 시간은 KST 기준

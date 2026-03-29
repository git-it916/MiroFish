# Phase 3: 포트폴리오 추적 + 리스크 엔진

CLAUDE.md를 읽고 Phase 3를 진행해줘. PM들의 매매를 추적하고, 리스크 매니저가 사용할 리스크 엔진을 구축한다.

## 1. backend/app/services/portfolio_tracker.py (신규)

```python
class PortfolioTracker:
    """펀드별 포지션/NAV 추적. 매매 체결 처리."""

    def __init__(self, market_data: MarketDataProvider, cost_model: CostModel):
        """market_data_provider와 cost_model을 주입받음"""

    # === 펀드 초기화 ===
    def init_fund(self, fund_name: str, initial_capital: float = 10_000_000_000):
        """펀드 생성. 초기 자본 100억원 기본값
        펀드 3개: Korea Value Fund (팀장), Global Macro Fund (과장), Sector ETF Fund (대리)"""

    # === 매매 체결 ===
    def execute_trade(self, fund_name: str, ticker: str, side: str,
                      quantity: int, price: float, asset_type: str) -> dict:
        """매매 체결 처리.
        - side: 'buy' 또는 'sell' (선물은 'long'/'short'/'close_long'/'close_short')
        - cost_model로 수수료/세금 자동 차감
        - 반환: {success, fill_price, cost, new_position, reason}
        - 잔고 부족/한도 초과 시 거부 + 사유 반환"""

    # === 포지션 조회 ===
    def get_holdings(self, fund_name: str) -> List[dict]:
        """현재 보유 종목 리스트.
        반환: [{ticker, quantity, avg_price, current_price, unrealized_pnl, weight_pct}]"""

    def get_position(self, fund_name: str, ticker: str) -> Optional[dict]:
        """특정 종목 포지션 조회"""

    # === NAV/성과 ===
    def get_nav(self, fund_name: str) -> dict:
        """펀드 NAV.
        반환: {nav, cash, invested, unrealized_pnl, daily_return, cumulative_return}"""

    def get_total_nav(self) -> dict:
        """전체 펀드 합산 NAV"""

    def update_prices(self, date: str):
        """장 마감 후 당일 종가로 모든 보유 종목 시가 업데이트 → NAV 재계산"""

    # === 히스토리 ===
    def get_trade_history(self, fund_name: str, days: int = 30) -> List[dict]:
        """최근 매매 내역"""

    def get_nav_history(self, fund_name: str, days: int = 30) -> List[dict]:
        """NAV 히스토리 (일별)"""

    # === 10일선/손절 체크 (PM 매도 규칙 지원) ===
    def check_stop_loss_triggers(self, fund_name: str) -> List[dict]:
        """10일선 이탈 종목 + -10% 손실 종목 리스트 반환.
        팀장: 10일선 이탈 → 매도
        과장: 10일선 이탈 OR -10% → 매도
        반환: [{ticker, trigger_type, current_price, trigger_price, loss_pct}]"""
```

### 저장 구조

```
backend/data/
├── portfolios/
│   ├── korea_value_fund.json       # 팀장 펀드 상태
│   ├── global_macro_fund.json      # 과장 펀드 상태
│   └── sector_etf_fund.json        # 대리 펀드 상태
├── trades/
│   └── 2026-03-29_trades.jsonl     # 일별 매매 기록
└── nav/
    └── nav_history.parquet         # NAV 히스토리
```

## 2. backend/app/services/cost_model.py (신규)

```python
class CostModel:
    """거래 비용 계산"""

    def calculate_cost(self, asset_type: str, side: str, notional: float) -> dict:
        """비용 계산. 반환: {commission, tax, total_cost}

        비용 구조:
        - 한국 주식 매수: 수수료 0.015%
        - 한국 주식 매도: 수수료 0.015% + 세금 0.18%
        - 국내 ETF: 수수료 0.015%, 세금 없음
        - 해외 ETF: 수수료 0.07%
        - 해외 선물: 계약당 $2.5 (ES, NQ 등), 원자재는 계약당 $1.5
        """

    def estimate_slippage(self, asset_type: str, notional: float) -> float:
        """슬리피지 추정.
        - 대형주: 0.05%
        - 중소형주: 0.10%
        - ETF: 0.03%
        - 선물: 0.02%
        """
```

## 3. backend/app/services/risk_engine.py (신규)

CLAUDE.md의 리스크 매니저 역할을 정량적으로 구현.

```python
class RiskEngine:
    """리스크 매니저 에이전트가 사용하는 리스크 계산 엔진"""

    def __init__(self, portfolio_tracker: PortfolioTracker, market_data: MarketDataProvider):
        pass

    # === VaR ===
    def calculate_var(self, fund_name: str, confidence: float = 0.95) -> dict:
        """Historical Simulation VaR.
        반환: {var_95, var_99, is_over_limit}
        한도: 펀드 NAV의 2%"""

    # === MDD ===
    def calculate_mdd(self, fund_name: str) -> dict:
        """최대 드로다운.
        반환: {current_dd, max_dd, peak_date, alert_level}
        alert_level: 'normal' / 'warning'(-5%) / 'critical'(-10%) / 'emergency'(-15%)"""

    # === 집중도 ===
    def check_concentration(self, fund_name: str) -> dict:
        """포지션 집중도 체크.
        반환: {stock_max_weight, sector_max_weight, country_max_weight, violations: [...]}
        한도: 종목 10%, 섹터 30%, 국가 70%"""

    # === 공포탐욕 ===
    def get_sentiment_grade(self, date: str) -> dict:
        """시장 센티먼트 등급.
        VIX, VKOSPI, Fear&Greed 종합.
        반환: {grade, score, components, recommendation}
        grade: 'extreme_fear' / 'fear' / 'neutral' / 'greed' / 'extreme_greed'
        recommendation: PM들에게 전달할 포지션 가이드"""

    # === 디커플링 ===
    def check_us_kr_decoupling(self, date: str) -> dict:
        """S&P500 vs KOSPI 이격도.
        반환: {spread, zscore, is_abnormal, direction, message}
        is_abnormal: |zscore| > 2"""

    # === 상관관계 ===
    def check_portfolio_correlation(self) -> dict:
        """전체 보유 종목 간 평균 상관.
        반환: {avg_correlation, is_concentrated, warning_message}
        경고: avg_correlation > 0.7"""

    # === 종합 리스크 대시보드 ===
    def daily_risk_report(self, date: str) -> dict:
        """일일 종합 리스크 리포트.
        모든 펀드의 VaR, MDD, 집중도, 센티먼트, 디커플링을 한번에 산출.
        반환: {funds: {fund_name: {...}}, market: {sentiment, decoupling}, alerts: [...]}"""

    # === 매매 전 한도 체크 ===
    def pre_trade_check(self, fund_name: str, ticker: str, side: str,
                        quantity: int, price: float) -> dict:
        """매매 전 한도 검증. execute_trade 전에 호출.
        반환: {approved: bool, violations: [...], warnings: [...]}"""
```

## 주의사항

- PortfolioTracker는 상태를 JSON 파일로 persist (서버 재시작 후 복원 가능)
- RiskEngine은 stateless — 매번 PortfolioTracker와 MarketDataProvider에서 데이터를 읽어 계산
- 모든 금액은 원화(KRW) 기준. 해외 자산은 환율 반영하여 원화 환산
- Phase 2의 MarketDataProvider를 import하여 사용

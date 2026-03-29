# Phase 1: 뼈대 교체 (config, profile, state)

CLAUDE.md를 읽고 프로젝트 배경을 파악한 뒤 아래 3개 파일을 수정해줘.

## 1. backend/app/config.py

- `OASIS_TWITTER_ACTIONS`, `OASIS_REDDIT_ACTIONS` 리스트를 삭제
- 새로운 `MARKET_ACTIONS` 리스트로 교체:

```python
MARKET_ACTIONS = [
    'PUBLISH_ANALYSIS',    # 리서치: 분석 리포트/브리핑 발행
    'BUY',                 # PM: 매수 주문
    'SELL',                # PM: 매도 주문
    'REBALANCE',           # PM: 포트폴리오 리밸런싱
    'HEDGE',               # 과장: 롱숏 헤지 포지션 구축
    'RISK_CHECK',          # 리스크: 한도/VaR/MDD 점검
    'RISK_ALERT',          # 리스크: 경고 발행 (센티먼트, 디커플링, 한도 위반)
    'UPDATE_VIEW',         # CIO: 하우스 뷰 업데이트
    'ENDORSE_IDEA',        # 다른 에이전트 아이디어에 동의
    'CHALLENGE_IDEA',      # 다른 에이전트 아이디어에 반대
    'MORNING_BRIEF',       # 리서치: 모닝 브리핑 발행
    'DO_NOTHING',          # 관망
]
```

- Twitter/Reddit 관련 설정 변수가 있으면 전부 금융 시장용으로 교체
- 데이터 소스 설정 추가:

```python
DATA_SOURCES = {
    'kr_stock': 'FinanceDataReader',
    'kr_financial': 'DART',
    'global_price': 'yfinance',
    'us_macro': 'FRED',
    'kr_macro': 'ECOS',
    'fear_greed': 'CNN',
}
```

## 2. backend/app/services/oasis_profile_generator.py

- `OasisAgentProfile` 클래스를 `FundManagerProfile`로 변경
- 소셜 필드 삭제: `karma`, `follower_count`, `friend_count`, `statuses_count`
- 금융 필드 추가:

```python
@dataclass
class FundManagerProfile:
    user_id: int
    name: str                          # "팀장", "과장", "대리" 등
    role: str                          # "pm", "researcher", "risk", "cio"
    bio: str                           # 배경 요약
    persona: str                       # LLM 생성 상세 페르소나

    # PM 전용
    fund_name: Optional[str] = None    # "Korea Value Fund" 등
    investment_style: Optional[str] = None  # "value_turnaround", "long_short_macro", "sector_rotation"
    risk_tolerance: float = 0.5        # 0.0(보수) ~ 1.0(공격)
    asset_universe: List[str] = field(default_factory=list)  # ["KR_STOCK", "KR_ETF", "US_ETF", "FUTURES"]
    max_position_pct: float = 0.10     # 종목당 최대 비중
    stop_loss_rule: Optional[str] = None  # "10일선 이탈", "-10% 기계적 손절" 등
    leverage_limit: float = 1.0        # 과장은 2.0
    rebalance_freq: str = "daily"

    # 공통
    conviction_threshold: float = 0.6  # 확신도 임계값
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
```

- `to_twitter_format()`, `to_reddit_format()` 삭제 → `to_agent_format()` 하나로 통합
- 프로필 생성 LLM 프롬프트를 금융 팀 맥락으로 수정. CLAUDE.md의 Team Structure를 참고하여 각 에이전트의 배경/전략/성격을 프롬프트에 반영

## 3. backend/app/services/simulation_runner.py

- `SimulationRunState`에서 `twitter_*`/`reddit_*` 필드 전부 제거
- 금융 시뮬레이션용으로 교체:

```python
@dataclass
class SimulationRunState:
    status: str = "idle"
    current_round: int = 0           # 시뮬레이션 일차
    market_date: str = ""            # "2026-03-29"
    market_phase: str = "pre_market" # pre_market → trading → post_market → closed
    total_nav: float = 0.0           # 전체 펀드 합산 NAV
    actions_count: int = 0
    trades_executed: int = 0
    risk_alerts: int = 0             # 리스크 경고 횟수
    recent_actions: List[AgentAction] = field(default_factory=list)
```

- `AgentAction`의 `platform` 필드를 `market_phase`로 변경 (pre_market/trading/post_market)
- `RoundSummary`에 `simulated_hour` 대신 `market_phase`, `nav_change` 추가
- `add_action()`에서 twitter/reddit 분기 제거, 단일 카운터로 통합

## 주의사항

- 기존 import와 다른 서비스와의 연결은 깨지지 않게 주의
- 아직 연결되는 다른 파일(simulation_manager, run_parallel_simulation 등)은 이후 Phase에서 수정할 예정
- 타입 호환만 유지하면 됨. 예: 다른 파일에서 `AgentAction`을 import하고 있으면 클래스명은 유지하되 필드만 변경

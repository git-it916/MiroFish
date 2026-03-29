# Phase 4: 시뮬레이션 로직 (에이전트 의사결정 + 상호작용)

CLAUDE.md를 읽고 Phase 4를 진행해줘. 이 Phase가 핵심이다. 에이전트들이 실제 시장 데이터를 보고 의사결정을 내리는 로직을 구현한다.

## 1. backend/scripts/run_market_simulation.py (신규, 기존 run_parallel/twitter/reddit 대체)

하루 시뮬레이션의 전체 오케스트레이션.

```python
class MarketSimulation:
    """하루 시뮬레이션 실행기"""

    def __init__(self, date: str, data_collector, market_data, portfolio_tracker, risk_engine):
        """Phase 2, 3에서 만든 모듈들을 주입"""

    def run_day(self, date: str):
        """하루 전체 시뮬레이션"""
        self.collect_data(date)           # 06:30 데이터 수집
        self.run_pre_market(date)         # 07:00-08:59
        self.run_trading_session(date)    # 09:00-15:29
        self.run_post_market(date)        # 15:30-17:00

    def run_pre_market(self, date: str):
        """장 전 세션
        1. 리서치 → 모닝 브리핑 생성 (MORNING_BRIEF)
           - 전일 미국장 요약, 매크로 스냅샷, 이벤트 캘린더
           - 팀장용: 턴어라운드 후보 스크리닝 결과, 보호예수 해제 종목
           - 과장용: 선물 야간 동향, VIX 변화, 주요 매크로 이벤트
           - 대리용: 섹터별 글로벌 흐름, ETF 자금 유출입
        2. 리스크 → 리스크 대시보드 업데이트 (RISK_CHECK)
           - 전일 종가 기준 VaR, MDD, 센티먼트 등급, 디커플링 이격도
           - 한도 위반 종목 리스트
           - 10일선 이탈 / -10% 손절 대상 종목 알림
        3. 모닝미팅 → 전원 참여 (각자 PUBLISH_ANALYSIS 또는 UPDATE_VIEW)
           - CIO가 하우스 뷰 요약
           - PM들이 오늘의 매매 계획 공유
           - 의견 충돌 시 ENDORSE_IDEA / CHALLENGE_IDEA"""

    def run_trading_session(self, date: str):
        """장중 세션 — PM들의 매매 의사결정

        각 PM에게 아래 정보를 LLM 프롬프트로 제공:
        - 모닝 브리핑 내용
        - 리스크 대시보드 (한도 위반/경고 포함)
        - 현재 보유 포지션 + 손익
        - 10일선 이탈 / 손절 대상 종목 리스트
        - 다른 PM들의 모닝미팅 발언

        PM별 의사결정 루프:
        1. 팀장:
           - 10일선 이탈 종목 → 기계적 매도 (SELL)
           - 리서치 스크리닝 결과에서 관심 종목 → 리서치 확인 후 매수 (BUY)
           - 보호예수 해제 + 상승 추세 종목 → 매수 (BUY)

        2. 과장:
           - 10일선 이탈 OR -10% 종목 → 기계적 매도 (SELL)
           - 매크로 방향성 판단 → 선물 롱/숏 (BUY/SELL/HEDGE)
           - 기존 롱 포지션 하락 시 → 소규모 숏 헤지 (HEDGE)
           - 상황 급변 → 포지션 전면 청산 또는 반대 전환

        3. 대리:
           - 유망 섹터 ETF 매수 (BUY)
           - 섹터 대표주 1~2개 병행 매수 (BUY)
           - 뉴스/이벤트 기반 선제 매매 (BUY/SELL)

        모든 매매 전:
        - risk_engine.pre_trade_check() 호출
        - 거부되면 매매 취소 + RISK_ALERT 로그

        매매 후:
        - portfolio_tracker.execute_trade() 호출
        - 체결 결과 기록"""

    def run_post_market(self, date: str):
        """장 후 세션
        1. portfolio_tracker.update_prices(date) → 당일 종가로 NAV 확정
        2. 리스크 → 장 마감 기준 최종 리스크 리포트 (RISK_CHECK)
        3. CIO → 일일 종합 리포트 (UPDATE_VIEW)
           - 각 펀드 성과 요약
           - 잘한 판단 / 아쉬운 판단
           - 내일 주시 포인트"""
```

## 2. 에이전트 LLM 프롬프트 설계

각 에이전트의 의사결정은 LLM 호출로 이루어진다. 프롬프트 구조:

```
[시스템 프롬프트]
너는 {name}이다. {CLAUDE.md의 해당 에이전트 전체 설명}

[유저 프롬프트]
## 오늘 날짜: {date}

## 모닝 브리핑
{리서치가 생성한 브리핑 내용}

## 리스크 대시보드
{리스크 매니저가 생성한 리스크 현황}

## 현재 포트폴리오
{보유 종목, 수량, 평균가, 현재가, 손익률}

## 매도 시그널
{10일선 이탈 종목, -10% 손절 대상}

## 모닝미팅 발언록
{다른 에이전트들의 오늘 의견}

## 지시사항
위 정보를 바탕으로 오늘의 매매 의사결정을 JSON으로 반환해라.
반환 형식:
{
  "reasoning": "오늘의 판단 근거 (2-3문장)",
  "actions": [
    {"type": "SELL", "ticker": "005930", "quantity": 500, "reason": "10일선 이탈"},
    {"type": "BUY", "ticker": "373220", "quantity": 200, "reason": "LG에너지솔루션 턴어라운드 기대"},
  ]
}
매매할 필요가 없으면 actions를 빈 배열로 반환.
```

## 3. 모닝미팅 상호작용 구현

```python
class MorningMeeting:
    """에이전트 간 모닝미팅 시뮬레이션"""

    def run(self, date: str, agents: List, context: dict) -> dict:
        """
        라운드 1: 리서치 브리핑 → 리스크 현황 발표
        라운드 2: 각 PM이 오늘의 뷰/계획 발표
        라운드 3: 상호 의견 교환 (ENDORSE/CHALLENGE)
        라운드 4: CIO가 하우스 뷰 정리

        각 라운드의 발언은 다음 라운드의 컨텍스트로 전달됨.
        반환: {briefing, risk_dashboard, pm_views, interactions, house_view}
        """
```

## 4. backend/app/services/simulation_manager.py 수정

- twitter/reddit 시뮬레이션 시작/중지 로직 → `MarketSimulation` 호출로 교체
- dual-platform 구조 → single-market 구조로 단순화
- 상태 관리: 시뮬레이션 진행 날짜, 현재 phase (pre_market/trading/post_market)

## 5. backend/scripts/ 정리

- `run_twitter_simulation.py` → 삭제
- `run_reddit_simulation.py` → 삭제
- `run_parallel_simulation.py` → 삭제 (또는 `run_market_simulation.py`로 교체)
- 새로 추가: `run_market_simulation.py` (MarketSimulation을 실행하는 엔트리포인트)

## 주의사항

- LLM 프롬프트에 CLAUDE.md의 에이전트 설명을 그대로 시스템 프롬프트로 사용
- 에이전트 의사결정 JSON은 파싱 실패 시 재시도 (최대 2회), 그래도 실패하면 DO_NOTHING
- 매매 순서: 리서치 → 리스크 → PM들 (동시) → CIO. 리서치/리스크가 먼저 정보를 만들어야 PM이 참고 가능
- 각 에이전트의 LLM 호출은 config.py의 LLM 설정을 사용 (기존 MiroFish와 동일)

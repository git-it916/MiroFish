# Phase 5: 메모리 + 리포트

CLAUDE.md를 읽고 Phase 5를 진행해줘.

## 1. backend/app/services/zep_graph_memory_updater.py 수정

에이전트의 매매 행동을 Zep 메모리에 자연어로 기록. 이 기록이 쌓이면서 에이전트가 과거 판단을 기억하고 참고할 수 있게 된다.

### to_episode_text()의 action_descriptions를 전면 교체:

```python
action_descriptions = {
    "BUY": "{agent_name}이(가) {ticker}({company_name}) {quantity}주를 {price:,}원에 매수했습니다. 근거: {reason}",
    "SELL": "{agent_name}이(가) {ticker}({company_name}) {quantity}주를 {price:,}원에 매도했습니다. 트리거: {trigger}. 실현손익: {realized_pnl:+,}원",
    "HEDGE": "{agent_name}이(가) {ticker} {direction} 헤지 포지션을 구축했습니다. 수량: {quantity}계약. 근거: {reason}",
    "REBALANCE": "{agent_name}이(가) {fund_name} 포트폴리오를 리밸런싱했습니다. 변경: {changes_summary}",
    "PUBLISH_ANALYSIS": "{agent_name}이(가) 분석 리포트를 발행했습니다. 주제: {subject}. 요약: {summary}",
    "MORNING_BRIEF": "{agent_name}이(가) 모닝 브리핑을 발행했습니다. 핵심: {key_points}",
    "RISK_CHECK": "{agent_name}이(가) 리스크 점검을 수행했습니다. {fund_name} VaR: {var:.1%}, MDD: {mdd:.1%}, 센티먼트: {sentiment}",
    "RISK_ALERT": "{agent_name}이(가) 리스크 경고를 발행했습니다. 유형: {alert_type}. 내용: {message}",
    "UPDATE_VIEW": "{agent_name}이(가) 하우스 뷰를 업데이트했습니다: {view_summary}",
    "ENDORSE_IDEA": "{agent_name}이(가) {target_agent}의 의견에 동의했습니다. 원래 의견: {original_idea}. 동의 근거: {reason}",
    "CHALLENGE_IDEA": "{agent_name}이(가) {target_agent}의 의견에 반대했습니다. 원래 의견: {original_idea}. 반대 근거: {reason}",
    "DO_NOTHING": "{agent_name}이(가) 관망을 선택했습니다. 사유: {reason}",
}
```

### 기존 `_describe_create_post`, `_describe_like_post` 등 소셜 메서드 전부 삭제.

### Zep 메모리 활용 방식:
- 에이전트가 과거 매매 기록을 참조하여 일관된 판단 가능
  - 예: 팀장이 과거에 "A기업 턴어라운드 기대"로 매수했다면, 실적 발표 후 그 판단이 맞았는지 리뷰
- 에이전트 간 상호작용 기록도 저장
  - 예: 과장이 팀장의 한국 강세 뷰에 반대했던 기록 → 이후 시장이 어떻게 됐는지 맥락 제공

## 2. backend/app/services/report_agent.py 수정

리포트 생성을 금융 리포트 형식으로 변경.

### 리포트 구조 (LLM 프롬프트에 포함):

```markdown
# 일일 운용 리포트 — {date}

## 1. 시장 요약
- 전일 미국장: S&P500 {sp500_change}, 나스닥 {nasdaq_change}
- 금일 한국장: KOSPI {kospi_change}, KOSDAQ {kosdaq_change}
- 주요 이벤트: {events}
- 센티먼트: {fear_greed_label} ({fear_greed_score}/100)

## 2. 펀드별 성과
### Korea Value Fund (팀장)
- NAV: {nav:,}원 ({daily_return:+.2%})
- 주요 매매: {trades}
- 매매 근거: {reasoning}

### Global Macro Fund (과장)
- NAV: {nav:,}원 ({daily_return:+.2%})
- 주요 매매: {trades}
- 매매 근거: {reasoning}

### Sector ETF Fund (대리)
- NAV: {nav:,}원 ({daily_return:+.2%})
- 주요 매매: {trades}
- 매매 근거: {reasoning}

## 3. 팀 전체 성과
- 합산 AUM: {total_nav:,}원
- 일일 수익률: {team_return:+.2%}
- 누적 수익률: {cumulative_return:+.2%}

## 4. 리스크 현황
- 센티먼트 등급: {sentiment_grade}
- US-KR 이격도: {decoupling_zscore:.1f}σ
- 펀드별 VaR: {var_table}
- MDD: {mdd_table}
- 한도 위반: {violations}

## 5. PM 투자 판단 요약
{각 PM의 reasoning을 요약}

## 6. CIO 코멘트
{CIO의 하우스 뷰, 잘한 점, 아쉬운 점, 내일 주시 포인트}
```

### 기존 여론분석 관련 프롬프트/템플릿 전부 제거.

## 3. backend/app/services/graph_builder.py + ontology_generator.py 수정

### 온톨로지 변경:
- 기존 엔티티 타입: 인물, 조직, 사건, 장소
- 새 엔티티 타입:

```python
ENTITY_TYPES = [
    'FUND_MANAGER',      # 팀장, 과장, 대리, 리서치, 리스크, CIO
    'FUND',              # Korea Value Fund, Global Macro Fund, Sector ETF Fund
    'STOCK',             # 개별 주식
    'ETF',               # 국내/해외 ETF
    'FUTURES',           # 선물
    'SECTOR',            # 반도체, 자동차, 바이오 등
    'MACRO_INDICATOR',   # 금리, CPI, 환율 등
    'EVENT',             # FOMC, 실적 발표, 보호예수 해제 등
]

RELATION_TYPES = [
    'MANAGES',           # PM → Fund
    'HOLDS',             # Fund → Stock/ETF/Futures
    'BELONGS_TO',        # Stock → Sector
    'IMPACTS',           # Event → Stock/Sector/Macro
    'CORRELATED_WITH',   # Stock ↔ Stock, Sector ↔ Sector
    'ANALYZED_BY',       # Stock → Researcher
    'ENDORSED_BY',       # Idea → PM (동의)
    'CHALLENGED_BY',     # Idea → PM (반대)
]
```

### 그래프 초기화:
- 시드 문서 대신 CLAUDE.md의 Team Structure를 파싱하여 에이전트/펀드 노드 생성
- 시뮬레이션 실행 중 매매/분석 행위가 그래프에 자동 반영

## 주의사항

- report_agent.py의 LLM 호출 구조(OpenAI 호환 API)는 유지, 프롬프트만 교체
- Zep 메모리 구조(episode, fact)는 기존 방식 유지, 내용만 금융 맥락으로 변경
- 리포트는 마크다운으로 생성 → 프론트엔드에서 렌더링 (기존 방식 동일)

# Phase 6: 프론트엔드 UI

CLAUDE.md를 읽고 Phase 6를 진행해줘. 텍스트/라벨 변경 위주로 진행하고, 큰 레이아웃 변경은 하지 마. 기존 UI 구조를 최대한 살려.

## 1. frontend/src/components/Step1GraphBuild.vue

- 문서 업로드 설명: "뉴스/기사 업로드" → "팀 구성 파일 업로드 또는 시뮬레이션 시작"
- 실제로는 CLAUDE.md의 Team Structure가 자동으로 로드되므로, 사용자가 별도 시드 문서를 올릴 필요 없음
- "그래프 구축" 버튼 → "팀 초기화" 버튼으로 변경

## 2. frontend/src/components/Step2EnvSetup.vue

- 플랫폼 선택 UI (Twitter/Reddit 체크박스) → 시장 환경 설정 UI로 교체:
  - **시뮬레이션 날짜**: date picker (기본값: 오늘)
  - **초기 자본**: 펀드별 입력 (기본 100억원씩)
  - **변동성 레짐**: 드롭다운 (Low / Normal / High / Crisis) — 이건 실제로는 데이터에서 자동 판단되지만, 수동 오버라이드 옵션
  - **활성 에이전트**: 체크박스 (팀장, 과장, 대리, 리서치, 리스크, CIO — 기본 전부 선택)
- 에이전트 프로필 미리보기: 각 에이전트 카드에 이름, 역할, 투자 스타일, 유니버스 표시

## 3. frontend/src/components/Step3Simulation.vue

이 파일이 가장 많이 바뀜.

### 플랫폼 라벨 변경
- "Info Plaza" (Twitter) → "Trading Floor" (매매 실행)
- "Topic Community" (Reddit) → "Research Hub" (리서치/미팅)
- 또는 단일 패널로 통합: "Market Simulation"

### 액션 라벨 변경
- POST → ANALYSIS / MORNING_BRIEF
- LIKE → ENDORSE_IDEA
- DISLIKE → CHALLENGE_IDEA
- REPOST → (삭제)
- FOLLOW → (삭제)
- 새로 추가: BUY, SELL, HEDGE, REBALANCE, RISK_CHECK, RISK_ALERT

### 에이전트 표시
- username → "팀장", "과장", "대리" 등 역할명으로 표시
- 각 에이전트 옆에 역할 뱃지 (PM / Research / Risk / CIO)
- 색상 코드: PM들은 파랑 계열, 리서치는 초록, 리스크는 빨강, CIO는 금색

### 액션 로그 표시
- 기존: "UserA가 게시물을 작성했습니다: 내용..."
- 변경: "팀장이 005930(삼성전자) 500주를 매수했습니다. 근거: PER 저평가 + 턴어라운드 기대"
- 매매 액션은 금액/수량 포함하여 표시
- RISK_ALERT는 빨간색 하이라이트

### 라운드 표시
- 기존: "Round 1 (Hour 8-9)"
- 변경: "장 전 (07:00-09:00)" → "장 중 (09:00-15:30)" → "장 후 (15:30-17:00)"

### 실시간 포트폴리오 패널 (신규, 사이드바 또는 하단)
- 각 펀드의 현재 NAV, 일일 수익률
- 간단한 보유 종목 리스트 (상위 5개)
- 팀 합산 AUM

## 4. frontend/src/components/Step4Report.vue

- 리포트 뷰어는 기존 마크다운 렌더링 유지
- 리포트 제목: "예측 보고서" → "일일 운용 리포트"
- 가능하면 펀드별 수익률을 간단한 바 차트로 표시 (Chart.js 등 이미 프로젝트에 있으면 활용, 없으면 텍스트로도 충분)

## 5. frontend/src/components/Step5Interaction.vue

- 에이전트 대화 인터페이스는 거의 그대로 유지 (이 기능 자체가 유용)
- 에이전트 선택 드롭다운에서 이름 옆에 역할 표시: "팀장 (국내주식 PM)" 등
- 대화 시 에이전트가 자기 펀드 현황을 참조할 수 있도록 컨텍스트 전달

## 6. frontend/src/api/

- `simulation.js`: API 호출 파라미터에서 twitter/reddit 관련 필드 → market 관련 필드로 변경
- `graph.js`: 그래프 데이터 구조 변경 반영 (엔티티 타입이 바뀌었으므로)
- `report.js`: 리포트 API 엔드포인트는 동일할 것이므로 최소 변경

## 7. frontend/src/components/GraphPanel.vue

- 그래프 시각화에서 노드 타입에 따른 색상/아이콘 변경:
  - FUND_MANAGER → 사람 아이콘
  - FUND → 폴더/지갑 아이콘
  - STOCK → 주식 차트 아이콘
  - SECTOR → 카테고리 아이콘
  - 등등

## 주의사항

- 대규모 레이아웃 변경 금지. 기존 5단계 스텝 구조 유지
- CSS 큰 변경 없이 텍스트/라벨/색상 위주로 수정
- 새 컴포넌트 추가보다는 기존 컴포넌트 내용 교체 우선
- 한국어 UI (기존 MiroFish가 중국어/영어 혼용이면, 한국어로 통일)

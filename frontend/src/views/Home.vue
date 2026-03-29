<template>
  <div class="home-container">
    <!-- 상단 내비게이션 바 -->
    <nav class="navbar">
      <div class="nav-brand">MIROFISH</div>
      <div class="nav-links">
        <a href="https://github.com/666ghj/MiroFish" target="_blank" class="github-link">
          GitHub 홈페이지 방문 <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <div class="main-content">
      <!-- 상단: Hero 영역 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">간결하고 범용적인 집단지능 엔진</span>
            <span class="version-text">/ v0.1-프리뷰</span>
          </div>
          
          <h1 class="main-title">
            어떤 보고서든 업로드<br>
            <span class="gradient-text">미래를 즉시 시뮬레이션</span>
          </h1>
          
          <div class="hero-desc">
            <p>
              단 한 단락의 텍스트만으로도, <span class=”highlight-bold”>MiroFish</span> 그 안의 현실 시드를 기반으로 최대 <span class=”highlight-orange”>백만 Agent</span>로 구성된 평행세계를 자동 생성합니다. 신의 시점으로 변수를 주입하여, 복잡한 집단 상호작용 속에서 동적 환경의 <span class=”highlight-code”>”국소 최적해”</span>
            </p>
            <p class="slogan-text">
              미래를 Agent 군집에서 미리 시뮬레이션하고, 결정을 수백 번의 검증 후 승리하게 하다<span class="blinking-cursor">_</span>
            </p>
          </div>
           
          <div class="decoration-square"></div>
        </div>
        
        <div class="hero-right">
          <!-- Logo 영역 -->
          <div class="logo-container">
            <img src="../assets/logo/MiroFish_logo_left.jpeg" alt="MiroFish Logo" class="hero-logo" />
          </div>
          
          <button class="scroll-down-btn" @click="scrollToBottom">
            ↓
          </button>
        </div>
      </section>

      <!-- 하단: 이중 컬럼 레이아웃 -->
      <section class="dashboard-section">
        <!-- 왼쪽 컬럼: 상태 및 단계 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> 시스템 상태
          </div>
          
          <h2 class="section-title">준비 완료</h2>
          <p class="section-desc">
            예측 엔진 대기 중, 비정형 데이터를 업로드하여 시뮬레이션 시퀀스를 초기화하세요
          </p>
          
          <!-- 데이터 지표 카드 -->
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">저비용</div>
              <div class="metric-label">일반 시뮬레이션 평균 5$/회</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">고가용성</div>
              <div class="metric-label">최대 백만 Agent 시뮬레이션</div>
            </div>
          </div>

          <!-- 프로젝트 시뮬레이션 단계 소개 -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> 워크플로우 시퀀스
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">그래프 구축</div>
                  <div class="step-desc">현실 시드 추출 & 개체 및 집단 기억 주입 & GraphRAG 구축</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">환경 구성</div>
                  <div class="step-desc">엔티티 관계 추출 & 페르소나 생성 & 환경 설정 Agent 시뮬레이션 파라미터 주입</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">시뮬레이션 시작</div>
                  <div class="step-desc">듀얼 플랫폼 병렬 시뮬레이션 & 예측 요구사항 자동 분석 & 시계열 기억 동적 업데이트</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">보고서 생성</div>
                  <div class="step-desc">ReportAgent의 풍부한 도구로 시뮬레이션 후 환경과 심층 상호작용</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">심층 상호작용</div>
                  <div class="step-desc">시뮬레이션 세계의 누구와도 대화 & ReportAgent와 대화</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 오른쪽 컬럼: 인터랙티브 콘솔 -->
        <div class="right-panel">
          <div class="console-box">
            <!-- 업로드 영역 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">01 / 현실 시드</span>
                <span class="console-meta">지원 형식: PDF, MD, TXT</span>
              </div>
              
              <div 
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">파일을 드래그하여 업로드</div>
                  <div class="upload-hint">또는 클릭하여 파일 탐색</div>
                </div>
                
                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 구분선 -->
            <div class="console-divider">
              <span>입력 파라미터</span>
            </div>

            <!-- 입력 영역 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 02 / 시뮬레이션 프롬프트</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  placeholder="// 자연어로 시뮬레이션 또는 예측 요구사항을 입력하세요 (예: 특정 사건이 발생하면 어떤 여론 동향이 생길까요?)"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">엔진: MiroFish-V1.0</div>
              </div>
            </div>

            <!-- 시작 버튼 -->
            <div class="console-section btn-section">
              <button 
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">엔진 시작</span>
                <span v-else>초기화 중...</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 히스토리 프로젝트 데이터베이스 -->
      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'

const router = useRouter()

// 폼 데이터
const formData = ref({
  simulationRequirement: ''
})

// 파일 목록
const files = ref([])

// 상태
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// 파일 입력 참조
const fileInput = ref(null)

// 계산 속성: 제출 가능 여부
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

// 파일 선택 트리거
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// 파일 선택 처리
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// 드래그 관련 처리
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// 파일 추가
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// 파일 제거
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// 하단으로 스크롤
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// 시뮬레이션 시작 - 즉시 이동, API 호출은 Process 페이지에서 수행
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  
  // 업로드 대기 데이터 저장
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)
    
    // Process 페이지로 즉시 이동 (특수 식별자로 새 프로젝트 표시)
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
/* 전역 변수 및 리셋 */
:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  /* 
    Space Grotesk를 주요 제목 폰트로, JetBrains Mono를 코드/태그 폰트로 사용
    index.html에서 이 Google Fonts를 불러왔는지 확인하세요
  */
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans KR', system-ui, sans-serif;
  --font-ko: 'Noto Sans KR', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

/* 상단 내비게이션 */
.navbar {
  height: 60px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
}

.nav-links {
  display: flex;
  align-items: center;
}

.github-link {
  color: var(--white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.2s;
}

.github-link:hover {
  opacity: 0.8;
}

.arrow {
  font-family: sans-serif;
}

/* 메인 콘텐츠 영역 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 40px;
}

/* Hero 영역 */
.hero-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 80px;
  position: relative;
}

.hero-left {
  flex: 1;
  padding-right: 60px;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.orange-tag {
  background: var(--orange);
  color: var(--white);
  padding: 4px 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  font-size: 0.75rem;
}

.version-text {
  color: #999;
  font-weight: 500;
  letter-spacing: 0;
}

.main-title {
  font-size: 3.8rem;
  line-height: 1.25;
  font-weight: 500;
  margin: 0 0 40px 0;
  letter-spacing: -0.02em;
  color: var(--black);
  word-break: keep-all;
}

.gradient-text {
  background: linear-gradient(90deg, #000000 0%, #444444 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--gray-text);
  max-width: 640px;
  margin-bottom: 50px;
  font-weight: 400;
  text-align: justify;
  word-break: keep-all;
}

.hero-desc p {
  margin-bottom: 1.5rem;
}

.highlight-bold {
  color: var(--black);
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 700;
  font-family: var(--font-mono);
}

.highlight-code {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--black);
  font-weight: 600;
}

.slogan-text {
  font-size: 1.1rem;
  font-weight: 520;
  color: var(--black);
  letter-spacing: 0;
  border-left: 3px solid var(--orange);
  padding-left: 15px;
  margin-top: 20px;
  word-break: keep-all;
}

.blinking-cursor {
  color: var(--orange);
  animation: blink 1s step-end infinite;
  font-weight: 700;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: 16px;
  height: 16px;
  background: var(--orange);
}

.hero-right {
  flex: 0.8;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
}

.logo-container {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  padding-right: 40px;
}

.hero-logo {
  max-width: 500px; /* 로고 크기 조정 */
  width: 100%;
}

.scroll-down-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--orange);
  font-size: 1.2rem;
  transition: all 0.2s;
}

.scroll-down-btn:hover {
  border-color: var(--orange);
}

/* Dashboard 이중 컬럼 레이아웃 */
.dashboard-section {
  display: flex;
  gap: 60px;
  border-top: 1px solid var(--border);
  padding-top: 60px;
  align-items: flex-start;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* 왼쪽 패널 */
.left-panel {
  flex: 0.8;
}

.panel-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.status-dot {
  color: var(--orange);
  font-size: 0.8rem;
}

.section-title {
  font-size: 2rem;
  font-weight: 520;
  margin: 0 0 15px 0;
}

.section-desc {
  color: var(--gray-text);
  margin-bottom: 25px;
  line-height: 1.6;
  word-break: keep-all;
}

.metrics-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.metric-card {
  border: 1px solid var(--border);
  padding: 20px 30px;
  min-width: 150px;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1.8rem;
  font-weight: 520;
  margin-bottom: 5px;
}

.metric-label {
  font-size: 0.85rem;
  color: #999;
}

/* 프로젝트 시뮬레이션 단계 소개 */
.steps-container {
  border: 1px solid var(--border);
  padding: 30px;
  position: relative;
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  margin-bottom: 25px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diamond-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--black);
  opacity: 0.3;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 520;
  font-size: 1rem;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 0.85rem;
  color: var(--gray-text);
  word-break: keep-all;
}

/* 오른쪽 인터랙티브 콘솔 */
.right-panel {
  flex: 1.2;
}

.console-box {
  border: 1px solid #CCC; /* 외부 실선 */
  padding: 8px; /* 내부 여백으로 이중 테두리 효과 */
}

.console-section {
  padding: 20px;
}

.console-section.btn-section {
  padding-top: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666;
}

.upload-zone {
  border: 1px dashed #CCC;
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #FAFAFA;
}

.upload-zone.has-files {
  align-items: flex-start;
}

.upload-zone:hover {
  background: #F0F0F0;
  border-color: #999;
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 40px;
  height: 40px;
  border: 1px solid #DDD;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 15px;
  color: #999;
}

.upload-title {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 5px;
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
}

.file-list {
  width: 100%;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--white);
  padding: 8px 12px;
  border: 1px solid #EEE;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.file-name {
  flex: 1;
  margin: 0 10px;
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: #999;
}

.console-divider {
  display: flex;
  align-items: center;
  margin: 10px 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #EEE;
}

.console-divider span {
  padding: 0 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #BBB;
  letter-spacing: 0.05em;
}

.input-wrapper {
  position: relative;
  border: 1px solid #DDD;
  background: #FAFAFA;
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
}

.model-badge {
  position: absolute;
  bottom: 10px;
  right: 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #AAA;
}

.start-engine-btn {
  width: 100%;
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 0.02em;
  position: relative;
  overflow: hidden;
}

/* 클릭 가능 상태 (비활성화 아님) */
.start-engine-btn:not(:disabled) {
  background: var(--black);
  border: 1px solid var(--black);
  animation: pulse-border 2s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--orange);
  border-color: var(--orange);
  transform: translateY(-2px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: #E5E5E5;
  color: #999;
  cursor: not-allowed;
  transform: none;
  border: 1px solid #E5E5E5;
}

/* 가이드 애니메이션: 미묘한 테두리 펄스 */
@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.2); }
  70% { box-shadow: 0 0 0 6px rgba(0, 0, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
}

/* 반응형 적응 */
@media (max-width: 1200px) {
  .main-title {
    font-size: 3rem;
  }

  .dashboard-section {
    gap: 40px;
  }
}

@media (max-width: 1024px) {
  .dashboard-section {
    flex-direction: column;
  }

  .hero-section {
    flex-direction: column;
  }

  .hero-left {
    padding-right: 0;
    margin-bottom: 40px;
  }

  .hero-logo {
    max-width: 200px;
    margin-bottom: 20px;
  }

  .main-title {
    font-size: 2.5rem;
  }
}
</style>

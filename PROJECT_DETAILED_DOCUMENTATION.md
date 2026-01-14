# DIA-AGENT-PLATFORM 프로젝트 상세 문서

## 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [아키텍처 설계](#아키텍처-설계)
3. [핵심 기능 상세](#핵심-기능-상세)
4. [기술 스택](#기술-스택)
5. [프로젝트 구조](#프로젝트-구조)
6. [주요 컴포넌트 설명](#주요-컴포넌트-설명)
7. [세부 구현 로직](#세부-구현-로직)
8. [개발 환경 설정](#개발-환경-설정)
9. [사용 방법](#사용-방법)
10. [Phase 1/2 완료 사항](#phase-12-완료-사항)
11. [확장 가능성](#확장-가능성)
12. [참고 자료](#참고-자료)

---

## 프로젝트 개요

### 프로젝트명
**DIA (Decision & Insight Automation Agent) Platform**

### 핵심 목표
DIA-AGENT-PLATFORM은 자연어로 주어진 업무 지시를 이해하고, 스스로 **계획 → 실행 → 검증** 과정을 거쳐 최종 결과물(분석 결과, 시각화, 보고서 등)을 완성하는 **Multi-Agent 기반 AI 플랫폼**입니다.

### 주요 특징

1. **플러그인 기반 Agent 시스템**
   - 새로운 Agent를 쉽게 추가할 수 있는 확장 가능한 아키텍처
   - Agent 간 독립성 보장
   - 공통 도구 재사용

2. **자동 라우팅 시스템**
   - 파일 타입 및 키워드 기반 자동 Agent 선택
   - 신뢰도 기반 라우팅 결정

3. **안정적인 Fallback 메커니즘**
   - LLM 없이도 동작 가능 (Rule-based 처리)
   - 네트워크 오류, API Key 미설정 등 다양한 상황 대응
   - 사용자에게 안전한 안내 메시지 제공

4. **표준화된 실행 흐름**
   - Planner → Executor → Reviewer 단계별 명확한 구조
   - 표준화된 컨텍스트 및 파일 로딩
   - 일관된 메타데이터 및 이벤트 시스템

5. **사용자 친화적 UI**
   - Chainlit 기반 대화형 인터페이스
   - Agent Step 시각화
   - Artifact 인라인 표시

### 한 줄 요약
> "자연어로 업무를 지시하면, AI Agent가 스스로 판단·실행·검증하여 결과물을 완성한다."

---

## 아키텍처 설계

### 전체 시스템 아키텍처

```
┌─────────────────────────────────────────┐
│         UI Layer (apps/)                │
│  - Chainlit App                         │
│  - 메시지 렌더링                          │
│  - 파일 업로드 처리                       │
│  - Step/Trace 시각화                     │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      Core Platform (core/)              │
│  - Agent Registry & Runner              │
│  - Router (자동 라우팅)                  │
│  - LLM Client (OpenRouter)              │
│  - Context Normalization                │
│  - File Loader (표준화)                  │
│  - Tools (공통 도구)                     │
│  - Artifact Management                  │
│  - Audit Export                         │
│  - Logging System                       │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│    Agent Plugins (agents/)              │
│  - DIA Agent (데이터 분석)                │
│  - LogCop Agent (로그 분석)              │
│  - (추가 Agent 확장 가능)                 │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      Workspace (workspace/)             │
│  - uploads/ (업로드 파일)                 │
│  - artifacts/ (생성 결과물)               │
│  - audit/ (실행 기록)                    │
│  - logs/ (로그 파일)                     │
└─────────────────────────────────────────┘
```

### 3레이어 구조

1. **UI Layer (`apps/`)**
   - Chainlit 기반 사용자 인터페이스
   - 파일 업로드 및 결과 렌더링
   - Agent 실행 과정 시각화

2. **Core Platform (`core/`)**
   - 플랫폼 공통 인프라
   - Agent 등록 및 실행 관리
   - 라우팅, LLM, 도구, Artifact 관리

3. **Agent Plugins (`agents/`)**
   - 개별 Agent 구현
   - 각 Agent는 독립적으로 동작
   - 공통 Core 인프라 재사용

### 데이터 흐름

```
User Input (Message + Files)
    ↓
Chainlit App (app.py)
    ↓
File Upload Handler (workspace/uploads/)
    ↓
AgentRunner
    ├─ Context Normalization
    ├─ Router (자동 Agent 선택)
    └─ Agent Execution
        ├─ Planner: 계획 수립
        ├─ Executor: 도구 실행
        │   ├─ File Loader (표준화)
        │   ├─ Data Analysis
        │   ├─ Visualization
        │   └─ LLM Client (인사이트 생성)
        └─ Reviewer: 검증 및 승인
    ↓
AgentResult (Artifacts + Events + Meta)
    ↓
Audit Export (workspace/audit/)
    ↓
UI Rendering (render.py)
    ↓
User (최종 결과 확인)
```

---

## 핵심 기능 상세

### 1. 플러그인 기반 Agent 시스템

#### BaseAgent 인터페이스
모든 Agent는 `BaseAgent` 인터페이스를 구현해야 합니다:

```python
class BaseAgent(ABC):
    id: str
    name: str
    description: str
    
    @abstractmethod
    async def run(self, user_message: str, context: Optional[Dict[str, Any]], settings: Any) -> AgentResult:
        raise NotImplementedError
```

#### Agent 등록 및 조회
- `AgentRegistry`: Agent 등록 및 조회 시스템
- 자동으로 `agents/` 디렉토리의 Agent를 인식
- 런타임에 Agent 추가/제거 가능

#### Agent 실행 흐름
모든 Agent는 표준화된 단계를 따릅니다:
1. **Planner**: 요청 해석 및 작업 계획 수립
2. **Executor**: 실제 도구 실행 및 결과 생성
3. **Reviewer**: 결과 검증 및 승인/거절 결정

### 2. 자동 라우팅 시스템

#### 라우팅 규칙 (우선순위 순)

1. **파일 확장자 기반** (가장 높은 신뢰도)
   - `.log`, `.txt`, `.out` → LogCop Agent (confidence: 0.95)
   - `.csv`, `.xlsx`, `.xls`, `.pdf` → DIA Agent (confidence: 0.9)

2. **키워드 기반**
   - 로그/에러 관련 키워드 → LogCop Agent (confidence: 0.8)

3. **Fallback**
   - 기본값: DIA Agent (confidence: 0.6)

#### 라우팅 예시

```python
# 케이스 1: CSV 파일 업로드
uploaded_files: [{"name": "data.csv", "path": "..."}]
→ DIA Agent (confidence: 0.9, reason: "file_ext=.csv -> dia")

# 케이스 2: 로그 파일 업로드
uploaded_files: [{"name": "app.log", "path": "..."}]
→ LogCop Agent (confidence: 0.95, reason: "file_ext=.log -> logcop")

# 케이스 3: 일반 메시지
user_message: "안녕하세요"
→ DIA Agent (confidence: 0.6, reason: "default -> dia")
```

### 3. DIA Agent (Decision & Insight Automation)

#### 주요 기능

1. **CSV 파일 분석**
   - Pandas 기반 데이터 분석
   - 통계 요약 (describe)
   - 숫자형 컬럼 자동 시각화 (Matplotlib)
   - LLM 기반 인사이트 생성 (또는 Rule-based Fallback)

2. **Excel 파일 분석**
   - XLSX/XLS 파일 지원
   - CSV와 동일한 분석 파이프라인

3. **PDF 파일 처리**
   - pdfplumber를 통한 텍스트 추출
   - 첫 페이지 텍스트 분석 (기본값)

4. **보고서 자동 생성**
   - Markdown 형식 보고서
   - 데이터 요약, 인사이트, 권장 액션, 주의사항 포함

#### 실행 흐름

```
Planner 단계
    ↓
요청 해석 및 작업 분해
첨부 파일 확인
    ↓
Executor 단계
    ├─ CSV/Excel: 파일 로드 → 통계 분석 → 시각화 → 인사이트 생성
    └─ PDF: 텍스트 추출 → 분석 → 보고서 생성
    ↓
Reviewer 단계
    ├─ 산출물 존재 여부 확인
    ├─ Markdown 보고서 품질 검증
    └─ 승인/거절 결정
```

#### Rule-based 인사이트 (LLM Fallback)

LLM이 사용 불가능할 때를 대비한 규칙 기반 인사이트:
- 숫자형 컬럼 분석 (변동폭, 이상치 후보)
- 범주형 컬럼 분석 (유니크 비율, 상위 값 빈도)
- 자동 보고서 생성

### 4. LogCop Agent

#### 주요 기능

1. **로그/텍스트 파일 분석**
   - `.log`, `.txt`, `.out` 파일 처리
   - 최대 20,000자까지 읽기 (파일이 크면 tail 처리)

2. **에러 패턴 탐지**
   - Rule-based 키워드 스캔: `exception`, `error`, `stacktrace`, `traceback`, `timeout`, `ssl`, `connection` 등

3. **LLM 기반 인사이트 생성**
   - SRE/플랫폼 엔지니어 관점의 분석
   - Root cause 후보 제시
   - 즉시 조치 및 원인 규명 액션 플랜

4. **Fallback 메커니즘**
   - LLM 실패 시 Rule-based 인사이트 제공

#### 실행 흐름

```
파일/텍스트 수집
    ├─ 업로드 파일: .log/.txt/.out 감지 → 최대 20,000자 읽기
    └─ 메시지: user_message를 로그 텍스트로 처리
    ↓
LLM 인사이트 생성 (또는 Rule-based Fallback)
    ├─ SRE/플랫폼 엔지니어 프롬프트 사용
    └─ 요약, 인사이트, 권장 액션, 주의사항 생성
    ↓
보고서 생성
    └─ Markdown 형식, LLM 사용 여부 힌트 포함
```

### 5. LLM 통합 및 Fallback 메커니즘

#### LLMClient 특징

1. **OpenRouter 기반**
   - LangChain ChatOpenAI 래퍼 사용
   - OpenRouter API 엔드포인트 사용

2. **모델 정책**
   - Primary: `anthropic/claude-3.5-sonnet`
   - Fallback: `openai/gpt-4o-mini`
   - Primary 실패 시 자동 Fallback

3. **안정적인 Fallback 메커니즘**
   - `LLM_ENABLED=false`: LLM 호출 건너뜀 (폐쇄망/데모 안정성)
   - API Key 없음: Rule-based 처리로 자동 전환
   - 네트워크 오류: "환경 제약"으로 분류하여 사용자 안내
   - LLM 호출 실패: Rule-based 처리

4. **재시도 로직**
   - 각 모델당 최대 재시도 횟수 설정 가능
   - Primary → Fallback 순서로 시도

#### LLM 상태 코드

- `ok`: LLM 호출 성공
- `llm_disabled`: LLM_ENABLED=false로 비활성화
- `missing_api_key`: API Key 미설정
- `network_unreachable`: 네트워크 연결 불가
- `llm_call_failed`: LLM 호출 실패

### 6. 표준화된 파일 로딩

#### File Loader (`core/tools/file_loader.py`)

**단일 진입점 원칙**: 모든 파일 로딩은 `load_file()` 함수를 통해 수행됩니다.

#### 지원 파일 형식

1. **텍스트 파일** (`.log`, `.txt`, `.out`)
   - 최대 20,000자까지 읽기 (tail 처리)
   - `kind: "text"` 반환

2. **CSV 파일** (`.csv`)
   - Pandas DataFrame으로 로드
   - 최대 5,000행까지 처리 (기본값)
   - `kind: "csv"` 반환, DataFrame 포함

3. **Excel 파일** (`.xlsx`, `.xls`)
   - Pandas DataFrame으로 로드
   - 최대 5,000행까지 처리 (기본값)
   - `kind: "excel"` 반환, DataFrame 포함

4. **PDF 파일** (`.pdf`)
   - pdfplumber로 텍스트 추출
   - 첫 페이지만 읽기 (기본값)
   - `kind: "pdf"` 반환, 텍스트 포함

#### ToolResult 구조

```python
@dataclass
class ToolResult:
    ok: bool
    summary: str
    data: Dict[str, Any]  # kind, path, ext, df/text 등
    error: Optional[str] = None
    last_error: Optional[str] = None
```

### 7. 컨텍스트 표준화

#### Context Normalization (`core/context/normalize.py`)

**단일 컨텍스트 원칙**: Agent 진입 전 컨텍스트는 `normalize_context()`로 표준화됩니다.

#### AgentContext 구조

```python
@dataclass
class AgentContext:
    session_id: str
    uploaded_files: List[UploadedFileRef]
    meta: Dict[str, Any]
```

#### UploadedFileRef 구조

```python
@dataclass
class UploadedFileRef:
    name: str
    path: str
    mime: Optional[str] = None
```

### 8. Artifact 관리 시스템

#### Artifact 타입

- `markdown`: 분석 보고서
- `image`: 시각화 그래프 (PNG)
- `file`: 기타 파일
- `json`: 구조화된 데이터

#### 저장 위치

`workspace/artifacts/`
- 파일명 형식: `{timestamp}__{safe_filename}.{ext}`
- 타임스탬프 기반 버전 관리

#### ArtifactRef 구조

```python
@dataclass
class ArtifactRef:
    kind: Literal["markdown", "image", "file", "json"]
    name: str
    path: str
    mime_type: Optional[str] = None
    meta: Dict[str, Any] = {}
```

### 9. Reviewer 시스템

#### 공통 Reviewer 엔진 (`core/agent/reviewer.py`)

최소 품질 게이트 구현:
- 산출물 존재 여부 확인
- Markdown 보고서 필수 여부
- Markdown 최소 길이 체크
- Placeholder 탐지
- 실행 실패 여부 점검

#### ReviewSpec (Agent별 차별화 가능)

```python
@dataclass
class ReviewSpec:
    require_artifacts: bool = True
    min_artifacts: int = 1
    require_markdown: bool = True
    markdown_min_chars: int = 80
    markdown_disallow_placeholders: bool = True
    placeholder_markers: Tuple[str, ...] = (...)
    allow_approve_when_exec_failed: bool = False
```

#### ReviewOutcome

```python
@dataclass
class ReviewOutcome:
    approved: bool
    issues: List[str]
    followups: List[str]
    details: Dict[str, Any]
```

### 10. Audit Export 시스템

#### 기능

Agent 실행 결과를 JSON/JSONL 형식으로 저장:
- 단건 JSON: `workspace/audit/{timestamp}__{agent_id}__{trace_id}.json`
- JSONL Append: `workspace/audit/audit.jsonl`

#### Meta Contract v1

```json
{
  "agent_id": "dia",
  "mode": "p2-2-c",
  "approved": true,
  "file_kind": "csv",
  "artifacts_count": 2,
  "error_code": null,
  "llm": {
    "used": true,
    "status": "ok",
    "reason": null,
    "model": "anthropic/claude-3.5-sonnet"
  },
  "review": {
    "issues": [],
    "followups": []
  },
  "trace_id": "abc123"
}
```

#### 설정 기반 제어

- `AUDIT_ENABLED`: Audit 활성화 여부 (기본: true)
- `AUDIT_STORE_MESSAGE`: 사용자 메시지 저장 여부 (기본: true)
- `AUDIT_MESSAGE_MAX_LEN`: 메시지 최대 길이 (기본: 500)
- `AUDIT_STORE_FILE_PATH`: 파일 경로 저장 여부 (기본: true)

### 11. 로깅 시스템

#### 특징

- 콘솔 + 파일 로깅
- `trace_id` / `session_id` 상관관계
- Runner/Router/Tool/LLM 주요 이벤트 기록
- "리팩터링 안전망" 역할

#### 로그 파일 위치

`workspace/logs/dia-agent-platform.log`
- RotatingFileHandler 사용 (최대 10MB, 백업 5개)

#### 로그 레벨

- INFO: 일반 정보
- WARNING: 경고 (LLM 실패 등)
- ERROR: 에러

---

## 기술 스택

### Runtime
- **Python 3.11.x** (권장: 3.11.9)

### UI
- **Chainlit** (>=2.9.0, <3.0.0)
  - 대화형 UI
  - Agent Step / Trace 시각화
  - 비동기 스트리밍 지원

### Agent Orchestration
- **LangGraph** (>=1.0.5, <2.0.0)
  - Planner–Executor–Reviewer 루프 구성
  - 조건 분기 및 반복 제어

### LLM Interface
- **LangChain** (>=1.2.0, <2.0.0)
- **LangChain OpenAI** (>=1.1.6, <2.0.0)
- **OpenRouter** (모델 제공)
  - Primary: `anthropic/claude-3.5-sonnet`
  - Fallback: `openai/gpt-4o-mini`

### Data / Tools
- **Pandas** (>=2.2.0, <3.0.0): 데이터 분석
- **Matplotlib** (>=3.8.0, <4.0.0): 시각화
- **pdfplumber** (>=0.11.8, <2.0.0): PDF 텍스트 추출
- **FAISS-CPU** (==1.13.2): RAG 인덱싱 (옵션)

### Config / State
- **pydantic** (>=2.7.0, <3.0.0)
- **pydantic-settings** (>=2.3.0, <3.0.0)
- **python-dotenv** (>=1.0.1, <2.0.0)

### 기타
- **tiktoken** (>=0.12.0, <1.0.0): 토큰 카운팅
- **tabulate** (>=0.9.0, <2.0.0): 테이블 포맷팅

---

## 프로젝트 구조

```
dia-agent-platform/
├─ README.md                    # 프로젝트 기본 문서
├─ PROJECT_DETAILED_DOCUMENTATION.md  # 본 상세 문서
├─ PHASE1_COMPLETION.md         # Phase 1 완료 보고서
├─ PHASE2_TODO_LIST.md          # Phase 2 작업 목록
├─ requirements.txt             # 의존성 목록
├─ requirements.lock.txt        # 고정된 의존성 (권장)
├─ pyproject.toml               # 프로젝트 설정
├─ .env.example                 # 환경 변수 예시
├─ .gitignore                   # Git 제외 파일
│
├─ apps/                        # UI 레이어
│  └─ chainlit_app/
│     ├─ app.py                 # Chainlit entrypoint
│     └─ ui/
│        ├─ render.py            # 메시지/아티팩트 렌더
│        ├─ steps.py             # Agent Step/Trace 시각화
│        └─ upload.py            # 파일 업로드 처리
│
├─ core/                        # 플랫폼 공통 영역
│  ├─ agent/
│  │  ├─ base.py                # BaseAgent 인터페이스
│  │  ├─ registry.py            # Agent 등록/조회
│  │  ├─ runner.py              # Agent 실행/스트리밍
│  │  ├─ router.py              # 라우팅 로직
│  │  ├─ stages.py              # Planner/Executor/Reviewer 구조
│  │  ├─ reviewer.py            # 공통 Reviewer 엔진
│  │  └─ audit.py               # Audit Export 기능
│  │
│  ├─ graph/
│  │  ├─ state.py               # GraphState 정의 (예비)
│  │  └─ events.py              # trace 이벤트 스키마 (예비)
│  │
│  ├─ llm/
│  │  ├─ client.py              # LangChain LLM 클라이언트(OpenRouter)
│  │  ├─ models.py              # 모델 정책(primary/fallback)
│  │  ├─ prompts.py             # 프롬프트 로더
│  │  ├─ validators.py          # 프롬프트 검증
│  │  └─ ux.py                  # LLM UX 정책 공통화
│  │
│  ├─ tools/
│  │  ├─ base.py                # Tool 스키마/공통 유틸
│  │  ├─ file_loader.py         # CSV/XLSX/PDF/TEXT 로더 (표준화)
│  │  ├─ data_analysis.py       # pandas 분석
│  │  ├─ plotting.py            # matplotlib 렌더 + 파일 저장
│  │  ├─ report_writer.py       # markdown 보고서 생성
│  │  └─ rag_faiss.py           # FAISS 인덱싱/검색 (예비)
│  │
│  ├─ artifacts/
│  │  ├─ store.py                # 산출물 저장
│  │  └─ types.py               # Artifact 타입
│  │
│  ├─ context/
│  │  ├─ schema.py              # AgentContext 정의
│  │  └─ normalize.py           # 컨텍스트 표준화
│  │
│  ├─ config/
│  │  ├─ settings.py            # 환경 설정
│  │  └─ logging.py             # 로깅 설정
│  │
│  ├─ logging/
│  │  └─ logger.py              # 로깅 시스템
│  │
│  ├─ routing/
│  │  ├─ router.py              # (예비) 추가 라우터
│  │  └─ rules.py               # (예비) 추가 규칙
│  │
│  ├─ utils/
│  │  ├─ fs.py                  # 경로/파일 유틸
│  │  └─ time.py                # timestamp 유틸
│  │
│  └─ tests/                    # 스모크 테스트
│     ├─ smoke_audit.py
│     ├─ smoke_context.py
│     ├─ smoke_file_loader.py
│     ├─ smoke_meta.py
│     └─ smoke_route.py
│
├─ agents/                      # Agent 플러그인 영역
│  ├─ dia/
│  │  ├─ agent.py               # DIA Agent 구현
│  │  ├─ graph.py               # 실행 로직 (Planner/Executor/Reviewer)
│  │  ├─ insights.py            # Rule-based 인사이트 생성
│  │  ├─ report.py              # Markdown 보고서 빌더
│  │  ├─ tools.py               # (예비) 전용 Tool
│  │  ├─ schemas.py             # (예비) 확장 State
│  │  ├─ prompts/
│  │  │  ├─ planner.md          # (예비)
│  │  │  ├─ executor.md         # (예비)
│  │  │  ├─ reviewer.md         # (예비)
│  │  │  └─ insight.md          # LLM 인사이트 프롬프트
│  │  └─ README.md              # agent 설명/데모 시나리오
│  │
│  └─ logcop/                   # 로그 분석 Agent
│     ├─ agent.py
│     ├─ graph.py
│     ├─ prompts/
│     │  └─ insight.md          # LLM 프롬프트
│     └─ README.md
│
├─ workspace/                   # 런타임 데이터 (git 제외)
│  ├─ uploads/                  # 업로드된 파일
│  ├─ artifacts/                # 생성된 결과물
│  ├─ audit/                    # 실행 기록 (JSON/JSONL)
│  ├─ indexes/                  # (예비) FAISS 인덱스
│  └─ logs/                     # 애플리케이션 로그
│
├─ scripts/                     # 유틸리티 스크립트
│  ├─ smoke.py                  # 통합 스모크 테스트
│  ├─ smoke_llm.py             # LLM 연결 테스트
│  └─ bootstrap.ps1            # Windows 환경 설정 스크립트
│
└─ tests/                       # 테스트 픽스처
   └─ fixtures/
      ├─ sample_utf8bom.csv
      ├─ sample.log
      ├─ sample.pdf
      └─ sample.txt
```

---

## 주요 컴포넌트 설명

### 1. AgentRunner (`core/agent/runner.py`)

Agent 실행 및 라우팅 오케스트레이션을 담당합니다.

**주요 기능**:
- 컨텍스트 정규화 (`normalize_context()`)
- 자동 라우팅 (`route()`)
- Agent 실행 (`run()`)
- Audit Export (best-effort)

**시그니처**:
```python
class AgentRunner:
    def __init__(self, *, registry: Any, settings: Any)
    def route(self, ctx: Any) -> RouteDecision
    async def run(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> AgentResult
```

### 2. AgentRegistry (`core/agent/registry.py`)

Agent 등록 및 조회 시스템입니다.

**주요 기능**:
- Agent 등록 (`register()`)
- Agent 조회 (`get()`)
- 모든 Agent 목록 조회

### 3. LLMClient (`core/llm/client.py`)

OpenRouter 기반 LLM 클라이언트입니다.

**주요 기능**:
- Primary/Fallback 모델 정책
- 재시도 로직
- 네트워크 오류 감지
- 안전한 Fallback 처리

**시그니처**:
```python
class LLMClient:
    def __init__(self, settings: Any)
    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse
```

### 4. File Loader (`core/tools/file_loader.py`)

표준화된 파일 로딩 도구입니다.

**주요 기능**:
- CSV/XLSX/PDF/TEXT 파일 지원
- 최대 행/문자 수 제한
- ToolResult 형식으로 통일된 반환

**시그니처**:
```python
def load_file(
    path: str,
    *,
    max_rows: int = 5000,
    pdf_max_pages: int = 1,
    text_max_chars: int = 20000,
) -> ToolResult
```

### 5. Context Normalization (`core/context/normalize.py`)

컨텍스트 표준화 함수입니다.

**주요 기능**:
- 다양한 입력 형태 지원 (dict, 객체 등)
- 표준 AgentContext로 변환
- UploadedFileRef 정규화

**시그니처**:
```python
def normalize_context(raw: Optional[Dict[str, Any]]) -> AgentContext
```

### 6. Reviewer Engine (`core/agent/reviewer.py`)

공통 Reviewer 엔진입니다.

**주요 기능**:
- 최소 품질 게이트 구현
- 산출물 검증
- Markdown 품질 체크
- Placeholder 탐지

**시그니처**:
```python
def review_execution(
    *,
    spec: ReviewSpec,
    exec_ok: bool,
    exec_text: Optional[str],
    artifacts: Sequence[ArtifactRef],
    error_code: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> ReviewOutcome
```

### 7. Audit Export (`core/agent/audit.py`)

Agent 실행 결과를 JSON/JSONL로 저장합니다.

**주요 기능**:
- 단건 JSON 저장
- JSONL Append 저장
- Meta Contract v1 포함

**시그니처**:
```python
def export_and_append(
    result: AgentResult,
    user_message: str,
    context: AgentContext,
    settings: Any,
) -> Tuple[Optional[Path], Optional[Path], Dict[str, Any]]
```

---

## 세부 구현 로직

### 1. Agent 실행 흐름 상세

#### DIA Agent 실행 흐름

**Planner 단계 (`_plan()`)**

```python
def _plan(sc: StageContext) -> tuple[Plan, List[AgentEvent]]:
    # 1. 업로드된 파일 확인
    uploaded_files = _get_uploaded_files(sc.context)
    has_file = bool(uploaded_files)
    
    # 2. 파일 메타데이터 수집
    if has_file:
        f0 = uploaded_files[0]
        file_name, file_path, file_ext, file_mime = _file_name_and_path(f0)
        notes = {
            "first_file_name": file_name,
            "first_file_ext": file_ext,
            ...
        }
    
    # 3. 계획 수립
    plan = Plan(
        intent="data_inspection",
        assumptions=[
            "CSV/PDF 입력을 우선 지원",
            "LLM은 설정/네트워크에 따라 비활성 또는 실패할 수 있음",
        ],
        constraints=[
            "파일 로딩은 load_file() 단일 진입점 사용",
            "LLM 실패는 예외가 아니라 상태로 처리",
        ],
        notes=notes,
    )
    
    # 4. 이벤트 생성 및 반환
    return plan, events
```

**Executor 단계 (`_execute()`) - CSV 처리**

```python
async def _execute(sc: StageContext, plan: Plan) -> tuple[ExecutionResult, List[AgentEvent]]:
    # 1. 파일 로드 (표준화된 load_file() 사용)
    load_res = load_file(file_path)
    
    # 2. CSV 처리
    if kind == "csv":
        df = load_res.data["df"]  # DataFrame 직접 제공
        
        # 2-1. 통계 요약 생성
        head = df.head(10).to_markdown(index=False)
        desc_md = df.describe(include="all").to_markdown()
        numeric_summary = _summarize_numeric(df)
        
        # 2-2. 시각화 생성
        plot_path = _save_line_plot(
            settings=sc.settings,
            df=df,
            title=f"dia_csv_plot_{Path(file_path).stem}"
        )
        # - 숫자형 컬럼만 선택 (최대 2개)
        # - 최대 200행만 시각화
        # - Matplotlib로 line plot 생성
        # - PNG로 저장 (dpi=150)
        
        # 2-3. LLM 인사이트 생성 (또는 Rule-based Fallback)
        llm_client = LLMClient(sc.settings)
        llm_res = await llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        
        if llm_res.ok:
            llm_section = ensure_sections(llm_res.content)
        else:
            # Rule-based Fallback
            llm_section = rule_based_insights(df)
        
        # 2-4. Markdown 보고서 생성
        report_md = build_markdown_report(
            ReportInputs(
                user_request=sc.user_message,
                file_name=file_name,
                head_md=head,
                describe_md=desc_md,
                plot_file=plot_path.name if plot_path else None,
                llm_insights_md=llm_section,
            )
        )
        
        # 2-5. Artifact 저장
        md_path = _save_artifact_markdown(
            settings=sc.settings,
            title=f"dia_csv_report_{Path(file_path).stem}",
            body=report_md
        )
        
        artifacts.append(ArtifactRef(kind="markdown", ...))
        if plot_path:
            artifacts.append(ArtifactRef(kind="image", ...))
    
    return ExecutionResult(...), events
```

**Executor 단계 - PDF 처리**

```python
if kind == "pdf":
    # 1. 텍스트 추출
    text = load_res.data.get("text", "")
    if not text:
        text = "(텍스트 추출 실패: 스캔 PDF 가능)"
    
    # 2. 간단한 보고서 생성
    md_path = _save_artifact_markdown(
        settings=sc.settings,
        title=f"dia_pdf_extract_{Path(file_path).stem}",
        body=f"# DIA 분석 결과 (PDF)\n\n{text}\n"
    )
    
    artifacts.append(ArtifactRef(kind="markdown", ...))
```

**Reviewer 단계 (`_review()`)**

```python
def _review(sc: StageContext, plan: Plan, exec_res: ExecutionResult) -> tuple[ReviewResult, List[AgentEvent]]:
    # 1. ReviewSpec 정의 (Agent별 차별화)
    spec = ReviewSpec(
        require_artifacts=True,
        min_artifacts=1,
        require_markdown=True,
        markdown_min_chars=80,
        markdown_disallow_placeholders=True,
        allow_approve_when_exec_failed=False,
    )
    
    # 2. 공통 Reviewer 엔진 호출
    outcome = review_execution(
        spec=spec,
        exec_ok=exec_res.ok,
        exec_text=exec_res.text,
        artifacts=exec_res.artifacts,
        error_code=exec_res.error_code,
    )
    
    # 3. 결과에 따른 이벤트 생성
    if outcome.approved:
        events.append(info("reviewer.approve", "승인"))
    else:
        events.append(warn("reviewer.reject", "거절"))
        events.append(evlog("reviewer.issues", _format_review_issues(outcome.issues)))
    
    return ReviewResult(...), events
```

#### LogCop Agent 실행 흐름

**Executor 단계 - 텍스트 처리**

```python
async def _execute(sc: StageContext, plan: Plan) -> tuple[ExecutionResult, List[AgentEvent]]:
    # 1. 텍스트 수집
    if uploaded_files:
        # 파일에서 텍스트 로드
        load_res = load_file(path)
        log_text = load_res.data.get("text", "")
        # 최대 20,000자 (tail 처리)
    else:
        # user_message를 로그 텍스트로 처리
        log_text = sc.user_message
    
    # 2. LLM 인사이트 생성 (또는 Rule-based Fallback)
    llm_client = LLMClient(sc.settings)
    llm_res = await llm_client.generate(
        system_prompt=system_prompt,  # SRE/플랫폼 엔지니어 프롬프트
        user_prompt=user_prompt
    )
    
    if llm_res.ok:
        body = llm_res.content
    else:
        # Rule-based 키워드 스캔
        body = _rule_based_log_insights(log_text)
        # - exception, error, stacktrace, traceback 등 키워드 탐지
        # - 기본 안내 메시지 생성
    
    # 3. 보고서 생성 및 저장
    report = f"# LogCop 분석 보고서\n\n{body}\n"
    out_path = _save_markdown(sc.settings, "logcop_report", report)
    
    artifacts.append(ArtifactRef(kind="markdown", ...))
    
    return ExecutionResult(...), events
```

### 2. UI 렌더링 세부 로직

#### 이벤트 타입 추론 (`_infer_event_type()`)

```python
def _infer_event_type(ev: Any) -> str:
    """
    AgentEvent가 dict 형태로 올 때 type이 없을 수 있으므로
    name suffix로 step_start/step_end를 추론한다.
    """
    ev_type = _ev_get(ev, "type", None)
    if ev_type:
        return ev_type.strip()
    
    name = _ev_get(ev, "name", "")
    # 'planner.start' -> 'step_start'
    if name.endswith(".start"):
        return "step_start"
    if name.endswith(".end"):
        return "step_end"
    
    return "log"
```

#### 이벤트 렌더링 (`render_events()`)

```python
async def render_events(events: List[AgentEvent]) -> None:
    for ev in events:
        ev_type = _infer_event_type(ev)
        ev_name = _ev_get(ev, "name", "")
        ev_message = _ev_get(ev, "message", "")
        
        if ev_type in ("step_start", "step_end"):
            # Step으로 렌더링
            step_name = _infer_step_name(ev)  # 'planner.start' -> 'planner'
            async with cl.Step(name=step_name):
                await cl.Message(content=ev_message).send()
        else:
            # 일반 메시지로 렌더링
            prefix = f"[{ev_name}] " if ev_name else ""
            await cl.Message(content=f"{prefix}{ev_message}").send()
```

#### 메타 요약 생성 (`build_meta_summary()`)

```python
def build_meta_summary(meta: Any) -> str:
    """
    Meta Contract v1을 사용자 친화적인 Markdown으로 변환
    """
    agent_id = _meta_get(meta, ["agent_id"], "-")
    approved = bool(_meta_get(meta, ["approved"], False))
    llm_used = bool(_meta_get(meta, ["llm", "used"], False))
    llm_status = _meta_get(meta, ["llm", "status"], "-")
    review_issues = _meta_get(meta, ["review", "issues"], [])
    
    lines = []
    lines.append("## Meta 요약")
    lines.append(f"- Agent: `{agent_id}`")
    lines.append(f"- Approved: {'✅' if approved else '❌'}")
    lines.append(f"- LLM: used={llm_used}, status=`{llm_status}`")
    
    if review_issues:
        lines.append("\n### Reviewer issues")
        for issue in review_issues[:5]:
            lines.append(f"- {issue}")
    
    return "\n".join(lines)
```

#### Artifact 렌더링 (`_to_elements()`)

```python
def _to_elements(artifacts: List[ArtifactRef]) -> List[cl.Element]:
    elements = []
    for a in artifacts:
        kind = getattr(a, "kind", None) if not isinstance(a, dict) else a.get("kind")
        name = getattr(a, "name", None)
        path = getattr(a, "path", None)
        
        if kind == "image":
            # 이미지는 인라인 표시
            elements.append(cl.Image(name=name, path=path, display="inline"))
        else:
            # 파일은 다운로드 링크
            elements.append(cl.File(name=name, path=path, display="inline"))
    
    return elements
```

### 3. 파일 업로드 처리 상세

#### Chainlit 파일 업로드 처리 (`handle_uploads()`)

```python
async def handle_uploads(message: cl.Message, settings: Settings):
    """
    1. Chainlit message.elements에서 파일 추출
    2. workspace/uploads/로 복사
    3. 안전한 파일명 변환
    4. dict 형태로 반환 (Agent/Core 호환)
    """
    uploaded = []
    
    # Chainlit File element는 .path를 제공 (임시 경로)
    for el in message.elements:
        src = getattr(el, "path", None)  # 임시 경로
        name = getattr(el, "name", None)
        mime = getattr(el, "mime", None)
        
        if not src or not name:
            continue
        
        # 안전한 파일명 변환
        safe_name = safe_filename(name)
        # 특수문자 제거: < > : " / \ | ? *
        
        # 타임스탬프 추가 (중복 방지)
        dst_name = f"{ts()}__{safe_name}"
        
        # workspace/uploads/로 복사
        dst_path = copy_to(
            src_path=src,
            dst_dir=_get_workspace_upload_dir(settings),
            dst_name=dst_name
        )
        
        uploaded.append({
            "name": safe_name,
            "path": str(dst_path),
            "mime": mime,
        })
    
    return uploaded
```

### 4. 유틸리티 함수 상세

#### 파일 시스템 유틸 (`core/utils/fs.py`)

```python
def ensure_dir(path: str | Path) -> Path:
    """
    디렉토리가 없으면 생성 (부모 디렉토리 포함)
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def copy_to(src_path: str | Path, dst_dir: str | Path, dst_name: str) -> Path:
    """
    파일을 dst_dir로 복사
    - shutil.copy2 사용 (메타데이터 보존)
    """
    dst_dir_p = ensure_dir(dst_dir)
    dst_path = dst_dir_p / dst_name
    shutil.copy2(str(src_path), str(dst_path))
    return dst_path

def safe_filename(name: str) -> str:
    """
    Windows/Unix 공통으로 위험한 문자 제거
    - < > : " / \ | ? * 제거
    - 빈 문자열이면 "file" 반환
    """
    bad = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for b in bad:
        name = name.replace(b, "_")
    return name.strip() or "file"
```

#### 타임스탬프 유틸 (`core/utils/time.py`)

```python
def ts() -> str:
    """
    타임스탬프 생성: YYYYMMDD_HHMMSS 형식
    예: "20250113_143022"
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")
```

### 5. 로깅 시스템 세부 구현

#### LogRecordFactory를 통한 trace_id 주입

```python
def _install_trace_id_record_factory() -> None:
    """
    모든 LogRecord에 trace_id 필드를 자동 주입
    - 로거/핸들러/서드파티 출처와 무관하게 적용
    - 전역 _TRACE_ID 변수 참조
    """
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        # trace_id가 없으면 전역 _TRACE_ID 주입
        if not hasattr(record, "trace_id") or record.trace_id is None:
            record.trace_id = _TRACE_ID
        return record
    
    logging.setLogRecordFactory(record_factory)
```

#### TraceIdFilter

```python
class TraceIdFilter(logging.Filter):
    """
    2차 방어: 핸들러 레벨에서 trace_id 보장
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id") or record.trace_id is None:
            record.trace_id = _TRACE_ID
        return True
```

#### 로깅 설정 (`setup_logging()`)

```python
def setup_logging(
    workspace_dir: str = "workspace",
    log_filename: str = "app.log",
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 5,
    enable_console: bool = False,
) -> TraceIdFilter:
    """
    1. LogRecordFactory 설치 (trace_id 주입)
    2. RotatingFileHandler 구성
    3. TraceIdFilter 추가 (2차 방어)
    4. Console handler는 옵션 (기본 False)
    """
    _install_trace_id_record_factory()
    
    log_dir = Path(workspace_dir) / "logs"
    log_path = log_dir / log_filename
    
    root = logging.getLogger()
    root.setLevel(level)
    
    # Formatter: trace_id 포함
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | "
        "trace_id=%(trace_id)s | %(message)s"
    )
    
    # Filter
    tf = TraceIdFilter()
    root.addFilter(tf)
    
    # File handler (rotating)
    fh = RotatingFileHandler(
        str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    fh.addFilter(tf)
    root.addHandler(fh)
    
    # Console handler (옵션)
    if enable_console:
        sh = logging.StreamHandler()
        sh.setLevel(level)
        sh.setFormatter(formatter)
        sh.addFilter(tf)
        root.addHandler(sh)
    
    return tf
```

### 6. Audit Export 세부 구현

#### 데이터 정규화 로직

```python
def _normalize_artifacts(artifacts: Any) -> List[Dict[str, Any]]:
    """
    ArtifactRef (dict/객체)를 표준 dict로 변환
    """
    out = []
    for a in artifacts:
        if isinstance(a, dict):
            out.append({
                "kind": a.get("kind"),
                "name": a.get("name"),
                "path": a.get("path"),
                "mime_type": a.get("mime_type"),
            })
        else:
            out.append({
                "kind": getattr(a, "kind", None),
                "name": getattr(a, "name", None),
                "path": getattr(a, "path", None),
                "mime_type": getattr(a, "mime_type", None),
            })
    return out

def _normalize_files(context: Any, settings: Any) -> List[Dict[str, Any]]:
    """
    context에서 uploaded_files 메타만 추출
    - path 저장은 AUDIT_STORE_FILE_PATH 설정에 따라 제어
    """
    store_path = _bool_setting(settings, "AUDIT_STORE_FILE_PATH", True)
    
    files = _file_get(context)  # stages.py 헬퍼 사용
    out = []
    
    for f in files[:10]:  # 상한(운영 안전)
        name, path, ext, mime = _file_name_and_path(f)
        out.append({
            "name": name,
            "path": (path if store_path else ""),  # 설정에 따라
            "ext": ext,
            "mime": mime,
        })
    return out

def _normalize_events_summary(events: Any, max_names: int = 30) -> Dict[str, Any]:
    """
    이벤트 목록을 요약 (이름만 추출)
    """
    names = []
    for ev in events:
        if isinstance(ev, dict):
            n = ev.get("name") or ev.get("type") or ""
        else:
            n = getattr(ev, "name", None) or getattr(ev, "type", None) or ""
        if n:
            names.append(str(n))
        if len(names) >= max_names:
            break
    
    return {
        "count": len(list(events)) if hasattr(events, "__len__") else len(names),
        "names": names
    }
```

#### JSON 직렬화 처리 (`_json_default()`)

```python
def _json_default(o: Any):
    """
    JSON 직렬화 시 특수 타입 처리
    """
    # dataclass → dict
    if is_dataclass(o):
        return asdict(o)
    
    # Path → str
    if isinstance(o, Path):
        return str(o)
    
    # bytes → len만
    if isinstance(o, (bytes, bytearray)):
        return {"_type": "bytes", "len": len(o)}
    
    # 그 외: string fallback
    return str(o)
```

#### Audit 엔트리 생성 (`build_audit_entry()`)

```python
def build_audit_entry(
    result: Any,
    user_message: str,
    context: Any,
    settings: Any,
) -> Dict[str, Any]:
    """
    Meta Contract v1을 포함한 감사용 엔트리 생성
    """
    # 1. 설정 확인
    audit_enabled = _bool_setting(settings, "AUDIT_ENABLED", True)
    if not audit_enabled:
        return {"schema_version": "audit.v1", "disabled": True}
    
    # 2. 메타데이터 추출
    meta = getattr(result, "meta", None)
    trace_id = _meta_get(meta, ["trace_id"], "-")
    
    # 3. 데이터 정규화
    artifacts = _normalize_artifacts(getattr(result, "artifacts", None))
    events_summary = _normalize_events_summary(getattr(result, "events", None))
    files = _normalize_files(context, settings)
    
    # 4. 엔트리 구성
    entry = {
        "schema_version": "audit.v1",
        "ts": ts(),
        "trace_id": trace_id,
        "agent": {
            "agent_id": _meta_get(meta, ["agent_id"], None),
            "mode": _meta_get(meta, ["mode"], None),
        },
        "outcome": {
            "approved": _meta_get(meta, ["approved"], False),
            "file_kind": _meta_get(meta, ["file_kind"], None),
            "error_code": _meta_get(meta, ["error_code"], None),
            "artifacts_count": len(artifacts),
        },
        "request": {
            "message_len": len(user_message or ""),
            "message_preview": _safe_preview(user_message or "", max_len),
        },
        "files": files,
        "artifacts": artifacts,
        "events_summary": events_summary,
        "meta": meta,  # v1 contract 그대로 저장
    }
    
    # 5. 메시지 전체 저장 (설정에 따라)
    if _bool_setting(settings, "AUDIT_STORE_MESSAGE", False):
        entry["request"]["message"] = user_message
    
    return entry
```

#### Audit 파일 저장

```python
def export_audit_json(entry: Dict[str, Any], settings: Any) -> Path:
    """
    단건 JSON export 저장
    파일명: {timestamp}__{agent_id}__{trace_id}.json
    """
    out_dir = ensure_dir(_audit_dir(settings))
    agent_id = str((entry.get("agent") or {}).get("agent_id") or "").strip()
    trace_id = str(entry.get("trace_id") or "").strip()
    
    fname = f"{ts()}__{safe_filename(agent_id or 'agent')}__{safe_filename(trace_id or '-')}.json"
    out_path = out_dir / fname
    
    out_path.write_text(
        json.dumps(entry, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8"
    )
    return out_path

def append_audit_jsonl(entry: Dict[str, Any], settings: Any) -> Path:
    """
    Append-only JSONL 저장
    파일: workspace/audit/audit.jsonl
    """
    out_dir = ensure_dir(_audit_dir(settings))
    out_path = out_dir / "audit.jsonl"
    
    line = json.dumps(entry, ensure_ascii=False, default=_json_default)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    
    return out_path
```

### 7. Rule-based 인사이트 생성 상세

#### DIA Agent Rule-based 인사이트 (`agents/dia/insights.py`)

```python
def rule_based_insights(df: pd.DataFrame) -> str:
    """
    LLM 없이도 의미 있는 인사이트 생성
    """
    insights = []
    actions = []
    cautions = []
    
    # 1. 숫자 컬럼 분석
    num = df.select_dtypes(include="number")
    if not num.empty:
        desc = num.describe().T
        desc["range"] = desc["max"] - desc["min"]
        desc = desc.sort_values("range", ascending=False)
        
        # 변동폭 상위 1~2개 지표만 요약
        for col in desc.index[:2]:
            row = desc.loc[col]
            insights.append(
                f"- `{col}` 변동폭이 큽니다: "
                f"min={row['min']:.3f}, p50={row['50%']:.3f}, "
                f"max={row['max']:.3f} (mean={row['mean']:.3f})."
            )
        
        # 이상치 후보 안내(상/하위 10%)
        col0 = desc.index[0]
        low = num[col0].quantile(0.1)
        high = num[col0].quantile(0.9)
        insights.append(
            f"- `{col0}` 기준 상/하위 10% 임계값: "
            f"<= {low:.3f}, >= {high:.3f}."
        )
        actions.append(
            f"- `{col0}` 상/하위 10% 레코드를 추출하여 교차분석하세요."
        )
    
    # 2. 범주형 컬럼 분석
    cat = df.select_dtypes(exclude="number")
    if not cat.empty:
        n = len(df)
        candidate_cols = []
        
        # 유니크 비율이 낮은 컬럼만 선택 (노이즈 제거)
        for col in cat.columns:
            uniq = df[col].nunique(dropna=False)
            uniq_ratio = (uniq / n) if n else 1.0
            if uniq_ratio <= 0.5:  # 유니크 비율 50% 이하만
                candidate_cols.append(col)
        
        # 상위 3개 값의 빈도 및 비율 계산
        for col in candidate_cols[:3]:
            top3 = _top_k_share(df[col], k=3)
            if top3:
                formatted = ", ".join([
                    f"`{v}` {c}건({p}%)" for v, c, p in top3
                ])
                insights.append(f"- `{col}` 분포 상위: {formatted}.")
    
    # 3. Markdown 섹션 구성
    md = []
    md.append("## 요약\n" + "\n".join(summary))
    md.append("\n## 인사이트\n" + "\n".join(insights[:6]))
    md.append("\n## 권장 액션\n" + "\n".join(actions[:4]))
    md.append("\n## 주의사항\n" + "\n".join(cautions))
    
    return "\n".join(md)
```

#### LogCop Agent Rule-based 인사이트

```python
def _rule_based_log_insights(text: str) -> str:
    """
    로그 텍스트에서 키워드 스캔
    """
    lowered = (text or "").lower()
    hits = []
    
    # 에러 키워드 탐지
    keywords = [
        "exception", "error", "stacktrace", "traceback",
        "caused by", "timeout", "pkix", "ssl", "connection"
    ]
    for k in keywords:
        if k in lowered:
            hits.append(k)
    
    lines = []
    lines.append("## 요약")
    lines.append("- 업로드된 로그/텍스트에서 오류 징후를 스캔했습니다.")
    if hits:
        lines.append(f"- 탐지 키워드: {', '.join(hits)}")
    else:
        lines.append("- 명확한 오류 키워드는 탐지되지 않았습니다.")
    
    lines.append("\n## 권장 액션")
    lines.append("- 에러 발생 시각/요청 단위로 주변 로그(전후 200~500라인)를 확보하세요.")
    lines.append("- `Exception / Caused by` 체인 최하단(root cause) 메시지를 우선 확인하세요.")
    
    return "\n".join(lines)
```

### 8. 시각화 생성 로직 상세

#### DIA Agent 시각화 (`_save_line_plot()`)

```python
def _save_line_plot(settings: Any, df: pd.DataFrame, title: str) -> Path | None:
    """
    숫자형 컬럼만 선택하여 line plot 생성
    """
    # 1. 숫자형 컬럼만 선택
    num_df = df.select_dtypes(include="number")
    if num_df.empty:
        return None
    
    # 2. 최대 2개 컬럼, 최대 200행
    cols = list(num_df.columns)[:2]
    plot_df = num_df[cols].head(200)
    
    # 3. 파일 경로 생성
    out_dir = ensure_dir(_artifact_dir(settings))
    filename = f"{ts()}__{safe_filename(title)}.png"
    out_path = out_dir / filename
    
    # 4. Matplotlib로 plot 생성
    plt.figure()
    plot_df.plot()  # line plot
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)  # 고해상도
    plt.close()  # 메모리 해제
    
    return out_path
```

---

## 개발 환경 설정

### 1. Python 버전

- **Python 3.11.x** (권장: 3.11.9)
- Python 3.12 / 3.13은 일부 라이브러리 호환성 이슈 가능성

### 2. 가상환경 생성 및 활성화

```powershell
# Python 3.11로 가상환경 생성
py -3.11 -m venv .venv

# 가상환경 활성화
.\.venv\Scripts\activate

# Python 버전 확인
python --version
# Python 3.11.x 출력 확인
```

### 3. 의존성 설치

```powershell
# pip 업그레이드
python -m pip install --upgrade pip setuptools wheel

# Lock 파일 기준 설치 (권장)
pip install -r requirements.lock.txt

# 의존성 충돌 확인
pip check
# 출력이 없으면 정상
```

### 4. 환경 변수 설정

`.env` 파일 생성 (`.env.example` 참고):

```env
# OpenRouter API Key (선택)
OPENROUTER_API_KEY=sk-or-v1-...

# LLM 활성화 (기본: false, 폐쇄망 안정성)
LLM_ENABLED=false

# Agent 선택 (auto | dia | logcop)
ACTIVE_AGENT=auto

# LLM 옵션
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=900
LLM_TIMEOUT_SEC=45
LLM_MAX_RETRIES=1

# Audit 설정
AUDIT_ENABLED=true
AUDIT_STORE_MESSAGE=true
AUDIT_MESSAGE_MAX_LEN=500
AUDIT_STORE_FILE_PATH=true
```

### 5. 환경 재현성 검증 (권장)

```powershell
# 가상환경 삭제
deactivate
Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue

# 재설치
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.lock.txt
pip check
```

---

## 사용 방법

### 1. 애플리케이션 실행

```powershell
# 가상환경 활성화
.\.venv\Scripts\activate

# Chainlit 앱 실행
chainlit run apps/chainlit_app/app.py
```

브라우저에서 `http://localhost:8000` 접속

### 2. 스모크 테스트 실행

```powershell
# 통합 스모크 테스트
python -m scripts.smoke

# 개별 테스트
python -m core.tests.smoke_context
python -m core.tests.smoke_file_loader
python -m core.tests.smoke_route
python -m core.tests.smoke_meta
python -m core.tests.smoke_audit

# LLM 연결 테스트
python -m scripts.smoke_llm
```

### 3. 사용 시나리오

#### 시나리오 1: CSV 파일 분석

1. Chainlit UI에서 CSV 파일 업로드
2. "이 데이터를 분석해줘" 메시지 입력
3. DIA Agent가 자동 선택됨
4. 결과:
   - 통계 요약
   - 시각화 그래프 (PNG)
   - Markdown 보고서 (인사이트, 권장 액션 포함)

#### 시나리오 2: 로그 파일 분석

1. Chainlit UI에서 `.log` 파일 업로드
2. "이 로그를 분석해줘" 메시지 입력
3. LogCop Agent가 자동 선택됨
4. 결과:
   - 에러 패턴 탐지
   - Root cause 후보
   - 즉시 조치 및 액션 플랜
   - Markdown 보고서

#### 시나리오 3: PDF 파일 분석

1. Chainlit UI에서 PDF 파일 업로드
2. "이 문서를 요약해줘" 메시지 입력
3. DIA Agent가 자동 선택됨
4. 결과:
   - PDF 텍스트 추출
   - 분석 및 요약
   - Markdown 보고서

---

## Phase 1/2 완료 사항

### Phase 1 완료 사항

1. ✅ 플러그인 기반 Agent 시스템 구축
2. ✅ DIA Agent (데이터 분석) 구현
3. ✅ LogCop Agent (로그 분석) 구현
4. ✅ 자동 라우팅 시스템 구현
5. ✅ Chainlit UI 통합
6. ✅ Artifact 관리 시스템 구축
7. ✅ LLM 통합 및 Fallback 메커니즘

### Phase 2 완료 사항

#### Phase 2-1 (표준화 · 안정성)

1. ✅ **P2-1-A**: File Loader 텍스트 지원 완결
2. ✅ **P2-1-B**: DIA Agent load_file 통합
3. ✅ **P2-1-C**: Runner 단 normalize_context 강제
4. ✅ **P2-1-D**: LLM UX 정책 공통화
5. ✅ **P2-1-E**: Phase2 스모크 테스트 고정
6. ✅ **P2-1-L**: Logging Baseline 추가

#### Phase 2-2 (Agent 품질 · 내부 구조 개선)

1. ✅ **P2-2-A**: Planner/Executor/Reviewer 구조 명확화
2. ✅ **P2-2-B**: Reviewer 실질화 (Lite)
3. ✅ **P2-2-C**: AgentResult meta 표준화 확장
4. ✅ **P2-2-D**: Audit Export 기능 구현

#### Phase 2-3 (플랫폼 관점 마무리)

- ⏳ **P2-3-A**: Agent Capability 선언 (대기)
- ⏳ **P2-3-B**: Router 신뢰도 계산 정제 (대기)
- ⏳ **P2-3-C**: 실패 시나리오 문서화 (대기)
- ⏳ **P2-3-D**: Phase2 기준 README 갱신 (대기)

### 주요 개선 사항

1. **표준화**
   - 단일 진입점 원칙 (파일 로딩)
   - 단일 컨텍스트 원칙 (컨텍스트 정규화)
   - 일관된 메타데이터 구조

2. **안정성**
   - LLM 실패는 에러가 아니라 상태로 처리
   - 폐쇄망/개방망 모두 예측 가능한 동작
   - Rule-based Fallback으로 안정성 확보

3. **품질**
   - Reviewer로 최소 품질 게이트 구현
   - 명확한 단계별 구조 (Planner/Executor/Reviewer)
   - 표준화된 이벤트 및 메타데이터

4. **관측 가능성**
   - 로깅 시스템 구축
   - Audit Export 기능
   - Trace ID 기반 상관관계

---

## 확장 가능성

### 1. 새 Agent 추가

새 Agent를 추가하려면:

1. `agents/<agent_id>/` 디렉토리 생성
2. `agent.py`에서 `BaseAgent` 구현
3. `graph.py`에서 실행 로직 구현 (Planner/Executor/Reviewer)
4. `AgentRegistry`에 등록

**예시 구조**:
```
agents/new_agent/
├─ agent.py      # BaseAgent 구현
├─ graph.py      # 실행 로직
└─ prompts/      # 프롬프트 (선택)
```

### 2. 새 도구 추가

`core/tools/` 디렉토리에 새 도구 모듈 추가:

```python
# core/tools/new_tool.py
from core.tools.base import ToolResult

def new_tool(...) -> ToolResult:
    # 도구 로직 구현
    return ToolResult(ok=True, summary="...", data={...})
```

### 3. 라우팅 규칙 확장

`core/agent/router.py`의 `route()` 메서드 수정:

```python
def route(self, ctx: Any) -> RouteDecision:
    # 새로운 라우팅 규칙 추가
    if ...:
        return RouteDecision(agent_id="new_agent", confidence=0.9, reason="...")
    ...
```

### 4. UI 교체

`apps/` 레이어만 수정하면 다른 UI 프레임워크로 교체 가능:
- Streamlit
- Gradio
- FastAPI + React
- 등등

### 5. LangGraph 통합 (향후)

현재는 순차 실행 구조이지만, 향후 LangGraph로 전환 가능:
- 실제 Graph 기반 실행 흐름
- 조건부 분기 및 반복 제어
- State 관리 시스템

---

## 참고 자료

### 프로젝트 문서

- `README.md`: 프로젝트 기본 문서
- `PHASE1_COMPLETION.md`: Phase 1 완료 보고서
- `PHASE2_TODO_LIST.md`: Phase 2 작업 목록

### Agent 문서

- `agents/dia/README.md`: DIA Agent 설명
- `agents/logcop/README.md`: LogCop Agent 설명

### 외부 문서

- [Chainlit Documentation](https://docs.chainlit.io/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Documentation](https://python.langchain.com/)
- [OpenRouter Documentation](https://openrouter.ai/docs)

---

## 결론

DIA-AGENT-PLATFORM은 **확장 가능한 Multi-Agent 플랫폼의 견고한 기반**을 구축한 프로젝트입니다. 플러그인 기반 아키텍처, 자동 라우팅, 안정적인 Fallback 메커니즘을 통해 실용적인 Agent를 구현하고, 사용자 친화적인 UI를 제공합니다.

Phase 1과 Phase 2를 통해 표준화, 안정성, 품질, 관측 가능성을 확보했으며, 명확한 확장 포인트와 모듈화된 구조로 인해 향후 기능 추가가 용이하도록 설계되었습니다.

---

**작성일**: 2025-01-13  
**버전**: Phase 2 완료  
**상태**: 프로덕션 준비 완료 (MVP)

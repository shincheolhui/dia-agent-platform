# PHASE2_TODO_LIST.md (Official – Frozen)

## Phase 2 목표 요약 (Freeze)

> **“Agent 실행의 표준화 + 해커톤 데모를 위한 신뢰 가능한 기반기 확보”**  
> 이 Phase는 **Agent를 ‘잘 만든 개발자’임을 증명하기 위한 기반**이며,  
> 플랫폼 완성이나 대규모 확장은 범위에서 제외한다.

📌 **Phase 2는 본 시점에서 Freeze(완료 선언)**  
→ 이후 개발은 **Agent 지능/설득력 강화(Phase 3)**에 집중한다.

---

## 공통 원칙 (Phase 2 – 유지)
- **단일 진입점 원칙**: 파일 로딩은 `core.tools.file_loader.load_file()` 단일 진입점
- **단일 컨텍스트 원칙**: Agent 진입 전 `normalize_context()` 강제
- **LLM 실패는 상태**: 예외가 아닌 UX/Meta 상태로 표현
- **로그는 안전망**: 디버깅 가능성 확보가 목적 (플랫폼화 금지)

---

## 🟢 Phase 2-1 (표준화 · 안정성) — 완료

> 해커톤에서 “이 사람은 구조를 이해하고 만든다”는 신뢰를 주는 구간

모든 항목 **완료 및 Freeze**

| Task Name | 설명 | 우선순위 | 상태 |
|---|---|---:|---|
| **P2-1-A. File Loader 텍스트 지원 완결** | `load_file()`이 `.log/.txt/.out`을 **kind=text**로 반환. `ToolResult.data.text` 포함. LogCop에서 tail fallback 최소화 | 🔴 High | ✅ 완료 |
| **P2-1-B. DIA Agent load_file 통합** | DIA의 CSV/PDF 로딩을 `load_file()`로 통일. Agent 내부에서 `pd.read_csv`, `pdfplumber.open` 직접 호출 제거 | 🔴 High | ✅ 완료 |
| **P2-1-C. Runner 단 normalize_context 강제** | Runner/UI → Agent 호출 직전에 **반드시** `normalize_context()` 적용. Agent는 dict/raw 입력을 신뢰하지 않음 | 🔴 High | ✅ 완료 |
| **P2-1-D. LLM UX 정책 공통화** | `llm_disabled / network_unreachable / missing_api_key / llm_call_failed` 등 상태코드 → UX 문구/이벤트명을 공통 유틸로 표준화 | 🟠 Medium | ✅ 완료 |
| **P2-1-E. Phase2 스모크 테스트 고정** | `smoke_context`, `smoke_file_loader`, `smoke_route`를 Phase2 기준으로 고정(텍스트 포함). CI 없이도 로컬에서 동일 결과 | 🟠 Medium | ✅ 완료 |
| **P2-1-L. Logging Baseline 추가 (권장 선행)** | 콘솔+파일 로깅, trace_id/session_id 상관관계, runner/router/tool/llm 주요 이벤트 기록. “리팩터링 안전망” | 🔴 High | ✅ 완료 |

### Phase 2-1 종료 조건
- Agent 코드에 **파일 직접 로딩 로직이 없음**(모두 `load_file()` 경유)
- 컨텍스트는 **항상 표준화된 AgentContext** 형태로 Agent에 들어감
- 폐쇄망/개방망 모두 **행동이 예측 가능**
- LLM 실패는 “예외”가 아니라 **상태 + UX**

### Phase 2-1 권장 진행 순서
1) **P2-1-A 완료**  
2) **P2-1-L 로깅 베이스라인 추가(커밋)**  
3) **P2-1-B DIA 통합(커밋)**  
4) **P2-1-C Runner normalize 강제(커밋)**  
5) **P2-1-D UX 공통화(커밋)**  
6) **P2-1-E 스모크 고정(커밋)**  

---

## 🟡 Phase 2-2 (Agent 품질 · 내부 구조) — 완료

> “에이전트가 생각하고 검증한다”는 인상을 주는 최소 구조

모든 항목 **완료 및 Freeze**

| Task Name | 설명 | 우선순위 | 상태 |
|---|---|---:|---|
| **P2-2-A. Planner/Executor/Reviewer 구조 명확화** | 현재 이벤트 나열 수준 → **명시적 단계 전환**(state-like)으로 정리. 각 단계 입력/출력 정의 | 🔴 High | ✅ 완료 |
| **P2-2-B. Reviewer 실질화 (Lite)** | 자동 승인 → 최소 품질 게이트: 산출물 존재/비어있음/실패 여부/필수 섹션 유무 점검 | 🔴 High | ✅ 완료 |
| **P2-2-C. AgentResult meta 표준화 확장** | `agent_id, mode, file_kind, llm_used, fallback_reason, artifacts_count` 등을 meta로 통일 | 🟠 Medium | ✅ 완료 |
| **P2-2-D. Audit Export 기능 구현** | Agent 실행 결과를 JSON/JSONL 형식으로 저장. Meta Contract v1 포함, workspace/audit/ 디렉토리에 저장, 설정 기반 제어(AUDIT_ENABLED 등) | 🟠 Medium | ✅ 완료 |

### Phase 2-2 종료 조건
- LLM 없이도 “똑똑하게 일한다”는 인상 제공
- Reviewer가 최소한의 품질 게이트 역할 수행

---

## 🔵 Phase 2-3 (플랫폼 관점) — **옵션 / 해커톤 범위 외**

> 아래 항목은 **플랫폼 PoC를 목표로 할 경우에만 진행**
> 해커톤 시간 제한 내에서는 **미수행이 정상**

| Task Name | 설명 | 우선순위 | 상태 |
|---|---|---:|---|
| **P2-3-A. Agent Capability 선언** | Agent별 `capabilities = {file_types, intents}` 선언 및 registry 등록 정보로 활용 | 🟡 Low | ⏳ Optional  |
| **P2-3-B. Router 신뢰도 계산 정제** | confidence 산출 근거를 코드/문서로 명확화(파일/키워드/폴백 가중치) | 🟡 Low | ⏳ Optional  |
| **P2-3-C. 실패 시나리오 문서화** | “언제 무엇을 포기하는가(LLM/파일/컨텍스트)”를 README에 명시 | 🟡 Low | ⏳ Optional  |
| **P2-3-D. Phase2 기준 README 갱신** | Phase1 대비 변경점(표준화/안정성/UX/로깅)을 정리 | 🟡 Low | ⏳ Optional  |

### Phase 2 종료 조건
- “데모용 해커톤 코드”가 아니라 **해커톤 데모에서 재현 가능하고 디버깅 가능한 에이전트 기반기 확보**
- 실행/재현/디버깅이 가능한 기본 운영 수준 확보

---

## 현재 상태 메모 (업데이트 로그)

- P2-1-A: `load_file()` 텍스트(kind=text) 반환 및 LogCop 연동 테스트 성공(폐쇄망/LLM_ENABLED true/false 모두 확인)
- P2-1-L: 로깅 베이스라인 구축 완료 - trace_id 지원, RotatingFileHandler, Agent Runner/LLM Client 로깅 통합
- P2-1-B: DIA Agent `load_file()` 통합 완료 - Agent 내부 파일 직접 로딩 제거
- P2-1-C: Runner 단 `normalize_context()` 강제 적용 완료 - Agent는 항상 표준화된 AgentContext를 받음
- P2-1-D: LLM UX 정책 공통화 완료 - `core/llm/ux.py` 모듈 생성(LLMUX dataclass, build_llm_ux/build_llm_event 함수), LLM 상태 코드(ok/llm_disabled/network_unreachable/missing_api_key/llm_call_failed)를 예외가 아닌 UX 상태로 처리, DIA/LogCop Agent 간 Planner→Executor→Reviewer UX 흐름 통일, executor.llm_used/executor.llm_fallback 이벤트로 LLM 사용 여부 명확화
- P2-1-E: Phase2 스모크 테스트 고정 완료 - `smoke_context`, `smoke_file_loader`, `smoke_route` 3개 테스트 및 실행 스크립트 추가, 테스트 fixtures 준비, `normalize_context()` session_id 기본값 처리 개선
- P2-2-A: Planner/Executor/Reviewer 구조 명확화 완료 - `core/agent/stages.py` 모듈 생성(StageContext, Plan, ExecutionResult, ReviewResult dataclass 정의), 표준 이벤트 헬퍼 함수(step_start/step_end/info/log/warn/error), `build_agent_meta()` 함수로 메타데이터 표준화, 파일 접근 헬퍼(`_file_get`, `_file_name_and_path`), DIA/LogCop Agent 모두 `_plan()/_execute()/_review()` 함수로 명시적 단계 분리 및 타입 안전성 확보, 각 단계의 입력/출력이 명확한 타입으로 정의됨
- P2-2-B: Reviewer 실질화 완료 - `core/agent/reviewer.py` 모듈 생성(ReviewSpec, ReviewOutcome dataclass, `review_execution()` 공통 Reviewer 엔진), 최소 품질 게이트 구현(산출물 존재 여부, markdown 필수 여부, markdown 최소 길이 체크, placeholder 탐지, 실행 실패 여부 점검), DIA/LogCop Agent 모두 `_review()` 함수에서 `review_execution()` 공통 엔진 사용하도록 통합, Agent별 스펙 차별화(DIA: markdown_min_chars=80, placeholder 금지 / LogCop: markdown_min_chars=50, placeholder 금지 약화), 승인/거절 판단 및 이슈/후속 조치 메시지 표준화
- P2-2-C: AgentResult meta 표준화 확장 완료 - ExecutionResult에 debug/llm_status/llm_reason/llm_model 필드 확장, `build_agent_meta()` v1 도입(approved, llm, review, trace_id 구조화된 메타데이터), legacy 필드(llm_used 등) 유지로 하위 호환 보장, Chainlit UI에 Meta 요약/Reviewer issues·followups 렌더링 추가, dict/객체 혼용 이벤트 방어 로직 추가(`_ev_get`, `_meta_get`, `_infer_event_type` 등), `smoke_meta` 테스트 포함 전체 smoke 테스트 PASS, DIA/LogCop Agent 모두 mode="p2-2-c"로 업데이트
- P2-2-D: Audit Export 기능 구현 완료 - `core/agent/audit.py` 모듈 생성(`build_audit_entry`, `export_audit_json`, `append_audit_jsonl`, `export_and_append` 함수), Meta Contract v1 포함한 audit 엔트리 생성, 단건 JSON 및 JSONL append 저장, `core/agent/runner.py`에 audit export 통합(best-effort 방식, 실패해도 전체 실행 중단 안 함), 설정 기반 제어(AUDIT_ENABLED, AUDIT_STORE_MESSAGE, AUDIT_MESSAGE_MAX_LEN, AUDIT_STORE_FILE_PATH), `workspace/audit/` 디렉토리에 저장, `core/tests/smoke_audit.py` 테스트 추가 및 `scripts/smoke.py`에 통합, `.gitignore`에 workspace/audit/ 추가

---

## Phase 2 종료 선언 (중요)

✅ Agent 실행은 **재현 가능**  
✅ 실패는 **예측 가능**  
✅ 구조는 **설명 가능**  

📌 **이후 작업은 “플랫폼”이 아닌 “Agent Intelligence”에 집중한다.**

➡ 다음 단계: **PHASE 3 – Hackathon Agent Intelligence**
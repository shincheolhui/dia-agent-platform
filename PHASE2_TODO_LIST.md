# Phase 2 남은 Task 정리 (공식)

## Phase 2 목표 요약

> **“Agent 실행의 표준화 + 신뢰 가능한 내부 품질 확보”**
> → LangGraph·대규모 기능 확장이 아니라, **플랫폼으로서 완성도**를 끌어올리는 단계

---

## 🟢 Phase 2-1 (표준화 · 안정성) — *거의 완료, 일부 마무리*

| Task Name                                 | 설명                                                                                  | 우선순위      | 상태       |
| ----------------------------------------- | ----------------------------------------------------------------------------------- | --------- | -------- |
| **P2-1-A. File Loader 텍스트 지원 완결**         | `load_file()`이 `.log/.txt/.out`을 **정식 text kind**로 반환하도록 확장 (현재 LogCop fallback 제거) | 🔴 High   | 🔧 거의 완료 |
| **P2-1-B. DIA Agent load_file 통합**        | DIA의 CSV/PDF 로딩을 `load_file()` 단일 진입점으로 통합                                          | 🔴 High   | ⏳ 대기     |
| **P2-1-C. Runner 단 normalize_context 강제** | Runner/UI → Agent 진입 전에 항상 `normalize_context()` 적용                                 | 🔴 High   | ⏳ 대기     |
| **P2-1-D. LLM UX 정책 공통화**                 | `LLM_ENABLED`, `network_unreachable`, `llm_disabled` 등의 UX 문구를 공통 유틸로 승격            | 🟠 Medium | ⏳ 대기     |
| **P2-1-E. Phase2 스모크 테스트 고정**             | context / file_loader / routing 스모크 테스트를 “Phase2 기준”으로 고정                           | 🟠 Medium | ⏳ 대기     |

➡️ **Phase 2-1 종료 조건**

* Agent 코드에 “파일 직접 로딩” 로직이 없음
* 폐쇄망/개방망 모두 **행동이 예측 가능**
* LLM 실패는 *에러가 아니라 상태*

---

## 🟡 Phase 2-2 (Agent 품질 · 내부 구조 개선)

| Task Name                                        | 설명                                                              | 우선순위      |
| ------------------------------------------------ | --------------------------------------------------------------- | --------- |
| **P2-2-A. Planner / Executor / Reviewer 구조 명확화** | 현재 “로그 이벤트” 수준인 단계를 **명시적 State 전환 구조**로 정리                     | 🔴 High   |
| **P2-2-B. Reviewer 실질화 (Lite)**                  | 단순 승인 → “산출물 유효성 체크” (파일 수, 비어 있음, 실패 여부)                       | 🔴 High   |
| **P2-2-C. AgentResult Meta 확장**                  | `mode`, `llm_used`, `fallback_reason`, `file_kind` 등을 meta로 표준화 | 🟠 Medium |
| **P2-2-D. Rule-based Insight 품질 상향**             | CSV/Log 규칙 인사이트를 “LLM 부재 환경에서도 납득 가능” 수준으로 개선                   | 🟠 Medium |

➡️ **Phase 2-2 종료 조건**

* LLM 없이도 “Agent가 똑똑하다”는 인상
* Reviewer가 최소한의 품질 게이트 역할 수행

---

## 🔵 Phase 2-3 (플랫폼 관점 마무리)

| Task Name                       | 설명                                                | 우선순위      |
| ------------------------------- | ------------------------------------------------- | --------- |
| **P2-3-A. Agent Capability 선언** | Agent마다 `capabilities = {file_types, intents}` 선언 | 🟠 Medium |
| **P2-3-B. Router 신뢰도 계산 정제**    | confidence 산출 근거를 코드/문서로 명확화                      | 🟠 Medium |
| **P2-3-C. 실패 시나리오 문서화**         | “이 플랫폼은 언제 무엇을 포기하는가”를 README에 명시                 | 🟡 Low    |
| **P2-3-D. Phase2 기준 README 갱신** | Phase1 대비 무엇이 달라졌는지 정리                            | 🟡 Low    |

➡️ **Phase 2 종료 조건**

* “데모용 해커톤 코드”가 아니라
* **내부 플랫폼 PoC로 제출 가능한 상태**

---

## 🔥 지금 기준 추천 진행 순서 (현실적)

1. **P2-1-A / B / C**
   → *표준 입력·도구·컨텍스트 완결*
2. **P2-2-A / B**
   → *Agent 품질 체감 상승*
3. **P2-3-A**
   → *Phase 3 (LangGraph / RAG) 진입 준비*

---

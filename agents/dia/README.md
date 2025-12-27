# DIA Agent

**Decision & Insight Automation Agent**

---

## 1. Agent 개요

**DIA Agent**는
자연어로 주어진 업무 지시를 해석하고, 스스로 **계획 → 실행 → 검증** 과정을 거쳐
최종 결과물(분석 결과, 시각화, 보고서 등)을 완성하는 **Multi-Agent 기반 업무 자동화 Agent**입니다.

이 Agent는 단순 질의응답(Chatbot)이 아니라,
**실제 업무를 수행하는 주체(Agent)**로 설계되었습니다.

---

## 2. DIA Agent의 목표

- 사용자의 자연어 업무 요청을 **구조화된 작업(Task)**으로 분해
- 데이터 분석, 문서 처리, 시각화 등 **실제 도구 실행**
- 결과를 스스로 검증하고 **수정 또는 승인 판단**
- 해커톤 환경에서 **Agent의 사고 과정이 명확히 보이도록 시각화**

---

## 3. Multi-Agent 역할 구성

DIA Agent는 내부적으로 3개의 역할을 수행합니다.

### 3.1 Planner Agent

- 사용자 요청 해석
- 업무 목표 정의
- 작업(Task) 목록 및 순서 수립

**예**

- “매출 데이터 분석 후 보고서 작성” → 데이터 로드 → 분석 → 그래프 생성 → 요약 → 보고서 작성

---

### 3.2 Executor Agent

- Planner가 정의한 Task를 순차 실행
- 실제 Tool 호출 담당

  - 파일 로딩
  - Pandas 분석
  - Matplotlib 시각화
  - 문서 초안 생성

---

### 3.3 Reviewer Agent

- Executor 결과 검증
- 요청 충족 여부 판단
- 수정 필요 시 Planner로 재요청
- 승인 시 최종 결과 확정

> 이 Reviewer 루프가 DIA를 “단순 자동화”가 아닌 **자기 검증(Self-checking) Agent**로 만듭니다.

---

## 4. 동작 흐름 요약

```text
User Input
   ↓
Planner Agent (계획 수립)
   ↓
Executor Agent (실행)
   ↓
Reviewer Agent (검증)
   ├─ 승인 → 최종 결과 반환
   └─ 수정 요청 → Planner로 회귀
```

이 흐름은 **LangGraph**로 구성되며, Chainlit UI에서는 각 단계가 **Step/Trace 형태로 시각화**됩니다.

---

## 5. 주요 기능

- 자연어 기반 업무 지시 처리
- CSV / XLSX / PDF 파일 분석
- 데이터 시각화(그래프 이미지 생성)
- 요약 및 보고서 초안 자동 생성
- Agent 사고 과정(계획/실행/검증) 시각화

---

## 6. DIA Agent 디렉토리 구조

```
agents/dia/
├─ agent.py            # DIA Agent 엔트리 (BaseAgent 구현)
├─ graph.py            # LangGraph 구성 (Planner/Executor/Reviewer)
├─ tools.py            # (선택) DIA 전용 Tool
├─ schemas.py          # (선택) DIA 확장 State 스키마
├─ prompts/
│  ├─ planner.md       # Planner 프롬프트
│  ├─ executor.md      # Executor 프롬프트
│  └─ reviewer.md      # Reviewer 프롬프트
└─ README.md           # DIA Agent 설명 문서
```

---

## 7. 확장성

DIA Agent는 **플러그인 형태의 Agent**로 설계되어 다음이 가능합니다.

- 동일한 플랫폼 위에 다른 Agent 추가

  - 예: 로그 분석 Agent, 정책 검토 Agent

- 공통 Tool(`core/tools`) 재사용
- Agent별 Prompt / Graph 독립 관리

---

## 8. 해커톤 관점 설계 포인트

- **Agent성 명확**: Planner–Executor–Reviewer 구조
- **데모 안정성**: 로컬 실행 중심, 외부 의존 최소화
- **시각적 설득력**: Chainlit Step/Trace 활용
- **확장 메시지**: “DIA는 하나의 Use Case일 뿐”

---

## 9. 한 줄 요약 (발표용)

> **“DIA Agent는 자연어 업무 지시를 받아, <br/>
> 스스로 계획·실행·검증하여 결과물을 완성하는 Multi-Agent 시스템입니다.”**

---

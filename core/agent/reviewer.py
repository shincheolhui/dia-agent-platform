# core/agent/reviewer.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.artifacts.types import ArtifactRef


@dataclass
class ReviewSpec:
    """
    Reviewer 품질 게이트 스펙(공통).

    - 최소 산출물(artifact) 존재 여부
    - markdown 산출물 존재 여부
    - markdown 내용이 너무 짧거나 placeholder인지 여부
    - exec_res.ok, error_code 등을 참고하여 승인/거절 판단

    NOTE:
    - 파일 내용(artifact 파일)을 직접 읽는 것은 선택 사항.
      지금 단계(P2-2-B)에서는 "읽지 않아도 되는 기본 게이트"를 먼저 고정한다.
    """

    # 산출물 관련
    require_artifacts: bool = True
    min_artifacts: int = 1
    require_markdown: bool = True

    # markdown 품질(가벼운 휴리스틱)
    markdown_min_chars: int = 80
    markdown_disallow_placeholders: bool = True

    # placeholder 탐지 키워드(필요 시 추가)
    placeholder_markers: Tuple[str, ...] = (
        "(텍스트 추출 실패",
        "지원하지 않는 파일 형식",
        "파일 로드에 실패",
        "파일 미첨부",
        "unknown_error",
    )

    # 실패여도 승인 가능한 예외 케이스를 허용할지 (기본 False)
    allow_approve_when_exec_failed: bool = False


@dataclass
class ReviewOutcome:
    approved: bool
    issues: List[str]
    followups: List[str]
    details: Dict[str, Any]


def _is_markdown(a: ArtifactRef) -> bool:
    # kind="markdown" 우선
    if getattr(a, "kind", None) == "markdown":
        return True
    # mime_type이 있다면 힌트로 사용
    mt = getattr(a, "mime_type", None) or ""
    if isinstance(mt, str) and "markdown" in mt.lower():
        return True
    # 파일 확장자 힌트
    p = getattr(a, "path", None) or ""
    if isinstance(p, str) and p.lower().endswith(".md"):
        return True
    n = getattr(a, "name", None) or ""
    if isinstance(n, str) and n.lower().endswith(".md"):
        return True
    return False


def _safe_len_text(text: Any) -> int:
    if text is None:
        return 0
    try:
        return len(str(text))
    except Exception:
        return 0


def review_execution(
    *,
    spec: ReviewSpec,
    exec_ok: bool,
    exec_text: Optional[str],
    artifacts: Sequence[ArtifactRef],
    error_code: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> ReviewOutcome:
    """
    공통 Reviewer 엔진.
    - exec_result/plan 등 어떤 구조든 붙일 수 있도록 입력을 평탄화했다.
    """
    issues: List[str] = []
    followups: List[str] = []
    details: Dict[str, Any] = dict(extra or {})

    a_list = list(artifacts or [])
    details["artifacts_count"] = len(a_list)
    details["exec_ok"] = bool(exec_ok)
    details["error_code"] = error_code
    details["exec_text_len"] = _safe_len_text(exec_text)

    # 0) 실행 실패 처리
    if not exec_ok and not spec.allow_approve_when_exec_failed:
        issues.append("Executor 단계가 실패 상태로 종료되었습니다.")
        if error_code:
            issues.append(f"- error_code: {error_code}")
        followups.append("에러 코드/이벤트 로그를 확인하고, 입력 파일/설정을 점검하세요.")

    # 1) 산출물 존재
    if spec.require_artifacts:
        if len(a_list) < spec.min_artifacts:
            issues.append(f"산출물(artifact)이 부족합니다. (min={spec.min_artifacts}, actual={len(a_list)})")
            followups.append("CSV/PDF/LOG 파일을 다시 업로드하고 동일 요청으로 재시도하세요.")

    # 2) markdown 필수
    md_list = [a for a in a_list if _is_markdown(a)]
    details["markdown_count"] = len(md_list)
    if spec.require_markdown and not md_list:
        issues.append("Markdown 보고서 산출물이 없습니다.")
        followups.append("보고서(markdown) 산출 로직이 정상 동작하는지 확인하세요.")

    # 3) markdown 품질(초경량)
    # - exec_text가 "보고서 생성" 계열이면 길이로 1차 체크
    if spec.require_markdown and spec.markdown_min_chars > 0:
        if _safe_len_text(exec_text) < spec.markdown_min_chars:
            # exec_text는 Agent가 반환하는 실행 요약일 수 있으니, 너무 공격적이면 조건 완화 가능
            # 현재는 "품질 신호"로만 사용: markdown 부족 이슈가 이미 있으면 중복 추가하지 않는다.
            if not any("Markdown" in x for x in issues):
                issues.append(
                    f"보고서 텍스트가 너무 짧습니다. (len<{spec.markdown_min_chars})"
                )
                followups.append("입력 파일이 너무 작거나, 로더가 preview만 반환했는지 확인하세요.")

    # 4) placeholder 탐지(텍스트 기반)
    if spec.markdown_disallow_placeholders and exec_text:
        low = str(exec_text).lower()
        for m in spec.placeholder_markers:
            if str(m).lower() in low:
                issues.append(f"보고서가 placeholder/에러 안내 중심으로 보입니다. (marker='{m}')")
                followups.append("실제 데이터가 로딩/추출되었는지 확인하고, 파일을 다시 업로드해보세요.")
                break

    approved = len(issues) == 0
    return ReviewOutcome(approved=approved, issues=issues, followups=followups, details=details)

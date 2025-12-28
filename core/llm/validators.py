from __future__ import annotations

def ensure_sections(md: str) -> str:
    required = ["## 요약", "## 인사이트", "## 권장 액션", "## 주의사항"]
    missing = [h for h in required if h not in md]
    if not missing:
        return md
    # 형식이 깨지면 그대로 반환하되, 상단에 경고를 추가
    warn = "⚠️ LLM 출력 형식이 일부 누락되었습니다: " + ", ".join(missing)
    return warn + "\n\n" + md

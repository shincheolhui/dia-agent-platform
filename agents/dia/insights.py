from __future__ import annotations

import pandas as pd


def _top_k_share(s: pd.Series, k: int = 3) -> list[tuple[str, int, float]]:
    vc = s.value_counts(dropna=False)
    total = int(vc.sum())
    out = []
    for val, cnt in vc.head(k).items():
        share = (float(cnt) / float(total) * 100.0) if total else 0.0
        out.append((str(val), int(cnt), round(share, 1)))
    return out


def rule_based_insights(df: pd.DataFrame) -> str:
    """
    LLM 없이도 의미 있는 '요약/인사이트/액션/주의사항'을 생성.
    반환은 Markdown 섹션(## 포함) 형태.
    """
    insights: list[str] = []
    actions: list[str] = []
    cautions: list[str] = []

    # 1) 숫자 컬럼 분석
    num = df.select_dtypes(include="number")
    if not num.empty:
        desc = num.describe().T
        desc["range"] = desc["max"] - desc["min"]
        desc = desc.sort_values("range", ascending=False)

        # 변동폭 상위 1~2개 지표만 요약 (너무 많으면 보고서가 지저분)
        for col in desc.index[:2]:
            row = desc.loc[col]
            insights.append(
                f"- `{col}` 변동폭이 큽니다: min={row['min']:.3f}, p50={row['50%']:.3f}, max={row['max']:.3f} (mean={row['mean']:.3f})."
            )

        # 이상치 후보 안내(상/하위 10%)
        col0 = desc.index[0]
        low = num[col0].quantile(0.1)
        high = num[col0].quantile(0.9)
        insights.append(f"- `{col0}` 기준 상/하위 10% 임계값: <= {low:.3f}, >= {high:.3f}. 해당 구간 레코드 원인 점검을 권장합니다.")
        actions.append(f"- `{col0}` 상/하위 10% 레코드를 추출하여 `department/owner/status`와 교차분석(피벗)하세요.")
    else:
        insights.append("- 숫자형 지표가 없어 정량 인사이트 생성이 제한됩니다.")
        actions.append("- 범주형 컬럼의 빈도/추세(날짜) 분석 위주로 보고서를 구성하세요.")

    # 2) 범주형 컬럼 분석: “유니크 비율”이 낮은 컬럼만 선택
    cat = df.select_dtypes(exclude="number")
    if not cat.empty:
        n = len(df)
        candidate_cols = []
        for col in cat.columns:
            uniq = df[col].nunique(dropna=False)
            uniq_ratio = (uniq / n) if n else 1.0
            # 유니크 비율이 너무 높으면(예: record_id/date) 제외
            if uniq_ratio <= 0.5:
                candidate_cols.append(col)

        for col in candidate_cols[:3]:
            top3 = _top_k_share(df[col], k=3)
            if top3:
                formatted = ", ".join([f"`{v}` {c}건({p}%)" for v, c, p in top3])
                insights.append(f"- `{col}` 분포 상위: {formatted}.")

        # 대표 권장 액션
        if candidate_cols:
            actions.append(f"- `{candidate_cols[0]}` 기준으로 주요 지표(성공률/지연/사고건수)의 그룹별 평균을 비교하세요.")

    # 3) 요약/주의사항
    summary = [
        "- 업로드된 데이터를 기반으로 기본 통계 및 분포를 확인했습니다.",
        "- 변동폭이 큰 지표와 주요 범주 분포를 중심으로 원인 후보를 정리했습니다.",
        "- 추가 교차분석을 위한 실행 액션을 포함했습니다.",
    ]

    cautions.append("- 본 인사이트는 간단 규칙 기반으로 생성되었으며, 추가 검증이 필요합니다.")
    cautions.append("- 데이터 정의(단위/산출 로직)와 수집 기간/표본 대표성 확인 후 해석하세요.")

    md = []
    md.append("## 요약\n" + "\n".join(summary))
    md.append("\n## 인사이트\n" + "\n".join(insights[:6]))
    md.append("\n## 권장 액션\n" + "\n".join(actions[:4] if actions else ["- 추가 분석 항목을 정의하세요."]))
    md.append("\n## 주의사항\n" + "\n".join(cautions))
    return "\n".join(md)

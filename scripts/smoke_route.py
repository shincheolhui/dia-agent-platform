from __future__ import annotations

from core.agent.registry import build_default_registry
from core.agent.router import decide_agent_id


def main():
    reg = build_default_registry()
    available = reg.list_ids()

    case1 = decide_agent_id(
        user_message="요약해줘",
        context={"uploaded_files": [{"name": "a.csv", "path": "x/a.csv"}]},
        available_agent_ids=available,
        default_agent_id="dia",
    )
    print("case1:", case1)

    case2 = decide_agent_id(
        user_message="Exception stacktrace error 발생",
        context={},
        available_agent_ids=available,
        default_agent_id="dia",
    )
    print("case2:", case2)

    case3 = decide_agent_id(
        user_message="그냥 인사",
        context={},
        available_agent_ids=available,
        default_agent_id="dia",
    )
    print("case3:", case3)

if __name__ == "__main__":
    main()

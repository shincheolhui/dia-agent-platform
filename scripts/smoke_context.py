# scripts/smoke_context.py
from core.context import normalize_context


def main():
    raw = {
        "session_id": "s1",
        "uploaded_files": [{"name": "a.csv", "path": "workspace/uploads/a.csv", "mime": "text/csv"}],
        "something_else": 123,
    }
    ctx = normalize_context(raw)
    print(ctx)
    print(ctx.to_dict())


if __name__ == "__main__":
    main()

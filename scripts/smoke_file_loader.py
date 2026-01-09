# scripts/smoke_file_loader.py
from core.tools.file_loader import load_file


def main():
    # 1) CSV 테스트
    csv_path = "workspace/uploads/20260109_071705__csv_upload_test_data_utf8bom.csv"
    csv_res = load_file(csv_path)
    print("=== CSV ===")
    print("ok:", csv_res.ok)
    print("summary:", csv_res.summary)
    print("error:", csv_res.error)
    if csv_res.data:
        print("kind:", csv_res.data.get("kind"))
        print("shape:", csv_res.data.get("shape"))
        print("preview_csv:\n", (csv_res.data.get("preview_csv", "") or "")[:300])

    # 2) TEXT 테스트 (.log/.txt/.out 중 실제 존재 파일로 교체)
    text_path = "workspace/uploads/20260109_074941__ai-agent-hack.log"
    text_res = load_file(text_path)
    print("\n=== TEXT ===")
    print("ok:", text_res.ok)
    print("summary:", text_res.summary)
    print("error:", text_res.error)
    if text_res.data:
        print("kind:", text_res.data.get("kind"))
        print("ext:", text_res.data.get("ext"))
        print("text_truncated:", text_res.data.get("text_truncated"))
        print("text(head):\n", (text_res.data.get("text", "") or "")[:300])


if __name__ == "__main__":
    main()

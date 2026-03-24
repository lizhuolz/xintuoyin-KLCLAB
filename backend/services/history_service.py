from __future__ import annotations

import json
from pathlib import Path


def log_to_history(history_dir: Path, conv_id: str, user_msg: str, ai_msg: str) -> None:
    path = history_dir / f"{conv_id}.json"
    history = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": ai_msg})

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[Logging Error] {exc}")

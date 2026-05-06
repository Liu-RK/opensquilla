from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime_src"))

from src.router.inference.core import InferenceCore  # noqa: E402
from src.router.inference.types import InferenceRequest  # noqa: E402


def _serialize(obj):
    if is_dataclass(obj):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    return obj


def _load_request(args) -> InferenceRequest:
    if args.request_json:
        payload = json.loads(Path(args.request_json).read_text(encoding="utf-8"))
        return InferenceRequest(
            current_user_text=payload["current_user_text"],
            history_user_texts=payload.get("history_user_texts", []),
            prev_assistant_text=payload.get("prev_assistant_text"),
            prev_assistant_usage=payload.get("prev_assistant_usage"),
            prev_route_decisions=payload.get("prev_route_decisions", []),
            flags_text_override=payload.get("flags_text_override"),
            context_metadata=payload.get("context_metadata", {}),
        )
    return InferenceRequest(
        current_user_text=args.current_user_text,
        history_user_texts=args.history_user_texts or [],
        prev_assistant_text=args.prev_assistant_text,
        prev_assistant_usage=None,
        prev_route_decisions=[],
        context_metadata={},
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(ROOT))
    parser.add_argument("--config", default=str(ROOT / "router.runtime.yaml"))
    parser.add_argument("--request-json")
    parser.add_argument("--current-user-text")
    parser.add_argument("--history-user-texts", nargs="*")
    parser.add_argument("--prev-assistant-text")
    parser.add_argument("--use-aux-head", action="store_true")
    args = parser.parse_args()

    if not args.request_json and not args.current_user_text:
        raise SystemExit("provide --request-json or --current-user-text")

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    core = InferenceCore.from_model_dir(
        args.model_dir,
        config=config,
        use_aux_head=args.use_aux_head,
    )
    result = core.predict(_load_request(args))
    print(json.dumps(_serialize(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

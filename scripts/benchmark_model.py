"""Measure actual stream TTFT and decode speed against the local vLLM endpoint."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import statistics
import time

import httpx

CASES = [
    ("arithmetic", [{"role": "user", "content": "只回答一个数字：17乘以19等于多少？"}], "323"),
    ("chinese", [{"role": "user", "content": "用中文给摄影初学者三条构图建议，每条不超过30字。"}], None),
    ("memory", [{"role": "user", "content": "我的相机是索尼A7M4，请记住。"}, {"role": "assistant", "content": "记住了，你的相机是索尼A7M4。"}, {"role": "user", "content": "我的相机是什么？只回答相机型号。"}], "A7M4"),
]


def measure(client, model, messages):
    start = time.perf_counter()
    first = last_token = None
    content = ""
    usage = None
    with client.stream("POST", "/v1/chat/completions", json={"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 256, "stream": True, "stream_options": {"include_usage": True}, "chat_template_kwargs": {"enable_thinking": False}}) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data: ") or line[6:] == "[DONE]":
                continue
            item = json.loads(line[6:])
            if item.get("error"):
                raise RuntimeError(item["error"])
            if item.get("usage"):
                usage = item["usage"]
            delta = (item.get("choices") or [{}])[0].get("delta", {}).get("content", "")
            if delta:
                now = time.perf_counter()
                if first is None:
                    first = now
                last_token = now
                content += delta
    finish = time.perf_counter()
    if first is None or not usage:
        raise RuntimeError("Missing stream output or usage")
    return {"answer": content, "firstTokenSeconds": first - start, "totalSeconds": finish - start, "usage": usage, "generationTokensPerSecond": (usage["completion_tokens"] - 1) / (finish - first) if finish > first else None, "lastContentSeconds": last_token - start}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3.8-27b")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("benchmark-results/model.json"))
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    records = []
    with httpx.Client(base_url=args.url.rstrip("/"), trust_env=False, timeout=180) as client:
        warmup = measure(client, args.model, [{"role": "user", "content": "只回答：准备好了。"}])
        for trial in range(args.repeat):
            for name, messages, expected in CASES:
                record = {"case": name, "trial": trial + 1, **measure(client, args.model, messages)}
                if expected:
                    assert expected in record["answer"], record
                if name == "chinese":
                    assert len(record["answer"]) >= 15, record
                records.append(record)
                print(json.dumps(record, ensure_ascii=False), flush=True)
    summaries = {}
    for name, _, _ in CASES:
        subset = [record for record in records if record["case"] == name]
        summaries[name] = {"trials": len(subset), "medianFirstTokenSeconds": statistics.median(record["firstTokenSeconds"] for record in subset), "medianGenerationTokensPerSecond": statistics.median(record["generationTokensPerSecond"] for record in subset), "medianTotalSeconds": statistics.median(record["totalSeconds"] for record in subset)}
    result = {"measuredAt": datetime.now(timezone(timedelta(hours=8))).isoformat(), "model": args.model, "thinking": False, "maxTokens": 256, "temperature": 0.2, "warmup": warmup, "cases": records, "summary": summaries, "measurement": "TTFT=request to first nonempty content delta; decode=(completion_tokens-1)/(stream_finish-first_content). Includes EOS/final stream overhead; not a standardized benchmark."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASSED:", json.dumps(summaries), flush=True)


if __name__ == "__main__":
    main()

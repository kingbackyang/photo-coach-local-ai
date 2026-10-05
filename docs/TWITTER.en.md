# Twitter / X launch post

Draft only. Attach [the English launch card](../assets/twitter-card-en.png).

```text
I open-sourced Photo Coach: Qwen3.8-27B GGUF on one RTX 3090, Windows + Docker. HTTPS chat via a small VPS, streaming + automatic queuing.

Warm short-prompt test: ~0.50s TTFT, 7.72 tokens/s.

Code, guide & raw benchmarks:
https://github.com/kingbackyang/photo-coach-local-ai
```

## Image alt text

Photo Coach open-source launch card. Qwen3.8-27B GGUF runs on one RTX 3090 with Windows and Docker, with HTTPS chat, streaming replies and automatic queuing. The graphic includes a screenshot of the actual chat page and measured results: approximately 0.50 seconds to the first token and 7.72 tokens per second. Measurements are warm short-prompt medians from three runs, with a 2048-token context and thinking disabled.

## Measurement details

- The headline numbers are from the 27B model, using `UD-Q4_K_M`, on an RTX 3090 with 24 GB VRAM.
- These are warm, short-prompt medians, not cold-start or long-context results. The Chinese short-reply case had a median first-token latency of 0.498 seconds and median decode speed of 7.724 tokens/s.
- One request generates at a time; additional requests join a FIFO queue. Waiting time is not included in the local model benchmark.
- Raw records: [rtx3090-20261005.json](../benchmarks/rtx3090-20261005.json). Full methods: [benchmark guide](BENCHMARKS.zh-CN.md).
- The website currently supports chat. Image generation has not been connected or benchmarked.
- The launch card is a promotional composition made with the built-in imagegen tool, using the actual application screenshot as a supporting insert. It is not an output from the local Qwen image model.

The post is within the ordinary 280-character limit when the repository URL is counted as 23 characters. Additional links or hashtags may change that count.

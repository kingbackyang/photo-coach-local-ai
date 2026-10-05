# English launch card generation prompt

Tool: built-in imagegen. Supporting insert: `assets/chat-demo.png`, the actual application screenshot. Final asset: `assets/twitter-card-en.png`.

```text
Use case: ads-marketing.
Asset type: English Twitter/X launch graphic, landscape 16:9, high resolution, one final polished image.
Primary request: compose a beautiful editorial launch card for the real open-source project "Photo Coach", a chat website running Qwen3.8-27B GGUF on one consumer RTX 3090 with Windows + Docker and a small cloud server relay.
Input image 1 is a supporting insert: the actual Photo Coach chat page screenshot. Preserve the screenshot's real content, including its Chinese UI and real reply. Place it intact inside an elegant thin browser-like panel on the right. Do not translate or invent any UI messages. Do not invent screenshots.
Style: premium calm technology editorial, warm ivory canvas #F7F7F0, deep forest green #285C49, ink black #192721, very subtle pale sage accents. Crisp highly legible modern sans serif typography, generous negative space, strong grid, sophisticated restrained print/poster quality. A faint photographic brushed-metal edge texture or subtle depth is welcome, but avoid neon, futuristic circuitry, clutter, gradients that impair readability, or generic AI robot art.
Composition: left 45 percent holds the headline and model/hardware; right 55 percent holds the real screenshot in a slightly raised panel. Lower band spanning both columns has two large benchmark numbers with labels. Bottom footer has a concise honest measurement qualifier and repository identity. Keep ample safe margins and readable type even on a phone.
Render the following exact English text once each, spell precisely:
Top small pill: "OPEN SOURCE"
Project headline, very large: "Photo Coach"
Main claim under headline: "27B. One RTX 3090."
Technical subtitle: "Qwen3.8-27B GGUF"
Second subtitle: "Windows + Docker"
Short feature line: "HTTPS chat · Streaming · Automatic queue"
Benchmark band left large number: "~0.50 s"
Label directly below: "Time to first token"
Benchmark band right large number: "7.72 tokens/s"
Label directly below: "Generation speed"
Small condition text: "Warm short-prompt median · 3 runs · 2048-token context · Thinking off"
Footer repository identity: "github.com/kingbackyang/photo-coach-local-ai"
Keep the screenshot's existing Chinese words only inside the screenshot; all surrounding graphic copy must be English.
Factual constraints: The numbers are measurements from the 27B model, not the 0.6B smoke-test model; do not mention 0.6B. This is single-request-at-a-time inference with queuing, not parallel GPU generation. Do not claim image generation, server-side GPU inference, free cloud compute, universal benchmarks, or throughput beyond 7.72 tokens/s. No invented plots, awards, badges, extra logos or text. No passwords, public server IP addresses, personal information or watermark.
```

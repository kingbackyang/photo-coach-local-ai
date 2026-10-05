# Twitter / X 发布草稿

这些是可复用的文案，尚未代为发布。仓库链接已放入正文。英文推文可配 [英文发布卡片](../assets/twitter-card-en.png)，也可使用真实网页截图 `assets/chat-demo.png`。英文文案、图片说明与测速条件见 [TWITTER.en.md](TWITTER.en.md)。不要附上自己的公网访问密码、FRP 令牌或服务器私有配置。

## 中文短帖

开源了 Photo Coach：单张 RTX 3090 在 Windows 上跑 Qwen3.8-27B GGUF，用小云服务器转发成 HTTPS 聊天网站。支持流式回复、自动排队和取消。

预热后中文短回复实测：首个输出约 0.50 秒，生成约 7.72 tokens/s。

完整安装教程、部署脚本与原始测速记录：
https://github.com/kingbackyang/photo-coach-local-ai

## English short post

I open-sourced Photo Coach: Qwen3.8-27B GGUF on one RTX 3090, Windows + Docker. HTTPS chat via a small VPS, streaming + automatic queuing.

Warm short-prompt test: ~0.50s TTFT, 7.72 tokens/s.

Code, guide & raw benchmarks:
https://github.com/kingbackyang/photo-coach-local-ai

## 中文线程：逐条发布

### 1/6

把本地 3090 上的 Qwen3.8-27B 接到了公网聊天网页，并整理成开源项目 Photo Coach。

推理在自己的 Windows 电脑上，云服务器负责转发。包含完整教程、脚本和实测数据：
https://github.com/kingbackyang/photo-coach-local-ai

### 2/6

实际配置：RTX 3090 24GB、5800X、32GB 内存。

Windows + WSL2 + Docker，vLLM 0.31.0，固定源码版 GGUF 插件。27B 采用 UD-Q4_K_M，权重约 16.46GB，另有 0.93GB 配套 projector。

教程写到了驱动、磁盘、下载校验和镜像构建。

### 3/6

公网部分用 Ubuntu 小服务器 + Nginx + FRP WSS。模型仍在本地，云端不需要 GPU。

网页有访问密码、流式输出和自动排队；等待者看到位置，也能取消。单次生成，最多 16 条等待消息。

本机需要保持在线，电脑休眠后服务也会暂停。

### 4/6

实测，不用宣传数字代替：

预热后每个用例重复 3 次。中文短回复首个输出中位数 0.498 秒，生成速度中位数 7.72 tokens/s。

2048 tokens 上下文、单条生成、关闭深入思考。算术和多轮记忆也通过，原始 JSON 随仓库公开。

### 5/6

踩到的关键点：插件显示的包版本相同，不代表源码适配相同；分词器要用官方原模型配置；模型下载用 ModelScope 直连并做 SHA256；转发凭证和网页登录密码放在仓库外。

这些都写进了教程，方便按同一条件复现。

### 6/6

当前完成的是聊天。Qwen-Image-2.1 的 GGUF、VAE 和文本编码器已下载校验，生图推理和网页入口还没接入，因此暂不公布生图速度。

欢迎复现、提交问题和改进：
https://github.com/kingbackyang/photo-coach-local-ai

## 使用提示

短帖的中文字符在平台计数中可能按双宽字符处理，URL 通常单独计数。上述短帖和线程按普通 280 字符帖子规划，实际发布前在编辑器确认长度；若添加额外标签、图片说明或其他链接，请再次检查。

适合附图的是网页截图；不要用只有模型下载进度的截图暗示生图已经成功运行。若复测改了参数或得到新结果，应同步更新文案和测试记录。

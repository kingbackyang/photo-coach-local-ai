# Windows + RTX 3090：从空环境到本地 27B 聊天网站

本文对应 2026-10-05 实际跑通的配置。命令注明了在 Windows PowerShell 还是云服务器 Linux 上执行；不要把两个环境的命令混用。第一次安装按照顺序完成，每个阶段都有检查方法。

公网部分放在[公网发布教程](PUBLIC_DEPLOYMENT.zh-CN.md)。本地聊天先正常，再添加公网连接，这样出错时容易定位。

## 1. 最终会得到什么

你在浏览器输入问题，网页后端验证访问密码，把请求送给本机的 vLLM。vLLM 在 3090 上运行量化的 Qwen3.8-27B，网页逐步显示模型输出。

多人同时提问时，网站按已校验请求进入队列的顺序逐条处理。等待者能看到前面的消息数量，也能取消等待。每个浏览器标签页单独保存当前会话，刷新会丢失它；没有数据库，也没有把聊天历史永久保存到服务器的功能。

当前上下文限制为 2048 tokens，包含全部输入、聊天模板和输出。网页会先调用分词接口检查剩余空间，再安排生成。每次最多输出 1024 tokens，实际还受剩余上下文限制。

## 2. 硬件准备

### 实测电脑

| 部件 | 实测设备 | 为什么需要 |
| --- | --- | --- |
| 显卡 | NVIDIA RTX 3090，24 GB 显存 | 存放量化权重、KV cache 和推理临时数据 |
| CPU | AMD Ryzen 7 5800X，8 核 16 线程 | 运行 Windows、Docker、网页后端，以及编译插件 |
| 内存 | 32 GB | 容器、模型加载与系统共用；同时开大型软件会挤压内存 |
| 模型磁盘 | C 盘 SSD | 降低模型读盘与加载等待 |
| Docker 数据磁盘 | E 盘，容量较大 | 容器镜像与构建缓存占用明显多于模型本身 |
| 网络 | 本机能持续访问云服务器 | 公网转发需要本机主动连接服务器 |

这里证明的是该 3090 配置可运行，没有测量 12 GB、16 GB 显卡或 CPU 卸载方案。选择其他 GPU 时，要重新核算显存、调整编译架构并做实际验证。

### 磁盘空间怎样规划

- 聊天 GGUF 权重约 **16.46 GB**。
- 配套 `mmproj-BF16.gguf` 约 **0.93 GB**。
- 官方分词器、词表和配置约 **23 MB**。
- 生图可选的三个文件合计约 **10.02 GB**。
- 已下载的 vLLM 基础镜像显示约 **32.3 GB**；本地 GGUF 镜像约 **32.6 GB**。二者共享大量镜像层，不能简单相加成实际占盘量。
- SGLang 镜像在本次环境中显示约 **46.5 GB**。主线不需要同时保留它。
- 下载临时文件、Docker 构建缓存、升级时的旧镜像还会占空间。

建议模型盘留出至少 30–40 GB 给聊天模型与后续操作；如果要同时保留生图文件，留更多空间。Docker 盘建议先准备 100 GB 以上可用空间，安装多个框架时进一步增加。以上是容量规划建议，不是运行框架的硬性最小值。

权重下载使用 `.part` 临时文件，校验后重命名，不会为了完成一次下载再复制一份完整权重。已有文件也会做 SHA256 检查。

### 为什么选 GGUF Q4，没选 FP8

当前 27B FP8 下载文件超过单张 3090 的 24 GB 显存容量，还需考虑缓存和临时数据；因此本次全显卡运行采用 `UD-Q4_K_M`。这不代表所有 CPU 卸载、分层加载或多卡 FP8 方案都不能运行。

GGUF 是量化后的权重格式。文件名里的 Q4 描述量化方案，不表示每个张量都严格是 4 bit。网页、vLLM 和模型权重是三个不同部分。

## 3. 需要安装的软件

| 软件 | 实测版本 | 安装在哪 |
| --- | --- | --- |
| Windows 11 Pro | Build 26200.9457 | 本地电脑 |
| NVIDIA Windows 驱动 | 591.86 | 本地电脑 |
| WSL | 2.7.13，内核 6.18.33.2 | 本地电脑 |
| Docker Desktop | 4.93.0，Docker Engine 29.8.1 | 本地电脑 |
| Python | 3.12 | 本地电脑，网页后端用独立虚拟环境 |
| Git | 已安装的 Windows Git | 本地电脑，克隆与版本管理 |
| vLLM | 0.31.0 | Linux 容器内 |
| PyTorch | 2.13.0+cu130 | Linux 容器内 |
| CUDA runtime | 容器镜像内 CUDA 13.0.2 | Linux 容器内 |
| GGUF 插件 | 固定源码提交，包版本仍显示 0.0.5 | Linux 容器内 |
| FRP | 0.71.0 | 公网阶段才需要，本地客户端与云端服务端 |

不必把 vLLM 或 PyTorch 安装到 Windows 的网页 Python 虚拟环境。Windows 环境只负责轻量网页服务与辅助脚本；显卡推理依赖位于容器。

使用 Docker GPU 透传时，选择 WSL 2 后端和 Linux 容器。官方 GPU 文档明确列出 Windows NVIDIA 驱动、WSL 内核和 WSL 2 后端要求。[Docker GPU 文档](https://docs.docker.com/desktop/features/gpu/)

## 4. 安装 NVIDIA 驱动，确认显卡

从 [NVIDIA 官方驱动页面](https://www.nvidia.com/Download/index.aspx) 下载适合 RTX 3090 的 Windows 驱动。安装后按安装器提示重启。

普通 Windows PowerShell 执行：

```powershell
nvidia-smi
```

应看到 RTX 3090、驱动版本和约 24576 MiB 总显存。`nvidia-smi` 标题里的 CUDA 版本表示驱动支持的 CUDA 级别，不等于你已在 Windows 安装了对应 CUDA Toolkit。

WSL 使用 Windows 驱动提供的 GPU 接口。不要在 WSL 中额外安装 Linux NVIDIA 显示驱动，否则可能覆盖 WSL 的驱动映射。[NVIDIA CUDA on WSL 文档](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)

## 5. 安装 WSL 2

先在任务管理器 → 性能 → CPU 确认“虚拟化：已启用”。未启用时，到 BIOS/UEFI 开启 AMD SVM 或 Intel 的硬件虚拟化选项，具体菜单依主板而定。

在**管理员 PowerShell**中执行：

```powershell
wsl --install
```

按提示重启，再执行：

```powershell
wsl --update
wsl --set-default-version 2
wsl --version
wsl --status
```

若默认安装了 Ubuntu，按提示完成首次 Linux 用户创建。Docker 自带所需的 WSL 数据环境；本教程主要在 Windows PowerShell 中操作，不要求把项目复制到 Ubuntu 家目录。[Microsoft WSL 安装说明](https://learn.microsoft.com/en-us/windows/wsl/install)

只有安装器或系统提示需要重启时才重启；下载模型、启动网页、改 Nginx 配置通常不需要重启整台电脑。

## 6. 安装和设置 Docker Desktop

1. 打开 [Docker 官方 Windows 安装页面](https://docs.docker.com/desktop/setup/install/windows-install/)。
2. 下载 x86_64 安装器并安装。
3. 选择 WSL 2 后端，启动 Docker Desktop，阅读并接受其适用条款。
4. 确认运行的是 Linux containers。
5. 在 Settings → General 检查 WSL 2 engine 设置。
6. 在 Settings → Resources → Advanced 调整 Docker 数据位置，例如 E 盘。
7. 等待数据迁移完成，确认 Docker 能启动，再拉取大型镜像。

本次实际 Docker 虚拟磁盘位于 `E:\Docker\wsl\disk\docker_data.vhdx`。不同版本显示的设置名称或子目录可能不同。使用 Docker 提供的数据位置迁移功能，避免在 Docker 运行时直接移动或删除 VHDX 文件。[Docker WSL 后端说明](https://docs.docker.com/desktop/features/wsl/)

打开**新的普通 PowerShell**检查：

```powershell
docker version
docker info
```

如果提示找不到 `docker`，当前用户安装的 CLI 常见位置是：

```powershell
$dockerExe = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
& $dockerExe version
```

全用户安装的常见位置是 `C:\Program Files\Docker\Docker\resources\bin\docker.exe`。可将正确的 `resources\bin` 加入用户 PATH，重新打开终端，再使用简短的 `docker` 命令。

### 容器内 GPU 检查

执行 Docker 官方示例：

```powershell
docker run --rm --gpus all nvcr.io/nvidia/k8s/cuda-sample:nbody nbody -gpu -benchmark
```

能看到 GPU 设备和完成的计算结果，再进入模型阶段。首次执行会下载测试镜像。若出现找不到 GPU、驱动不兼容或 WSL 错误，先修复这一层，网页代码无法补救 GPU 透传问题。

## 7. 安装 Python 和 Git，获取项目

从 [Python 官方下载页](https://www.python.org/downloads/windows/) 安装 Python 3.12，并从 [Git 官方下载页](https://git-scm.com/downloads/win) 安装 Git for Windows。重新打开终端，检查：

```powershell
py -3.12 --version
git --version
```

这里固定 Python 3.12 是为了贴近已验证环境；不要直接把教程中的依赖装到已有的复杂 Conda 环境。此前基础环境的二进制依赖曾不匹配，独立虚拟环境避免相互影响。

在你选择的项目目录执行：

```powershell
Set-Location D:\project
git clone https://github.com/kingbackyang/photo-coach-local-ai.git
Set-Location .\photo-coach-local-ai
py -3.12 -m venv C:\AIInference\runtime\chat-venv
$python = 'C:\AIInference\runtime\chat-venv\Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
```

网络受限时，可按自己信任的镜像源配置 pip；例如本次使用腾讯云 PyPI 镜像下载网页依赖。不要随意运行未知镜像网站提供的脚本。

```powershell
& $python -m pip install -r requirements.txt --index-url https://mirrors.cloud.tencent.com/pypi/simple
```

网页环境锁定了 FastAPI、Uvicorn、HTTPX 等实际版本，见 `requirements.txt`。推理镜像另行固定，不受这个 Windows 虚拟环境影响。

## 8. 目录布局

```text
C:\AIModels\
  Qwen3.8-27B-GGUF\
    Qwen3.8-27B-UD-Q4_K_M.gguf
    mmproj-BF16.gguf
  Qwen3.8-27B-config\
    config.json
    tokenizer.json
    tokenizer_config.json
    chat_template.jinja
    merges.txt
    vocab.json
    generation_config.json
    preprocessor_config.json
  Qwen-Image-2.1-GGUF\        可选，当前未接入网页
C:\AIInference\runtime\
  chat-venv\                 网页 Python 虚拟环境
  frp\                       公网客户端
E:\Docker\
  wsl\                       Docker 数据
  huggingface\               容器缓存
%LOCALAPPDATA%\InferenceChat\
  settings.json              密码哈希、会话密钥、模型地址
  access.txt                 本地查看随机访问密码
  frpc.toml                  公网阶段才生成
  relay-token.txt            公网阶段才生成
  gateway.log
  relay.log
```

模型和运行时使用英文路径。模型目录不用放进 Git 仓库。系统用户名包含中文时，默认私有配置目录可能包含中文；需要全英文私有路径时，可先设置 `INFERENCE_CHAT_HOME`，例如 `C:\AIInference\private`，并在以后启动时保持这个环境变量一致。

## 9. 从 ModelScope 直连下载模型

项目的 `models.lock.json` 保存具体文件、仓库、文件版本、字节大小和 SHA256。聊天组不仅有 GGUF，还包括配套 projector 和官方分词器配置；不会误下载完整 BF16 或 FP8 权重。

先只查看清单：

```powershell
& $python scripts\download_modelscope.py --group chat --dry-run
```

确认 C 盘空间，再下载：

```powershell
& $python scripts\download_modelscope.py --group chat --root C:\AIModels
```

下载脚本关闭系统和环境变量代理读取，从 ModelScope 直连，以减少代理流量。GitHub、Docker Hub 或 PyPI 的网络配置和它互相独立。

下载中断后重新运行同一命令，会从 `.part` 文件继续。只有大小和 SHA256 都正确才会变为正式文件；终端中的 `VERIFIED` 才表示该文件完成验证。

只做一次小文件试下载：

```powershell
& $python scripts\download_modelscope.py --group chat --include config.json --root .cache\model-test
```

完整复核已下载文件：

```powershell
& $python scripts\download_modelscope.py --group chat --root C:\AIModels --verify-only
```

16 GB 文件的 SHA256 计算会读完整个文件，校验时看似没进度属于正常情况；不要把“文件存在”当成“校验通过”。

即使目前网页只做文字聊天，也保留 `mmproj-BF16.gguf`：本次固定版本的加载器实际需要这份配套文件。文件存在不表示网页已支持图像输入。

ModelScope 若删除或改动固定版本，脚本会失败而不是静默换新权重。先查看上游模型仓库、对照文件哈希，再决定是否更新清单。

## 10. 构建实际支持该模型的 vLLM GGUF 镜像

本次使用的插件包版本显示 `0.0.5`，但安装的是后续源码提交。直接安装 PyPI 的同名 `0.0.5` 发布包无法等价复现本次模型适配，必须固定源码提交。

插件编译使用容器中现有的 PyTorch，并关闭 build isolation，防止临时构建环境换掉 Torch/CUDA 组合。这与插件的官方源码构建流程一致。[插件源码说明](https://github.com/vllm-project/vllm-gguf-plugin/tree/e2b8ad532b8b5ea175100202c30430c1d2b5e6a8)

普通 Windows PowerShell 中执行：

```powershell
docker pull vllm/vllm-openai:v0.31.0
& $python scripts\prepare_image_build.py
docker build --network none --progress plain -t local/vllm-gguf:qwen38-e2b8ad5 docker/vllm-gguf
```

GitHub 下载需要本地代理时，只给构建准备脚本传入代理：

```powershell
& $python scripts\prepare_image_build.py --proxy http://127.0.0.1:7890
```

该地址只是本地 HTTP 代理示例，要换成自己的实际地址。模型下载脚本仍直连，不受这个选项影响。

构建准备脚本下载官方 GitHub 固定提交的源码，以及经过 PyPI SHA256 校验的 `gguf==0.19.0` wheel。它们存入被 Git 忽略的 `docker/vllm-gguf/vendor`。Docker 构建自身使用 `--network none`，所以不会在容器构建时再次访问 GitHub。

Dockerfile 针对 3090 编译 CUDA 架构 `8.6`，编译并发限制为 2，以控制内存占用。换显卡时，要按其实际 CUDA compute capability 设置 `--build-arg CUDA_ARCH=...`，并重新验证；本文没有测量其他显卡。

看到 `GGUF extension import verified` 和成功生成镜像，表示编译与导入完成。本次重新构建已实际通过；这仍不代替下面的模型推理检查。

## 11. 启动 27B 模型

确保当前没有另一个程序占用大部分显存。浏览器、视频应用也可能使用显存。

```powershell
.\scripts\start-model.ps1 -ModelRoot C:\AIModels -CacheRoot E:\Docker\huggingface
```

没有 E 盘时，换一个真实存在且有空间的缓存目录，例如 `C:\AIInference\cache`。若 Docker CLI 不在 PATH，给脚本加 `-Docker '完整的 docker.exe 路径'`。

脚本不会替换同名已有容器。已经创建过时用：

```powershell
docker start vllm-qwen38-27b
```

查看启动日志：

```powershell
docker logs --tail 100 vllm-qwen38-27b
docker ps
```

启动后检查接口：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/v1/models
```

列表里应出现 `qwen3.8-27b`。容器状态显示 running 不代表模型已经完成加载，以接口返回为准。

### 关键运行参数

| 参数 | 当前值 | 目的 |
| --- | --- | --- |
| `--gpus all` | 开启 | 让 Linux 容器访问本地 NVIDIA GPU |
| `--ipc host` | 开启 | 使用容器所需共享内存路径 |
| 宿主端口绑定 | `127.0.0.1:8000:8000` | 模型 API 只对本机开放 |
| 模型挂载 | `C:\AIModels` → `/models`，只读 | 不把大权重复制进镜像 |
| `--tokenizer` | 官方配置目录 | 使用原模型词表与模板 |
| `--hf-config-path` | 官方配置目录 | 指定架构配置 |
| `--served-model-name` | `qwen3.8-27b` | 网页调用的模型别名 |
| `--max-model-len` | `2048` | 给 24 GB 显存留出运行空间 |
| `--max-num-seqs` | `1` | 模型一次处理一条生成 |
| `--gpu-memory-utilization` | `0.90` | 限制框架计划使用的显存比例 |
| `--enforce-eager` | 开启 | 当前已验证的运行模式 |
| `--language-model-only` | 开启 | 当前网页只接文字推理 |
| offline 环境变量 | 开启 | 运行时使用已下载的本地文件 |

`0.90` 不是“只把权重放到显存的 90%”；模型、缓存和临时开销都要考虑。当前观察到整卡占用约 21.3 GiB，其中包含显卡的其他使用者；实际可用空间会随桌面应用变化。

修改这些参数后，应创建或更新自己的容器并重新测试。容器创建时的参数不会因为修改启动脚本而自动改变。

## 12. 启动本地网页

第一次初始化：

```powershell
& $python chat\setup.py
```

它生成随机访问密码、盐值、密码哈希与会话密钥，并限制私有目录权限。再次执行会保留现有配置。打开 `%LOCALAPPDATA%\InferenceChat\access.txt` 查看密码，不要把这个文件提交到 GitHub。

在前台启动网页，便于第一次查看报错：

```powershell
& $python -m uvicorn chat.app:app --host 127.0.0.1 --port 8088 --workers 1 --no-proxy-headers
```

打开 `http://127.0.0.1:8088/`，输入刚生成的密码，看到“模型在线”后发送一句中文问题。

这里必须保持 `--workers 1`：排队状态在一个进程的内存中，开多个 worker 会产生多个互相独立的队列。想横向扩容，需要改成共享队列或统一的任务调度系统。

### 设置自己的访问密码

```powershell
& $python chat\setup.py --set-password
```

终端会交互询问两次，不把密码写入命令行或 shell 历史。开源版要求至少 12 个字符；建议每个安装者使用自己的强密码。修改后会更新会话密钥，旧登录失效。

### 本地检查

另开 PowerShell、回到项目目录，重新设置 `$python` 变量，再执行：

```powershell
& $python scripts\verify_chat_gateway.py http://127.0.0.1:8088
& $python scripts\verify_chat_queue.py http://127.0.0.1:8088
& $python scripts\verify_queue_controlled.py
```

前两项连接实际模型；第三项启动独立的本地测试服务，不需要 GPU，也不读取你的真实密码。它检查顺序排队、每 5 秒状态更新、取消等待、停止生成后继续下一条。

## 13. SGLang、0.6B 和生图模型在哪里

本次环境曾先用 Qwen3-0.6B 验证 vLLM 与 SGLang 能在 Windows Docker 中使用显卡。27B 的实际网站采用上述 vLLM GGUF 插件路径。不要把“0.6B 在 SGLang 跑通”推断成“这个 27B GGUF 在 SGLang 已经验证”。

主线已经提供完整 27B 下载与启动流程，安装者不必为了启动这个网站再下载 0.6B 或 SGLang 镜像。初次排障时，可选用自己确认兼容的小模型检查 GPU 和 API，再换回大模型。

下载生图文件：

```powershell
& $python scripts\download_modelscope.py --group image --root C:\AIModels
```

这会下载约 10.02 GB：Qwen-Image-2.1 GGUF、VAE、Qwen3-VL 文本编码器。当前只完成文件下载和 SHA256 校验，网站没有生图入口，也没有公布生成耗时。后续生图推理还需匹配后端和接口，不能把文件放进目录就视为部署完成。

## 14. 本地常见故障

| 现象 | 先检查 | 常见处理 |
| --- | --- | --- |
| 桌面 Docker 快捷方式点击没窗口 | 托盘图标、`docker info` | 已在后台运行时，CLI 可用就能继续；GUI 与模型接口分别确认 |
| `docker` 找不到 | PATH 与安装方式 | 用完整 CLI 路径；重新打开终端 |
| 容器中看不到 GPU | Windows 驱动、WSL 2、nbody | 先修复 GPU 测试，不先修改网页 |
| CUDA OOM | `nvidia-smi`、其他模型容器 | 关闭不需要的 GPU 程序；保持当前上下文与单生成参数 |
| 不认识架构或 GGUF tensor | 插件提交、官方配置 | 固定源码重新构建；不要只看包版本 0.0.5 |
| 缺少 mmproj | 权重目录 | 下载同组 projector，并保留正确文件名 |
| 8000 端口已占用 | `docker ps`、端口监听 | 确认只有实际推理容器发布该端口，构建临时容器不应占它 |
| 网页提示模型准备中 | `/v1/models`、模型日志 | 等加载结束；检查模型别名与 upstream |
| 对话达到长度限制 | 历史输入长度 | 点“新对话”；本配置总上下文 2048 tokens |
| 下载看似完成但无法加载 | SHA256、`.part` | 重新校验，不将残缺文件改名强行使用 |

本地验证成功后，继续[公网发布教程](PUBLIC_DEPLOYMENT.zh-CN.md)。

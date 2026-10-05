# 把本地 3090 聊天网站接到公网

先完成[本地安装](INSTALLATION.zh-CN.md)，并确认 `http://127.0.0.1:8088/` 能登录和聊天。本节使用 Ubuntu 24.04 云服务器、FRP 0.71.0、Nginx 和 IP 地址 HTTPS。需要的是一台带公网 IPv4 的转发服务器，推理仍由家里的 3090 完成。

以下 `YOUR_SERVER_IP` 必须替换成你自己的真实公网 IPv4。仓库没有提供可供复制使用的个人服务器 IP、密码或转发令牌。

## 1. 公网链路怎么工作

```mermaid
flowchart LR
    U[浏览器用户] -->|HTTPS 3389| N[云服务器 Nginx]
    N -->|回环地址 18080| S[云端 FRPS]
    S <-->|本地主动建立的 WSS 443 连接| C[Windows FRPC]
    C -->|127.0.0.1:8088| W[FastAPI 网页后端与队列]
    W -->|127.0.0.1:8000| V[vLLM 容器 · RTX 3090]
```

本地电脑主动向服务器建立出站连接，因此通常不需要家里有公网 IP，也不需要在路由器上开放入站端口。服务器收到网页请求后，通过这条连接送到本地网页后端，再由后端调用模型。

云服务器会处理 HTTPS 明文请求和回复，因此它也属于你需要信任和管理的服务端。FRP 不是让第三方服务器完全看不到聊天内容的端到端加密产品。

这套架构使用 FRP 的 WebSocket over TLS 传输；IP HTTPS 证书由 Nginx 终止，`/~!frp` 路径转发到本机 FRPS。[FRP 网络与传输文档](https://gofrp.org/en/docs/features/common/network/network/)

## 2. 云服务器要准备什么

实测服务器是 Ubuntu 24.04、2 vCPU、4 GB 内存、70 GB 系统盘、6 Mbps 公网带宽。它没有 GPU，没有下载 27B 权重，也没有运行推理框架。

CPU 和内存主要用于 Nginx、FRP、系统服务。聊天文字流量较小，但访问人数、其他业务以及将来的图片输出都会影响带宽。这里记录的是已经运行成功的规格，不承诺所有更小套餐都能承担同样负载。

准备：

1. 一台你拥有管理员权限的 Ubuntu 24.04 服务器。
2. 真实公网 IPv4，以及云平台的防火墙或安全组控制权限。
3. 能执行 Linux 命令的途径：控制台“执行命令”、网页终端或已有 SSH。
4. 能上传两个文件的途径：控制台文件管理或已有 SFTP/SCP。
5. 服务器可访问系统软件仓库、PyPI 镜像和证书机构。

不需要为了下载 FRP 而先让服务器访问 GitHub。可以在有代理的 Windows 电脑下载，再上传到服务器。

### IP 测试和正式域名

本教程先用 IP 地址测试，不依赖购买域名。腾讯云截至 2026-09-28 的官方说明允许未解析域名、仅通过公网 IP 直接访问的测试暂不备案；若计划将域名解析到中国内地云资源正式使用，应提前按平台要求完成 ICP 备案。更换端口不改变相关要求。[腾讯云“是否需要备案”](https://cloud.tencent.com/document/product/243/19630/)

注册域名、域名实名认证、DNS 解析和 ICP 备案是不同事情。域名注册审核通过，不表示网站备案已经完成。

## 3. 端口清单和防火墙

| 所在位置 | 端口 | 作用 | 是否需要公网放行 |
| --- | --- | --- | --- |
| 云服务器 | TCP 80 | 证书 HTTP 校验和跳转 | 是 |
| 云服务器 | TCP 443 | FRPC 的 WSS 连接和旧入口跳转 | 是 |
| 云服务器 | TCP 3389 | 本教程选择的 HTTPS 网页入口 | 是 |
| 云服务器回环地址 | 127.0.0.1:7000 | FRPS 接收 Nginx 转发的连接 | 否 |
| 云服务器回环地址 | 127.0.0.1:18080 | FRP 转发出来的网页 | 否 |
| Windows 本机 | 127.0.0.1:8088 | FastAPI 网页后端 | 否 |
| Windows 本机 | 127.0.0.1:8000 | vLLM 模型 API | 否 |

这里的 3389 运行 HTTPS 网站，不是远程桌面服务。选择这个端口是本次部署方案；如果服务器已经有程序占用它，换一个浏览器允许访问且空闲的端口，并同步更新配置和防火墙。

在腾讯云轻量应用服务器控制台：实例详情 → 防火墙，确认 TCP 80、443、3389 入站规则允许访问。局域网浏览器能打开网站不能证明云端防火墙已经正确设置，最终要从公网测试。

云端检查监听状态，**Linux 服务器执行**：

```bash
ss -ltnp
sudo ufw status
```

如果你已经启用了 UFW，可在保留已有管理入口规则的前提下加入：

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 3389/tcp
```

不要为了安装本项目直接重置服务器防火墙、删除现有站点配置，或关闭其他业务。没有 SSH 22 入站规则时，可以直接使用平台的执行命令功能；网站本身不需要公网 SSH 端口。

## 4. Windows 下载官方 FRP 文件

在 **Windows PowerShell 的项目目录**执行：

```powershell
$python = 'C:\AIInference\runtime\chat-venv\Scripts\python.exe'
& $python scripts\download_frp.py --destination C:\AIInference\runtime\frp
```

需要本地代理时：

```powershell
& $python scripts\download_frp.py --destination C:\AIInference\runtime\frp --proxy http://127.0.0.1:7890
```

脚本从 FRP 官方固定版本 release 下载 Windows 客户端 zip 和 Linux 服务端压缩包，并验证 release 提供的 SHA256。它会解压 Windows 客户端，保留 Linux 压缩包供上传。

预期文件：

```text
C:\AIInference\runtime\frp\frp_0.71.0_windows_amd64\frpc.exe
C:\AIInference\runtime\frp\frp_0.71.0_linux_amd64.tar.gz
```

如果你手动下载，使用 [FRP 官方 v0.71.0 release](https://github.com/fatedier/frp/releases/tag/v0.71.0)，不要混用 Windows 与 Linux 二进制。

## 5. 为自己的 IP 生成配置

先运行过 `chat\setup.py`，让私有目录及访问密码配置存在。

**Windows PowerShell**执行，把 IP 替换掉：

```powershell
& $python scripts\prepare_relay.py --server-ip YOUR_SERVER_IP --public-port 3389
```

生成的私有文件位于 `%LOCALAPPDATA%\InferenceChat`：

- `relay-token.txt`：随机的 FRP 连接凭证。
- `frpc.toml`：本地转发配置，读取上面的凭证文件。
- `deploy-server.sh`：准备上传的云端安装脚本，包含同一个随机凭证。

这些文件已经在 `.gitignore` 中排除。源代码里只有无凭证的模板。不要把生成后的脚本粘贴进公开 issue、论坛或 Twitter。

生成器检查 IPv4 格式、全局可路由地址和端口范围。文档示例地址、私网地址与回环地址不能获得可用的公网 IP 证书，应使用自己服务器的真实地址。

再次生成时会复用已有转发令牌；网站访问密码和 FRP 转发令牌是两种不同的凭证。

## 6. 上传到云服务器

在腾讯云控制台打开对应实例的文件管理，把以下文件上传到服务器 `/root`：

1. `C:\AIInference\runtime\frp\frp_0.71.0_linux_amd64.tar.gz`
2. `%LOCALAPPDATA%\InferenceChat\deploy-server.sh`

云端文件名应为：

```text
/root/frp_0.71.0_linux_amd64.tar.gz
/root/deploy-server.sh
```

如果已有正常工作的 SSH/SFTP，也可以用它们上传。不要为了这一步把不需要的管理端口暴露给所有公网地址。

**Linux 服务器**检查并限制上传脚本权限：

```bash
ls -lh /root/frp_0.71.0_linux_amd64.tar.gz /root/deploy-server.sh
chmod 600 /root/deploy-server.sh
```

上传的服务器脚本没有网页密码，但包含 FRP 凭证，所以也需要保护。

## 7. 执行服务器安装脚本

先阅读 `deploy/server-setup.sh.template` 和生成的脚本，确认 IP、端口和准备安装的服务符合你的服务器用途。脚本调用 Certbot 同意证书机构条款；执行前应阅读适用的条款。

然后在 **Linux 服务器 root 会话**或云控制台的 root 执行命令功能中运行：

```bash
bash /root/deploy-server.sh
```

云控制台使用执行超时设置时，首次 apt/pip 下载可能超过默认 60 秒，可调整到足够完成安装的时长。只放入 Linux 命令，不把“本地”“服务器”等说明文字一并粘贴到命令内容里。

脚本完成这些工作：

1. 安装 Nginx、Python venv 支持。
2. 校验上传的 Linux FRP 压缩包，安装 `frps`。
3. 创建权限受限的 `inference-relay` 系统用户。
4. 写入 FRPS 配置：仅监听回环地址；只允许转发 18080；每客户端最多一个转发端口。
5. 新建项目自己的 Nginx 配置，已有同名配置先备份。
6. 准备 HTTP 证书校验目录，确保 Nginx 有读权限。
7. 在独立 Python venv 中安装 Certbot 5.4 以上版本，签发短期 IP HTTPS 证书。
8. 加载 HTTPS 3389 网站和 WSS 443 路径，保留 80 上的证书校验。
9. 注册并启动 FRP systemd 服务和证书续期定时器。

脚本不删除其他 Nginx 站点或替换你的其他业务配置。不过，本项目是有管理员权限的服务器部署，不是无风险的纯文件预览；在运行其他重要业务的服务器上，应先理解新配置的端口和主机名匹配。

### IP HTTPS 为什么能用

Let’s Encrypt 已支持短期 IP 地址证书；Certbot 从 5.4 起支持这里使用的 Webroot IP 申请方式。公网 IP 证书短期有效，需要自动续期，不能申请一次就忘记。[Let’s Encrypt 官方说明](https://letsencrypt.org/2026/03/11/shorter-certs-certbot)

本项目每 12 小时检查是否需要续期。检查不表示每 12 小时一定重新签发证书；Certbot 根据证书状态决定是否续期。

### 检查服务器服务

**Linux 服务器**执行：

```bash
nginx -t
systemctl is-active nginx inference-relay.service inference-cert-renew.timer
systemctl list-timers inference-cert-renew.timer
ss -ltnp
```

应看到三个服务 active，以及 Nginx 监听 80、443、3389。FRPS 的 7000 应仅监听 `127.0.0.1`。18080 会在本地客户端连上并注册转发后出现。

项目主要服务器文件：

```text
/etc/nginx/conf.d/inference-chat.conf
/etc/inference-chat/frps.toml
/etc/inference-chat/relay-token
/etc/inference-chat/letsencrypt/
/opt/inference-chat/frps
/opt/inference-chat/certbot/
/etc/systemd/system/inference-relay.service
/etc/systemd/system/inference-cert-renew.service
/etc/systemd/system/inference-cert-renew.timer
```

## 8. 启动本地 FRPC

模型容器和本地网页应处于运行状态。然后在 **Windows PowerShell**执行：

```powershell
$frpc = 'C:\AIInference\runtime\frp\frp_0.71.0_windows_amd64\frpc.exe'
$clientConfig = Join-Path $env:LOCALAPPDATA 'InferenceChat\frpc.toml'
& $frpc verify -c $clientConfig
& $frpc -c $clientConfig
```

设置了 `INFERENCE_CHAT_HOME` 时，改用该目录下的 `frpc.toml`。

配置使用服务器 443 的 WSS 连接，开启 TLS 并明确提供 certifi CA 文件。不要通过删除 CA 校验、跳过证书验证或忽略浏览器警告来掩盖配置错误。

网页后端继续监听 `127.0.0.1:8088`，vLLM 继续只发布 `127.0.0.1:8000`。公网不需要直接访问模型 API。

## 9. 公网验证

浏览器打开：

```text
https://YOUR_SERVER_IP:3389/
```

完整地址带 `https://` 和 `:3389`。它不是 `http://IP:3389`，也不是远程桌面地址。

确认：

1. 浏览器没有证书警告，显示实际聊天页面。
2. 未登录时要求输入访问密码。
3. 登录后状态显示“模型在线”。
4. 发送中文问题，看到流式输出而不是只有“ok”。
5. 两个独立浏览器会话同时发送时，有一条等待并自动开始。
6. 等待时点停止按钮可以取消该条，不影响另一条生成。

**Windows PowerShell 的项目目录**验证真实公网路径：

```powershell
& $python scripts\verify_chat_gateway.py https://YOUR_SERVER_IP:3389
& $python scripts\verify_chat_queue.py https://YOUR_SERVER_IP:3389
```

这些请求会使用实际模型生成短回复。队列取消的细节测试请用 `verify_queue_controlled.py`，避免在生产网站上为测试故意占用模型生成长文本。

## 10. 让本机登录后自动启动

先停止手工启动的网页与 FRPC 前台进程，例如在各自 PowerShell 窗口按 Ctrl+C。模型容器可以保持运行。

**Windows PowerShell**执行：

```powershell
.\chat\start.ps1
.\scripts\install-shortcuts.ps1 -Startup
```

会生成桌面与 Windows 启动目录中的 `Photo Coach` 快捷方式。后台启动器会尝试启动 Docker 和已有模型容器，监控网页与 FRPC 子进程，退出后约 5 秒重新启动。

这属于 **Windows 用户登录后的自动启动**，不是无人登录就运行的 Windows 系统服务。锁屏不等于退出登录；休眠、关机、断网或 Docker 停止都会影响服务。

本机有多个 Docker 安装位置时，启动器优先查 PATH 和官方常见安装路径。需要自定义时使用 `INFERENCE_DOCKER`；FRPC 不在默认位置时使用 `INFERENCE_FRPC_PATH`。环境变量要保存在启动进程能读取的位置。

日志在私有目录：

```text
gateway.log
relay.log
runner.pid
```

观察日志，**Windows PowerShell**：

```powershell
Get-Content (Join-Path $env:LOCALAPPDATA 'InferenceChat\gateway.log') -Tail 60
Get-Content (Join-Path $env:LOCALAPPDATA 'InferenceChat\relay.log') -Tail 60
docker logs --tail 60 vllm-qwen38-27b
```

## 11. 改端口时要同时改哪些地方

新装时用 `prepare_relay.py --public-port 新端口` 生成即可。

已经部署的站点迁移时，需要：

1. 确认新端口没有被其他程序占用。
2. 在云平台防火墙和已启用的本机防火墙中放行对应 TCP 入站。
3. 备份 `/etc/nginx/conf.d/inference-chat.conf`。
4. 修改网页 `listen` 端口及旧入口的跳转目标。
5. 执行 `nginx -t`，成功后 `systemctl reload nginx`。
6. 从公网用新地址验证证书、登录和实际回复。

网站入口改动时，本方案的 FRPC 仍连 443，不必同步改变内部 7000、18080、8088 和 8000。80 的 ACME 校验路径也应继续保留，确保续期有效。

本教程的 3389 已实测通过。不是所有数字端口都适合浏览器使用，也不要复用现有其他业务正在监听的端口。

## 12. 故障定位顺序

| 现象 | 优先检查 |
| --- | --- |
| 本地网站也不能用 | Docker、`/v1/models`、FastAPI 日志、8088 监听 |
| 本地正常，公网打不开 | 云防火墙、Nginx 3389 监听、地址协议和端口 |
| 公网 502 | FRPC 是否运行、FRPS 是否已注册 18080、网页是否运行 |
| 页面只有 `ok` | Nginx 是否指向真实网页后端；可能仍指向早期连通性测试服务 |
| TLS 或证书失败 | 系统时间、IP 是否与证书匹配、CA 路径、续期定时器 |
| Certbot 校验 403 | Webroot 和父目录权限、Nginx ACME location |
| Certbot 校验连接失败 | TCP 80 防火墙、实际公网 IP、80 上其他配置 |
| WSS 登录失败 | `/~!frp` 路径、Upgrade 头、两端令牌是否一致 |
| 登录返回来源不匹配 | Nginx `Host $http_host` 是否保留含端口的 Host |
| 流式输出变成一次性整段 | Nginx buffering 是否关闭，中间代理是否缓冲 |
| 访问旧地址绕到其他站点 | Nginx IP `server_name` 匹配和证书配置 |
| 密码连续失败后暂时不能登录 | 等一分钟后用正确密码重试；当前 FRP 链路的失败计数可能由访客共用 |
| 重启后无法聊天 | 是否已经登录 Windows、Docker 能否启动、模型是否仍在加载 |

云端日志和状态，**Linux 服务器**执行：

```bash
journalctl -u inference-relay.service -n 60 --no-pager
journalctl -u inference-cert-renew.service -n 60 --no-pager
systemctl status inference-cert-renew.timer --no-pager
```

分享排障日志之前，先删除令牌、Cookie、密码、个人 IP、账号信息及任何聊天内容。仓库提供的是部署代码，自己的运行日志默认不属于开源材料。

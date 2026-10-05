"""Windows supervisor for the model, local gateway and optional FRP relay."""
import json
import msvcrt
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat.paths import private_dir

private = private_dir()
private.mkdir(parents=True, exist_ok=True)
lock = (private / "runner.lock").open("a+b")
lock.seek(0)
try:
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    sys.exit(0)
(private / "runner.pid").write_text(str(os.getpid()))
root = Path(__file__).resolve().parents[1]
candidates = [os.environ.get("INFERENCE_DOCKER"), shutil.which("docker"), str(Path(os.environ["LOCALAPPDATA"]) / "Programs/DockerDesktop/resources/bin/docker.exe"), r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"]
docker = next((value for value in candidates if value and Path(value).is_file()), None)
if not docker:
    raise SystemExit("Docker CLI not found; install Docker Desktop or set INFERENCE_DOCKER")
desktop_candidates = [Path(os.environ["LOCALAPPDATA"]) / "Programs/DockerDesktop/Docker Desktop.exe", Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe")]
relay = os.environ.get("INFERENCE_FRPC_PATH", r"C:\AIInference\runtime\frp\frp_0.71.0_windows_amd64\frpc.exe")
container = os.environ.get("INFERENCE_MODEL_CONTAINER", "vllm-qwen38-27b")
children = {}


def spawn(name, command):
    with (private / f"{name}.log").open("ab", buffering=0) as output:
        return subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)


def gateway_running():
    import httpx
    try:
        result = httpx.get("http://127.0.0.1:8088/api/status", trust_env=False, timeout=2)
        return result.is_success and result.json().get("model") == json.loads((private / "settings.json").read_text(encoding="utf-8"))["model"]
    except (httpx.HTTPError, ValueError, OSError):
        return False


try:
    ready = subprocess.run([docker, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW, timeout=20).returncode == 0
except (subprocess.TimeoutExpired, OSError):
    ready = False
if not ready:
    desktop = next((p for p in desktop_candidates if p.is_file()), None)
    if desktop:
        subprocess.Popen([str(desktop)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
for _ in range(120):
    try:
        result = subprocess.run([docker, "start", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if result.returncode == 0:
            break
    except subprocess.TimeoutExpired:
        pass
    time.sleep(5)
while True:
    if not gateway_running():
        process = children.get("gateway")
        if process is None or process.poll() is not None:
            children["gateway"] = spawn("gateway", [sys.executable, "-m", "uvicorn", "chat.app:app", "--host", "127.0.0.1", "--port", "8088", "--workers", "1", "--no-proxy-headers"])
    if (private / "frpc.toml").is_file() and Path(relay).is_file():
        process = children.get("relay")
        if process is None or process.poll() is not None:
            children["relay"] = spawn("relay", [relay, "-c", str(private / "frpc.toml")])
    time.sleep(5)

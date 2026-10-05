import asyncio
import base64
from collections import deque
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlparse

import httpx
import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles


WEB = Path(__file__).parent / "web"
from chat.paths import settings_path
SETTINGS = settings_path()
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
login_attempts = {}


class GenerationQueue:
    """FIFO admission to the single model, with removable waiting requests."""

    def __init__(self, limit=16):
        self.limit = limit
        self.waiting = deque()
        self.active = None

    def join(self):
        if len(self.waiting) >= self.limit:
            raise HTTPException(429, "等待的人较多，请稍后再试")
        ticket = asyncio.Event()
        self.waiting.append(ticket)
        self.start_next()
        return ticket

    def start_next(self):
        if self.active is None and self.waiting:
            self.active = self.waiting.popleft()
            self.active.set()

    def position(self, ticket):
        if self.active is ticket:
            return 0
        return self.waiting.index(ticket) + 1

    def finish(self, ticket):
        if self.active is ticket:
            self.active = None
        else:
            try:
                self.waiting.remove(ticket)
            except ValueError:
                pass
        self.start_next()


generation_queue = GenerationQueue()


def stream_event(data):
    return ("data: " + json.dumps(data, ensure_ascii=False) + "\n\n").encode()


def settings():
    return json.loads(SETTINGS.read_text(encoding="utf-8"))


def authenticated(request, config):
    token = request.cookies.get("chat_session", "")
    try:
        payload, signature = token.split(".")
        expected = hmac.new(bytes.fromhex(config["session_secret"]), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return False
        expiry = int(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode().split(":")[0])
        return time.time() < expiry
    except (ValueError, TypeError, UnicodeError):
        return False


def check_origin(request):
    origin = request.headers.get("origin")
    host = request.headers.get("host", "")
    if origin and urlparse(origin).netloc != host:
        raise HTTPException(403, "请求来源不匹配")


async def limited_json(request, limit):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > limit:
            raise HTTPException(413, "请求过大，请开始新对话")
    try:
        return json.loads(content)
    except (ValueError, UnicodeError):
        raise HTTPException(400, "请求格式不正确")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
async def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/status")
async def status(request: Request):
    config = settings()
    ready = False
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=3) as client:
            response = await client.get(config["upstream"] + "/models")
            ready = response.is_success and any(m["id"] == config["model"] for m in response.json().get("data", []))
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    return {"ready": ready, "model": config["model"], "label": config["model_label"], "authenticated": authenticated(request, config)}


@app.post("/api/login")
async def login(request: Request):
    check_origin(request)
    config = settings()
    now = time.time()
    address = request.client.host
    attempts = [t for t in login_attempts.get(address, []) if t > now - 60]
    if len(attempts) >= 5:
        raise HTTPException(429, "尝试次数过多，请一分钟后再试")
    try:
        body = await limited_json(request, 4096)
        password = body.get("password", "")
        if not isinstance(password, str) or len(password) > 256:
            raise ValueError()
    except (ValueError, AttributeError):
        raise HTTPException(400, "请输入访问密码")
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(config["password_salt"]), 200_000).hex()
    if not hmac.compare_digest(candidate, config["password_hash"]):
        login_attempts[address] = attempts + [now]
        raise HTTPException(401, "访问密码不正确")
    login_attempts.pop(address, None)
    payload = base64.urlsafe_b64encode(f"{int(now + 28800)}:{secrets.token_hex(16)}".encode()).decode().rstrip("=")
    signature = hmac.new(bytes.fromhex(config["session_secret"]), payload.encode(), hashlib.sha256).hexdigest()
    response = JSONResponse({"ok": True})
    response.set_cookie("chat_session", payload + "." + signature, max_age=28800, httponly=True, secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https", samesite="strict")
    return response


@app.post("/api/logout")
async def logout(request: Request):
    check_origin(request)
    response = JSONResponse({"ok": True})
    response.delete_cookie("chat_session")
    return response


@app.post("/api/chat")
async def chat(request: Request):
    check_origin(request)
    config = settings()
    if not authenticated(request, config):
        raise HTTPException(401, "请先输入访问密码")
    body = await limited_json(request, 64000)
    try:
        messages = body["messages"]
        if not isinstance(messages, list) or not 1 <= len(messages) <= 30:
            raise ValueError()
        for message in messages:
            if message.get("role") not in ("user", "assistant") or not isinstance(message.get("content"), str):
                raise ValueError()
        if sum(len(m["content"]) for m in messages) > 12000 or messages[-1]["role"] != "user":
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(400, "对话格式不正确或内容过长，请开始新对话")
    payload = {"model": config["model"], "messages": messages, "stream": True, "stream_options": {"include_usage": True}, "max_tokens": 1024, "temperature": 0.7, "top_p": 0.8, "chat_template_kwargs": {"enable_thinking": bool(body.get("thinking", False))}}
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            tokenization = await client.post(config["upstream"].removesuffix("/v1") + "/tokenize", json={
                "model": config["model"], "messages": messages,
                "chat_template_kwargs": payload["chat_template_kwargs"],
            })
        tokenization.raise_for_status()
        token_info = tokenization.json()
        remaining = int(token_info["max_model_len"]) - int(token_info["count"]) - 8
        if remaining < 128:
            raise HTTPException(400, "对话已达到长度限制，请开始新对话")
        payload["max_tokens"] = min(1024, remaining)
    except httpx.HTTPError as error:
        raise HTTPException(503, "模型正在准备中，请稍后再试") from error

    async def stream():
        ticket = None
        client = None
        upstream = None
        try:
            ticket = generation_queue.join()
            yield stream_event({"queue": {"position": generation_queue.position(ticket)}})
            while not ticket.is_set():
                try:
                    await asyncio.wait_for(ticket.wait(), timeout=5)
                except asyncio.TimeoutError:
                    # Keep the relay alive, and update the visitor's queue position.
                    yield stream_event({"queue": {"position": generation_queue.position(ticket)}})
            if await request.is_disconnected():
                return
            yield stream_event({"queue": {"position": 0}})
            client = httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(180, connect=5))
            upstream = await client.send(client.build_request("POST", config["upstream"] + "/chat/completions", json=payload), stream=True)
            if upstream.status_code != 200:
                yield stream_event({"error": "模型暂时不可用，请稍后再试"})
                return
            async for chunk in upstream.aiter_bytes():
                yield chunk
        except HTTPException as error:
            yield stream_event({"error": error.detail})
        except httpx.HTTPError:
            yield stream_event({"error": "连接中断，请重试"})
        finally:
            with anyio.CancelScope(shield=True):
                try:
                    try:
                        if upstream is not None:
                            await upstream.aclose()
                    finally:
                        if client is not None:
                            await client.aclose()
                finally:
                    if ticket is not None:
                        generation_queue.finish(ticket)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


app.mount("/assets", StaticFiles(directory=WEB), name="assets")

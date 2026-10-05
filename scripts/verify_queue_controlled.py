"""Test the real gateway against a controlled streaming upstream on loopback."""
import asyncio
import json
import os
import hashlib
import secrets
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = 'http://127.0.0.1:18089'
UPSTREAM = 'http://127.0.0.1:18090'
private = Path(tempfile.gettempdir())
workspace = Path(__file__).resolve().parent.parent
password = secrets.token_urlsafe(18)

async def verify():
    clients = [httpx.AsyncClient(base_url=ROOT, trust_env=False, timeout=20) for _ in range(4)]
    tasks = []
    records = []
    try:
        for client in clients:
            assert (await client.post('/api/login', json={'password': password})).status_code == 200

        async def consume(index, name, started=None, queued=None, cancel=False):
            record = {'name': name, 'positions': [], 'answer': ''}
            async with clients[index].stream('POST', '/api/chat', json={'messages': [{'role': 'user', 'content': name}]}) as response:
                assert response.status_code == 200
                async for line in response.aiter_lines():
                    if not line.startswith('data: ') or line[6:] == '[DONE]':
                        continue
                    event = json.loads(line[6:])
                    assert not event.get('error'), event
                    if 'queue' in event:
                        position = event['queue']['position']
                        record['positions'].append(position)
                        if position > 0:
                            if queued:
                                queued.set()
                            if cancel:
                                record['cancelled'] = True
                                return record
                    content = (event.get('choices') or [{}])[0].get('delta', {}).get('content', '')
                    if content:
                        record['answer'] += content
                        if started:
                            started.set()
            return record

        started, queued = asyncio.Event(), asyncio.Event()
        first = asyncio.create_task(consume(0, 'first', started=started))
        tasks.append(first)
        await asyncio.wait_for(started.wait(), 5)
        second = asyncio.create_task(consume(1, 'second', queued=queued))
        tasks.append(second)
        await asyncio.wait_for(queued.wait(), 5)
        cancelled = await consume(2, 'cancelled-waiter', cancel=True)
        assert cancelled['positions'] == [2], cancelled
        await asyncio.sleep(.3)
        fourth = asyncio.create_task(consume(3, 'fourth'))
        tasks.append(fourth)
        await asyncio.sleep(5.2)
        async with httpx.AsyncClient(trust_env=False) as control:
            await control.post(UPSTREAM + '/test/release/first')
        a, b, d = await asyncio.wait_for(asyncio.gather(first, second, fourth), 8)
        assert b['positions'][:2] == [1, 1], b
        assert d['positions'][:2] == [2, 2], d
        assert a['answer'] == 'first finished' and b['answer'] == 'second finished' and d['answer'] == 'fourth finished'
        records.extend([a, b, cancelled, d])

        started, queued = asyncio.Event(), asyncio.Event()
        active = asyncio.create_task(consume(0, 'cancelled-active', started=started))
        tasks.append(active)
        await asyncio.wait_for(started.wait(), 5)
        next_reply = asyncio.create_task(consume(1, 'after-cancelled-active', queued=queued))
        tasks.append(next_reply)
        await asyncio.wait_for(queued.wait(), 5)
        active.cancel()
        await asyncio.gather(active, return_exceptions=True)
        result = await asyncio.wait_for(next_reply, 5)
        assert result['answer'] == 'after-cancelled-active finished', result
        records.append(result)
        async with httpx.AsyncClient(trust_env=False) as control:
            events = (await control.get(UPSTREAM + '/test/events')).json()
        assert [e['name'] for e in events if e['event'] == 'started'] == ['first', 'second', 'fourth', 'cancelled-active', 'after-cancelled-active'], events
        assert any(e == {'name': 'cancelled-active', 'event': 'cancelled'} for e in events), events
        output = workspace / 'benchmark-results' / 'queue-controlled.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({'responses': records, 'upstreamEvents': events}, indent=2), encoding='utf-8')
        print('PASSED: FIFO order, five-second queue updates, cancelled waiter removal, active cancellation and automatic continuation')
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(*(client.aclose() for client in clients))

with tempfile.TemporaryDirectory(prefix='queue-test-', dir=private) as directory:
    test_root = Path(directory).resolve()
    assert test_root.parent == private.resolve()
    salt = secrets.token_bytes(16)
    config = {'upstream': UPSTREAM + '/v1', 'model': 'qwen3.8-27b', 'model_label': 'Controlled test', 'password_salt': salt.hex(), 'password_hash': hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 200000).hex(), 'session_secret': secrets.token_hex(32)}
    config_path = test_root / 'settings.json'
    config_path.write_text(json.dumps(config), encoding='utf-8')
    env = dict(os.environ, INFERENCE_CHAT_SETTINGS=str(config_path))
    log = (test_root / 'servers.log').open('wb')
    servers = []
    try:
        for module, port in [('scripts.queue_fixture:app', '18090'), ('chat.app:app', '18089')]:
            servers.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', module, '--host', '127.0.0.1', '--port', port], cwd=workspace, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
        for _ in range(40):
            try:
                if httpx.get(ROOT + '/api/status', trust_env=False, timeout=1).is_success:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.2)
        else:
            raise RuntimeError('Test gateway did not start')
        asyncio.run(verify())
    finally:
        for server in servers:
            server.terminate()
            server.wait(timeout=10)
        log.close()

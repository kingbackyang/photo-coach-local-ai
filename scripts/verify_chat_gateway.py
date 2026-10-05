"""Exercise access control and real model streaming without printing credentials."""
import json
import os
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat.paths import private_dir

root = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://127.0.0.1:8088'
client = httpx.Client(base_url=root, trust_env=False, timeout=180)
messages = [{'role': 'user', 'content': '只回答一个数字：3加4等于多少？'}]
assert client.get('/api/status').json()['ready']
assert client.post('/api/chat', json={'messages': messages}).status_code == 401
assert client.post('/api/login', headers={'Origin': 'https://unrelated.example'}, json={'password': 'bad'}).status_code == 403
assert client.post('/api/login', content=b'x' * 5000).status_code == 413
assert client.post('/api/login', content=b'{broken').status_code == 400
access = (private_dir() / 'access.txt').read_text(encoding='utf-8')
password = [line for line in access.splitlines() if line.strip()][1]
login = client.post('/api/login', json={'password': password}, headers={'Origin': root})
assert login.status_code == 200
assert 'HttpOnly' in login.headers['set-cookie']
if root.startswith('https:'):
    assert 'Secure' in login.headers['set-cookie']
assert client.get('/api/status').json()['authenticated']
oversize_context = [{'role': 'user', 'content': '春天的山川湖泊' * 750}]
rejected = client.post('/api/chat', json={'messages': oversize_context})
assert rejected.status_code == 400, f'Context limit returned {rejected.status_code}'
answer = ''
with client.stream('POST', '/api/chat', json={'messages': messages}) as response:
    assert response.status_code == 200, response.read().decode()
    for line in response.iter_lines():
        if not line.startswith('data: ') or line[6:] == '[DONE]':
            continue
        event = json.loads(line[6:])
        assert not event.get('error'), event
        answer += (event.get('choices') or [{}])[0].get('delta', {}).get('content', '')
assert '7' in answer, answer
assert client.post('/api/logout').status_code == 200
assert not client.get('/api/status').json()['authenticated']
print('PASSED: model online, authentication, origin checks, body limits, context limits, real streaming and logout')
print('Stream answer:', answer)

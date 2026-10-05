"""Verify independent real conversations queue through the public relay.

Cancellation and FIFO edge cases use verify_queue_controlled.py, which isolates
its fixture from production traffic.
"""
import asyncio
import json
import os
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat.paths import private_dir

ROOT = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://127.0.0.1:8088'
password = [line for line in (private_dir() / 'access.txt').read_text(encoding='utf-8').splitlines() if line.strip()][1]


async def main():
    async def chat(prompt, expected):
        async with httpx.AsyncClient(base_url=ROOT, trust_env=False, timeout=180) as client:
            login = await client.post('/api/login', json={'password': password}, headers={'Origin': ROOT})
            assert login.status_code == 200, login.status_code
            record = {'positions': [], 'answer': ''}
            async with client.stream('POST', '/api/chat', json={'messages': [{'role': 'user', 'content': prompt}]}) as response:
                assert response.status_code == 200, response.status_code
                async for line in response.aiter_lines():
                    if not line.startswith('data: ') or line[6:] == '[DONE]':
                        continue
                    event = json.loads(line[6:])
                    assert not event.get('error'), event
                    if 'queue' in event:
                        record['positions'].append(event['queue']['position'])
                    record['answer'] += (event.get('choices') or [{}])[0].get('delta', {}).get('content', '')
            assert expected in record['answer'], record
            assert 0 in record['positions'], record
            return record

    records = await asyncio.gather(
        chat('只回答一个数字：6乘以7等于多少？', '42'),
        chat('只回答一个数字：8乘以9等于多少？', '72'),
    )
    assert any(position > 0 for record in records for position in record['positions']), records
    artifact = {'url': ROOT, 'cases': records}
    output = Path('benchmark-results/queue-public.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASSED: two independent public conversations queued and returned correct answers')
    print('Queue positions:', [record['positions'] for record in records])


if __name__ == '__main__':
    asyncio.run(main())

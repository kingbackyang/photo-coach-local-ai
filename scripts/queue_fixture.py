"""Local controlled upstream for queue integration tests, never publicly hosted."""
import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()
gates = {}
events = []

@app.get('/v1/models')
async def models():
    return {'data': [{'id': 'qwen3.8-27b'}]}

@app.post('/tokenize')
async def tokenize():
    return {'count': 20, 'max_model_len': 2048}

@app.post('/test/release/{name}')
async def release(name: str):
    gates.setdefault(name, asyncio.Event()).set()
    return {'ok': True}

@app.get('/test/events')
async def inspect():
    return events

@app.post('/v1/chat/completions')
async def completions(request: Request):
    name = (await request.json())['messages'][-1]['content']
    async def stream():
        events.append({'name': name, 'event': 'started'})
        complete = False
        try:
            await asyncio.sleep(.05)
            yield ('data: ' + json.dumps({'choices': [{'delta': {'content': name + ' '}}]}) + '\n\n').encode()
            if name in ('first', 'cancelled-active'):
                gate = gates.setdefault(name, asyncio.Event())
                while not gate.is_set():
                    yield b': heartbeat\n\n'
                    await asyncio.sleep(.2)
            yield b'data: {"choices":[{"delta":{"content":"finished"}}]}\n\n'
            yield b'data: [DONE]\n\n'
            complete = True
        finally:
            events.append({'name': name, 'event': 'finished' if complete else 'cancelled'})
    return StreamingResponse(stream(), media_type='text/event-stream')

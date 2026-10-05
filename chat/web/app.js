const $ = (id) => document.getElementById(id);
let history = [];
let controller = null;
let ready = false;
let signedIn = false;

function showLogin() {
  if (!$('login-dialog').open) $('login-dialog').showModal();
}

async function refreshStatus() {
  try {
    const response = await fetch('/api/status');
    if (!response.ok) throw new Error();
    const data = await response.json();
    ready = data.ready;
    signedIn = data.authenticated;
    $('model').textContent = data.label;
    $('status').textContent = ready ? '模型在线' : '模型准备中';
    $('status').classList.toggle('online', ready);
    if (!signedIn) showLogin();
  } catch {
    ready = false;
    $('status').textContent = '连接中断';
    $('status').classList.remove('online');
  }
}

$('login-dialog').addEventListener('cancel', (event) => event.preventDefault());
$('login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button');
  button.disabled = true;
  $('login-error').textContent = '';
  try {
    const response = await fetch('/api/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({password: $('password').value})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '暂时无法登录');
    $('password').value = '';
    $('login-dialog').close();
    signedIn = true;
    $('prompt').focus();
  } catch (error) {
    $('login-error').textContent = error.message;
  } finally { button.disabled = false; }
});

function addMessage(role, content) {
  const welcome = $('welcome');
  if (welcome) welcome.remove();
  const message = document.createElement('article');
  message.className = `message ${role}`;
  const name = document.createElement('div');
  name.className = 'message-name';
  name.textContent = role === 'user' ? '你' : 'Photo Coach';
  const reasoning = document.createElement('div');
  reasoning.className = 'reasoning';
  const text = document.createElement('div');
  text.className = 'message-content';
  text.textContent = content;
  const metrics = document.createElement('div');
  metrics.className = 'metrics';
  message.append(name, reasoning, text, metrics);
  $('messages').append(message);
  $('messages').scrollTop = $('messages').scrollHeight;
  return {message, text, reasoning, metrics};
}

function setBusy(busy) {
  $('prompt').disabled = busy;
  $('thinking').disabled = busy;
  $('send').textContent = busy ? '■' : '↑';
  $('send').setAttribute('aria-label', busy ? '停止生成' : '发送消息');
}

async function send() {
  if (controller) { controller.abort(); return; }
  if (!signedIn) { showLogin(); return; }
  const prompt = $('prompt').value.trim();
  if (!prompt) return;
  if (!ready) { $('notice').textContent = '模型正在准备中，稍后即可开始对话。'; return; }
  $('notice').textContent = '';
  history.push({role: 'user', content: prompt});
  addMessage('user', prompt);
  $('prompt').value = '';
  const result = addMessage('assistant', '正在连接…');
  let answer = '', reasoning = '', usage = null;
  const start = performance.now();
  let firstToken = null;
  let queued = false;
  let waited = false;
  let queueSeconds = 0;
  controller = new AbortController();
  setBusy(true);
  try {
    const response = await fetch('/api/chat', {method: 'POST', signal: controller.signal, headers: {'Content-Type': 'application/json'}, body: JSON.stringify({messages: history, thinking: $('thinking').checked})});
    if (!response.ok) {
      const error = await response.json();
      if (response.status === 401) { signedIn = false; showLogin(); }
      throw new Error(error.detail || '暂时无法生成回答');
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ') || line.slice(6).trim() === '[DONE]') continue;
        const data = JSON.parse(line.slice(6));
        if (data.error) throw new Error(typeof data.error === 'string' ? data.error : '连接中断，请重试');
        if (data.queue) {
          const position = data.queue.position;
          queued = position > 0;
          if (queued) {
            waited = true;
            result.text.textContent = `正在排队，前面还有 ${position} 条消息…`;
            result.metrics.textContent = '轮到后自动开始，可点击停止按钮取消等待';
            $('send').setAttribute('aria-label', '取消排队');
          } else {
            if (waited) queueSeconds = (performance.now() - start) / 1000;
            result.text.textContent = '正在思考…';
            result.metrics.textContent = '';
            $('send').setAttribute('aria-label', '停止生成');
          }
          continue;
        }
        if (data.usage) usage = data.usage;
        const delta = data.choices?.[0]?.delta || {};
        if (delta.content || delta.reasoning_content || delta.reasoning) {
          if (firstToken === null) firstToken = performance.now();
          answer += delta.content || '';
          reasoning += delta.reasoning_content || delta.reasoning || '';
          result.text.textContent = answer || (reasoning ? '' : '正在思考…');
          result.reasoning.textContent = reasoning;
          $('messages').scrollTop = $('messages').scrollHeight;
        }
      }
    }
    if (!answer && !reasoning) throw new Error('模型没有返回内容，请重试');
    const elapsed = (performance.now() - start) / 1000;
    result.metrics.textContent = `${elapsed.toFixed(1)} 秒` + (waited ? ` · 排队 ${queueSeconds.toFixed(1)} 秒` : '') + (usage?.completion_tokens ? ` · ${usage.completion_tokens} tokens` : '');
  } catch (error) {
    if (error.name === 'AbortError') result.metrics.textContent = queued ? '已取消排队' : '已停止生成';
    else { $('notice').textContent = error.message; result.metrics.textContent = '生成未完成'; }
    if (!answer && !reasoning) result.text.textContent = error.name === 'AbortError' && queued ? '已取消等待。' : '这次没有获得回答。';
  } finally {
    if (answer) history.push({role: 'assistant', content: answer});
    else history.pop();
    controller = null;
    setBusy(false);
    $('prompt').focus();
  }
}

$('chat-form').addEventListener('submit', (event) => {event.preventDefault(); send();});
$('prompt').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {event.preventDefault(); send();}
});
$('new-chat').addEventListener('click', () => {
  if (controller) {controller.abort(); return;}
  history = [];
  $('messages').replaceChildren();
  $('notice').textContent = '';
  $('prompt').value = '';
  $('prompt').focus();
});
document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => {
  $('prompt').value = button.dataset.prompt;
  $('prompt').focus();
}));
refreshStatus();
setInterval(refreshStatus, 15000);

# Web GUI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a server-side rendered web chat GUI to sonya-gateway, accessible via browser on Cloud Run.

**Architecture:** Jinja2 templates + vanilla JS integrated into the existing FastAPI app. `GET /` serves the chat page, JS communicates with existing session REST + SSE endpoints. Multi-session support with model selector and tone presets in the input bar. Deploy via `deploy/cloud-run/Dockerfile`.

**Tech Stack:** FastAPI, Jinja2, vanilla JS, EventSource API, CSS (no framework)

---

### Task 1: Add Jinja2 template support to FastAPI

**Files:**
- Modify: `packages/sonya-gateway/pyproject.toml`
- Modify: `packages/sonya-gateway/src/sonya/gateway/server.py`
- Create: `packages/sonya-gateway/src/sonya/gateway/templates/base.html`
- Create: `packages/sonya-gateway/src/sonya/gateway/templates/chat.html`

**Step 1: Add jinja2 dependency**

In `packages/sonya-gateway/pyproject.toml`, add `"jinja2>=3.1"` to `dependencies`:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sse-starlette>=2.0",
    "sonya-core",
    "jinja2>=3.1",
]
```

**Step 2: Install the dependency**

Run: `cd packages/sonya-gateway && uv pip install -e .`

**Step 3: Create base.html template**

```html
<!-- packages/sonya-gateway/src/sonya/gateway/templates/base.html -->
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sonya</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    {% block content %}{% endblock %}
    {% block scripts %}{% endblock %}
</body>
</html>
```

**Step 4: Create minimal chat.html template**

```html
<!-- packages/sonya-gateway/src/sonya/gateway/templates/chat.html -->
{% extends "base.html" %}

{% block content %}
<div id="app">
    <header id="header">
        <button id="sidebar-toggle" aria-label="Toggle sidebar">&#9776;</button>
        <h1>Sonya</h1>
    </header>

    <div id="layout">
        <aside id="sidebar">
            <button id="new-chat-btn">+ New Chat</button>
            <div id="session-list"></div>
        </aside>

        <main id="chat-area">
            <div id="messages"></div>

            <div id="input-bar">
                <textarea id="message-input"
                    placeholder="Message..."
                    rows="1"></textarea>
                <div id="input-controls">
                    <div id="tool-buttons">
                        <button id="tone-btn"
                            class="tool-btn"
                            title="Tone">&#127917;</button>
                        <button id="research-btn"
                            class="tool-btn"
                            title="Deep Research"
                            disabled>&#128300;</button>
                    </div>
                    <div id="right-controls">
                        <select id="model-select">
                            {% for model in models %}
                            <option value="{{ model.id }}"
                                {% if loop.first %}selected{% endif %}>
                                {{ model.name }}
                            </option>
                            {% endfor %}
                        </select>
                        <button id="send-btn" title="Send">&#9650;</button>
                    </div>
                </div>
            </div>

            <div id="tone-popover" class="popover hidden">
                <div class="popover-item" data-tone="default">Default</div>
                <div class="popover-item" data-tone="friendly">Friendly</div>
                <div class="popover-item" data-tone="formal">Formal</div>
                <div class="popover-item" data-tone="concise">Concise</div>
            </div>
        </main>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/app.js"></script>
{% endblock %}
```

**Step 5: Add HTML route and static mount to server.py**

Add to `packages/sonya-gateway/src/sonya/gateway/server.py`:

```python
import os
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

_base_dir = os.path.dirname(os.path.abspath(__file__))

app.mount(
    '/static',
    StaticFiles(
        directory=os.path.join(_base_dir, 'static')
    ),
    name='static',
)

_templates = Jinja2Templates(
    directory=os.path.join(_base_dir, 'templates')
)

_MODELS = [
    {'id': 'claude-sonnet-4-6', 'name': 'Claude 4.6 Sonnet'},
    {'id': 'claude-haiku-4-5-20251001', 'name': 'Claude 4.5 Haiku'},
    {'id': 'gpt-4o', 'name': 'GPT-4o'},
    {'id': 'gpt-4.1', 'name': 'GPT-4.1'},
    {'id': 'gpt-4.1-mini', 'name': 'GPT-4.1 mini'},
    {'id': 'gemini-3-flash-preview', 'name': 'Gemini 3 Flash'},
    {'id': 'gemini-3.1-pro-preview', 'name': 'Gemini 3.1 Pro'},
]


@app.get('/')
async def index(request: Request):
    """Serve the chat GUI."""
    return _templates.TemplateResponse(
        'chat.html',
        {'request': request, 'models': _MODELS},
    )
```

**Step 6: Create empty static directories**

Run: `mkdir -p packages/sonya-gateway/src/sonya/gateway/static/css packages/sonya-gateway/src/sonya/gateway/static/js`

**Step 7: Verify server starts**

Run: `cd packages/sonya-gateway && python -c "from sonya.gateway.server import app; print('OK')"`
Expected: `OK`

**Step 8: Commit**

```bash
git add packages/sonya-gateway/
git commit -m "feat(sonya-gateway): add Jinja2 template support and chat.html route"
```

---

### Task 2: Modify session creation to use server-side API keys

**Files:**
- Modify: `packages/sonya-gateway/src/sonya/gateway/server.py`
- Modify: `packages/sonya-gateway/src/sonya/gateway/schemas.py`

**Step 1: Make api_key optional in CreateSessionRequest**

In `packages/sonya-gateway/src/sonya/gateway/schemas.py`, change:

```python
class CreateSessionRequest(BaseModel):
    """Request body for POST /sessions."""

    model: str
    api_key: str = ''
    system_prompt: str = ''
```

**Step 2: Add server-side API key resolution in server.py**

Add to `packages/sonya-gateway/src/sonya/gateway/server.py`:

```python
_MODEL_KEY_MAP = {
    'claude': 'ANTHROPIC_API_KEY',
    'gpt': 'OPENAI_API_KEY',
    'gemini': 'GOOGLE_API_KEY',
}


def _resolve_api_key(model: str, provided_key: str) -> str:
    """Resolve API key: use provided or fall back to env."""
    if provided_key:
        return provided_key
    for prefix, env_var in _MODEL_KEY_MAP.items():
        if model.startswith(prefix):
            return os.environ.get(env_var, '')
    return ''
```

Modify the `create_session` endpoint:

```python
@app.post(
    '/sessions',
    response_model=CreateSessionResponse,
    status_code=201,
)
async def create_session(
    body: CreateSessionRequest,
) -> CreateSessionResponse:
    """Create a new LLM session."""
    api_key = _resolve_api_key(
        body.model, body.api_key
    )
    session_id = session_manager.create(
        model=body.model,
        api_key=api_key,
        system_prompt=body.system_prompt,
    )
    return CreateSessionResponse(
        session_id=session_id,
        model=body.model,
    )
```

**Step 3: Run existing tests**

Run: `cd packages/sonya-gateway && python -m pytest tests/ -v`
Expected: PASS (or adjust tests if they hardcode api_key)

**Step 4: Commit**

```bash
git add packages/sonya-gateway/src/sonya/gateway/schemas.py packages/sonya-gateway/src/sonya/gateway/server.py
git commit -m "feat(sonya-gateway): auto-resolve API key from server env"
```

---

### Task 3: Create CSS stylesheet

**Files:**
- Create: `packages/sonya-gateway/src/sonya/gateway/static/css/style.css`

**Step 1: Write the stylesheet**

```css
/* packages/sonya-gateway/src/sonya/gateway/static/css/style.css */

/* ── Reset ── */
*, *::before, *::after {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

:root {
    --bg: #f9fafb;
    --bg-sidebar: #111827;
    --bg-chat: #ffffff;
    --bg-input: #f3f4f6;
    --bg-user: #e0e7ff;
    --bg-assistant: #f3f4f6;
    --text: #111827;
    --text-light: #9ca3af;
    --text-sidebar: #e5e7eb;
    --border: #e5e7eb;
    --primary: #4f46e5;
    --primary-hover: #4338ca;
    --radius: 12px;
    --sidebar-w: 260px;
}

html, body {
    height: 100%;
    font-family: -apple-system, BlinkMacSystemFont,
        'Segoe UI', Roboto, sans-serif;
    font-size: 15px;
    color: var(--text);
    background: var(--bg);
}

/* ── Layout ── */
#app {
    display: flex;
    flex-direction: column;
    height: 100%;
}

#header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 20px;
    background: var(--bg-sidebar);
    color: #fff;
}

#header h1 {
    font-size: 18px;
    font-weight: 600;
}

#sidebar-toggle {
    background: none;
    border: none;
    color: #fff;
    font-size: 20px;
    cursor: pointer;
    display: none;
}

#layout {
    display: flex;
    flex: 1;
    overflow: hidden;
}

/* ── Sidebar ── */
#sidebar {
    width: var(--sidebar-w);
    min-width: var(--sidebar-w);
    background: var(--bg-sidebar);
    color: var(--text-sidebar);
    display: flex;
    flex-direction: column;
    padding: 12px;
    overflow-y: auto;
}

#new-chat-btn {
    width: 100%;
    padding: 10px;
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: var(--radius);
    background: transparent;
    color: var(--text-sidebar);
    font-size: 14px;
    cursor: pointer;
    margin-bottom: 12px;
    transition: background 0.15s;
}

#new-chat-btn:hover {
    background: rgba(255,255,255,0.1);
}

#session-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    transition: background 0.15s;
}

.session-item:hover {
    background: rgba(255,255,255,0.1);
}

.session-item.active {
    background: rgba(255,255,255,0.15);
}

.session-item .delete-btn {
    background: none;
    border: none;
    color: var(--text-light);
    cursor: pointer;
    opacity: 0;
    font-size: 14px;
    transition: opacity 0.15s;
}

.session-item:hover .delete-btn {
    opacity: 1;
}

/* ── Chat Area ── */
#chat-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    position: relative;
    background: var(--bg-chat);
}

#messages {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.message {
    max-width: 720px;
    width: 100%;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.message .role {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-light);
}

.message .content {
    padding: 12px 16px;
    border-radius: var(--radius);
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
}

.message.user .content {
    background: var(--bg-user);
}

.message.assistant .content {
    background: var(--bg-assistant);
}

/* ── Input Bar ── */
#input-bar {
    max-width: 720px;
    width: 100%;
    margin: 0 auto;
    padding: 16px 24px 24px;
}

#message-input {
    width: 100%;
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 15px;
    font-family: inherit;
    resize: none;
    outline: none;
    line-height: 1.5;
    max-height: 200px;
    transition: border-color 0.15s;
}

#message-input:focus {
    border-color: var(--primary);
}

#input-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
}

#tool-buttons {
    display: flex;
    gap: 4px;
}

.tool-btn {
    width: 36px;
    height: 36px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg);
    cursor: pointer;
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s;
}

.tool-btn:hover:not(:disabled) {
    background: var(--bg-input);
}

.tool-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.tool-btn.active {
    border-color: var(--primary);
    background: #eef2ff;
}

#right-controls {
    display: flex;
    gap: 8px;
    align-items: center;
}

#model-select {
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 13px;
    font-family: inherit;
    background: var(--bg);
    outline: none;
    cursor: pointer;
}

#send-btn {
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 8px;
    background: var(--primary);
    color: #fff;
    font-size: 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s;
}

#send-btn:hover {
    background: var(--primary-hover);
}

/* ── Tone Popover ── */
.popover {
    position: absolute;
    bottom: 100px;
    left: 24px;
    background: var(--bg-chat);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    padding: 4px;
    z-index: 100;
}

.popover.hidden {
    display: none;
}

.popover-item {
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    transition: background 0.15s;
}

.popover-item:hover {
    background: var(--bg-input);
}

.popover-item.active {
    background: #eef2ff;
    color: var(--primary);
}

/* ── Thinking indicator ── */
.thinking {
    max-width: 720px;
    width: 100%;
    margin: 0 auto;
    color: var(--text-light);
    font-size: 14px;
    padding: 8px 0;
}

.thinking::after {
    content: '';
    animation: dots 1.5s infinite;
}

@keyframes dots {
    0%, 20% { content: '.'; }
    40% { content: '..'; }
    60%, 100% { content: '...'; }
}

/* ── Responsive ── */
@media (max-width: 768px) {
    #sidebar-toggle {
        display: block;
    }

    #sidebar {
        position: fixed;
        top: 0;
        left: 0;
        height: 100%;
        z-index: 200;
        transform: translateX(-100%);
        transition: transform 0.2s;
    }

    #sidebar.open {
        transform: translateX(0);
    }

    #input-controls {
        flex-wrap: wrap;
        gap: 8px;
    }

    #model-select {
        font-size: 12px;
    }
}
```

**Step 2: Commit**

```bash
git add packages/sonya-gateway/src/sonya/gateway/static/css/style.css
git commit -m "feat(sonya-gateway): add chat GUI stylesheet"
```

---

### Task 4: Create JavaScript — session and chat logic

**Files:**
- Create: `packages/sonya-gateway/src/sonya/gateway/static/js/app.js`

**Step 1: Write app.js**

```javascript
/* packages/sonya-gateway/src/sonya/gateway/static/js/app.js */

'use strict';

// ── State ──
const state = {
    sessions: [],        // [{id, model, title, messages: [], tone: 'default'}]
    activeSessionId: null,
};

const TONE_PROMPTS = {
    default: '',
    friendly: 'Please respond in a friendly, casual tone.',
    formal: 'Please respond in a formal, professional tone.',
    concise: 'Please respond as concisely as possible.',
};

// ── DOM refs ──
const $ = (sel) => document.querySelector(sel);
const sessionList = $('#session-list');
const messages = $('#messages');
const messageInput = $('#message-input');
const sendBtn = $('#send-btn');
const newChatBtn = $('#new-chat-btn');
const modelSelect = $('#model-select');
const toneBtn = $('#tone-btn');
const tonePopover = $('#tone-popover');
const sidebarToggle = $('#sidebar-toggle');
const sidebar = $('#sidebar');

// ── API helpers ──
async function apiCreateSession(model, systemPrompt) {
    const res = await fetch('/sessions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            model: model,
            system_prompt: systemPrompt,
        }),
    });
    return res.json();
}

async function apiDeleteSession(sessionId) {
    await fetch(`/sessions/${sessionId}`, {
        method: 'DELETE',
    });
}

async function apiUpdateSession(sessionId, systemPrompt) {
    await fetch(`/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({system_prompt: systemPrompt}),
    });
}

function apiChatStream(sessionId, message, onChunk, onDone, onError) {
    fetch(`/sessions/${sessionId}/chat`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: message}),
    }).then((res) => {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function read() {
            reader.read().then(({done, value}) => {
                if (done) {
                    onDone();
                    return;
                }
                buffer += decoder.decode(value, {stream: true});
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        if (data.text !== undefined) {
                            onChunk(data.text);
                        }
                    } else if (line.startsWith('event: error')) {
                        // next data line has error
                    } else if (line.startsWith('event: done')) {
                        // next data line has full_text
                    }
                }
                read();
            });
        }
        read();
    }).catch(onError);
}

// ── Session management ──
function getActiveSession() {
    return state.sessions.find(
        (s) => s.id === state.activeSessionId
    );
}

async function createNewChat() {
    const model = modelSelect.value;
    const session = getActiveSession();
    const tone = session ? session.tone : 'default';
    const systemPrompt = TONE_PROMPTS[tone] || '';

    const data = await apiCreateSession(model, systemPrompt);
    const newSession = {
        id: data.session_id,
        model: data.model,
        title: `Chat ${state.sessions.length + 1}`,
        messages: [],
        tone: tone,
    };
    state.sessions.unshift(newSession);
    state.activeSessionId = newSession.id;
    renderSidebar();
    renderMessages();
    messageInput.focus();
}

async function switchSession(sessionId) {
    state.activeSessionId = sessionId;
    renderSidebar();
    renderMessages();
}

async function deleteSession(sessionId) {
    await apiDeleteSession(sessionId);
    state.sessions = state.sessions.filter(
        (s) => s.id !== sessionId
    );
    if (state.activeSessionId === sessionId) {
        state.activeSessionId = state.sessions.length
            ? state.sessions[0].id
            : null;
    }
    renderSidebar();
    renderMessages();
}

// ── Send message ──
let isSending = false;

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isSending) return;

    let session = getActiveSession();
    if (!session) {
        await createNewChat();
        session = getActiveSession();
    }

    // Check if model changed
    if (session.model !== modelSelect.value) {
        await apiDeleteSession(session.id);
        const data = await apiCreateSession(
            modelSelect.value,
            TONE_PROMPTS[session.tone] || ''
        );
        session.id = data.session_id;
        session.model = data.model;
        state.activeSessionId = session.id;
        renderSidebar();
    }

    session.messages.push({role: 'user', content: text});
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Update title from first message
    if (session.messages.length === 1) {
        session.title = text.slice(0, 30) + (
            text.length > 30 ? '...' : ''
        );
        renderSidebar();
    }

    renderMessages();
    scrollToBottom();

    // Show thinking
    const thinkingEl = document.createElement('div');
    thinkingEl.className = 'thinking';
    thinkingEl.textContent = 'Thinking';
    messages.appendChild(thinkingEl);
    scrollToBottom();

    isSending = true;
    sendBtn.disabled = true;
    let assistantText = '';

    apiChatStream(
        session.id,
        text,
        (chunk) => {
            // On first chunk, remove thinking
            if (thinkingEl.parentNode) {
                thinkingEl.remove();
            }
            assistantText += chunk;
            renderStreamingMessage(assistantText);
            scrollToBottom();
        },
        () => {
            // Done
            if (thinkingEl.parentNode) {
                thinkingEl.remove();
            }
            session.messages.push({
                role: 'assistant',
                content: assistantText,
            });
            isSending = false;
            sendBtn.disabled = false;
            renderMessages();
            scrollToBottom();
        },
        (err) => {
            if (thinkingEl.parentNode) {
                thinkingEl.remove();
            }
            session.messages.push({
                role: 'assistant',
                content: `Error: ${err.message}`,
            });
            isSending = false;
            sendBtn.disabled = false;
            renderMessages();
        }
    );
}

// ── Rendering ──
function renderSidebar() {
    sessionList.innerHTML = '';
    for (const s of state.sessions) {
        const el = document.createElement('div');
        el.className = 'session-item'
            + (s.id === state.activeSessionId ? ' active' : '');
        el.innerHTML = `
            <span>${escapeHtml(s.title)}</span>
            <button class="delete-btn" title="Delete">&times;</button>
        `;
        el.querySelector('span').onclick = () =>
            switchSession(s.id);
        el.querySelector('.delete-btn').onclick = (e) => {
            e.stopPropagation();
            deleteSession(s.id);
        };
        sessionList.appendChild(el);
    }
}

function renderMessages() {
    const session = getActiveSession();
    messages.innerHTML = '';
    if (!session) return;

    for (const msg of session.messages) {
        messages.appendChild(createMessageEl(msg));
    }
    scrollToBottom();
}

function renderStreamingMessage(text) {
    // Remove previous streaming element if exists
    const prev = messages.querySelector('.streaming');
    if (prev) prev.remove();

    const el = createMessageEl({
        role: 'assistant',
        content: text,
    });
    el.classList.add('streaming');
    messages.appendChild(el);
}

function createMessageEl(msg) {
    const el = document.createElement('div');
    el.className = `message ${msg.role}`;
    el.innerHTML = `
        <div class="role">${
            msg.role === 'user' ? 'You' : 'Sonya'
        }</div>
        <div class="content">${escapeHtml(msg.content)}</div>
    `;
    return el;
}

function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Tone popover ──
function setTone(tone) {
    const session = getActiveSession();
    if (!session) return;

    session.tone = tone;
    apiUpdateSession(
        session.id,
        TONE_PROMPTS[tone] || ''
    );

    // Update popover active state
    tonePopover.querySelectorAll('.popover-item').forEach(
        (el) => {
            el.classList.toggle(
                'active', el.dataset.tone === tone
            );
        }
    );
    toneBtn.classList.toggle('active', tone !== 'default');
    tonePopover.classList.add('hidden');
}

// ── Auto-resize textarea ──
function autoResize() {
    messageInput.style.height = 'auto';
    messageInput.style.height =
        Math.min(messageInput.scrollHeight, 200) + 'px';
}

// ── Event listeners ──
sendBtn.addEventListener('click', sendMessage);

messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

messageInput.addEventListener('input', autoResize);

newChatBtn.addEventListener('click', createNewChat);

toneBtn.addEventListener('click', () => {
    tonePopover.classList.toggle('hidden');
});

tonePopover.querySelectorAll('.popover-item').forEach(
    (el) => {
        el.addEventListener('click', () => {
            setTone(el.dataset.tone);
        });
    }
);

sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
});

// Close popover on outside click
document.addEventListener('click', (e) => {
    if (!toneBtn.contains(e.target)
        && !tonePopover.contains(e.target)) {
        tonePopover.classList.add('hidden');
    }
    // Close sidebar on mobile when clicking outside
    if (window.innerWidth <= 768
        && !sidebar.contains(e.target)
        && !sidebarToggle.contains(e.target)) {
        sidebar.classList.remove('open');
    }
});

// ── Init ──
messageInput.focus();
```

**Step 2: Verify by starting server and visiting localhost**

Run: `cd packages/sonya-gateway && python -m uvicorn sonya.gateway.server:app --port 8340`
Then visit: `http://localhost:8340/`
Expected: Chat GUI loads with sidebar, input bar, model selector, tone button

**Step 3: Commit**

```bash
git add packages/sonya-gateway/src/sonya/gateway/static/js/app.js
git commit -m "feat(sonya-gateway): add chat GUI JavaScript with multi-session and SSE streaming"
```

---

### Task 5: Add GET /sessions endpoint for listing sessions

**Files:**
- Modify: `packages/sonya-gateway/src/sonya/gateway/server.py`
- Modify: `packages/sonya-gateway/src/sonya/gateway/session.py`
- Test: `packages/sonya-gateway/tests/test_server.py` (append)

**Step 1: Write the failing test**

Append to `packages/sonya-gateway/tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_list_sessions(client):
    # Create a session first
    res = await client.post('/sessions', json={
        'model': 'gpt-4o',
        'api_key': 'test-key',
    })
    assert res.status_code == 201

    # List sessions
    res = await client.get('/sessions')
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert 'session_id' in data[0]
    assert 'model' in data[0]
```

**Step 2: Run test to verify it fails**

Run: `cd packages/sonya-gateway && python -m pytest tests/test_server.py::test_list_sessions -v`
Expected: FAIL — 404 or method not allowed

**Step 3: Add list_all to SessionManager**

In `packages/sonya-gateway/src/sonya/gateway/session.py`, add method:

```python
    def list_all(self) -> list[dict[str, str | int]]:
        """Return summary of all sessions.

        Returns:
            List of session info dicts.
        """
        return [
            {
                'session_id': sid,
                'model': data['model'],
                'system_prompt': data['system_prompt'],
                'message_count': len(data['history']),
            }
            for sid, data in self._sessions.items()
        ]
```

**Step 4: Add GET /sessions endpoint in server.py**

```python
@app.get('/sessions')
async def list_sessions() -> list[dict]:
    """List all active sessions."""
    return session_manager.list_all()
```

**Step 5: Run test to verify it passes**

Run: `cd packages/sonya-gateway && python -m pytest tests/test_server.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add packages/sonya-gateway/src/sonya/gateway/session.py packages/sonya-gateway/src/sonya/gateway/server.py packages/sonya-gateway/tests/test_server.py
git commit -m "feat(sonya-gateway): add GET /sessions endpoint for listing sessions"
```

---

### Task 6: Create Cloud Run deployment files

**Files:**
- Create: `deploy/cloud-run/Dockerfile`
- Create: `deploy/cloud-run/.dockerignore`

**Step 1: Create Dockerfile**

```dockerfile
# deploy/cloud-run/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy packages
COPY packages/sonya-core/ packages/sonya-core/
COPY packages/sonya-gateway/ packages/sonya-gateway/

# Install sonya-core then sonya-gateway
RUN uv pip install --system \
    ./packages/sonya-core[all] \
    ./packages/sonya-gateway

# Cloud Run provides PORT env var (default 8080)
ENV PORT=8080

EXPOSE ${PORT}

CMD uvicorn sonya.gateway.server:app \
    --host 0.0.0.0 \
    --port ${PORT}
```

**Step 2: Create .dockerignore**

```
# deploy/cloud-run/.dockerignore
__pycache__
*.pyc
.venv
.git
.pytest_cache
*.egg-info
tests/
docs/
*.md
```

**Step 3: Verify Docker build (if Docker available)**

Run from project root:
```bash
docker build -f deploy/cloud-run/Dockerfile -t sonya-gateway .
```
Expected: Build succeeds

**Step 4: Commit**

```bash
git add deploy/
git commit -m "feat(deploy): add Cloud Run Dockerfile for sonya-gateway"
```

---

### Task 7: Update gateway __init__.py for PORT env var support

**Files:**
- Modify: `packages/sonya-gateway/src/sonya/gateway/__init__.py`

**Step 1: Update run_server to read PORT env var**

```python
"""Sonya Gateway — REST + SSE server for LLM sessions."""

import os

import uvicorn


def run_server(
    host: str = '0.0.0.0',
    port: int | None = None,
) -> None:
    """Start the gateway server.

    Args:
        host: Bind address.
        port: Bind port. Defaults to PORT env var or 8340.
    """
    if port is None:
        port = int(os.environ.get('PORT', '8340'))
    uvicorn.run(
        'sonya.gateway.server:app',
        host=host,
        port=port,
    )
```

**Step 2: Commit**

```bash
git add packages/sonya-gateway/src/sonya/gateway/__init__.py
git commit -m "feat(sonya-gateway): support PORT env var for Cloud Run"
```

---

### Task 8: End-to-end manual verification

**Step 1: Start gateway locally**

```bash
source .venv/bin/activate
cd packages/sonya-gateway && python -m uvicorn sonya.gateway.server:app --port 8340 --reload
```

**Step 2: Open browser**

Visit: `http://localhost:8340/`

**Step 3: Verify checklist**

- [ ] Page loads with sidebar + chat area + input bar
- [ ] [+ New Chat] creates a session and shows in sidebar
- [ ] Model selector dropdown works
- [ ] Tone button shows popover with 4 options
- [ ] Sending a message streams response (if API key set)
- [ ] Multiple sessions can be created and switched
- [ ] Session delete works
- [ ] Mobile responsive (resize window narrow)
- [ ] Hamburger menu toggles sidebar on mobile

**Step 4: Run all gateway tests**

```bash
cd packages/sonya-gateway && python -m pytest tests/ -v
```
Expected: All tests pass

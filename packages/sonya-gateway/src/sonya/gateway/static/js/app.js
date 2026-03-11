'use strict';

// ── State ──
const state = {
    sessions: [],
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
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.text !== undefined) {
                                onChunk(data.text);
                            }
                        } catch (e) {
                            // skip malformed data
                        }
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
            if (thinkingEl.parentNode) {
                thinkingEl.remove();
            }
            assistantText += chunk;
            renderStreamingMessage(assistantText);
            scrollToBottom();
        },
        () => {
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
    if (window.innerWidth <= 768
        && !sidebar.contains(e.target)
        && !sidebarToggle.contains(e.target)) {
        sidebar.classList.remove('open');
    }
});

// ── Init ──
messageInput.focus();

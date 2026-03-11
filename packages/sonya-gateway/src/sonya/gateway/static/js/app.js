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
const modelSelect = $('#model-select'); // This is now a hidden input
const modelSelectBtn = $('#model-select-btn');
const modelDropdown = $('#model-dropdown');
const customModelWrapper = $('#custom-model-wrapper');
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

// ── Dropdown Helper ──
const PROVIDER_ICONS = {
    gemini: `<svg role="img" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><title>Google Gemini</title><path d="M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81"/></svg>`,
    claude: `<svg role="img" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><title>Anthropic</title><path d="M17.3041 3.541h-3.6718l6.696 16.918H24Zm-10.6082 0L0 20.459h3.7442l1.3693-3.5527h7.0052l1.3693 3.5528h3.7442L10.5363 3.5409Zm-.3712 10.2232 2.2914-5.9456 2.2914 5.9456Z"/></svg>`,
    gpt: `<svg role="img" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><title>OpenAI</title><path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z"/></svg>`
};

function getProviderClass(modelId) {
    if (!modelId) return '';
    const id = modelId.toLowerCase();
    if (id.includes('gemini')) return 'gemini';
    if (id.includes('claude') || id.includes('anthropic')) return 'claude';
    if (id.includes('gpt') || id.includes('openai')) return 'gpt';
    return '';
}

function formatModelName(name) {
    if (!name) return "";
    
    // Replace hyphen between digits with a dot (e.g., 3-5 -> 3.5)
    let formatted = name.replace(/(\d)-(\d)/g, '$1.$2');
    
    // Replace remaining hyphens and underscores with spaces
    formatted = formatted.replace(/[-_]/g, ' ');
    
    // Determine title casing with specific acronym exceptions
    formatted = formatted.split(' ').map(word => {
        if (!word) return '';
        const lower = word.toLowerCase();
        // Special handles for acronyms
        if (lower === 'gpt') return 'GPT';
        if (lower === 'openai') return 'OpenAI';
        
        // Capitalize first letter
        return word.charAt(0).toUpperCase() + word.slice(1);
    }).join(' ');

    return formatted;
}

function updateModelDropdownUI() {
    const val = modelSelect.value;
    const activeOpt = modelDropdown.querySelector(`.model-option[data-value="${val}"]`);
    if (activeOpt) {
        // Update button text and icon
        const fullName = formatModelName(activeOpt.dataset.full);
        modelSelectBtn.querySelector('.model-name').textContent = fullName;
        
        const icon = modelSelectBtn.querySelector('.provider-icon');
        const provider = getProviderClass(val);
        icon.className = 'provider-icon'; // reset
        icon.innerHTML = provider ? PROVIDER_ICONS[provider] : '';
        if (provider) icon.classList.add(provider);
        
        // Update active class in dropdown
        modelDropdown.querySelectorAll('.model-option').forEach(el => el.classList.remove('active'));
        activeOpt.classList.add('active');
    }
}
updateModelDropdownUI(); // initial call

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

// Close popovers on outside click
document.addEventListener('click', (e) => {
    if (!toneBtn.contains(e.target) && !tonePopover.contains(e.target)) {
        tonePopover.classList.add('hidden');
    }
    if (!modelSelectBtn.contains(e.target) && !modelDropdown.contains(e.target)) {
        customModelWrapper.classList.remove('open');
        modelDropdown.classList.add('hidden');
    }
    if (window.innerWidth <= 768
        && !sidebar.contains(e.target)
        && !sidebarToggle.contains(e.target)) {
        sidebar.classList.remove('open');
    }
});

// Custom model select events
modelSelectBtn.addEventListener('click', () => {
    customModelWrapper.classList.toggle('open');
    modelDropdown.classList.toggle('hidden');
});

modelDropdown.querySelectorAll('.model-option').forEach(opt => {
    opt.addEventListener('click', () => {
        modelSelect.value = opt.dataset.value;
        updateModelDropdownUI();
        customModelWrapper.classList.remove('open');
        modelDropdown.classList.add('hidden');
    });
});

// Initialize provider icons and format names in dropdown
modelDropdown.querySelectorAll('.model-option').forEach(opt => {
    // Inject Provider icon
    const p = getProviderClass(opt.dataset.value);
    const iconContainer = opt.querySelector('.provider-icon');
    if (p) {
        iconContainer.classList.add(p);
        iconContainer.innerHTML = PROVIDER_ICONS[p];
    }
    
    // Format model string
    const nameEl = opt.querySelector('.opt-model-name');
    if (nameEl && opt.dataset.full) {
        nameEl.textContent = formatModelName(opt.dataset.full);
    }
});

// ── Init ──
messageInput.focus();

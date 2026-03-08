const chatHistory = document.getElementById('chat-history');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const approvalModal = document.getElementById('approval-modal');
const approvalText = document.getElementById('approval-text');
const approveBtn = document.getElementById('approve-btn');
const rejectBtn = document.getElementById('reject-btn');
const typingIndicator = document.getElementById('typing-indicator');

// Trace Modal Elements
const traceModal = document.getElementById('trace-modal');
const closeTraceBtn = document.getElementById('close-trace-btn');
const traceBody = document.getElementById('trace-body');

// Generate a random thread_id if not present
let threadId = localStorage.getItem('threadId') || 'user_' + Math.random().toString(36).substring(7);
localStorage.setItem('threadId', threadId);

const SESSION_TOKEN = 'session_abc123';

// --- Guardrail badge mappings ---
const GUARDRAIL_ICONS = {
    'BLOCK': { icon: '🚫', cls: 'badge-block', label: 'Blocked' },
    'REDACT': { icon: '🔒', cls: 'badge-redact', label: 'PII Redacted' },
    'MASK': { icon: '🔒', cls: 'badge-redact', label: 'PII Masked' },
    'REWRITE': { icon: '✏️', cls: 'badge-rewrite', label: 'Rewritten' },
    'THROTTLED': { icon: '⏳', cls: 'badge-throttle', label: 'Rate Limited' },
    'PASS': { icon: '✅', cls: 'badge-pass', label: 'Passed' },
};

function createGuardrailBadges(guardrails, traceData) {
    if (!guardrails || guardrails.length === 0) return '';

    const badges = guardrails.map(g => {
        const info = GUARDRAIL_ICONS[g.action] || { icon: 'ℹ️', cls: 'badge-info', label: g.action };
        const detail = g.detail ? `: ${g.detail}` : '';
        return `<span class="guardrail-badge ${info.cls}" title="${g.stage}${detail}">
            ${info.icon} ${g.stage}
        </span>`;
    }).join('');

    // Add "View Trace" button if trace data exists
    let traceBtn = '';
    if (traceData && Object.keys(traceData).length > 0) {
        // Store trace data in a global map or directly on the element (using DOM stringification)
        const traceJson = escapeHtml(JSON.stringify({ guardrails, trace: traceData }));
        traceBtn = `<button class="trace-button" onclick="showTraceModal(this)" data-trace="${traceJson}">🔍 Trace</button>`;
    }

    return `<div class="guardrail-badges">${badges}${traceBtn}</div>`;
}

function appendMessage(role, content, guardrails = [], traceData = null) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const badgesHtml = role === 'assistant' ? createGuardrailBadges(guardrails, traceData) : '';

    div.innerHTML = `
        <div class="message-content">${escapeHtml(content)}</div>
        ${badgesHtml}
        <div class="message-time">${time}</div>
    `;

    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    // Keep quotes intact for JSON parsing later, but escape angled brackets
    return div.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function showTyping() {
    typingIndicator.classList.remove('hidden');
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function hideTyping() {
    typingIndicator.classList.add('hidden');
}

function setInputEnabled(enabled) {
    userInput.disabled = !enabled;
    sendBtn.disabled = !enabled;
    if (enabled) {
        userInput.focus();
    }
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    appendMessage('user', message);
    userInput.value = '';
    setInputEnabled(false);
    showTyping();

    try {
        const response = await fetch('http://localhost:8001/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages: [{ role: 'user', content: message }],
                thread_id: threadId,
                session_token: SESSION_TOKEN
            })
        });

        const data = await response.json();
        hideTyping();

        if (data.detail) {
            // FastAPI error response
            appendMessage('assistant', `Sorry, something went wrong: ${data.detail}`);
        } else if (data.is_paused) {
            showApprovalModal(data.content);
        } else {
            appendMessage('assistant', data.content || 'No response received.', data.guardrails || [], data.trace || null);
        }
    } catch (error) {
        hideTyping();
        appendMessage('assistant', "I can't reach the server right now. Please make sure the backend is running on port 8001.");
        console.error('[Chat Error]', error);
    } finally {
        setInputEnabled(true);
    }
});

function showApprovalModal(text) {
    approvalText.textContent = text;
    approvalModal.classList.remove('hidden');
}

approveBtn.addEventListener('click', async () => {
    await sendApproval('approve');
});

rejectBtn.addEventListener('click', async () => {
    await sendApproval('reject');
});

async function sendApproval(decision) {
    approvalModal.classList.add('hidden');
    showTyping();
    setInputEnabled(false);

    try {
        const response = await fetch('http://localhost:8001/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                thread_id: threadId,
                decision: decision
            })
        });

        const data = await response.json();
        hideTyping();
        appendMessage('assistant', data.content || 'Action processed.', data.guardrails || []);
    } catch (error) {
        hideTyping();
        appendMessage('assistant', "Error sending approval decision. Please try again.");
    } finally {
        setInputEnabled(true);
    }
}

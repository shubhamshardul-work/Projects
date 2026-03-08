const chatHistory = document.getElementById('chat-history');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const approvalModal = document.getElementById('approval-modal');
const approvalText = document.getElementById('approval-text');
const approveBtn = document.getElementById('approve-btn');
const rejectBtn = document.getElementById('reject-btn');

// Generate a random thread_id if not present
let threadId = localStorage.getItem('threadId') || 'user_' + Math.random().toString(36).substring(7);
localStorage.setItem('threadId', threadId);

const SESSION_TOKEN = 'session_abc123'; // Mock session token

function appendMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    div.innerHTML = `
        <div class="message-content">${content}</div>
        <div class="message-time">${time}</div>
    `;

    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    appendMessage('user', message);
    userInput.value = '';

    try {
        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages: [{ role: 'user', content: message }],
                thread_id: threadId,
                session_token: SESSION_TOKEN
            })
        });

        const data = await response.json();

        if (data.is_paused) {
            showApprovalModal(data.content);
        } else {
            appendMessage('assistant', data.content);
        }
    } catch (error) {
        appendMessage('assistant', "Sorry, I can't connect to the server. Please make sure the backend is running.");
        console.error(error);
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

    try {
        const response = await fetch('http://localhost:8000/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                thread_id: threadId,
                decision: decision
            })
        });

        const data = await response.json();
        appendMessage('assistant', data.content);
    } catch (error) {
        appendMessage('assistant', "Error sending approval decision.");
    }
}

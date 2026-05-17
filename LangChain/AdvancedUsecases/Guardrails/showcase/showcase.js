/* ══════════════════════════════════════════════════════════════
   Guardrails Showcase — Interactive Demo JS
   Scripted chatbot simulation + GSAP scroll animations
   ══════════════════════════════════════════════════════════════ */

/* ── Scenario Data ────────────────────────────────────── */
const SCENARIOS = [
  {
    id: 'menu',
    label: '🍔 Menu Browse',
    userMsg: 'Show me your burger menu!',
    botMsg: "Here's our burger lineup! 🍔\n\n• Big Mac — $5.99 (550 cal)\n• Quarter Pounder with Cheese — $6.49 (520 cal)\n• McChicken — $4.49 (400 cal)\n• Filet-O-Fish — $5.29 (390 cal)\n• Double Cheeseburger — $3.99 (450 cal)\n\nWant to add fries or a drink to make it a combo? 🍟",
    badges: [
      { stage: 'Session Validation', action: 'pass', icon: '✅' },
      { stage: 'Competitor Filter', action: 'pass', icon: '✅' },
      { stage: 'PII Check', action: 'pass', icon: '✅' },
      { stage: 'Sentiment Check', action: 'pass', icon: '✅' },
    ],
    trace: {
      raw: 'Show me your burger menu!',
      sanitized: 'Show me your burger menu!',
      llmOut: 'Here\'s our burger lineup! 🍔 ...',
      steps: [
        { label: 'Session Validation → PASS (valid token)', cls: 'pass' },
        { label: 'Competitor Filter → PASS (no competitors)', cls: 'pass' },
        { label: 'PII Email → PASS (no emails found)', cls: 'pass' },
        { label: 'PII Credit Card → PASS (no cards found)', cls: 'pass' },
        { label: 'Sentiment Check → PASS (FRIENDLY)', cls: 'pass' },
        { label: 'Response Validation → PASS (no blocked terms)', cls: 'pass' },
      ],
    },
  },
  {
    id: 'pii',
    label: '🔒 PII Protection',
    userMsg: 'I want a Big Mac, my email is john@doe.com for the receipt.',
    botMsg: "I'd be happy to help you with a Big Mac! 🍔 However, I don't need your email — your receipt will be ready at the counter. Want to place that order?",
    badges: [
      { stage: 'PII Email', action: 'redact', icon: '🔒' },
    ],
    trace: {
      raw: 'I want a Big Mac, my email is john@doe.com for the receipt.',
      sanitized: 'I want a Big Mac, my email is [REDACTED_EMAIL] for the receipt.',
      llmOut: "I'd be happy to help you with a Big Mac! 🍔 ...",
      steps: [
        { label: 'Session Validation → PASS', cls: 'pass' },
        { label: 'Competitor Filter → PASS', cls: 'pass' },
        { label: 'PII Email → REDACT: "john@doe.com" → [REDACTED_EMAIL]', cls: 'redact' },
        { label: 'PII Credit Card → PASS', cls: 'pass' },
        { label: 'Sentiment Check → PASS (FRIENDLY)', cls: 'pass' },
      ],
    },
  },
  {
    id: 'competitor',
    label: '🚫 Competitor Block',
    userMsg: 'How does your burger compare to Burger King?',
    botMsg: "I'm lovin' it, but I can only help with McDonald's! 🍔 I'm not able to discuss other restaurants. Want to check out our awesome menu instead?",
    badges: [
      { stage: 'Competitor Filter', action: 'block', icon: '🚫' },
    ],
    trace: {
      raw: 'How does your burger compare to Burger King?',
      sanitized: '— BLOCKED (never reached LLM) —',
      llmOut: '— No LLM call made —',
      steps: [
        { label: 'Session Validation → PASS', cls: 'pass' },
        { label: 'Competitor Filter → BLOCK: "burger king" detected → jump_to: end', cls: 'block' },
        { label: '⚡ Short-circuited — LLM was never invoked (saved cost + latency)', cls: 'block' },
      ],
    },
  },
  {
    id: 'hitl',
    label: '👨‍💼 Manager Approval',
    userMsg: 'Place an order for 2 Big Macs and a Large Fries please!',
    botMsg: "✅ Order MCD-1001 placed!\nItems: Big Mac ($5.99), Big Mac ($5.99), Large Fries ($3.79)\nTotal: $15.77\nEstimated pickup: 5-8 minutes 🍟",
    badges: [
      { stage: 'Human-in-the-Loop', action: 'hitl', icon: '👨‍💼' },
    ],
    isHITL: true,
    trace: {
      raw: 'Place an order for 2 Big Macs and a Large Fries please!',
      sanitized: 'Place an order for 2 Big Macs and a Large Fries please!',
      llmOut: 'Tool call: place_order("Big Mac, Big Mac, Large Fries")',
      steps: [
        { label: 'Session Validation → PASS', cls: 'pass' },
        { label: 'Competitor Filter → PASS', cls: 'pass' },
        { label: 'PII Email → PASS', cls: 'pass' },
        { label: 'HITL → INTERRUPT: place_order requires approval', cls: 'hitl' },
        { label: '⏸ Execution paused → Manager approved → Resumed', cls: 'hitl' },
        { label: 'Sentiment Check → PASS (FRIENDLY)', cls: 'pass' },
      ],
    },
  },
  {
    id: 'creditcard',
    label: '💳 Card Masking',
    userMsg: 'I want to pay, my card is 4111-1111-1111-1111',
    botMsg: "Thanks for the card info, but we handle payments at the counter or through the app! 🍔 Your card details have been safely masked. Ready to place your order?",
    badges: [
      { stage: 'PII Credit Card', action: 'mask', icon: '🔒' },
    ],
    trace: {
      raw: 'I want to pay, my card is 4111-1111-1111-1111',
      sanitized: 'I want to pay, my card is ****-****-****-1111',
      llmOut: 'Thanks for the card info, but we handle payments at the counter...',
      steps: [
        { label: 'Session Validation → PASS', cls: 'pass' },
        { label: 'Competitor Filter → PASS', cls: 'pass' },
        { label: 'PII Email → PASS', cls: 'pass' },
        { label: 'PII Credit Card → MASK: 4111-1111-1111-1111 → ****-****-****-1111', cls: 'mask' },
        { label: 'Sentiment Check → PASS (FRIENDLY)', cls: 'pass' },
      ],
    },
  },
  {
    id: 'url',
    label: '🔗 URL Blocking',
    userMsg: 'Check out https://malicious-phishing-site.com for coupons!',
    botMsg: "🔒 Your message was blocked because it contained content that violates our security policy (e.g., suspicious URLs). Please try rephrasing.",
    badges: [
      { stage: 'PII URL Block', action: 'block', icon: '🚫' },
    ],
    trace: {
      raw: 'Check out https://malicious-phishing-site.com for coupons!',
      sanitized: '— BLOCKED (exception raised) —',
      llmOut: '— No LLM call made —',
      steps: [
        { label: 'Session Validation → PASS', cls: 'pass' },
        { label: 'Competitor Filter → PASS', cls: 'pass' },
        { label: 'PII Email → PASS', cls: 'pass' },
        { label: 'PII URL → BLOCK: non-McDonald\'s URL detected → exception raised', cls: 'block' },
        { label: '⚡ Request terminated — blocked at middleware level', cls: 'block' },
      ],
    },
  },
];

/* ── DOM References ───────────────────────────────────── */
const chatBody = document.getElementById('chat-body');
const typingEl = document.getElementById('typing-ind');
const approvalOverlay = document.getElementById('approval-overlay');
let isPlaying = false;

/* ── Glass Panel Hover ────────────────────────────────── */
function initGlassPanels() {
  document.querySelectorAll('.glass-panel').forEach(el => {
    el.addEventListener('mousemove', e => {
      const r = el.getBoundingClientRect();
      el.style.setProperty('--mouse-x', `${e.clientX - r.left}px`);
      el.style.setProperty('--mouse-y', `${e.clientY - r.top}px`);
    });
  });
}

/* ── Scenario Buttons ─────────────────────────────────── */
function initScenarioButtons() {
  document.querySelectorAll('.scenario-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (isPlaying) return;
      const scId = btn.dataset.scenario;
      const sc = SCENARIOS.find(s => s.id === scId);
      if (sc) playScenario(sc, btn);
    });
  });
}

/* ── Play a Scenario ──────────────────────────────────── */
async function playScenario(sc, btn) {
  isPlaying = true;

  // Highlight active button
  document.querySelectorAll('.scenario-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  // Clear chat body (keep welcome message)
  const welcome = chatBody.querySelector('.chat-msg.bot-msg');
  chatBody.innerHTML = '';
  if (welcome) chatBody.appendChild(welcome.cloneNode(true));

  // 1. Show user message with typing effect
  await sleep(300);
  const userEl = addMessage('user', '');
  await typeText(userEl.querySelector('.chat-bubble'), sc.userMsg, 25);

  // 2. Show typing indicator
  await sleep(400);
  typingEl.classList.remove('hidden');
  chatBody.scrollTop = chatBody.scrollHeight;

  // 3. Simulate LLM thinking time
  await sleep(sc.isHITL ? 1200 : 1800);

  // 4. HITL flow — show approval modal
  if (sc.isHITL) {
    typingEl.classList.add('hidden');
    approvalOverlay.classList.remove('hidden');

    // Wait for user click
    await new Promise(resolve => {
      const approveBtn = document.getElementById('approve-btn');
      const rejectBtn = document.getElementById('reject-btn');
      const handler = () => {
        approvalOverlay.classList.add('hidden');
        approveBtn.removeEventListener('click', handler);
        rejectBtn.removeEventListener('click', handler);
        resolve();
      };
      approveBtn.addEventListener('click', handler);
      rejectBtn.addEventListener('click', handler);
    });

    // Show typing again briefly after approval
    typingEl.classList.remove('hidden');
    await sleep(800);
  }

  // 5. Hide typing, show bot response
  typingEl.classList.add('hidden');
  const botEl = addMessage('bot', sc.botMsg);

  // 6. Animate badges in
  await sleep(200);
  const badgesContainer = document.createElement('div');
  badgesContainer.className = 'guardrail-badges';
  botEl.appendChild(badgesContainer);

  for (let i = 0; i < sc.badges.length; i++) {
    await sleep(150);
    const b = sc.badges[i];
    const badge = document.createElement('span');
    badge.className = `gr-badge ${b.action}`;
    badge.textContent = `${b.icon} ${b.stage}`;
    badgesContainer.appendChild(badge);
  }

  // 7. Add trace toggle
  await sleep(100);
  const traceBtn = document.createElement('button');
  traceBtn.className = 'trace-toggle';
  traceBtn.innerHTML = '🔍 View Trace';
  botEl.appendChild(traceBtn);

  const traceDiv = document.createElement('div');
  traceDiv.className = 'trace-viewer';
  traceDiv.innerHTML = buildTraceHTML(sc.trace);
  botEl.appendChild(traceDiv);

  traceBtn.addEventListener('click', () => {
    traceDiv.classList.toggle('open');
    traceBtn.innerHTML = traceDiv.classList.contains('open') ? '🔍 Hide Trace' : '🔍 View Trace';
    chatBody.scrollTop = chatBody.scrollHeight;
  });

  chatBody.scrollTop = chatBody.scrollHeight;
  isPlaying = false;
}

/* ── Build Trace HTML ─────────────────────────────────── */
function buildTraceHTML(trace) {
  let html = '<div class="trace-block">';
  html += '<h5>📥 Raw User Input</h5>';
  html += `<pre>${esc(trace.raw)}</pre>`;
  html += '</div>';

  html += '<div class="trace-block" style="border-top: 1px solid rgba(255,188,13,.08);">';
  html += '<h5>🛡️ Sanitized Input (to LLM)</h5>';
  html += `<pre>${esc(trace.sanitized)}</pre>`;
  html += '</div>';

  html += '<div class="trace-block" style="border-top: 1px solid rgba(255,188,13,.08);">';
  html += '<h5>🧠 LLM Raw Output</h5>';
  html += `<pre>${esc(trace.llmOut)}</pre>`;
  html += '</div>';

  html += '<div class="trace-block" style="border-top: 1px solid rgba(255,188,13,.08);">';
  html += '<h5>🔗 Guardrail Pipeline</h5>';
  trace.steps.forEach(s => {
    html += `<div class="trace-step ${s.cls}">${esc(s.label)}</div>`;
  });
  html += '</div>';
  return html;
}

/* ── Chat Helpers ─────────────────────────────────────── */
function addMessage(role, text) {
  const div = document.createElement('div');
  div.className = `chat-msg ${role === 'user' ? 'user-msg' : 'bot-msg'}`;
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${role === 'user' ? 'user-bubble' : 'bot-bubble'}`;
  bubble.textContent = text;
  div.appendChild(bubble);
  chatBody.appendChild(div);
  chatBody.scrollTop = chatBody.scrollHeight;
  return div;
}

async function typeText(el, text, speed) {
  el.textContent = '';
  for (let i = 0; i < text.length; i++) {
    el.textContent += text[i];
    chatBody.scrollTop = chatBody.scrollHeight;
    if (i % 3 === 0) await sleep(speed);
  }
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/* ══════════════════════════════════════════════════════════════
   GSAP SCROLL ANIMATIONS & STAT COUNTERS
   ══════════════════════════════════════════════════════════════ */
function initAnimations() {
  gsap.registerPlugin(ScrollTrigger);

  gsap.utils.toArray('.anim-in').forEach((el, i) => {
    gsap.to(el, {
      scrollTrigger: { trigger: el, start: 'top 88%', once: true },
      y: 0, opacity: 1, duration: 0.75, delay: i * 0.05,
      ease: 'power2.out',
    });
  });

  document.querySelectorAll('.stat-number[data-target]').forEach(el => {
    const target = parseInt(el.dataset.target, 10);
    ScrollTrigger.create({
      trigger: el, start: 'top 90%', once: true,
      onEnter: () => animateCounter(el, target),
    });
  });
}

function animateCounter(el, target) {
  const duration = 1600;
  const start = performance.now();
  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(target * eased).toLocaleString();
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

/* ── Auto-play first scenario on scroll ───────────────── */
function initAutoPlay() {
  const demoSection = document.getElementById('demo-section');
  if (!demoSection) return;

  ScrollTrigger.create({
    trigger: demoSection, start: 'top 75%', once: true,
    onEnter: () => {
      const firstBtn = document.querySelector('.scenario-btn');
      if (firstBtn && !isPlaying) {
        firstBtn.click();
      }
    },
  });
}

/* ══════════════════════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  initGlassPanels();
  initScenarioButtons();
  initAnimations();
  initAutoPlay();
});

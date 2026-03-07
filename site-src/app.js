// ── Config ────────────────────────────────────
const GITHUB_OWNER = 'shubhamshardul-work';
const GITHUB_REPO = 'Projects';
const WORKFLOW_FILE = 'genai_news.yml';
const PAT_KEY = 'genai_github_pat';

// ── DOM References ────────────────────────────
const reportBody = document.getElementById('report-body');
const reportDate = document.getElementById('report-date');
const reportLabel = document.getElementById('report-label');
const archiveList = document.getElementById('archive-list');
const btnGenerate = document.getElementById('btn-generate');
const statusBanner = document.getElementById('status-banner');
const statusText = document.getElementById('status-text');
const statusClose = document.getElementById('status-close');
const patModal = document.getElementById('pat-modal');
const patInput = document.getElementById('pat-input');
const patSubmit = document.getElementById('pat-submit');
const patCancel = document.getElementById('pat-cancel');
const patClear = document.getElementById('pat-clear');

let reportsIndex = [];

// ── Init ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadReportsIndex();
  setupEventListeners();
});

// ── Load Reports Index ────────────────────────
async function loadReportsIndex() {
  try {
    const res = await fetch('reports-index.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    reportsIndex = await res.json();

    if (reportsIndex.length > 0) {
      renderArchive();
      loadReport(reportsIndex[0].filename, 0);
    } else {
      reportBody.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">No reports generated yet. Click <strong>Generate New Report</strong> above!</p>';
    }
  } catch (err) {
    console.error('Failed to load reports index:', err);
    reportBody.innerHTML = '<p style="color: var(--error); text-align: center; padding: 2rem;">Failed to load reports. Please try refreshing the page.</p>';
  }
}

// ── Render Archive Sidebar ────────────────────
function renderArchive() {
  archiveList.innerHTML = '';
  reportsIndex.forEach((report, idx) => {
    const li = document.createElement('li');
    li.className = 'archive-item';
    li.dataset.index = idx;
    li.innerHTML = `
      <div class="archive-item-date">${formatDate(report.date)}</div>
      <div class="archive-item-title">${escapeHtml(report.title)}</div>
    `;
    li.addEventListener('click', () => loadReport(report.filename, idx));
    archiveList.appendChild(li);
  });
}

// ── Load a Single Report ──────────────────────
async function loadReport(filename, activeIdx) {
  // Update active state in archive
  document.querySelectorAll('.archive-item').forEach((el, i) => {
    el.classList.toggle('active', i === activeIdx);
  });

  const report = reportsIndex[activeIdx];
  reportLabel.textContent = activeIdx === 0 ? '📡 Latest Report' : '📄 Report';
  reportDate.textContent = formatDate(report.date);

  // Show loading
  reportBody.innerHTML = `<div class="loading-skeleton">
    <div class="skeleton-line skeleton-line--title"></div>
    <div class="skeleton-line"></div>
    <div class="skeleton-line"></div>
    <div class="skeleton-line skeleton-line--short"></div>
  </div>`;

  try {
    const res = await fetch(`reports/${filename}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const md = await res.text();
    reportBody.innerHTML = marked.parse(md);
    // Smooth scroll to report on mobile
    if (window.innerWidth <= 900) {
      document.getElementById('report-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } catch (err) {
    console.error('Failed to load report:', err);
    reportBody.innerHTML = '<p style="color: var(--error);">Failed to load this report.</p>';
  }
}

// ── Event Listeners ───────────────────────────
function setupEventListeners() {
  // Generate button
  btnGenerate.addEventListener('click', handleGenerate);

  // Status banner close
  statusClose.addEventListener('click', () => {
    statusBanner.hidden = true;
  });

  // PAT modal
  patSubmit.addEventListener('click', handlePATSubmit);
  patCancel.addEventListener('click', () => { patModal.classList.remove('show'); });
  patClear.addEventListener('click', () => {
    localStorage.removeItem(PAT_KEY);
    patClear.hidden = true;
    patInput.value = '';
    showStatus('Token cleared.', 'warning');
    patModal.classList.remove('show');
  });

  // Close modal on overlay click
  patModal.addEventListener('click', (e) => {
    if (e.target === patModal) patModal.classList.remove('show');
  });

  // Escape key closes modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && patModal.classList.contains('show')) patModal.classList.remove('show');
  });
}

// ── Generate Handler ──────────────────────────
function handleGenerate() {
  const savedToken = localStorage.getItem(PAT_KEY);
  if (savedToken) {
    triggerWorkflow(savedToken);
  } else {
    // Show modal
    patInput.value = '';
    patClear.hidden = true;
    patModal.classList.add('show');
    patInput.focus();
  }
}

async function handlePATSubmit() {
  const token = patInput.value.trim();
  if (!token) {
    patInput.style.borderColor = 'var(--error)';
    return;
  }
  localStorage.setItem(PAT_KEY, token);
  patModal.classList.remove('show');
  await triggerWorkflow(token);
}

// ── Trigger GitHub Actions ────────────────────
async function triggerWorkflow(token) {
  btnGenerate.disabled = true;
  btnGenerate.innerHTML = `
    <svg class="spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
    Triggering…
  `;

  try {
    const res = await fetch(
      `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
        },
        body: JSON.stringify({ ref: 'main' }),
      }
    );

    if (res.status === 204) {
      showStatus('✅ Report generation triggered! The page will update once the workflow completes and redeploys (~3-5 min).', 'success');
    } else if (res.status === 401 || res.status === 403) {
      localStorage.removeItem(PAT_KEY);
      showStatus('❌ Invalid or expired token. Please enter a new one.', 'error');
    } else {
      const data = await res.json().catch(() => ({}));
      showStatus(`❌ GitHub API error (${res.status}): ${data.message || 'Unknown error'}`, 'error');
    }
  } catch (err) {
    showStatus(`❌ Network error: ${err.message}`, 'error');
  } finally {
    btnGenerate.disabled = false;
    btnGenerate.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
      Generate New Report
    `;
  }
}

// ── Show Status Banner ────────────────────────
function showStatus(message, type = 'success') {
  statusBanner.hidden = false;
  statusBanner.className = 'status-banner' + (type !== 'success' ? ` ${type}` : '');
  statusText.textContent = message;
  // Auto-scroll up so user can see it
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Utilities ─────────────────────────────────
function formatDate(dateStr) {
  try {
    // dateStr is like "2026-03-03" or "2026-03-03_08-51-26"
    const parts = dateStr.split('_');
    const datePart = parts[0];
    const timePart = parts[1] ? parts[1].replace(/-/g, ':') : null;
    const d = new Date(datePart + (timePart ? `T${timePart}` : ''));
    if (isNaN(d)) return dateStr;
    return d.toLocaleDateString('en-US', {
      weekday: 'short', year: 'numeric', month: 'short', day: 'numeric',
      ...(timePart ? { hour: '2-digit', minute: '2-digit' } : {}),
    });
  } catch {
    return dateStr;
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Spin animation (injected via CSS) ─────────
const style = document.createElement('style');
style.textContent = `
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .spin { animation: spin 1s linear infinite; }
`;
document.head.appendChild(style);

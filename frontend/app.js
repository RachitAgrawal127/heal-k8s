/* ═══════════════════════════════════════════════════════
   Heal-K8s Dashboard — app.js (v2 — hardened)
   Vanilla JS • Chart.js • MOCK_MODE auto-cycling
   ═══════════════════════════════════════════════════════ */

// ═══════════ MODULE 1: CONFIGURATION & MOCK SYSTEM ═══════════

const CONFIG = {
  API_BASE: 'http://localhost:8000',
  POLL_INTERVAL_MS: 2000,
  HISTORY_POLL_MS: 10000,
  MOCK_MODE: false,   // true = offline dev mode, false = hit real backend
  FETCH_TIMEOUT_MS: 5000,  // [FIX-1] abort fetch after 5s to prevent stale connections
};

// ── Mock State Machine ──
// Cycles: Healthy → Warning → Critical → Healthy ...
const MOCK_STATES = [
  // State 0: Healthy
  {
    pod_status: 'Healthy',
    memory_readings: [120, 118, 122, 119, 121, 120, 118, 122],
    prediction_seconds: null,
    badge_type: null,
    diagnosis: null,
    confidence: null,
    kubectl_command: null,
    memory_hit: false,
  },
  // State 1: Warning (prediction firing)
  {
    pod_status: 'Warning',
    memory_readings: [120, 145, 178, 210, 255, 301, 355, 410],
    prediction_seconds: 42,
    badge_type: 'prediction',
    diagnosis: 'Sustained memory growth detected — 4.1 MB/s over 70s. OOMKill predicted in 42 seconds.',
    confidence: 0.87,
    kubectl_command: 'kubectl delete pod leaky-app-7x9k2 -n default',
    memory_hit: false,
  },
  // State 2: Critical (signature match)
  {
    pod_status: 'Critical',
    memory_readings: [120, 145, 178, 210, 255, 301, 355, 490],
    prediction_seconds: 8,
    badge_type: 'signature',
    diagnosis: 'Container killed due to exceeding memory limit (OOMKilled).',
    confidence: 0.99,
    kubectl_command: 'kubectl delete pod leaky-app-7x9k2 -n default',
    memory_hit: true,
  },
];

const MOCK_INCIDENTS = [
  {
    id: 1,
    failure_type: 'OOMKilled',
    fix: 'kubectl delete pod leaky-app-7x9k2 -n default',
    confidence: 0.99,
    success_count: 3,
    failure_count: 0,
    last_seen: '2025-03-09T03:42:11',
    created_at: '2025-03-07T10:00:00',
  },
  {
    id: 2,
    failure_type: 'CrashLoopBackOff',
    fix: 'kubectl delete pod api-server-3b2m1 -n production',
    confidence: 0.95,
    success_count: 1,
    failure_count: 0,
    last_seen: '2025-03-08T14:18:33',
    created_at: '2025-03-08T14:00:00',
  },
];

let mockStateIndex = 0;
const MOCK_CYCLE_MS = 4000;

function getMockState() {
  const state = MOCK_STATES[mockStateIndex];
  return { ...state };
}

// Advance mock state on a timer
setInterval(() => {
  mockStateIndex = (mockStateIndex + 1) % MOCK_STATES.length;
}, MOCK_CYCLE_MS);


// ═══════════ MODULE 2: API CLIENT (hardened) ═══════════

// [FIX-1] AbortController factory — cancels stale requests when a new poll fires
let statusController = null;
let historyController = null;

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort('Request timed out'), CONFIG.FETCH_TIMEOUT_MS);

  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timeoutId);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}

async function fetchSystemStatus() {
  if (CONFIG.MOCK_MODE) {
    return getMockState();
  }

  // [FIX-2] Cancel previous in-flight request to prevent pile-up
  if (statusController) statusController.abort();
  statusController = new AbortController();

  try {
    const res = await fetch(`${CONFIG.API_BASE}/system-status`, {
      signal: statusController.signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err.name === 'AbortError') return null; // silently ignore cancelled requests
    console.error('[API] fetchSystemStatus failed:', err);
    return null;
  }
}

async function executeCommand(cmd) {
  if (CONFIG.MOCK_MODE) {
    // [FIX-3] Simulate realistic network latency in mock mode
    await new Promise(r => setTimeout(r, 600));
    return {
      status: 'executed',
      command: cmd,
      result: { status: 'success', message: 'Pod restarted (mock)' },
      k8s_available: true,
    };
  }
  try {
    return await fetchWithTimeout(`${CONFIG.API_BASE}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kubectl_command: cmd }),
    });
  } catch (err) {
    console.error('[API] executeCommand failed:', err);
    const message = err.name === 'AbortError'
      ? 'Execution timed out waiting for backend response.'
      : err.message;
    return { status: 'error', result: { status: 'error', message } };
  }
}

async function fetchIncidentHistory() {
  if (CONFIG.MOCK_MODE) {
    return { incidents: MOCK_INCIDENTS };
  }

  // [FIX-2] Cancel previous in-flight history request
  if (historyController) historyController.abort();
  historyController = new AbortController();

  try {
    const res = await fetch(`${CONFIG.API_BASE}/incident-history`, {
      signal: historyController.signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err.name === 'AbortError') return null;
    console.error('[API] fetchIncidentHistory failed:', err);
    return { incidents: [] };
  }
}


// ═══════════ MODULE 3: UI UPDATERS (hardened) ═══════════

// Cache DOM references
const DOM = {
  statusBadge:    document.getElementById('status-badge'),
  badgeType:      document.getElementById('badge-type'),
  memoryHit:      document.getElementById('memory-hit'),
  countdownValue: document.getElementById('countdown-value'),
  diagnosisText:  document.getElementById('diagnosis-text'),
  confidenceArc:  document.getElementById('confidence-arc'),
  confidenceValue:document.getElementById('confidence-value'),
  kubectlCmd:     document.getElementById('kubectl-cmd'),
  approveBtn:     document.getElementById('approve-btn'),
  executeFeedback:document.getElementById('execute-feedback'),
  incidentTable:  document.getElementById('incident-table'),
  incidentCount:  document.getElementById('incident-count'),
  chartReading:   document.getElementById('chart-reading'),
  mockIndicator:  document.getElementById('mock-indicator'),
  k8sStatus:      document.getElementById('k8s-status'),
};

// Total circumference of the SVG confidence ring (2πr, r=52)
const RING_CIRCUMFERENCE = 2 * Math.PI * 52;  // ≈ 326.73

// [FIX-4] Diff-check: skip DOM writes when value hasn't changed
let prevState = null;
let countdownDeadlineMs = null;
let countdownIntervalId = null;

function renderCountdownValue(secs) {
  DOM.countdownValue.textContent = secs;

  if (secs <= 15) {
    DOM.countdownValue.className = 'countdown-value critical';
  } else if (secs <= 60) {
    DOM.countdownValue.className = 'countdown-value warning';
  } else {
    DOM.countdownValue.className = 'countdown-value';
  }
}

function clearCountdown() {
  countdownDeadlineMs = null;
  DOM.countdownValue.textContent = '—';
  DOM.countdownValue.className = 'countdown-value';
}

function tickCountdown() {
  if (countdownDeadlineMs == null) {
    return;
  }

  const remainingSecs = Math.max(0, Math.ceil((countdownDeadlineMs - Date.now()) / 1000));
  renderCountdownValue(remainingSecs);
}

function ensureCountdownTicker() {
  if (countdownIntervalId !== null) {
    return;
  }

  countdownIntervalId = setInterval(tickCountdown, 250);
}

function stateChanged(newState) {
  if (!prevState) return true;
  // Quick structural comparison for the fields that drive UI
  return prevState.pod_status !== newState.pod_status
      || prevState.prediction_seconds !== newState.prediction_seconds
      || prevState.confidence !== newState.confidence
      || prevState.diagnosis !== newState.diagnosis
      || prevState.badge_type !== newState.badge_type
      || prevState.memory_hit !== newState.memory_hit
      || prevState.kubectl_command !== newState.kubectl_command
      || prevState.memory_readings?.length !== newState.memory_readings?.length
      || prevState.memory_readings?.[prevState.memory_readings.length - 1]
         !== newState.memory_readings?.[newState.memory_readings.length - 1];
}

function updateStatusBadge(state) {
  if (!state) return;
  const status = (state.pod_status || 'Healthy').toLowerCase();
  DOM.statusBadge.textContent = state.pod_status || 'Healthy';
  DOM.statusBadge.className = 'status-badge ' + status;
}

function updateBadgeType(state) {
  if (!state) return;
  if (state.badge_type) {
    const labels = {
      signature: '🔍 Signature',
      prediction: '📈 Prediction',
      memory_hit: '🧠 Memory',
      llm_fallback: '🤖 LLM',
    };
    DOM.badgeType.textContent = labels[state.badge_type] || state.badge_type;
  } else {
    DOM.badgeType.textContent = '—';
  }

  // Memory hit indicator
  if (state.memory_hit) {
    DOM.memoryHit.textContent = 'Yes';
    DOM.memoryHit.className = 'memory-hit-badge active';
  } else {
    DOM.memoryHit.textContent = 'No';
    DOM.memoryHit.className = 'memory-hit-badge';
  }
}

function updateCountdown(state) {
  if (!state || state.prediction_seconds == null) {
    clearCountdown();
    return;
  }

  const shouldResetCountdown = !prevState
    || prevState.badge_type !== state.badge_type
    || prevState.prediction_seconds !== state.prediction_seconds;

  if (shouldResetCountdown) {
    countdownDeadlineMs = Date.now() + (state.prediction_seconds * 1000);
  }

  tickCountdown();
}

function updateDiagnosis(state) {
  if (!state) return;
  if (state.diagnosis) {
    DOM.diagnosisText.textContent = state.diagnosis;
    DOM.diagnosisText.className = 'diagnosis-text active';
  } else {
    DOM.diagnosisText.textContent = 'No active incidents.';
    DOM.diagnosisText.className = 'diagnosis-text';
  }
}

function updateConfidence(state) {
  if (!state || state.confidence == null) {
    DOM.confidenceValue.textContent = '—';
    DOM.confidenceArc.style.strokeDashoffset = RING_CIRCUMFERENCE;
    DOM.confidenceArc.className.baseVal = 'confidence-ring-fill';
    return;
  }

  const pct = Math.round(state.confidence * 100);
  DOM.confidenceValue.textContent = pct + '%';

  // Animate SVG ring
  const offset = RING_CIRCUMFERENCE * (1 - state.confidence);
  DOM.confidenceArc.style.strokeDashoffset = offset;

  // Color by confidence level
  if (state.confidence >= 0.95) {
    DOM.confidenceArc.className.baseVal = 'confidence-ring-fill';
  } else if (state.confidence >= 0.80) {
    DOM.confidenceArc.className.baseVal = 'confidence-ring-fill warning';
  } else {
    DOM.confidenceArc.className.baseVal = 'confidence-ring-fill critical';
  }
}

function updateApproveButton(state) {
  if (!state) return;
  if (state.kubectl_command) {
    DOM.kubectlCmd.textContent = state.kubectl_command;
    DOM.kubectlCmd.className = 'kubectl-cmd';
    // [FIX-5] Only re-enable if not mid-execution
    if (!isExecuting) {
      DOM.approveBtn.disabled = false;
    }
  } else {
    DOM.kubectlCmd.textContent = 'No command pending';
    DOM.kubectlCmd.className = 'kubectl-cmd empty';
    DOM.approveBtn.disabled = true;
  }
}

function updateMemoryChart(state) {
  if (!state || !state.memory_readings || !memoryChart) return;

  const readings = state.memory_readings;
  memoryChart.data.labels = readings.map((_, i) => `R${i + 1}`);
  memoryChart.data.datasets[0].data = readings;

  // Change chart color based on status
  const status = (state.pod_status || 'Healthy').toLowerCase();
  const colors = {
    healthy:  { border: '#00d68f', bg: 'rgba(0, 214, 143, 0.08)' },
    warning:  { border: '#ffaa00', bg: 'rgba(255, 170, 0, 0.08)' },
    critical: { border: '#ff3d71', bg: 'rgba(255, 61, 113, 0.08)' },
  };
  const c = colors[status] || colors.healthy;
  memoryChart.data.datasets[0].borderColor = c.border;
  memoryChart.data.datasets[0].backgroundColor = c.bg;
  memoryChart.data.datasets[0].pointBackgroundColor = c.border;

  memoryChart.update('none');  // 'none' = skip animation for fast updates

  // Update reading display
  const latest = readings[readings.length - 1];
  DOM.chartReading.textContent = latest != null ? `${latest} MB` : '— MB';
  DOM.chartReading.style.color = c.border;
}

// [FIX-6] XSS prevention: escape untrusted backend data before inserting into DOM
function escapeHtml(str) {
  if (!str) return '—';
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

function updateIncidentTable(incidents) {
  if (!incidents || incidents.length === 0) {
    DOM.incidentTable.innerHTML = '<tr class="empty-row"><td colspan="7">No incidents recorded.</td></tr>';
    DOM.incidentCount.textContent = '0 incidents';
    return;
  }

  DOM.incidentCount.textContent = `${incidents.length} incident${incidents.length !== 1 ? 's' : ''}`;

  // [FIX-6] Use escapeHtml on all backend-sourced strings to prevent XSS
  // Fields match real backend schema: fix, success_count, failure_count (not fix_applied/success/count/signature_matched)
  DOM.incidentTable.innerHTML = incidents.map(inc => {
    const total = (inc.success_count || 0) + (inc.failure_count || 0);
    const majority = (inc.success_count || 0) >= (inc.failure_count || 0);
    return `
    <tr>
      <td class="mono">${escapeHtml(String(inc.id))}</td>
      <td>${escapeHtml(inc.failure_type)}</td>
      <td class="mono">${escapeHtml(truncateCmd(inc.fix))}</td>
      <td><span class="${majority ? 'success-yes' : 'success-no'}">${inc.success_count || 0}/${total}</span></td>
      <td class="mono">${inc.confidence != null ? Math.round(inc.confidence * 100) + '%' : '—'}</td>
      <td class="mono">${escapeHtml(String(total))}</td>
      <td class="mono">${formatTime(inc.last_seen)}</td>
    </tr>
  `;
  }).join('');
}

// ── Helpers ──

function truncateCmd(cmd) {
  if (!cmd) return '—';
  return cmd.length > 50 ? cmd.substring(0, 47) + '...' : cmd;
}

function formatTime(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return escapeHtml(isoStr); // [FIX-7] Guard invalid dates
    return d.toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return escapeHtml(isoStr);
  }
}


// ═══════════ MODULE 4: CHART.JS SETUP ═══════════

const memoryChart = new Chart(document.getElementById('memory-chart'), {
  type: 'line',
  data: {
    labels: [],
    datasets: [{
      label: 'Memory (MB)',
      data: [],
      borderColor: '#00d68f',
      borderWidth: 2,
      tension: 0.35,
      fill: true,
      backgroundColor: 'rgba(0, 214, 143, 0.08)',
      pointRadius: 3,
      pointBackgroundColor: '#00d68f',
      pointBorderWidth: 0,
    }],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    // [FIX-8] Disable resize observer debounce for smoother responsiveness
    resizeDelay: 0,
    scales: {
      x: {
        display: true,
        grid: { color: 'rgba(30, 42, 58, 0.5)' },
        ticks: { color: '#556677', font: { size: 10, family: "'JetBrains Mono'" } },
      },
      y: {
        beginAtZero: true,
        grid: { color: 'rgba(30, 42, 58, 0.5)' },
        ticks: {
          color: '#556677',
          font: { size: 10, family: "'JetBrains Mono'" },
          callback: (val) => val + ' MB',
        },
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1a2332',
        borderColor: '#2a3a4a',
        borderWidth: 1,
        titleColor: '#e4e9f0',
        bodyColor: '#8899aa',
        bodyFont: { family: "'JetBrains Mono'" },
        callbacks: {
          label: (ctx) => ` ${ctx.parsed.y} MB`,
        },
      },
    },
    animation: { duration: 0 }, // [FIX-9] Zero animation for 2s polling — prevents frame stacking
  },
});


// ═══════════ MODULE 5: MAIN LOOP & EVENT HANDLERS (hardened) ═══════════

// [FIX-5] Execution state flag to prevent poll from re-enabling button mid-execution
let isExecuting = false;
let executeFeedbackTimeoutId = null;

// [FIX-10] Polling guard: prevent overlapping async poll cycles
let isPollingStatus = false;
let isPollingHistory = false;

// ── Initialize UI state ──
function initUI() {
  ensureCountdownTicker();

  // Show/hide mock indicator
  if (CONFIG.MOCK_MODE) {
    DOM.mockIndicator.classList.remove('hidden');
    DOM.k8sStatus.textContent = 'Mock';
  } else {
    DOM.mockIndicator.classList.add('hidden');
    DOM.k8sStatus.textContent = 'Connecting...';
  }
}

// ── Update all panels from a single state object ──
function updateDashboard(state) {
  if (!state) return;

  // [FIX-4] Skip DOM writes if nothing changed (saves layout/paint cycles)
  if (!stateChanged(state)) return;

  // [FIX-11] Batch DOM writes inside rAF to prevent layout thrashing
  requestAnimationFrame(() => {
    updateStatusBadge(state);
    updateBadgeType(state);
    updateMemoryChart(state);
    updateCountdown(state);
    updateDiagnosis(state);
    updateConfidence(state);
    updateApproveButton(state);
    prevState = { ...state, memory_readings: [...(state.memory_readings || [])] };
  });
}

// ── Polling: System Status (with overlap guard) ──
async function pollSystemStatus() {
  if (isPollingStatus) return; // [FIX-10] Skip if previous poll is still in-flight
  isPollingStatus = true;
  try {
    const state = await fetchSystemStatus();
    updateDashboard(state);
  } finally {
    isPollingStatus = false;
  }
}

// ── Polling: Incident History (with overlap guard) ──
async function pollIncidentHistory() {
  if (isPollingHistory) return; // [FIX-10]
  isPollingHistory = true;
  try {
    const data = await fetchIncidentHistory();
    if (data && data.incidents) {
      updateIncidentTable(data.incidents);
    }
  } finally {
    isPollingHistory = false;
  }
}

// ── Approve button click (hardened) ──
DOM.approveBtn.addEventListener('click', async () => {
  const cmd = DOM.kubectlCmd.textContent;
  if (!cmd || cmd === 'No command pending') return;

  if (executeFeedbackTimeoutId !== null) {
    clearTimeout(executeFeedbackTimeoutId);
    executeFeedbackTimeoutId = null;
  }

  // [FIX-5] Set execution flag so poll doesn't re-enable the button
  isExecuting = true;
  DOM.approveBtn.disabled = true;
  DOM.approveBtn.textContent = '⏳ Executing...';
  DOM.executeFeedback.textContent = '';
  DOM.executeFeedback.className = 'execute-feedback';

  try {
    const result = await executeCommand(cmd);
    if (result && result.result && ['success', 'mock_success'].includes(result.result.status)) {
      DOM.executeFeedback.textContent = `✓ ${result.result.message}`;
      DOM.executeFeedback.className = 'execute-feedback';
    } else {
      DOM.executeFeedback.textContent = `✗ ${result?.result?.message || 'Execution failed'}`;
      DOM.executeFeedback.className = 'execute-feedback error';
    }

    // Update K8s availability
    if (result && result.k8s_available != null) {
      DOM.k8sStatus.textContent = result.k8s_available ? 'Connected' : 'Offline';
    }
  } catch (err) {
    DOM.executeFeedback.textContent = `✗ Error: ${err.message}`;
    DOM.executeFeedback.className = 'execute-feedback error';
  }

  executeFeedbackTimeoutId = setTimeout(() => {
    DOM.executeFeedback.textContent = '';
    DOM.executeFeedback.className = 'execute-feedback';
    executeFeedbackTimeoutId = null;
  }, 1500);

  // Re-enable button after a brief delay
  setTimeout(() => {
    isExecuting = false;
    DOM.approveBtn.innerHTML = '<span class="btn-icon">⚡</span> Approve & Execute';
    // Only re-enable if there's still a command pending
    if (DOM.kubectlCmd.textContent && DOM.kubectlCmd.textContent !== 'No command pending') {
      DOM.approveBtn.disabled = false;
    }
  }, 2000);
});

// ── Start everything ──
initUI();
pollSystemStatus();
pollIncidentHistory();

setInterval(pollSystemStatus, CONFIG.POLL_INTERVAL_MS);
setInterval(pollIncidentHistory, CONFIG.HISTORY_POLL_MS);

console.log(`[Heal-K8s] Dashboard initialized (v2 hardened) — MOCK_MODE: ${CONFIG.MOCK_MODE}`);

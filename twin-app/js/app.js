/* ==========================================================================
   TWIN — application logic
   Everything here runs client-side against the API.
   ========================================================================== */

const state = {
  agentStatus: {},          // id -> 'idle' | 'running' | 'done'
  simHistory: [],
  chatSeeded: false
};

let currentProfile = null;
let pendingScenarioPrefill = null;

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

AGENTS.forEach(a => state.agentStatus[a.id] = 'idle');

function profile() { return currentProfile; }
function fmt(n) { return Math.round(n).toLocaleString('en-IN'); }
function metricByIdVal(id) {
  if (!profile()) return 0;
  const m = profile().metrics.find(m => m.id === id);
  return m ? m.value : 0;
}

/* ============ Routing ============ */
const views = document.querySelectorAll('.view');
const navItems = document.querySelectorAll('.navitem');
const titles = {
  overview: ['Overview', 'Live snapshot of the digital twin'],
  simulate: ['Simulate a decision', 'Run scenarios on the twin before anything is recommended'],
  ask: ['Ask Twin', 'Grounded answers from your financial data'],
  agents: ['Agent team', 'Six specialists, orchestrated on every request'],
  about: ['About this build', 'What the demo shows and how it maps to the architecture']
};

navItems.forEach(btn => {
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

function isStartup() {
  return !!(profile() && profile().key === 'startup');
}

function switchView(name) {
  views.forEach(v => v.classList.remove('is-active'));
  document.getElementById('view-' + name).classList.add('is-active');
  navItems.forEach(b => b.classList.toggle('is-active', b.dataset.view === name));
  const titleSet = (isStartup() && typeof STARTUP_TITLES !== 'undefined' && STARTUP_TITLES[name]) ? STARTUP_TITLES[name] : titles[name];
  if (titleSet) {
    document.getElementById('topbarTitle').textContent = titleSet[0];
    document.getElementById('topbarSub').textContent = titleSet[1];
  }
  if (name === 'ask') {
    resetChat();
    loadChatSessions();
  }
  if (name === 'simulate' && pendingScenarioPrefill) {
    scenarioInput.value = pendingScenarioPrefill;
    pendingScenarioPrefill = null;
    scenarioInput.focus();
  }
  if (name === 'overview' && isStartup()) {
    loadStartupOverviewAndRender();
  }
  if (name === 'hisaab' && isStartup()) {
    loadHisaabAndRender();
  }
  if (name === 'alerts' && isStartup()) {
    renderAlertsView();
  }
  if (name === 'reports' && isStartup()) {
    renderReportsView();
  }
}

// Profile switching logic removed, account type is strictly enforced by the backend

async function loadProfileAndRender() {
  try {
    currentProfile = await window.api.fetchProfile();
    if (currentProfile) {
      // /profile/me resolves the real profile.key for the logged-in user
      // (e.g. "custom_<username>" or "startup") — always trust it over
      // whatever state.profileKey happened to default to, so a page
      // refresh/relogin doesn't leave chat/simulate calls sending a
      // stale "individual" key that matches no row in the DB.
      state.profileKey = currentProfile.key;
      applyPersonaNav(currentProfile.key === 'startup' ? 'startup' : 'individual');
      if (currentProfile.key === 'startup') {
        await loadStartupOverviewAndRender();
      } else {
        renderOverview();
      }
      renderSimulateForm();
      resetSimResults();
      renderSimHistory();
      resetChat();
    }
  } catch (e) {
    // Not logged in or no profile
    localStorage.removeItem('twin_session');
    window.location.href = '/login.html';
  }
}

/* ============ Sparkline (inline SVG, no chart library) ============ */
function sparkline(data, w = 220, h = 48, color = '#0E5C4A') {
  if (!data || data.length === 0) return '';
  const min = Math.min(...data), max = Math.max(...data);
  const range = (max - min) || 1;
  const step = w / (data.length - 1);
  const pts = data.map((v, i) => `${(i * step).toFixed(1)},${(h - ((v - min) / range) * (h - 8) - 4).toFixed(1)}`).join(' ');
  const lastX = ((data.length - 1) * step).toFixed(1);
  const lastY = (h - ((data[data.length - 1] - min) / range) * (h - 8) - 4).toFixed(1);
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${lastX}" cy="${lastY}" r="2.6" fill="${color}"/>
  </svg>`;
}

/* ============ Overview ============ */
function renderOverview() {
  const p = profile();
  if (!p) return;
  document.getElementById('personaLabel').textContent = p.persona;
  document.getElementById('goalStrip').textContent = `${p.goal.title} — ${p.goal.progress}% there`;

  const currency = p.currency || '₹';
  const grid = document.getElementById('statGrid');
  grid.innerHTML = p.metrics.map(m => {
    const trendUp = m.trend && m.trend.length > 0 ? m.trend[m.trend.length - 1] >= m.trend[0] : true;
    const displayVal = m.isPercent ? `${m.value}%` : `${currency}${fmt(m.value)}${m.unit || ''}`;
    return `
      <div class="stat-card">
        <span class="stat-card__label">${m.label}</span>
        <span class="stat-card__value">${displayVal}</span>
        <div class="stat-card__chart">${sparkline(m.trend, 220, 42, trendUp ? '#0E5C4A' : '#B5502F')}</div>
      </div>`;
  }).join('');

  document.getElementById('historyList').innerHTML = p.history.map(h => `
    <li>
      <div>
        <p class="decision-list__title">${h.title}</p>
        <p class="decision-list__date">${h.date || h.date_str}</p>
      </div>
      <span class="tag tag--${h.tag}">${h.outcome}</span>
    </li>`).join('');

  document.getElementById('alertList').innerHTML = p.alerts.map(a => `
    <li class="alert alert--${a.level}">
      <span class="alert__dot"></span>
      <p>${a.text}</p>
    </li>`).join('');
}

/* ============ Simulate ============ */
const scenarioInput = document.getElementById('scenarioInput');
const simSuggestionsEl = document.getElementById('simSuggestions');

const SCENARIO_SUGGESTIONS = [
  'What happens if I invest ₹20,000 every month for 3 years?',
  'Can I afford a ₹50,000 EMI?',
  'What if I increase my monthly savings by ₹10,000?',
  'How quickly can I reach my savings goal?',
  'What happens if I have no income for 6 months?'
];

const STAGE_ID_MAP = { Understand: 'understand', Watch: 'watch', Simulate: 'simulate', Recommend: 'recommend', Teach: 'teach', Check: 'check' };

const IMPACT_LABELS = {
  monthly_surplus_before: 'Monthly surplus — before',
  monthly_surplus_after: 'Monthly surplus — after',
  savings_impact: 'Savings impact',
  emergency_buffer_before_months: 'Emergency buffer — before',
  emergency_buffer_after_months: 'Emergency buffer — after',
  goal_progress_before_pct: 'Goal progress — before',
  goal_progress_after_pct: 'Goal progress — after',
  investment_contribution: 'Monthly investment contribution',
  foir_pct: 'Fixed-obligation ratio (FOIR)',
  affordability_verdict: 'Affordability verdict',
  goal_months_remaining_before: 'Months to goal — before',
  goal_months_remaining_after: 'Months to goal — after',
  coverage_months: 'Emergency coverage',
  requested_months: 'Months without income',
  goal_title: 'Goal',
  goal_target: 'Goal target',
  monthly_contribution_rate: 'Monthly contribution rate',
  months_to_goal: 'Months to reach goal',
  projected_savings: 'Projected savings',
  projected_value: 'Projected value',
  invested_total: 'Total invested',
  estimated_gain: 'Estimated gain',
  savings_before: 'Savings — no change',
  savings_after: 'Savings — with change',
  extra_saved: 'Extra saved',
  remaining_savings: 'Remaining savings',
  shortfall: 'Shortfall',
  amount_saved: 'Amount saved',
  emergency_buffer_months: 'Emergency buffer',
  goal_progress_pct: 'Goal progress',
  note: 'Note'
};

function humanizeKey(k) {
  return IMPACT_LABELS[k] || k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatImpactValue(k, v, currency) {
  if (typeof v === 'string') return v;
  if (typeof v !== 'number') return String(v);
  if (k.includes('pct') || k === 'foir_pct') return `${v}%`;
  if (k.includes('months') || k.startsWith('runway')) return `${v} mo`;
  if (k.startsWith('financial_health')) return `${v}/100`;
  if (k === 'headcount_added' || k === 'headcount') return `${v}`;
  return `${currency}${fmt(v)}`;
}

function renderSimulateForm() {
  const suggestions = (isStartup() && typeof STARTUP_SCENARIO_SUGGESTIONS !== 'undefined') ? STARTUP_SCENARIO_SUGGESTIONS : SCENARIO_SUGGESTIONS;
  simSuggestionsEl.innerHTML = suggestions.map(s => `<button type="button" class="chip">${s}</button>`).join('');
  simSuggestionsEl.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => { scenarioInput.value = chip.textContent; scenarioInput.focus(); });
  });
}

function resetSimResults() {
  document.getElementById('simResults').innerHTML = `
    <div class="empty-state">
      <p>Describe a scenario in plain language and run the simulation to see a grounded, personalized breakdown here.</p>
    </div>`;
  document.getElementById('pipeline').innerHTML = '';
}

function timelineDetail(entry, currency) {
  return Object.entries(entry)
    .filter(([k]) => k !== 'label' && k !== 'months')
    .map(([k, v]) => `<div class="timeline-step__row"><span>${humanizeKey(k)}:</span><b>${formatImpactValue(k, v, currency)}</b></div>`)
    .join('');
}

function renderSimulationResult(res) {
  const p = profile();
  const currency = (p && p.currency) || '₹';
  const impact = res.financial_impact || {};
  const isInformational = res.mode === 'informational';

  const impactRows = Object.entries(impact)
    .filter(([, v]) => v !== null && v !== undefined && typeof v !== 'object')
    .map(([k, v]) => `<div class="impact-tile"><span class="impact-tile__label">${humanizeKey(k)}</span><span class="impact-tile__value">${formatImpactValue(k, v, currency)}</span></div>`)
    .join('');

  const traceHtml = (res.stages || []).map(s => `<li><b>${escapeHtml(s.agent)}:</b> ${escapeHtml(s.summary)}</li>`).join('');

  const sections = [];

  sections.push(`
    <div class="panel__head"><h3>Scenario</h3></div>
    <p class="sim-scenario-text">“${escapeHtml(res.scenario)}”</p>`);

  sections.push(`
    <div class="sim-section">
      <h4 class="sim-section__title">${isInformational ? 'Your current snapshot' : 'Financial impact'}</h4>
      <div class="impact-grid">${impactRows || '<p class="sim-empty">No quantitative impact could be computed from this scenario.</p>'}</div>
    </div>`);

  if (!isInformational && impact.goal_impact && impact.goal_impact.length) {
    const goalRows = impact.goal_impact.map(g => {
      const before = (g.progress_before_pct !== null && g.progress_before_pct !== undefined) ? `${g.progress_before_pct.toFixed(0)}%` : '—';
      const after = (g.progress_after_pct !== null && g.progress_after_pct !== undefined) ? `${g.progress_after_pct.toFixed(0)}%` : '—';
      return `<div class="impact-tile"><span class="impact-tile__label">${escapeHtml(g.label)}</span><span class="impact-tile__value">${before} → ${after}</span></div>`;
    }).join('');
    sections.push(`
      <div class="sim-section">
        <h4 class="sim-section__title">Goal impact</h4>
        <div class="impact-grid">${goalRows}</div>
      </div>`);
  }

  if (!isInformational) {
    const timelineHtml = (res.timeline || []).map(t => `
      <div class="timeline-step">
        <div class="timeline-step__dot"></div>
        <div class="timeline-step__label">${escapeHtml(t.label)}</div>
        <div class="timeline-step__body">${timelineDetail(t, currency)}</div>
      </div>`).join('');

    sections.push(`
      <div class="sim-section">
        <h4 class="sim-section__title">Timeline</h4>
        <div class="sim-timeline">${timelineHtml || '<p class="sim-empty">No timeline applies to this scenario.</p>'}</div>
      </div>`);
  }

  if (isInformational) {
    // Reuses Ask Twin's own markdown-formatted, grounded answer verbatim.
    const answerHtml = (typeof marked !== 'undefined') ? marked.parse(res.recommendation || '') : `<p>${escapeHtml(res.recommendation)}</p>`;
    sections.push(`
      <div class="explanation">
        <span class="explanation__label">Twin's answer</span>
        ${answerHtml}
      </div>`);
  } else {
    sections.push(`
      <div class="explanation">
        <span class="explanation__label">Recommend agent</span>
        <p><b>${escapeHtml(res.recommendation)}</b></p>
        <p>${escapeHtml(res.why)}</p>
      </div>`);

    if (res.risks && res.risks.length) {
      const risksHtml = res.risks.map(r => `
        <li class="alert alert--warn"><span class="alert__dot"></span><p>${escapeHtml(r)}</p></li>`).join('');
      sections.push(`
        <div class="sim-section">
          <h4 class="sim-section__title">Risks / what to watch</h4>
          <ul class="alert-list">${risksHtml}</ul>
        </div>`);
    }

    if (res.assumptions && res.assumptions.length) {
      const assumptionsHtml = res.assumptions.map(a => `
        <li class="alert alert--info"><span class="alert__dot"></span><p>${escapeHtml(a)}</p></li>`).join('');
      sections.push(`
        <div class="sim-section">
          <h4 class="sim-section__title">Assumptions</h4>
          <ul class="alert-list">${assumptionsHtml}</ul>
        </div>`);
    }

    if (res.teaching) {
      sections.push(`
        <div class="explanation">
          <span class="explanation__label">Teach agent explains</span>
          <p>${escapeHtml(res.teaching)}</p>
        </div>`);
    }
  }

  sections.push(`
    <details class="sim-trace">
      <summary>How this was computed</summary>
      <ul>${traceHtml}</ul>
    </details>
    <p class="chat-note" style="padding:0; margin-top:14px;">${escapeHtml(res.disclaimer)}</p>`);

  document.getElementById('simResults').innerHTML = sections.join('');
}

async function runSimulation() {
  const p = profile();
  if (!p) return;
  const scenario = scenarioInput.value.trim();
  if (!scenario) { scenarioInput.focus(); return; }

  const pipelineEl = document.getElementById('pipeline');
  pipelineEl.innerHTML = AGENTS.map(a => `
    <div class="pipe-step" data-agent="${a.id}">
      <span class="pipe-step__dot"></span>
      <span class="pipe-step__name">${a.name}</span>
      <span class="pipe-step__state">Queued</span>
    </div>`).join('');

  document.getElementById('runSimBtn').disabled = true;
  document.getElementById('simResults').innerHTML = '';

  // API call — Understand/Watch/Simulate/Recommend/Teach/Check all run
  // server-side, grounded in the same financial context Ask Twin uses.
  let res;
  try {
    res = await window.api.simulateScenario(scenario, state.profileKey);
  } catch (e) {
    console.error(e);
    document.getElementById('simResults').innerHTML = `
      <div class="empty-state"><p>Couldn't run that simulation — ${escapeHtml(e.message || 'please try again.')}</p></div>`;
    document.getElementById('runSimBtn').disabled = false;
    return;
  }

  // Reveal the real backend stage trace one at a time so the pipeline
  // reflects what actually ran, not a fake spinner.
  for (const stage of (res.stages || [])) {
    const id = STAGE_ID_MAP[stage.agent];
    const row = id && pipelineEl.querySelector(`[data-agent="${id}"]`);
    if (row) {
      row.classList.add('is-running');
      row.querySelector('.pipe-step__state').textContent = 'Running…';
    }
    if (id) { state.agentStatus[id] = 'running'; renderAgents(); }
    await new Promise(r => setTimeout(r, 220 + Math.random() * 140));
    if (row) {
      row.classList.remove('is-running');
      row.classList.add('is-done');
      row.querySelector('.pipe-step__state').textContent = 'Done';
      row.title = stage.summary;
    }
    if (id) { state.agentStatus[id] = 'done'; renderAgents(); }
  }

  // Informational answers only run a subset of stages (no hypothetical to
  // calculate) — mark the rest "Skipped" rather than leaving them stuck on
  // "Queued", which would read as broken.
  pipelineEl.querySelectorAll('.pipe-step:not(.is-done)').forEach(row => {
    row.querySelector('.pipe-step__state').textContent = 'Skipped';
  });

  if (isStartup() && typeof renderStartupSimulationResult === 'function') {
    renderStartupSimulationResult(res);
  } else {
    renderSimulationResult(res);
  }

  state.simHistory.unshift({
    scenario, scenarioType: res.scenario_type,
    time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
  });
  renderSimHistory();

  document.getElementById('runSimBtn').disabled = false;
  setTimeout(() => { AGENTS.forEach(a => state.agentStatus[a.id] = 'idle'); renderAgents(); }, 1400);
}

document.getElementById('runSimBtn').addEventListener('click', runSimulation);

function renderSimHistory() {
  const el = document.getElementById('simHistory');
  if (!state.simHistory.length) {
    el.innerHTML = '<li class="empty-row">No simulations run yet this session.</li>';
    return;
  }
  el.innerHTML = state.simHistory.map(s => `
    <li>
      <div>
        <p class="decision-list__title">${escapeHtml(s.scenario)}</p>
        <p class="decision-list__date">${s.time}</p>
      </div>
      <span class="tag tag--good">${s.scenarioType.replace(/_/g, ' ')}</span>
    </li>`).join('');
}

/* ============ Agent team view ============ */
function renderAgents() {
  const grid = document.getElementById('agentGrid');
  grid.innerHTML = AGENTS.map(a => `
    <div class="agent-card">
      <div class="agent-card__head">
        <span class="agent-card__name">${a.name}</span>
        <span class="status status--${state.agentStatus[a.id]}">${state.agentStatus[a.id]}</span>
      </div>
      <p>${a.desc}</p>
    </div>`).join('');
}

/* ============ Ask Twin (chat) ============ */
const chatLog = document.getElementById('chatLog');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const chatSuggestions = document.getElementById('chatSuggestions');
const chatSessionList = document.getElementById('chatSessionList');
const btnNewChat = document.getElementById('btnNewChat');

let currentSessionId = null;

const SUGGESTIONS = [
  'What\u2019s my emergency buffer?',
  'How are my savings trending?',
  'Am I on track for my goal?'
];

async function loadChatSessions() {
  if (!profile()) return;
  try {
    const sessions = await window.api.getChatSessions(state.profileKey);
    if (chatSessionList) {
      chatSessionList.innerHTML = sessions.map(s => `
          <li style="padding: 8px; border-radius: 4px; cursor: pointer; font-size: 13px; background: ${s.id === currentSessionId ? 'var(--bg-subtle)' : 'transparent'}; position: relative;" 
              onclick="switchSession('${s.id}')">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div style="font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1;" title="${escapeHtml(s.title)}">${escapeHtml(s.title)}</div>
              <div style="position: relative; margin-left: 8px;">
                <button onclick="toggleChatMenu('${s.id}')" style="background:none; border:none; cursor:pointer; font-size:16px; color:var(--ink-faint); padding:0 4px; line-height: 1;">⋮</button>
                <div id="chat-menu-${s.id}" class="chat-menu-dropdown" style="display:none; position: absolute; right: 0; top: 100%; background: var(--surface); border: 1px solid var(--line); border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); z-index: 100; min-width: 100px; overflow: hidden;">
                  <button onclick="event.stopPropagation(); toggleChatMenu('${s.id}'); renameSession('${s.id}', '${escapeHtml(s.title).replace(/'/g, "\\'")}')" class="chat-menu-btn" style="display:block; width:100%; text-align:left; padding: 8px 12px; background:none; border:none; border-bottom: 1px solid var(--line); font-size:12px; cursor:pointer; color:var(--ink);">Rename</button>
                  <button onclick="event.stopPropagation(); toggleChatMenu('${s.id}'); deleteSession('${s.id}')" class="chat-menu-btn" style="display:block; width:100%; text-align:left; padding: 8px 12px; background:none; border:none; font-size:12px; cursor:pointer; color:var(--warn);">Delete</button>
                </div>
              </div>
            </div>
            <div style="font-size: 11px; color: var(--ink-faint); margin-top: 4px;">${new Date(s.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
          </li>
        `).join('');
    }
  } catch (e) {
    console.error(e);
  }
}

window.toggleChatMenu = function (id) {
  event.stopPropagation();
  const menu = document.getElementById('chat-menu-' + id);
  const isVisible = menu.style.display === 'block';

  // hide all other menus
  document.querySelectorAll('.chat-menu-dropdown').forEach(el => el.style.display = 'none');

  if (!isVisible) {
    menu.style.display = 'block';
  }
}

document.addEventListener('click', () => {
  document.querySelectorAll('.chat-menu-dropdown').forEach(el => el.style.display = 'none');
});

window.renameSession = async function (id, currentTitle) {
  const newTitle = prompt("Enter new title for the chat:", currentTitle);
  if (newTitle && newTitle.trim() !== "" && newTitle !== currentTitle) {
    try {
      await window.api.renameChatSession(id, newTitle.trim(), state.profileKey);
      loadChatSessions();
      if (currentSessionId === id) {
        // If needed, update current session's UI beyond the sidebar list
      }
    } catch (e) {
      alert("Failed to rename chat session.");
    }
  }
};

window.deleteSession = async function (id) {
  if (confirm("Are you sure you want to delete this chat session?")) {
    try {
      await window.api.deleteChatSession(id, state.profileKey);
      if (currentSessionId === id) {
        currentSessionId = null;
        resetChat();
      }
      loadChatSessions();
    } catch (e) {
      alert("Failed to delete chat session.");
    }
  }
};

window.switchSession = async function (id) {
  currentSessionId = id;
  chatLog.innerHTML = '';
  chatSuggestions.innerHTML = '';
  loadChatSessions();

  try {
    const session = await window.api.getChatSession(id, state.profileKey);
    session.messages.forEach(m => {
      const who = m.role === 'assistant' || m.role === 'twin' ? 'twin' : 'user';
      addBubble(who, m.content);
    });
  } catch (e) {
    addBubble('twin', 'Failed to load chat history.');
  }
};

if (btnNewChat) {
  btnNewChat.addEventListener('click', () => {
    currentSessionId = null;
    resetChat();
    loadChatSessions();
  });
}

function seedChat() {
  if (!profile()) return;
  if (state.chatSeeded || currentSessionId) return;
  state.chatSeeded = true;
  const greeting = isStartup()
    ? `Hi — I'm Tathya, grounded in your Startup Financial Twin. Ask me about your cash, burn, runway, revenue, funding, or anything else.`
    : `Hi — I’m grounded in your custom financial profile. Ask me about your runway, savings, exposure, or anything else.`;
  addBubble('twin', greeting);
  renderSuggestions();
}

function resetChat() {
  chatLog.innerHTML = '';
  state.chatSeeded = false;
  currentSessionId = null;
  if (document.getElementById('view-ask').classList.contains('is-active')) {
    seedChat();
  }
  renderSuggestions();
}

function renderSuggestions() {
  if (currentSessionId) return; // Don't show suggestions in an active session
  const suggestions = (isStartup() && typeof STARTUP_CHAT_SUGGESTIONS !== 'undefined') ? STARTUP_CHAT_SUGGESTIONS : SUGGESTIONS;
  chatSuggestions.innerHTML = suggestions.map(s => `<button type="button" class="chip">${s}</button>`).join('');
  chatSuggestions.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => { chatInput.value = chip.textContent; chatForm.requestSubmit(); });
  });
}

function addBubble(who, text) {
  const div = document.createElement('div');
  div.className = 'bubble bubble--' + who;

  if (who === 'twin' && typeof marked !== 'undefined') {
    div.innerHTML = marked.parse(text);
  } else {
    div.textContent = text;
  }

  chatLog.appendChild(div);

  if (who === 'user') {
    const action = document.createElement('button');
    action.type = 'button';
    action.className = 'bubble-action';
    action.textContent = 'Simulate this →';
    action.addEventListener('click', () => {
      pendingScenarioPrefill = text;
      switchView('simulate');
    });
    chatLog.appendChild(action);
  }

  chatLog.scrollTop = chatLog.scrollHeight;
}

chatForm.addEventListener('submit', async e => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;

  addBubble('user', text);
  chatInput.value = '';
  chatSuggestions.innerHTML = ''; // Hide suggestions once chatting

  const thinking = document.createElement('div');
  thinking.className = 'bubble bubble--twin bubble--thinking';
  thinking.textContent = 'Thinking…';
  chatLog.appendChild(thinking);
  chatLog.scrollTop = chatLog.scrollHeight;

  try {
    const res = await window.api.askTwin(text, currentSessionId, state.profileKey);
    currentSessionId = res.session_id;
    thinking.remove();
    // "Show the financial insight visually first, then let Tathya explain it" —
    // a numeric/trend question gets a chart (built entirely from the Financial
    // Twin's own metrics) ahead of the text answer; simple questions get none.
    if (res.visualization && typeof suChatVizHtml === 'function') {
      const vizHtml = suChatVizHtml(res.visualization);
      if (vizHtml) {
        const vizDiv = document.createElement('div');
        vizDiv.innerHTML = vizHtml;
        chatLog.appendChild(vizDiv.firstElementChild);
      }
    }
    addBubble('twin', res.answer);
    loadChatSessions();
  } catch (e) {
    thinking.remove();
    addBubble('twin', "I encountered an error connecting to the backend.");
  }
});

/* ============ Onboarding State ============ */
let obUserId = "";
/* ============ Init ============ */
const savedSession = localStorage.getItem('twin_session');
if (savedSession) {
  const session = JSON.parse(savedSession);
  loadProfileAndRender().then(() => {
    renderAgents();
    switchView("overview");
  });
} else {
  window.location.href = '/login.html';
}

/* ============ Logout ============ */
const btnLogout = document.getElementById("btnLogout");
if (btnLogout) {
  btnLogout.addEventListener("click", () => {
    localStorage.removeItem('twin_session');
    window.location.href = '/';
  });
}

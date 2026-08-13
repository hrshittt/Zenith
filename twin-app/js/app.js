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

function switchView(name) {
  views.forEach(v => v.classList.remove('is-active'));
  document.getElementById('view-' + name).classList.add('is-active');
  navItems.forEach(b => b.classList.toggle('is-active', b.dataset.view === name));
  document.getElementById('topbarTitle').textContent = titles[name][0];
  document.getElementById('topbarSub').textContent = titles[name][1];
  if (name === 'ask') {
      resetChat();
      loadChatSessions();
  }
}

/* ============ Profile switching ============ */
document.querySelectorAll('.profileSwitch button').forEach(btn => {
  btn.addEventListener('click', async () => {
    document.querySelectorAll('.profileSwitch button').forEach(b => b.classList.remove('is-active'));
    btn.classList.add('is-active');
    state.profileKey = btn.dataset.profile;
    state.simHistory = [];
    await loadProfileAndRender();
  });
});

async function loadProfileAndRender() {
    try {
        currentProfile = await window.api.fetchProfile();
        if (currentProfile) {
            renderOverview();
            renderSimulateForm();
            resetSimResults();
            renderSimHistory();
            resetChat();
        }
    } catch(e) {
        // Not logged in or no profile
        showObView("view-type");
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

  const grid = document.getElementById('statGrid');
  grid.innerHTML = p.metrics.map(m => {
    const trendUp = m.trend && m.trend.length > 0 ? m.trend[m.trend.length - 1] >= m.trend[0] : true;
    const displayVal = m.isPercent ? `${m.value}%` : `${p.currency}${fmt(m.value)}${m.unit}`;
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
const decisionSelect = document.getElementById('decisionSelect');
const pctSlider = document.getElementById('pctSlider');
const pctLabel = document.getElementById('pctLabel');

function renderSimulateForm() {
  const p = profile();
  if (!p) return;
  decisionSelect.innerHTML = p.decisionTypes.map(d => `<option value="${d.id}">${d.label}</option>`).join('');
}

pctSlider.addEventListener('input', () => { pctLabel.textContent = pctSlider.value + '%'; });

function resetSimResults() {
  document.getElementById('simResults').innerHTML = `
    <div class="empty-state">
      <p>Pick a decision, set a commitment level, and run the simulation to see outcomes here.</p>
    </div>`;
  document.getElementById('pipeline').innerHTML = '';
}

async function runSimulation() {
  const p = profile();
  if (!p) return;
  const decision = p.decisionTypes.find(d => d.id === decisionSelect.value);
  const pct = parseInt(pctSlider.value, 10);

  const pipelineEl = document.getElementById('pipeline');
  pipelineEl.innerHTML = AGENTS.map(a => `
    <div class="pipe-step" data-agent="${a.id}">
      <span class="pipe-step__dot"></span>
      <span class="pipe-step__name">${a.name}</span>
      <span class="pipe-step__state">Queued</span>
    </div>`).join('');

  document.getElementById('runSimBtn').disabled = true;

  for (const a of AGENTS) {
    const row = pipelineEl.querySelector(`[data-agent="${a.id}"]`);
    row.classList.add('is-running');
    row.querySelector('.pipe-step__state').textContent = 'Running…';
    state.agentStatus[a.id] = 'running';
    renderAgents();
    await new Promise(r => setTimeout(r, 260 + Math.random() * 180));
    row.classList.remove('is-running');
    row.classList.add('is-done');
    row.querySelector('.pipe-step__state').textContent = 'Done';
    state.agentStatus[a.id] = 'done';
    renderAgents();
  }

  // API Call to simulate
  let res;
  try {
      res = await window.api.simulateDecision(decision.id, pct);
  } catch (e) {
      console.error(e);
      document.getElementById('runSimBtn').disabled = false;
      return;
  }

  const cardsHtml = res.outcomes.map((o) => {
    const primaryStr = `${o.primary_outcome.toFixed(decision.primaryUnit === '%' || decision.primaryUnit === ' mo' ? 1 : 0)}${decision.primaryUnit}`;
    const secondaryStr = `${o.secondary_outcome.toFixed(decision.secondaryUnit === '%' || decision.secondaryUnit === ' mo' ? 1 : decision.secondaryUnit === ' Cr' ? 2 : 0)}${decision.secondaryUnit}`;
    return `
    <div class="outcome-card ${o.is_best ? 'is-best' : ''}">
      ${o.is_best ? '<span class="outcome-card__badge">Recommended</span>' : ''}
      <h4>${o.label}</h4>
      <div class="outcome-card__row"><span>${decision.primaryLabel}</span><b>${primaryStr}</b></div>
      <div class="outcome-card__row"><span>${decision.secondaryLabel}</span><b>${secondaryStr}</b></div>
    </div>`;
  }).join('');
  
  const best = res.outcomes.find(o => o.is_best);
  const explanation = res.explanation;

  document.getElementById('simResults').innerHTML = `
    <div class="panel__head"><h3>Outcomes — ${decision.label}</h3></div>
    <div class="outcome-grid">${cardsHtml}</div>
    <div class="explanation">
      <span class="explanation__label">Teach agent explains</span>
      <p>${explanation}</p>
    </div>`;

  state.simHistory.unshift({
    decisionLabel: decision.label, pct, bestLabel: best.label,
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
        <p class="decision-list__title">${s.decisionLabel} <span class="sim-history__pct">(${s.pct}% commitment tested)</span></p>
        <p class="decision-list__date">${s.time}</p>
      </div>
      <span class="tag tag--good">${s.bestLabel}</span>
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
    const sessions = await window.api.getChatSessions();
    if(chatSessionList) {
        chatSessionList.innerHTML = sessions.map(s => `
          <li style="padding: 8px; border-radius: 4px; cursor: pointer; font-size: 13px; background: ${s.id === currentSessionId ? 'var(--bg-subtle)' : 'transparent'}" 
              onclick="switchSession('${s.id}')">
            <div style="font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${s.title}</div>
            <div style="font-size: 11px; color: var(--ink-faint); margin-top: 2px;">${new Date(s.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
          </li>
        `).join('');
    }
  } catch(e) {
    console.error(e);
  }
}

window.switchSession = async function(id) {
  currentSessionId = id;
  chatLog.innerHTML = '';
  chatSuggestions.innerHTML = '';
  loadChatSessions(); 
  
  try {
    const session = await window.api.getChatSession(id);
    session.messages.forEach(m => {
      const who = m.role === 'assistant' || m.role === 'twin' ? 'twin' : 'user';
      addBubble(who, m.content);
    });
  } catch(e) {
    addBubble('twin', 'Failed to load chat history.');
  }
};

if(btnNewChat) {
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
  addBubble('twin', `Hi — I’m grounded in your custom financial profile. Ask me about your runway, savings, exposure, or anything else.`);
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
  if(currentSessionId) return; // Don't show suggestions in an active session
  chatSuggestions.innerHTML = SUGGESTIONS.map(s => `<button type="button" class="chip">${s}</button>`).join('');
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
      const res = await window.api.askTwin(text, currentSessionId);
      currentSessionId = res.session_id; 
      thinking.remove();
      addBubble('twin', res.answer);
      loadChatSessions(); 
  } catch(e) {
      thinking.remove();
      addBubble('twin', "I encountered an error connecting to the backend.");
  }
});

/* ============ Onboarding State ============ */
let obUserId = "";
let obPersona = "Individual";
let obMethod = "upload";
let obMessages = [];

/* ============ Init ============ */
const savedSession = localStorage.getItem('twin_session');
if (savedSession) {
    const session = JSON.parse(savedSession);
    obUserId = session.userId;
    if (session.hasProfile) {
        document.getElementById("appShell").classList.remove("is-onboarding");
        loadProfileAndRender().then(() => { renderAgents(); });
        switchView("overview");
    } else {
        showObView("view-type");
    }
} else {
    showObView("view-auth");
}

/* ============ Logout ============ */
document.getElementById("btnLogout").addEventListener("click", () => {
    localStorage.removeItem('twin_session');
    location.reload();
});

/* ============ Onboarding Logic ============ */

function showObView(id) {
    document.querySelectorAll(".view").forEach(v => v.classList.remove("is-active"));
    document.getElementById(id).classList.add("is-active");
}

document.getElementById("btnLogin").addEventListener("click", async () => {
    const email = document.getElementById("authEmail").value || "user@example.com";
    const pass = document.getElementById("authPassword").value || "password";
    const btn = document.getElementById("btnLogin");
    btn.disabled = true;
    btn.textContent = "Logging in...";
    
    try {
        const res = await window.api.login(email, pass);
        obUserId = res.user_id;
        
        localStorage.setItem('twin_session', JSON.stringify({
            token: res.access_token,
            userId: res.user_id,
            hasProfile: !!res.profile_key
        }));
        
        if (res.profile_key) {
            document.getElementById("appShell").classList.remove("is-onboarding");
            await loadProfileAndRender();
            renderAgents();
            switchView("overview");
        } else {
            showObView("view-type");
        }
    } catch (e) {
        alert("Login failed. Check credentials.");
    }
    btn.disabled = false;
    btn.textContent = "Continue";
});

document.querySelectorAll("#typeOptions .ob-option").forEach(opt => {
    opt.addEventListener("click", () => {
        document.querySelectorAll("#typeOptions .ob-option").forEach(o => o.classList.remove("is-selected"));
        opt.classList.add("is-selected");
        obPersona = opt.dataset.type;
    });
});

document.getElementById("btnTypeSelect").addEventListener("click", () => {
    if (obPersona === "Individual") {
        showObView("view-method");
    } else {
        showObView("view-confirm");
    }
});

document.querySelectorAll("#methodOptions .ob-option").forEach(opt => {
    opt.addEventListener("click", () => {
        document.querySelectorAll("#methodOptions .ob-option").forEach(o => o.classList.remove("is-selected"));
        opt.classList.add("is-selected");
        obMethod = opt.dataset.method;
    });
});

document.getElementById("btnMethodSelect").addEventListener("click", () => {
    if (obMethod === "upload") {
        showObView("view-upload");
    } else {
        obMessages = [];
        document.getElementById("obChatLog").innerHTML = "";
        addObBubble("twin", "Hello! Let`s build your financial twin. To start, roughly what is your monthly income?");
        showObView("view-ai-onboard");
    }
});

const obFile = document.getElementById("obFile");
const btnUpload = document.getElementById("btnUpload");

if(obFile) {
    obFile.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            document.getElementById("uploadLabel").textContent = e.target.files[0].name;
            btnUpload.disabled = false;
        }
    });
}

if(btnUpload) {
    btnUpload.addEventListener("click", async () => {
        btnUpload.textContent = "Extracting...";
        btnUpload.disabled = true;
        try {
            const data = await window.api.parseStatement(obFile.files[0]);
            document.getElementById("cfIncome").value = data.salary || 0;
            document.getElementById("cfSavings").value = data.savings || 0;
            let totalExp = 0;
            if (data.expenses) {
                Object.values(data.expenses).forEach(v => totalExp += (Number(v)||0));
            }
            document.getElementById("cfExpenses").value = totalExp;
            document.getElementById("cfLoans").value = data.loans || 0;
            showObView("view-confirm");
        } catch(err) {
            alert("Failed to parse statement.");
        }
        btnUpload.textContent = "Extract & Build Twin";
        btnUpload.disabled = false;
    });
}

document.getElementById("btnConfirmData").addEventListener("click", async () => {
    const btn = document.getElementById("btnConfirmData");
    btn.disabled = true;
    btn.textContent = "Initializing...";
    
    const metrics = [
        { id: "m_income", label: "Monthly Income", value: Number(document.getElementById("cfIncome").value || 0), trend: [0,0] },
        { id: "m_savings", label: "Total Savings", value: Number(document.getElementById("cfSavings").value || 0), trend: [0,0] },
        { id: "m_expenses", label: "Monthly Expenses", value: Number(document.getElementById("cfExpenses").value || 0), trend: [0,0] },
        { id: "m_loans", label: "Active Loans", value: Number(document.getElementById("cfLoans").value || 0), trend: [0,0] },
        { id: "m_health", label: "Financial Health", value: 85, isPercent: true, trend: [80,85] }
    ];
    
    try {
        const res = await window.api.confirmProfile(obUserId, obPersona, metrics);
        
        const sess = JSON.parse(localStorage.getItem('twin_session') || '{}');
        sess.hasProfile = true;
        localStorage.setItem('twin_session', JSON.stringify(sess));
        
        document.getElementById("appShell").classList.remove("is-onboarding");
        await loadProfileAndRender();
        renderAgents();
        switchView("overview");
    } catch (e) {
        alert("Failed to initialize twin.");
    }
    btn.disabled = false;
    btn.textContent = "Initialize Twin";
});

function addObBubble(who, text) {
    const div = document.createElement("div");
    div.className = "bubble bubble--" + who;
    if (who === "twin" && typeof marked !== "undefined") {
        div.innerHTML = marked.parse(text);
    } else {
        div.textContent = text;
    }
    document.getElementById("obChatLog").appendChild(div);
    document.getElementById("obChatLog").scrollTop = document.getElementById("obChatLog").scrollHeight;
    if (who === "twin") obMessages.push({role: "assistant", content: text});
    else obMessages.push({role: "user", content: text});
}

const obChatForm = document.getElementById("obChatForm");
if(obChatForm) {
    obChatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const input = document.getElementById("obChatInput");
        const text = input.value.trim();
        if (!text) return;
        
        input.value = "";
        addObBubble("user", text);
        
        const btn = e.target.querySelector("button");
        btn.disabled = true;
        
        try {
            const res = await window.api.onboardingChat(obMessages);
            let reply = res.reply;
            
            if (reply.includes("ONBOARDING_COMPLETE")) {
                const parts = reply.split("ONBOARDING_COMPLETE");
                if (parts[0].trim()) addObBubble("twin", parts[0]);
                
                try {
                    const match = parts[1].match(/\{[\s\S]*\}/);
                    if (match) {
                        const data = JSON.parse(match[0]);
                        document.getElementById("cfIncome").value = data.salary || 0;
                        document.getElementById("cfSavings").value = data.savings || 0;
                        let totalExp = 0;
                        if (data.expenses) { Object.values(data.expenses).forEach(v => totalExp += (Number(v)||0)); }
                        document.getElementById("cfExpenses").value = totalExp;
                        document.getElementById("cfLoans").value = data.loans || 0;
                    }
                } catch(e) {}
                showObView("view-confirm");
            } else {
                addObBubble("twin", reply);
            }
        } catch(e) {
            addObBubble("twin", "Sorry, I encountered an error.");
        }
        btn.disabled = false;
    });
}


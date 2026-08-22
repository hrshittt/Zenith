// auth.js - Handles logic for login.html and register.html

const API_BASE = 'http://127.0.0.1:8000';

function showError(id, msg) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = msg;
    el.style.display = 'block';
  }
}

function hideError(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

// ---------------------------------------------------------
// Login Flow
// ---------------------------------------------------------
const loginForm = document.getElementById('loginForm');
if (loginForm) {
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError('loginError');
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value.trim();
    const btn = document.getElementById('btnLogin');
    
    btn.disabled = true;
    btn.textContent = 'Logging in...';

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: email, password: password })
      });

      if (!res.ok) {
        throw new Error('Invalid credentials');
      }

      const data = await res.json();
      localStorage.setItem('twin_session', JSON.stringify({
        token: data.access_token,
        userId: data.user_id,
        username: data.username,
        profileKey: data.profile_key
      }));

      window.location.href = '/dashboard.html';
    } catch (err) {
      showError('loginError', err.message);
      btn.disabled = false;
      btn.textContent = 'Log In';
    }
  });
}

// ---------------------------------------------------------
// Registration Flow (Wizard)
// ---------------------------------------------------------
let selectedAccountType = 'individual'; // default
let currentStep = 1;

// Parse query params to optionally preselect type (e.g. ?type=startup)
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.has('type')) {
  selectedAccountType = urlParams.get('type').toLowerCase();
}

// Step 1: Type Selection
const typeOptions = document.querySelectorAll('#typeOptions .ob-option');
if (typeOptions.length > 0) {
  
  // Apply initial selection
  typeOptions.forEach(opt => {
    if (opt.dataset.type.toLowerCase() === selectedAccountType) {
      opt.classList.add('is-selected');
    } else {
      opt.classList.remove('is-selected');
    }
  });

  typeOptions.forEach(opt => {
    opt.addEventListener('click', () => {
      typeOptions.forEach(o => o.classList.remove('is-selected'));
      opt.classList.add('is-selected');
      selectedAccountType = opt.dataset.type.toLowerCase();
    });
  });

  const btnNext1 = document.getElementById('btnNext1');
  if (btnNext1) {
    btnNext1.addEventListener('click', () => {
      setStep(2);
    });
  }
}

// Wizard Step Navigation
function setStep(step) {
  document.querySelectorAll('.step-view').forEach(v => v.classList.remove('is-active'));
  currentStep = step;
  hideError('regError');
  
  if (step === 1) {
    document.getElementById('step1').classList.add('is-active');
  } else if (step === 2) {
    document.getElementById('step2').classList.add('is-active');
  } else if (step === 3) {
    document.getElementById(`step3-${selectedAccountType}`).classList.add('is-active');
  }
}

// Helper: Make authenticated POST request
async function authFetch(endpoint, payload) {
  const sess = JSON.parse(localStorage.getItem('twin_session') || '{}');
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${sess.token}`
    },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'An error occurred on the server.');
  }
  return res.json();
}

// Step 2: Create Account
const accountForm = document.getElementById('accountForm');
if (accountForm) {
  accountForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError('regError');
    const name = document.getElementById('regName').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    const password = document.getElementById('regPassword').value.trim();
    const btn = document.getElementById('btnCreateAccount');
    
    btn.disabled = true;
    btn.textContent = 'Creating account...';

    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: email, password: password })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Registration failed');
      }

      const data = await res.json();
      // Store token immediately to proceed with profile building
      localStorage.setItem('twin_session', JSON.stringify({
        token: data.access_token,
        userId: data.user_id,
        username: data.username,
        profileKey: data.profile_key
      }));

      setStep(3);
    } catch (err) {
      showError('regError', err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Create Account & Continue';
    }
  });
}

// Step 3: Complete Individual Profile
const indForm = document.getElementById('individualForm');
if (indForm) {
  indForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError('regError');
    const btn = document.getElementById('btnIndSubmit');
    btn.disabled = true;
    btn.textContent = 'Initializing...';

    const metrics = [
      { id: "m_income", label: "Monthly Income", value: Number(document.getElementById("indIncome").value || 0), unit: "", trend: [0,0] },
      { id: "m_savings", label: "Total Savings", value: Number(document.getElementById("indSavings").value || 0), unit: "", trend: [0,0] },
      { id: "m_expenses", label: "Monthly Expenses", value: Number(document.getElementById("indExpenses").value || 0), unit: "", trend: [0,0] },
      { id: "m_loans", label: "Active Loans", value: Number(document.getElementById("indLoans").value || 0), unit: "", trend: [0,0] },
      { id: "m_health", label: "Financial Health", value: 85, isPercent: true, trend: [80,85] }
    ];

    try {
      await authFetch('/onboard/confirm', {
        persona: "individual",
        metrics: metrics
      });
      window.location.href = '/dashboard.html';
    } catch (err) {
      showError('regError', err.message);
      btn.disabled = false;
      btn.textContent = 'Initialize Twin';
    }
  });
}

// Step 3: Complete Startup Profile
const suForm = document.getElementById('startupForm');
if (suForm) {
  suForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError('regError');
    const btn = document.getElementById('btnSuSubmit');
    btn.disabled = true;
    btn.textContent = 'Initializing...';

    const payload = {
      founder: { name: "Founder", email: "", mobile: "", preferred_language: "English" },
      company: { 
        name: document.getElementById('suCompanyName').value, 
        industry: document.getElementById('suIndustry').value,
        business_model: "", founded_year: 2024, stage: "", location: "", website: "", headcount: 0 
      },
      revenue: {
        is_pre_revenue: false,
        monthly_revenue: Number(document.getElementById('suMonthlyRevenue').value || 0),
        revenue_streams: "", revenue_growth_pct: null, paying_customers: 0
      },
      expenses: {
        fixed_costs: Number(document.getElementById('suFixedCosts').value || 0),
        variable_costs: 0
      },
      cash: {
        current_cash: Number(document.getElementById('suCurrentCash').value || 0),
        monthly_burn: Number(document.getElementById('suMonthlyBurn').value || 0)
      },
      debt: { business_loans_debt: 0 },
      funding: { total_funding: 0, last_round: "", currently_fundraising: false, fundraising_target: null },
      team: { planned_hires: 0, cost_per_hire: 0 },
      goals: [],
      current_decision: ""
    };

    try {
      await authFetch('/onboard/startup', payload);
      window.location.href = '/dashboard.html';
    } catch (err) {
      showError('regError', err.message);
      btn.disabled = false;
      btn.textContent = 'Initialize Twin';
    }
  });
}

// Step 3: Complete Enterprise Profile
const entForm = document.getElementById('enterpriseForm');
if (entForm) {
  entForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError('regError');
    const btn = document.getElementById('btnEntSubmit');
    btn.disabled = true;
    btn.textContent = 'Initializing...';

    const payload = {
      orgName: document.getElementById('entOrgName').value,
      treasury: Number(document.getElementById('entTreasury').value || 0),
      cashFlow: Number(document.getElementById('entCashFlow').value || 0),
      fx: Number(document.getElementById('entFx').value || 0)
    };

    try {
      await authFetch('/onboard/enterprise', payload);
      window.location.href = '/dashboard.html';
    } catch (err) {
      showError('regError', err.message);
      btn.disabled = false;
      btn.textContent = 'Initialize Twin';
    }
  });
}

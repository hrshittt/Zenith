// auth.js - Handles logic for login.html and register.html

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:8000' : `http://${window.location.hostname}:8000`;

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

      // Check onboarding status
      if (data.profile_key && data.profile_key.trim() !== '') {
        window.location.href = '/dashboard.html';
      } else {
        window.location.href = '/register.html?resume=true';
      }
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
  } else if (step === 4) {
    document.getElementById(`step4-${selectedAccountType}`).classList.add('is-active');
  } else if (step === 5) {
    document.getElementById(`step5-${selectedAccountType}`).classList.add('is-active');
  }
}

// Resume onboarding if needed
if (urlParams.has('zoho')) {
  const zohoStatus = urlParams.get('zoho');
  const savedState = JSON.parse(localStorage.getItem('twin_onboarding_state') || '{}');
  if (savedState.accountType) selectedAccountType = savedState.accountType;
  
  if (zohoStatus === 'success') {
    savedState.zohoConnected = true;
    localStorage.setItem('twin_onboarding_state', JSON.stringify(savedState));
    
    // Inject real data pulled from Zoho Books
    const cash = parseFloat(urlParams.get('cash') || 0);
    const rev = parseFloat(urlParams.get('rev') || 0);
    const burn = parseFloat(urlParams.get('burn') || 0);

    document.getElementById('suCurrentCash').value = cash;
    document.getElementById('suMonthlyRevenue').value = rev;
    document.getElementById('suMonthlyBurn').value = burn;
    document.getElementById('zohoMsg').style.display = 'block';
    
    if (cash === 0 && rev === 0 && burn === 0) {
      document.getElementById('zohoMsg').textContent = '✅ Zoho Books connected! (Note: No active transactions found, please fill manually)';
    } else {
      document.getElementById('zohoMsg').textContent = '✅ Zoho Books connected. We imported your real data. Please review.';
    }
    
    document.getElementById('step5Title').textContent = 'Confirm Financial Details';
    
    updateCalculations();
    setStep(5);
  } else {
    alert("Zoho connection failed or was cancelled. Please try again or use Manual Entry.");
    setStep(4);
  }
} else if (urlParams.has('resume') && urlParams.get('resume') === 'true') {
  const savedState = JSON.parse(localStorage.getItem('twin_onboarding_state') || '{}');
  if (savedState.accountType) selectedAccountType = savedState.accountType;
  
  if (!savedState.startupProfileCompleted) {
    setStep(3);
  } else if (!savedState.financialSetupCompleted) {
    setStep(4);
  } else {
    setStep(3); // fallback
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
const suProfileForm = document.getElementById('startupProfileForm');
if (suProfileForm) {
  suProfileForm.addEventListener('submit', (e) => {
    e.preventDefault();
    hideError('regError');
    
    const state = JSON.parse(localStorage.getItem('twin_onboarding_state') || '{}');
    state.accountType = 'startup';
    state.companyName = document.getElementById('suCompanyName').value;
    state.industry = document.getElementById('suIndustry').value;
    state.businessModel = document.getElementById('suBusinessModel').value;
    state.stage = document.getElementById('suStage').value;
    state.headcount = Number(document.getElementById('suHeadcount').value || 1);
    state.startupProfileCompleted = true;
    
    localStorage.setItem('twin_onboarding_state', JSON.stringify(state));
    setStep(4);
  });
}

// Step 4: Financial Setup Choice
let selectedFinType = 'manual';
const finSetupOptions = document.querySelectorAll('#finSetupOptions .ob-option');
if (finSetupOptions.length > 0) {
  finSetupOptions.forEach(opt => {
    opt.addEventListener('click', () => {
      finSetupOptions.forEach(o => o.classList.remove('is-selected'));
      opt.classList.add('is-selected');
      selectedFinType = opt.dataset.finType;
    });
  });

  const btnNext4 = document.getElementById('btnNext4Startup');
  if (btnNext4) {
    btnNext4.addEventListener('click', () => {
      const state = JSON.parse(localStorage.getItem('twin_onboarding_state') || '{}');
      if (selectedFinType === 'zoho') {
        // Trigger real Zoho OAuth Flow
        btnNext4.disabled = true;
        btnNext4.textContent = 'Connecting to Zoho...';
        
        // Save state so we can resume properly when callback returns
        state.zohoConnected = false; 
        localStorage.setItem('twin_onboarding_state', JSON.stringify(state));
        
        window.location.href = `${API_BASE}/api/zoho/auth`;
      } else {
        document.getElementById('zohoMsg').style.display = 'none';
        document.getElementById('step5Title').textContent = 'Enter Financial Details';
        state.zohoConnected = false;
        localStorage.setItem('twin_onboarding_state', JSON.stringify(state));
        setStep(5);
      }
    });
  }
}

// Auto-calculations for Step 5
function updateCalculations() {
  const cash = Number(document.getElementById('suCurrentCash').value || 0);
  const rev = Number(document.getElementById('suMonthlyRevenue').value || 0);
  const burn = Number(document.getElementById('suMonthlyBurn').value || 0);
  
  const netCashFlow = rev - burn;
  const runway = (netCashFlow < 0 && cash > 0) ? (cash / Math.abs(netCashFlow)).toFixed(1) : '\u221E';
  
  document.getElementById('calcCashFlow').textContent = (netCashFlow < 0 ? '-' : '+') + '\u20B9' + Math.abs(netCashFlow).toLocaleString();
  document.getElementById('calcCashFlow').style.color = netCashFlow < 0 ? 'var(--warn)' : 'var(--good)';
  document.getElementById('calcRunway').textContent = runway;
  document.getElementById('calcRunway').style.color = (runway !== '\u221E' && runway < 6) ? 'var(--warn)' : 'var(--good)';
}

const calcInputs = ['suCurrentCash', 'suMonthlyRevenue', 'suMonthlyBurn'];
calcInputs.forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', updateCalculations);
});

// Step 5: Final Submission
const suFinForm = document.getElementById('startupFinForm');
if (suFinForm) {
  suFinForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError('regError');
    const btn = document.getElementById('btnSuSubmit');
    btn.disabled = true;
    btn.textContent = 'Initializing Twin...';

    const state = JSON.parse(localStorage.getItem('twin_onboarding_state') || '{}');
    state.financialSetupCompleted = true;
    localStorage.setItem('twin_onboarding_state', JSON.stringify(state));

    const payload = {
      founder: { name: "Founder", email: "", mobile: "", preferred_language: "English" },
      company: { 
        name: state.companyName || "My Startup", 
        industry: state.industry || "",
        business_model: state.businessModel || "", 
        founded_year: new Date().getFullYear(), 
        stage: state.stage || "", 
        location: "", 
        website: "", 
        headcount: state.headcount || 1 
      },
      revenue: {
        is_pre_revenue: (Number(document.getElementById('suMonthlyRevenue').value || 0) === 0),
        monthly_revenue: Number(document.getElementById('suMonthlyRevenue').value || 0),
        revenue_streams: [], revenue_growth_pct: null, paying_customers: 0
      },
      expenses: {
        fixed_costs: Number(document.getElementById('suMonthlyBurn').value || 0), // Assumed as total for simplification
        variable_costs: 0
      },
      cash: {
        current_cash: Number(document.getElementById('suCurrentCash').value || 0),
        monthly_burn: Number(document.getElementById('suMonthlyBurn').value || 0)
      },
      debt: { business_loans_debt: Number(document.getElementById('suDebt').value || 0) },
      funding: { 
        total_funding: Number(document.getElementById('suTotalFunding').value || 0), 
        last_round: "", 
        currently_fundraising: false, 
        fundraising_target: null 
      },
      team: { planned_hires: 0, cost_per_hire: 0 },
      goals: [],
      current_decision: ""
    };

    try {
      await authFetch('/onboard/startup', payload);
      
      // Update session with new profileKey
      const sess = JSON.parse(localStorage.getItem('twin_session') || '{}');
      sess.profileKey = 'startup';
      localStorage.setItem('twin_session', JSON.stringify(sess));
      
      // Mark global onboarding complete
      state.onboardingCompleted = true;
      localStorage.setItem('twin_onboarding_state', JSON.stringify(state));
      
      window.location.href = '/dashboard.html';
    } catch (err) {
      showError('regError', err.message);
      btn.disabled = false;
      btn.textContent = 'Create Financial Twin';
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

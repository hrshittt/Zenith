/* ==========================================================================
   TWIN — Startup journey (separate from Individual)
   Onboarding wizard + Overview/Hisaab/Alerts/Reports rendering, driven
   entirely by the deterministic /startup/* and /onboard/startup APIs.
   Relies on escapeHtml/fmt/sparkline/switchView/loadProfileAndRender/
   profile(), all defined in app.js (loaded after this file, but only
   referenced here inside function bodies that run later).
   ========================================================================== */

window.startupState = window.startupState || {};

const STARTUP_SCENARIO_SUGGESTIONS = [
  'What happens if I hire 5 engineers?',
  'What if I raise ₹2 Cr?',
  'What happens if I increase marketing spend by 20%?',
  'What if my revenue drops by 15%?',
  'What if I cut costs by ₹1,00,000/month?'
];

const STARTUP_CHAT_SUGGESTIONS = [
  'How much runway do I have?',
  'Why did my burn increase?',
  'Is my current hiring plan sustainable?'
];

const STARTUP_TITLES = {
  overview: ['Startup Overview', 'Live snapshot of your Startup Financial Twin'],
  hisaab: ['Hisaab', 'Money in, money out, and net — categorized'],
  ask: ['Ask Twin', 'Grounded answers from your Startup Financial Twin'],
  simulate: ['Simulate a decision', 'Run scenarios on your startup twin before anything is recommended'],
  alerts: ['Risk alerts', 'Runway, burn, revenue, hiring, and goal alerts'],
  reports: ['Reports', 'Daily brief and weekly financial health report']
};

/* ============ Nav / persona ============ */
function applyPersonaNav(personaKey) {
  document.querySelectorAll('.navitem[data-persona]').forEach(btn => {
    btn.style.display = (btn.dataset.persona === personaKey) ? '' : 'none';
  });
  document.querySelectorAll('.profileSwitch button').forEach(b => {
    b.classList.toggle('is-active', b.dataset.profile === personaKey);
  });
}

/* ============ Shared calc-info toggle ============ */
function suStatusLabel(status) {
  const map = { actual: 'Actual', forecast: 'Forecast', estimated: 'Estimated', assumption: 'Assumption', insufficient_data: 'Insufficient data' };
  return map[status] || status;
}

function attachCalcInfoToggles(container) {
  container.querySelectorAll('.calc-info-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      const showing = target.style.display !== 'none';
      target.style.display = showing ? 'none' : 'block';
      btn.textContent = showing ? 'How is this calculated?' : 'Hide calculation';
    });
  });
}

function suCalcInfoHtml(m, idSuffix) {
  const id = 'calc-' + m.id + '-' + idSuffix;
  const inputsTxt = Object.entries(m.calculation.inputs || {}).map(([k, v]) => `${k}: ${v === null || v === undefined ? '—' : v}`).join(', ');
  return `
    <button type="button" class="calc-info-toggle" data-target="${id}">How is this calculated?</button>
    <div class="calc-info" id="${id}" style="display:none;">
      <p><b>Formula:</b> ${escapeHtml(m.calculation.formula)}</p>
      <p><b>Inputs:</b> ${escapeHtml(inputsTxt || 'none')}</p>
      <p><b>Data source:</b> ${escapeHtml(m.calculation.data_source)}</p>
      <p><b>Last updated:</b> ${new Date(m.calculation.last_updated).toLocaleString()}</p>
    </div>`;
}

function suMetricCardHtml(m) {
  return `
    <div class="stat-card">
      <div class="stat-card__label-row">
        <span class="stat-card__label">${escapeHtml(m.label)}</span>
        <span class="status-chip status-chip--${m.status}">${suStatusLabel(m.status)}</span>
      </div>
      <span class="stat-card__value">${escapeHtml(m.display)}</span>
      ${suCalcInfoHtml(m, 'card')}
    </div>`;
}

function suMetricRowHtml(m) {
  if (!m) return '';
  return `
    <div class="metric-row">
      <div class="metric-row__main">
        <span class="metric-row__label">${escapeHtml(m.label)}</span>
        <span class="status-chip status-chip--${m.status}">${suStatusLabel(m.status)}</span>
      </div>
      <div class="metric-row__value">${escapeHtml(m.display)}</div>
      ${suCalcInfoHtml(m, 'row')}
    </div>`;
}

/* ============ Onboarding wizard ============ */
let suStep = 1;
const SU_TOTAL_STEPS = 4;

function suGoToStep(n) {
  suStep = n;
  document.querySelectorAll('#suWizardForm .wizard-step').forEach(el => {
    el.classList.toggle('is-active', Number(el.dataset.step) === n);
  });
  document.querySelectorAll('.wizard__step').forEach(el => {
    const s = Number(el.dataset.step);
    el.classList.toggle('is-active', s === n);
    el.classList.toggle('is-done', s < n);
  });
  const backBtn = document.getElementById('suBtnBack');
  const nextBtn = document.getElementById('suBtnNext');
  if (backBtn) backBtn.style.visibility = n === 1 ? 'hidden' : 'visible';
  if (nextBtn) nextBtn.textContent = n === SU_TOTAL_STEPS ? 'Create my Startup Twin' : 'Next';
  const errEl = document.getElementById('suWizardError');
  if (errEl) errEl.style.display = 'none';
}

function suResetWizard() {
  const form = document.getElementById('suWizardForm');
  if (form) form.reset();
  suGoToStep(1);
}

function suValidateStep(n) {
  if (n === 1) {
    if (!document.getElementById('suFounderName').value.trim()) return 'Founder name is required.';
    const email = document.getElementById('suFounderEmail').value.trim();
    if (!email || !email.includes('@')) return 'A valid founder email is required.';
    if (!document.getElementById('suCompanyName').value.trim()) return 'Company name is required.';
  }
  if (n === 3) {
    const cash = document.getElementById('suCurrentCash').value;
    if (cash === '' || cash === null) return 'Current cash is required — the twin needs this to compute anything else.';
  }
  return null;
}

function suNum(id) {
  const el = document.getElementById(id);
  if (!el || el.value === '') return null;
  const v = Number(el.value);
  return Number.isNaN(v) ? null : v;
}

function suStr(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  const v = el.value.trim();
  return v === '' ? null : v;
}

function suBuildGoals() {
  const goals = [];
  if (document.getElementById('suGoalRunway').checked) {
    const t = suNum('suGoalRunwayTarget');
    goals.push({ type: 'extend_runway', label: 'Extend runway' + (t ? ` to ${t} months` : ''), target_value: t, target_unit: 'months' });
  }
  if (document.getElementById('suGoalRevenue').checked) {
    const t = suNum('suGoalRevenueTarget');
    goals.push({ type: 'revenue_milestone', label: 'Reach ₹' + (t ? fmt(t) : '?') + ' monthly revenue', target_value: t, target_unit: 'INR/mo' });
  }
  if (document.getElementById('suGoalFundraise').checked) {
    const t = suNum('suGoalFundraiseTarget');
    goals.push({ type: 'fundraise', label: 'Raise ₹' + (t ? fmt(t) : '?'), target_value: t, target_unit: 'INR' });
  }
  if (document.getElementById('suGoalProfitability').checked) {
    goals.push({ type: 'profitability', label: 'Reach profitability' });
  }
  if (document.getElementById('suGoalCustom').checked) {
    goals.push({ type: 'custom', label: suStr('suGoalCustomLabel') || 'Custom goal' });
  }
  return goals;
}

async function suSubmitWizard() {
  const nextBtn = document.getElementById('suBtnNext');
  const backBtn = document.getElementById('suBtnBack');
  nextBtn.disabled = true;
  backBtn.disabled = true;
  nextBtn.textContent = 'Creating your twin…';

  const payload = {
    founder: {
      name: suStr('suFounderName'), email: suStr('suFounderEmail'),
      mobile: suStr('suFounderMobile'), preferred_language: suStr('suFounderLang')
    },
    company: {
      name: suStr('suCompanyName'), industry: suStr('suIndustry'), business_model: suStr('suBusinessModel'),
      founded_year: suNum('suFoundedYear'), stage: suStr('suStage'), location: suStr('suLocation'),
      website: suStr('suWebsite'), headcount: suNum('suHeadcount')
    },
    revenue: {
      is_pre_revenue: document.getElementById('suPreRevenue').checked,
      monthly_revenue: suNum('suMonthlyRevenue'),
      revenue_streams: (suStr('suRevenueStreams') || '').split(',').map(s => s.trim()).filter(Boolean),
      revenue_growth_pct: suNum('suRevenueGrowth'),
      paying_customers: suNum('suPayingCustomers')
    },
    expenses: { fixed_costs: suNum('suFixedCosts'), variable_costs: suNum('suVariableCosts') },
    cash: { current_cash: suNum('suCurrentCash'), monthly_burn: suNum('suMonthlyBurn') },
    debt: { business_loans_debt: suNum('suDebt') },
    funding: {
      total_funding: suNum('suTotalFunding'), last_round: suStr('suLastRound'),
      currently_fundraising: document.getElementById('suFundraising').checked,
      fundraising_target: suNum('suFundraisingTarget')
    },
    team: { planned_hires: suNum('suPlannedHires'), cost_per_hire: suNum('suCostPerHire') },
    goals: suBuildGoals(),
    current_decision: suStr('suDecision')
  };

  try {
    const overview = await window.api.startupOnboard(payload);
    window.startupState.overview = overview;

    const sess = JSON.parse(localStorage.getItem('twin_session') || '{}');
    sess.hasProfile = true;
    localStorage.setItem('twin_session', JSON.stringify(sess));

    document.getElementById('appShell').classList.remove('is-onboarding');
    applyPersonaNav('startup');
    await loadProfileAndRender();
    renderAgents();
    switchView('overview');
  } catch (e) {
    const errEl = document.getElementById('suWizardError');
    errEl.textContent = 'Failed to create your twin: ' + (e.message || 'please try again.');
    errEl.style.display = 'block';
  }
  nextBtn.disabled = false;
  backBtn.disabled = false;
  suGoToStep(suStep);
}

const suBtnNextEl = document.getElementById('suBtnNext');
if (suBtnNextEl) {
  suBtnNextEl.addEventListener('click', async () => {
    const err = suValidateStep(suStep);
    const errEl = document.getElementById('suWizardError');
    if (err) { errEl.textContent = err; errEl.style.display = 'block'; return; }
    errEl.style.display = 'none';
    if (suStep < SU_TOTAL_STEPS) {
      suGoToStep(suStep + 1);
    } else {
      await suSubmitWizard();
    }
  });
}
const suBtnBackEl = document.getElementById('suBtnBack');
if (suBtnBackEl) {
  suBtnBackEl.addEventListener('click', () => { if (suStep > 1) suGoToStep(suStep - 1); });
}

/* ============ Chart primitives — plain inline SVG, no chart library ============
   "Show the financial insight visually first, then let Tathya explain it."
   All values plotted here come straight from the API response (the Financial
   Twin / deterministic engine) — nothing here computes a new number, it only
   draws the ones the backend already gave us. */

function suAbbrevINR(v) {
  if (v === null || v === undefined) return '—';
  const sign = v < 0 ? '-' : '';
  const abs = Math.abs(v);
  if (abs >= 1e7) return sign + (abs / 1e7).toFixed(abs % 1e7 === 0 ? 0 : 1) + 'Cr';
  if (abs >= 1e5) return sign + (abs / 1e5).toFixed(abs % 1e5 === 0 ? 0 : 1) + 'L';
  if (abs >= 1e3) return sign + (abs / 1e3).toFixed(0) + 'k';
  return sign + Math.round(abs);
}

function suHealthColor(score) {
  if (score === null || score === undefined) return 'var(--status-neutral)';
  if (score >= 70) return 'var(--status-good)';
  if (score >= 40) return 'var(--status-warning)';
  return 'var(--status-critical)';
}

function suIndicatorColor(status) {
  const map = { good: 'var(--status-good)', warning: 'var(--status-warning)', serious: 'var(--status-serious)', critical: 'var(--status-critical)', insufficient_data: 'var(--status-neutral)' };
  return map[status] || 'var(--status-neutral)';
}

/** A line/area trend chart supporting multiple series (e.g. Actual vs
 * Forecast, or Baseline vs Scenario), reference threshold lines, and
 * marker-only series (e.g. a single "cash-out" point). Native <title>
 * elements give every point a hover tooltip with the exact value. */
function svgTrendChart(opts) {
  const { series, width = 600, height = 220, currency = '₹', xLabels = [], refLines = [] } = opts;
  const padding = { top: 14, right: 16, bottom: 26, left: 56 };
  const plotW = Math.max(10, width - padding.left - padding.right);
  const plotH = Math.max(10, height - padding.top - padding.bottom);

  const allY = [];
  let maxLen = 0;
  series.forEach(s => {
    s.points.forEach(p => { if (typeof p.y === 'number') allY.push(p.y); });
    maxLen = Math.max(maxLen, s.points.length);
  });
  refLines.forEach(rl => allY.push(rl.value));
  if (!allY.length || maxLen < 2) return null;

  let yMin = Math.min(0, ...allY);
  let yMax = Math.max(...allY);
  if (yMax === yMin) yMax = yMin + 1;
  yMax += (yMax - yMin) * 0.14;

  const xForIndex = i => padding.left + (maxLen === 1 ? 0 : (i / (maxLen - 1)) * plotW);
  const yForValue = v => padding.top + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  const gridCount = 4;
  let gridSvg = '', yLabelsSvg = '';
  for (let g = 0; g <= gridCount; g++) {
    const val = yMin + (yMax - yMin) * (g / gridCount);
    const y = yForValue(val);
    gridSvg += `<line x1="${padding.left}" y1="${y.toFixed(1)}" x2="${width - padding.right}" y2="${y.toFixed(1)}" stroke="var(--chart-grid)" stroke-width="1"/>`;
    yLabelsSvg += `<text x="${padding.left - 8}" y="${(y + 3).toFixed(1)}" text-anchor="end" class="chart-axis-label">${currency}${suAbbrevINR(val)}</text>`;
  }

  let refSvg = '';
  refLines.forEach(rl => {
    const y = yForValue(rl.value);
    refSvg += `<line x1="${padding.left}" y1="${y.toFixed(1)}" x2="${width - padding.right}" y2="${y.toFixed(1)}" stroke="${rl.color || 'var(--status-critical)'}" stroke-width="1.2" stroke-dasharray="3,3"/>`;
    if (rl.label) refSvg += `<text x="${width - padding.right}" y="${(y - 4).toFixed(1)}" text-anchor="end" class="chart-axis-label" fill="${rl.color || 'var(--status-critical)'}">${escapeHtml(rl.label)}</text>`;
  });

  let seriesSvg = '';
  series.forEach(s => {
    const coords = s.points.map((p, i) => typeof p.y === 'number' ? [xForIndex(i), yForValue(p.y)] : null);
    if (!s.markerOnly) {
      let d = '', started = false;
      coords.forEach(c => {
        if (!c) { started = false; return; }
        d += (started ? 'L' : 'M') + c[0].toFixed(1) + ',' + c[1].toFixed(1) + ' ';
        started = true;
      });
      if (d) {
        if (s.area) {
          const baselineY = yForValue(Math.max(yMin, 0));
          let firstX = null, lastX = null;
          coords.forEach(c => { if (c) { if (firstX === null) firstX = c[0]; lastX = c[0]; } });
          seriesSvg += `<path d="${d}L${lastX.toFixed(1)},${baselineY.toFixed(1)} L${firstX.toFixed(1)},${baselineY.toFixed(1)} Z" fill="${s.color}" opacity="0.12" stroke="none"/>`;
        }
        seriesSvg += `<path d="${d.trim()}" fill="none" stroke="${s.color}" stroke-width="2" ${s.dashed ? 'stroke-dasharray="5,4"' : ''} stroke-linecap="round" stroke-linejoin="round"/>`;
      }
    }
    const r = s.markerRadius || 3.2;
    s.points.forEach((p, i) => {
      if (typeof p.y !== 'number' || p.noMarker) return;
      const [x, y] = [xForIndex(i), yForValue(p.y)];
      seriesSvg += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${s.color}" stroke="var(--surface)" stroke-width="1.4"><title>${escapeHtml(p.tooltip || (s.label + ': ' + currency + fmt(p.y)))}</title></circle>`;
    });
  });

  let xLabelsSvg = '';
  if (xLabels && xLabels.length) {
    const step = Math.max(1, Math.round(maxLen / Math.min(6, maxLen)));
    for (let i = 0; i < maxLen; i += step) {
      if (!xLabels[i]) continue;
      xLabelsSvg += `<text x="${xForIndex(i).toFixed(1)}" y="${height - 6}" text-anchor="middle" class="chart-axis-label">${escapeHtml(xLabels[i])}</text>`;
    }
  }

  return `<svg class="chart-svg" viewBox="0 0 ${width} ${height}" width="100%" height="${height}" preserveAspectRatio="xMidYMid meet">${gridSvg}${refSvg}${seriesSvg}${yLabelsSvg}${xLabelsSvg}</svg>`;
}

/** Categorical donut — capped at `maxSlices` + an "Other" bucket, fixed hue
 * order (never cycled), each slice tooltipped with its exact value. */
function svgDonutChart(items, opts) {
  const { size = 152, currency = '₹', maxSlices = 5 } = opts || {};
  if (!items || !items.length) return null;
  const palette = ['var(--chart-blue)', 'var(--chart-orange)', 'var(--chart-aqua)', 'var(--chart-yellow)', 'var(--chart-magenta)', 'var(--chart-violet)'];
  const sorted = [...items].sort((a, b) => b.amount - a.amount);
  const sliced = sorted.slice(0, maxSlices);
  const rest = sorted.slice(maxSlices);
  if (rest.length) sliced.push({ category: 'Other', amount: rest.reduce((s, i) => s + i.amount, 0) });

  const total = sliced.reduce((s, i) => s + i.amount, 0) || 1;
  const r = size / 2, cx = size / 2, cy = size / 2, strokeW = size * 0.24, rInner = r - strokeW / 2;
  const gapDeg = sliced.length > 1 ? 2.5 : 0;
  let angle = -90, arcs = '';
  const withColor = sliced.map((it, idx) => ({ ...it, _color: palette[idx % palette.length], _pct: (it.amount / total) * 100 }));
  withColor.forEach(it => {
    const sweepFull = (it.amount / total) * 360;
    const sweep = Math.max(0, sweepFull - gapDeg);
    const startRad = angle * Math.PI / 180, endRad = (angle + sweep) * Math.PI / 180;
    const x1 = cx + rInner * Math.cos(startRad), y1 = cy + rInner * Math.sin(startRad);
    const x2 = cx + rInner * Math.cos(endRad), y2 = cy + rInner * Math.sin(endRad);
    const largeArc = sweep > 180 ? 1 : 0;
    arcs += `<path d="M${x1.toFixed(2)},${y1.toFixed(2)} A${rInner.toFixed(2)},${rInner.toFixed(2)} 0 ${largeArc} 1 ${x2.toFixed(2)},${y2.toFixed(2)}" fill="none" stroke="${it._color}" stroke-width="${strokeW.toFixed(1)}"><title>${escapeHtml(it.category)}: ${currency}${fmt(it.amount)} (${it._pct.toFixed(0)}%)</title></path>`;
    angle += sweepFull;
  });

  const svg = `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">${arcs}</svg>`;
  const legendHtml = `<ul class="donut-legend">${withColor.map(it => `
    <li><span class="donut-legend__name"><span class="chart-legend__swatch" style="background:${it._color};"></span>${escapeHtml(it.category)}</span><span class="donut-legend__value">${currency}${fmt(it.amount)} · ${it._pct.toFixed(0)}%</span></li>`).join('')}</ul>`;
  return { svg, legendHtml };
}

/** Circular progress ring — used for both the overall Health Score hero and
 * individual goal cards. */
function svgProgressRing(pct, opts) {
  const { size = 92, color = 'var(--primary)', strokeW = 9, showLabel = true } = opts || {};
  const r = (size - strokeW) / 2, c = size / 2;
  const circumference = 2 * Math.PI * r;
  const clamped = (pct === null || pct === undefined) ? 0 : Math.max(0, Math.min(100, pct));
  const dash = circumference * clamped / 100;
  const labelText = (pct === null || pct === undefined) ? '—' : Math.round(clamped) + '%';
  return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">
    <circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="var(--surface-2)" stroke-width="${strokeW}"/>
    <circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${color}" stroke-width="${strokeW}" stroke-linecap="round"
      stroke-dasharray="${dash.toFixed(1)} ${circumference.toFixed(1)}" transform="rotate(-90 ${c} ${c})"/>
    ${showLabel ? `<text x="${c}" y="${c + size * 0.06}" text-anchor="middle" font-family="var(--font-mono)" font-size="${(size * 0.2).toFixed(0)}" fill="var(--ink)">${labelText}</text>` : ''}
  </svg>`;
}

/* ============ Overview ============ */
function renderStartupPersonaStrip(overview) {
  const c = overview.company || {};
  const bits = [c.company_name, c.stage, c.industry].filter(Boolean);
  document.getElementById('personaLabel').textContent = bits.join(' · ') || 'Your Startup';

  const goals = overview.goals || [];
  const goalStrip = document.getElementById('goalStrip');
  if (goals.length) {
    const g = goals[0];
    const pctTxt = (g.progress_pct !== null && g.progress_pct !== undefined) ? `${g.progress_pct.toFixed(0)}% there` : 'tracking';
    goalStrip.textContent = `${g.label} — ${pctTxt}` + (goals.length > 1 ? ` (+${goals.length - 1} more goal${goals.length > 2 ? 's' : ''})` : '');
  } else {
    goalStrip.textContent = 'No goals set yet';
  }
}

function renderStartupStatGrid(overview) {
  const m = overview.metrics || {};
  const order = ['cash_position', 'net_burn', 'runway', 'revenue'];
  const grid = document.getElementById('statGrid');
  grid.innerHTML = order.map(id => (m[id] ? suMetricCardHtml(m[id]) : '')).join('');
  attachCalcInfoToggles(grid);
}

/* ---- 1. Financial Health ---- */
function suHealthNarrative(overview) {
  const health = (overview.metrics || {}).financial_health;
  const indicators = overview.health_indicators || [];
  if (!health || health.value === null || health.value === undefined) {
    return "Not enough data yet to compute a Financial Health Score — add Cash and Expenses to your profile.";
  }
  const weak = indicators.filter(i => i.status === 'critical' || i.status === 'serious').map(i => i.label);
  const strong = indicators.filter(i => i.status === 'good').map(i => i.label);
  const parts = [`Your Financial Health Score is ${Math.round(health.value)}/100.`];
  if (weak.length) parts.push(`${weak.join(' and ')} ${weak.length > 1 ? 'are' : 'is'} pulling it down.`);
  if (strong.length) parts.push(`${strong.join(', ')} ${strong.length > 1 ? 'are' : 'is'} in good shape.`);
  return parts.join(' ');
}

function renderHealthSection(overview) {
  const health = (overview.metrics || {}).financial_health;
  const score = health ? health.value : null;
  const indicators = overview.health_indicators || [];

  const componentsHtml = indicators.map(ind => `
    <div class="health-component">
      <div class="health-component__head">
        <span class="health-component__label"><span class="dot-status dot-status--${ind.status}"></span> ${escapeHtml(ind.label)}</span>
      </div>
      <div class="health-component__value">${escapeHtml(ind.display)}</div>
      <div class="health-component__bar"><div class="health-component__bar-fill" style="width:100%; background:${suIndicatorColor(ind.status)};"></div></div>
      <span class="health-component__meta">${escapeHtml(ind.detail || '')}</span>
    </div>`).join('');

  return `
    <div class="panel">
      <div class="panel__head">
        <h3>Financial Health</h3>
        ${health ? `<span class="status-chip status-chip--${health.status}">${suStatusLabel(health.status)}</span>` : ''}
      </div>
      <div class="health-hero">
        <div class="health-hero__ring">${svgProgressRing(score, { size: 108, color: suHealthColor(score), strokeW: 10 })}</div>
        <div class="health-hero__body">
          <p class="health-hero__narrative">${escapeHtml(suHealthNarrative(overview))}</p>
          <div class="health-components">${componentsHtml}</div>
        </div>
      </div>
      ${health ? suCalcInfoHtml(health, 'health') : ''}
    </div>`;
}

/* ---- 2. Cash & Runway (shared block — reused by Overview and Ask Twin) ---- */
function suCashRunwayBlockHtml(history, projection, currency) {
  history = history || [];
  projection = projection || {};
  const forecastSeries = projection.series || [];
  const histLen = history.length;
  const foreLen = forecastSeries.length;
  const totalLen = histLen + foreLen;

  let chartHtml;
  if (totalLen < 2) {
    chartHtml = `<p class="sim-empty">Not enough data yet to chart cash forward — add Current Cash and expenses to your profile.</p>`;
  } else {
    const actualPts = [], forecastPts = [];
    for (let i = 0; i < totalLen; i++) {
      if (i < histLen) actualPts.push({ y: history[i].cash, tooltip: `${history[i].date}: ${currency}${fmt(history[i].cash)} (Actual)` });
      else actualPts.push({ y: null });
    }
    for (let i = 0; i < totalLen; i++) {
      if (i < histLen - 1) forecastPts.push({ y: null });
      else if (i === histLen - 1) forecastPts.push({ y: histLen ? history[histLen - 1].cash : (foreLen ? forecastSeries[0].projected_cash : null), tooltip: 'Today', noMarker: histLen > 0 });
      else {
        const f = forecastSeries[i - histLen];
        forecastPts.push({ y: f.projected_cash, tooltip: `Month +${f.month}: ${currency}${fmt(f.projected_cash)} (Forecast)` });
      }
    }
    const xLabels = [];
    for (let i = 0; i < totalLen; i++) xLabels.push(i < histLen ? history[i].date.slice(5) : `+${forecastSeries[i - histLen].month}mo`);

    const seriesList = [
      { label: 'Actual', color: 'var(--chart-blue)', points: actualPts, area: true },
      { label: 'Forecast', color: 'var(--chart-orange)', dashed: true, points: forecastPts },
    ];
    if (projection.cash_out_month) {
      const idx = histLen - 1 + projection.cash_out_month;
      const coPts = new Array(totalLen).fill(null).map(() => ({ y: null }));
      if (idx >= 0 && idx < totalLen) coPts[idx] = { y: 0, tooltip: `Projected cash-out — month ${projection.cash_out_month}` };
      seriesList.push({ label: 'Cash-out point', color: 'var(--status-critical)', points: coPts, markerOnly: true, markerRadius: 5.5 });
    }
    const refLines = [{ value: 0, label: 'Min. cash threshold', color: 'var(--status-critical)' }];

    const svg = svgTrendChart({ series: seriesList, width: 640, height: 230, currency, xLabels, refLines });
    chartHtml = svg ? `
      <div class="chart-wrap">${svg}</div>
      <div class="chart-legend">
        <span class="chart-legend__item"><span class="chart-legend__swatch" style="background:var(--chart-blue);"></span>Actual</span>
        <span class="chart-legend__item"><span class="chart-legend__swatch chart-legend__swatch--dashed" style="color:var(--chart-orange);"></span>Forecast</span>
        ${projection.cash_out_month ? `<span class="chart-legend__item"><span class="chart-legend__swatch" style="background:var(--status-critical);"></span>Projected cash-out</span>` : ''}
      </div>` : `<p class="sim-empty">Not enough data yet to chart cash forward.</p>`;
  }

  const outNote = projection.cash_out_month
    ? `<p class="alert alert--warn" style="margin-top:10px;"><span class="alert__dot"></span><span>Projected to run out of cash around month ${projection.cash_out_month} at the current trajectory.</span></p>`
    : (forecastSeries.length ? `<p class="chat-note" style="padding:0; margin-top:10px;">Cash stays positive across the 12-month projection at the current trajectory.</p>` : '');
  const assumptions = (projection.assumptions || []).map(a => `<li>${escapeHtml(a)}</li>`).join('');

  return `
    ${chartHtml}
    ${outNote}
    ${assumptions ? `<details class="sim-trace" style="margin-top:10px;"><summary>Assumptions</summary><ul>${assumptions}</ul></details>` : ''}`;
}

function renderCashRunwaySection(overview) {
  const currency = overview.currency || '₹';
  const netBurn = (overview.metrics || {}).net_burn;
  return `
    <div class="panel">
      <div class="panel__head"><h3>Cash &amp; Runway</h3></div>
      ${suCashRunwayBlockHtml(overview.history, overview.cash_projection, currency)}
      ${netBurn ? suCalcInfoHtml(netBurn, 'cashrunway') : ''}
    </div>`;
}

/* ---- 3. Revenue Intelligence ---- */
function renderRevenueSection(overview) {
  const currency = overview.currency || '₹';
  const m = overview.metrics || {};
  const history = (overview.history || []).filter(h => h.revenue !== null && h.revenue !== undefined);
  const breakdown = overview.revenue_breakdown || {};

  let trendHtml = `<p class="sim-empty">Not enough revenue history yet to chart a trend.</p>`;
  if (history.length >= 2) {
    const pts = history.map(h => ({ y: h.revenue, tooltip: `${h.date}: ${currency}${fmt(h.revenue)}` }));
    const svg = svgTrendChart({ series: [{ label: 'Revenue', color: 'var(--chart-blue)', points: pts, area: true }], width: 300, height: 140, currency, xLabels: history.map(h => h.date.slice(5)) });
    if (svg) trendHtml = `<div class="chart-wrap">${svg}</div>`;
  }

  let donutHtml = `<p class="sim-empty">No categorized revenue yet — log Hisaab "money in" transactions to see a breakdown.</p>`;
  if (breakdown.items && breakdown.items.length) {
    const d = svgDonutChart(breakdown.items, { currency, size: 132 });
    if (d) donutHtml = `<div class="donut-layout">${d.svg}${d.legendHtml}</div>`;
  }
  const streamsHtml = (breakdown.streams && breakdown.streams.length)
    ? `<div class="chart-legend" style="margin-top:6px;">${breakdown.streams.map(s => `<span class="tag tag--good">${escapeHtml(s)}</span>`).join('')}</div>` : '';

  return `
    <div class="panel">
      <div class="panel__head"><h3>Revenue Intelligence</h3></div>
      ${trendHtml}
      <div style="margin-top:14px;">${donutHtml}${streamsHtml}</div>
      ${suMetricRowHtml(m.revenue_growth)}
      ${suMetricRowHtml(m.breakeven)}
    </div>`;
}

/* ---- 4. Expense Intelligence ---- */
function renderExpenseSection(overview) {
  const currency = overview.currency || '₹';
  const m = overview.metrics || {};
  const breakdown = overview.expense_breakdown || {};

  let donutHtml = `<p class="sim-empty">No expense data yet.</p>`;
  if (breakdown.items && breakdown.items.length) {
    const d = svgDonutChart(breakdown.items, { currency, size: 132 });
    if (d) donutHtml = `<div class="donut-layout">${d.svg}${d.legendHtml}</div>`;
  }
  const growthFlag = (m.expense_growth && m.expense_growth.status === 'actual' && m.expense_growth.value > 10)
    ? `<p class="alert alert--warn" style="margin-top:10px;"><span class="alert__dot"></span><span>Expenses grew ${m.expense_growth.value.toFixed(1)}%/mo — costs are accelerating.</span></p>` : '';

  return `
    <div class="panel">
      <div class="panel__head"><h3>Expense Intelligence</h3></div>
      ${donutHtml}
      ${growthFlag}
      ${suMetricRowHtml(m.gross_burn)}
      ${suMetricRowHtml(m.expense_growth)}
      ${suHiringCapacityRow(overview.hiring_capacity)}
    </div>`;
}

function suHiringCapacityRow(hc) {
  if (!hc || hc.status === 'insufficient_data') {
    return `<div class="metric-row">
      <div class="metric-row__main"><span class="metric-row__label">Hiring Capacity</span><span class="status-chip status-chip--insufficient_data">Insufficient data</span></div>
      <p class="chat-note" style="padding:0; margin-top:4px;">Set Cost per Hire on your profile to see how many hires you can sustainably make.</p>
    </div>`;
  }
  return `
    <div class="metric-row">
      <div class="metric-row__main">
        <span class="metric-row__label">Hiring Capacity</span>
        <span class="status-chip status-chip--${hc.status}">${suStatusLabel(hc.status)}</span>
      </div>
      <div class="metric-row__value">${hc.max_sustainable_hires} more hire(s) sustainable, keeping a 6-month runway floor</div>
      <p class="chat-note" style="padding:0; margin-top:4px;">Each additional hire costs about ${hc.runway_lost_per_hire != null ? hc.runway_lost_per_hire.toFixed(1) : '?'} month(s) of runway.</p>
    </div>`;
}

/* ---- 5. Goals ---- */
function suGoalStatusColor(g) {
  if (g.progress_pct === null || g.progress_pct === undefined) return 'var(--status-neutral)';
  if (g.progress_pct >= 70) return 'var(--status-good)';
  if (g.progress_pct >= 35) return 'var(--status-warning)';
  return 'var(--status-serious)';
}

function suGoalRingCardHtml(g) {
  const currency = '₹';
  const meta = [];
  if (g.current_value !== null && g.current_value !== undefined && g.target_value) meta.push(`${currency}${fmt(g.current_value)} / ${currency}${fmt(g.target_value)}`);
  else if (g.target_value) meta.push(`Target: ${currency}${fmt(g.target_value)}`);
  if (g.target_date) meta.push(`Due ${g.target_date}`);
  if (g.expected_completion_date) meta.push(`Est. ${g.expected_completion_date}`);
  return `
    <div class="goal-ring-card">
      ${svgProgressRing(g.progress_pct, { size: 96, color: suGoalStatusColor(g), strokeW: 8 })}
      <span class="goal-ring-card__label">${escapeHtml(g.label)}</span>
      ${meta.length ? `<span class="goal-ring-card__meta">${meta.map(escapeHtml).join(' · ')}</span>` : ''}
      ${(g.note || g.projection_note) ? `<span class="goal-ring-card__note">${escapeHtml(g.note || g.projection_note)}</span>` : ''}
    </div>`;
}

function renderGoalsSection(overview) {
  const goals = overview.goals || [];
  return `
    <div class="panel">
      <div class="panel__head"><h3>Goals</h3></div>
      <div class="goal-ring-grid">${goals.map(suGoalRingCardHtml).join('') || '<p class="sim-empty">No goals set yet.</p>'}</div>
    </div>`;
}

function suDailyBriefHtml(brief) {
  if (!brief || !brief.bullets || !brief.bullets.length) return '<p class="sim-empty">No brief available yet.</p>';
  return `<ul class="brief-list">${brief.bullets.map(b => `<li>${escapeHtml(b)}</li>`).join('')}</ul>`;
}

function renderStartupOverviewExtra(overview) {
  const container = document.getElementById('startupOverviewExtra');
  if (!container) return;

  container.innerHTML = `
    ${renderHealthSection(overview)}
    <div style="margin-top:16px;">${renderCashRunwaySection(overview)}</div>
    <div class="startup-extra-grid" style="margin-top:16px;">
      ${renderRevenueSection(overview)}
      ${renderExpenseSection(overview)}
    </div>
    <div style="margin-top:16px;">${renderGoalsSection(overview)}</div>
    <div class="panel" style="margin-top:16px;">
      <div class="panel__head"><h3>Daily Financial Brief</h3></div>
      ${suDailyBriefHtml(overview.daily_brief)}
    </div>`;

  attachCalcInfoToggles(container);
}

/* ---- 6 & 7. Risk Alerts + Recent Decisions ---- */
const SEVERITY_LABEL = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' };

function suAlertCardHtml(a) {
  const sev = a.severity || (a.level === 'warn' ? 'medium' : 'low');
  return `
    <div class="alert-card">
      <span class="alert-card__badge alert-card__badge--${sev}">${SEVERITY_LABEL[sev] || sev}</span>
      <div class="alert-card__body">
        ${a.metric ? `<div class="alert-card__metric">${escapeHtml(a.metric.replace(/_/g, ' '))}</div>` : ''}
        <div class="alert-card__text">${escapeHtml(a.text)}</div>
      </div>
    </div>`;
}

function suDecisionCardHtml(d) {
  const p = d.predicted || {};
  const a = d.actual_now || {};
  const status = d.decision_status || 'unknown';
  const statusLabel = { on_track: 'Actual ≥ predicted', diverged: 'Actual worse than predicted', pending: 'Pending', unknown: 'Not comparable' }[status] || status;
  return `
    <div class="decision-card">
      <div class="decision-card__head">
        <span class="decision-card__title">${escapeHtml(d.title)}</span>
        <span class="decision-status decision-status--${status}">${escapeHtml(statusLabel)}</span>
      </div>
      <div class="decision-card__row">
        ${p.runway_after !== null && p.runway_after !== undefined ? `<span>Predicted runway: <b>${p.runway_after.toFixed(1)} mo</b></span>` : ''}
        ${a.runway !== null && a.runway !== undefined ? `<span>Runway now: <b>${a.runway.toFixed(1)} mo</b></span>` : ''}
        ${p.financial_health_after !== null && p.financial_health_after !== undefined ? `<span>Predicted health: <b>${p.financial_health_after.toFixed(0)}</b></span>` : ''}
        ${a.financial_health !== null && a.financial_health !== undefined ? `<span>Health now: <b>${a.financial_health.toFixed(0)}</b></span>` : ''}
      </div>
      <p class="decision-list__date" style="margin-top:8px;">${new Date(d.created_at).toLocaleDateString()}${d.outcome ? ' · ' + escapeHtml(d.outcome) : ''}</p>
    </div>`;
}

function renderStartupHistoryAndAlerts(overview) {
  const historyTitle = document.getElementById('historyPanelTitle');
  const alertTitle = document.getElementById('alertPanelTitle');
  if (historyTitle) historyTitle.textContent = 'Recent decisions';
  if (alertTitle) alertTitle.textContent = 'Risk alerts';

  const decisions = overview.recent_decisions || [];
  document.getElementById('historyList').innerHTML = `<div class="decision-card-grid">${
    decisions.length ? decisions.map(suDecisionCardHtml).join('') : '<p class="empty-row">No decisions logged yet — try Simulate.</p>'
  }</div>`;

  const alerts = overview.alerts || [];
  document.getElementById('alertList').innerHTML = `<div class="alert-severity-grid">${
    alerts.length ? alerts.map(suAlertCardHtml).join('') : '<p class="empty-row">No active alerts.</p>'
  }</div>`;
}

async function loadStartupOverviewAndRender() {
  try {
    const overview = await window.api.fetchStartupOverview();
    window.startupState.overview = overview;
    renderStartupPersonaStrip(overview);
    renderStartupStatGrid(overview);
    renderStartupOverviewExtra(overview);
    renderStartupHistoryAndAlerts(overview);
  } catch (e) {
    console.error(e);
  }
}

/* ============ Hisaab ============ */
async function loadHisaabAndRender() {
  const summaryEl = document.getElementById('hisaabSummary');
  if (!summaryEl) return;
  summaryEl.innerHTML = '<p class="sim-empty">Loading…</p>';
  try {
    const data = await window.api.fetchStartupHisaab();
    window.startupState.hisaab = data;
    renderHisaab(data);
  } catch (e) {
    summaryEl.innerHTML = '<p class="sim-empty">Failed to load Hisaab.</p>';
  }
}

function renderHisaab(data) {
  const currency = data.currency || '₹';
  const summaryEl = document.getElementById('hisaabSummary');
  summaryEl.innerHTML = `
    <div class="stat-grid">
      <div class="stat-card"><span class="stat-card__label">Money in</span><span class="stat-card__value">${currency}${fmt(data.money_in)}</span></div>
      <div class="stat-card"><span class="stat-card__label">Money out</span><span class="stat-card__value">${currency}${fmt(data.money_out)}</span></div>
      <div class="stat-card"><span class="stat-card__label">Net</span><span class="stat-card__value">${currency}${fmt(data.net)}</span></div>
    </div>
    ${(data.by_category && data.by_category.length) ? `
    <div class="panel" style="margin-top:16px;">
      <div class="panel__head"><h3>By category</h3></div>
      <ul class="hisaab-cat-list">${data.by_category.map(c => `
        <li><span>${escapeHtml(c.category)} <span class="tag tag--${c.type === 'in' ? 'good' : 'warn'}">${c.type}</span></span><b>${currency}${fmt(c.amount)}</b></li>`).join('')}</ul>
    </div>` : ''}`;

  const txns = data.transactions || [];
  document.getElementById('hisaabList').innerHTML = txns.length ? txns.map(t => `
    <li class="hisaab-row">
      <div>
        <p class="decision-list__title">${escapeHtml(t.category)}${t.description ? ' — ' + escapeHtml(t.description) : ''}</p>
        <p class="decision-list__date">${t.txn_date}</p>
      </div>
      <span class="hisaab-row__amount hisaab-row__amount--${t.type}">${t.type === 'in' ? '+' : '−'}${currency}${fmt(t.amount)}</span>
    </li>`).join('') : '<li class="empty-row">No transactions logged yet.</li>';
}

const hisaabFormEl = document.getElementById('hisaabForm');
if (hisaabFormEl) {
  hisaabFormEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = hisaabFormEl.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const amount = Number(document.getElementById('hxAmount').value);
      await window.api.addStartupTransaction({
        type: document.getElementById('hxType').value,
        category: document.getElementById('hxCategory').value.trim(),
        amount: amount,
        description: document.getElementById('hxDescription').value.trim() || null
      });
      document.getElementById('hxCategory').value = '';
      document.getElementById('hxAmount').value = '';
      document.getElementById('hxDescription').value = '';
      await loadHisaabAndRender();
    } catch (err) {
      alert('Failed to add transaction: ' + (err.message || 'please try again.'));
    }
    btn.disabled = false;
  });
}

/* ============ Alerts ============ */
async function renderAlertsView() {
  const el = document.getElementById('alertsFullList');
  if (!el) return;
  el.innerHTML = '<li class="empty-row">Loading…</li>';
  try {
    const overview = await window.api.fetchStartupOverview();
    window.startupState.overview = overview;
    const alerts = overview.alerts || [];
    el.innerHTML = alerts.length ? alerts.map(a => `
      <li class="alert alert--${a.level}">
        <span class="alert__dot"></span>
        <p><span class="tag tag--${a.level === 'warn' ? 'warn' : 'good'}" style="margin-right:8px;">${escapeHtml(a.category)}</span>${escapeHtml(a.text)}</p>
      </li>`).join('') : '<li class="empty-row">No active alerts — everything looks healthy.</li>';
  } catch (e) {
    el.innerHTML = '<li class="empty-row">Failed to load alerts.</li>';
  }
}

/* ============ Reports ============ */
function suWeeklyReportHtml(report) {
  if (!report || !report.points || !report.points.length) {
    return `<p class="sim-empty">${escapeHtml((report && report.note) || 'No tracking history yet for this week.')}</p>`;
  }
  const rows = report.points.map(p => `
    <div class="timeline-step">
      <div class="timeline-step__dot"></div>
      <div class="timeline-step__label">${p.date}</div>
      <div class="timeline-step__body">
        <div class="timeline-step__row"><span>Cash:</span><b>${p.cash != null ? '₹' + fmt(p.cash) : '—'}</b></div>
        <div class="timeline-step__row"><span>Net burn:</span><b>${p.net_burn != null ? '₹' + fmt(p.net_burn) : '—'}</b></div>
        <div class="timeline-step__row"><span>Runway:</span><b>${p.runway_months != null ? p.runway_months.toFixed(1) + ' mo' : '—'}</b></div>
        <div class="timeline-step__row"><span>Health:</span><b>${p.financial_health_score != null ? p.financial_health_score.toFixed(0) : '—'}</b></div>
      </div>
    </div>`).join('');

  const noteHtml = report.note ? `<p class="chat-note" style="padding:0; margin-bottom:12px;">${escapeHtml(report.note)}</p>` : '';
  const deltaBits = [];
  if (report.health_delta !== null && report.health_delta !== undefined) deltaBits.push(`Health ${report.health_delta >= 0 ? '+' : ''}${report.health_delta.toFixed(1)}`);
  if (report.runway_delta !== null && report.runway_delta !== undefined) deltaBits.push(`Runway ${report.runway_delta >= 0 ? '+' : ''}${report.runway_delta.toFixed(1)} mo`);
  if (report.cash_delta !== null && report.cash_delta !== undefined) deltaBits.push(`Cash ${report.cash_delta >= 0 ? '+' : ''}₹${fmt(report.cash_delta)}`);
  const deltaHtml = deltaBits.length ? `<p class="sim-scenario-text" style="font-size:14px;">Week-over-week: ${deltaBits.join(' · ')}</p>` : '';
  return `${noteHtml}${deltaHtml}<div class="sim-timeline">${rows}</div>`;
}

async function loadWeeklyReport() {
  const el = document.getElementById('weeklyReport');
  if (!el) return;
  el.innerHTML = '<p class="sim-empty">Loading…</p>';
  try {
    const report = await window.api.fetchWeeklyReport();
    el.innerHTML = suWeeklyReportHtml(report);
  } catch (e) {
    el.innerHTML = '<p class="sim-empty">Failed to load weekly report.</p>';
  }
}

async function renderReportsView() {
  const briefEl = document.getElementById('dailyBriefFull');
  if (briefEl) {
    try {
      const overview = window.startupState.overview || await window.api.fetchStartupOverview();
      window.startupState.overview = overview;
      briefEl.innerHTML = suDailyBriefHtml(overview.daily_brief);
    } catch (e) {
      briefEl.innerHTML = '<p class="sim-empty">Failed to load daily brief.</p>';
    }
  }
  await loadWeeklyReport();
}

const btnRefreshWeeklyEl = document.getElementById('btnRefreshWeekly');
if (btnRefreshWeeklyEl) {
  btnRefreshWeeklyEl.addEventListener('click', loadWeeklyReport);
}

/* ==========================================================================
   Simulate — visual rebuild. "Show the insight visually first, then let
   Tathya explain it": Scenario Summary -> Before/After -> Impact Flow ->
   Projection chart -> Comparison -> Recommendation. Every number here comes
   straight from financial_impact / timeline_series / comparison_variants,
   which the backend already computed — this file only draws them.
   ========================================================================== */

function suDeltaClass(before, after, goodDirection) {
  if (before === null || before === undefined || after === null || after === undefined) return 'flat';
  const diff = after - before;
  if (Math.abs(diff) < 1e-9) return 'flat';
  const improved = goodDirection === 'up' ? diff > 0 : diff < 0;
  return improved ? 'good' : 'bad';
}

function suCompareCard(label, before, after, formatFn, goodDirection) {
  const cls = suDeltaClass(before, after, goodDirection);
  const hasBoth = before !== null && before !== undefined && after !== null && after !== undefined;
  const deltaTxt = hasBoth
    ? (Math.abs(after - before) < 1e-9 ? 'No change' : (after >= before ? '+' : '') + formatFn(after - before))
    : '';
  return `
    <div class="compare-card">
      <span class="compare-card__label">${escapeHtml(label)}</span>
      <div class="compare-card__values">
        <span class="compare-card__before">${before === null || before === undefined ? '—' : formatFn(before)}</span>
        <span class="compare-card__after">${after === null || after === undefined ? '—' : formatFn(after)}</span>
      </div>
      ${deltaTxt ? `<span class="compare-card__delta compare-card__delta--${cls}">${deltaTxt}</span>` : ''}
    </div>`;
}

function suScenarioSummaryHtml(res, currency) {
  const impact = res.financial_impact || {};
  const row = (label, before, after, fmtFn) => `<div class="sim-summary-card__row"><span>${escapeHtml(label)}</span><b>${before !== null && before !== undefined ? fmtFn : '—'}</b></div>`;
  const money = v => v === null || v === undefined ? '—' : currency + fmt(v);
  const mo = v => v === null || v === undefined ? '—' : v.toFixed(1) + ' mo';
  const assumptionsHtml = (res.assumptions || []).map(a => `<li class="alert alert--info"><span class="alert__dot"></span><p>${escapeHtml(a)}</p></li>`).join('');

  return `
    <div class="sim-summary-grid">
      <div class="sim-summary-card">
        <span class="sim-summary-card__label">Current baseline</span>
        <div class="sim-summary-card__rows">
          <div class="sim-summary-card__row"><span>Cash</span><b>${money(impact.cash_before)}</b></div>
          <div class="sim-summary-card__row"><span>Monthly burn</span><b>${money(impact.net_burn_before)}</b></div>
          <div class="sim-summary-card__row"><span>Runway</span><b>${mo(impact.runway_before)}</b></div>
          <div class="sim-summary-card__row"><span>Revenue</span><b>${money(impact.revenue_before)}</b></div>
        </div>
      </div>
      <div class="sim-summary-card">
        <span class="sim-summary-card__label">Projected scenario</span>
        <div class="sim-summary-card__rows">
          <div class="sim-summary-card__row"><span>Cash</span><b>${money(impact.cash_after)}</b></div>
          <div class="sim-summary-card__row"><span>Monthly burn</span><b>${money(impact.net_burn_after)}</b></div>
          <div class="sim-summary-card__row"><span>Runway</span><b>${mo(impact.runway_after)}</b></div>
          <div class="sim-summary-card__row"><span>Revenue</span><b>${money(impact.revenue_after)}</b></div>
        </div>
      </div>
    </div>
    ${assumptionsHtml ? `<div class="sim-section"><h4 class="sim-section__title">Scenario assumptions</h4><ul class="alert-list">${assumptionsHtml}</ul></div>` : ''}`;
}

function suBeforeAfterHtml(res, currency) {
  const impact = res.financial_impact || {};
  const goalImpact = impact.goal_impact || [];
  const beforeAvg = goalImpact.length ? goalImpact.reduce((s, g) => s + (g.progress_before_pct || 0), 0) / goalImpact.length : null;
  const afterAvg = goalImpact.length ? goalImpact.reduce((s, g) => s + (g.progress_after_pct || 0), 0) / goalImpact.length : null;

  const cards = [
    suCompareCard('Cash', impact.cash_before, impact.cash_after, v => currency + fmt(v), 'up'),
    suCompareCard('Monthly Burn', impact.net_burn_before, impact.net_burn_after, v => currency + fmt(v), 'down'),
    suCompareCard('Runway', impact.runway_before, impact.runway_after, v => v.toFixed(1) + ' mo', 'up'),
    suCompareCard('Revenue', impact.revenue_before, impact.revenue_after, v => currency + fmt(v), 'up'),
    suCompareCard('Financial Health', impact.financial_health_before, impact.financial_health_after, v => v.toFixed(0) + '/100', 'up'),
  ];
  if (goalImpact.length) cards.push(suCompareCard('Goal Progress (avg)', beforeAvg, afterAvg, v => v.toFixed(0) + '%', 'up'));
  const riskCount = (res.risks || []).filter(r => r !== 'No material risks identified from the available data.').length;
  cards.push(suCompareCard('Risk flags', 0, riskCount, v => Math.round(v) + ' flag' + (Math.round(v) === 1 ? '' : 's'), 'down'));

  return `<div class="sim-section"><h4 class="sim-section__title">Before vs After</h4><div class="compare-grid">${cards.join('')}</div></div>`;
}

function suImpactFlowHtml(res, currency) {
  const impact = res.financial_impact || {};
  if (impact.net_burn_before == null || impact.net_burn_after == null) return '';
  const nodes = [{ label: 'Decision', value: (res.scenario_type || '').replace(/_/g, ' ') || 'Scenario', cls: '' }];

  const burnDelta = impact.net_burn_after - impact.net_burn_before;
  nodes.push({ label: 'Burn Impact', value: `${burnDelta >= 0 ? '+' : ''}${currency}${fmt(burnDelta)}/mo`, cls: burnDelta > 0 ? 'bad' : (burnDelta < 0 ? 'good' : '') });

  if (impact.cash_after != null && impact.cash_before != null) {
    const cashDelta = impact.cash_after - impact.cash_before;
    nodes.push({ label: 'Cash Impact', value: `${cashDelta >= 0 ? '+' : ''}${currency}${fmt(cashDelta)}`, cls: cashDelta >= 0 ? 'good' : 'bad' });
  }
  if (impact.runway_after != null && impact.runway_before != null) {
    const runwayDelta = impact.runway_after - impact.runway_before;
    nodes.push({ label: 'Runway Impact', value: `${runwayDelta >= 0 ? '+' : ''}${runwayDelta.toFixed(1)} mo`, cls: runwayDelta >= 0 ? 'good' : 'bad' });
  }
  const riskCount = (res.risks || []).filter(r => r !== 'No material risks identified from the available data.').length;
  nodes.push({ label: 'Goal / Risk Impact', value: `${riskCount} risk flag${riskCount === 1 ? '' : 's'}`, cls: riskCount > 0 ? 'bad' : 'good' });

  const flowHtml = nodes.map((n, i) => `
    ${i > 0 ? '<span class="impact-flow__arrow">→</span>' : ''}
    <div class="impact-flow__node">
      <div class="impact-flow__node-label">${escapeHtml(n.label)}</div>
      <div class="impact-flow__node-value${n.cls ? ' impact-flow__node-value--' + n.cls : ''}">${escapeHtml(n.value)}</div>
    </div>`).join('');
  return `<div class="sim-section"><h4 class="sim-section__title">Scenario Impact Flow</h4><div class="impact-flow">${flowHtml}</div></div>`;
}

function suRenderProjectionChart(ts, currency, months) {
  const baseline = (ts.baseline || []).slice(0, months);
  const scenario = (ts.scenario || []).slice(0, months);
  const len = Math.max(baseline.length, scenario.length);
  const baselinePts = [], scenarioPts = [];
  for (let i = 0; i < len; i++) {
    const b = baseline[i], s = scenario[i];
    baselinePts.push({ y: b ? b.projected_cash : null, tooltip: b ? `Month ${b.month} — baseline: ${currency}${fmt(b.projected_cash)}` : undefined });
    scenarioPts.push({ y: s ? s.projected_cash : null, tooltip: s ? `Month ${s.month} — scenario: ${currency}${fmt(s.projected_cash)}` : undefined });
  }
  const xLabels = [];
  for (let i = 0; i < len; i++) xLabels.push(`+${i + 1}mo`);
  const svg = svgTrendChart({
    series: [
      { label: 'Baseline', color: 'var(--chart-blue)', points: baselinePts },
      { label: 'Scenario', color: 'var(--chart-orange)', dashed: true, points: scenarioPts },
    ], width: 640, height: 220, currency, xLabels,
  });
  if (!svg) return '<p class="sim-empty">Not enough projection data.</p>';
  return `<div class="chart-wrap">${svg}</div>
    <div class="chart-legend">
      <span class="chart-legend__item"><span class="chart-legend__swatch" style="background:var(--chart-blue);"></span>Baseline (no change)</span>
      <span class="chart-legend__item"><span class="chart-legend__swatch chart-legend__swatch--dashed" style="color:var(--chart-orange);"></span>Scenario</span>
    </div>`;
}

function suScenarioProjectionHtml(res, currency) {
  const ts = res.timeline_series;
  if (!ts || (!(ts.baseline || []).length && !(ts.scenario || []).length)) return '';
  const maxLen = Math.max((ts.baseline || []).length, (ts.scenario || []).length);
  const periods = [3, 6, 12].filter(p => p <= maxLen);
  if (!periods.length) periods.push(maxLen);
  window._suProjData = { ts, currency };
  const initial = periods[periods.length - 1];
  return `
    <div class="sim-section">
      <h4 class="sim-section__title">Scenario Projection</h4>
      <div class="sim-chip-row" id="simProjPeriods">
        ${periods.map(p => `<button type="button" class="chip${p === initial ? ' is-active' : ''}" data-months="${p}">${p} months</button>`).join('')}
      </div>
      <div id="simProjChart">${suRenderProjectionChart(ts, currency, initial)}</div>
    </div>`;
}

function suComparisonTableHtml(res, currency) {
  const variants = res.comparison_variants;
  if (!variants || !variants.length) return '';
  const rows = variants.map(v => `
    <tr class="${v.is_recommended ? 'is-recommended' : ''}">
      <td>${escapeHtml(v.label)}${v.is_recommended ? '<span class="variant-table__badge">Recommended</span>' : ''}</td>
      <td>${v.cash_after != null ? currency + fmt(v.cash_after) : '—'}</td>
      <td>${v.net_burn_after != null ? currency + fmt(v.net_burn_after) : '—'}</td>
      <td>${v.runway_after != null ? v.runway_after.toFixed(1) + ' mo' : '—'}</td>
      <td>${v.revenue_after != null ? currency + fmt(v.revenue_after) : '—'}</td>
      <td>${v.goal_progress_avg_after != null ? v.goal_progress_avg_after.toFixed(0) + '%' : '—'}</td>
      <td>${v.risk_count}</td>
    </tr>`).join('');
  return `
    <div class="sim-section">
      <h4 class="sim-section__title">Scenario Comparison</h4>
      <div style="overflow-x:auto;">
        <table class="variant-table">
          <thead><tr><th>Option</th><th>Cash</th><th>Burn</th><th>Runway</th><th>Revenue</th><th>Goals</th><th>Risks</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function suMainBenefit(res, currency) {
  const impact = res.financial_impact || {};
  const bits = [];
  if (impact.runway_after != null && impact.runway_before != null && impact.runway_after > impact.runway_before) bits.push(`Runway extends by ${(impact.runway_after - impact.runway_before).toFixed(1)} months.`);
  if (impact.financial_health_after != null && impact.financial_health_before != null && impact.financial_health_after > impact.financial_health_before) bits.push(`Financial Health improves by ${(impact.financial_health_after - impact.financial_health_before).toFixed(0)} points.`);
  if (impact.cash_after != null && impact.cash_before != null && impact.cash_after > impact.cash_before) bits.push(`Cash position increases by ${currency}${fmt(impact.cash_after - impact.cash_before)}.`);
  return bits[0] || 'See the recommendation above.';
}

function suRecommendationCardHtml(res, currency) {
  const mainRisk = (res.risks && res.risks[0] && res.risks[0] !== 'No material risks identified from the available data.') ? res.risks[0] : 'No material risk identified from the available data.';
  return `
    <div class="recommend-card">
      <span class="recommend-card__icon">✅</span>
      <div class="recommend-card__body">
        <h4>${escapeHtml(res.recommendation)}</h4>
        <p>${escapeHtml(res.why)}</p>
        <div class="recommend-card__grid">
          <div class="recommend-card__grid-item"><b>Main benefit</b>${escapeHtml(suMainBenefit(res, currency))}</div>
          <div class="recommend-card__grid-item"><b>Main risk</b>${escapeHtml(mainRisk)}</div>
        </div>
      </div>
    </div>`;
}

function renderStartupSimulationResult(res) {
  const currency = (profile() && profile().currency) || '₹';
  const isInformational = res.mode === 'informational';
  const el = document.getElementById('simResults');

  if (isInformational) {
    const answerHtml = (typeof marked !== 'undefined') ? marked.parse(res.recommendation || '') : `<p>${escapeHtml(res.recommendation)}</p>`;
    el.innerHTML = `
      <div class="panel__head"><h3>Scenario</h3></div>
      <p class="sim-scenario-text">“${escapeHtml(res.scenario)}”</p>
      <div class="explanation"><span class="explanation__label">Twin's answer</span>${answerHtml}</div>
      <p class="chat-note" style="padding:0; margin-top:14px;">${escapeHtml(res.disclaimer)}</p>`;
    return;
  }

  const traceHtml = (res.stages || []).map(s => `<li><b>${escapeHtml(s.agent)}:</b> ${escapeHtml(s.summary)}</li>`).join('');
  const materialRisks = (res.risks || []).filter(r => r !== 'No material risks identified from the available data.');
  const risksHtml = materialRisks.length ? `
    <div class="sim-section"><h4 class="sim-section__title">Risks / what to watch</h4><ul class="alert-list">${materialRisks.map(r => `<li class="alert alert--warn"><span class="alert__dot"></span><p>${escapeHtml(r)}</p></li>`).join('')}</ul></div>` : '';
  const teachingHtml = res.teaching ? `<div class="explanation"><span class="explanation__label">Teach agent explains</span><p>${escapeHtml(res.teaching)}</p></div>` : '';

  el.innerHTML = `
    <div class="panel__head"><h3>Scenario</h3></div>
    <p class="sim-scenario-text">“${escapeHtml(res.scenario)}”</p>
    ${suScenarioSummaryHtml(res, currency)}
    ${suBeforeAfterHtml(res, currency)}
    ${suImpactFlowHtml(res, currency)}
    ${suScenarioProjectionHtml(res, currency)}
    ${suComparisonTableHtml(res, currency)}
    <div class="sim-section"><h4 class="sim-section__title">Tathya's recommendation</h4>${suRecommendationCardHtml(res, currency)}</div>
    ${risksHtml}
    ${teachingHtml}
    <details class="sim-trace"><summary>How this was computed</summary><ul>${traceHtml}</ul></details>
    <p class="chat-note" style="padding:0; margin-top:14px;">${escapeHtml(res.disclaimer)}</p>`;

  const periodRow = document.getElementById('simProjPeriods');
  if (periodRow && window._suProjData) {
    periodRow.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        periodRow.querySelectorAll('.chip').forEach(c => c.classList.remove('is-active'));
        chip.classList.add('is-active');
        const months = Number(chip.dataset.months);
        document.getElementById('simProjChart').innerHTML = suRenderProjectionChart(window._suProjData.ts, window._suProjData.currency, months);
      });
    });
  }
}

/* ==========================================================================
   Ask Twin — inline visualizations. Deterministic keyword routing on the
   backend decides *whether* to attach a chart; this only draws whatever
   payload came back (cash_runway / expense_breakdown / revenue_goals).
   ========================================================================== */

function suChatVizHtml(viz) {
  if (!viz) return '';
  const currency = '₹';

  if (viz.type === 'cash_runway') {
    return `
      <div class="chat-viz">
        <div class="chat-viz__title">Cash &amp; Runway</div>
        ${suCashRunwayBlockHtml(viz.history, viz.projection, currency)}
      </div>`;
  }

  if (viz.type === 'expense_breakdown') {
    const breakdown = viz.breakdown || {};
    let donutHtml = '<p class="sim-empty">No expense data yet.</p>';
    if (breakdown.items && breakdown.items.length) {
      const d = svgDonutChart(breakdown.items, { currency, size: 120 });
      if (d) donutHtml = `<div class="donut-layout">${d.svg}${d.legendHtml}</div>`;
    }
    const growth = viz.expense_growth;
    const growthHtml = growth ? `<p class="chat-note" style="padding:0; margin-top:8px;">${escapeHtml(growth.label)}: ${escapeHtml(growth.display)}</p>` : '';
    return `<div class="chat-viz"><div class="chat-viz__title">Expense Breakdown</div>${donutHtml}${growthHtml}</div>`;
  }

  if (viz.type === 'revenue_goals') {
    const history = (viz.history || []).filter(h => h.revenue !== null && h.revenue !== undefined);
    let trendHtml = '<p class="sim-empty">Not enough revenue history yet to chart a trend.</p>';
    if (history.length >= 2) {
      const pts = history.map(h => ({ y: h.revenue, tooltip: `${h.date}: ${currency}${fmt(h.revenue)}` }));
      const svg = svgTrendChart({ series: [{ label: 'Revenue', color: 'var(--chart-blue)', points: pts, area: true }], width: 420, height: 140, currency, xLabels: history.map(h => h.date.slice(5)) });
      if (svg) trendHtml = `<div class="chart-wrap">${svg}</div>`;
    }
    const goals = (viz.goals || []).slice(0, 3);
    const goalsHtml = goals.length ? `<div class="goal-ring-grid" style="margin-top:10px;">${goals.map(suGoalRingCardHtml).join('')}</div>` : '';
    return `<div class="chat-viz"><div class="chat-viz__title">Revenue &amp; Goals</div>${trendHtml}${goalsHtml}</div>`;
  }

  return '';
}

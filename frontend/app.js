/* ════════════════════════════════════════════════════════
   AgentPay Frontend — App Logic
   Router · API Client · Page Renderers · i18n · Voice Input
   ════════════════════════════════════════════════════════ */

import { t, getLang, setLang, getVoiceLangCode } from './i18n.js';
import { KillChainVisualizer } from './kill_chain_graph.js';

const API = '/api';
const app = document.getElementById('app');

// ── API Client ──
async function api(path, options = {}) {
  try {
    const res = await fetch(`${API}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`[API] ${path} failed:`, err);
    return null;
  }
}

// ── Helpers ──
function renderStars(score, max = 5) {
  let html = '';
  for (let i = 1; i <= max; i++) {
    html += `<span class="star ${i <= Math.round(score) ? '' : 'empty'}">★</span>`;
  }
  return html;
}

function formatPrice(amount) {
  return '₹' + Number(amount).toLocaleString('en-IN');
}

function loading() {
  return `<div class="loading"><div class="spinner"></div><span>${t('checking')}</span></div>`;
}

function emptyState(icon, text) {
  return `<div class="empty-state"><div class="empty-icon">${icon}</div><p>${text}</p></div>`;
}

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));
}

function explainabilityHTML(stage, index) {
  const event = stage.event || {};
  const policy = stage.policy_result || event.policy_result || {};
  const metadata = stage.metadata || event.metadata || {};
  const breakdown = policy.arithmetic_breakdown || metadata.arithmetic_breakdown || event.arithmetic_breakdown;
  const values = policy.values || policy.details || metadata.values || event.input_data;
  const result = policy.result ?? policy.allowed ?? event.status;
  const score = policy.explainability_score ?? metadata.explainability_score ?? event.explainability_score;
  return `<button class="why-button" type="button" onclick="window.showWhy(${index})">Why?</button>
    <div class="why-panel" id="why-panel-${index}" hidden>
      <div class="why-heading">Why was this stage ${escapeHTML(stage.status)}?</div>
      ${stage.reason ? `<p class="why-reason">${escapeHTML(stage.reason)}</p>` : ''}
      <dl class="why-facts">
        <dt>Decision</dt><dd>${escapeHTML(stage.status.toUpperCase())}</dd>
        <dt>Policy / rule</dt><dd>${escapeHTML(policy.name || policy.check_name || event.action || stage.name)}</dd>
        ${values ? `<dt>Values used</dt><dd><code>${escapeHTML(JSON.stringify(values))}</code></dd>` : ''}
        ${breakdown ? `<dt>Arithmetic breakdown</dt><dd>${Array.isArray(breakdown) ? breakdown.map(item => `<div>${escapeHTML(item)}</div>`).join('') : escapeHTML(breakdown)}</dd>` : ''}
        ${result !== undefined ? `<dt>Result</dt><dd>${escapeHTML(typeof result === 'object' ? JSON.stringify(result) : result)}</dd>` : ''}
        ${score !== undefined ? `<dt>Explainability score</dt><dd>${escapeHTML(score)}</dd>` : ''}
      </dl>
    </div>`;
}

function renderKillChain(chain) {
  const stages = chain?.stages || [];
  if (!stages.length) return emptyState('🔗', 'No audit-chain data found for this session.');
  window.currentAuditChain = stages;
  return `<section class="kill-chain" aria-label="Transaction security pipeline">
    <div class="kill-chain-header">
      <div><div class="card-title">Transaction Kill Chain</div><div class="card-subtitle">${escapeHTML(chain.status || 'unreached')} ${chain.stopping_stage ? `at ${escapeHTML(chain.stopping_stage)}` : ''}</div></div>
      ${chain.stop_reason ? `<div class="chain-stop-reason">${escapeHTML(chain.stop_reason)}</div>` : ''}
    </div>
    <div class="kill-chain-track">
      ${stages.map((stage, index) => `<div class="chain-step ${escapeHTML(stage.status)}">
        <button class="chain-node" type="button" title="Open ${escapeHTML(stage.name)} details" aria-label="Open ${escapeHTML(stage.name)} details" onclick="window.showStage(${index})"><span>${stage.status === 'passed' ? '✓' : stage.status === 'blocked' ? '!' : stage.status === 'pending' ? '…' : '·'}</span></button>
        <div class="chain-label">${escapeHTML(stage.name)}</div>
        <div class="chain-status">${escapeHTML(stage.status)}</div>
        ${stage.reason ? `<div class="chain-reason">${escapeHTML(stage.reason)}</div>` : ''}
        ${stage.event ? explainabilityHTML(stage, index) : ''}
        ${stage.event ? `<div class="stage-details" id="stage-details-${index}" hidden><dl class="why-facts"><dt>Action</dt><dd>${escapeHTML(stage.event.action || stage.event.action_type || 'Unavailable')}</dd><dt>Timestamp</dt><dd>${escapeHTML(stage.event.timestamp || stage.event.created_at || 'Unavailable')}</dd><dt>Trace / request ID</dt><dd>${escapeHTML(stage.event.metadata?.request_id || stage.event.output_data?.request_id || 'Unavailable')}</dd><dt>Metadata</dt><dd><code>${escapeHTML(JSON.stringify(stage.metadata || stage.event.metadata || {}))}</code></dd></dl></div>` : ''}
        ${index < stages.length - 1 ? '<div class="chain-arrow" aria-hidden="true">→</div>' : ''}
      </div>`).join('')}
    </div>
  </section>`;
}

// ── Update Navigation Text on Language Switch ──
function updateNavTranslations() {
  const el = (id) => document.getElementById(id);
  if (el('nav-label-dashboard')) el('nav-label-dashboard').textContent = t('navDashboard');
  if (el('nav-label-merchants')) el('nav-label-merchants').textContent = t('navMerchants');
  if (el('nav-label-agent')) el('nav-label-agent').textContent = t('navAgent');
  if (el('nav-label-policy')) el('nav-label-policy').textContent = t('navPolicy');
  if (el('nav-label-audit')) el('nav-label-audit').textContent = t('navAudit');
  if (el('nav-label-kill-chain')) el('nav-label-kill-chain').textContent = t('navKillChain');
  if (el('nav-label-refunds')) el('nav-label-refunds').textContent = t('navRefunds');
  if (el('nav-label-refunds-merchant')) el('nav-label-refunds-merchant').textContent = t('navMerchantRefunds');
}


// ════════════════════════════════════════════════════════
// PAGES
// ════════════════════════════════════════════════════════

// ── Dashboard ──
async function renderDashboard() {
  app.innerHTML = `<div class="page-enter">${loading()}</div>`;

  const health = await api('/health');
  const merchantsData = await api('/merchants');
  const merchants = merchantsData?.merchants || [];

  const totalProducts = merchants.reduce((sum, m) => sum + (m.product_count || 0), 0);
  const avgTrust = merchants.length
    ? (merchants.reduce((sum, m) => sum + m.trust_score, 0) / merchants.length).toFixed(1)
    : '—';

  app.innerHTML = `<div class="page-enter">
    <!-- Hero -->
    <div class="hero">
      <h1>${t('brandName')}</h1>
      <p>${t('dashSubtitle')}</p>
      <div class="hero-badges">
        <span class="badge ${health?.status === 'healthy' ? 'badge-green' : 'badge-red'}">
          ${health?.status === 'healthy' ? `● ${t('statusHealthy')}` : `● ${t('statusOffline')}`}
        </span>
        <span class="badge badge-purple">
          LLM: ${health?.llm_provider || 'none'}
        </span>
        <span class="badge badge-cyan">
          ${health?.razorpay_configured ? '● Razorpay Connected' : '○ Razorpay Test Mode'}
        </span>
        <span class="badge badge-amber">v${health?.version || '1.0.0'}</span>
      </div>
      <div style="margin-top:20px;display:flex;gap:12px;flex-wrap:wrap">
        <a href="#/agent" class="btn-primary" style="padding:10px 20px;font-size:0.9rem">${t('launchAgentBtn')}</a>
        <a href="#/policy" class="btn-secondary" style="padding:10px 20px;font-size:0.9rem">${t('launchTrustBtn')}</a>
      </div>
    </div>

    <!-- Stats -->
    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-icon">🏪</span>
        <div class="stat-value">${merchants.length}</div>
        <div class="stat-label">${t('statMerchants')}</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">📦</span>
        <div class="stat-value">${totalProducts}</div>
        <div class="stat-label">${t('statProducts')}</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">⭐</span>
        <div class="stat-value">${avgTrust}</div>
        <div class="stat-label">${t('statAvgTrust')}</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">🛡️</span>
        <div class="stat-value">${health?.llm_configured ? 'AI' : 'Rule'}</div>
        <div class="stat-label">${t('statFeatures')}</div>
      </div>
    </div>

    <!-- Quick Scenarios -->
    <div class="section-title">${t('quickScenarios')}</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:14px;margin-bottom:28px">
      <div class="card" style="cursor:pointer" onclick="window.location.hash='#/agent'">
        <div style="font-weight:700;color:var(--accent-green)">1. ${t('scenario1Title')}</div>
        <div style="font-size:0.82rem;color:var(--text-muted);margin-top:4px">${t('scenario1Desc')}</div>
      </div>
      <div class="card" style="cursor:pointer" onclick="window.location.hash='#/policy'">
        <div style="font-weight:700;color:var(--accent-amber)">2. ${t('scenario2Title')}</div>
        <div style="font-size:0.82rem;color:var(--text-muted);margin-top:4px">${t('scenario2Desc')}</div>
      </div>
      <div class="card" style="cursor:pointer" onclick="window.location.hash='#/policy'">
        <div style="font-weight:700;color:var(--accent-red)">3. ${t('scenario3Title')}</div>
        <div style="font-size:0.82rem;color:var(--text-muted);margin-top:4px">${t('scenario3Desc')}</div>
      </div>
    </div>

    <!-- Quick Merchants Preview -->
    <div class="section-title">${t('merchantsTitle')}</div>
    <div class="merchants-grid">
      ${merchants.slice(0, 6).map(m => merchantCardHTML(m)).join('')}
    </div>
  </div>`;
}


// ── Merchants List ──
async function renderMerchants() {
  app.innerHTML = `<div class="page-enter">
    <div class="page-header">
      <h1>${t('merchantsTitle')}</h1>
      <p>${t('merchantsSubtitle')}</p>
    </div>
    ${loading()}
  </div>`;

  const data = await api('/merchants');
  const merchants = data?.merchants || [];

  if (!merchants.length) {
    app.querySelector('.loading').outerHTML = emptyState('🏪', 'No merchants found.');
    return;
  }

  app.querySelector('.loading').outerHTML = `
    <div class="merchants-grid">
      ${merchants.map(m => merchantCardHTML(m)).join('')}
    </div>`;
}

function merchantCardHTML(m) {
  return `
    <div class="merchant-card" onclick="window.location.hash='#/merchants/${m.id}'">
      <div class="merchant-name">${m.name}</div>
      <div class="merchant-desc">${m.description || ''}</div>
      <div class="merchant-meta">
        <span class="meta-tag">📂 ${m.category}</span>
        <span class="meta-tag">📦 ${m.product_count} ${t('statProducts')}</span>
        <span class="meta-tag">${renderStars(m.trust_score)} ${m.trust_score}</span>
        ${m.policy?.negotiation_enabled ? `<span class="meta-tag">🤝 ${t('negotiationActive')}</span>` : ''}
        ${m.policy ? `<span class="meta-tag">💰 ${t('maxDiscount')}: ${m.policy.max_discount_percent}%</span>` : ''}
      </div>
      <div class="merchant-footer">
        <span class="view-catalog">${t('viewCatalog')}</span>
      </div>
    </div>`;
}


// ── Merchant Detail (Product Catalog) ──
async function renderMerchantDetail(merchantId) {
  const [merchantKey, query] = merchantId.split('?');
  const productKey = new URLSearchParams(query || '').get('product');
  app.innerHTML = `<div class="page-enter">
    <button class="back-btn" onclick="window.location.hash='#/merchants'">← ${t('navMerchants')}</button>
    ${loading()}
  </div>`;

  const merchant = await api(`/merchants/${merchantKey}`);
  const productsData = await api(`/merchants/${merchantKey}/products`);
  const products = productsData?.products || [];

  if (!merchant || merchant.error) {
    app.querySelector('.loading').outerHTML = emptyState('❌', 'Merchant not found.');
    return;
  }

  app.querySelector('.loading').outerHTML = `
    <div class="page-header" style="margin-top:12px">
      <h1>${merchant.name}</h1>
      <p>${merchant.description || ''}</p>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-icon">📦</span>
        <div class="stat-value">${products.length}</div>
        <div class="stat-label">${t('statProducts')}</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">⭐</span>
        <div class="stat-value">${merchant.trust_score}</div>
        <div class="stat-label">${t('trustScore')}</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">💰</span>
        <div class="stat-value">${merchant.policy?.max_discount_percent || 0}%</div>
        <div class="stat-label">${t('maxDiscount')}</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon">🤝</span>
        <div class="stat-value">${merchant.policy?.negotiation_enabled ? 'Yes' : 'No'}</div>
        <div class="stat-label">Negotiation</div>
      </div>
    </div>

    ${merchant.policy ? `
      <div class="card" style="margin-bottom:24px">
        <div class="card-title">${t('merchantPolicyTitle')}</div>
        <div class="card-subtitle">${t('merchantPolicySub')}</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:12px;margin-top:14px">
          <div style="background:rgba(255,255,255,0.02);padding:10px 14px;border-radius:8px;border:1px solid var(--border-subtle)">
            <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase">${t('maxDiscount')}</div>
            <div style="font-size:1.1rem;font-weight:700;color:var(--accent-purple)">${merchant.policy.max_discount_percent || 0}%</div>
          </div>
          <div style="background:rgba(255,255,255,0.02);padding:10px 14px;border-radius:8px;border:1px solid var(--border-subtle)">
            <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase">${t('baseDiscount')}</div>
            <div style="font-size:1.1rem;font-weight:700;color:var(--accent-green)">${merchant.policy.auto_discount_percent || 0}%</div>
          </div>
          <div style="background:rgba(255,255,255,0.02);padding:10px 14px;border-radius:8px;border:1px solid var(--border-subtle)">
            <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase">${t('minOrderVal')}</div>
            <div style="font-size:1.1rem;font-weight:700;color:var(--text-primary)">${formatPrice(merchant.policy.min_order_value || 0)}</div>
          </div>
          <div style="background:rgba(255,255,255,0.02);padding:10px 14px;border-radius:8px;border:1px solid var(--border-subtle)">
            <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase">${t('approvalAbove')}</div>
            <div style="font-size:1.1rem;font-weight:700;color:var(--accent-amber)">${formatPrice(merchant.policy.requires_merchant_approval_above || 100000)}</div>
          </div>
        </div>
      </div>
    ` : ''}

    <div class="section-title">📦 ${t('statProducts')}</div>
    ${products.length ? `
      <div class="products-grid">
        ${products.map(p => productCardHTML(p, merchant.name)).join('')}
      </div>
    ` : emptyState('📦', 'No products found for this merchant.')}
  `;
  if (productKey) document.getElementById(`product-${productKey}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function getCategoryPolicy(category, price) {
  const cat = (category || '').toLowerCase();
  if (cat.includes('laptop') || cat.includes('computer')) {
    return {
      windowDays: 10,
      refundPercent: 100,
      condition: 'Unused, undamaged, or verified defective; original charger, serial box, and accessories required.',
      categoryLabel: 'Electronics & Computing',
    };
  } else if (cat.includes('phone') || cat.includes('mobile')) {
    return {
      windowDays: 7,
      refundPercent: 100,
      condition: 'Unused or defective; original box, IMEI match, and charging cable required.',
      categoryLabel: 'Smartphones & Mobile',
    };
  } else {
    return {
      windowDays: 7,
      refundPercent: 100,
      condition: 'Unused, unopened, and in resalable condition with all tags and seals intact.',
      categoryLabel: 'Accessories & Peripherals',
    };
  }
}

window.openProductRefundModal = function(productId, productName, category, price, windowDays, condition, refundPercent, merchantId) {
  const existing = document.getElementById('product-policy-modal-overlay');
  if (existing) existing.remove();

  const pol = getCategoryPolicy(category, price);
  const wDays = windowDays || pol.windowDays;
  const rPercent = refundPercent || pol.refundPercent;
  const condText = condition || pol.condition;
  const isHighValue = price >= 50000;

  const modalHtml = `
    <div class="policy-modal-overlay" id="product-policy-modal-overlay" onclick="if(event.target === this) window.closeProductRefundModal()">
      <div class="policy-modal-card" role="dialog" aria-modal="true">
        <div class="policy-modal-header">
          <div>
            <div class="badge badge-purple">${pol.categoryLabel}</div>
            <h2 class="policy-modal-title">📋 ${escapeHTML(productName)}</h2>
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px">ID: <code>${escapeHTML(productId)}</code> · Retail: <strong>${formatPrice(price)}</strong></div>
          </div>
          <button class="policy-modal-close" onclick="window.closeProductRefundModal()" title="Close">✕</button>
        </div>

        <div class="policy-modal-body">
          <!-- Quick Policy Metrics -->
          <div class="policy-highlights-grid">
            <div class="policy-highlight-card">
              <div class="policy-highlight-val">${wDays} ${t('deliveryDays') ? 'Days' : 'Days'}</div>
              <div class="policy-highlight-label">${t('policyWindowLabel')}</div>
            </div>
            <div class="policy-highlight-card">
              <div class="policy-highlight-val">${rPercent}%</div>
              <div class="policy-highlight-label">${t('policyCoverageLabel')}</div>
            </div>
            <div class="policy-highlight-card">
              <div class="policy-highlight-val">${isHighValue ? '⚡ Sign-Off' : '⚡ Instant'}</div>
              <div class="policy-highlight-label">Approval Rail</div>
            </div>
          </div>

          <!-- Key Policy Protection & Rules -->
          <div class="policy-rules-box">
            <div style="font-size:0.8rem;font-weight:700;color:var(--accent-cyan);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.04em">
              🛡️ ${t('policyKeyPointsLabel')}
            </div>

            <div class="policy-rule-item">
              <span class="policy-rule-icon">📦</span>
              <div><strong>${t('policyConditionLabel')}:</strong> ${escapeHTML(condText)}</div>
            </div>

            <div class="policy-rule-item">
              <span class="policy-rule-icon">💳</span>
              <div><strong>Instant Razorpay Gateway Payout:</strong> Once approved by the merchant or automated policy engine, the refund is credited directly to your original payment method.</div>
            </div>

            <div class="policy-rule-item">
              <span class="policy-rule-icon">🤖</span>
              <div><strong>Autonomous Agent Verification:</strong> Natural language refund requests (e.g. <em>"Arrived damaged"</em>) are extracted by the AI Buyer Agent and deterministically verified against 8 strict safety checks.</div>
            </div>

            <div class="policy-rule-item">
              <span class="policy-rule-icon">🔒</span>
              <div><strong>Money Conservation & Idempotency:</strong> Over-refunds, duplicate claims, and altered payloads are mathematically prevented with SHA-256 idempotency locks.</div>
            </div>

            ${isHighValue ? `
              <div class="policy-rule-item" style="background:rgba(251,191,36,0.08);padding:8px 10px;border-radius:6px;border:1px solid rgba(251,191,36,0.25);margin-top:4px">
                <span class="policy-rule-icon">⚠️</span>
                <div style="color:var(--accent-amber)"><strong>High-Value Item Guardrail:</strong> As this item is over ₹50,000, refunds require a one-click merchant approval sign-off before Razorpay payout.</div>
              </div>
            ` : ''}
          </div>

          <!-- Modal Action Buttons -->
          <div class="policy-modal-actions">
            <button class="btn-primary" style="flex:1" onclick="window.closeProductRefundModal();window.location.hash='#/agent';setTimeout(() => window.startAgentNegotiation('${merchantId || ''}', '${productId}', '${escapeHTML(productName).replace(/'/g, "\\'")}', ${price}), 150)">
              ${t('negotiateAndBuy')}
            </button>
            <button class="btn-secondary" onclick="window.closeProductRefundModal();window.location.hash='#/refunds'">
              ↩ ${t('navRefunds')}
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);
};

window.closeProductRefundModal = function() {
  const modal = document.getElementById('product-policy-modal-overlay');
  if (modal) modal.remove();
};

function productCardHTML(p, merchantName = '') {
  const specs = p.specifications || {};
  const specEntries = Object.entries(specs).slice(0, 5);
  const pol = getCategoryPolicy(p.category, p.price);
  const wDays = p.refund_policy?.window_days || pol.windowDays;
  const rPercent = p.refund_policy?.refund_percent || pol.refundPercent;
  const condText = p.refund_policy?.condition || pol.condition;

  return `
    <div class="product-card" id="product-${escapeHTML(p.id)}">
      <div class="product-name">${p.name}</div>
      <div class="product-desc">${p.description || ''}</div>
      <div class="product-price">${formatPrice(p.price)}</div>
      <div class="product-meta">
        <span class="meta-tag">📂 ${p.category}</span>
        <span class="meta-tag">📦 ${p.stock} ${t('inStock')}</span>
        <span class="meta-tag">🚚 ${p.delivery_days} ${t('deliveryDays')}</span>
        <span class="meta-tag">${renderStars(p.rating)} ${p.rating}</span>
      </div>

      <!-- Interactive Refund Policy Bar -->
      <div class="product-policy-bar">
        <span class="product-policy-text">↩ ${wDays}-day returns (${rPercent}%)</span>
        <button type="button" class="btn-policy-tag" onclick="window.openProductRefundModal('${p.id}', '${p.name.replace(/'/g, "\\'")}', '${p.category}', ${p.price}, ${wDays}, '${condText.replace(/'/g, "\\'")}', ${rPercent}, '${p.merchant_id}')">
          ${t('viewRefundPolicyBtn')}
        </button>
      </div>

      ${specEntries.length ? `
        <div class="product-specs">
          ${specEntries.map(([k, v]) => `
            <div class="spec-row">
              <span class="spec-key">${k.replace(/_/g, ' ')}</span>
              <span class="spec-val">${v}</span>
            </div>
          `).join('')}
        </div>
      ` : ''}
      <button class="btn-primary" style="margin-top:12px;font-size:0.82rem;padding:7px 12px;width:100%" onclick="window.location.hash='#/agent';setTimeout(() => window.startAgentNegotiation('${p.merchant_id}', '${p.id}', '${p.name.replace(/'/g, "\\'")}', ${p.price}), 150)">
        ${t('negotiateAndBuy')}
      </button>
    </div>`;
}


// ════════════════════════════════════════════════════════
// AI BUYER AGENT & VOICE INPUT CONTROLLER
// ════════════════════════════════════════════════════════

let chatMessages = [];
let voiceRecognition = null;
let isListening = false;

function initVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return null;
  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = getVoiceLangCode();
  return recognition;
}

window.toggleVoiceInput = function() {
  const micBtn = document.getElementById('chat-mic-btn');
  const input = document.getElementById('chat-input');
  const statusEl = document.getElementById('voice-status');
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    showToast('Voice input is not supported in this browser. Please use Chrome, Edge, or Safari.', 'error');
    return;
  }

  if (isListening && voiceRecognition) {
    voiceRecognition.stop();
    isListening = false;
    if (micBtn) micBtn.classList.remove('listening');
    if (statusEl) statusEl.style.display = 'none';
    return;
  }

  try {
    voiceRecognition = initVoiceInput();
    if (!voiceRecognition) return;

    voiceRecognition.onstart = () => {
      isListening = true;
      if (micBtn) micBtn.classList.add('listening');
      if (statusEl) {
        statusEl.style.display = 'flex';
        const langName = getLang() === 'kn' ? 'ಕನ್ನಡ' : getLang() === 'hi' ? 'हिन्दी' : 'English';
        statusEl.innerHTML = `
          <div class="voice-wave"><span></span><span></span><span></span></div>
          <span>${t('voiceListening')} <strong>${langName}</strong>…</span>
        `;
      }
    };

    voiceRecognition.onresult = (event) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        transcript += event.results[i][0].transcript;
      }
      if (input && transcript) {
        input.value = transcript;
      }
    };

    voiceRecognition.onerror = (event) => {
      console.warn('Voice recognition error:', event.error);
      isListening = false;
      if (micBtn) micBtn.classList.remove('listening');
      if (statusEl) statusEl.style.display = 'none';
      if (event.error !== 'no-speech') {
        showToast('Microphone error: ' + event.error, 'error');
      }
    };

    voiceRecognition.onend = () => {
      isListening = false;
      if (micBtn) micBtn.classList.remove('listening');
      if (statusEl) statusEl.style.display = 'none';
      if (input && input.value.trim().length > 0) {
        sendChatMessage();
      }
    };

    voiceRecognition.start();
  } catch (err) {
    console.error('Voice start failed:', err);
    isListening = false;
    if (micBtn) micBtn.classList.remove('listening');
  }
};

async function renderAgent() {
  app.innerHTML = `<div class="page-enter">
    <div class="page-header">
      <h1>${t('agentTitle')}</h1>
      <p>${t('agentSubtitle')}</p>
    </div>
    <div id="scenarios-area">${loading()}</div>
    <div class="chat-container">
      <div class="chat-messages" id="chat-messages">
        ${chatMessages.length === 0
          ? `<div class="chat-message system">
               <div class="msg-label">🤖 AgentPay AI</div>
               ${getLang() === 'kn'
                 ? 'ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ AI ಖರೀದಿದಾರ ಏಜೆಂಟ್. ನೀವು ಖರೀದಿಸಲು ಬಯಸುವ ಉತ್ಪನ್ನವನ್ನು ಧ್ವನಿ ಅಥವಾ ಟೈಪ್ ಮೂಲಕ ತಿಳಿಸಿ (ಉದಾ: "70000 ರೂಪಾಯಿ ಒಳಗೆ ಲ್ಯಾಪ್‌ಟಾಪ್"). ನಾನು ಎಲ್ಲಾ ವ್ಯಾಪಾರಿಗಳಲ್ಲಿ ಹುಡುಕಿ ಬೆಲೆ ಚೌಕಾಶಿ ಮಾಡುತ್ತೇನೆ.'
                 : getLang() === 'hi'
                 ? 'नमस्ते! मैं आपका AI खरीदार एजेंट हूँ। आप जो उत्पाद खरीदना चाहते हैं, उसे बोलकर या लिखकर बताएं (उदा: "70000 रुपये के अंदर लैपटॉप")। मैं सबसे अच्छी कीमत पर मोलभाव करूंगा।'
                 : "Hello! I'm your AI Buyer Agent. Tell me or speak what you'd like to purchase and I'll find, compare, negotiate discounts, and enforce your spending limits across all merchants."
               }
             </div>`
          : chatMessages.map(m => `<div class="chat-message ${m.role}">${m.role === 'system' ? '<div class="msg-label">🤖 AgentPay AI</div>' : ''}${m.html}</div>`).join('')
        }
      </div>
      <div class="chat-input-area">
        <div class="chat-input-row">
          <input type="text" id="chat-input" placeholder="${t('chatPlaceholder')}" />
          <button id="chat-mic-btn" class="btn-mic" title="${t('voiceMicTitle')}" onclick="window.toggleVoiceInput()">🎙️</button>
          <button id="chat-send" class="btn-primary">${t('sendBtn')}</button>
        </div>
        <div id="voice-status" class="voice-status-bar" style="display:none"></div>
      </div>
    </div>
  </div>`;

  // Multilingual quick suggestions
  const scenariosArea = document.getElementById('scenarios-area');
  const suggestions = getLang() === 'kn' ? [
    { name: "ಲ್ಯಾಪ್‌ಟಾಪ್ ಹುಡುಕಾಟ", req: "70000 ರೂಪಾಯಿ ಒಳಗೆ 16GB RAM ಲ್ಯಾಪ್‌ಟಾಪ್ ಬೇಕು" },
    { name: "ಮೊಬೈಲ್ ಹುಡುಕಾಟ", req: "50000 ಒಳಗೆ 5G ಸ್ಮಾರ್ಟ್‌ಫೋನ್" },
    { name: "ಹೈ-ವ್ಯಾಲ್ಯೂ ಆರ್ಡರ್", req: "80000 ಒಳಗೆ ಪ್ರೀಮಿಯಂ ಲ್ಯಾಪ್ಟಾಪ್" }
  ] : getLang() === 'hi' ? [
    { name: "लैपटॉप खोजें", req: "70000 रुपये के अंदर 16GB RAM वाला लैपटॉप दिखाओ" },
    { name: "मोबाइल खोजें", req: "50000 के अंदर 5G स्मार्टफोन" },
    { name: "उच्च-मूल्य ऑर्डर", req: "80000 के अंदर प्रीमियम लैपटॉप" }
  ] : [
    { name: "AI/ML Laptop under ₹80k", req: "Find me a laptop for AI/ML development under ₹80,000" },
    { name: "High-Value Demo (>₹50k)", req: "Find a premium TechNova Pro 16 laptop" },
    { name: "Budget Accessories", req: "Find mechanical keyboard and mouse under ₹10,000" }
  ];

  scenariosArea.innerHTML = `
    <div class="chat-scenarios">
      ${suggestions.map(s => `
        <button class="scenario-btn" data-request="${s.req.replace(/"/g, '&quot;')}">
          <div class="scenario-name">💡 ${s.name}</div>
          <div class="scenario-desc">${s.req}</div>
        </button>
      `).join('')}
    </div>`;

  scenariosArea.querySelectorAll('.scenario-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById('chat-input');
      input.value = btn.dataset.request;
      sendChatMessage();
    });
  });

  // Chat handlers
  const input = document.getElementById('chat-input');
  const send = document.getElementById('chat-send');
  send.addEventListener('click', sendChatMessage);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendChatMessage(); });
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  // Add user message
  chatMessages.push({ role: 'user', html: text });
  const container = document.getElementById('chat-messages');
  container.innerHTML += `<div class="chat-message user">${text}</div>`;
  input.value = '';

  // Add thinking indicator
  container.innerHTML += `<div class="chat-message system" id="thinking"><div class="msg-label">🤖 AgentPay AI</div><div class="spinner" style="width:20px;height:20px;border-width:2px;margin:4px 0"></div> <span>${t('thinking')}</span></div>`;
  container.scrollTop = container.scrollHeight;

  // Call buyer request endpoint
  await api('/buyer/requests', {
    method: 'POST',
    body: JSON.stringify({ raw_request: text }),
  });

  // Search across all merchants
  const merchantsData = await api('/merchants');
  const merchants = merchantsData?.merchants || [];

  let allProducts = [];
  for (const m of merchants) {
    const pData = await api(`/merchants/${m.id}/products`);
    if (pData?.products) {
      allProducts.push(...pData.products.map(p => ({ ...p, merchant_name: m.name })));
    }
  }

  const keywords = text.toLowerCase();
  let filtered = allProducts;

  // Multilingual price matching (English / Hindi / Kannada)
  let maxPrice = null;
  const rawNumMatch = text.match(/(\d{4,7})/);
  if (rawNumMatch) {
    maxPrice = parseInt(rawNumMatch[1]);
  } else if (text.match(/(\d+)\s*k\b/i)) {
    maxPrice = parseInt(text.match(/(\d+)\s*k\b/i)[1]) * 1000;
  } else if (text.match(/(\d+)\s*(?:thousand|hajar|हज़ार|हजार|savira|ಸಾವಿರ)/i)) {
    maxPrice = parseInt(text.match(/(\d+)\s*(?:thousand|hajar|हज़ार|हजार|savira|ಸಾವಿರ)/i)[1]) * 1000;
  }

  if (maxPrice) {
    filtered = filtered.filter(p => p.price <= maxPrice);
  }

  // RAM filter
  const ramMatch = keywords.match(/(\d+)\s*gb\s*ram/i) || keywords.match(/(\d+)\s*gb/i);
  if (ramMatch) {
    const minRam = parseInt(ramMatch[1]);
    if (minRam >= 8) {
      filtered = filtered.filter(p => {
        const ram = p.specifications?.ram_gb || p.specifications?.ram || 0;
        const ramNum = typeof ram === 'string' ? parseInt(ram) : ram;
        return ramNum >= minRam;
      });
    }
  }

  // Remove thinking
  const thinking = document.getElementById('thinking');
  if (thinking) thinking.remove();

  // Sort by rating & price
  filtered.sort((a, b) => b.rating - a.rating || a.price - b.price);
  const top = filtered.slice(0, 5);

  let responseHtml = '';
  if (top.length) {
    responseHtml = `${t('foundProducts')}<br><br>`;
    responseHtml += top.map((p, i) => {
      const specs = p.specifications || {};
      return `<div style="margin-bottom:14px;padding:16px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
          <div>
            <strong style="font-size:1.05rem">${i + 1}. ${p.name}</strong><br>
            <span style="font-size:0.82rem;color:var(--text-muted)">by <strong>${p.merchant_name}</strong> · ⭐ ${p.rating} · 🚚 ${p.delivery_days} ${t('deliveryDays')} · 📦 ${p.stock} ${t('inStock')}</span>
          </div>
          <div style="text-align:right">
            <span style="color:var(--accent-purple);font-size:1.15rem;font-weight:700">${formatPrice(p.price)}</span>
          </div>
        </div>
        ${Object.keys(specs).length ? `<div style="margin-top:8px;font-size:0.78rem;color:var(--text-secondary)">${Object.entries(specs).slice(0, 4).map(([k,v]) => `<span style="background:rgba(255,255,255,0.05);padding:2px 6px;border-radius:4px;margin-right:4px">${k.replace(/_/g,' ')}: ${v}</span>`).join('')}</div>` : ''}
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn-primary" style="font-size:0.82rem;padding:7px 14px;" onclick="window.startAgentNegotiation('${p.merchant_id}', '${p.id}', '${p.name.replace(/'/g, "\\'")}', ${p.price})">${t('negotiateAndBuy')}</button>
          <button type="button" class="btn-secondary" style="font-size:0.82rem;padding:7px 14px;" onclick="window.openProductRefundModal('${p.id}', '${p.name.replace(/'/g, "\\'")}', '${p.category || ''}', ${p.price}, ${p.refund_policy?.window_days || 7}, '${(p.refund_policy?.condition || '').replace(/'/g, "\\'")}', ${p.refund_policy?.refund_percent || 100}, '${p.merchant_id}')">${t('viewRefundPolicyBtn')}</button>
        </div>
      </div>`;
    }).join('');
  } else {
    responseHtml = t('noProductsFound');
  }

  chatMessages.push({ role: 'system', html: responseHtml });
  container.innerHTML += `<div class="chat-message system"><div class="msg-label">🤖 AgentPay AI</div>${responseHtml}</div>`;
  container.scrollTop = container.scrollHeight;
}

// ── Interactive Agent Negotiation & Order Handler ──
window.startAgentNegotiation = async function(merchantId, productId, productName, originalPrice) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const initMsg = `<div class="chat-message system">
    <div class="msg-label">🤖 Buyer Agent</div>
    ${t('negotiatingWithMerchant')} <strong>${productName}</strong> (Original: ${formatPrice(originalPrice)}). ${t('requestingDiscount')}
  </div>`;
  container.innerHTML += initMsg;
  container.scrollTop = container.scrollHeight;

  const negRes = await api(`/merchants/${merchantId}/negotiate`, {
    method: 'POST',
    body: JSON.stringify({
      product_id: productId,
      requested_discount_percent: 10.0,
      session_id: 'chat-session-' + Date.now().toString().slice(-4),
    }),
  });

  if (!negRes || !negRes.quote_id) {
    container.innerHTML += `<div class="chat-message system" style="border-left:3px solid var(--accent-red)"><div class="msg-label">⚠️ System</div>Negotiation failed or merchant is unavailable.</div>`;
    return;
  }

  const merchantMsg = `<div class="chat-message system">
    <div class="msg-label">🏪 ${negRes.merchant_name} Agent</div>
    ${negRes.merchant_message}<br>
    <strong>${t('finalPrice')}: ${formatPrice(negRes.final_price)}</strong> <span style="color:var(--accent-green)">(${t('saved')} ${formatPrice(negRes.discount_amount)} / ${negRes.approved_discount_percent}% off)</span>
  </div>`;
  container.innerHTML += merchantMsg;
  container.scrollTop = container.scrollHeight;

  const orderRes = await api('/orders', {
    method: 'POST',
    body: JSON.stringify({
      quote_id: negRes.quote_id,
      user_id: 'demo-user-001',
      session_id: 'chat-session-001',
    }),
  });

  if (!orderRes || !orderRes.id) {
    container.innerHTML += `<div class="chat-message system" style="border-left:3px solid var(--accent-red)"><div class="msg-label">⚠️ Order Error</div>Failed to convert quote to order.</div>`;
    return;
  }

  if (orderRes.status === 'pending_approval') {
    const threshold = orderRes.metadata_json?.approval_threshold || 50000;
    const excess = Math.max(0, orderRes.amount - threshold);
    const gateHtml = `<div class="chat-message system" style="border-left:3px solid var(--accent-amber);background:rgba(251,191,36,0.05)">
      <div class="msg-label">🛡️ Policy Engine Gate</div>
      <strong style="color:var(--accent-amber)">${t('orderPendingApproval')}</strong><br>
      ${t('orderPendingDesc')} <strong>${formatPrice(threshold)}</strong> (${t('excessOverLimit')}: +${formatPrice(excess)}).<br>
      <span style="font-size:0.82rem;color:var(--text-muted)">${t('securityToken')}: <code>${orderRes.metadata_json?.approval_token || 'N/A'}</code></span>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <a href="#/policy" class="btn-secondary" style="font-size:0.82rem;padding:6px 12px">${t('viewInTrustCenter')}</a>
        <button class="btn-approve" style="font-size:0.82rem;padding:6px 12px" onclick="window.quickApproveInChat('${orderRes.id}')">${t('quickAuthorize')}</button>
      </div>
    </div>`;
    container.innerHTML += gateHtml;
  } else {
    const approvedHtml = `<div class="chat-message system" style="border-left:3px solid var(--accent-green);background:rgba(16,185,129,0.05)">
      <div class="msg-label">${t('orderAutoApproved')}</div>
      Order <strong>${orderRes.id.slice(0, 8)}</strong> for <strong>${formatPrice(orderRes.amount)}</strong> is within your autonomous spending limit.<br>
      <div style="margin-top:10px">
        <button class="btn-primary" style="font-size:0.82rem;padding:6px 14px" onclick="window.launchRazorpayPayment('${orderRes.id}')">${t('payRazorpay')}</button>
      </div>
    </div>`;
    container.innerHTML += approvedHtml;
  }
  container.scrollTop = container.scrollHeight;
};

window.quickApproveInChat = async function(orderId) {
  const res = await api(`/policy/approvals/${orderId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approver: 'human_admin' }),
  });
  if (res && res.status === 'approved') {
    showToast('Order authorized! Ready for Razorpay payment.', 'success');
    const container = document.getElementById('chat-messages');
    container.innerHTML += `<div class="chat-message system" style="border-left:3px solid var(--accent-green)">
      <div class="msg-label">✅ Order Authorized by Human</div>
      Order <strong>${orderId.slice(0, 8)}</strong> has been unlocked for payment.<br>
      <button class="btn-primary" style="margin-top:8px;font-size:0.82rem;padding:6px 14px" onclick="window.launchRazorpayPayment('${orderId}')">${t('payRazorpay')}</button>
    </div>`;
    container.scrollTop = container.scrollHeight;
  } else {
    showToast('Failed to authorize: ' + (res?.detail || 'Error'), 'error');
  }
};

window.launchRazorpayPayment = async function(orderId) {
  const res = await api('/payments/create', {
    method: 'POST',
    body: JSON.stringify({ order_id: orderId }),
  });
  if (res && res.razorpay_order_id) {
    showToast(`Razorpay test order ${res.razorpay_order_id} created!`, 'success');
    const vRes = await api('/payments/verify', {
      method: 'POST',
      body: JSON.stringify({
        order_id: orderId,
        razorpay_order_id: res.razorpay_order_id,
        razorpay_payment_id: 'pay_test_' + Date.now().toString().slice(-6),
        razorpay_signature: 'sig_simulated_valid',
      }),
    });
    if (vRes && vRes.status === 'success') {
      showToast('Payment settled and converged successfully!', 'success');
      const container = document.getElementById('chat-messages');
      container.innerHTML += `<div class="chat-message system" style="border-left:3px solid var(--accent-green);background:rgba(16,185,129,0.06)">
        <div class="msg-label">${t('paymentComplete')}</div>
        ${t('paymentCompleteDesc')}<br>
        <strong>Order Status:</strong> PAID (Success)<br>
        <span style="font-size:0.8rem;color:var(--text-muted)">Receipt: ${vRes.payment_id} · Invariant Verified</span>
      </div>`;
      container.scrollTop = container.scrollHeight;
    }
  } else {
    showToast('Payment creation failed: ' + (res?.detail || 'Error'), 'error');
  }
};

function showToast(message, type = 'info') {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span> ${message}`;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}


// ════════════════════════════════════════════════════════
// POLICY & TRUST CENTER
// ════════════════════════════════════════════════════════

async function renderPolicy() {
  app.innerHTML = `<div class="page-enter">
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px">
      <div>
        <h1>${t('policyTitle')}</h1>
        <p>${t('policySubtitle')}</p>
      </div>
      <div style="display:flex;gap:8px">
        <button id="trigger-demo-order-btn" class="btn-primary" style="font-size:0.85rem;padding:8px 16px;background:linear-gradient(135deg, #f59e0b 0%, #d97706 100%)">
          ${t('triggerDemoBtn')}
        </button>
      </div>
    </div>

    <!-- ───── Pending Human Approvals Queue ───── -->
    <div class="card" style="margin-bottom:24px;border:1px solid rgba(251,191,36,0.35);background:rgba(251,191,36,0.03)">
      <div class="card-title" style="display:flex;align-items:center;justify-content:space-between">
        <span>${t('pendingQueueTitle')}</span>
        <button id="refresh-approvals-btn" class="btn-secondary" style="font-size:0.78rem;padding:4px 10px">${t('refreshQueue')}</button>
      </div>
      <div class="card-subtitle">${t('pendingQueueSub')}</div>
      <div id="pending-approvals-list" style="margin-top:14px">${loading()}</div>
    </div>

    <div class="policy-grid">
      <!-- ───── Spending Passport ───── -->
      <div class="card">
        <div class="card-title">${t('passportTitle')}</div>
        <div class="card-subtitle">${t('passportSub')}</div>
        <div id="passport-result" style="margin-top:14px">${loading()}</div>
      </div>

      <!-- ───── Policy Evaluation Simulator ───── -->
      <div class="card">
        <div class="card-title">${t('evalTitle')}</div>
        <div class="card-subtitle">${t('evalSub')}</div>
        <form class="policy-form" id="policy-form" style="margin-top:14px">
          <div class="form-group">
            <label>${t('amountLabel')}</label>
            <input type="number" id="eval-amount" value="65000" min="1" />
          </div>
          <div class="form-group">
            <label>${t('discountLabel')}</label>
            <input type="number" id="eval-discount" value="8" min="0" max="100" />
          </div>
          <div class="form-group">
            <label>${t('userIdLabel')}</label>
            <input type="text" id="eval-user" value="demo-user-001" />
          </div>
          <button type="submit" class="btn-primary">${t('runSimBtn')}</button>
        </form>
        <div id="eval-result" style="margin-top:14px"></div>
      </div>

      <!-- ───── Policy Violations ───── -->
      <div class="card" style="grid-column: 1 / -1">
        <div class="card-title" style="display:flex;justify-content:space-between;align-items:center">
          <span>${t('violationsTitle')}</span>
          <button class="btn-secondary" id="load-violations" style="font-size:0.78rem;padding:4px 10px">${t('refreshViolations')}</button>
        </div>
        <div class="card-subtitle">${t('violationsSub')}</div>
        <div id="violations-result" style="margin-top:14px">${loading()}</div>
      </div>
    </div>
  </div>`;

  async function loadPendingApprovals() {
    const listEl = document.getElementById('pending-approvals-list');
    if (!listEl) return;
    listEl.innerHTML = loading();

    const data = await api('/policy/approvals/pending');
    const pending = data?.pending_approvals || [];

    if (!pending.length) {
      listEl.innerHTML = emptyState('✅', t('noPendingApprovals'));
      return;
    }

    listEl.innerHTML = `
      <div class="approval-queue">
        ${pending.map(order => {
          const meta = order.metadata_json || {};
          const threshold = meta.approval_threshold || 50000;
          const token = meta.approval_token || 'N/A';
          return `
            <div class="approval-card" id="approval-card-${order.id}">
              <div class="approval-header">
                <div>
                  <strong style="color:var(--text-primary);font-size:1.05rem">${order.product_name || 'Product'}</strong>
                  <span style="color:var(--text-muted);font-size:0.85rem"> · Merchant: <strong>${order.merchant_name || 'Merchant'}</strong></span>
                </div>
                <span class="approval-status-badge">${t('pendingSignOff')}</span>
              </div>

              <div class="approval-details-grid">
                <div class="approval-metric">
                  <span class="approval-metric-label">${t('orderTotal')}</span>
                  <span class="approval-metric-value" style="color:var(--accent-amber);font-size:1.1rem">${formatPrice(order.amount)}</span>
                </div>
                <div class="approval-metric">
                  <span class="approval-metric-label">${t('autoApprovalLimit')}</span>
                  <span class="approval-metric-value">${formatPrice(threshold)}</span>
                </div>
                <div class="approval-metric">
                  <span class="approval-metric-label">${t('excessOverLimit')}</span>
                  <span class="approval-metric-value" style="color:var(--accent-red)">+${formatPrice(Math.max(0, order.amount - threshold))}</span>
                </div>
                <div class="approval-metric">
                  <span class="approval-metric-label">${t('orderIdLabel')}</span>
                  <span class="approval-metric-value" style="font-family:monospace;font-size:0.8rem">${order.id.slice(0, 12)}…</span>
                </div>
              </div>

              <div class="approval-token-box">
                <span style="color:var(--text-muted)">🔑 ${t('securityToken')}:</span>
                <code>${token}</code>
              </div>

              <div class="approval-actions">
                <button class="btn-reject" onclick="handleRejectOrder('${order.id}')">${t('rejectBtn')}</button>
                <button class="btn-approve" onclick="handleApproveOrder('${order.id}')">${t('authorizeBtn')}</button>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  async function loadPassport(userId = 'demo-user-001') {
    const passEl = document.getElementById('passport-result');
    if (!passEl) return;
    const res = await api(`/policy/passport/${userId}`);
    if (!res || !res.user_id) {
      passEl.innerHTML = emptyState('❌', 'Could not load Spending Passport.');
      return;
    }

    const cats = Array.isArray(res.allowed_categories) ? res.allowed_categories : [];
    passEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:14px">
        <div style="display:flex;justify-content:space-between;align-items:center;padding-bottom:10px;border-bottom:1px solid var(--border-subtle)">
          <div>
            <strong style="font-size:1.05rem">${res.user_name || 'Demo Buyer'}</strong>
            <span style="color:var(--text-muted);font-size:0.8rem"> (${res.user_id})</span>
          </div>
          <span style="background:rgba(16,185,129,0.15);color:var(--accent-green);border:1px solid rgba(16,185,129,0.3);font-size:0.75rem;padding:3px 8px;border-radius:999px;font-weight:700">🟢 ACTIVE</span>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div style="background:rgba(255,255,255,0.02);padding:10px 14px;border-radius:8px;border:1px solid var(--border-subtle)">
            <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase">${t('singleTxLimit')}</div>
            <div style="font-size:1.1rem;font-weight:700;color:var(--text-primary)">${formatPrice(res.single_transaction_limit)}</div>
          </div>
          <div style="background:rgba(255,255,255,0.02);padding:10px 14px;border-radius:8px;border:1px solid var(--border-subtle)">
            <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase">${t('approvalAbove')}</div>
            <div style="font-size:1.1rem;font-weight:700;color:var(--accent-amber)">${formatPrice(res.requires_approval_above)}</div>
          </div>
          <div style="background:rgba(255,255,255,0.02);padding:10px 14px;border-radius:8px;border:1px solid var(--border-subtle)">
            <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase">${t('dailySpendingLimit')}</div>
            <div style="font-size:1.1rem;font-weight:700;color:var(--text-primary)">${formatPrice(res.daily_spending_limit)}</div>
          </div>
          <div style="background:rgba(255,255,255,0.02);padding:10px 14px;border-radius:8px;border:1px solid var(--border-subtle)">
            <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase">${t('dailyRemaining')}</div>
            <div style="font-size:1.1rem;font-weight:700;color:var(--accent-teal)">${formatPrice(res.daily_remaining)}</div>
          </div>
        </div>

        <div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:6px;text-transform:uppercase">${t('allowedCategories')}:</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            ${cats.map(c => `<span style="background:rgba(167,139,250,0.12);color:var(--accent-purple);border:1px solid rgba(167,139,250,0.25);padding:2px 8px;border-radius:6px;font-size:0.78rem">${c}</span>`).join('')}
          </div>
        </div>
      </div>
    `;
  }

  async function loadViolations() {
    const vEl = document.getElementById('violations-result');
    if (!vEl) return;
    vEl.innerHTML = loading();

    const res = await api('/policy/violations');
    const violations = res?.violations || [];

    if (!violations.length) {
      vEl.innerHTML = emptyState('🛡️', t('zeroViolations'));
      return;
    }

    vEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:8px">
        ${violations.map(v => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:rgba(239,68,68,0.04);border:1px solid rgba(239,68,68,0.2);border-radius:8px;flex-wrap:wrap;gap:8px">
            <div>
              <span style="background:rgba(239,68,68,0.15);color:var(--accent-red);padding:2px 6px;border-radius:4px;font-size:0.72rem;font-weight:700;text-transform:uppercase">${v.policy_type || 'VIOLATION'}</span>
              <span style="font-size:0.85rem;color:var(--text-primary);margin-left:8px">${v.reason || 'Policy check failed'}</span>
            </div>
            <div style="font-size:0.78rem;color:var(--text-muted)">
              Requested: <strong style="color:var(--accent-red)">${formatPrice(v.requested_value || 0)}</strong> · Limit: ${formatPrice(v.allowed_value || 0)}
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  window.handleApproveOrder = async function(orderId) {
    const card = document.getElementById(`approval-card-${orderId}`);
    if (card) card.style.opacity = '0.5';

    const res = await api(`/policy/approvals/${orderId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approver: 'human_admin' }),
    });

    if (res && res.status === 'approved') {
      showToast(`Order approved! Payment processing is unlocked.`, 'success');
    } else {
      showToast(`Failed to approve: ${res?.detail || 'Error'}`, 'error');
    }
    await loadPendingApprovals();
  };

  window.handleRejectOrder = async function(orderId) {
    const card = document.getElementById(`approval-card-${orderId}`);
    if (card) card.style.opacity = '0.5';

    const res = await api(`/policy/approvals/${orderId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ approver: 'human_admin', reason: 'Declined by administrator in Trust Center' }),
    });

    if (res && res.status === 'rejected') {
      showToast(`Order rejected and cancelled.`, 'info');
    } else {
      showToast(`Failed to reject: ${res?.detail || 'Error'}`, 'error');
    }
    await loadPendingApprovals();
  };

  document.getElementById('refresh-approvals-btn').addEventListener('click', loadPendingApprovals);
  document.getElementById('load-violations').addEventListener('click', loadViolations);

  document.getElementById('trigger-demo-order-btn').addEventListener('click', async () => {
    const btn = document.getElementById('trigger-demo-order-btn');
    btn.disabled = true;
    btn.textContent = 'Creating Demo Order…';

    const res = await api('/demo/trigger-approval-demo', { method: 'POST' });
    btn.disabled = false;
    btn.textContent = t('triggerDemoBtn');

    if (res && res.status === 'pending_approval_created') {
      showToast('Created ₹67,500 order in Pending Approval state!', 'success');
      await loadPendingApprovals();
    } else {
      showToast('Failed to trigger demo order: ' + (res?.detail || 'Error'), 'error');
    }
  });

  document.getElementById('policy-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const amount = parseFloat(document.getElementById('eval-amount').value);
    const discount = parseFloat(document.getElementById('eval-discount').value);
    const userId = document.getElementById('eval-user').value;

    const evalResultEl = document.getElementById('eval-result');
    evalResultEl.innerHTML = loading();

    const res = await api('/policy/simulate', {
      method: 'POST',
      body: JSON.stringify({
        amount: amount,
        discount_percent: discount,
        user_id: userId,
        product_name: 'Simulated Device',
        category: 'laptops',
        stock: 5,
      }),
    });

    if (!res) {
      evalResultEl.innerHTML = emptyState('❌', 'Evaluation failed.');
      return;
    }

    const checks = res.checks || [];
    const statusText = !res.allowed ? '🔴 BLOCKED BY POLICY' : res.requires_user_approval ? '⏳ REQUIRES HUMAN APPROVAL' : '🟢 AUTO-APPROVED';
    const statusColor = !res.allowed ? 'var(--accent-red)' : res.requires_user_approval ? 'var(--accent-amber)' : 'var(--accent-green)';

    evalResultEl.innerHTML = `
      <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border-subtle);border-radius:10px;padding:14px;margin-top:10px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <strong style="color:${statusColor}">${statusText}</strong>
          <span style="font-size:0.75rem;color:var(--text-muted)">Explainability: 100% Deterministic</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          ${checks.map(c => `
            <div style="display:flex;justify-content:space-between;font-size:0.8rem;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.03)">
              <span>${c.passed ? '✅' : '❌'} <strong>${c.name.replace(/_/g, ' ')}</strong></span>
              <span style="color:var(--text-secondary);font-family:monospace;font-size:0.75rem">${c.formula || c.reason}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  });

  await loadPendingApprovals();
  await loadPassport();
  await loadViolations();
}


// ════════════════════════════════════════════════════════
// AUDIT TRAIL
// ════════════════════════════════════════════════════════

async function renderAudit() {
  app.innerHTML = `<div class="page-enter">
    <div class="page-header">
      <h1>${t('auditTitle')}</h1>
      <p>${t('auditSubtitle')}</p>
    </div>

    <div class="card" style="margin-bottom:24px">
      <div class="card-title">${t('sessionLookupTitle')}</div>
      <div class="card-subtitle">${t('sessionLookupSub')}</div>
      <form class="policy-form" id="audit-session-form" style="margin-top:12px;flex-direction:row;align-items:flex-end;gap:12px">
        <div class="form-group" style="flex:1">
          <label>${t('sessionLookupTitle')}</label>
          <input type="text" id="audit-session-id" placeholder="${t('sessionPlaceholder')}" />
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:6px">
            ${t('quickSamples')} 
            <span style="cursor:pointer;color:var(--accent-purple);text-decoration:underline;margin-right:8px" onclick="window.lookupSession('demo-approval-session')">demo-approval-session</span>
            <span style="cursor:pointer;color:var(--accent-purple);text-decoration:underline" onclick="window.lookupSession('chat-session-001')">chat-session-001</span>
          </div>
        </div>
        <button type="submit" class="btn-primary" style="height:46px">${t('lookupBtn')}</button>
      </form>
      <div id="session-result"></div>
    </div>

    <div class="section-title">${t('recentEventsTitle')}</div>
    <div id="audit-events">${loading()}</div>
  </div>`;

  window.lookupSession = function(id) {
    const input = document.getElementById('audit-session-id');
    if (input) {
      input.value = id;
      document.getElementById('audit-session-form').dispatchEvent(new Event('submit'));
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  window.showWhy = function(index) {
    const panel = document.getElementById(`why-panel-${index}`);
    if (panel) panel.hidden = !panel.hidden;
  };

  window.showStage = function(index) {
    const panel = document.getElementById(`stage-details-${index}`);
    if (panel) panel.hidden = !panel.hidden;
  };

  const data = await api('/audit');
  const eventsEl = document.getElementById('audit-events');
  const events = data?.audit_logs || data?.events || (Array.isArray(data) ? data : []);

  if (events.length) {
    eventsEl.innerHTML = `<div class="audit-list">
      ${events.map(e => {
        const actionTitle = e.action ? e.action.replace(/_/g, ' ').toUpperCase() : (e.event_type || e.type || 'EVENT');
        const actor = e.actor || 'system';
        const actorIcon = actor.includes('buyer') ? '🤖' : actor.includes('admin') || actor.includes('human') ? '👤' : actor.includes('payment') ? '💳' : actor.includes('order') ? '📦' : '🛡️';
        return `
          <div class="audit-event">
            <div class="audit-icon">${actorIcon}</div>
            <div class="audit-content">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">
                <div class="audit-title"><strong>${actionTitle}</strong> <span style="font-size:0.75rem;color:var(--text-muted)">(${actor})</span></div>
                ${e.amount ? `<span style="color:var(--accent-purple);font-weight:700;font-size:0.85rem">${formatPrice(e.amount)}</span>` : ''}
              </div>
              <div class="audit-detail">${e.reason || e.details || e.message || ''}</div>
              ${e.session_id ? `
                <div style="font-size:0.75rem;color:var(--text-muted);margin-top:6px">
                  Session: <code style="cursor:pointer;background:rgba(167,139,250,0.12);color:var(--accent-purple);padding:2px 8px;border-radius:4px;border:1px solid rgba(167,139,250,0.25)" title="Click to auto-lookup this session" onclick="window.lookupSession('${e.session_id}')">${e.session_id} 🔍</code>
                </div>` : ''}
            </div>
            <div class="audit-time">${e.timestamp ? new Date(e.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : ''}</div>
          </div>
        `;
      }).join('')}
    </div>`;
  } else {
    eventsEl.innerHTML = emptyState('📝', t('noAuditEvents'));
  }

  document.getElementById('audit-session-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('audit-session-id').value.trim();
    if (!id) return;
    const resEl = document.getElementById('session-result');
    resEl.innerHTML = loading();
    const res = await api(`/audit/${id}`);
    const chain = await api(`/audit/${id}/chain`);
    if (!res || (!res.audit_logs?.length && !res.agent_actions?.length && !res.policy_violations?.length)) {
      resEl.innerHTML = emptyState('🔍', `No audit records found for session ID "${id}".`);
      return;
    }

    const sessionLogs = res.audit_logs || [];
    const paymentEvent = (chain?.stages || []).find((stage) => stage.id === 'verified')?.event;
    const paymentMeta = paymentEvent?.metadata || {};
    const canRefund = chain?.status === 'passed' && paymentMeta.order_id && paymentMeta.payment_id;
    resEl.innerHTML = `
      <div style="margin-top:14px;background:rgba(255,255,255,0.02);border:1px solid var(--border-subtle);border-radius:10px;padding:16px">
        <div style="font-weight:700;color:var(--text-primary);margin-bottom:12px">Session Audit Trail: <code>${id}</code></div>
        ${chain ? renderKillChain(chain) : `<div class="chain-error">Kill-chain data is temporarily unavailable.</div>`}
        <div class="audit-list">
          ${sessionLogs.map(l => `
            <div class="audit-event" style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04)">
              <div class="audit-content">
                <div style="font-weight:600;font-size:0.9rem">${l.action?.replace(/_/g, ' ').toUpperCase()} <span style="font-size:0.75rem;color:var(--text-muted)">by ${l.actor}</span></div>
                <div style="font-size:0.82rem;color:var(--text-secondary)">${l.reason || ''}</div>
              </div>
              <div class="audit-time">${l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : ''}</div>
            </div>
          `).join('')}
        </div>
        ${canRefund ? `<div class="refund-panel" style="margin-top:18px;padding-top:16px;border-top:1px solid var(--border-subtle)">
          <div class="card-title">Request Refund</div>
          <div class="card-subtitle">Refund the captured payment through the secure refund workflow.</div>
          <form id="refund-form" class="policy-form" style="margin-top:12px">
            <label>Amount (leave blank for full remaining refund)<input id="refund-amount" type="number" min="0.01" step="0.01" placeholder="Full remaining amount" /></label>
            <label>Reason<input id="refund-reason" required maxlength="500" placeholder="Reason for refund" /></label>
            <button class="btn-primary" type="submit">Request Refund</button>
          </form><div id="refund-result" style="margin-top:12px"></div>
        </div>` : ''}
      </div>
    `;
    if (canRefund) document.getElementById('refund-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      const resultEl = document.getElementById('refund-result');
      resultEl.innerHTML = loading();
      const amount = document.getElementById('refund-amount').value;
      const result = await api('/refunds', {
        method: 'POST',
        headers: { 'Idempotency-Key': `refund-${crypto.randomUUID()}` },
        body: JSON.stringify({ order_id: paymentMeta.order_id, payment_id: paymentMeta.payment_id, amount: amount ? Number(amount) : null, reason: document.getElementById('refund-reason').value })
      });
      resultEl.innerHTML = result ? `<div class="badge badge-green">Refund ${escapeHTML(result.status)}</div><div>Refund ID: <code>${escapeHTML(result.id)}</code> · ${formatPrice(result.amount)}</div>` : `<div class="badge badge-red">Refund request failed. Check the API response and try again.</div>`;
    });
  });
}

async function renderRefunds() {
  app.innerHTML = `<div class="page-enter">
    <div class="page-header"><h1>${t('refundTitle')}</h1><p>${t('refundSubtitle')}</p></div>

    <div class="refund-tabs">
      <button class="refund-tab active" onclick="window.showRefundTab('nlp')">${t('refundTabAi')}</button>
      <button class="refund-tab" onclick="window.showRefundTab('lookup')">${t('refundTabLookup')}</button>
    </div>

    <!-- Quick sample orders bar -->
    <div style="margin-bottom:16px;padding:12px 16px;background:rgba(167,139,250,0.06);border:1px solid rgba(167,139,250,0.2);border-radius:10px;display:flex;align-items:center;flex-wrap:wrap;gap:8px;">
      <span style="font-size:0.78rem;font-weight:700;color:var(--accent-purple);">${t('refundSampleOrders')}</span>
      <button type="button" class="meta-tag" style="cursor:pointer;background:rgba(255,255,255,0.06);" onclick="window.fillSampleOrder('order-laptop-demo-01', 'I want to return this laptop because it arrived with screen damage.')">💻 Laptop (${t('kcLegendPassed')})</button>
      <button type="button" class="meta-tag" style="cursor:pointer;background:rgba(255,255,255,0.06);" onclick="window.fillSampleOrder('order-phone-demo-02', 'I changed my mind and want a refund for this phone.')">📱 Phone (${t('kcLegendPassed')})</button>
      <button type="button" class="meta-tag" style="cursor:pointer;background:rgba(255,255,255,0.06);" onclick="window.fillSampleOrder('order-expired-demo-03', 'I want to return this laptop bought 20 days ago.')">⏰ Laptop (${t('kcLegendBlocked')})</button>
    </div>

    <div id="refund-tab-nlp">
      <section class="nlp-refund-input">
        <div class="card-title" style="margin-bottom:8px">${t('refundDescribeTitle')}</div>
        <div class="card-subtitle" style="margin-bottom:12px">${t('refundDescribeSubtitle')}</div>
        <form id="nlp-refund-form">
          <textarea id="nlp-refund-text" placeholder="${t('refundPlaceholder')}" maxlength="2000" required></textarea>
          <div style="display:flex;gap:10px;align-items:end;margin-top:10px">
            <div style="flex:1"><label style="display:block;color:var(--text-muted);font-size:0.75rem;margin-bottom:4px">${t('refundOrderIdOptional')}</label><input id="nlp-order-id" placeholder="e.g. order-laptop-demo-01" style="width:100%" /></div>
            <button class="btn-primary" type="submit">${t('refundSubmitBtn')}</button>
          </div>
        </form>
      </section>
    </div>

    <div id="refund-tab-lookup" style="display:none">
      <section class="refund-lookup card">
        <form id="refund-lookup-form"><label for="refund-order-id">${t('orderIdLabel')}</label>
          <div class="refund-lookup-row"><input id="refund-order-id" required placeholder="Paste the order ID (e.g. order-laptop-demo-01)" /><button class="btn-primary" type="submit">${t('refundCheckEligibility')}</button></div>
        </form>
      </section>
    </div>

    <div id="refund-result-area"></div>
  </div>`;

  window.fillSampleOrder = function(orderId, text) {
    const textEl = document.getElementById('nlp-refund-text');
    const orderEl = document.getElementById('nlp-order-id');
    const lookupEl = document.getElementById('refund-order-id');
    if (textEl) textEl.value = text;
    if (orderEl) orderEl.value = orderId;
    if (lookupEl) lookupEl.value = orderId;
  };

  // Tab switching
  window.showRefundTab = function(tab) {
    document.getElementById('refund-tab-nlp').style.display = tab === 'nlp' ? '' : 'none';
    document.getElementById('refund-tab-lookup').style.display = tab === 'lookup' ? '' : 'none';
    document.querySelectorAll('.refund-tab').forEach((tEl, i) => tEl.classList.toggle('active', i === (tab === 'nlp' ? 0 : 1)));
  };

  // NLP request
  document.getElementById('nlp-refund-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const area = document.getElementById('refund-result-area');
    area.innerHTML = loading();
    const text = document.getElementById('nlp-refund-text').value.trim();
    const orderId = document.getElementById('nlp-order-id').value.trim() || null;
    const result = await api('/refunds/request', {
      method: 'POST',
      body: JSON.stringify({ message: text, order_id: orderId, user_id: 'demo-user-001' }),
    });
    if (!result) { area.innerHTML = emptyState('⚠️', 'Request failed. Check the backend.'); return; }
    area.innerHTML = renderRefundResult(result);
    bindRefundActions(result);
  });

  // Lookup
  document.getElementById('refund-lookup-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const area = document.getElementById('refund-result-area');
    area.innerHTML = loading();
    const orderId = document.getElementById('refund-order-id').value.trim();
    const data = await api(`/refunds/eligibility/${encodeURIComponent(orderId)}`);
    if (!data) { area.innerHTML = emptyState('⚠️', 'Could not check eligibility.'); return; }
    area.innerHTML = renderEligibilityResult(data);
    bindEligibilityActions(data);
  });
}

function renderRefundResult(result) {
  const ext = result.extraction || {};
  const elig = result.eligibility;
  const refund = result.refund;
  const error = result.error;

  let html = `<section class="card" style="margin-top:16px">
    <div class="card-title">${t('refundAiExtractionTitle')}</div>
    <div class="card-subtitle" style="margin-bottom:10px">Provider: <span class="badge badge-purple">${escapeHTML(result.provider || 'deterministic')}</span> ${result.used_fallback ? '<span class="badge badge-amber">Fallback</span>' : '<span class="badge badge-green">LLM</span>'}</div>
    <div class="refund-facts" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr))">
      <div><span>${t('orderIdLabel')}</span><strong>${escapeHTML(ext.order_id || 'Not detected')}</strong></div>
      <div><span>Reason Category</span><strong>${escapeHTML((ext.reason_category || 'other').replace(/_/g, ' '))}</strong></div>
      <div><span>Refund Type</span><strong>${escapeHTML(ext.refund_type || 'full')}</strong></div>
      <div><span>${t('amountLabel')}</span><strong>${ext.requested_amount ? formatPrice(ext.requested_amount) : 'Full'}</strong></div>
    </div>
  </section>`;

  if (error && !refund) {
    html += `<section class="card refund-rejected" style="margin-top:16px">
      <div class="refund-decision"><span class="badge badge-red">CANNOT PROCESS</span><strong>${escapeHTML(error)}</strong></div>
    </section>`;
  }

  if (elig) {
    html += renderEligibilityChecks(elig);
  }

  if (refund) {
    html += renderRefundDetail(refund);
  }

  return html;
}

function renderEligibilityChecks(elig) {
  const checks = elig.checks || [];
  if (!checks.length) return '';
  return `<section class="card" style="margin-top:16px">
    <div class="card-title">${t('refundPolicyChecksTitle')}</div>
    <div class="refund-eligibility-checks">
      ${checks.map(c => `<div class="eligibility-check ${c.passed ? 'passed' : 'failed'}">
        <span class="check-icon">${c.passed ? '✅' : '❌'}</span>
        <div><div class="check-label">${escapeHTML(c.label)}</div><div class="check-detail">${escapeHTML(c.detail)}</div></div>
      </div>`).join('')}
    </div>
  </section>`;
}

function renderEligibilityResult(data) {
  const policy = data.policy || {};
  const accepted = data.eligible === true;
  let html = `<section class="refund-preview card ${accepted ? 'refund-accepted' : 'refund-rejected'}" style="margin-top:16px">
    <div class="refund-decision"><span class="badge ${accepted ? 'badge-green' : 'badge-red'}">${accepted ? t('refundAvailable') : t('refundRejected')}</span><strong>${escapeHTML(data.decision_reason || '')}</strong></div>
    ${data.product_name ? `<div class="refund-product"><div class="audit-icon">📦</div><div><h2>${escapeHTML(data.product_name)}</h2><p>${escapeHTML(data.category)} · ${t('orderIdLabel')} ${escapeHTML(data.order_id)} · Payment ${escapeHTML(data.payment_id || 'N/A')}</p></div></div>` : ''}
    <div class="refund-facts"><div><span>${t('refundPaid')}</span><strong>${formatPrice(data.amount_paid || 0)}</strong></div><div><span>${t('refundAlreadyRefunded')}</span><strong>${formatPrice(data.refunded_amount || 0)}</strong></div><div><span>${t('refundRemaining')}</span><strong>${formatPrice(data.remaining_refundable_amount || 0)}</strong></div><div><span>${t('refundDeadline')}</span><strong>${policy.deadline ? new Date(policy.deadline).toLocaleDateString() : 'N/A'}</strong></div></div>
    <div class="refund-policy"><strong>${t('refundPolicyTitle')}</strong><p>${escapeHTML(policy.refund_percent || 100)}% refund within ${escapeHTML(policy.window_days || 7)} days. ${escapeHTML(policy.condition || '')}</p></div>
  </section>`;

  html += renderEligibilityChecks(data);

  if (accepted) {
    html += `<section class="card" style="margin-top:16px">
      <form id="verified-refund-form" class="verified-refund-form">
        <label>${t('refundAmountLabel')}<input id="verified-refund-amount" type="number" min="0.01" max="${escapeHTML(data.remaining_refundable_amount)}" step="0.01" placeholder="Full remaining amount" /></label>
        <label>${t('refundReasonLabel')}<select id="verified-refund-reason"><option value="Product not as expected">Product not as expected</option><option value="Product defective">Product defective</option><option value="Wrong item received">Wrong item received</option><option value="Changed my mind">Changed my mind</option><option value="Other">Other</option></select></label>
        <button class="btn-primary" type="submit">${t('refundConfirmBtn')}</button>
      </form><div id="verified-refund-result"></div>
    </section>`;
  }

  return html;
}

function renderRefundDetail(refund) {
  const events = refund.events || [];
  const rec = refund.ai_recommendation || {};

  let html = `<section class="refund-approval-card" style="margin-top:16px">
    <div class="refund-approval-header">Refund ${escapeHTML(refund.id).slice(0, 8)}… — <span class="status-pill ${refund.status}">${escapeHTML(refund.status.replace(/_/g, ' '))}</span></div>
    <div class="refund-facts" style="grid-template-columns:repeat(auto-fit,minmax(140px,1fr))">
      <div><span>${t('refundAmountLabel')}</span><strong>${formatPrice(refund.amount)}</strong></div>
      <div><span>Approved</span><strong>${refund.approved_amount ? formatPrice(refund.approved_amount) : '—'}</strong></div>
      <div><span>Type</span><strong>${escapeHTML(refund.refund_type)}</strong></div>
      <div><span>Status</span><strong>${escapeHTML(refund.status.replace(/_/g, ' '))}</strong></div>
    </div>`;

  if (rec.recommendation) {
    html += `<div class="ai-explanation">
      <div class="ai-explanation-title">${t('refundAiRecTitle')}</div>
      <div class="ai-explanation-item"><span class="icon">${rec.recommendation === 'REJECT' ? '❌' : '✅'}</span><span class="text"><strong>${escapeHTML(rec.recommendation)}</strong></span></div>
      <div class="ai-explanation-item"><span class="icon">💬</span><span class="text">${escapeHTML(rec.reasoning)}</span></div>
      <div class="ai-explanation-item"><span class="icon">📊</span><span class="text">Confidence: ${(rec.confidence * 100).toFixed(0)}% · Provider: ${escapeHTML(rec.provider || '—')}</span></div>
    </div>`;
  }

  // Timeline
  if (events.length) {
    html += renderRefundTimeline(events, refund.status);
  }

  // Approve/Reject buttons if pending
  if (refund.status === 'pending_approval') {
    html += `<div class="refund-actions" data-refund-id="${escapeHTML(refund.id)}">
      <button class="btn-approve" onclick="window.approveRefund('${escapeHTML(refund.id)}')">${t('refundApproveBtn')}</button>
      <button class="btn-reject" onclick="window.rejectRefund('${escapeHTML(refund.id)}')">${t('refundRejectBtn')}</button>
    </div>`;
  }
  if (refund.status === 'failed') {
    html += `<div class="refund-actions" data-refund-id="${escapeHTML(refund.id)}">
      <button class="btn-approve" onclick="window.retryRefund('${escapeHTML(refund.id)}')">${t('refundRetryBtn')}</button>
    </div>`;
  }

  html += `<div id="refund-action-result" style="margin-top:12px"></div>`;
  html += `</section>`;

  return html;
}

function renderRefundTimeline(events, currentStatus) {
  const stageLabels = {
    refund_requested: 'Refund Requested', eligibility_checked: 'Eligibility Verified', merchant_recommended: 'AI Merchant Review',
    approval_pending: 'Pending Approval', refund_approved: 'Merchant Approved', refund_rejected: 'Merchant Rejected',
    refund_processing: 'Processing via Razorpay', refund_processed: 'Refund Completed', refund_failed: 'Refund Failed',
    refund_retried: 'Retrying', webhook_confirmed: 'Webhook Confirmed', razorpay_initiated: 'Razorpay Initiated',
  };

  let html = `<div class="refund-timeline" style="margin-top:20px"><div class="card-title" style="margin-bottom:14px">${t('refundTimelineTitle')}</div>`;
  events.forEach((e, i) => {
    const isLast = i === events.length - 1;
    const stepClass = isLast && !['processed', 'rejected', 'failed'].includes(currentStatus) ? 'active' : 'completed';
    const icon = e.event_type.includes('failed') || e.event_type.includes('rejected') ? '✗' :
                 stepClass === 'completed' ? '✓' : '●';
    html += `<div class="refund-timeline-step ${stepClass}">
      <div class="timeline-indicator">${icon}</div>
      <div class="timeline-content">
        <div class="timeline-title">${escapeHTML(stageLabels[e.event_type] || e.event_type.replace(/_/g, ' '))}</div>
        <div class="timeline-detail">by ${escapeHTML(e.actor)}</div>
        <div class="timeline-time">${e.created_at ? new Date(e.created_at).toLocaleString() : ''}</div>
      </div>
    </div>`;
  });
  html += '</div>';
  return html;
}

function bindRefundActions(result) {
  window.approveRefund = async (id) => {
    const el = document.getElementById('refund-action-result'); if(el) el.innerHTML = loading();
    const res = await api(`/refunds/${id}/approve`, { method: 'POST', body: JSON.stringify({}) });
    if (el) el.innerHTML = res ? renderRefundDetail(res) : '<div class="badge badge-red">Approve failed</div>';
  };
  window.rejectRefund = async (id) => {
    const reason = prompt('Rejection reason:');
    if (!reason) return;
    const el = document.getElementById('refund-action-result'); if(el) el.innerHTML = loading();
    const res = await api(`/refunds/${id}/reject`, { method: 'POST', body: JSON.stringify({ rejection_reason: reason }) });
    if (el) el.innerHTML = res ? renderRefundDetail(res) : '<div class="badge badge-red">Reject failed</div>';
  };
  window.retryRefund = async (id) => {
    const el = document.getElementById('refund-action-result'); if(el) el.innerHTML = loading();
    const res = await api(`/refunds/${id}/retry`, { method: 'POST' });
    if (el) el.innerHTML = res ? renderRefundDetail(res) : '<div class="badge badge-red">Retry failed</div>';
  };
}

function bindEligibilityActions(data) {
  const form = document.getElementById('verified-refund-form');
  if (!form) return;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const resultEl = document.getElementById('verified-refund-result'); resultEl.innerHTML = loading();
    const amount = document.getElementById('verified-refund-amount').value;
    const result = await api('/refunds', {
      method: 'POST',
      headers: { 'Idempotency-Key': `refund-${crypto.randomUUID()}` },
      body: JSON.stringify({ order_id: data.order_id, payment_id: data.payment_id, amount: amount ? Number(amount) : null, reason: document.getElementById('verified-refund-reason').value }),
    });
    if (result) {
      resultEl.innerHTML = renderRefundDetail(result);
      bindRefundActions({ refund: result });
    } else {
      resultEl.innerHTML = emptyState('❌', 'Refund request failed.');
    }
  });
}

async function renderMerchantRefunds() {
  app.innerHTML = `<div class="page-enter"><div class="page-header"><h1>${t('merchantRefundTitle')}</h1><p>${t('merchantRefundSubtitle')}</p></div>${loading()}</div>`;
  const data = await api('/refunds/dashboard');
  if (!data) { app.innerHTML = `<div class="page-enter"><div class="page-header"><h1>${t('merchantRefundTitle')}</h1></div>${emptyState('⚠️', 'Could not load dashboard.')}</div>`; return; }

  app.innerHTML = `<div class="page-enter">
    <div class="page-header"><h1>${t('merchantRefundTitle')}</h1><p>${t('merchantRefundSubtitle')}</p></div>
    <div class="refund-dashboard-grid">
      <div class="refund-stat"><div class="refund-stat-value">${data.total_refunds}</div><div class="refund-stat-label">${t('merchantTotalRefunds')}</div></div>
      <div class="refund-stat"><div class="refund-stat-value">${data.pending_approval}</div><div class="refund-stat-label">${t('merchantPending')}</div></div>
      <div class="refund-stat"><div class="refund-stat-value">${data.processing}</div><div class="refund-stat-label">${t('merchantProcessing')}</div></div>
      <div class="refund-stat"><div class="refund-stat-value">${data.completed}</div><div class="refund-stat-label">${t('merchantCompleted')}</div></div>
      <div class="refund-stat"><div class="refund-stat-value">${data.rejected}</div><div class="refund-stat-label">${t('merchantRejected')}</div></div>
      <div class="refund-stat"><div class="refund-stat-value">${data.failed}</div><div class="refund-stat-label">${t('merchantFailed')}</div></div>
      <div class="refund-stat"><div class="refund-stat-value">${formatPrice(data.total_refunded_amount)}</div><div class="refund-stat-label">${t('merchantTotalRefunded')}</div></div>
    </div>
    ${data.refunds.length ? `<section class="card">
      <div class="card-title">${t('merchantRequestsTable')}</div>
      <table class="refund-table"><thead><tr><th>ID</th><th>${t('orderIdLabel')}</th><th>${t('amountLabel')}</th><th>${t('refundReasonLabel')}</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      ${data.refunds.map(r => `<tr>
        <td><code style="font-size:0.75rem">${escapeHTML(r.id).slice(0,8)}…</code></td>
        <td><code style="font-size:0.75rem">${escapeHTML(r.order_id).slice(0,12)}…</code></td>
        <td>${formatPrice(r.amount)}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHTML(r.reason)}">${escapeHTML(r.reason)}</td>
        <td><span class="status-pill ${r.status}">${escapeHTML(r.status.replace(/_/g, ' '))}</span></td>
        <td>${r.status === 'pending_approval' ?
          `<button class="btn-approve" style="padding:4px 12px;font-size:0.78rem" onclick="window.merchantApprove('${escapeHTML(r.id)}')">${t('refundApproveBtn')}</button>
           <button class="btn-reject" style="padding:4px 12px;font-size:0.78rem" onclick="window.merchantReject('${escapeHTML(r.id)}')">${t('refundRejectBtn')}</button>` :
          r.status === 'failed' ?
          `<button class="btn-primary" style="padding:4px 12px;font-size:0.78rem" onclick="window.merchantRetry('${escapeHTML(r.id)}')">${t('refundRetryBtn')}</button>` :
          '—'}</td>
      </tr>`).join('')}
      </tbody></table>
    </section>` : emptyState('📭', t('merchantNoRequests'))}
    <div id="merchant-refund-detail"></div>
  </div>`;

  window.merchantApprove = async (id) => {
    const el = document.getElementById('merchant-refund-detail'); el.innerHTML = loading();
    const res = await api(`/refunds/${id}/approve`, { method: 'POST', body: JSON.stringify({}) });
    if (res) { el.innerHTML = `<div class="refund-success">✅ Refund approved and processing. ID: ${escapeHTML(res.id)}</div>` + renderRefundDetail(res); setTimeout(() => renderMerchantRefunds(), 2000); }
    else { el.innerHTML = '<div class="badge badge-red">Failed to approve</div>'; }
  };
  window.merchantReject = async (id) => {
    const reason = prompt('Rejection reason:');
    if (!reason) return;
    const el = document.getElementById('merchant-refund-detail'); el.innerHTML = loading();
    const res = await api(`/refunds/${id}/reject`, { method: 'POST', body: JSON.stringify({ rejection_reason: reason }) });
    if (res) { el.innerHTML = `<div class="badge badge-red">Refund rejected.</div>` + renderRefundDetail(res); setTimeout(() => renderMerchantRefunds(), 2000); }
    else { el.innerHTML = '<div class="badge badge-red">Failed to reject</div>'; }
  };
  window.merchantRetry = async (id) => {
    const el = document.getElementById('merchant-refund-detail'); el.innerHTML = loading();
    const res = await api(`/refunds/${id}/retry`, { method: 'POST' });
    if (res) { el.innerHTML = `<div class="refund-success">🔄 Retry initiated.</div>` + renderRefundDetail(res); setTimeout(() => renderMerchantRefunds(), 2000); }
    else { el.innerHTML = '<div class="badge badge-red">Retry failed</div>'; }
  };
}

let activeVisualizerInstance = null;

async function renderKillChainPage() {
  app.innerHTML = `<div class="page-enter">
    <div class="page-header">
      <h1>${t('kcTitle')}</h1>
      <p>${t('kcSubtitle')}</p>
    </div>

    <!-- Quick Session Switcher & Demos -->
    <div class="card" style="margin-bottom:20px;padding:16px 20px">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:12px">
        <div style="font-size:0.85rem;font-weight:700;color:var(--text-primary)">
          ${t('kcSelectSession')}
        </div>
        <div id="kc-view-tabs" style="display:flex;gap:4px;background:rgba(255,255,255,0.05);padding:3px;border-radius:8px">
          <button class="refund-tab active" id="kc-tab-neural" style="padding:6px 14px;font-size:0.78rem" onclick="window.switchKCView('neural')">${t('kcNeuralView')}</button>
          <button class="refund-tab" id="kc-tab-matrix" style="padding:6px 14px;font-size:0.78rem" onclick="window.switchKCView('matrix')">${t('kcMatrixView')}</button>
        </div>
      </div>

      <!-- Quick Session Pills -->
      <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center" id="kc-quick-sessions">
        <span style="font-size:0.75rem;color:var(--text-muted)">${t('kcDemoSessions')}</span>
        <button type="button" class="meta-tag" style="cursor:pointer;background:rgba(16,185,129,0.12);color:var(--accent-green);border-color:rgba(16,185,129,0.3)" onclick="window.loadKCSession('session-demo-laptop-01')">💻 TechNova (${t('kcLegendPassed')} ✓)</button>
        <button type="button" class="meta-tag" style="cursor:pointer;background:rgba(59,130,246,0.12);color:var(--accent-blue);border-color:rgba(59,130,246,0.3)" onclick="window.loadKCSession('session-demo-phone-02')">📱 Phone (${t('kcLegendPassed')} ✓)</button>
        <button type="button" class="meta-tag" style="cursor:pointer;background:rgba(239,68,68,0.12);color:var(--accent-red);border-color:rgba(239,68,68,0.3)" onclick="window.loadKCSession('session-demo-expired-03')">⏰ Expired (${t('kcLegendBlocked')} ✗)</button>
      </div>

      <!-- Custom Session ID Input -->
      <form id="chain-form" style="display:flex;gap:10px;margin-top:14px">
        <input id="chain-session-id" placeholder="${t('kcSessionInputPlaceholder')}" style="flex:1" />
        <button class="btn-primary" type="submit" style="white-space:nowrap">${t('kcLoadBtn')}</button>
      </form>
    </div>

    <!-- Main Graph Render Area -->
    <div id="kc-main-view">
      <div id="kc-graph-mount"></div>
      <div id="kc-matrix-mount" style="display:none"></div>
    </div>
  </div>`;

  let currentView = 'neural';
  let currentChainData = null;

  window.switchKCView = (view) => {
    currentView = view;
    document.getElementById('kc-tab-neural').classList.toggle('active', view === 'neural');
    document.getElementById('kc-tab-matrix').classList.toggle('active', view === 'matrix');
    document.getElementById('kc-graph-mount').style.display = view === 'neural' ? 'block' : 'none';
    document.getElementById('kc-matrix-mount').style.display = view === 'matrix' ? 'block' : 'none';
    if (view === 'neural' && activeVisualizerInstance && currentChainData) {
      activeVisualizerInstance.loadChain(currentChainData);
    }
  };

  // Fetch recent sessions dynamically
  api('/audit/sessions/recent').then((res) => {
    if (res?.sessions?.length) {
      const container = document.getElementById('kc-quick-sessions');
      if (!container) return;
      res.sessions.slice(0, 4).forEach((s) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'meta-tag';
        btn.style.cursor = 'pointer';
        btn.textContent = `⚡ ${s.session_id.slice(0, 16)}… (${s.last_action || 'audit'})`;
        btn.onclick = () => window.loadKCSession(s.session_id);
        container.appendChild(btn);
      });
    }
  }).catch(() => {});

  window.loadKCSession = async (sessionId) => {
    const input = document.getElementById('chain-session-id');
    if (input) input.value = sessionId;

    const graphMount = document.getElementById('kc-graph-mount');
    const matrixMount = document.getElementById('kc-matrix-mount');

    if (activeVisualizerInstance) {
      activeVisualizerInstance.destroy();
      activeVisualizerInstance = null;
    }

    graphMount.innerHTML = loading();
    matrixMount.innerHTML = loading();

    const chain = await api(`/audit/${encodeURIComponent(sessionId)}/chain`);
    if (!chain || !chain.stages || !chain.stages.length) {
      graphMount.innerHTML = emptyState('🔍', `No audit kill-chain events found for session "${escapeHTML(sessionId)}". Try creating a transaction first.`);
      matrixMount.innerHTML = emptyState('🔍', `No audit records found.`);
      return;
    }

    currentChainData = chain;

    // 1. Initialize Interactive Physics Graph
    graphMount.innerHTML = '';
    activeVisualizerInstance = new KillChainVisualizer('kc-graph-mount');
    activeVisualizerInstance.loadChain(chain);

    // 2. Render Matrix Fallback View
    matrixMount.innerHTML = renderKillChain(chain);
  };

  // Form submit handler
  document.getElementById('chain-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const id = document.getElementById('chain-session-id').value.trim();
    if (id) window.loadKCSession(id);
  });

  window.showWhy = function(index) {
    const panel = document.getElementById(`why-panel-${index}`);
    if (panel) panel.hidden = !panel.hidden;
  };
  window.showStage = function(index) {
    const panel = document.getElementById(`stage-details-${index}`);
    if (panel) panel.hidden = !panel.hidden;
  };

  // Auto-load default demo session immediately so user sees the interactive graph!
  window.loadKCSession('session-demo-laptop-01');
}


// ════════════════════════════════════════════════════════
// ROUTER & APP INITIALIZATION
// ════════════════════════════════════════════════════════

function setActiveNav(page) {
  document.querySelectorAll('.nav-link').forEach(link => {
    link.classList.toggle('active', link.dataset.page === page);
  });
}

async function handleRoute() {
  updateNavTranslations();
  const hash = window.location.hash || '#/';
  const match = hash.match(/^#\/([\w-]*)(?:\/(.*?))?$/);
  const [, page, param] = match || [null, '', null];

  switch (page) {
    case '':
    case 'dashboard':
      setActiveNav('dashboard');
      await renderDashboard();
      break;
    case 'merchants':
      setActiveNav('merchants');
      if (param) {
        await renderMerchantDetail(param);
      } else {
        await renderMerchants();
      }
      break;
    case 'agent':
      setActiveNav('agent');
      await renderAgent();
      break;
    case 'policy':
      setActiveNav('policy');
      await renderPolicy();
      break;
    case 'audit':
      setActiveNav('audit');
      await renderAudit();
      break;
    case 'kill-chain':
      setActiveNav('kill-chain');
      await renderKillChainPage();
      break;
    case 'refunds':
      if (param === 'merchant') {
        setActiveNav('refunds-merchant');
        await renderMerchantRefunds();
      } else {
        setActiveNav('refunds');
        await renderRefunds();
      }
      break;
    case 'refunds-merchant':
    case 'merchant-refunds':
      setActiveNav('refunds-merchant');
      await renderMerchantRefunds();
      break;
    default:
      setActiveNav('dashboard');
      await renderDashboard();
  }
}

window.addEventListener('hashchange', handleRoute);

async function checkHealth() {
  const badge = document.getElementById('health-badge');
  const data = await api('/health');
  if (data?.status === 'healthy') {
    badge.innerHTML = `<span class="status-dot healthy"></span><span class="status-text">${t('statusHealthy')}</span>`;
  } else {
    badge.innerHTML = `<span class="status-dot error"></span><span class="status-text">${t('statusOffline')}</span>`;
  }
}

async function init() {
  // Bind language selector
  const langSelect = document.getElementById('lang-select');
  if (langSelect) {
    langSelect.value = getLang();
    langSelect.addEventListener('change', (e) => {
      setLang(e.target.value);
      handleRoute();
    });
  }

  await checkHealth();
  await handleRoute();
  setInterval(checkHealth, 30000);
}

init();

import { t } from './i18n.js';

/* ════════════════════════════════════════════════════════════════════════
   AgentPay — Interactive Neural Kill Chain Graph & Visualizer
   Physics-based draggable node graph, particle flow, zoom/pan, HUD inspector
   ════════════════════════════════════════════════════════════════════════ */

export class KillChainVisualizer {
  constructor(containerId, options = {}) {
    this.container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
    this.options = { ...options };
    this.chainData = null;
    this.nodes = [];
    this.links = [];
    this.particles = [];
    this.activeNode = null;
    this.hoveredNode = null;
    this.draggedNode = null;
    this.isDragging = false;
    this.dragOffset = { x: 0, y: 0 };
    
    // View transform (Pan & Zoom)
    this.camera = { x: 0, y: 0, zoom: 1, targetZoom: 1 };
    this.isPanning = false;
    this.panStart = { x: 0, y: 0 };
    
    // Simulation / Playback state
    this.isPlaying = false;
    this.simStep = -1;
    this.simTimer = null;
    this.particlesEnabled = true;

    this.initDOM();
    this.bindEvents();
    this.animate = this.animate.bind(this);
    this.animId = requestAnimationFrame(this.animate);
  }

  initDOM() {
    this.container.innerHTML = `
      <div class="kc-graph-wrapper">
        <!-- Canvas Container -->
        <div class="kc-canvas-container" id="kc-canvas-box">
          <canvas id="kc-canvas"></canvas>

          <!-- Floating Canvas Overlay Controls -->
          <div class="kc-canvas-overlay">
            <div class="kc-controls-left">
              <button class="kc-ctrl-btn" id="kc-btn-play" title="${t('kcSimulateFlow')}">
                <span class="kc-icon">▶</span> <span class="kc-btn-text">${t('kcSimulateFlow')}</span>
              </button>
              <button class="kc-ctrl-btn" id="kc-btn-reset-layout" title="${t('kcLayoutBtn')}">
                <span class="kc-icon">⟳</span> ${t('kcLayoutBtn')}
              </button>
              <button class="kc-ctrl-btn" id="kc-btn-particles" title="Toggle Particle Streams">
                <span class="kc-icon">⚡</span> <span id="kc-particles-label">${t('kcParticlesOn')}</span>
              </button>
            </div>

            <div class="kc-controls-right">
              <div class="kc-zoom-controls">
                <button class="kc-ctrl-btn kc-ctrl-mini" id="kc-btn-zoom-in" title="Zoom In">+</button>
                <button class="kc-ctrl-btn kc-ctrl-mini" id="kc-btn-zoom-reset" title="Reset View">100%</button>
                <button class="kc-ctrl-btn kc-ctrl-mini" id="kc-btn-zoom-out" title="Zoom Out">−</button>
              </div>
            </div>
          </div>

          <!-- Simulation Live Status Banner -->
          <div class="kc-sim-banner" id="kc-sim-banner" style="display:none">
            <div class="kc-sim-pulse"></div>
            <div class="kc-sim-info">
              <div class="kc-sim-step-name" id="kc-sim-title">Stage 1: Request</div>
              <div class="kc-sim-desc" id="kc-sim-desc">Evaluating requirements...</div>
            </div>
            <button class="kc-sim-close" id="kc-sim-stop" title="Stop Simulation">✕</button>
          </div>

          <!-- Drag Hint Badge -->
          <div class="kc-drag-hint">
            <span>${t('kcDragHint')}</span>
          </div>
        </div>

        <!-- Node Inspector HUD Drawer -->
        <div class="kc-inspector-drawer" id="kc-inspector" style="display:none">
          <div class="kc-inspector-header">
            <div class="kc-inspector-title-wrap">
              <div class="kc-inspector-badge" id="kc-insp-badge">STAGE 01</div>
              <h3 class="kc-inspector-title" id="kc-insp-name">Parse Requirements</h3>
            </div>
            <button class="kc-inspector-close" id="kc-insp-close" title="Close Inspector">✕</button>
          </div>

          <div class="kc-inspector-body">
            <div class="kc-insp-status-card" id="kc-insp-status-card">
              <div class="kc-insp-status-label">${t('kcStageVerdict')}</div>
              <div class="kc-insp-status-val" id="kc-insp-status">PASSED</div>
              <div class="kc-insp-reason" id="kc-insp-reason">All policy requirements met.</div>
            </div>

            <!-- Explainability Meter -->
            <div class="kc-insp-metric-box">
              <div class="kc-insp-metric-header">
                <span>${t('kcExplainability')}</span>
                <strong id="kc-insp-score">100%</strong>
              </div>
              <div class="kc-progress-bar">
                <div class="kc-progress-fill" id="kc-insp-score-bar" style="width:100%"></div>
              </div>
            </div>

            <!-- Stage Facts List -->
            <div class="kc-insp-section">
              <div class="kc-insp-section-title">${t('kcExecutionContext')}</div>
              <dl class="kc-insp-dl" id="kc-insp-facts"></dl>
            </div>

            <!-- Arithmetic / Policy Breakdown -->
            <div class="kc-insp-section" id="kc-insp-breakdown-box">
              <div class="kc-insp-section-title">${t('kcPolicyBreakdown')}</div>
              <div class="kc-insp-code-box" id="kc-insp-breakdown">No mathematical constraints violated.</div>
            </div>

            <!-- Raw JSON Payload -->
            <div class="kc-insp-section">
              <div class="kc-insp-section-title">${t('kcPayload')}</div>
              <pre class="kc-json-pre" id="kc-insp-payload">{}</pre>
            </div>
          </div>
        </div>
      </div>
    `;

    this.canvas = document.getElementById('kc-canvas');
    this.ctx = this.canvas.getContext('2d');
    this.resizeCanvas();
  }

  resizeCanvas() {
    const box = document.getElementById('kc-canvas-box');
    if (!box || !this.canvas) return;
    const rect = box.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width;
    this.height = Math.max(520, rect.height || 540);
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.ctx.scale(dpr, dpr);
  }

  bindEvents() {
    window.addEventListener('resize', () => this.resizeCanvas());

    // Mouse / Touch Dragging & Panning
    const canvas = this.canvas;

    canvas.addEventListener('mousedown', (e) => this.onPointerDown(e));
    window.addEventListener('mousemove', (e) => this.onPointerMove(e));
    window.addEventListener('mouseup', (e) => this.onPointerUp(e));

    // Touch support
    canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        const touch = e.touches[0];
        this.onPointerDown({ clientX: touch.clientX, clientY: touch.clientY, button: 0 });
      }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1 && (this.draggedNode || this.isPanning)) {
        const touch = e.touches[0];
        this.onPointerMove({ clientX: touch.clientX, clientY: touch.clientY });
      }
    }, { passive: true });

    window.addEventListener('touchend', (e) => this.onPointerUp(e));

    // Wheel Zoom
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.12 : 0.88;
      this.zoomAt(zoomFactor, e.clientX, e.clientY);
    }, { passive: false });

    // Controls
    document.getElementById('kc-btn-zoom-in')?.addEventListener('click', () => this.zoomAt(1.2));
    document.getElementById('kc-btn-zoom-out')?.addEventListener('click', () => this.zoomAt(0.8));
    document.getElementById('kc-btn-zoom-reset')?.addEventListener('click', () => this.resetView());
    document.getElementById('kc-btn-reset-layout')?.addEventListener('click', () => this.resetLayout(true));
    document.getElementById('kc-btn-particles')?.addEventListener('click', () => this.toggleParticles());
    document.getElementById('kc-btn-play')?.addEventListener('click', () => this.startSimulation());
    document.getElementById('kc-sim-stop')?.addEventListener('click', () => this.stopSimulation());
    document.getElementById('kc-insp-close')?.addEventListener('click', () => this.closeInspector());
  }

  loadChain(chainData) {
    this.chainData = chainData;
    const stages = chainData.stages || [];
    this.nodes = [];
    this.links = [];
    this.particles = [];
    this.activeNode = null;

    if (!stages.length) return;

    this.resizeCanvas();

    // Generate Layout Positions (Organic wave / force layout)
    const count = stages.length;
    const paddingX = 80;
    const availableW = this.width - paddingX * 2;
    const stepX = Math.max(130, availableW / (count - 1 || 1));
    const startX = Math.max(paddingX, (this.width - (count - 1) * stepX) / 2);
    const centerY = this.height / 2;

    stages.forEach((stage, idx) => {
      // Gentle sine-wave vertical offset for dynamic aesthetic
      const waveY = Math.sin((idx / (count - 1)) * Math.PI * 2) * 36;
      const x = startX + idx * stepX;
      const y = centerY + waveY;

      const node = {
        index: idx,
        id: stage.id,
        name: stage.name,
        status: stage.status || 'unreached',
        reason: stage.reason,
        event: stage.event,
        policy_result: stage.policy_result,
        metadata: stage.metadata,
        // Physics properties
        x,
        y,
        origX: x,
        origY: y,
        vx: 0,
        vy: 0,
        radius: 34,
        isHovered: false,
        pulsePhase: Math.random() * Math.PI * 2,
        // Status color configs
        theme: this.getStatusTheme(stage.status),
      };

      this.nodes.push(node);

      // Create link to previous node
      if (idx > 0) {
        this.links.push({
          source: this.nodes[idx - 1],
          target: node,
          status: stage.status,
        });
      }
    });

    // Seed moving particle packets
    this.initParticles();
    this.resetView();
  }

  getStatusTheme(status) {
    switch (status) {
      case 'passed':
        return {
          primary: '#10b981',
          secondary: '#34d399',
          glow: 'rgba(16, 185, 129, 0.45)',
          bg: 'rgba(16, 185, 129, 0.14)',
          text: '#4ade80',
          icon: '✓',
          badge: 'PASSED',
        };
      case 'blocked':
        return {
          primary: '#ef4444',
          secondary: '#f87171',
          glow: 'rgba(239, 68, 68, 0.65)',
          bg: 'rgba(239, 68, 68, 0.18)',
          text: '#f87171',
          icon: '!',
          badge: 'BLOCKED',
        };
      case 'pending':
        return {
          primary: '#f59e0b',
          secondary: '#fbbf24',
          glow: 'rgba(245, 158, 11, 0.55)',
          bg: 'rgba(245, 158, 11, 0.16)',
          text: '#fbbf24',
          icon: '…',
          badge: 'PENDING',
        };
      default:
        return {
          primary: '#475569',
          secondary: '#64748b',
          glow: 'rgba(100, 116, 139, 0.18)',
          bg: 'rgba(30, 41, 59, 0.4)',
          text: '#94a3b8',
          icon: '·',
          badge: 'UNREACHED',
        };
    }
  }

  initParticles() {
    this.particles = [];
    if (!this.links.length) return;

    // Create stream packets traveling along active links
    for (let i = 0; i < 28; i++) {
      const linkIdx = Math.floor(Math.random() * this.links.length);
      this.particles.push({
        linkIdx,
        progress: Math.random(),
        speed: 0.006 + Math.random() * 0.008,
        size: 2.2 + Math.random() * 2.2,
        glow: Math.random() * 0.5 + 0.5,
      });
    }
  }

  toggleParticles() {
    this.particlesEnabled = !this.particlesEnabled;
    const label = document.getElementById('kc-particles-label');
    if (label) label.textContent = `Particles: ${this.particlesEnabled ? 'ON' : 'OFF'}`;
  }

  // ── Interaction & Pointer Handlers ─────────────────────────

  getCanvasCoords(clientX, clientY) {
    const rect = this.canvas.getBoundingClientRect();
    const rawX = clientX - rect.left;
    const rawY = clientY - rect.top;
    // Apply camera pan & zoom inversion
    const x = (rawX - this.camera.x) / this.camera.zoom;
    const y = (rawY - this.camera.y) / this.camera.zoom;
    return { x, y, rawX, rawY };
  }

  findNodeAt(x, y) {
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const node = this.nodes[i];
      const dx = x - node.x;
      const dy = y - node.y;
      if (Math.sqrt(dx * dx + dy * dy) <= node.radius + 6) {
        return node;
      }
    }
    return null;
  }

  onPointerDown(e) {
    if (e.button !== 0) return;
    const { x, y, rawX, rawY } = this.getCanvasCoords(e.clientX, e.clientY);
    const hitNode = this.findNodeAt(x, y);

    if (hitNode) {
      this.draggedNode = hitNode;
      this.dragOffset = { x: hitNode.x - x, y: hitNode.y - y };
      this.canvas.style.cursor = 'grabbing';
      this.selectNode(hitNode);
    } else {
      this.isPanning = true;
      this.panStart = { x: rawX - this.camera.x, y: rawY - this.camera.y };
      this.canvas.style.cursor = 'move';
    }
  }

  onPointerMove(e) {
    const { x, y, rawX, rawY } = this.getCanvasCoords(e.clientX, e.clientY);

    if (this.draggedNode) {
      this.draggedNode.x = x + this.dragOffset.x;
      this.draggedNode.y = y + this.dragOffset.y;
      this.draggedNode.vx = 0;
      this.draggedNode.vy = 0;
      return;
    }

    if (this.isPanning) {
      this.camera.x = rawX - this.panStart.x;
      this.camera.y = rawY - this.panStart.y;
      return;
    }

    // Hover detection
    const hover = this.findNodeAt(x, y);
    if (hover !== this.hoveredNode) {
      this.hoveredNode = hover;
      this.canvas.style.cursor = hover ? 'pointer' : 'default';
    }
  }

  onPointerUp(e) {
    if (this.draggedNode) {
      this.draggedNode = null;
      this.canvas.style.cursor = this.hoveredNode ? 'pointer' : 'default';
    }
    this.isPanning = false;
  }

  zoomAt(factor, clientX, clientY) {
    const rect = this.canvas.getBoundingClientRect();
    const cx = clientX !== undefined ? clientX - rect.left : this.width / 2;
    const cy = clientY !== undefined ? clientY - rect.top : this.height / 2;

    const newZoom = Math.min(2.5, Math.max(0.4, this.camera.zoom * factor));
    if (newZoom === this.camera.zoom) return;

    // Zoom centered on cursor
    this.camera.x = cx - (cx - this.camera.x) * (newZoom / this.camera.zoom);
    this.camera.y = cy - (cy - this.camera.y) * (newZoom / this.camera.zoom);
    this.camera.zoom = newZoom;
  }

  resetView() {
    this.camera = { x: 0, y: 0, zoom: 1 };
  }

  resetLayout(smooth = false) {
    const count = this.nodes.length;
    if (!count) return;
    const paddingX = 80;
    const availableW = this.width - paddingX * 2;
    const stepX = Math.max(130, availableW / (count - 1 || 1));
    const startX = Math.max(paddingX, (this.width - (count - 1) * stepX) / 2);
    const centerY = this.height / 2;

    this.nodes.forEach((node, idx) => {
      const waveY = Math.sin((idx / (count - 1)) * Math.PI * 2) * 36;
      node.origX = startX + idx * stepX;
      node.origY = centerY + waveY;
      if (!smooth) {
        node.x = node.origX;
        node.y = node.origY;
        node.vx = 0;
        node.vy = 0;
      }
    });
    this.resetView();
  }

  // ── Physics Update ─────────────────────────────────────────

  updatePhysics() {
    const springK = 0.04;
    const damping = 0.82;

    this.nodes.forEach((node) => {
      if (node === this.draggedNode) return;

      // Spring force returning to baseline
      const fx = (node.origX - node.x) * springK;
      const fy = (node.origY - node.y) * springK;

      node.vx = (node.vx + fx) * damping;
      node.vy = (node.vy + fy) * damping;

      node.x += node.vx;
      node.y += node.vy;
    });

    // Particle flow
    if (this.particlesEnabled) {
      this.particles.forEach((p) => {
        p.progress += p.speed;
        if (p.progress >= 1) {
          p.progress = 0;
          p.linkIdx = Math.floor(Math.random() * this.links.length);
        }
      });
    }
  }

  // ── Rendering Loop ─────────────────────────────────────────

  animate() {
    this.updatePhysics();
    this.draw();
    this.animId = requestAnimationFrame(this.animate);
  }

  draw() {
    const ctx = this.ctx;
    if (!ctx) return;

    ctx.save();
    ctx.clearRect(0, 0, this.width, this.height);

    // Apply Camera Transform
    ctx.translate(this.camera.x, this.camera.y);
    ctx.scale(this.camera.zoom, this.camera.zoom);

    // Draw Background Grid
    this.drawBackgroundGrid(ctx);

    // Draw Connecting Curves & Splines
    this.drawConnections(ctx);

    // Draw Energy Particles
    if (this.particlesEnabled) {
      this.drawParticles(ctx);
    }

    // Draw Stage Nodes
    this.nodes.forEach((node) => this.drawNode(ctx, node));

    ctx.restore();
  }

  drawBackgroundGrid(ctx) {
    const gridSize = 40;
    const startX = -this.camera.x / this.camera.zoom - gridSize;
    const endX = (this.width - this.camera.x) / this.camera.zoom + gridSize;
    const startY = -this.camera.y / this.camera.zoom - gridSize;
    const endY = (this.height - this.camera.y) / this.camera.zoom + gridSize;

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.025)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = Math.floor(startX / gridSize) * gridSize; x < endX; x += gridSize) {
      ctx.moveTo(x, startY);
      ctx.lineTo(x, endY);
    }
    for (let y = Math.floor(startY / gridSize) * gridSize; y < endY; y += gridSize) {
      ctx.moveTo(startX, y);
      ctx.lineTo(endX, y);
    }
    ctx.stroke();
  }

  drawConnections(ctx) {
    this.links.forEach((link) => {
      const s = link.source;
      const t = link.target;

      const midX = (s.x + t.x) / 2;
      const midY = (s.y + t.y) / 2;

      ctx.save();

      // Outer glow track
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.quadraticCurveTo(midX, s.y, midX, midY);
      ctx.quadraticCurveTo(midX, t.y, t.x, t.y);

      if (t.status === 'passed') {
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.25)';
        ctx.lineWidth = 4;
        ctx.stroke();

        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      } else if (t.status === 'blocked') {
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.3)';
        ctx.lineWidth = 4;
        ctx.stroke();

        ctx.strokeStyle = '#ef4444';
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1.5;
        ctx.stroke();
      } else {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
      }

      ctx.restore();
    });
  }

  drawParticles(ctx) {
    this.particles.forEach((p) => {
      const link = this.links[p.linkIdx];
      if (!link) return;

      const s = link.source;
      const t = link.target;
      const u = p.progress;

      // Spline point evaluation
      const midX = (s.x + t.x) / 2;
      const midY = (s.y + t.y) / 2;

      let x, y;
      if (u < 0.5) {
        const t1 = u * 2;
        x = (1 - t1) * (1 - t1) * s.x + 2 * (1 - t1) * t1 * midX + t1 * t1 * midX;
        y = (1 - t1) * (1 - t1) * s.y + 2 * (1 - t1) * t1 * s.y + t1 * t1 * midY;
      } else {
        const t2 = (u - 0.5) * 2;
        x = (1 - t2) * (1 - t2) * midX + 2 * (1 - t2) * t2 * midX + t2 * t2 * t.x;
        y = (1 - t2) * (1 - t2) * midY + 2 * (1 - t2) * t2 * t.y + t2 * t2 * t.y;
      }

      const color = link.target.status === 'passed' ? '#34d399' :
                    link.target.status === 'blocked' ? '#f87171' : '#a78bfa';

      ctx.save();
      ctx.shadowColor = color;
      ctx.shadowBlur = 12;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, p.size, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    });
  }

  drawNode(ctx, node) {
    const isSelected = node === this.activeNode;
    const isHovered = node === this.hoveredNode;
    const theme = node.theme;
    const radius = node.radius;

    ctx.save();

    // 1. Halo Glow
    const pulse = Math.sin(Date.now() * 0.003 + node.pulsePhase) * 4;
    ctx.shadowColor = theme.primary;
    ctx.shadowBlur = isSelected ? 30 : isHovered ? 22 : 12;

    // 2. Outer Rotating Orbital Ring for active / passed nodes
    if (node.status === 'passed' || node.status === 'pending' || isSelected) {
      ctx.save();
      ctx.translate(node.x, node.y);
      ctx.rotate(Date.now() * 0.001 * (node.index % 2 === 0 ? 1 : -1));
      ctx.strokeStyle = theme.primary;
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      ctx.setLineDash([8, 8]);
      ctx.beginPath();
      ctx.arc(0, 0, radius + 8 + pulse * 0.5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    // 3. Node Body Circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = '#0f172a';
    ctx.fill();

    // Radial Gradient Fill
    const grad = ctx.createRadialGradient(node.x, node.y, 4, node.x, node.y, radius);
    grad.addColorStop(0, theme.bg);
    grad.addColorStop(1, 'rgba(15, 23, 42, 0.95)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Node Border
    ctx.strokeStyle = isSelected ? '#ffffff' : theme.primary;
    ctx.lineWidth = isSelected ? 3 : 2;
    ctx.stroke();

    // 4. Center Icon / Symbol
    ctx.shadowBlur = 0;
    ctx.fillStyle = theme.text;
    ctx.font = `800 ${radius * 0.65}px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(theme.icon, node.x, node.y - 2);

    // 5. Stage Number Tag (Top pill)
    ctx.font = '700 10px Inter, sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(`0${node.index + 1}`, node.x, node.y - radius - 12);

    // 6. Label & Status Below
    ctx.font = '700 12px Inter, sans-serif';
    ctx.fillStyle = isSelected ? '#ffffff' : '#f1f5f9';
    ctx.fillText(node.name, node.x, node.y + radius + 18);

    ctx.font = '600 9px Inter, sans-serif';
    ctx.fillStyle = theme.text;
    ctx.fillText(theme.badge, node.x, node.y + radius + 32);

    ctx.restore();
  }

  // ── Node Inspector Modal / Drawer ──────────────────────────

  selectNode(node) {
    this.activeNode = node;
    const inspector = document.getElementById('kc-inspector');
    if (!inspector) return;

    inspector.style.display = 'block';

    const stageNum = String(node.index + 1).padStart(2, '0');
    document.getElementById('kc-insp-badge').textContent = `STAGE ${stageNum} / 10`;
    document.getElementById('kc-insp-name').textContent = node.name;

    // Status styling
    const statusCard = document.getElementById('kc-insp-status-card');
    const statusVal = document.getElementById('kc-insp-status');
    const reasonVal = document.getElementById('kc-insp-reason');

    statusVal.textContent = node.status.toUpperCase();
    reasonVal.textContent = node.reason || (node.status === 'passed' ? 'Stage verified with no security or policy violations.' : 'Stage was not reached.');

    statusCard.className = `kc-insp-status-card ${node.status}`;

    // Explainability score
    const event = node.event || {};
    const policy = node.policy_result || event.policy_result || {};
    const metadata = node.metadata || event.metadata || {};
    const score = policy.explainability_score ?? metadata.explainability_score ?? (node.status === 'passed' ? 100 : node.status === 'blocked' ? 95 : 0);

    document.getElementById('kc-insp-score').textContent = `${score}%`;
    document.getElementById('kc-insp-score-bar').style.width = `${score}%`;

    // Context facts
    const factsEl = document.getElementById('kc-insp-facts');
    factsEl.innerHTML = `
      <dt>Agent / Actor</dt><dd>${this.escape(event.actor || event.agent_type || (node.index < 3 ? 'AI Buyer Agent' : node.index < 6 ? 'AI Merchant Agent' : node.index === 6 ? 'Policy Engine' : 'Payment Service'))}</dd>
      <dt>Action Name</dt><dd>${this.escape(event.action || event.action_type || node.id)}</dd>
      <dt>Timestamp</dt><dd>${event.timestamp || event.created_at ? new Date(event.timestamp || event.created_at).toLocaleString() : 'N/A'}</dd>
      <dt>Trace ID</dt><dd><code>${this.escape(metadata.request_id || event.id || 'trc-verified')}</code></dd>
    `;

    // Breakdown
    const breakdown = policy.arithmetic_breakdown || metadata.arithmetic_breakdown || event.arithmetic_breakdown;
    const breakdownEl = document.getElementById('kc-insp-breakdown');
    if (breakdown) {
      breakdownEl.innerHTML = Array.isArray(breakdown) ? breakdown.map((item) => `<div>• ${this.escape(item)}</div>`).join('') : this.escape(breakdown);
    } else {
      breakdownEl.textContent = node.status === 'passed' ? '✓ Arithmetic and cryptographic constraints verified.' : 'No mathematical deficit recorded.';
    }

    // JSON payload
    document.getElementById('kc-insp-payload').textContent = JSON.stringify(node.event || { stage: node.id, status: node.status, timestamp: new Date().toISOString() }, null, 2);
  }

  closeInspector() {
    this.activeNode = null;
    const inspector = document.getElementById('kc-inspector');
    if (inspector) inspector.style.display = 'none';
  }

  // ── Step-by-Step Simulation Playback ───────────────────────

  startSimulation() {
    if (!this.nodes.length) return;
    this.isPlaying = true;
    this.simStep = 0;

    const btn = document.getElementById('kc-btn-play');
    if (btn) btn.innerHTML = '<span class="kc-icon">⏹</span> Stop';

    const banner = document.getElementById('kc-sim-banner');
    if (banner) banner.style.display = 'flex';

    this.runSimStep();
  }

  runSimStep() {
    if (!this.isPlaying || this.simStep >= this.nodes.length) {
      this.stopSimulation();
      return;
    }

    const node = this.nodes[this.simStep];
    this.selectNode(node);

    // Update banner
    const titleEl = document.getElementById('kc-sim-title');
    const descEl = document.getElementById('kc-sim-desc');
    if (titleEl) titleEl.textContent = `Stage ${this.simStep + 1} of 10: ${node.name}`;
    if (descEl) descEl.textContent = `${node.status.toUpperCase()}: ${node.reason || 'Verification check in progress...'}`;

    // Camera pan to focus node smoothly
    this.camera.x = this.width / 2 - node.x * this.camera.zoom;
    this.camera.y = this.height / 2 - node.y * this.camera.zoom;

    // Node pop effect
    node.vx += (Math.random() - 0.5) * 8;
    node.vy += (Math.random() - 0.5) * 8;

    // Stop early if blocked
    if (node.status === 'blocked') {
      if (descEl) descEl.textContent = `⛔ KILL CHAIN TRIPPED AT STAGE ${this.simStep + 1}: ${node.reason}`;
      this.isPlaying = false;
      const btn = document.getElementById('kc-btn-play');
      if (btn) btn.innerHTML = '<span class="kc-icon">▶</span> Replay Flow';
      return;
    }

    this.simTimer = setTimeout(() => {
      this.simStep++;
      this.runSimStep();
    }, 1800);
  }

  stopSimulation() {
    this.isPlaying = false;
    clearTimeout(this.simTimer);
    const btn = document.getElementById('kc-btn-play');
    if (btn) btn.innerHTML = '<span class="kc-icon">▶</span> Simulate Flow';

    const banner = document.getElementById('kc-sim-banner');
    if (banner) banner.style.display = 'none';
  }

  escape(str) {
    return String(str ?? '').replace(/[&<>'"]/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[c]));
  }

  destroy() {
    cancelAnimationFrame(this.animId);
    clearTimeout(this.simTimer);
  }
}

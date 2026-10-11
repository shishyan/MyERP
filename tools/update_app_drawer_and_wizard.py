import os

script_path = 'static/app.js'
with open(script_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Redesigned openTicketDrawer implementation
new_openTicketDrawer = '''  function openTicketDrawer(ticketId) {
    const inc = state.incidents.find(i => i.id === ticketId);
    if (!inc) return;

    state.selectedTicket = inc;
    const ciObj = state.cmdbNodes.find(n => n.id === inc.ci);
    state.activeDrawerTab = state.activeDrawerTab || 'overview';

    // Worklogs calculation
    const totalLaborMinutes = (inc.worklogs || []).reduce((acc, w) => acc + ((Number(w.hours) || 0) * 60 + (Number(w.minutes) || 0)), 0);
    const totalLaborCost = (inc.worklogs || []).reduce((acc, w) => acc + (Number(w.cost) || 0), 0);
    const billableLaborCost = (inc.worklogs || []).filter(w => w.isBillable).reduce((acc, w) => acc + (Number(w.cost) || 0), 0);
    const billablePct = totalLaborCost > 0 ? Math.round((billableLaborCost / totalLaborCost) * 100) : 100;

    // Subtasks calculation
    const subtasksList = inc.subtasks || [];
    const completedSubtasks = subtasksList.filter(s => s.completed).length;
    const subtasksPct = subtasksList.length > 0 ? Math.round((completedSubtasks / subtasksList.length) * 100) : 0;

    // SLA Target Hours from policy
    const policyTargetHours = state.slaPolicies && state.slaPolicies[inc.priority] ? state.slaPolicies[inc.priority].resolveHours : (inc.priority === 'P1' ? 1 : 4);

    // Dynamic Lifecycle Transitions Buttons for Header Ribbon & Sidebar
    let ribbonActionBtn = '';
    let transitionsHtml = '';
    if (inc.status === 'NEW') {
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-start" id="ribbon-btn-start">▶ Start Work</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-start" id="trans-btn-start" title="Acknowledge, assign and begin active incident triage">▶ Assign &amp; Start Work</button>
        <button class="btn-transition btn-transition-hold" id="trans-btn-hold" title="Pause SLA clock and place on hold">⏸ Put on Hold</button>
        <button class="btn-transition btn-transition-resolve" id="trans-btn-resolve" title="Record resolution code and close out issue">✓ Resolve Ticket</button>
        <button class="btn-transition btn-transition-close" id="trans-btn-close" title="Cancel or close ticket">✕ Close</button>
      `;
    } else if (inc.status === 'IN_PROGRESS') {
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-resolve" id="ribbon-btn-resolve">✓ Resolve Incident</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-hold" id="trans-btn-hold" title="Pause SLA clock and place on hold">⏸ Put on Hold</button>
        <button class="btn-transition btn-transition-resolve" id="trans-btn-resolve" title="Record resolution code and close out issue">✓ Resolve Ticket</button>
        ${inc.priority !== 'P1' ? `<button class="btn-transition btn-transition-escalate" id="trans-btn-escalate" title="Escalate severity to P1 Critical">⚡ Escalate to P1</button>` : ''}
        <button class="btn-transition btn-transition-close" id="trans-btn-close" title="Close incident">✕ Close</button>
      `;
    } else if (inc.status === 'ON_HOLD') {
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-start" id="ribbon-btn-resume">▶ Resume SLA</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-resume" id="trans-btn-resume" title="Resume active mitigation and unpause SLA timer">▶ Resume Work (Unpause SLA)</button>
        <button class="btn-transition btn-transition-resolve" id="trans-btn-resolve" title="Record resolution code and close out issue">✓ Resolve Ticket</button>
        <button class="btn-transition btn-transition-close" id="trans-btn-close" title="Close incident">✕ Close</button>
      `;
    } else if (inc.status === 'RESOLVED') {
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-reopen" id="ribbon-btn-reopen">⟲ Reopen</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-reopen" id="trans-btn-reopen" title="Reopen incident and restart mitigation">⟲ Reopen Incident</button>
        <button class="btn-transition btn-transition-close" id="trans-btn-close" title="Archive and close permanently">✕ Archive &amp; Close</button>
      `;
    } else { // CLOSED
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-reopen" id="ribbon-btn-reopen">⟲ Reopen</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-reopen" id="trans-btn-reopen" title="Reopen incident">⟲ Reopen Incident</button>
      `;
    }

    // Status Ribbon CSS Class & Label
    let statusBadgeClass = 'status-badge-new';
    let statusLabel = 'New / Triaging';
    if (inc.status === 'IN_PROGRESS') { statusBadgeClass = 'status-badge-progress'; statusLabel = '⚡ In Progress'; }
    else if (inc.status === 'ON_HOLD') { statusBadgeClass = 'status-badge-hold'; statusLabel = `⏸ Paused (${escapeHtml(inc.holdReason || 'Hold')})`; }
    else if (inc.status === 'RESOLVED') { statusBadgeClass = 'status-badge-resolved'; statusLabel = '✓ Resolved'; }
    else if (inc.status === 'CLOSED') { statusBadgeClass = 'status-badge-closed'; statusLabel = 'Closed'; }

    // SLA Countdown text
    const slaText = (inc.status === 'RESOLVED') ? 'MET TARGET' : (inc.status === 'ON_HOLD' ? `PAUSED (${formatSlaTime(inc.slaSecondsRemaining)})` : formatSlaTime(inc.slaSecondsRemaining));

    const techniciansList = state.technicians || DEFAULT_TECHNICIANS;
    const defaultTechRate = techniciansList[0] ? techniciansList[0].rate : 150;

    DOM.drawerContentContainer.innerHTML = `
      <!-- 1. Top Drawer Command Ribbon -->
      <div class="drawer-command-ribbon">
        <div class="drawer-ribbon-left">
          <span class="drawer-ribbon-key-badge">${inc.id}</span>
          <span class="priority-pill pill-${inc.priority.toLowerCase()}" id="drawer-header-priority-pill">${inc.priority}</span>
          <span class="drawer-ribbon-status ${statusBadgeClass}">${statusLabel}</span>
          <span class="drawer-header-title-summary" title="${escapeHtml(inc.title)}">${escapeHtml(inc.title)}</span>
        </div>
        <div class="drawer-ribbon-actions">
          ${ribbonActionBtn}
          <button class="btn-icon-sm" id="btn-close-drawer" title="Close Drawer (Esc)">&times;</button>
        </div>
      </div>

      <!-- 2. Interactive KPI Glass HUD Strip (Zero Wall of White Text) -->
      <div class="drawer-kpi-hud-strip">
        <div class="kpi-hud-card" style="border-left: 3.5px solid ${inc.status === 'ON_HOLD' ? '#f59e0b' : inc.status === 'RESOLVED' ? '#10b981' : '#6366f1'};">
          <div class="kpi-hud-top">
            <span class="kpi-hud-title">SLA Resolution Target</span>
            <span class="kpi-hud-icon">${inc.status === 'ON_HOLD' ? '⏸️' : '⏱️'}</span>
          </div>
          <span class="kpi-hud-val font-mono ${inc.status === 'ON_HOLD' ? 'text-amber' : inc.status === 'RESOLVED' ? 'text-emerald' : 'text-indigo'}">${slaText}</span>
          <span class="kpi-hud-sub">Target: ${policyTargetHours}h • Paused: ${formatDurationShort(inc.totalPausedSeconds || 0)}</span>
        </div>

        <div class="kpi-hud-card" style="border-left: 3.5px solid #f59e0b;">
          <div class="kpi-hud-top">
            <span class="kpi-hud-title">Priority Matrix</span>
            <span class="kpi-hud-icon">⚡</span>
          </div>
          <span class="kpi-hud-val">${inc.priority} Severity</span>
          <span class="kpi-hud-sub">${escapeHtml(inc.impact || 'Enterprise')} × ${escapeHtml(inc.urgency || 'High')}</span>
        </div>

        <div class="kpi-hud-card" style="border-left: 3.5px solid #10b981;">
          <div class="kpi-hud-top">
            <span class="kpi-hud-title">Affected Service CI</span>
            <span class="kpi-hud-icon">🌐</span>
          </div>
          <span class="kpi-hud-val" style="font-size:13.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(inc.ciName || inc.ci)}</span>
          <span class="kpi-hud-sub font-mono">Tier: ${ciObj ? ciObj.tier : '1'} • Provider: ${ciObj ? ciObj.provider : 'Cloud'}</span>
        </div>

        <div class="kpi-hud-card" style="border-left: 3.5px solid #0284c7;">
          <div class="kpi-hud-top">
            <span class="kpi-hud-title">Labor &amp; Subtasks</span>
            <span class="kpi-hud-icon">💵</span>
          </div>
          <span class="kpi-hud-val text-emerald font-mono">$${totalLaborCost.toFixed(2)}</span>
          <span class="kpi-hud-sub">${completedSubtasks}/${subtasksList.length} Tasks Done (${subtasksPct}%)</span>
        </div>
      </div>

      <!-- 3. Segmented Workspace Navigation Tabs (Left Column Focus) -->
      <div class="drawer-erp-workspace">
        
        <!-- Left Column: Tabbed Content Area -->
        <div class="drawer-col-left" style="padding: 0; background: #fafafa;">
          
          <!-- Tab Navigation Bar -->
          <div class="drawer-workspace-tabs">
            <button class="drawer-tab-btn ${state.activeDrawerTab === 'overview' ? 'active' : ''}" data-drawer-tab="overview">
              <span>📋 Overview &amp; Diagnostics</span>
            </button>
            <button class="drawer-tab-btn ${state.activeDrawerTab === 'subtasks' ? 'active' : ''}" data-drawer-tab="subtasks">
              <span>☑️ Action Checklist</span>
              <span class="drawer-tab-badge">${completedSubtasks}/${subtasksList.length}</span>
            </button>
            <button class="drawer-tab-btn ${state.activeDrawerTab === 'worklogs' ? 'active' : ''}" data-drawer-tab="worklogs">
              <span>⏱️ Worklogs &amp; Costs</span>
              <span class="drawer-tab-badge font-mono">$${totalLaborCost.toFixed(0)}</span>
            </button>
            <button class="drawer-tab-btn ${state.activeDrawerTab === 'timeline' ? 'active' : ''}" data-drawer-tab="timeline">
              <span>📜 Audit Stream</span>
              <span class="drawer-tab-badge">${inc.timeline.length}</span>
            </button>
          </div>

          <div style="padding: 20px 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px;">
            
            <!-- TAB PANEL 1: Overview & Diagnostics -->
            <div class="drawer-tab-panel ${state.activeDrawerTab === 'overview' ? 'active' : ''}" id="drawer-tab-overview">
              
              <!-- Executive Summary Card -->
              <div class="drawer-summary-card">
                <h3 class="drawer-summary-title">${escapeHtml(inc.title)}</h3>
                <div class="drawer-title-meta-row">
                  <span>Created: <strong>${inc.createdAt}</strong></span>
                  <span>•</span>
                  <span>AI Triage Confidence: <strong class="text-emerald font-mono">${inc.aiConfidence || '98.2%'}</strong></span>
                  <span>•</span>
                  <span>Caller: <span class="font-mono text-secondary">${escapeHtml(inc.caller)}</span></span>
                </div>
              </div>

              <!-- High-Contrast Dark Telemetry & Log Payload Box (Zero Wall of White Text) -->
              <div class="telemetry-code-block">
                <div class="telemetry-code-header">
                  <div class="telemetry-header-title">
                    <span class="telemetry-dot-red"></span>
                    <span class="telemetry-dot-yellow"></span>
                    <span class="telemetry-dot-green"></span>
                    <span>SYSTEM DIAGNOSTIC TELEMETRY &amp; STACK TRACE</span>
                  </div>
                  <button class="btn-copy-telemetry" id="btn-copy-telemetry-text">Copy Payload</button>
                </div>
                <div class="telemetry-code-content" id="telemetry-code-view">${escapeHtml(inc.description)}</div>
              </div>

              <!-- Autonomous AI Diagnostics Hub (Modern Interactive Tiles) -->
              <div class="erp-section-card" style="border: 1.5px solid #d8b4fe; background: linear-gradient(180deg, #faf5ff 0%, #ffffff 100%);">
                <div class="ai-copilot-top">
                  <div class="ai-copilot-title-group">
                    <span class="ai-star-sparkle">✦</span>
                    <h4 style="color:#581c87; font-weight:800;">Autonomous Sentinel-AI Action Hub</h4>
                  </div>
                  <span class="ai-copilot-badge">Real-time Heuristics</span>
                </div>
                <p class="ai-copilot-subtext">Click any intelligence action below to execute automated graph traversal, diagnostic synthesis, or executive communication drafting.</p>

                <div class="ai-tiles-grid">
                  <button class="btn-ai-tile" id="ai-btn-triage">
                    <span class="tile-icon">⚡</span>
                    <div class="tile-info">
                      <h5>Auto-Triage Analysis</h5>
                      <p>Neural root-cause hypothesis</p>
                    </div>
                  </button>
                  <button class="btn-ai-tile" id="ai-btn-blast">
                    <span class="tile-icon">🌐</span>
                    <div class="tile-info">
                      <h5>CMDB Blast Radius</h5>
                      <p>Traverse graph dependencies</p>
                    </div>
                  </button>
                  <button class="btn-ai-tile" id="ai-btn-runbook">
                    <span class="tile-icon">🛠️</span>
                    <div class="tile-info">
                      <h5>Synthesize Runbook</h5>
                      <p>Diagnostic commands &amp; steps</p>
                    </div>
                  </button>
                  <button class="btn-ai-tile" id="ai-btn-stakeholder">
                    <span class="tile-icon">📢</span>
                    <div class="tile-info">
                      <h5>Draft Stakeholder Update</h5>
                      <p>Customer &amp; leadership memo</p>
                    </div>
                  </button>
                </div>

                <div class="ai-output-box mt-3" id="drawer-ai-output" style="display: none;"></div>
              </div>

            </div>

            <!-- TAB PANEL 2: Remediation Checklist & Subtasks -->
            <div class="drawer-tab-panel ${state.activeDrawerTab === 'subtasks' ? 'active' : ''}" id="drawer-tab-subtasks">
              <div class="erp-section-card">
                <div class="subtasks-progress-box">
                  <div class="progress-header-row">
                    <div class="drawer-section-title mb-0">
                      <span class="sec-icon">☑️</span>
                      <span>Remediation Action Items</span>
                    </div>
                    <span class="font-mono text-indigo font-bold text-xs" id="subtasks-header-count">${completedSubtasks} of ${subtasksList.length} Completed (${subtasksPct}%)</span>
                  </div>
                  <div class="subtasks-track mt-2">
                    <div class="subtasks-bar-fill" style="width: ${subtasksPct}%;"></div>
                  </div>
                </div>

                <!-- Add Subtask Form -->
                <form id="form-add-subtask" class="add-subtask-bar mt-3">
                  <input type="text" id="input-subtask-title" placeholder="Add checklist action (e.g. Verify DB read replicas, Flush cache)..." required>
                  <select id="input-subtask-assignee" class="zen-select" style="height:32px; font-size:11.5px;">
                    ${techniciansList.map(t => `<option value="${escapeHtml(t.name)}">${escapeHtml(t.name)}</option>`).join('')}
                    <option value="Unassigned">Unassigned</option>
                  </select>
                  <button type="submit" class="btn btn-sm btn-zen-primary">+ Add</button>
                </form>

                <!-- Subtasks List -->
                <div class="subtasks-items-list mt-3" id="subtasks-list-container">
                  ${subtasksList.length > 0 ? subtasksList.map(st => `
                    <div class="subtask-item ${st.completed ? 'completed' : ''}" data-subtask-id="${st.id}">
                      <div class="subtask-left">
                        <input type="checkbox" class="subtask-checkbox subtask-toggle" data-subtask-id="${st.id}" ${st.completed ? 'checked' : ''}>
                        <span class="subtask-title-text">${escapeHtml(st.title)}</span>
                      </div>
                      <div style="display:flex; align-items:center; gap:8px;">
                        <span class="subtask-assignee-pill">${escapeHtml(st.assignee)}</span>
                        <button class="btn-del-item btn-del-subtask" data-subtask-id="${st.id}" title="Remove subtask">&times;</button>
                      </div>
                    </div>
                  `).join('') : `
                    <div class="empty-subtasks-hint">
                      No subtasks yet. Add specific remediation steps above.
                    </div>
                  `}
                </div>
              </div>
            </div>

            <!-- TAB PANEL 3: Worklogs & Labor Costing -->
            <div class="drawer-tab-panel ${state.activeDrawerTab === 'worklogs' ? 'active' : ''}" id="drawer-tab-worklogs">
              <div class="erp-section-card">
                <div class="worklogs-summary-strip">
                  <div class="worklog-summary-card">
                    <span class="wl-metric-label">Duration Logged</span>
                    <span class="wl-metric-val font-mono">${formatMinutesToHours(totalLaborMinutes)}</span>
                  </div>
                  <div class="worklog-summary-card">
                    <span class="wl-metric-label">Total Labor Cost</span>
                    <span class="wl-metric-val font-mono text-emerald">$${totalLaborCost.toFixed(2)}</span>
                  </div>
                  <div class="worklog-summary-card">
                    <span class="wl-metric-label">Billing Ratio</span>
                    <span class="wl-metric-val font-mono text-indigo">${billablePct}% Billable</span>
                  </div>
                </div>

                <!-- Add Worklog Form -->
                <div class="add-worklog-card mt-3">
                  <div class="text-xs font-bold text-secondary mb-2">Log Technician Labor Hours</div>
                  <form id="form-add-worklog" style="display:flex; flex-direction:column; gap:8px;">
                    <div class="worklog-inputs-grid">
                      <div>
                        <label class="text-xs text-muted">Technician</label>
                        <select id="input-wl-tech" class="zen-select w-full" style="height:32px;">
                          ${techniciansList.map(t => `<option value="${escapeHtml(t.name)}" data-rate="${t.rate}">${escapeHtml(t.name)} ($${t.rate}/hr)</option>`).join('')}
                        </select>
                      </div>
                      <div style="display:flex; gap:6px;">
                        <div style="flex:1;">
                          <label class="text-xs text-muted">Hours</label>
                          <input type="number" id="input-wl-hours" class="zen-form-control" style="height:32px;" value="1" min="0" max="24">
                        </div>
                        <div style="flex:1;">
                          <label class="text-xs text-muted">Mins</label>
                          <select id="input-wl-mins" class="zen-select w-full" style="height:32px;">
                            <option value="0">0m</option>
                            <option value="15">15m</option>
                            <option value="30" selected>30m</option>
                            <option value="45">45m</option>
                          </select>
                        </div>
                      </div>
                      <div>
                        <label class="text-xs text-muted">Hourly Rate ($/hr)</label>
                        <input type="number" id="input-wl-rate" class="zen-form-control font-mono" style="height:32px;" value="${defaultTechRate}" min="0" step="5">
                      </div>
                    </div>

                    <div>
                      <label class="text-xs text-muted">Work Description / Remediation Notes</label>
                      <input type="text" id="input-wl-desc" class="zen-form-control" placeholder="Describe actions performed during this labor window..." required>
                    </div>

                    <div style="display:flex; align-items:center; justify-content:space-between; margin-top:4px;">
                      <label style="display:inline-flex; align-items:center; gap:6px; font-size:12px; cursor:pointer;">
                        <input type="checkbox" id="check-wl-billable" checked class="zen-checkbox">
                        <span>Billable to department cost center</span>
                      </label>
                      <button type="submit" class="btn btn-sm btn-zen-primary">
                        <span>+ Log Labor Entry</span>
                      </button>
                    </div>
                  </form>
                </div>

                <!-- Worklogs List -->
                <div class="worklog-entries-list mt-3" id="worklogs-list-container">
                  ${(inc.worklogs && inc.worklogs.length > 0) ? inc.worklogs.map(w => `
                    <div class="worklog-row-item">
                      <div class="worklog-row-header">
                        <div class="worklog-tech-badge">
                          <span class="tech-avatar-mini">${escapeHtml(w.technician.substring(0, 2).toUpperCase())}</span>
                          <span>${escapeHtml(w.technician)}</span>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px;">
                          <span class="worklog-cost-pill">$${Number(w.cost).toFixed(2)}</span>
                          <button class="btn-del-item btn-del-worklog" data-wl-id="${w.id}" title="Remove entry">&times;</button>
                        </div>
                      </div>
                      <div class="worklog-meta-line">
                        <span class="font-mono"><strong>${w.hours}h ${w.minutes}m</strong> (@ $${w.rate}/hr)</span>
                        <span>•</span>
                        <span class="${w.isBillable ? 'badge-billable' : 'badge-nonbillable'}">${w.isBillable ? 'Billable' : 'Non-Billable'}</span>
                        <span>•</span>
                        <span>${w.loggedAt}</span>
                      </div>
                      <div class="worklog-desc-text">${escapeHtml(w.description)}</div>
                    </div>
                  `).join('') : `
                    <div class="empty-worklogs-hint">
                      No labor hours recorded yet. Use the form above to track technician time and costs.
                    </div>
                  `}
                </div>
              </div>
            </div>

            <!-- TAB PANEL 4: Activity & Audit Timeline Stream -->
            <div class="drawer-tab-panel ${state.activeDrawerTab === 'timeline' ? 'active' : ''}" id="drawer-tab-timeline">
              <div class="erp-section-card">
                <div class="drawer-section-title">
                  <span class="sec-icon">📜</span>
                  <span>Incident Audit Stream (${inc.timeline.length} Entries)</span>
                </div>

                <div class="timeline-list" id="drawer-timeline-list">
                  ${inc.timeline.map(t => `
                    <div class="timeline-item">
                      <span class="timeline-bullet ${t.isAi ? 'bullet-ai' : ''}"></span>
                      <div class="timeline-item-meta">
                        <strong>${escapeHtml(t.user)}</strong> • ${t.time}
                      </div>
                      <div class="timeline-item-body">${escapeHtml(t.text)}</div>
                    </div>
                  `).join('')}
                </div>

                <div class="add-comment-row mt-3">
                  <input type="text" id="input-drawer-comment" class="add-comment-input" placeholder="Add work note or stakeholder update...">
                  <button class="btn btn-sm btn-zen-primary" id="btn-add-drawer-comment">Log Note</button>
                </div>
              </div>
            </div>

          </div>
        </div>

        <!-- ======================================================== -->
        <!-- RIGHT COLUMN: Governance, People, Classification & CI    -->
        <!-- ======================================================== -->
        <div class="drawer-col-right">
          
          <!-- Lifecycle State Machine Flow Card -->
          <div class="drawer-side-card side-card-accent-indigo">
            <div class="side-card-header">
              <span class="side-card-title">STATUS &amp; LIFECYCLE ACTION</span>
            </div>
            <div>
              <label class="text-xs text-muted">Current ITIL Status</label>
              <select id="drawer-status-select" class="zen-select w-full" style="height:32px; font-weight:700; margin-top:3px;">
                <option value="NEW" ${inc.status === 'NEW' ? 'selected' : ''}>New / Triaging</option>
                <option value="IN_PROGRESS" ${inc.status === 'IN_PROGRESS' ? 'selected' : ''}>In Progress / Mitigating</option>
                <option value="ON_HOLD" ${inc.status === 'ON_HOLD' ? 'selected' : ''}>On Hold / SLA Paused</option>
                <option value="RESOLVED" ${inc.status === 'RESOLVED' ? 'selected' : ''}>Resolved / Mitigated</option>
                <option value="CLOSED" ${inc.status === 'CLOSED' ? 'selected' : ''}>Closed / Archived</option>
              </select>
            </div>
            <div class="mt-3">
              <span class="text-xs text-muted mb-1" style="display:block;">Allowed Actions:</span>
              <div class="transition-actions-row">
                ${transitionsHtml}
              </div>
            </div>
          </div>

          <!-- People & Ownership Card -->
          <div class="drawer-side-card side-card-accent-sky">
            <div class="side-card-header">
              <span class="side-card-title">PEOPLE &amp; ESCALATION</span>
            </div>
            <div class="caller-profile-row">
              <div class="tech-avatar-mini" style="width:34px; height:34px; font-size:13px; background:#4f46e5; color:white;">
                ${escapeHtml((inc.caller || 'AR').substring(0, 2).toUpperCase())}
              </div>
              <div class="caller-details">
                <strong>${escapeHtml(inc.caller || 'alex.rivera@opennow.io')}</strong>
                <span class="text-xs text-muted">Site Reliability Engineering</span>
              </div>
            </div>
            <div class="assignment-meta-lines mt-3">
              <div class="pair-row"><span class="pair-k">Assignment Group:</span><strong class="pair-v text-indigo">${escapeHtml(inc.team)}</strong></div>
              <div class="pair-row"><span class="pair-k">Primary Lead:</span><span class="pair-v">Alex Rivera (Lead)</span></div>
              <div class="pair-row"><span class="pair-k">ITIL State:</span><span class="pair-v font-bold ${inc.status === 'ON_HOLD' ? 'text-amber' : inc.status === 'RESOLVED' ? 'text-emerald' : 'text-indigo'}">${formatStatusLabel(inc.status)}</span></div>
            </div>
          </div>

          <!-- Three-Tier ITIL Classification Card -->
          <div class="drawer-side-card side-card-accent-emerald">
            <div class="side-card-header">
              <span class="side-card-title">3-TIER TAXONOMY</span>
              <span class="badge-tag">ITIL 4</span>
            </div>
            <div class="classification-vertical-stack">
              <div class="form-group mb-2">
                <label class="text-xs text-muted">Category</label>
                <select id="drawer-cat-select" class="zen-select w-full" style="height:30px;"></select>
              </div>
              <div class="form-group mb-2">
                <label class="text-xs text-muted">Subcategory</label>
                <select id="drawer-subcat-select" class="zen-select w-full" style="height:30px;"></select>
              </div>
              <div class="form-group">
                <label class="text-xs text-muted">Item</label>
                <select id="drawer-item-select" class="zen-select w-full" style="height:30px;"></select>
              </div>
            </div>
          </div>

          <!-- Priority Matrix Card -->
          <div class="drawer-side-card side-card-accent-amber">
            <div class="side-card-header">
              <span class="side-card-title">PRIORITY MATRIX</span>
              <span class="priority-pill pill-${inc.priority.toLowerCase()}" id="drawer-matrix-badge">${inc.priority}</span>
            </div>
            <div class="matrix-inputs-stack">
              <div class="form-group mb-2">
                <label class="text-xs text-muted">Impact</label>
                <select id="drawer-impact-select" class="zen-select w-full" style="height:30px;">
                  <option value="Enterprise" ${inc.impact === 'Enterprise' ? 'selected' : ''}>Enterprise (High / Org-wide)</option>
                  <option value="Department" ${inc.impact === 'Department' ? 'selected' : ''}>Department (Medium / Service)</option>
                  <option value="Single User" ${inc.impact === 'Single User' ? 'selected' : ''}>Single User (Low / Localized)</option>
                </select>
              </div>
              <div class="form-group mb-2">
                <label class="text-xs text-muted">Urgency</label>
                <select id="drawer-urgency-select" class="zen-select w-full" style="height:30px;">
                  <option value="Critical" ${inc.urgency === 'Critical' ? 'selected' : ''}>Critical (Immediate Outage)</option>
                  <option value="High" ${inc.urgency === 'High' ? 'selected' : ''}>High (Severe Disruption)</option>
                  <option value="Medium" ${inc.urgency === 'Medium' ? 'selected' : ''}>Medium (Workaround Exists)</option>
                  <option value="Low" ${inc.urgency === 'Low' ? 'selected' : ''}>Low (Minor / Inquiry)</option>
                </select>
              </div>
              <div class="matrix-calc-result-box">
                <span class="matrix-calc-label" id="drawer-matrix-label">${inc.impact || 'Enterprise'} × ${inc.urgency || 'High'} = ${inc.priority}</span>
              </div>
            </div>
          </div>

          <!-- Affected CI & Topology Dependencies -->
          <div class="drawer-side-card">
            <div class="side-card-header">
              <span class="side-card-title">AFFECTED CI &amp; TOPOLOGY</span>
              <span class="badge-tag">${ciObj ? ciObj.tier : 'Service'}</span>
            </div>
            <div class="ci-summary-box">
              <div class="ci-title-link" id="drawer-jump-ci" title="Click to inspect node in CMDB Topology Graph">
                <span class="ci-name font-bold text-indigo">${escapeHtml(inc.ciName || inc.ci)}</span>
                <span class="ci-jump-icon">➔</span>
              </div>
              <div class="ci-submeta font-mono text-xs text-muted mt-1">
                ID: ${inc.ci} • Provider: ${ciObj ? ciObj.provider : 'Cloud AWS'}
              </div>
              
              <div class="ci-dep-links mt-3">
                <div class="dep-link-label text-xs text-muted">Upstream Callers:</div>
                <div class="dep-chips-list-sm mt-1">
                  ${(ciObj && ciObj.upstream && ciObj.upstream.length > 0) ? ciObj.upstream.map(u => `<span class="ci-dep-chip">${u}</span>`).join('') : '<span class="text-xs text-muted">No upstream callers (Edge origin)</span>'}
                </div>

                <div class="dep-link-label text-xs text-muted mt-2">Downstream Dependencies:</div>
                <div class="dep-chips-list-sm mt-1">
                  ${(ciObj && ciObj.downstream && ciObj.downstream.length > 0) ? ciObj.downstream.map(d => `<span class="ci-dep-chip chip-downstream">${d}</span>`).join('') : '<span class="text-xs text-muted">Terminal dependency</span>'}
                </div>
              </div>
            </div>
          </div>

          <!-- Resolution Verification Card (if resolved) -->
          ${inc.status === 'RESOLVED' ? `
            <div class="drawer-side-card" style="background:#ecfdf5; border-color:#a7f3d0;">
              <div class="side-card-header" style="border-bottom-color:#a7f3d0;">
                <span class="side-card-title text-emerald">✓ RESOLUTION DETAILS</span>
                <span class="badge-tag text-emerald">${escapeHtml(inc.resolutionCode || 'Resolved')}</span>
              </div>
              <div class="text-xs" style="color:#065f46; line-height:1.45;">
                <p><strong>Root Cause:</strong> ${escapeHtml(inc.rootCause || 'Root cause eliminated.')}</p>
                ${inc.preventiveAction ? `<p class="mt-2"><strong>Preventive Action:</strong> ${escapeHtml(inc.preventiveAction)}</p>` : ''}
                <p class="mt-2"><strong>FCR:</strong> ${inc.isFcr ? 'Yes (First Call Resolution)' : 'No (Escalated)'}</p>
                <p class="mt-1 text-muted">Resolved at: ${inc.resolvedAt || 'Recently'}</p>
              </div>
            </div>
          ` : ''}

          <!-- On Hold Justification Card (if on hold) -->
          ${inc.status === 'ON_HOLD' ? `
            <div class="drawer-side-card" style="background:#fffbeb; border-color:#fde68a;">
              <div class="side-card-header" style="border-bottom-color:#fde68a;">
                <span class="side-card-title text-amber">⏸️ HOLD JUSTIFICATION</span>
                <span class="badge-tag text-amber">${escapeHtml(inc.holdReason || 'Pending Input')}</span>
              </div>
              <div class="text-xs" style="color:#92400e; line-height:1.45;">
                <p><strong>Justification:</strong> ${escapeHtml(inc.holdNotes || 'Work paused awaiting external dependency.')}</p>
                <p class="mt-2"><strong>Total SLA Time Frozen:</strong> ${formatDurationShort(inc.totalPausedSeconds || 0)}</p>
              </div>
            </div>
          ` : ''}

        </div>
      </div>
    `;

    // Bind Workspace Tabs Navigation
    document.querySelectorAll('.drawer-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tabName = btn.getAttribute('data-drawer-tab');
        state.activeDrawerTab = tabName;
        document.querySelectorAll('.drawer-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.drawer-tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const targetPanel = document.getElementById(`drawer-tab-${tabName}`);
        if (targetPanel) targetPanel.classList.add('active');
      });
    });

    // Bind Copy Telemetry Button
    const btnCopy = document.getElementById('btn-copy-telemetry-text');
    if (btnCopy) {
      btnCopy.addEventListener('click', () => {
        navigator.clipboard.writeText(inc.description);
        btnCopy.textContent = 'Copied!';
        setTimeout(() => { btnCopy.textContent = 'Copy Payload'; }, 1800);
      });
    }

    // Bind Close Button & Backdrop
    const btnCloseDrawer = document.getElementById('btn-close-drawer');
    if (btnCloseDrawer) btnCloseDrawer.addEventListener('click', closeTicketDrawer);
    DOM.drawerBackdrop.classList.add('active');
    DOM.ticketSlideover.classList.add('open');

    // Bind Quick Action Ribbon Buttons
    const ribbonStart = document.getElementById('ribbon-btn-start');
    if (ribbonStart) {
      ribbonStart.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        inc.timeline.unshift({ time: 'Just now', user: 'Alex Rivera (SRE)', text: 'Began mitigation via quick ribbon action.' });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Work started on ${inc.id}. Status: In Progress.`, 'success');
      });
    }
    const ribbonResolve = document.getElementById('ribbon-btn-resolve');
    if (ribbonResolve) ribbonResolve.addEventListener('click', () => openResolutionModal(inc.id));
    const ribbonResume = document.getElementById('ribbon-btn-resume');
    if (ribbonResume) {
      ribbonResume.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        inc.timeline.unshift({ time: 'Just now', user: 'Alex Rivera (SRE)', text: 'Resumed mitigation from hold via ribbon.' });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Mitigation resumed on ${inc.id}. SLA unpaused.`, 'success');
      });
    }
    const ribbonReopen = document.getElementById('ribbon-btn-reopen');
    if (ribbonReopen) {
      ribbonReopen.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        if (inc.slaSecondsRemaining <= 0) inc.slaSecondsRemaining = 3600;
        inc.timeline.unshift({ time: 'Just now', user: 'Alex Rivera (SRE)', text: 'Reopened incident via ribbon action.' });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Incident ${inc.id} reopened!`, 'warning');
      });
    }

    // Bind Jump to CI
    const jumpCi = document.getElementById('drawer-jump-ci');
    if (jumpCi) {
      jumpCi.addEventListener('click', () => {
        closeTicketDrawer();
        switchView('cmdb-topology');
        openCmdbInspector(inc.ci);
      });
    }

    // Populate Cascading Classification in Drawer
    const drawerCat = document.getElementById('drawer-cat-select');
    const drawerSubcat = document.getElementById('drawer-subcat-select');
    const drawerItem = document.getElementById('drawer-item-select');
    if (drawerCat && drawerSubcat && drawerItem) {
      populateClassificationDropdowns(drawerCat, drawerSubcat, drawerItem, inc.category, inc.subcategory, inc.item);
      const onClassChange = () => {
        inc.category = drawerCat.value;
        inc.subcategory = drawerSubcat.value;
        inc.item = drawerItem.value;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: `Updated classification to: ${inc.category} ➔ ${inc.subcategory} ➔ ${inc.item}.`
        });
        showToast('Classification updated successfully.', 'info');
      };
      drawerCat.addEventListener('change', onClassChange);
      drawerSubcat.addEventListener('change', onClassChange);
      drawerItem.addEventListener('change', onClassChange);
    }

    // Setup Priority Matrix Calculator in Drawer
    const drawerImpact = document.getElementById('drawer-impact-select');
    const drawerUrgency = document.getElementById('drawer-urgency-select');
    const drawerMatrixBadge = document.getElementById('drawer-matrix-badge');
    const drawerMatrixLabel = document.getElementById('drawer-matrix-label');
    if (drawerImpact && drawerUrgency) {
      setupPriorityMatrixCalculator(drawerImpact, drawerUrgency, drawerMatrixBadge, drawerMatrixLabel, null, (calcP, imp, urg) => {
        if (inc.priority !== calcP || inc.impact !== imp || inc.urgency !== urg) {
          const oldP = inc.priority;
          inc.impact = imp;
          inc.urgency = urg;
          inc.priority = calcP;
          const headerBadge = document.getElementById('drawer-header-priority-pill');
          if (headerBadge) {
            headerBadge.className = `priority-pill pill-${calcP.toLowerCase()}`;
            headerBadge.textContent = calcP;
          }
          if (oldP !== calcP) {
            inc.timeline.unshift({
              time: 'Just now',
              user: 'Alex Rivera (SRE)',
              text: `Recalculated priority: ${oldP} ➔ ${calcP} based on Impact: ${imp}, Urgency: ${urg}.`
            });
            renderTickets();
            showToast(`Priority recalculated to ${calcP}`, 'info');
          }
        }
      });
    }

    // Lifecycle Action Bar Button Listeners
    const btnStart = document.getElementById('trans-btn-start');
    if (btnStart) {
      btnStart.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Assigned incident and began active mitigation. SLA countdown started.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Work started on ${inc.id}. Status: In Progress.`, 'success');
      });
    }

    const btnHold = document.getElementById('trans-btn-hold');
    if (btnHold) {
      btnHold.addEventListener('click', () => {
        openHoldModal(inc.id);
      });
    }

    const btnResume = document.getElementById('trans-btn-resume');
    if (btnResume) {
      btnResume.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Resumed mitigation from hold. Active SLA clock resumed.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Mitigation resumed on ${inc.id}. SLA unpaused.`, 'success');
      });
    }

    const btnResolve = document.getElementById('trans-btn-resolve');
    if (btnResolve) {
      btnResolve.addEventListener('click', () => {
        openResolutionModal(inc.id);
      });
    }

    const btnClose = document.getElementById('trans-btn-close');
    if (btnClose) {
      btnClose.addEventListener('click', () => {
        inc.status = 'CLOSED';
        inc.isPaused = false;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Incident closed and permanently archived.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Incident ${inc.id} closed.`, 'info');
      });
    }

    const btnReopen = document.getElementById('trans-btn-reopen');
    if (btnReopen) {
      btnReopen.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        if (inc.slaSecondsRemaining <= 0) inc.slaSecondsRemaining = 3600;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Reopened incident. SLA timer restarted.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Incident ${inc.id} reopened!`, 'warning');
      });
    }

    const btnEscalate = document.getElementById('trans-btn-escalate');
    if (btnEscalate) {
      btnEscalate.addEventListener('click', () => {
        inc.priority = 'P1';
        inc.impact = 'Enterprise';
        inc.urgency = 'Critical';
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Manually escalated incident to P1 Critical severity.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`🚨 ${inc.id} escalated to P1 Critical!`, 'error');
      });
    }

    // Status select change
    const statusSelect = document.getElementById('drawer-status-select');
    if (statusSelect) {
      statusSelect.addEventListener('change', (e) => {
        const newStatus = e.target.value;
        if (newStatus === 'RESOLVED') {
          openResolutionModal(inc.id);
        } else if (newStatus === 'ON_HOLD') {
          openHoldModal(inc.id);
        } else {
          inc.status = newStatus;
          inc.isPaused = false;
          inc.timeline.unshift({
            time: 'Just now',
            user: 'Alex Rivera (SRE)',
            text: `Changed status to ${formatStatusLabel(newStatus)}.`
          });
          renderTickets();
          openTicketDrawer(inc.id);
          showToast(`${inc.id} status updated to ${formatStatusLabel(newStatus)}`, 'success');
        }
      });
    }

    // Worklog Technician select auto-rate binding
    const wlTechSelect = document.getElementById('input-wl-tech');
    const wlRateInput = document.getElementById('input-wl-rate');
    if (wlTechSelect && wlRateInput) {
      wlTechSelect.addEventListener('change', () => {
        const selectedOpt = wlTechSelect.options[wlTechSelect.selectedIndex];
        const r = selectedOpt ? selectedOpt.getAttribute('data-rate') : null;
        if (r) wlRateInput.value = r;
      });
    }

    // Worklogs Form Submit
    const formWl = document.getElementById('form-add-worklog');
    if (formWl) {
      formWl.addEventListener('submit', (e) => {
        e.preventDefault();
        const tech = document.getElementById('input-wl-tech').value;
        const hours = parseInt(document.getElementById('input-wl-hours').value, 10) || 0;
        const mins = parseInt(document.getElementById('input-wl-mins').value, 10) || 0;
        const rate = parseFloat(document.getElementById('input-wl-rate').value) || 150;
        const desc = document.getElementById('input-wl-desc').value.trim();
        const isBillable = document.getElementById('check-wl-billable').checked;

        if (hours === 0 && mins === 0) {
          showToast('Please enter at least 15 minutes of work time.', 'error');
          return;
        }

        const cost = ((hours + mins / 60) * rate);
        const newWl = {
          id: `WL-${Date.now()}`,
          technician: tech,
          hours: hours,
          minutes: mins,
          rate: rate,
          cost: parseFloat(cost.toFixed(2)),
          isBillable: isBillable,
          description: desc,
          loggedAt: 'Just now'
        };

        if (!inc.worklogs) inc.worklogs = [];
        inc.worklogs.unshift(newWl);

        inc.timeline.unshift({
          time: 'Just now',
          user: tech,
          text: `Logged ${hours}h ${mins}m labor ($${cost.toFixed(2)}): ${desc}`
        });

        openTicketDrawer(inc.id);
        showToast(`⏱️ Logged ${hours}h ${mins}m ($${cost.toFixed(2)}) labor cost.`, 'success');
      });
    }

    // Delete Worklog entry
    document.querySelectorAll('.btn-del-worklog').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const wlId = btn.getAttribute('data-wl-id');
        inc.worklogs = (inc.worklogs || []).filter(w => w.id !== wlId);
        openTicketDrawer(inc.id);
        showToast('Worklog entry removed.', 'info');
      });
    });

    // Subtasks Add Submit
    const formSubtask = document.getElementById('form-add-subtask');
    if (formSubtask) {
      formSubtask.addEventListener('submit', (e) => {
        e.preventDefault();
        const title = document.getElementById('input-subtask-title').value.trim();
        const assignee = document.getElementById('input-subtask-assignee').value;
        if (!title) return;

        const newSt = {
          id: `SUB-${Date.now()}`,
          title: title,
          assignee: assignee,
          completed: false,
          completedAt: null
        };

        if (!inc.subtasks) inc.subtasks = [];
        inc.subtasks.push(newSt);

        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: `Added checklist subtask: "${title}" assigned to ${assignee}.`
        });

        openTicketDrawer(inc.id);
        showToast(`Added checklist subtask.`, 'success');
      });
    }

    // Toggle Subtask Checkbox
    document.querySelectorAll('.subtask-toggle').forEach(chk => {
      chk.addEventListener('change', () => {
        const stId = chk.getAttribute('data-subtask-id');
        const st = (inc.subtasks || []).find(s => s.id === stId);
        if (st) {
          st.completed = chk.checked;
          st.completedAt = chk.checked ? 'Just now' : null;
          inc.timeline.unshift({
            time: 'Just now',
            user: 'Alex Rivera (SRE)',
            text: `${st.completed ? 'Completed' : 'Unchecked'} checklist task: "${st.title}".`
          });
          openTicketDrawer(inc.id);
          showToast(st.completed ? '✓ Subtask marked complete.' : 'Subtask unchecked.', 'info');
        }
      });
    });

    // Delete Subtask
    document.querySelectorAll('.btn-del-subtask').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const stId = btn.getAttribute('data-subtask-id');
        inc.subtasks = (inc.subtasks || []).filter(s => s.id !== stId);
        openTicketDrawer(inc.id);
        showToast('Subtask removed from checklist.', 'info');
      });
    });

    // Activity Timeline Comment Add
    const commentInput = document.getElementById('input-drawer-comment');
    const commentBtn = document.getElementById('btn-add-drawer-comment');
    if (commentBtn && commentInput) {
      const submitComment = () => {
        const text = commentInput.value.trim();
        if (!text) return;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: text
        });
        commentInput.value = '';
        openTicketDrawer(inc.id);
        showToast('Work note logged to timeline.', 'info');
      };
      commentBtn.addEventListener('click', submitComment);
      commentInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitComment();
      });
    }

    bindAiCopilotButtons(inc);
  }
'''

# Find boundaries of openTicketDrawer in content
target_start = '  function openTicketDrawer(ticketId) {'
target_end = '  function closeTicketDrawer() {'

start_idx = content.find(target_start)
end_idx = content.find(target_end)

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_openTicketDrawer + '\n\n' + content[end_idx:]
    print("SUCCESS: Updated openTicketDrawer!")
else:
    print(f"ERROR: Could not find openTicketDrawer boundaries! start: {start_idx}, end: {end_idx}")

# 2. Add Wizard step switching logic and bindings
wizard_logic = '''
  // =========================================================================
  // INTERACTIVE 4-STEP WIZARD ENGINE (ZERO COGNITIVE OVERLOAD)
  // =========================================================================

  function switchWizardStep(stepNum) {
    state.wizardStep = stepNum;

    // 1. Update Stepper Tabs
    for (let i = 1; i <= 4; i++) {
      const tab = document.getElementById(`wizard-tab-${i}`);
      const conn = document.getElementById(`wizard-conn-${i}`);

      if (tab) {
        tab.classList.remove('active', 'completed');
        if (i < stepNum) {
          tab.classList.add('completed');
        } else if (i === stepNum) {
          tab.classList.add('active');
        }
      }

      if (conn) {
        if (i < stepNum) {
          conn.classList.add('active');
        } else {
          conn.classList.remove('active');
        }
      }
    }

    // 2. Update Counter Pill
    const counter = document.getElementById('wizard-step-counter');
    if (counter) counter.textContent = `Step ${stepNum} of 4`;

    // 3. Toggle Wizard Panels
    document.querySelectorAll('.wizard-panel').forEach(panel => {
      panel.style.display = 'none';
      panel.classList.remove('active');
    });

    const activePanel = document.getElementById(`wizard-panel-${stepNum}`);
    if (activePanel) {
      activePanel.style.display = 'block';
      activePanel.classList.add('active');
    }

    // Focus first input of panel
    if (stepNum === 1 && DOM.inputTicketTitle) DOM.inputTicketTitle.focus();
  }
'''

# In openCreateModal, call switchWizardStep(1)
if 'function openCreateModal(defaults = {}) {' in content:
    # replace openCreateModal definition
    modal_start = '  function openCreateModal(defaults = {}) {'
    modal_end = '  function closeCreateModal() {'
    
    m_start = content.find(modal_start)
    m_end = content.find(modal_end)
    
    new_openCreateModal = '''  function openCreateModal(defaults = {}) {
    switchWizardStep(1);

    if (defaults.ci && DOM.selectTicketCi) DOM.selectTicketCi.value = defaults.ci;

    if (DOM.inputTicketTitle) DOM.inputTicketTitle.value = '';
    if (DOM.inputTicketDesc) DOM.inputTicketDesc.value = '';
    if (DOM.liveAiCopilotContent) {
      DOM.liveAiCopilotContent.innerHTML = `
        <div class="ai-empty-prompt">
          <div class="ai-pulsing-rings">
            <div class="ring-1"></div>
            <div class="ring-2"></div>
          </div>
          <p>AI Copilot actively analyzes the symptoms entered in Step 1 to predict root cause, blast radius risk, and recommended runbook steps.</p>
        </div>
      `;
    }

    populateClassificationDropdowns(
      DOM.selectTicketCategory,
      DOM.selectTicketSubcategory,
      DOM.selectTicketItem,
      defaults.category || 'Database & Storage',
      defaults.subcategory,
      defaults.item
    );

    if (DOM.selectTicketImpact) DOM.selectTicketImpact.value = defaults.impact || 'Enterprise';
    if (DOM.selectTicketUrgency) DOM.selectTicketUrgency.value = defaults.urgency || (defaults.priority === 'P1' ? 'Critical' : defaults.priority === 'P3' ? 'Medium' : 'High');

    setupPriorityMatrixCalculator(
      DOM.selectTicketImpact,
      DOM.selectTicketUrgency,
      DOM.createPriorityPreviewBadge,
      DOM.createPriorityCalcLabel,
      DOM.selectTicketPriority
    );

    if (defaults.category || defaults.ci) {
      applyBusinessRuleToCreateModal();
    }

    if (DOM.createModalBackdrop) DOM.createModalBackdrop.classList.add('open');
    if (DOM.inputTicketTitle) DOM.inputTicketTitle.focus();
  }
'''
    content = content[:m_start] + wizard_logic + '\n' + new_openCreateModal + '\n' + content[m_end:]
    print("SUCCESS: Added switchWizardStep and updated openCreateModal!")

# Bind wizard navigation buttons inside bindEvents
wizard_event_bindings = '''
    // Interactive 4-Step Wizard Navigation
    document.querySelectorAll('.btn-wizard-next').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const nextStep = parseInt(btn.getAttribute('data-next-step'), 10);
        
        // Validate Step 1
        if (state.wizardStep === 1) {
          const t = DOM.inputTicketTitle ? DOM.inputTicketTitle.value.trim() : '';
          const d = DOM.inputTicketDesc ? DOM.inputTicketDesc.value.trim() : '';
          if (!t) {
            showToast('Please enter an incident title before proceeding.', 'error');
            DOM.inputTicketTitle.focus();
            return;
          }
          if (!d) {
            showToast('Please provide telemetry symptoms or diagnostic details.', 'error');
            DOM.inputTicketDesc.focus();
            return;
          }
        }
        
        switchWizardStep(nextStep);
      });
    });

    document.querySelectorAll('.btn-wizard-prev').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const prevStep = parseInt(btn.getAttribute('data-prev-step'), 10);
        switchWizardStep(prevStep);
      });
    });

    document.querySelectorAll('.wizard-step-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const stepNum = parseInt(tab.getAttribute('data-wizard-step'), 10);
        // Only allow jumping back or to completed steps
        if (stepNum <= state.wizardStep || tab.classList.contains('completed')) {
          switchWizardStep(stepNum);
        }
      });
    });
'''

# Insert wizard_event_bindings into bindEvents
bind_target = '    if (DOM.formCreateTicket) {'
b_idx = content.find(bind_target)
if b_idx != -1:
    content = content[:b_idx] + wizard_event_bindings + '\n' + content[b_idx:]
    print("SUCCESS: Bound wizard navigation buttons!")

with open(script_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: All updates written to static/app.js!")

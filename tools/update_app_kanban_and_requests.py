import os

script_path = 'static/app.js'
with open(script_path, 'r', encoding='utf-8') as f:
    js = f.read()

# 1. Add DEFAULT_SERVICE_REQUESTS right before state definition
default_requests_code = '''
  const DEFAULT_SERVICE_REQUESTS = [
    {
      id: 'REQ-101',
      title: 'MacBook Pro 16" M3 Max (64GB RAM, 1TB SSD) Developer Workstation',
      catalogItem: 'Developer Workstation (MacBook Pro M3 Max)',
      category: 'Hardware & Devices',
      requester: 'maya.patel@opennow.io',
      requesterName: 'Maya Patel',
      department: 'Site Reliability Engineering',
      priority: 'P2',
      status: 'IN_PROGRESS',
      stage: 'In Procurement / Asset Tagging',
      approver: 'Sarah Lin (Engineering Director)',
      approvalStatus: 'Approved by Director',
      assignedTeam: 'IT-Asset-Management',
      assignedTo: 'Carlos Mendes',
      createdAt: '2 hours ago',
      slaDue: 'Tomorrow 18:00 UTC (22h left)',
      slaHoursRemaining: 22,
      cost: 3899.00,
      justification: 'New hire onboarding for Principal Distributed Systems Architect.',
      specs: { 'Chip': 'Apple M3 Max (16-core CPU)', 'Unified Memory': '64GB', 'Storage': '1TB NVMe', 'Peripherals': 'Dual Studio Displays' }
    },
    {
      id: 'REQ-102',
      title: 'Production AWS VPC Cross-Account Peering & IAM ReadRole',
      catalogItem: 'Cloud Infrastructure / AWS IAM Role',
      category: 'Cloud & Access',
      requester: 'elena.rostova@opennow.io',
      requesterName: 'Elena Rostova',
      department: 'Payment Engineering',
      priority: 'P1',
      status: 'NEW',
      stage: 'Pending SecOps Approval',
      approver: 'Marcus Vance (Principal SecOps)',
      approvalStatus: 'Pending Security Review',
      assignedTeam: 'Cloud-Infra',
      assignedTo: 'Sarah Lin',
      createdAt: '45 mins ago',
      slaDue: 'Today 21:00 UTC (4h left)',
      slaHoursRemaining: 4,
      cost: 0.00,
      justification: 'Payment reconciliation microservice migration requires access to analytics Aurora RDS read replica.',
      specs: { 'Account': 'AWS Production (Acct: 492019481)', 'Role Requested': 'arn:aws:iam::role/FinTechPeeringRole', 'MFA Enforced': 'Yes' }
    },
    {
      id: 'REQ-103',
      title: 'JetBrains All Products Pack Enterprise Subscription Renewal',
      catalogItem: 'Software Development IDE License',
      category: 'Software & SaaS',
      requester: 'david.chen@opennow.io',
      requesterName: 'David Chen',
      department: 'Database Operations',
      priority: 'P3',
      status: 'RESOLVED',
      stage: 'Fulfilled & Delivered',
      approver: 'Alex Rivera (Lead Architect)',
      approvalStatus: 'Approved',
      assignedTeam: 'IT-Software-Procurement',
      assignedTo: 'Carlos Mendes',
      createdAt: '1 day ago',
      slaDue: '✓ Delivered within SLA',
      slaHoursRemaining: 0,
      cost: 499.00,
      justification: 'Annual license renewal for DataGrip and IntelliJ Ultimate for database performance tuning.',
      specs: { 'Vendor': 'JetBrains', 'Seats': '1 Enterprise Seat', 'License Key': 'JB-ENT-9942-8812-FL' }
    },
    {
      id: 'REQ-104',
      title: 'High-Throughput Kafka Cluster Dedicated Topic Provisioning',
      catalogItem: 'Event Bus / Kafka Dedicated Topic',
      category: 'Cloud & Access',
      requester: 'kevin.zhao@opennow.io',
      requesterName: 'Kevin Zhao',
      department: 'Event Analytics',
      priority: 'P2',
      status: 'IN_PROGRESS',
      stage: 'Terraform Automation Running',
      approver: 'Alex Rivera (Lead Architect)',
      approvalStatus: 'Approved',
      assignedTeam: 'SRE-Core',
      assignedTo: 'Alex Rivera',
      createdAt: '3 hours ago',
      slaDue: 'Today 23:00 UTC (6h left)',
      slaHoursRemaining: 6,
      cost: 150.00,
      justification: 'Ingesting 120,000 real-time checkout telemetry events per second requires 12 partitions with 7-day retention.',
      specs: { 'Topic Name': 'orders.payment.telemetry.v2', 'Partitions': '12', 'Replication Factor': '3', 'Cleanup Policy': 'delete' }
    }
  ];
'''

# Insert DEFAULT_SERVICE_REQUESTS before `const state = {`
if 'const DEFAULT_SERVICE_REQUESTS' not in js:
    state_decl = '  const state = {'
    js = js.replace(state_decl, default_requests_code + '\n' + state_decl, 1)
    print("SUCCESS: Added DEFAULT_SERVICE_REQUESTS!")

# In state object, add serviceRequests & kanbanTypeFilter
if 'serviceRequests:' not in js:
    target_state_prop = 'incidents: SAMPLE_INCIDENTS,'
    new_state_props = '''incidents: SAMPLE_INCIDENTS,
    serviceRequests: DEFAULT_SERVICE_REQUESTS,
    kanbanTypeFilter: 'ALL',
    kanbanPriorityFilter: 'ALL',
    requestsStageFilter: 'ALL','''
    js = js.replace(target_state_prop, new_state_props, 1)
    print("SUCCESS: Added serviceRequests & filters to state!")

# Add Unified Kanban Board renderer and Service Requests management functions
unified_engines = '''
  // =========================================================================
  // UNIFIED ENTERPRISE KANBAN OPERATIONS DASHBOARD (ALL OPEN WORK ITEMS)
  // =========================================================================

  function renderUnifiedKanbanBoard() {
    // 1. Aggregate All Open Work Items Across 4 ITIL Streams
    const allWorkItems = [];

    // Stream A: Incidents
    state.incidents.forEach(inc => {
      allWorkItems.push({
        id: inc.id,
        type: 'INCIDENT',
        typeLabel: '🚨 INCIDENT',
        typeClass: 'type-badge-incident',
        title: inc.title,
        priority: inc.priority,
        status: inc.status,
        metaLine: `${inc.ciName || inc.ci} • ${inc.team}`,
        slaTime: inc.slaSecondsRemaining,
        slaText: (inc.status === 'ON_HOLD' || inc.isPaused) ? `⏸ Paused (${escapeHtml(inc.holdReason || 'Hold')})` : inc.status === 'RESOLVED' ? '✓ Met SLA' : `⏱ ${formatSlaTime(inc.slaSecondsRemaining)}`,
        assignee: inc.team || 'SRE',
        raw: inc
      });
    });

    // Stream B: Problems
    state.problems.forEach(p => {
      allWorkItems.push({
        id: p.id,
        type: 'PROBLEM',
        typeLabel: '🔍 PROBLEM',
        typeClass: 'type-badge-problem',
        title: p.title,
        priority: 'P2',
        status: p.status === 'Resolved' ? 'RESOLVED' : p.isKedb ? 'ON_HOLD' : 'IN_PROGRESS',
        metaLine: `${p.ciName} • ${p.category}`,
        slaTime: 7200,
        slaText: p.isKedb ? '★ KEDB Published' : 'Investigating',
        assignee: 'Problem Ops',
        raw: p
      });
    });

    // Stream C: Changes
    state.changes.forEach(chg => {
      const isApproved = chg.cabStatus.includes('Approved');
      allWorkItems.push({
        id: chg.id,
        type: 'CHANGE',
        typeLabel: '🔄 CHANGE',
        typeClass: 'type-badge-change',
        title: chg.title,
        priority: chg.type === 'Emergency' ? 'P1' : 'P2',
        status: isApproved ? 'IN_PROGRESS' : 'NEW',
        metaLine: `${chg.ciName} • ${chg.type} Change`,
        slaTime: 14400,
        slaText: chg.scheduled,
        assignee: chg.lead,
        raw: chg
      });
    });

    // Stream D: Service Requests
    (state.serviceRequests || []).forEach(req => {
      allWorkItems.push({
        id: req.id,
        type: 'REQUEST',
        typeLabel: '📦 SERVICE REQ',
        typeClass: 'type-badge-request',
        title: req.title,
        priority: req.priority,
        status: req.status,
        metaLine: `${req.catalogItem} • ${req.requesterName}`,
        slaTime: req.slaHoursRemaining * 3600,
        slaText: req.slaDue,
        assignee: req.assignedTeam,
        raw: req
      });
    });

    // Update Counts in Toolbar
    const countAllEl = document.getElementById('count-kanban-all');
    if (countAllEl) countAllEl.textContent = allWorkItems.length;
    const countIncEl = document.getElementById('count-kanban-inc');
    if (countIncEl) countIncEl.textContent = state.incidents.length;
    const countPrbEl = document.getElementById('count-kanban-prb');
    if (countPrbEl) countPrbEl.textContent = state.problems.length;
    const countChgEl = document.getElementById('count-kanban-chg');
    if (countChgEl) countChgEl.textContent = state.changes.length;
    const countReqEl = document.getElementById('count-kanban-req');
    if (countReqEl) countReqEl.textContent = (state.serviceRequests || []).length;

    // Apply Filter Type
    let filtered = allWorkItems;
    if (state.kanbanTypeFilter && state.kanbanTypeFilter !== 'ALL') {
      filtered = filtered.filter(i => i.type === state.kanbanTypeFilter);
    }

    // Apply Priority Filter
    if (state.kanbanPriorityFilter && state.kanbanPriorityFilter !== 'ALL') {
      filtered = filtered.filter(i => i.priority === state.kanbanPriorityFilter);
    }

    // Apply Search Filter
    const searchVal = (document.getElementById('kanban-filter-search')?.value || '').toLowerCase().trim();
    if (searchVal) {
      filtered = filtered.filter(i => 
        i.title.toLowerCase().includes(searchVal) || 
        i.id.toLowerCase().includes(searchVal) || 
        i.metaLine.toLowerCase().includes(searchVal) ||
        i.assignee.toLowerCase().includes(searchVal)
      );
    }

    // Distribute into 4 Kanban Columns
    const cols = {
      NEW: [],
      IN_PROGRESS: [],
      ON_HOLD: [],
      RESOLVED: []
    };

    filtered.forEach(item => {
      if (cols[item.status]) {
        cols[item.status].push(item);
      } else {
        cols.NEW.push(item);
      }
    });

    const renderCard = (item) => {
      const pClass = (item.priority || 'P3').toLowerCase();
      return `
        <div class="ticket-card card-${pClass}" data-item-type="${item.type}" data-item-id="${item.id}" style="cursor:pointer;">
          <div class="kanban-item-headline">
            <span class="kanban-type-badge ${item.typeClass}">${item.typeLabel}</span>
            <div style="display:flex; align-items:center; gap:6px;">
              <span class="ticket-key font-mono" style="font-size:12px;">${item.id}</span>
              <span class="priority-pill pill-${pClass}">${item.priority}</span>
            </div>
          </div>
          <div class="ticket-title" style="font-size:13px; font-weight:700; margin-bottom:6px;">${escapeHtml(item.title)}</div>
          <div class="ticket-meta-tags" style="margin-bottom:8px;">
            <span class="ci-pill">${escapeHtml(item.metaLine)}</span>
          </div>
          <div class="ticket-card-footer">
            <span class="sla-timer-tag ${item.status === 'ON_HOLD' ? 'sla-paused' : 'sla-safe'}">${item.slaText}</span>
            <span class="team-pill" style="font-size:11px;">${escapeHtml(item.assignee)}</span>
          </div>
        </div>
      `;
    };

    if (DOM.cardsNew) DOM.cardsNew.innerHTML = cols.NEW.map(renderCard).join('');
    if (DOM.cardsInProgress) DOM.cardsInProgress.innerHTML = cols.IN_PROGRESS.map(renderCard).join('');
    if (DOM.cardsOnHold) DOM.cardsOnHold.innerHTML = cols.ON_HOLD.map(renderCard).join('');
    if (DOM.cardsResolved) DOM.cardsResolved.innerHTML = cols.RESOLVED.map(renderCard).join('');

    if (DOM.colCountNew) DOM.colCountNew.textContent = cols.NEW.length;
    if (DOM.colCountInProgress) DOM.colCountInProgress.textContent = cols.IN_PROGRESS.length;
    if (DOM.colCountOnHold) DOM.colCountOnHold.textContent = cols.ON_HOLD.length;
    if (DOM.colCountResolved) DOM.colCountResolved.textContent = cols.RESOLVED.length;

    // Bind card click triggers across all work item types
    document.querySelectorAll('#kanban-container .ticket-card').forEach(card => {
      card.addEventListener('click', () => {
        const itemType = card.getAttribute('data-item-type');
        const itemId = card.getAttribute('data-item-id');

        if (itemType === 'INCIDENT') {
          openTicketDrawer(itemId);
        } else if (itemType === 'PROBLEM') {
          open5WhysModal(itemId);
        } else if (itemType === 'CHANGE') {
          switchView('change-management');
          showToast(`Inspecting change request ${itemId}.`, 'info');
        } else if (itemType === 'REQUEST') {
          openServiceRequestDrawer(itemId);
        }
      });
    });
  }

  // =========================================================================
  // SERVICE REQUESTS QUEUE & FULFILLMENT MANAGEMENT
  // =========================================================================

  function renderServiceRequests() {
    const tbody = document.getElementById('requests-table-body');
    if (!tbody) return;

    let requests = state.serviceRequests || [];
    
    // Update KPI Header Metrics
    const statActive = document.getElementById('stat-requests-active');
    if (statActive) statActive.textContent = `${requests.filter(r => r.status !== 'RESOLVED').length} Active`;
    const statAppr = document.getElementById('stat-requests-approval');
    if (statAppr) statAppr.textContent = `${requests.filter(r => r.status === 'NEW').length} Pending`;
    const statFulfill = document.getElementById('stat-requests-fulfillment');
    if (statFulfill) statFulfill.textContent = `${requests.filter(r => r.status === 'IN_PROGRESS').length} In Progress`;

    // Filter Stage
    if (state.requestsStageFilter && state.requestsStageFilter !== 'ALL') {
      if (state.requestsStageFilter === 'Pending Approval') {
        requests = requests.filter(r => r.status === 'NEW');
      } else if (state.requestsStageFilter === 'In Fulfillment') {
        requests = requests.filter(r => r.status === 'IN_PROGRESS');
      } else if (state.requestsStageFilter === 'Fulfilled') {
        requests = requests.filter(r => r.status === 'RESOLVED');
      }
    }

    // Filter Search
    const search = (document.getElementById('requests-filter-search')?.value || '').toLowerCase().trim();
    if (search) {
      requests = requests.filter(r => 
        r.id.toLowerCase().includes(search) || 
        r.title.toLowerCase().includes(search) || 
        r.requesterName.toLowerCase().includes(search) || 
        r.catalogItem.toLowerCase().includes(search) ||
        r.department.toLowerCase().includes(search)
      );
    }

    tbody.innerHTML = requests.map(req => {
      let stageBadge = `<span class="badge-req-progress">⚡ ${escapeHtml(req.stage)}</span>`;
      if (req.status === 'NEW') {
        stageBadge = `<span class="badge-req-pending">⏸️ ${escapeHtml(req.stage)}</span>`;
      } else if (req.status === 'RESOLVED') {
        stageBadge = `<span class="badge-req-fulfilled">✓ ${escapeHtml(req.stage)}</span>`;
      }

      const pClass = req.priority.toLowerCase();

      return `
        <tr data-req-id="${req.id}" style="cursor:pointer;">
          <td class="font-mono text-emerald font-bold">${req.id}</td>
          <td>
            <div style="font-weight:700; color:var(--text-zen-primary); font-size:13px;">${escapeHtml(req.title)}</div>
            <div class="text-xs text-muted" style="margin-top:2px;">Offering: <strong>${escapeHtml(req.catalogItem)}</strong></div>
          </td>
          <td>
            <div style="font-weight:600; font-size:12.5px;">${escapeHtml(req.requesterName)}</div>
            <div class="text-xs text-muted">${escapeHtml(req.department)}</div>
          </td>
          <td>
            <span class="badge-tag ${req.approvalStatus.includes('Approved') ? 'text-emerald' : 'text-amber'}">${escapeHtml(req.approvalStatus)}</span>
          </td>
          <td>${stageBadge}</td>
          <td>
            <span class="priority-pill pill-${pClass}">${req.priority}</span>
          </td>
          <td class="font-mono text-xs ${req.status === 'RESOLVED' ? 'text-emerald font-semibold' : 'text-indigo'}">${escapeHtml(req.slaDue)}</td>
          <td class="text-right">
            <div style="display:inline-flex; gap:6px;">
              ${req.status === 'NEW' ? `
                <button class="btn btn-xs btn-zen-primary btn-req-approve" data-req-id="${req.id}" title="Approve service request">Approve</button>
              ` : req.status === 'IN_PROGRESS' ? `
                <button class="btn btn-xs btn-emerald-primary btn-req-fulfill" data-req-id="${req.id}" title="Complete procurement and mark delivered">Fulfill</button>
              ` : `
                <span class="text-emerald font-bold text-xs">✓ Delivered</span>
              `}
              <button class="btn btn-icon-sm btn-inspect-req" data-req-id="${req.id}" title="Inspect full request specifications">➔</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    // Row click
    tbody.querySelectorAll('tr').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        const id = row.getAttribute('data-req-id');
        openServiceRequestDrawer(id);
      });
    });

    tbody.querySelectorAll('.btn-inspect-req').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-req-id');
        openServiceRequestDrawer(id);
      });
    });

    tbody.querySelectorAll('.btn-req-approve').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-req-id');
        const req = (state.serviceRequests || []).find(r => r.id === id);
        if (req) {
          req.status = 'IN_PROGRESS';
          req.approvalStatus = 'Approved by Manager';
          req.stage = 'In Fulfillment / Asset Allocation';
          renderServiceRequests();
          if (state.activeView === 'kanban-board') renderUnifiedKanbanBoard();
          showToast(`Service Request ${id} approved and routed for fulfillment!`, 'success');
        }
      });
    });

    tbody.querySelectorAll('.btn-req-fulfill').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-req-id');
        const req = (state.serviceRequests || []).find(r => r.id === id);
        if (req) {
          req.status = 'RESOLVED';
          req.stage = 'Fulfilled & Delivered';
          req.slaDue = '✓ Delivered within SLA';
          renderServiceRequests();
          if (state.activeView === 'kanban-board') renderUnifiedKanbanBoard();
          showToast(`Service Request ${id} fulfilled and delivered to ${req.requesterName}!`, 'success');
        }
      });
    });
  }

  function openServiceRequestDrawer(reqId) {
    const req = (state.serviceRequests || []).find(r => r.id === reqId);
    if (!req) return;

    const modal = document.getElementById('request-detail-backdrop');
    const titleEl = document.getElementById('req-modal-title');
    const subEl = document.getElementById('req-modal-sub');
    const bodyEl = document.getElementById('req-modal-body');
    if (!modal || !bodyEl) return;

    if (titleEl) titleEl.textContent = `Service Request: ${req.id}`;
    if (subEl) subEl.textContent = `${req.catalogItem} • ${req.stage}`;

    bodyEl.innerHTML = `
      <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-bottom:14px;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
          <h4 style="font-size:15px; font-weight:800; color:#0f172a;">${escapeHtml(req.title)}</h4>
          <span class="priority-pill pill-${req.priority.toLowerCase()}">${req.priority} Priority</span>
        </div>
        <div style="font-size:12.5px; color:#475569; line-height:1.5;">
          <strong>Business Justification:</strong> ${escapeHtml(req.justification)}
        </div>
      </div>

      <!-- Offering Specifications Table -->
      <div style="margin-bottom:14px;">
        <span style="font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.05em; color:#64748b;">REQUESTED SPECIFICATIONS &amp; CONFIGURATION</span>
        <div class="req-specs-grid">
          ${Object.entries(req.specs || {}).map(([k, v]) => `
            <div class="req-spec-item">
              <span class="req-spec-label">${escapeHtml(k)}</span>
              <span class="req-spec-value">${escapeHtml(v)}</span>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Requester & Approver Information -->
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-bottom:14px;">
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
          <span style="font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase;">REQUESTER DETAILS</span>
          <div style="display:flex; align-items:center; gap:10px; margin-top:8px;">
            <div class="tech-avatar-mini" style="background:#10b981; color:white;">${escapeHtml(req.requesterName.substring(0, 2).toUpperCase())}</div>
            <div>
              <strong style="font-size:13px; display:block;">${escapeHtml(req.requesterName)}</strong>
              <span class="text-xs text-muted">${escapeHtml(req.department)}</span>
            </div>
          </div>
        </div>

        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
          <span style="font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase;">FULFILLMENT STAGE</span>
          <div style="margin-top:8px;">
            <strong style="font-size:13px; color:#4f46e5; display:block;">${escapeHtml(req.stage)}</strong>
            <span class="text-xs text-muted">Assigned Queue: <strong>${escapeHtml(req.assignedTeam)}</strong></span>
          </div>
        </div>
      </div>

      <!-- Multi-tier Approver Chain Status -->
      <div class="req-approval-chain-box">
        <div class="req-approval-header">
          <span>✓</span>
          <span>MULTI-TIER ITIL APPROVAL CHAIN</span>
        </div>
        <p style="font-size:12px; color:#15803d;">
          Current Approval Status: <strong>${escapeHtml(req.approvalStatus)}</strong> (Designated Approver: ${escapeHtml(req.approver)})
        </p>
      </div>

      <!-- Action Footer -->
      <div style="display:flex; align-items:center; justify-content:space-between; margin-top:18px; padding-top:14px; border-top:1px solid #e2e8f0;">
        <span class="font-mono text-xs text-muted">Estimated Cost: <strong>$${req.cost.toFixed(2)}</strong></span>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-sm btn-zen-outline" id="btn-close-req-modal-action">Close</button>
          ${req.status === 'NEW' ? `
            <button class="btn btn-sm btn-zen-primary" id="btn-modal-req-approve">Approve Request</button>
          ` : req.status === 'IN_PROGRESS' ? `
            <button class="btn btn-sm btn-emerald-primary" id="btn-modal-req-fulfill">Mark Fulfilled &amp; Delivered</button>
          ` : `
            <span class="text-emerald font-bold text-xs" style="align-self:center;">✓ Request Delivered</span>
          `}
        </div>
      </div>
    `;

    modal.classList.add('open');

    document.getElementById('btn-close-req-modal-action')?.addEventListener('click', () => modal.classList.remove('open'));
    document.getElementById('btn-close-req-modal')?.addEventListener('click', () => modal.classList.remove('open'));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('open');
    });

    document.getElementById('btn-modal-req-approve')?.addEventListener('click', () => {
      req.status = 'IN_PROGRESS';
      req.approvalStatus = 'Approved by Manager';
      req.stage = 'In Fulfillment / Asset Allocation';
      modal.classList.remove('open');
      renderServiceRequests();
      if (state.activeView === 'kanban-board') renderUnifiedKanbanBoard();
      showToast(`Request ${req.id} approved!`, 'success');
    });

    document.getElementById('btn-modal-req-fulfill')?.addEventListener('click', () => {
      req.status = 'RESOLVED';
      req.stage = 'Fulfilled & Delivered';
      req.slaDue = '✓ Delivered within SLA';
      modal.classList.remove('open');
      renderServiceRequests();
      if (state.activeView === 'kanban-board') renderUnifiedKanbanBoard();
      showToast(`Request ${req.id} fulfilled and delivered!`, 'success');
    });
  }
'''

# Insert unified_engines before `function renderTickets() {`
if 'function renderUnifiedKanbanBoard()' not in js:
    target_tickets_func = '  function renderTickets() {'
    js = js.replace(target_tickets_func, unified_engines + '\n' + target_tickets_func, 1)
    print("SUCCESS: Inserted unified_engines functions!")

# In switchView, add service-requests and call renderUnifiedKanbanBoard()
switchview_old = """    if (DOM.breadcrumbView) {
      const titles = {
        'incident-command': 'Incident Command',
        'kanban-board': 'Kanban Board',
        'problem-management': 'Problem Management & KEDB',
        'change-management': 'Change Management & CAB',
        'omnichannel-hub': 'Omnichannel Hub (Email & CTI)',
        'service-catalog': 'Enterprise Service Catalog',
        'knowledge-base': 'Knowledge Base & KCS',
        'cmdb-topology': 'CMDB Topology Graph',
        'migration-studio': 'Top 10 Migration Hub',
        'ai-ops': 'AI Ops Center',
        'setup': 'Setup / Configurations'
      };"""

switchview_new = """    if (DOM.breadcrumbView) {
      const titles = {
        'incident-command': 'Incident Command',
        'kanban-board': 'Unified Operations Kanban',
        'problem-management': 'Problem Management & KEDB',
        'change-management': 'Change Management & CAB',
        'omnichannel-hub': 'Omnichannel Hub (Email & CTI)',
        'service-catalog': 'Enterprise Service Catalog',
        'service-requests': 'Service Requests & Fulfillment Queue',
        'knowledge-base': 'Knowledge Base & KCS',
        'cmdb-topology': 'CMDB Topology Graph',
        'migration-studio': 'Top 10 Migration Hub',
        'ai-ops': 'AI Ops Center',
        'setup': 'Setup / Configurations'
      };"""

if switchview_old in js:
    js = js.replace(switchview_old, switchview_new, 1)
    print("SUCCESS: Updated breadcrumb titles in switchView!")

# Update switchView execution routing
routing_old = """    } else if (viewName === 'incident-command' || viewName === 'kanban-board') {
      renderTickets();
    }"""

routing_new = """    } else if (viewName === 'service-requests') {
      renderServiceRequests();
    } else if (viewName === 'kanban-board') {
      renderUnifiedKanbanBoard();
    } else if (viewName === 'incident-command') {
      renderTickets();
    }"""

if routing_old in js:
    js = js.replace(routing_old, routing_new, 1)
    print("SUCCESS: Updated switchView execution routing!")

# Bind Kanban Type Chips & Service Request controls in bindEvents
bind_events_addition = '''
    // Unified Kanban Type Filter Chips
    document.querySelectorAll('.kanban-type-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.kanban-type-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.kanbanTypeFilter = chip.getAttribute('data-type');
        renderUnifiedKanbanBoard();
      });
    });

    const kanbanSearchInput = document.getElementById('kanban-filter-search');
    if (kanbanSearchInput) {
      kanbanSearchInput.addEventListener('input', () => {
        renderUnifiedKanbanBoard();
      });
    }

    // Service Requests Stage Filter Chips
    document.querySelectorAll('.req-stage-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.req-stage-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.requestsStageFilter = chip.getAttribute('data-stage');
        renderServiceRequests();
      });
    });

    const reqSearchInput = document.getElementById('requests-filter-search');
    if (reqSearchInput) {
      reqSearchInput.addEventListener('input', () => {
        renderServiceRequests();
      });
    }

    const btnJumpCatalog = document.getElementById('btn-jump-catalog-order');
    if (btnJumpCatalog) {
      btnJumpCatalog.addEventListener('click', () => {
        switchView('service-catalog');
      });
    }
'''

bind_hook = '    // Interactive 4-Step Wizard Navigation'
if bind_hook in js:
    js = js.replace(bind_hook, bind_events_addition + '\n' + bind_hook, 1)
    print("SUCCESS: Bound Kanban type filters and Service Request events!")

with open(script_path, 'w', encoding='utf-8') as f:
    f.write(js)

print("SUCCESS: All updates written to static/app.js!")

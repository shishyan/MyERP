import os

# 1. Update static/index.html
with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Add nav-btn-requests right after nav-btn-catalog
sidebar_catalog_btn = '''        <button class="nav-item" data-view="service-catalog" id="nav-btn-catalog" title="Enterprise Service Catalog & Requests">
          <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
          </span>
          <span class="nav-label">Service Catalog</span>
        </button>'''

sidebar_requests_btn = '''        <button class="nav-item" data-view="service-catalog" id="nav-btn-catalog" title="Enterprise Service Catalog & Requests">
          <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
          </span>
          <span class="nav-label">Service Catalog</span>
          <span class="nav-pill pill-live">Store</span>
        </button>

        <button class="nav-item" data-view="service-requests" id="nav-btn-requests" title="Service Requests Queue & Fulfillment">
          <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
          </span>
          <span class="nav-label">Service Requests</span>
          <span class="nav-pill pill-emerald" id="badge-requests-sidebar">4</span>
        </button>'''

if sidebar_catalog_btn in html:
    html = html.replace(sidebar_catalog_btn, sidebar_requests_btn)
    print("SUCCESS: Added Service Requests sidebar button!")

# Update view-kanban-board toolbar to have Work Item Type Filters
old_kanban_toolbar = '''          <!-- Toolbar Filter Controls for Kanban -->
          <div class="zen-toolbar">
            <div class="toolbar-left">
              <div class="zen-input-wrap">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                <input type="text" id="kanban-filter-search" placeholder="Search cards by keyword, team, CI..." autocomplete="off">
              </div>
              <div class="filter-chips-row">
                <span class="filter-caption">Priority:</span>
                <button class="filter-chip active kanban-p-chip" data-filter-priority="ALL">All</button>
                <button class="filter-chip chip-p1 kanban-p-chip" data-filter-priority="P1">P1 Critical</button>
                <button class="filter-chip chip-p2 kanban-p-chip" data-filter-priority="P2">P2 High</button>
                <button class="filter-chip chip-p3 kanban-p-chip" data-filter-priority="P3">P3 Mod</button>
              </div>
            </div>
            <div class="toolbar-right">
              <span class="badge-tag">Drag &amp; Drop ITIL Flow</span>
            </div>
          </div>'''

new_kanban_toolbar = '''          <!-- Unified ITIL Operations Kanban Dashboard Toolbar -->
          <div class="zen-toolbar">
            <div class="toolbar-left" style="flex-wrap: wrap; gap: 10px;">
              <div class="zen-input-wrap">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                <input type="text" id="kanban-filter-search" placeholder="Search all open items (incidents, problems, changes, requests)..." autocomplete="off" style="width: 320px;">
              </div>
              
              <!-- Work Item Type Filter Chips -->
              <div class="filter-chips-row">
                <span class="filter-caption">Item Type:</span>
                <button class="filter-chip active kanban-type-chip" data-type="ALL" id="kanban-chip-all">All Items (<span id="count-kanban-all">23</span>)</button>
                <button class="filter-chip kanban-type-chip" data-type="INCIDENT" id="kanban-chip-inc">🚨 Incidents (<span id="count-kanban-inc">12</span>)</button>
                <button class="filter-chip kanban-type-chip" data-type="PROBLEM" id="kanban-chip-prb">🔍 Problems (<span id="count-kanban-prb">3</span>)</button>
                <button class="filter-chip kanban-type-chip" data-type="CHANGE" id="kanban-chip-chg">🔄 Changes (<span id="count-kanban-chg">4</span>)</button>
                <button class="filter-chip kanban-type-chip" data-type="REQUEST" id="kanban-chip-req">📦 Service Reqs (<span id="count-kanban-req">4</span>)</button>
              </div>

              <!-- Priority Filter Chips -->
              <div class="filter-chips-row">
                <span class="filter-caption">Severity:</span>
                <button class="filter-chip active kanban-p-chip" data-filter-priority="ALL">All</button>
                <button class="filter-chip chip-p1 kanban-p-chip" data-filter-priority="P1">P1 Critical</button>
                <button class="filter-chip chip-p2 kanban-p-chip" data-filter-priority="P2">P2 High</button>
                <button class="filter-chip chip-p3 kanban-p-chip" data-filter-priority="P3">P3 Mod</button>
              </div>
            </div>
            <div class="toolbar-right">
              <span class="badge-tag tag-aurora">● Unified Enterprise Board</span>
            </div>
          </div>'''

if old_kanban_toolbar in html:
    html = html.replace(old_kanban_toolbar, new_kanban_toolbar)
    print("SUCCESS: Updated Kanban toolbar with multi-type filter chips!")

# Insert view-service-requests right before view-setup
service_requests_section = '''        <!-- ======================================================== -->
        <!-- VIEW 5B: SERVICE REQUESTS & FULFILLMENT QUEUE             -->
        <!-- ======================================================== -->
        <section id="view-service-requests" class="view-panel">
          <!-- Hero Banner -->
          <div class="zen-hero-banner" style="background: linear-gradient(135deg, #064e3b 0%, #047857 50%, #0f766e 100%);">
            <div class="hero-left">
              <div class="hero-tag">
                <span class="tag-sparkle">📦</span>
                <span>Enterprise Service Request Fulfillment &amp; SLA Tracking</span>
              </div>
              <h2 style="color: #ffffff;">Service Requests &amp; Procurement Queue</h2>
              <p style="color: #a7f3d0;">Manage employee hardware allocations, cloud infrastructure IAM grants, software license subscriptions, and multi-tier manager approval chains. Built on ITIL v4 Service Request Management principles.</p>
            </div>
            <div class="hero-right">
              <div class="hero-metric-card">
                <span class="hero-m-val text-emerald font-mono" id="stat-requests-active">4 Active</span>
                <span class="hero-m-label">Open Requests</span>
              </div>
              <div class="hero-metric-card">
                <span class="hero-m-val text-amber font-mono" id="stat-requests-approval">1 Pending</span>
                <span class="hero-m-label">Manager Approval</span>
              </div>
              <div class="hero-metric-card">
                <span class="hero-m-val text-indigo font-mono" id="stat-requests-fulfillment">2 In Progress</span>
                <span class="hero-m-label">In Provisioning</span>
              </div>
              <div class="hero-metric-card">
                <span class="hero-m-val text-emerald font-mono">4.2 Hours</span>
                <span class="hero-m-label">Avg Fulfillment</span>
              </div>
            </div>
          </div>

          <!-- Toolbar -->
          <div class="zen-toolbar">
            <div class="toolbar-left" style="flex-wrap: wrap; gap: 10px;">
              <div class="zen-input-wrap">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                <input type="text" id="requests-filter-search" placeholder="Search requests by ID, employee, item, department..." autocomplete="off" style="width: 320px;">
              </div>
              <div class="filter-chips-row">
                <span class="filter-caption">Stage:</span>
                <button class="filter-chip active req-stage-chip" data-stage="ALL">All (4)</button>
                <button class="filter-chip req-stage-chip" data-stage="Pending Approval">Pending Approval (1)</button>
                <button class="filter-chip req-stage-chip" data-stage="In Fulfillment">In Fulfillment (2)</button>
                <button class="filter-chip req-stage-chip" data-stage="Fulfilled">Fulfilled (1)</button>
              </div>
            </div>
            <div class="toolbar-right">
              <button class="btn btn-zen-primary" id="btn-jump-catalog-order">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
                <span>+ Browse Service Catalog</span>
              </button>
            </div>
          </div>

          <!-- Requests Table Card -->
          <div class="zen-card" style="padding: 0; overflow: hidden; margin-top: 14px;">
            <div class="table-responsive">
              <table class="zen-table">
                <thead>
                  <tr>
                    <th style="width: 110px;">Request #</th>
                    <th>Service Offering / Item Requested</th>
                    <th>Requester &amp; Department</th>
                    <th>Approval Status</th>
                    <th>Fulfillment Stage</th>
                    <th>Priority</th>
                    <th>SLA Delivery Due</th>
                    <th class="text-right" style="width: 140px;">Actions</th>
                  </tr>
                </thead>
                <tbody id="requests-table-body">
                  <!-- Populated by app.js -->
                </tbody>
              </table>
            </div>
          </div>
        </section>
'''

setup_marker = '        <!-- VIEW 6: ENTERPRISE SETUP & MASTER DATA CONFIGURATION    -->'
if setup_marker in html and 'id="view-service-requests"' not in html:
    html = html.replace(setup_marker, service_requests_section + '\n' + setup_marker)
    print("SUCCESS: Added view-service-requests section!")

# Add Request Detail Modal before closing </body>
request_modal_markup = '''    <!-- ======================================================== -->
    <!-- SERVICE REQUEST DETAIL & FULFILLMENT MODAL               -->
    <!-- ======================================================== -->
    <div class="modal-backdrop" id="request-detail-backdrop">
      <div class="modal-dialog resolution-modal-card" style="width: 780px; max-height: 88vh;">
        <div class="modal-header modal-header-futuristic">
          <div class="modal-title-wrap">
            <span class="badge-gem-dot dot-emerald"></span>
            <div>
              <h3 id="req-modal-title" style="font-size:17px; font-weight:800; color:#0f172a;">Service Request Detail</h3>
              <p id="req-modal-sub" style="font-size:12px; color:#64748b; margin-top:2px;">ITIL Service Request Fulfillment &amp; Procurement Lifecycle</p>
            </div>
          </div>
          <button class="btn-icon-sm" id="btn-close-req-modal">&times;</button>
        </div>
        <div class="modal-form-body" id="req-modal-body" style="overflow-y: auto; max-height: calc(88vh - 120px);">
          <!-- Populated by app.js -->
        </div>
      </div>
    </div>
'''

if 'id="request-detail-backdrop"' not in html:
    kb_modal_marker = '    <!-- KNOWLEDGE BASE ARTICLE READER MODAL                      -->'
    if kb_modal_marker in html:
        html = html.replace(kb_modal_marker, request_modal_markup + '\n' + kb_modal_marker)
        print("SUCCESS: Added request-detail-backdrop modal markup!")

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("SUCCESS: Updated static/index.html!")

import os

wizard_html = '''    <!-- CREATE TICKET MODAL - INTERACTIVE 4-STEP WIZARD (ZERO COGNITIVE OVERLOAD) -->
    <!-- ======================================================== -->
    <div class="modal-backdrop" id="create-modal-backdrop">
      <div class="modal-dialog create-ticket-modal-card wizard-modal-card">
        <div class="modal-header modal-header-futuristic">
          <div class="modal-title-wrap">
            <span class="badge-gem-dot dot-indigo"></span>
            <div>
              <h3 style="font-size:18px; font-weight:800; letter-spacing:-0.02em; color:#0f172a;">File Production Incident</h3>
              <p style="font-size:12px; color:#64748b; margin-top:2px;">Step-by-Step ITIL v4 Triage Wizard • Zero Cognitive Overload</p>
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:12px;">
            <div class="wizard-step-counter-pill" id="wizard-step-counter">Step 1 of 4</div>
            <button class="btn-icon-sm" id="btn-close-create-modal">&times;</button>
          </div>
        </div>

        <!-- Wizard Stepper Navigation Track -->
        <div class="modal-stepper-bar wizard-stepper-track">
          <div class="guided-step-item wizard-step-tab active" data-wizard-step="1" id="wizard-tab-1">
            <div class="step-badge-icon icon-indigo">🎯</div>
            <div class="step-text">
              <span class="step-index">STEP 01</span>
              <span class="step-name">Scope &amp; Telemetry</span>
            </div>
            <span class="wizard-step-check">✓</span>
          </div>
          <div class="wizard-step-connector-line" id="wizard-conn-1"></div>

          <div class="guided-step-item wizard-step-tab" data-wizard-step="2" id="wizard-tab-2">
            <div class="step-badge-icon icon-emerald">🏷️</div>
            <div class="step-text">
              <span class="step-index">STEP 02</span>
              <span class="step-name">3-Tier Classify</span>
            </div>
            <span class="wizard-step-check">✓</span>
          </div>
          <div class="wizard-step-connector-line" id="wizard-conn-2"></div>

          <div class="guided-step-item wizard-step-tab" data-wizard-step="3" id="wizard-tab-3">
            <div class="step-badge-icon icon-amber">⚡</div>
            <div class="step-text">
              <span class="step-index">STEP 03</span>
              <span class="step-name">Priority &amp; SLA HUD</span>
            </div>
            <span class="wizard-step-check">✓</span>
          </div>
          <div class="wizard-step-connector-line" id="wizard-conn-3"></div>

          <div class="guided-step-item wizard-step-tab" data-wizard-step="4" id="wizard-tab-4">
            <div class="step-badge-icon icon-violet">✦</div>
            <div class="step-text">
              <span class="step-index">STEP 04</span>
              <span class="step-name">Routing &amp; AI Copilot</span>
            </div>
            <span class="wizard-step-check">✓</span>
          </div>
        </div>

        <div class="modal-body-vertical wizard-body-canvas">
          <form id="form-create-ticket" class="create-form-vertical">
            
            <!-- ======================================================== -->
            <!-- WIZARD STEP 1: Incident Scope, Caller & Telemetry Trace   -->
            <!-- ======================================================== -->
            <div class="wizard-panel active" id="wizard-panel-1" data-panel="1">
              <div class="step-guided-card card-step-scope">
                <div class="card-step-header">
                  <div class="step-header-left">
                    <span class="step-tag-pill pill-indigo">STEP 01</span>
                    <div class="step-title-group">
                      <span class="step-card-title">Incident Identity &amp; Telemetry Trace</span>
                      <span class="step-card-subtitle">Define the primary outage headline, reporting caller, and raw diagnostic logs</span>
                    </div>
                  </div>
                  <span class="badge-tag tag-required">Required</span>
                </div>

                <div class="step-card-body">
                  <div class="form-row-2 mb-3">
                    <div class="form-group">
                      <label for="input-ticket-caller" class="field-label-styled">
                        <span class="label-icon">👤</span>
                        <span>Reporting Caller / Engineer</span>
                        <span class="required">*</span>
                      </label>
                      <div class="input-with-icon-wrap">
                        <span class="input-icon-left">✉️</span>
                        <input type="text" id="input-ticket-caller" class="zen-form-control input-enhanced" value="alex.rivera@opennow.io" placeholder="caller@company.com" required>
                      </div>
                    </div>

                    <div class="form-group">
                      <label for="select-caller-dept" class="field-label-styled">
                        <span class="label-icon">🏢</span>
                        <span>Department / Tier</span>
                      </label>
                      <select id="select-caller-dept" class="zen-form-control zen-select select-enhanced">
                        <option value="Site Reliability Engineering" selected>Site Reliability Engineering (SRE)</option>
                        <option value="Platform Operations">Platform Operations</option>
                        <option value="Payment Engineering">Payment Engineering</option>
                        <option value="Security Operations">SecOps / Infosec</option>
                        <option value="Executive Management">Executive Management (VIP)</option>
                      </select>
                    </div>
                  </div>

                  <div class="form-group mb-3">
                    <label for="input-ticket-title" class="field-label-styled">
                      <span class="label-icon">🎯</span>
                      <span>Incident Title &amp; Headline</span>
                      <span class="required">*</span>
                    </label>
                    <div class="input-with-icon-wrap">
                      <span class="input-icon-left">📌</span>
                      <input type="text" id="input-ticket-title" class="zen-form-control input-enhanced" placeholder="e.g., PostgreSQL Lock Contention causing 504 on checkout endpoint" required>
                    </div>
                  </div>

                  <div class="form-group">
                    <div class="label-with-ai-hint">
                      <label for="input-ticket-desc" class="field-label-styled">
                        <span class="label-icon">📋</span>
                        <span>Detailed Symptoms &amp; Diagnostic Telemetry</span>
                        <span class="required">*</span>
                      </label>
                      <span class="ai-typing-indicator" id="ai-typing-status" style="display: none;">
                        <span class="ai-sparkle-dot"></span> AI Copilot analyzing stream...
                      </span>
                    </div>
                    <textarea id="input-ticket-desc" class="zen-form-control form-textarea input-enhanced font-mono" rows="5" placeholder="Paste HTTP 5xx traces, Datadog/CloudWatch alert URLs, affected endpoints, or error codes..." required></textarea>
                    <div class="field-micro-hint">
                      <span>💡 Tip: Pasting stack traces or server error codes activates real-time automated root-cause detection in Step 4.</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Wizard Step 1 Navigation Bar -->
              <div class="wizard-nav-footer">
                <button type="button" class="btn btn-zen-subtle" id="btn-cancel-create">Discard</button>
                <button type="button" class="btn btn-zen-primary btn-wizard-next" data-next-step="2" id="btn-step1-next">
                  <span>Continue to 3-Tier Classification</span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                </button>
              </div>
            </div>

            <!-- ======================================================== -->
            <!-- WIZARD STEP 2: 3-Tier ITIL Taxonomy & CMDB Service        -->
            <!-- ======================================================== -->
            <div class="wizard-panel" id="wizard-panel-2" data-panel="2" style="display: none;">
              <div class="step-guided-card card-step-classification">
                <div class="card-step-header">
                  <div class="step-header-left">
                    <span class="step-tag-pill pill-emerald">STEP 02</span>
                    <div class="step-title-group">
                      <span class="step-card-title">Three-Tier ITIL Taxonomic Classification</span>
                      <span class="step-card-subtitle">Structure incident taxonomy for accurate analytics, routing rules, and SLA policies</span>
                    </div>
                  </div>
                  <span class="badge-tag tag-required">Required</span>
                </div>

                <div class="step-card-body">
                  <div class="form-row-3 mb-4">
                    <div class="form-group">
                      <label for="select-ticket-category" class="field-label-styled">
                        <span class="label-icon">📁</span>
                        <span>Category</span>
                        <span class="required">*</span>
                      </label>
                      <select id="select-ticket-category" class="zen-form-control zen-select select-enhanced" required></select>
                    </div>
                    <div class="form-group">
                      <label for="select-ticket-subcategory" class="field-label-styled">
                        <span class="label-icon">📂</span>
                        <span>Subcategory</span>
                        <span class="required">*</span>
                      </label>
                      <select id="select-ticket-subcategory" class="zen-form-control zen-select select-enhanced" required></select>
                    </div>
                    <div class="form-group">
                      <label for="select-ticket-item" class="field-label-styled">
                        <span class="label-icon">📄</span>
                        <span>Item / Component</span>
                        <span class="required">*</span>
                      </label>
                      <select id="select-ticket-item" class="zen-form-control zen-select select-enhanced" required></select>
                    </div>
                  </div>

                  <!-- Configuration Item (CI) Link -->
                  <div class="form-group">
                    <label for="select-ticket-ci" class="field-label-styled">
                      <span class="label-icon">🌐</span>
                      <span>Affected CMDB Configuration Item (CI)</span>
                      <span class="required">*</span>
                    </label>
                    <select id="select-ticket-ci" class="zen-form-control zen-select select-enhanced">
                      <option value="CI-DB-001">PostgreSQL Primary (us-east-1) • Tier 1 Mission Critical</option>
                      <option value="CI-PAY-003">Payment Gateway Service • Tier 1 Financial Transaction</option>
                      <option value="CI-CACHE-002">Redis Session Cache • Tier 2 In-Memory Cluster</option>
                      <option value="CI-AUTH-004">Auth0 &amp; JWT Token Service • Tier 1 Identity Provider</option>
                      <option value="CI-INGRESS-005">Kong API Gateway Ingress • Tier 1 Edge Router</option>
                      <option value="CI-K8S-006">EKS Core Cluster (us-east-1) • Tier 1 Compute Engine</option>
                      <option value="CI-KAFKA-007">Kafka Order Event Bus • Tier 1 Event Streaming</option>
                      <option value="CI-CDN-008">Cloudflare Global Edge • Tier 1 Global Anycast</option>
                    </select>
                    <div class="field-micro-hint">
                      <span>🔗 Linking a CI automatically associates its upstream dependencies and downstream blast radius.</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Wizard Step 2 Navigation Bar -->
              <div class="wizard-nav-footer">
                <button type="button" class="btn btn-zen-subtle btn-wizard-prev" data-prev-step="1">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
                  <span>Back to Scope</span>
                </button>
                <button type="button" class="btn btn-zen-primary btn-wizard-next" data-next-step="3" id="btn-step2-next">
                  <span>Continue to Priority Matrix &amp; SLA</span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                </button>
              </div>
            </div>

            <!-- ======================================================== -->
            <!-- WIZARD STEP 3: Priority Matrix & Live SLA Target HUD      -->
            <!-- ======================================================== -->
            <div class="wizard-panel" id="wizard-panel-3" data-panel="3" style="display: none;">
              <div class="step-guided-card card-step-matrix">
                <div class="card-step-header">
                  <div class="step-header-left">
                    <span class="step-tag-pill pill-amber">STEP 03</span>
                    <div class="step-title-group">
                      <span class="step-card-title">Impact × Urgency Matrix &amp; SLA Target HUD</span>
                      <span class="step-card-subtitle">Calculates contractual response and resolution countdown target</span>
                    </div>
                  </div>
                  <span class="badge-tag tag-auto">Auto-Calculated</span>
                </div>

                <div class="step-card-body">
                  <div class="matrix-interactive-layout">
                    <div class="matrix-inputs-col">
                      <div class="form-group mb-3">
                        <label for="select-ticket-impact" class="field-label-styled">
                          <span class="label-icon">💥</span>
                          <span>Business Impact Scope</span>
                          <span class="required">*</span>
                        </label>
                        <select id="select-ticket-impact" class="zen-form-control zen-select select-enhanced">
                          <option value="Enterprise" selected>Enterprise (High / Org-wide Outage)</option>
                          <option value="Department">Department (Medium / Core Service Degraded)</option>
                          <option value="Single User">Single User (Low / Localized Minor Issue)</option>
                        </select>
                      </div>

                      <div class="form-group">
                        <label for="select-ticket-urgency" class="field-label-styled">
                          <span class="label-icon">⏱️</span>
                          <span>Operational Urgency</span>
                          <span class="required">*</span>
                        </label>
                        <select id="select-ticket-urgency" class="zen-form-control zen-select select-enhanced">
                          <option value="Critical">Critical (Immediate Outage / Revenue at Risk)</option>
                          <option value="High" selected>High (Severe Disruption / No Workaround)</option>
                          <option value="Medium">Medium (Workaround Exists / Business Operational)</option>
                          <option value="Low">Low (Informational / Scheduled Routine Action)</option>
                        </select>
                      </div>
                    </div>

                    <!-- Dynamic Priority Matrix & SLA HUD Card -->
                    <div class="matrix-hud-card" id="matrix-hud-container">
                      <div class="hud-top-row">
                        <span class="hud-label">CALCULATED PRIORITY</span>
                        <span class="priority-pill pill-p1 hud-priority-badge" id="create-priority-preview-badge">P1</span>
                      </div>
                      <div class="hud-formula-row">
                        <span id="create-priority-calc-label">Enterprise × High = P1 Critical</span>
                      </div>
                      <div class="hud-sla-row">
                        <div class="hud-sla-chip chip-response">
                          <span>First Response SLA:</span>
                          <strong id="hud-sla-response">15 Minutes</strong>
                        </div>
                        <div class="hud-sla-chip chip-resolution">
                          <span>Resolution SLA Target:</span>
                          <strong id="hud-sla-resolution">1.0 Hour</strong>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Wizard Step 3 Navigation Bar -->
              <div class="wizard-nav-footer">
                <button type="button" class="btn btn-zen-subtle btn-wizard-prev" data-prev-step="2">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
                  <span>Back to Classification</span>
                </button>
                <button type="button" class="btn btn-zen-primary btn-wizard-next" data-next-step="4" id="btn-step3-next">
                  <span>Continue to Routing &amp; AI Copilot</span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                </button>
              </div>
            </div>

            <!-- ======================================================== -->
            <!-- WIZARD STEP 4: Assignment Routing & Autonomous AI Copilot -->
            <!-- ======================================================== -->
            <div class="wizard-panel" id="wizard-panel-4" data-panel="4" style="display: none;">
              
              <!-- Routing & Ownership Card -->
              <div class="step-guided-card card-step-assignment mb-3">
                <div class="card-step-header">
                  <div class="step-header-left">
                    <span class="step-tag-pill pill-sky">STEP 04</span>
                    <div class="step-title-group">
                      <span class="step-card-title">Support Team Escalation &amp; Primary Assignee</span>
                      <span class="step-card-subtitle">Connect primary engineering escalation queue and on-call technician</span>
                    </div>
                  </div>
                  <span class="badge-tag tag-routing">Smart Routing</span>
                </div>

                <div class="step-card-body">
                  <div class="form-row-2">
                    <div class="form-group">
                      <label for="select-ticket-team" class="field-label-styled">
                        <span class="label-icon">👥</span>
                        <span>Assignment Support Group</span>
                        <span class="required">*</span>
                      </label>
                      <select id="select-ticket-team" class="zen-form-control zen-select select-enhanced">
                        <option value="Database-Ops">Database Ops (DBA Escalation)</option>
                        <option value="SRE-Core" selected>SRE Core (Reliability &amp; Outages)</option>
                        <option value="Payment-Platform">Payment Platform (FinTech Core)</option>
                        <option value="Cloud-Infra">Cloud Infra (AWS / Kubernetes)</option>
                        <option value="Security-SecOps">SecOps / IAM Security</option>
                      </select>
                    </div>

                    <div class="form-group">
                      <label for="select-ticket-technician" class="field-label-styled">
                        <span class="label-icon">🧑‍💻</span>
                        <span>Primary On-Call Technician</span>
                      </label>
                      <select id="select-ticket-technician" class="zen-form-control zen-select select-enhanced">
                        <option value="Alex Rivera" selected>Alex Rivera (Lead SRE Architect)</option>
                        <option value="Sarah Lin">Sarah Lin (Database Lead)</option>
                        <option value="Marcus Vance">Marcus Vance (Principal SecOps)</option>
                        <option value="Priya Sharma">Priya Sharma (Cloud Architect)</option>
                        <option value="Unassigned">Auto-Dispatch to Pool</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Autonomous AI Assist Widget -->
              <div class="step-guided-card card-step-ai">
                <div class="ai-bottom-head">
                  <div class="ai-bottom-head-left">
                    <div class="ai-bottom-sparkle-gem">✦</div>
                    <div class="ai-bottom-titles">
                      <h4>Autonomous AI Triage Copilot</h4>
                      <span>Continuous neural analysis of symptoms, topology blast radius, and historical incident patterns</span>
                    </div>
                  </div>
                  <span class="badge-tag tag-ai-live">● Real-time Heuristics</span>
                </div>

                <div class="ai-copilot-body-bottom" id="live-ai-copilot-content">
                  <div class="ai-empty-prompt">
                    <div class="ai-pulsing-rings">
                      <div class="ring-1"></div>
                      <div class="ring-2"></div>
                    </div>
                    <p>AI Copilot actively analyzes the symptoms entered in Step 1 to predict root cause, blast radius risk, and recommended runbook steps.</p>
                  </div>
                </div>
              </div>

              <!-- Wizard Step 4 Final Dispatch Navigation Bar -->
              <div class="wizard-nav-footer modal-dispatch-bar mt-3">
                <button type="button" class="btn btn-zen-subtle btn-wizard-prev" data-prev-step="3">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
                  <span>Back to Severity</span>
                </button>
                <div class="dispatch-sla-notice">
                  <span class="notice-icon">⏱️</span>
                  <span>Submitting immediately starts contractual SLA countdown and pages on-call.</span>
                </div>
                <button type="submit" class="btn btn-zen-primary btn-dispatch-prominent" id="btn-submit-wizard-dispatch">
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                  <span>🚀 Dispatch Incident &amp; Page On-Call</span>
                </button>
              </div>

            </div>

          </form>
        </div>
      </div>
    </div>
'''

with open('static/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '    <!-- CREATE TICKET MODAL WITH VERTICAL ZEN FLOW & AI COPILOT  -->'
end_marker = '    <!-- RESOLUTION MODAL (ITIL / ZOHO SDP / GLPI)                -->'

idx_start = content.find(start_marker)
idx_end = content.find(end_marker)

if idx_start != -1 and idx_end != -1:
    new_content = content[:idx_start] + wizard_html + '\n\n' + content[idx_end:]
    with open('static/index.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('SUCCESS: Updated static/index.html with interactive 4-step wizard!')
else:
    print('ERROR: Markers not found!')

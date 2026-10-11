import os

css_additions = '''
/* ========================================================================= */
/* UNIFIED ENTERPRISE KANBAN OPERATIONS DASHBOARD                            */
/* ========================================================================= */

.kanban-type-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  padding: 2px 7px;
  border-radius: 4px;
  text-transform: uppercase;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.type-badge-incident {
  background: #ffe4e6;
  color: #9f1239;
  border: 1px solid #fecdd3;
}

.type-badge-problem {
  background: #f3e8ff;
  color: #6b21a8;
  border: 1px solid #e9d5ff;
}

.type-badge-change {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
}

.type-badge-request {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.kanban-item-headline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

/* ========================================================================= */
/* SERVICE REQUESTS FULFILLMENT QUEUE & INSPECTOR                            */
/* ========================================================================= */

.badge-req-pending {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.badge-req-progress {
  background: #e0e7ff;
  color: #3730a3;
  border: 1px solid #c7d2fe;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.badge-req-fulfilled {
  background: #dcfce7;
  color: #065f46;
  border: 1px solid #a7f3d0;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.req-specs-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  margin-top: 10px;
}

.req-spec-item {
  display: flex;
  flex-direction: column;
}

.req-spec-label {
  font-size: 11px;
  color: #64748b;
  font-weight: 600;
}

.req-spec-value {
  font-size: 12.5px;
  font-weight: 700;
  color: #0f172a;
}

.req-approval-chain-box {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 12px 14px;
  margin-top: 12px;
}

.req-approval-header {
  font-size: 12px;
  font-weight: 800;
  color: #166534;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
'''

with open('static/style.css', 'a', encoding='utf-8') as f:
    f.write(css_additions)

print("SUCCESS: Appended CSS for Kanban and Service Requests!")

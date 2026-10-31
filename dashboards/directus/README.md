# Directus Dashboards

Nineteen JSON dashboard design/import templates for the optional legacy
Directus adapter. They describe intended views for partner roles, internal
roles, domain areas, and platform administration; they are not proof that the
dashboards are installed, that their queries work against the current schema,
or that their filters enforce authorization.

## Dashboard Index

### Partner Dashboards (4)

| Dashboard | JSON | Description |
|-----------|------|-------------|
| Partner — Funder | `partner-funder.json` | Financial performance, cost breakdown, forecast comparison, impact attestations |
| Partner — Operator | `partner-operator.json` | Operations overview: activity timeline, crop cycles, sensors, weather, financials |
| Partner — Buyer | `partner-buyer.json` | Production summary, upcoming harvests, recent sales, quality grades |
| Partner — Vendor | `partner-vendor.json` | Purchase summary, history, demand forecast, payment status |

### Internal Role Dashboards (6)

| Dashboard | JSON | Description |
|-----------|------|-------------|
| Field Worker | `field-worker.json` | Daily tasks, data entry, activity log, sensor readings, field notes |
| Supervisor | `supervisor.json` | Team activity, pending approvals, harvest quality, sensor alerts |
| Manager | `manager.json` | Crop cycles, financial performance, team productivity, expenses, sales |
| Finance | `finance.json` | Expense approval, revenue tracking, NOI analysis, CapEx, budget vs actual |
| Analyst | `analyst.json` | Metric definitions, computed values, forecasts, dashboard datasets |
| Auditor | `auditor.json` | Audit logs, workflow history, attestations, agent activity, MRV claims |

### Domain-Specific Dashboards (8)

| Dashboard | JSON | Description |
|-----------|------|-------------|
| Environmental Monitoring | `environmental.json` | Weather, sensors, NDVI, soil carbon, ecological alerts |
| Carbon Credits | `carbon-credits.json` | Credit lifecycle: issuance, adjustments, retirements, certificates, MRV |
| Stakeholder Governance | `stakeholder.json` | Feedback, outcomes, engagement, grievance tracking |
| Agent Activity | `agent-activity.json` | AI tasks, summaries, action logs, safety monitoring |
| Workflow Health | `workflow-health.json` | Transitions, pending approvals, status distribution, pipeline health |
| Impact & Accountability | `impact-accountability.json` | Impact claims, evidence maturity, attestations, metric proposals |
| Bio-Factory Operations | `bio-factory.json` | Batches, recipes, quality tests, provenance, regional inputs |
| Governance Cockpit | `governance-cockpit.json` | DAO proposals, guild activity, circles, tensions, coordination |

### Admin Dashboard (1)

| Dashboard | JSON | Description |
|-----------|------|-------------|
| Platform Admin | `platform-admin.json` | Migrations, API keys, webhooks, scheduled jobs, agent safety |

## File Structure

Each dashboard consists of:
- **JSON module spec** — Directus dashboard configuration with modules, filters, and data access rules
- **Markdown setup guide** — Overview, module descriptions, data access rules, and notes

## Illustrative Data Access Patterns

The snippets below describe the original dashboard design. They are not
verified Directus policies. `$CURRENT_USER.assigned_locations` and
`partner_id` are placeholders in these templates; only the deployed Directus
permission engine and the authenticated Gateway's grants can authorize data.

### Proposed Location Scope (Partner & Internal Roles)
```json
{
  "read": "location_id IN ($CURRENT_USER.assigned_locations)"
}
```

### Partner-Scoped (Buyer)
```json
{
  "read": "partner_id = $CURRENT_USER.partner_id"
}
```

### Network-Wide (Admin, Governance, Analyst)
```json
{
  "read": true
}
```

## Intended Role Matrix (Not Effective Access Proof)

| Role | Access Level | Key Collections |
|------|--------------|-----------------|
| Field Worker | Field data entry design | `harvest_event`, `field_note`; `farm_activity` is intentionally excluded from Directus permissions |
| Supervisor | Operational review design | `approval`, `harvest_event`; farm-activity operations are owned by the Gateway |
| Manager | Approve operational + financial | `crop_cycle`, `expense_event`, `sales_event`, `noi_snapshot` |
| Finance | Verify expenses/revenue | `expense_event`, `sales_event`, `revenue_event`, `capex_breakdown` |
| Analyst | Read-only all verified | `metric_value`, `forecast_output`, `dashboard_dataset` |
| Auditor | Read-only all statuses | `audit_log`, `workflow_history`, `attestation_record` |
| Admin | Full platform access | All collections |

## Lifecycle State Machine

All governed collections follow the workflow state machine defined in `extensions/kokonut-hooks/src/workflow.ts`:

```
draft → submitted → verified → published
                    ↓
                rejected (terminal)
```

- Role-based approval routing per collection/status
- 7-day review period for stakeholder feedback
- All transitions logged to `workflow_history`

## Setup (Optional Directus Adapter)

1. In Directus Admin → Settings → Roles → Create/verify roles
2. Apply permissions from `config/directus/permissions.sql`
3. Configure and verify supported user-to-organization/location permissions in the pinned Directus runtime. Do not treat the template's `assigned_locations` variable as an existing access control.
4. Review and adapt each JSON module before importing it. Dashboard import does not establish field, row, lifecycle, or tenant permissions.

## Notes

- All queries use bare table names (no schema prefix)
- Location scope snippets in these templates are illustrative only; they are not verified effective permission rules
- Agent safety enforced via `agent-safety.ts` hook
- High-risk actions require human approval

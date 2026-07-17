# Data Domain Ownership

Schema, service, test, and relationship vocabulary changes should have one
primary owning domain.

| Domain | Canonical responsibility |
| --- | --- |
| Identity | `party`, farmer profiles, credentials, KYC, identifiers |
| Stakeholders | Parties, interests, relationships, consent, representation |
| Farm operations | Locations, farms, plots, crop cycles, operational events |
| Measurement and evidence | Metrics, provenance, evidence links, attestations |
| Strategy and governance | Plans, choices, capabilities, decisions, approvals |
| Finance and marketplace | Accounts, transactions, credit, orders, settlement |
| Workflow and lifecycle | State models, transitions, work items, escalation |
| Analytics and projections | Views, reports, exports, derived graphs, schema inventory |

Each domain owns its migrations, service APIs, tests, lifecycle vocabulary, and
relationship review. Cross-domain relationships must be represented by an
explicit associative entity or a documented polymorphic policy.

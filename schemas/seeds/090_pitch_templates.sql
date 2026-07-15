-- 090_pitch_templates.sql — Seed audience-segmented pitch configurations
-- Uses ON CONFLICT for idempotency

INSERT INTO pitch_template (audience, hook, problem, solution, proof_headline, cta_label, cta_url, sections) VALUES

-- 1. Capital allocators / funders
('funders',
 '$45,000 in infrastructure funding produced a live, revenue-generating syntropic farm with on-chain verified impact — and the model is designed to replicate.',
 'Grassroots farmers who grow the world''s most vital crops operate without the capital, coordination tools, or governance structures needed to compete. Most agricultural communities perform the labor that sustains food systems while remaining excluded from the ownership, infrastructure, and market upside those systems generate. Traditional agricultural finance requires collateral and credit history that many grassroots farmers do not have. NGO funding is temporary. Corporate supply chains extract value upward.',
 'Kokonut Network coordinates four systems — a DAO for transparent capital governance, a Framework for standardized farm operations, an MRV stack that turns farm activity into publicly auditable evidence, and Guilds that let contributors earn standing through useful work. DAO members tribute stablecoins and receive $vKKN governance tokens backed 1:1 by real coconut trees. Farms follow a repeatable operating system that makes them comparable, fundable, governable, and verifiable.',
 'Adelphi — 15,725 m² of live syntropic agriculture in Monte Plata, Dominican Republic. CRISP risk-assessed, revenue-forecasted, MRV-verified, and publicly auditable at hub.kokonut.network.',
 'Inspect live farm data',
 'https://hub.kokonut.network/projects/41',
 '[
   {"title": "The Funding Gap", "content": "Farmers have land, knowledge, and community need — but lack the repeatable system for funding, governance, operations, reporting, and trust. The problem is not the land. It is the coordination layer around it."},
   {"title": "Four Closing Mechanisms", "content": "DAO (capital governance) + Framework (standardized operations) + MRV (public evidence) + Guilds (contributor coordination). Each closes a specific failure mode that traps farmers in poverty."},
   {"title": "Live Proof", "content": "Adelphi is already operational: syntropic production, harvest records, biodiversity tracking, community programs, on-chain attestations, and public dashboard data."},
   {"title": "Replication Design", "content": "The Framework is open-source. Each new farm follows the same schema, phases, and MRV standards — making the network self-sustaining at scale."}
 ]'::jsonb
),

-- 2. Farm operators / cooperatives
('operators',
 'A repeatable operating system for launching and running regenerative farms — so you can focus on farming, not reinventing coordination from scratch.',
 'Starting or transitioning a regenerative farm means navigating fragmented knowledge about crops, soil, governance, funding, certification, and market access. Every farm invents its own proposal format, data tracking, and reporting. There is no shared system for comparing practices, measuring impact, or accessing capital.',
 'The Kokonut Framework gives every farm a shared structure: common data schema, four development phases (Planning, Production, Consolidation, Replication), five regeneration principles, eight forms of capital tracking, and MRV standards. You keep your land, crops, and community identity. You gain a proven coordination layer that makes your farm fundable, governable, and verifiable.',
 'Adelphi is the reference implementation. The same Framework running there can be applied to your farm — with documented phases, templates, and lessons learned.',
 'Book a walkthrough',
 'https://link.kokonut.network/meeting',
 '[
   {"title": "What the Framework Covers", "content": "Farm onboarding, data schema, development phases, regeneration principles, MRV reporting, public goods allocation, governance and proposal standards."},
   {"title": "Adelphi as Reference", "content": "15,725 m² syntropic farm with live data on crops, harvests, biodiversity, infrastructure, poultry, training, and SDG alignment — all publicly documented."},
   {"title": "Your Farm, Your Identity", "content": "The Framework standardizes coordination, not farming. Your crops, community, and market strategy remain your own."},
   {"title": "How to Start", "content": "Connect with the community, review the Framework documentation, and explore the onboarding pathway."}
 ]'::jsonb
),

-- 3. Developers / builders
('developers',
 'Open-source farm coordination layer with 700+ structured data tables, MCP agent access, and CIDS-compatible schemas — build on top, not from scratch.',
 'Building tools for regenerative agriculture means solving the same coordination problems every time: farm data standards, MRV pipelines, governance integration, impact verification, and agent workflows. Most projects start from zero and never achieve interoperability.',
 'Kokonut Intelligence is a fully open-source platform with PostgreSQL, ClickHouse, Directus, Python services, Solidity contracts, and MCP-based agent access. The Common Data Schema is a shared JSON/TypeScript interface any farm can read and write against. CIDS compatibility means data can flow to any aligned registry. You get a working coordination layer to build on — not a greenfield project.',
 'The platform is live and open: github.com/wasalo/Kokonut-Intelligence. 700+ tables, 100+ services, 60+ report types, and a growing agent ecosystem.',
 'Explore the repo',
 'https://github.com/wasalo/Kokonut-Intelligence',
 '[
   {"title": "Architecture", "content": "PostgreSQL + ClickHouse + Directus + Python services + Solidity contracts. MCP-based agent access for AI workflows."},
   {"title": "Common Data Schema", "content": "Shared JSON/TypeScript interface covering identity, scope, funding, governance, and narrative fields. CIDS-compatible."},
   {"title": "Agent Access", "content": "AI agents can read canonical data and write verified outputs through scoped access, MCP integration, and full audit logging."},
   {"title": "What to Build", "content": "MRV tools, harvest forecasters, impact scorers, DAO automation, dashboards, integrations — the coordination layer is the product."}
 ]'::jsonb
),

-- 4. ReFi / Web3 community
('refi',
 'Proof-first grant qualification — not a speculative roadmap. A working ReFi farm funded transparently, operated profitably, and verified on-chain.',
 'The ReFi ecosystem has many proposals and pilot ideas, but few live, funded, verified farms with public data. Most projects describe what they plan to do. Few show what they have already done. Grant reviewers struggle to distinguish real impact from promising slides.',
 'Kokonut proves the model works at the farm level first, then scales. DAO governance on Gnosis Chain. EAS attestations on Celo. MRV pipeline producing public evidence. Regen Coordination partnership confirmed. Fortune 500 Farm Score, Monte Carlo revenue forecasting, and Shannon biodiversity index — all computed from live data, not projections.',
 'Adelphi is live. The DAO is funded. The MRV pipeline is active. The framework is open-source. This is not a proposal — it is an operating system that has already produced results.',
 'Open the DAO',
 'https://link.kokonut.network/dao',
 '[
   {"title": "Why Web3", "content": "Transparent funding, public data, verifiable impact, community-governed ownership — not another extractive intermediary."},
   {"title": "On-Chain Infrastructure", "content": "Moloch DAO on Gnosis Chain, EAS attestations on Celo, $vKKN governance tokens backed by real coconut trees, rage-quit protection."},
   {"title": "Regen Coordination", "content": "Funded partnership with Regen Coordination (GreenPill Network, ReFi DAO, Celo Public Goods). CIDS-compatible. Karma GAP profile active."},
   {"title": "The Loop", "content": "DAO members tribute stablecoins → DAO funds farms → farms run Framework → MRV verifies → revenue flows back → next farm launches faster."}
 ]'::jsonb
),

-- 5. Impact / NGO / grant reviewers
('impact',
 'From self-reported impact claims to publicly auditable evidence — MRV makes regenerative agriculture measurable and verifiable.',
 'Impact reporting in agriculture is often self-reported, inconsistent, and impossible to compare across projects. Grant reviewers receive narrative reports without underlying data. Funders cannot distinguish real outcomes from optimistic projections. The result: worthy projects go unfunded while the sector struggles with credibility.',
 'Kokonut''s MRV stack turns farm activity into structured, verifiable evidence. Satellite data, drone imagery, soil probes, community logs, harvest records, and EAS attestations make progress publicly auditable. Impact claims require evidence maturity thresholds. CRISP risk scoring provides independent assessment. The Common Data Schema makes farms comparable across sites.',
 'Adelphi produces MRV records, EAS attestations, harvest data, biodiversity observations, and stakeholder feedback — all publicly accessible and independently verifiable.',
 'Explore the Data Hub',
 'https://hub.kokonut.network/projects/41',
 '[
   {"title": "MRV Pipeline", "content": "Field data → structured payloads → IPFS/Filecoin evidence storage → EAS attestation on Celo → public dashboard → DAO and grant reporting."},
   {"title": "Evidence Standards", "content": "Impact claims require evidence maturity >= 4. Carbon claims require maturity 6, third-party verification, and published status. No self-reported marketing."},
   {"title": "CRISP Risk Scoring", "content": "Carbon yield, climate, policy, financial, and implementation risks independently assessed. Composite rating bands from AAA to D."},
   {"title": "SDG Alignment", "content": "Adelphi addresses SDG 1, SDG 2, SDG 5, SDG 8, and SDG 15 through measurable farm activity documented in the Framework."}
 ]'::jsonb
),

-- 6. Elevator pitch (generic / all audiences)
('elevator',
 'Kokonut Network proves regenerative farms can be funded transparently, verified on-chain, and replicated — and Adelphi is already doing it.',
 'Regenerative agriculture has land, knowledge, and community need — but lacks a repeatable coordination system for funding, governance, operations, and trust. Farmers stay trapped not because the land is unproductive, but because the system around it is broken.',
 'Four systems close the gap: a DAO for transparent capital governance, a Framework for standardized farm operations, an MRV stack for public evidence, and Guilds for contributor coordination. Open-source. Community-governed. Designed to replicate.',
 'Adelphi: 15,725 m² of syntropic agriculture in the Dominican Republic — live, funded, verified, and publicly auditable.',
 'See the live data',
 'https://hub.kokonut.network/projects/41',
 '[]'::jsonb
)

ON CONFLICT (audience) DO UPDATE SET
    hook = EXCLUDED.hook,
    problem = EXCLUDED.problem,
    solution = EXCLUDED.solution,
    proof_headline = EXCLUDED.proof_headline,
    cta_label = EXCLUDED.cta_label,
    cta_url = EXCLUDED.cta_url,
    sections = EXCLUDED.sections,
    updated_at = NOW();

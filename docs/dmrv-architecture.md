# dMRV Architecture

Digital Measurement, Reporting, and Verification (dMRV) architecture for the Kokonut Intelligence platform. Maps dMRV concepts to platform components.

## dMRV Concept Map

| dMRV Concept | Platform Implementation | Key Files |
|---|---|---|
| Automated data collection | 10+ ingestion pipelines (GEE, Copernicus, MQTT, HTTP, weather, market, EAS, Gnosis, sensors, climate) | `services/ingestion/` |
| Real-time monitoring | MQTT subscriber, HTTP webhook receiver, hourly anomaly detection | `mqtt_subscriber.py`, `http_sensor_receiver.py` |
| AI/ML pattern detection | Prophet (univariate seasonal) + Isolation Forest (multivariate) anomaly detection | `ml_anomaly_detector.py` |
| Blockchain verification | EAS attestation on Celo/Optimism/Base with resolver gating | `services/attestation/` |
| Open-source algorithms | Full codebase, versioned methodologies, IPCC references | All `services/` |
| Dynamic carbon credits | Auto-adjusting credits with buffer pool, margin-based adjustment | `carbon_credits.py` |
| Secondary verification | Continuous CRISP risk scoring, data freshness monitoring | `services/crisp/`, `data_freshness.py` |
| Due diligence | 5-dimension CRISP risk scoring, EBF scorecards, evidence maturity | `services/crisp/`, `services/scoring/` |
| Pipeline orchestration | Prefect workflows with dependency chains | `services/flows/` |
| Automated reporting | 42+ report types with --auto flag | `services/export/report_generator.py` |

## Data Flow Architecture

```
External Sources                    Ingestion Layer                    Storage                  Analytics                 Verification
────────────────                    ──────────────                    ───────                  ─────────                 ────────────
Sentinel-2 (GEE/Copernicus)  ──►   remote_sensing_fetcher     ──►   PostgreSQL (canonical)  ──►  CRISP risk scoring  ──►  EAS attestation
IoT Sensors (MQTT/HTTP)       ──►   mqtt_subscriber            ──►   ClickHouse (analytics) ──►  ML anomaly detection ──►  Carbon credits
Weather (OpenWeatherMap)      ──►   weather.py                 ──►   Dual-write pattern     ──►  Carbon balance      ──►  Impact claims
Market Data (World Bank)      ──►   market_data.py             ──►   Ingestion logging      ──►  SOC prediction      ──►  CIDS export
Blockchain (EAS/Gnosis)       ──►   eas_indexer.py             ──►   Data freshness         ──►  Ecological modeling ──►  Public views
Climate (WorldClim/NCEP)      ──►   climate_data.py            ──►   Remote sensing sync    ──►  Financial analysis  ──►  Dashboard refresh
```

## Carbon Credit Lifecycle

```
Measurement          Claim              Credit               Adjustment          Retirement
───────────          ─────              ───────              ──────────          ──────────
tree_inventory  ──►  mrv_claim    ──►   carbon_credit   ──►  credit_adjustment  ──►  credit_retirement
soil_carbon     ──►  impact_claim ──►   (issuance)      ──►  (auto/manual)      ──►  (permanent)
ghg_emissions   ──►  attestation  ──►   (Level 6)       ──►  (margin check)     ──►  (on-chain)
climate_impact  ──►  verification ──►   (buffer pool)   ──►  (human review)     ──►  (audited)
```

## Risk Scoring (CRISP)

| Dimension | Weight | Data Sources | Scoring |
|-----------|--------|--------------|---------|
| Carbon Yield | 40% | tree_inventory, soil_carbon, harvest_event, NDVI | 3-scenario modeling (min/realistic/optimistic) |
| Climate | 25% | weather_observation, emergency_incident | 6-hazard scoring (0-3 each, max 15) |
| Policy | 15% | organic_certification, adoption_barrier, land_stewardship | Sub-factor scoring (0-1 each) |
| Financial | 10% | financial_sustainability_plan, revenue/expense events | Revenue/cost/liquidity/market risk |
| Implementation | 10% | farm_onboarding, regenerative_practice, stakeholder_feedback | Track record/team/network/transparency |

## Pipeline Orchestration (Prefect)

| Schedule | Pipeline | Tasks |
|----------|----------|-------|
| Hourly | `scheduled_hourly` | Sensor ingestion, anomaly detection, freshness check |
| Every 6h | `scheduled_every_6h` | Weather, dashboards, remote sensing |
| Daily | `scheduled_daily` | Market data, metrics computation, credit adjustment |
| Weekly | `scheduled_weekly` | Climate data refresh |
| Manual | `full_pipeline` | Ingestion -> monitoring -> analytics -> remote sensing |

## Key Design Principles

1. **Dual-write**: Every ingestion writes to PostgreSQL (canonical) + ClickHouse (analytics)
2. **Governed lifecycle**: All records follow `draft -> submitted -> verified -> published`
3. **Evidence maturity**: Public claims require Level 4+; carbon claims require Level 6
4. **Agent safety**: Agents can draft/submit but cannot verify/publish governed records
5. **Open-source**: All algorithms are in the open repository with versioned methodologies
6. **Configurable**: Weights, thresholds, and SLAs are configurable per location

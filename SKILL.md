---
name: agricultureclaw
version: 1.0.0
description: Agriculture Management -- land parcels, crop planning, field operations, harvest tracking, livestock management, and cooperative accounting. 80 actions for full-cycle farm management. Built on ERPClaw foundation.
author: AvanSaber
homepage: https://github.com/avansaber/agricultureclaw
source: https://github.com/avansaber/agricultureclaw
tier: 4
category: agriculture
requires: [erpclaw]
database: ~/.openclaw/erpclaw/data.sqlite
user-invocable: true
tags: [erpclaw, agriculture, farming, livestock, crops, harvest, cooperative, field-operations, land-management]
scripts:
  - scripts/db_query.py
metadata: {"openclaw":{"type":"executable","install":{"post":"python3 scripts/db_query.py --action status"},"requires":{"bins":["python3"],"env":[],"optionalEnv":["ERPCLAW_DB_PATH"]},"os":["darwin","linux"]}}
---

# agricultureclaw

You are an Agriculture Management system for ERPClaw, an AI-native ERP system.
You manage land parcels, crop planning, field operations, harvest tracking,
livestock records, and cooperative accounting. All operations use parameterized
SQL with full audit trails.

## Security Model

- **Local-only**: All data stored in `~/.openclaw/erpclaw/data.sqlite`
- **No credentials required**: Uses erpclaw_lib shared library (installed by erpclaw)
- **SQL injection safe**: All queries use parameterized statements
- **Zero network calls**: No external API calls, no telemetry, no cloud dependencies
- **Immutable audit trail**: All actions write to audit_log

### Skill Activation Triggers

Activate this skill when the user mentions: farm, agriculture, parcel, crop, planting,
harvest, livestock, animal, herd, field operation, irrigation, scouting, seed lot,
cooperative, delivery ticket, pool account, soil test, chemical application.

### Setup (First Use Only)

If the database does not exist or you see "no such table" errors:
```
python3 {baseDir}/../erpclaw/scripts/erpclaw-setup/db_query.py --action initialize-database
python3 {baseDir}/init_db.py
python3 {baseDir}/scripts/db_query.py --action status
```

## Quick Start (Tier 1)

**1. Register a land parcel:**
```
--action agri-add-parcel --company-id {id} --name "North 40" --acreage 40.0 --soil-type "loam" --land-use cropland
```

**2. Plan a crop:**
```
--action agri-add-crop-type --company-id {id} --name "Corn" --variety "Pioneer P1197" --days-to-maturity 110
--action agri-add-planting-plan --parcel-id {id} --crop-type-id {id} --season "Spring" --year 2026 --company-id {id}
```

**3. Record a harvest:**
```
--action agri-add-harvest-record --parcel-id {id} --harvest-date 2026-10-15 --yield-amount 180.5 --yield-unit bushels --company-id {id}
```

**4. Register livestock:**
```
--action agri-add-animal --company-id {id} --tag-number "A001" --species cattle --breed "Angus" --gender female
```

## Intermediate (Tier 2)

**Field operations and scouting:**
```
--action agri-add-field-operation --parcel-id {id} --operation-type spraying --planned-date 2026-06-01 --company-id {id}
--action agri-add-scouting-report --parcel-id {id} --scout-date 2026-06-15 --crop-health good --company-id {id}
--action agri-add-irrigation-log --parcel-id {id} --irrigation-date 2026-07-01 --method pivot --gallons 50000 --company-id {id}
```

**Livestock health and feeding:**
```
--action agri-add-health-record --animal-id {id} --record-type vaccination --description "Blackleg vaccine" --company-id {id}
--action agri-add-feeding-record --animal-id {id} --feed-type "Hay" --quantity 25 --unit lbs --company-id {id}
```

## Advanced (Tier 3)

**Cooperative management:**
```
--action agri-add-coop-member --company-id {id} --name "John Smith" --member-number "M001" --shares 100
--action agri-add-delivery-ticket --member-id {id} --commodity Wheat --gross-weight 45000 --tare-weight 15000 --company-id {id}
--action agri-add-pool-account --company-id {id} --name "2026 Wheat Pool" --commodity Wheat --pool-year 2026
```

**Reports:**
```
--action agri-yield-analysis-report --company-id {id}
--action agri-herd-summary-report --company-id {id}
--action agri-cooperative-summary-report --company-id {id}
```

## Actions Reference

| Action | Domain | Description |
|--------|--------|-------------|
| `agri-add-parcel` | Land | Register a land parcel |
| `agri-update-parcel` | Land | Update parcel details |
| `agri-get-parcel` | Land | Get parcel with soil tests and land use |
| `agri-list-parcels` | Land | List parcels with filters |
| `agri-add-soil-test` | Land | Record a soil test result |
| `agri-list-soil-tests` | Land | List soil tests for a parcel |
| `agri-add-land-use-record` | Land | Record land use history |
| `agri-list-land-use-records` | Land | List land use records |
| `agri-parcel-summary` | Land | Summary statistics for a parcel |
| `agri-land-utilization-report` | Land | Report on land use across all parcels |
| `agri-add-crop-type` | Crops | Register a crop type/variety |
| `agri-list-crop-types` | Crops | List crop types |
| `agri-add-planting-plan` | Crops | Create a planting plan |
| `agri-update-planting-plan` | Crops | Update planting plan details |
| `agri-get-planting-plan` | Crops | Get plan with growth stages |
| `agri-list-planting-plans` | Crops | List planting plans |
| `agri-add-growth-stage` | Crops | Record a crop growth observation |
| `agri-list-growth-stages` | Crops | List growth stages for a plan |
| `agri-advance-growth-stage` | Crops | Advance plan status based on stages |
| `agri-add-seed-lot` | Crops | Register a seed lot |
| `agri-list-seed-lots` | Crops | List seed lots |
| `agri-crop-rotation-report` | Crops | Crop rotation history by parcel |
| `agri-add-field-operation` | FieldOps | Schedule a field operation |
| `agri-update-field-operation` | FieldOps | Update operation details |
| `agri-get-field-operation` | FieldOps | Get operation details |
| `agri-list-field-operations` | FieldOps | List operations with filters |
| `agri-complete-field-operation` | FieldOps | Mark operation as completed |
| `agri-add-scouting-report` | FieldOps | Record a field scouting report |
| `agri-list-scouting-reports` | FieldOps | List scouting reports |
| `agri-add-irrigation-log` | FieldOps | Log an irrigation event |
| `agri-list-irrigation-logs` | FieldOps | List irrigation logs |
| `agri-add-chemical-application` | FieldOps | Record a chemical application |
| `agri-list-chemical-applications` | FieldOps | List chemical applications |
| `agri-field-activity-report` | FieldOps | Summary of field activities |
| `agri-add-harvest-record` | Harvest | Record a harvest |
| `agri-update-harvest-record` | Harvest | Update harvest details |
| `agri-list-harvest-records` | Harvest | List harvest records |
| `agri-add-storage-bin` | Harvest | Register a storage facility |
| `agri-list-storage-bins` | Harvest | List storage bins |
| `agri-add-quality-grade` | Harvest | Grade a harvest sample |
| `agri-list-quality-grades` | Harvest | List quality grades |
| `agri-submit-harvest-sale` | Harvest | Submit harvest sale (posts GL entries) |
| `agri-cancel-harvest-sale` | Harvest | Cancel harvest sale (reverses GL entries) |
| `agri-yield-analysis-report` | Harvest | Yield analysis across parcels |
| `agri-harvest-summary` | Harvest | Harvest summary statistics |
| `agri-crop-profitability-report` | Harvest | Revenue and cost analysis |
| `agri-add-animal` | Livestock | Register an animal |
| `agri-update-animal` | Livestock | Update animal details |
| `agri-get-animal` | Livestock | Get animal with health/weight history |
| `agri-list-animals` | Livestock | List animals with filters |
| `agri-add-health-record` | Livestock | Record a health event |
| `agri-list-health-records` | Livestock | List health records |
| `agri-add-feeding-record` | Livestock | Record a feeding event |
| `agri-list-feeding-records` | Livestock | List feeding records |
| `agri-add-weight-record` | Livestock | Record a weight measurement |
| `agri-herd-summary-report` | Livestock | Herd statistics summary |
| `agri-add-coop-member` | Cooperative | Register a cooperative member |
| `agri-list-coop-members` | Cooperative | List cooperative members |
| `agri-add-delivery-ticket` | Cooperative | Record a grain delivery |
| `agri-submit-delivery-ticket` | Cooperative | Submit a delivery ticket |
| `agri-cancel-delivery-ticket` | Cooperative | Cancel a delivery ticket |
| `agri-list-delivery-tickets` | Cooperative | List delivery tickets |
| `agri-calculate-patronage` | Cooperative | Calculate member patronage |
| `agri-add-pool-account` | Cooperative | Create a commodity pool |
| `agri-list-pool-accounts` | Cooperative | List pool accounts |
| `agri-cooperative-summary-report` | Cooperative | Cooperative statistics |
| `status` | System | Skill health check |

#!/usr/bin/env python3
"""AgricultureClaw schema extension -- adds agriculture management tables to the shared database.

20 tables: parcel, soil_test, land_use_record, crop_type, planting_plan, growth_stage,
seed_lot, field_operation, scouting_report, irrigation_log, chemical_application,
harvest_record, storage_bin, quality_grade, animal, health_record, feeding_record,
weight_record, coop_member, delivery_ticket, pool_account.

Prerequisite: ERPClaw init_db.py must have run first (creates foundation tables).
Run: python3 init_db.py [db_path]
"""
import os
import sqlite3
import sys

DEFAULT_DB_PATH = os.path.expanduser("~/.openclaw/erpclaw/data.sqlite")
DISPLAY_NAME = "AgricultureClaw"

REQUIRED_FOUNDATION = [
    "company", "naming_series", "audit_log",
]


def create_agricultureclaw_tables(db_path=None):
    db_path = db_path or os.environ.get("ERPCLAW_DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")

    # -- Verify ERPClaw foundation --
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    missing = [t for t in REQUIRED_FOUNDATION if t not in tables]
    if missing:
        print(f"ERROR: Foundation tables missing: {', '.join(missing)}")
        print("Run erpclaw-setup first: clawhub install erpclaw-setup")
        conn.close()
        sys.exit(1)

    tables_created = 0
    indexes_created = 0

    # ==================================================================
    # 1. agricultureclaw_parcel
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_parcel (
            id              TEXT PRIMARY KEY,
            naming_series   TEXT,
            name            TEXT NOT NULL,
            acreage         TEXT,
            gps_lat         TEXT,
            gps_lon         TEXT,
            soil_type       TEXT,
            land_use        TEXT NOT NULL DEFAULT 'cropland'
                            CHECK(land_use IN ('cropland','pasture','orchard','vineyard','timber','other')),
            owner           TEXT,
            lease_info      TEXT,
            parcel_status   TEXT NOT NULL DEFAULT 'active'
                            CHECK(parcel_status IN ('active','fallow','leased','retired')),
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_parcel_company ON agricultureclaw_parcel(company_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_parcel_status ON agricultureclaw_parcel(parcel_status)")
    indexes_created += 2

    # ==================================================================
    # 2. agricultureclaw_soil_test
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_soil_test (
            id              TEXT PRIMARY KEY,
            parcel_id       TEXT NOT NULL REFERENCES agricultureclaw_parcel(id),
            test_date       TEXT,
            ph              TEXT,
            nitrogen        TEXT,
            phosphorus      TEXT,
            potassium       TEXT,
            organic_matter  TEXT,
            lab_name        TEXT,
            notes           TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_soil_parcel ON agricultureclaw_soil_test(parcel_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_soil_company ON agricultureclaw_soil_test(company_id)")
    indexes_created += 2

    # ==================================================================
    # 3. agricultureclaw_land_use_record
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_land_use_record (
            id              TEXT PRIMARY KEY,
            parcel_id       TEXT NOT NULL REFERENCES agricultureclaw_parcel(id),
            season          TEXT,
            year            INTEGER,
            crop_type       TEXT,
            notes           TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_lur_parcel ON agricultureclaw_land_use_record(parcel_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_lur_company ON agricultureclaw_land_use_record(company_id)")
    indexes_created += 2

    # ==================================================================
    # 4. agricultureclaw_crop_type
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_crop_type (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            variety         TEXT,
            growing_season  TEXT,
            days_to_maturity INTEGER,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_crop_company ON agricultureclaw_crop_type(company_id)")
    indexes_created += 1

    # ==================================================================
    # 5. agricultureclaw_planting_plan
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_planting_plan (
            id              TEXT PRIMARY KEY,
            naming_series   TEXT,
            parcel_id       TEXT NOT NULL REFERENCES agricultureclaw_parcel(id),
            crop_type_id    TEXT NOT NULL REFERENCES agricultureclaw_crop_type(id),
            season          TEXT,
            year            INTEGER,
            planned_acres   TEXT,
            seed_lot_id     TEXT,
            planting_date   TEXT,
            expected_harvest_date TEXT,
            plan_status     TEXT NOT NULL DEFAULT 'planned'
                            CHECK(plan_status IN ('planned','active','harvested','abandoned')),
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_pp_parcel ON agricultureclaw_planting_plan(parcel_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_pp_crop ON agricultureclaw_planting_plan(crop_type_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_pp_company ON agricultureclaw_planting_plan(company_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_pp_status ON agricultureclaw_planting_plan(plan_status)")
    indexes_created += 4

    # ==================================================================
    # 6. agricultureclaw_growth_stage
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_growth_stage (
            id              TEXT PRIMARY KEY,
            planting_plan_id TEXT NOT NULL REFERENCES agricultureclaw_planting_plan(id),
            stage_name      TEXT NOT NULL,
            observed_date   TEXT,
            notes           TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_gs_plan ON agricultureclaw_growth_stage(planting_plan_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_gs_company ON agricultureclaw_growth_stage(company_id)")
    indexes_created += 2

    # ==================================================================
    # 7. agricultureclaw_seed_lot
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_seed_lot (
            id              TEXT PRIMARY KEY,
            crop_type_id    TEXT NOT NULL REFERENCES agricultureclaw_crop_type(id),
            lot_number      TEXT,
            quantity         TEXT,
            unit            TEXT,
            supplier        TEXT,
            purchase_date   TEXT,
            expiry_date     TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_sl_crop ON agricultureclaw_seed_lot(crop_type_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_sl_company ON agricultureclaw_seed_lot(company_id)")
    indexes_created += 2

    # ==================================================================
    # 8. agricultureclaw_field_operation
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_field_operation (
            id              TEXT PRIMARY KEY,
            naming_series   TEXT,
            parcel_id       TEXT NOT NULL REFERENCES agricultureclaw_parcel(id),
            operation_type  TEXT NOT NULL
                            CHECK(operation_type IN ('planting','spraying','irrigation','fertilization','tillage','other')),
            planned_date    TEXT,
            completed_date  TEXT,
            operator        TEXT,
            equipment       TEXT,
            cost            TEXT,
            notes           TEXT,
            op_status       TEXT NOT NULL DEFAULT 'planned'
                            CHECK(op_status IN ('planned','in_progress','completed','cancelled')),
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_fo_parcel ON agricultureclaw_field_operation(parcel_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_fo_company ON agricultureclaw_field_operation(company_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_fo_status ON agricultureclaw_field_operation(op_status)")
    indexes_created += 3

    # ==================================================================
    # 9. agricultureclaw_scouting_report
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_scouting_report (
            id              TEXT PRIMARY KEY,
            parcel_id       TEXT NOT NULL REFERENCES agricultureclaw_parcel(id),
            scout_date      TEXT,
            pest_found      TEXT,
            disease_found   TEXT,
            weed_pressure   TEXT CHECK(weed_pressure IN ('none','low','moderate','high')),
            crop_health     TEXT CHECK(crop_health IN ('excellent','good','fair','poor')),
            notes           TEXT,
            photos          TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_sr_parcel ON agricultureclaw_scouting_report(parcel_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_sr_company ON agricultureclaw_scouting_report(company_id)")
    indexes_created += 2

    # ==================================================================
    # 10. agricultureclaw_irrigation_log
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_irrigation_log (
            id              TEXT PRIMARY KEY,
            parcel_id       TEXT NOT NULL REFERENCES agricultureclaw_parcel(id),
            irrigation_date TEXT,
            method          TEXT CHECK(method IN ('pivot','drip','flood','sprinkler')),
            gallons         TEXT,
            duration_hours  TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_il_parcel ON agricultureclaw_irrigation_log(parcel_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_il_company ON agricultureclaw_irrigation_log(company_id)")
    indexes_created += 2

    # ==================================================================
    # 11. agricultureclaw_chemical_application
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_chemical_application (
            id              TEXT PRIMARY KEY,
            parcel_id       TEXT NOT NULL REFERENCES agricultureclaw_parcel(id),
            application_date TEXT,
            chemical_name   TEXT,
            epa_reg_number  TEXT,
            rate            TEXT,
            unit            TEXT,
            target          TEXT CHECK(target IN ('pest','weed','disease','nutrient')),
            applicator      TEXT,
            wind_speed      TEXT,
            temperature     TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_ca_parcel ON agricultureclaw_chemical_application(parcel_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_ca_company ON agricultureclaw_chemical_application(company_id)")
    indexes_created += 2

    # ==================================================================
    # 12. agricultureclaw_harvest_record
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_harvest_record (
            id              TEXT PRIMARY KEY,
            naming_series   TEXT,
            planting_plan_id TEXT REFERENCES agricultureclaw_planting_plan(id),
            parcel_id       TEXT NOT NULL REFERENCES agricultureclaw_parcel(id),
            harvest_date    TEXT,
            yield_amount    TEXT,
            yield_unit      TEXT,
            moisture_content TEXT,
            quality_grade   TEXT,
            storage_bin_id  TEXT,
            market_price    TEXT,
            revenue         TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_hr_parcel ON agricultureclaw_harvest_record(parcel_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_hr_plan ON agricultureclaw_harvest_record(planting_plan_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_hr_company ON agricultureclaw_harvest_record(company_id)")
    indexes_created += 3

    # ==================================================================
    # 13. agricultureclaw_storage_bin
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_storage_bin (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            bin_type        TEXT CHECK(bin_type IN ('silo','bin','warehouse','other')),
            capacity        TEXT,
            current_quantity TEXT,
            crop_type       TEXT,
            location        TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_sb_company ON agricultureclaw_storage_bin(company_id)")
    indexes_created += 1

    # ==================================================================
    # 14. agricultureclaw_quality_grade
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_quality_grade (
            id              TEXT PRIMARY KEY,
            harvest_id      TEXT NOT NULL REFERENCES agricultureclaw_harvest_record(id),
            grade           TEXT CHECK(grade IN ('1','2','3','sample_grade')),
            test_weight     TEXT,
            foreign_material TEXT,
            damage_pct      TEXT,
            notes           TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_qg_harvest ON agricultureclaw_quality_grade(harvest_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_qg_company ON agricultureclaw_quality_grade(company_id)")
    indexes_created += 2

    # ==================================================================
    # 15. agricultureclaw_animal
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_animal (
            id              TEXT PRIMARY KEY,
            naming_series   TEXT,
            tag_number      TEXT,
            species         TEXT NOT NULL
                            CHECK(species IN ('cattle','swine','poultry','sheep','goat','other')),
            breed           TEXT,
            birth_date      TEXT,
            gender          TEXT CHECK(gender IN ('male','female')),
            sire_id         TEXT,
            dam_id          TEXT,
            purchase_date   TEXT,
            purchase_cost   TEXT,
            current_weight  TEXT,
            animal_status   TEXT NOT NULL DEFAULT 'active'
                            CHECK(animal_status IN ('active','sold','deceased','transferred')),
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_animal_company ON agricultureclaw_animal(company_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_animal_species ON agricultureclaw_animal(species)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_animal_status ON agricultureclaw_animal(animal_status)")
    indexes_created += 3

    # ==================================================================
    # 16. agricultureclaw_health_record
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_health_record (
            id              TEXT PRIMARY KEY,
            animal_id       TEXT NOT NULL REFERENCES agricultureclaw_animal(id),
            record_date     TEXT,
            record_type     TEXT NOT NULL
                            CHECK(record_type IN ('vaccination','treatment','examination','deworming')),
            description     TEXT,
            veterinarian    TEXT,
            cost            TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_health_animal ON agricultureclaw_health_record(animal_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_health_company ON agricultureclaw_health_record(company_id)")
    indexes_created += 2

    # ==================================================================
    # 17. agricultureclaw_feeding_record
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_feeding_record (
            id              TEXT PRIMARY KEY,
            animal_id       TEXT NOT NULL REFERENCES agricultureclaw_animal(id),
            feed_date       TEXT,
            feed_type       TEXT,
            quantity        TEXT,
            unit            TEXT,
            cost            TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_feed_animal ON agricultureclaw_feeding_record(animal_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_feed_company ON agricultureclaw_feeding_record(company_id)")
    indexes_created += 2

    # ==================================================================
    # 18. agricultureclaw_weight_record
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_weight_record (
            id              TEXT PRIMARY KEY,
            animal_id       TEXT NOT NULL REFERENCES agricultureclaw_animal(id),
            weigh_date      TEXT,
            weight          TEXT,
            unit            TEXT DEFAULT 'lbs',
            notes           TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_weight_animal ON agricultureclaw_weight_record(animal_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_weight_company ON agricultureclaw_weight_record(company_id)")
    indexes_created += 2

    # ==================================================================
    # 19. agricultureclaw_coop_member
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_coop_member (
            id              TEXT PRIMARY KEY,
            naming_series   TEXT,
            name            TEXT NOT NULL,
            member_number   TEXT,
            shares          TEXT,
            join_date       TEXT,
            member_status   TEXT NOT NULL DEFAULT 'active'
                            CHECK(member_status IN ('active','inactive','suspended')),
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_coop_company ON agricultureclaw_coop_member(company_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_coop_status ON agricultureclaw_coop_member(member_status)")
    indexes_created += 2

    # ==================================================================
    # 20. agricultureclaw_delivery_ticket
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_delivery_ticket (
            id              TEXT PRIMARY KEY,
            naming_series   TEXT,
            member_id       TEXT NOT NULL REFERENCES agricultureclaw_coop_member(id),
            delivery_date   TEXT,
            commodity       TEXT,
            gross_weight    TEXT,
            tare_weight     TEXT,
            net_weight      TEXT,
            moisture        TEXT,
            grade           TEXT,
            price_per_unit  TEXT,
            total_amount    TEXT,
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_dt_member ON agricultureclaw_delivery_ticket(member_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_dt_company ON agricultureclaw_delivery_ticket(company_id)")
    indexes_created += 2

    # ==================================================================
    # 21. agricultureclaw_pool_account
    # ==================================================================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agricultureclaw_pool_account (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            commodity       TEXT,
            pool_year       INTEGER,
            total_quantity  TEXT,
            total_value     TEXT,
            members_count   INTEGER NOT NULL DEFAULT 0,
            pool_status     TEXT NOT NULL DEFAULT 'open'
                            CHECK(pool_status IN ('open','closed','distributed')),
            company_id      TEXT NOT NULL REFERENCES company(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    tables_created += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_pa_company ON agricultureclaw_pool_account(company_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agr_pa_status ON agricultureclaw_pool_account(pool_status)")
    indexes_created += 2

    conn.commit()
    conn.close()

    return {
        "database": db_path,
        "tables": tables_created,
        "indexes": indexes_created,
    }


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else None
    result = create_agricultureclaw_tables(db)
    print(f"{DISPLAY_NAME} schema created in {result['database']}")
    print(f"  Tables: {result['tables']}")
    print(f"  Indexes: {result['indexes']}")

#!/usr/bin/env python3
"""AgricultureClaw schema extension -- adds agriculture management tables to the shared database.

21 tables: parcel, soil_test, land_use_record, crop_type, planting_plan, growth_stage,
seed_lot, field_operation, scouting_report, irrigation_log, chemical_application,
harvest_record, storage_bin, quality_grade, animal, health_record, feeding_record,
weight_record, coop_member, delivery_ticket, pool_account.

Prerequisite: ERPClaw init_db.py must have run first (creates foundation tables).
Run: python3 init_db.py [db_path]

ADR-0034 phase 2 bulk-39. Schema declared as metadata and provisioned through
`erpclaw_lib.seam`, which emits dialect-correct DDL, replacing a hand-written
``CREATE TABLE`` block opened with ``sqlite3.connect`` that could not run on
PostgreSQL at all. Conversion rules are the pilot's (`erpclaw-esign`): seam
vocabulary only, and every amount this vertical carries -- acreage, operation and
feed and veterinary cost, market price, harvest revenue, animal purchase cost,
delivery-ticket weights and totals, co-op shares and pool value -- stays TEXT.

The pre-conversion docstring said "20 tables" while listing 21 names, and the
installer created all 21. The count was the stale half; corrected here.
"""
import importlib.util
import os
import sys

# Bootstrap the shared lib only when it is not already reachable — an
# unconditional insert at position 0 overrides a caller that deliberately bound a
# different tree (ADR-0034 phase 2 step 2d).
if importlib.util.find_spec("erpclaw_lib") is None:
    sys.path.insert(0, os.path.join(os.path.expanduser(
        os.environ.get("ERPCLAW_HOME", "~/.openclaw/erpclaw")), "lib"))

from erpclaw_lib.seam import (  # noqa: E402
    CheckConstraint, Column, ForeignKey, Index, Integer, MetaData, Table, Text,
    provision, reference_table, text,
)

DEFAULT_DB_PATH = os.path.join(os.path.expanduser(os.environ.get("ERPCLAW_HOME", "~/.openclaw/erpclaw")), "data.sqlite")
DISPLAY_NAME = "AgricultureClaw"

REQUIRED_FOUNDATION = [
    "company", "naming_series", "audit_log",
]

METADATA = MetaData()

# The one foundation table this module points at but does not own. Declared for
# foreign key resolution only and never created here — see `seam.reference_table`.
reference_table("company", METADATA)

# ==================================================================
# 1. agricultureclaw_parcel
# ==================================================================
PARCEL = Table(
    "agricultureclaw_parcel", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("naming_series", Text),
    Column("name", Text, nullable=False),
    Column("acreage", Text),
    Column("gps_lat", Text),
    Column("gps_lon", Text),
    Column("soil_type", Text),
    Column("land_use", Text, nullable=False, server_default=text("'cropland'")),
    Column("owner", Text),
    Column("lease_info", Text),
    Column("parcel_status", Text, nullable=False, server_default=text("'active'")),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("land_use IN ('cropland','pasture','orchard','vineyard','timber','other')",
                    name="ck_agricultureclaw_parcel_land_use"),
    CheckConstraint("parcel_status IN ('active','fallow','leased','retired')",
                    name="ck_agricultureclaw_parcel_parcel_status"),
)

Index("idx_agr_parcel_company", PARCEL.c.company_id)
Index("idx_agr_parcel_status", PARCEL.c.parcel_status)

# ==================================================================
# 2. agricultureclaw_soil_test
# ==================================================================
SOIL_TEST = Table(
    "agricultureclaw_soil_test", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("parcel_id", Text, ForeignKey("agricultureclaw_parcel.id"),
           nullable=False),
    Column("test_date", Text),
    Column("ph", Text),
    Column("nitrogen", Text),
    Column("phosphorus", Text),
    Column("potassium", Text),
    Column("organic_matter", Text),
    Column("lab_name", Text),
    Column("notes", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_agr_soil_parcel", SOIL_TEST.c.parcel_id)
Index("idx_agr_soil_company", SOIL_TEST.c.company_id)

# ==================================================================
# 3. agricultureclaw_land_use_record
# ==================================================================
LAND_USE_RECORD = Table(
    "agricultureclaw_land_use_record", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("parcel_id", Text, ForeignKey("agricultureclaw_parcel.id"),
           nullable=False),
    Column("season", Text),
    Column("year", Integer),
    Column("crop_type", Text),
    Column("notes", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_agr_lur_parcel", LAND_USE_RECORD.c.parcel_id)
Index("idx_agr_lur_company", LAND_USE_RECORD.c.company_id)

# ==================================================================
# 4. agricultureclaw_crop_type
# ==================================================================
CROP_TYPE = Table(
    "agricultureclaw_crop_type", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("name", Text, nullable=False),
    Column("variety", Text),
    Column("growing_season", Text),
    Column("days_to_maturity", Integer),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_agr_crop_company", CROP_TYPE.c.company_id)

# ==================================================================
# 5. agricultureclaw_planting_plan
# ==================================================================
# `seed_lot_id` names a seed lot but carries no foreign key, where every other
# parent reference in this table does. The asymmetry is the original's and is
# preserved — the same holds for `storage_bin_id` on harvest_record below.
PLANTING_PLAN = Table(
    "agricultureclaw_planting_plan", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("naming_series", Text),
    Column("parcel_id", Text, ForeignKey("agricultureclaw_parcel.id"),
           nullable=False),
    Column("crop_type_id", Text, ForeignKey("agricultureclaw_crop_type.id"),
           nullable=False),
    Column("season", Text),
    Column("year", Integer),
    Column("planned_acres", Text),
    Column("seed_lot_id", Text),
    Column("planting_date", Text),
    Column("expected_harvest_date", Text),
    Column("plan_status", Text, nullable=False, server_default=text("'planned'")),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("plan_status IN ('planned','active','harvested','abandoned')",
                    name="ck_agricultureclaw_planting_plan_plan_status"),
)

Index("idx_agr_pp_parcel", PLANTING_PLAN.c.parcel_id)
Index("idx_agr_pp_crop", PLANTING_PLAN.c.crop_type_id)
Index("idx_agr_pp_company", PLANTING_PLAN.c.company_id)
Index("idx_agr_pp_status", PLANTING_PLAN.c.plan_status)

# ==================================================================
# 6. agricultureclaw_growth_stage
# ==================================================================
GROWTH_STAGE = Table(
    "agricultureclaw_growth_stage", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("planting_plan_id", Text,
           ForeignKey("agricultureclaw_planting_plan.id"), nullable=False),
    Column("stage_name", Text, nullable=False),
    Column("observed_date", Text),
    Column("notes", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_agr_gs_plan", GROWTH_STAGE.c.planting_plan_id)
Index("idx_agr_gs_company", GROWTH_STAGE.c.company_id)

# ==================================================================
# 7. agricultureclaw_seed_lot
# ==================================================================
SEED_LOT = Table(
    "agricultureclaw_seed_lot", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("crop_type_id", Text, ForeignKey("agricultureclaw_crop_type.id"),
           nullable=False),
    Column("lot_number", Text),
    Column("quantity", Text),
    Column("unit", Text),
    Column("supplier", Text),
    Column("purchase_date", Text),
    Column("expiry_date", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_agr_sl_crop", SEED_LOT.c.crop_type_id)
Index("idx_agr_sl_company", SEED_LOT.c.company_id)

# ==================================================================
# 8. agricultureclaw_field_operation
# ==================================================================
FIELD_OPERATION = Table(
    "agricultureclaw_field_operation", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("naming_series", Text),
    Column("parcel_id", Text, ForeignKey("agricultureclaw_parcel.id"),
           nullable=False),
    Column("operation_type", Text, nullable=False),
    Column("planned_date", Text),
    Column("completed_date", Text),
    Column("operator", Text),
    Column("equipment", Text),
    Column("cost", Text),
    Column("notes", Text),
    Column("op_status", Text, nullable=False, server_default=text("'planned'")),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("operation_type IN ('planting','spraying','irrigation','fertilization','tillage','other')",
                    name="ck_agricultureclaw_field_operation_operation_type"),
    CheckConstraint("op_status IN ('planned','in_progress','completed','cancelled')",
                    name="ck_agricultureclaw_field_operation_op_status"),
)

Index("idx_agr_fo_parcel", FIELD_OPERATION.c.parcel_id)
Index("idx_agr_fo_company", FIELD_OPERATION.c.company_id)
Index("idx_agr_fo_status", FIELD_OPERATION.c.op_status)

# ==================================================================
# 9. agricultureclaw_scouting_report
# ==================================================================
SCOUTING_REPORT = Table(
    "agricultureclaw_scouting_report", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("parcel_id", Text, ForeignKey("agricultureclaw_parcel.id"),
           nullable=False),
    Column("scout_date", Text),
    Column("pest_found", Text),
    Column("disease_found", Text),
    Column("weed_pressure", Text),
    Column("crop_health", Text),
    Column("notes", Text),
    Column("photos", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("weed_pressure IN ('none','low','moderate','high')",
                    name="ck_agricultureclaw_scouting_report_weed_pressure"),
    CheckConstraint("crop_health IN ('excellent','good','fair','poor')",
                    name="ck_agricultureclaw_scouting_report_crop_health"),
)

Index("idx_agr_sr_parcel", SCOUTING_REPORT.c.parcel_id)
Index("idx_agr_sr_company", SCOUTING_REPORT.c.company_id)

# ==================================================================
# 10. agricultureclaw_irrigation_log
# ==================================================================
IRRIGATION_LOG = Table(
    "agricultureclaw_irrigation_log", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("parcel_id", Text, ForeignKey("agricultureclaw_parcel.id"),
           nullable=False),
    Column("irrigation_date", Text),
    Column("method", Text),
    Column("gallons", Text),
    Column("duration_hours", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("method IN ('pivot','drip','flood','sprinkler')",
                    name="ck_agricultureclaw_irrigation_log_method"),
)

Index("idx_agr_il_parcel", IRRIGATION_LOG.c.parcel_id)
Index("idx_agr_il_company", IRRIGATION_LOG.c.company_id)

# ==================================================================
# 11. agricultureclaw_chemical_application
# ==================================================================
CHEMICAL_APPLICATION = Table(
    "agricultureclaw_chemical_application", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("parcel_id", Text, ForeignKey("agricultureclaw_parcel.id"),
           nullable=False),
    Column("application_date", Text),
    Column("chemical_name", Text),
    Column("epa_reg_number", Text),
    Column("rate", Text),
    Column("unit", Text),
    Column("target", Text),
    Column("applicator", Text),
    Column("wind_speed", Text),
    Column("temperature", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("target IN ('pest','weed','disease','nutrient')",
                    name="ck_agricultureclaw_chemical_application_target"),
)

Index("idx_agr_ca_parcel", CHEMICAL_APPLICATION.c.parcel_id)
Index("idx_agr_ca_company", CHEMICAL_APPLICATION.c.company_id)

# ==================================================================
# 12. agricultureclaw_harvest_record
# ==================================================================
# The GL columns (`revenue_account_id`, `receivable_account_id`,
# `cost_center_id`) carry no foreign key in the original — this module does not
# declare `account` and never pointed at it. Left as plain columns.
HARVEST_RECORD = Table(
    "agricultureclaw_harvest_record", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("naming_series", Text),
    Column("planting_plan_id", Text,
           ForeignKey("agricultureclaw_planting_plan.id")),
    Column("parcel_id", Text, ForeignKey("agricultureclaw_parcel.id"),
           nullable=False),
    Column("harvest_date", Text),
    Column("yield_amount", Text),
    Column("yield_unit", Text),
    Column("moisture_content", Text),
    Column("quality_grade", Text),
    Column("storage_bin_id", Text),
    Column("market_price", Text),
    Column("revenue", Text),
    Column("sale_status", Text, nullable=False, server_default=text("'draft'")),
    Column("revenue_account_id", Text),
    Column("receivable_account_id", Text),
    Column("cost_center_id", Text),
    Column("gl_entry_ids", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("sale_status IN ('draft','submitted','cancelled')",
                    name="ck_agricultureclaw_harvest_record_sale_status"),
)

Index("idx_agr_hr_parcel", HARVEST_RECORD.c.parcel_id)
Index("idx_agr_hr_plan", HARVEST_RECORD.c.planting_plan_id)
Index("idx_agr_hr_company", HARVEST_RECORD.c.company_id)

# ==================================================================
# 13. agricultureclaw_storage_bin
# ==================================================================
STORAGE_BIN = Table(
    "agricultureclaw_storage_bin", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("name", Text, nullable=False),
    Column("bin_type", Text),
    Column("capacity", Text),
    Column("current_quantity", Text),
    Column("crop_type", Text),
    Column("location", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("bin_type IN ('silo','bin','warehouse','other')",
                    name="ck_agricultureclaw_storage_bin_bin_type"),
)

Index("idx_agr_sb_company", STORAGE_BIN.c.company_id)

# ==================================================================
# 14. agricultureclaw_quality_grade
# ==================================================================
QUALITY_GRADE = Table(
    "agricultureclaw_quality_grade", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("harvest_id", Text,
           ForeignKey("agricultureclaw_harvest_record.id"), nullable=False),
    Column("grade", Text),
    Column("test_weight", Text),
    Column("foreign_material", Text),
    Column("damage_pct", Text),
    Column("notes", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("grade IN ('1','2','3','sample_grade')",
                    name="ck_agricultureclaw_quality_grade_grade"),
)

Index("idx_agr_qg_harvest", QUALITY_GRADE.c.harvest_id)
Index("idx_agr_qg_company", QUALITY_GRADE.c.company_id)

# ==================================================================
# 15. agricultureclaw_animal
# ==================================================================
# `sire_id` and `dam_id` are self-references in meaning only: the original
# declares no foreign key back to this table, so neither does the conversion.
ANIMAL = Table(
    "agricultureclaw_animal", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("naming_series", Text),
    Column("tag_number", Text),
    Column("species", Text, nullable=False),
    Column("breed", Text),
    Column("birth_date", Text),
    Column("gender", Text),
    Column("sire_id", Text),
    Column("dam_id", Text),
    Column("purchase_date", Text),
    Column("purchase_cost", Text),
    Column("current_weight", Text),
    Column("animal_status", Text, nullable=False, server_default=text("'active'")),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("species IN ('cattle','swine','poultry','sheep','goat','other')",
                    name="ck_agricultureclaw_animal_species"),
    CheckConstraint("gender IN ('male','female')",
                    name="ck_agricultureclaw_animal_gender"),
    CheckConstraint("animal_status IN ('active','sold','deceased','transferred')",
                    name="ck_agricultureclaw_animal_animal_status"),
)

Index("idx_agr_animal_company", ANIMAL.c.company_id)
Index("idx_agr_animal_species", ANIMAL.c.species)
Index("idx_agr_animal_status", ANIMAL.c.animal_status)

# ==================================================================
# 16. agricultureclaw_health_record
# ==================================================================
HEALTH_RECORD = Table(
    "agricultureclaw_health_record", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("animal_id", Text, ForeignKey("agricultureclaw_animal.id"),
           nullable=False),
    Column("record_date", Text),
    Column("record_type", Text, nullable=False),
    Column("description", Text),
    Column("veterinarian", Text),
    Column("cost", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("record_type IN ('vaccination','treatment','examination','deworming')",
                    name="ck_agricultureclaw_health_record_record_type"),
)

Index("idx_agr_health_animal", HEALTH_RECORD.c.animal_id)
Index("idx_agr_health_company", HEALTH_RECORD.c.company_id)

# ==================================================================
# 17. agricultureclaw_feeding_record
# ==================================================================
FEEDING_RECORD = Table(
    "agricultureclaw_feeding_record", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("animal_id", Text, ForeignKey("agricultureclaw_animal.id"),
           nullable=False),
    Column("feed_date", Text),
    Column("feed_type", Text),
    Column("quantity", Text),
    Column("unit", Text),
    Column("cost", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_agr_feed_animal", FEEDING_RECORD.c.animal_id)
Index("idx_agr_feed_company", FEEDING_RECORD.c.company_id)

# ==================================================================
# 18. agricultureclaw_weight_record
# ==================================================================
WEIGHT_RECORD = Table(
    "agricultureclaw_weight_record", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("animal_id", Text, ForeignKey("agricultureclaw_animal.id"),
           nullable=False),
    Column("weigh_date", Text),
    Column("weight", Text),
    Column("unit", Text, server_default=text("'lbs'")),
    Column("notes", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_agr_weight_animal", WEIGHT_RECORD.c.animal_id)
Index("idx_agr_weight_company", WEIGHT_RECORD.c.company_id)

# ==================================================================
# 19. agricultureclaw_coop_member
# ==================================================================
COOP_MEMBER = Table(
    "agricultureclaw_coop_member", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("naming_series", Text),
    Column("name", Text, nullable=False),
    Column("member_number", Text),
    Column("shares", Text),
    Column("join_date", Text),
    Column("member_status", Text, nullable=False, server_default=text("'active'")),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("member_status IN ('active','inactive','suspended')",
                    name="ck_agricultureclaw_coop_member_member_status"),
)

Index("idx_agr_coop_company", COOP_MEMBER.c.company_id)
Index("idx_agr_coop_status", COOP_MEMBER.c.member_status)

# ==================================================================
# 20. agricultureclaw_delivery_ticket
# ==================================================================
DELIVERY_TICKET = Table(
    "agricultureclaw_delivery_ticket", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("naming_series", Text),
    Column("member_id", Text, ForeignKey("agricultureclaw_coop_member.id"),
           nullable=False),
    Column("delivery_date", Text),
    Column("commodity", Text),
    Column("gross_weight", Text),
    Column("tare_weight", Text),
    Column("net_weight", Text),
    Column("moisture", Text),
    Column("grade", Text),
    Column("price_per_unit", Text),
    Column("total_amount", Text),
    Column("ticket_status", Text, nullable=False, server_default=text("'draft'")),
    Column("revenue_account_id", Text),
    Column("receivable_account_id", Text),
    Column("cogs_account_id", Text),
    Column("inventory_account_id", Text),
    Column("cost_center_id", Text),
    Column("gl_entry_ids", Text),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("ticket_status IN ('draft','submitted','cancelled')",
                    name="ck_agricultureclaw_delivery_ticket_ticket_status"),
)

Index("idx_agr_dt_member", DELIVERY_TICKET.c.member_id)
Index("idx_agr_dt_company", DELIVERY_TICKET.c.company_id)

# ==================================================================
# 21. agricultureclaw_pool_account
# ==================================================================
# `members_count` is a count and stays Integer; `total_value` is money and stays
# Text, like every other amount in this module (ADR-0034 dec. 1).
POOL_ACCOUNT = Table(
    "agricultureclaw_pool_account", METADATA,
    Column("id", Text, primary_key=True, nullable=True),
    Column("name", Text, nullable=False),
    Column("commodity", Text),
    Column("pool_year", Integer),
    Column("total_quantity", Text),
    Column("total_value", Text),
    Column("members_count", Integer, nullable=False, server_default=text("0")),
    Column("pool_status", Text, nullable=False, server_default=text("'open'")),
    Column("company_id", Text, ForeignKey("company.id"), nullable=False),
    Column("created_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, nullable=False,
           server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("pool_status IN ('open','closed','distributed')",
                    name="ck_agricultureclaw_pool_account_pool_status"),
)

Index("idx_agr_pa_company", POOL_ACCOUNT.c.company_id)
Index("idx_agr_pa_status", POOL_ACCOUNT.c.pool_status)


def _require_foundation(db_path):
    """The pre-conversion installer's foundation probe, asked through the seam.

    The original read ``sqlite_master`` directly, so the guard that exists to
    produce a friendly error was itself SQLite-only. ``seam.table_exists``
    answers on both backends (ADR-0034 bulk-39). The wording is this module's
    own, unchanged.
    """
    from erpclaw_lib import seam

    missing = [t for t in REQUIRED_FOUNDATION if not seam.table_exists(t, db_path)]
    if missing:
        print(f"ERROR: Foundation tables missing: {', '.join(missing)}")
        print("Run erpclaw-setup first: clawhub install erpclaw-setup")
        sys.exit(1)


def create_agricultureclaw_tables(db_path=None):
    """Create AgricultureClaw tables and indexes on whichever backend is configured.

    Same contract as before the ADR-0034 conversion: idempotent, and the returned
    counts are what was ACTUALLY created rather than what was declared.
    """
    db_path = db_path or os.environ.get("ERPCLAW_DB_PATH", DEFAULT_DB_PATH)
    _require_foundation(db_path)
    result = provision(METADATA, db_path)
    return {
        "database": db_path,
        "tables": result["tables"],
        "indexes": result["indexes"],
    }


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else None
    result = create_agricultureclaw_tables(db)
    print(f"{DISPLAY_NAME} schema created in {result['database']}")
    print(f"  Tables: {result['tables']}")
    print(f"  Indexes: {result['indexes']}")

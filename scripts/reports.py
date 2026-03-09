"""AgricultureClaw -- Cross-domain reports and status module.

Provides aggregated reports spanning multiple domains and the skill status action.
Imported by db_query.py (unified router).
"""
import os
import sys
from decimal import Decimal

try:
    sys.path.insert(0, os.path.expanduser("~/.openclaw/erpclaw/lib"))
    from erpclaw_lib.response import ok, err, row_to_dict
except ImportError:
    pass

SKILL = "agricultureclaw"

ALL_TABLES = [
    "agricultureclaw_parcel", "agricultureclaw_soil_test", "agricultureclaw_land_use_record",
    "agricultureclaw_crop_type", "agricultureclaw_planting_plan", "agricultureclaw_growth_stage",
    "agricultureclaw_seed_lot",
    "agricultureclaw_field_operation", "agricultureclaw_scouting_report",
    "agricultureclaw_irrigation_log", "agricultureclaw_chemical_application",
    "agricultureclaw_harvest_record", "agricultureclaw_storage_bin", "agricultureclaw_quality_grade",
    "agricultureclaw_animal", "agricultureclaw_health_record", "agricultureclaw_feeding_record",
    "agricultureclaw_weight_record",
    "agricultureclaw_coop_member", "agricultureclaw_delivery_ticket", "agricultureclaw_pool_account",
]


# ===========================================================================
# status
# ===========================================================================
def status_action(conn, args):
    counts = {}
    for tbl in ALL_TABLES:
        try:
            counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        except Exception:
            counts[tbl] = -1  # table missing
    ok({
        "skill": SKILL,
        "version": "1.0.0",
        "total_tables": len(ALL_TABLES),
        "record_counts": counts,
    })


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------
ACTIONS = {
    "status": status_action,
}

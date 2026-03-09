#!/usr/bin/env python3
"""AgricultureClaw -- db_query.py (unified router)

Agriculture management: land, crops, field operations, harvest, livestock, cooperative.
All 67 actions are routed through this single entry point.

Usage: python3 db_query.py --action <action-name> [--flags ...]
Output: JSON to stdout, exit 0 on success, exit 1 on error.
"""
import argparse
import json
import os
import sys

# Add shared lib to path
try:
    sys.path.insert(0, os.path.expanduser("~/.openclaw/erpclaw/lib"))
    from erpclaw_lib.db import get_connection, ensure_db_exists, DEFAULT_DB_PATH
    from erpclaw_lib.response import ok, err
except ImportError:
    import json as _json
    print(_json.dumps({
        "status": "error",
        "error": "ERPClaw foundation not installed. Install erpclaw-setup first: clawhub install erpclaw-setup",
        "suggestion": "clawhub install erpclaw-setup"
    }))
    sys.exit(1)

# Add this script's directory so domain modules can be imported
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from land import ACTIONS as LAND_ACTIONS  # noqa: E402
from crops import ACTIONS as CROPS_ACTIONS  # noqa: E402
from field_ops import ACTIONS as FIELD_OPS_ACTIONS  # noqa: E402
from harvest import ACTIONS as HARVEST_ACTIONS  # noqa: E402
from livestock import ACTIONS as LIVESTOCK_ACTIONS  # noqa: E402
from cooperative import ACTIONS as COOPERATIVE_ACTIONS  # noqa: E402
from reports import ACTIONS as REPORTS_ACTIONS  # noqa: E402

# Merge all domain actions
ACTIONS = {}
ACTIONS.update(LAND_ACTIONS)
ACTIONS.update(CROPS_ACTIONS)
ACTIONS.update(FIELD_OPS_ACTIONS)
ACTIONS.update(HARVEST_ACTIONS)
ACTIONS.update(LIVESTOCK_ACTIONS)
ACTIONS.update(COOPERATIVE_ACTIONS)
ACTIONS.update(REPORTS_ACTIONS)

SKILL = "agricultureclaw"
REQUIRED_TABLES = ["company", "agricultureclaw_parcel", "agricultureclaw_crop_type", "agricultureclaw_animal"]


def main():
    parser = argparse.ArgumentParser(description=SKILL)
    parser.add_argument("--action", required=True, choices=sorted(ACTIONS.keys()))
    parser.add_argument("--db-path", default=None)

    # Entity IDs
    parser.add_argument("--id")
    parser.add_argument("--company-id")
    parser.add_argument("--parcel-id")
    parser.add_argument("--crop-type-id")
    parser.add_argument("--planting-plan-id")
    parser.add_argument("--seed-lot-id")
    parser.add_argument("--animal-id")
    parser.add_argument("--member-id")
    parser.add_argument("--harvest-id")
    parser.add_argument("--storage-bin-id")

    # Common fields
    parser.add_argument("--name")
    parser.add_argument("--notes")
    parser.add_argument("--search")

    # Land fields
    parser.add_argument("--acreage")
    parser.add_argument("--gps-lat")
    parser.add_argument("--gps-lon")
    parser.add_argument("--soil-type")
    parser.add_argument("--land-use")
    parser.add_argument("--owner")
    parser.add_argument("--lease-info")
    parser.add_argument("--parcel-status")

    # Soil test fields
    parser.add_argument("--test-date")
    parser.add_argument("--ph")
    parser.add_argument("--nitrogen")
    parser.add_argument("--phosphorus")
    parser.add_argument("--potassium")
    parser.add_argument("--organic-matter")
    parser.add_argument("--lab-name")

    # Land use record fields
    parser.add_argument("--season")
    parser.add_argument("--year", type=int)
    parser.add_argument("--crop-type")

    # Crop type fields
    parser.add_argument("--variety")
    parser.add_argument("--growing-season")
    parser.add_argument("--days-to-maturity", type=int)

    # Planting plan fields
    parser.add_argument("--planned-acres")
    parser.add_argument("--planting-date")
    parser.add_argument("--expected-harvest-date")
    parser.add_argument("--plan-status")

    # Growth stage fields
    parser.add_argument("--stage-name")
    parser.add_argument("--observed-date")

    # Seed lot fields
    parser.add_argument("--lot-number")
    parser.add_argument("--quantity")
    parser.add_argument("--unit")
    parser.add_argument("--supplier")
    parser.add_argument("--purchase-date")
    parser.add_argument("--expiry-date")

    # Field operation fields
    parser.add_argument("--operation-type")
    parser.add_argument("--planned-date")
    parser.add_argument("--completed-date")
    parser.add_argument("--operator")
    parser.add_argument("--equipment")
    parser.add_argument("--cost")
    parser.add_argument("--op-status")

    # Scouting report fields
    parser.add_argument("--scout-date")
    parser.add_argument("--pest-found")
    parser.add_argument("--disease-found")
    parser.add_argument("--weed-pressure")
    parser.add_argument("--crop-health")
    parser.add_argument("--photos")

    # Irrigation fields
    parser.add_argument("--irrigation-date")
    parser.add_argument("--method")
    parser.add_argument("--gallons")
    parser.add_argument("--duration-hours")

    # Chemical application fields
    parser.add_argument("--application-date")
    parser.add_argument("--chemical-name")
    parser.add_argument("--epa-reg-number")
    parser.add_argument("--rate")
    parser.add_argument("--target")
    parser.add_argument("--applicator")
    parser.add_argument("--wind-speed")
    parser.add_argument("--temperature")

    # Harvest fields
    parser.add_argument("--harvest-date")
    parser.add_argument("--yield-amount")
    parser.add_argument("--yield-unit")
    parser.add_argument("--moisture-content")
    parser.add_argument("--quality-grade")
    parser.add_argument("--market-price")
    parser.add_argument("--revenue")

    # Storage bin fields
    parser.add_argument("--bin-type")
    parser.add_argument("--capacity")
    parser.add_argument("--current-quantity")
    parser.add_argument("--location")

    # Quality grade fields
    parser.add_argument("--grade")
    parser.add_argument("--test-weight")
    parser.add_argument("--foreign-material")
    parser.add_argument("--damage-pct")

    # Animal fields
    parser.add_argument("--tag-number")
    parser.add_argument("--species")
    parser.add_argument("--breed")
    parser.add_argument("--birth-date")
    parser.add_argument("--gender")
    parser.add_argument("--sire-id")
    parser.add_argument("--dam-id")
    parser.add_argument("--purchase-cost")
    parser.add_argument("--current-weight")
    parser.add_argument("--animal-status")

    # Health record fields
    parser.add_argument("--record-date")
    parser.add_argument("--record-type")
    parser.add_argument("--description")
    parser.add_argument("--veterinarian")

    # Feeding record fields
    parser.add_argument("--feed-date")
    parser.add_argument("--feed-type")

    # Weight record fields
    parser.add_argument("--weigh-date")
    parser.add_argument("--weight")

    # Co-op member fields
    parser.add_argument("--member-number")
    parser.add_argument("--shares")
    parser.add_argument("--join-date")
    parser.add_argument("--member-status")

    # Delivery ticket fields
    parser.add_argument("--delivery-date")
    parser.add_argument("--commodity")
    parser.add_argument("--gross-weight")
    parser.add_argument("--tare-weight")
    parser.add_argument("--net-weight")
    parser.add_argument("--moisture")
    parser.add_argument("--price-per-unit")
    parser.add_argument("--total-amount")

    # Pool account fields
    parser.add_argument("--pool-year", type=int)
    parser.add_argument("--total-quantity")
    parser.add_argument("--total-value")
    parser.add_argument("--members-count", type=int)
    parser.add_argument("--pool-status")

    # GL account fields (for commodity sale posting)
    parser.add_argument("--revenue-account-id")
    parser.add_argument("--receivable-account-id")
    parser.add_argument("--cogs-account-id")
    parser.add_argument("--inventory-account-id")
    parser.add_argument("--cost-center-id")
    parser.add_argument("--cogs-amount")

    # Pagination
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)

    args, _unknown = parser.parse_known_args()

    # DB setup
    db_path = args.db_path or os.environ.get("ERPCLAW_DB_PATH", DEFAULT_DB_PATH)
    ensure_db_exists(db_path)
    conn = get_connection(db_path)

    # Check required tables exist
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    missing = [t for t in REQUIRED_TABLES if t not in tables]
    if missing:
        conn.close()
        err(f"Missing tables: {', '.join(missing)}. Run init_db.py first.",
            suggestion="python3 init_db.py")

    try:
        ACTIONS[args.action](conn, args)
    except Exception as e:
        conn.rollback()
        sys.stderr.write(f"[{SKILL}] {e}\n")
        err(str(e))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

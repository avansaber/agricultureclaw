"""AgricultureClaw -- Land management domain module.

Actions for parcels, soil tests, and land use records (3 tables, 10 actions).
Imported by db_query.py (unified router).
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

try:
    sys.path.insert(0, os.path.expanduser("~/.openclaw/erpclaw/lib"))
    from erpclaw_lib.naming import get_next_name, ENTITY_PREFIXES
    from erpclaw_lib.response import ok, err, row_to_dict
    from erpclaw_lib.audit import audit

    ENTITY_PREFIXES.setdefault("parcel", "PRC-")
except ImportError:
    pass

SKILL = "agricultureclaw"

_now_iso = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_LAND_USE = ("cropland", "pasture", "orchard", "vineyard", "timber", "other")
VALID_PARCEL_STATUS = ("active", "fallow", "leased", "retired")


def _validate_company(conn, company_id):
    if not company_id:
        err("--company-id is required")
    if not conn.execute("SELECT id FROM company WHERE id = ?", (company_id,)).fetchone():
        err(f"Company {company_id} not found")


def _validate_parcel(conn, parcel_id):
    if not parcel_id:
        err("--parcel-id is required")
    if not conn.execute("SELECT id FROM agricultureclaw_parcel WHERE id = ?", (parcel_id,)).fetchone():
        err(f"Parcel {parcel_id} not found")


# ===========================================================================
# 1. add-parcel
# ===========================================================================
def add_parcel(conn, args):
    _validate_company(conn, args.company_id)
    name = getattr(args, "name", None)
    if not name:
        err("--name is required")

    land_use = getattr(args, "land_use", None) or "cropland"
    if land_use not in VALID_LAND_USE:
        err(f"Invalid land-use: {land_use}. Must be one of: {', '.join(VALID_LAND_USE)}")

    parcel_status = getattr(args, "parcel_status", None) or "active"
    if parcel_status not in VALID_PARCEL_STATUS:
        err(f"Invalid parcel-status: {parcel_status}. Must be one of: {', '.join(VALID_PARCEL_STATUS)}")

    parcel_id = str(uuid.uuid4())
    conn.company_id = args.company_id
    naming = get_next_name(conn, "parcel", company_id=args.company_id)
    now = _now_iso()

    conn.execute("""
        INSERT INTO agricultureclaw_parcel (
            id, naming_series, name, acreage, gps_lat, gps_lon, soil_type,
            land_use, owner, lease_info, parcel_status, company_id,
            created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        parcel_id, naming, name,
        getattr(args, "acreage", None),
        getattr(args, "gps_lat", None),
        getattr(args, "gps_lon", None),
        getattr(args, "soil_type", None),
        land_use,
        getattr(args, "owner", None),
        getattr(args, "lease_info", None),
        parcel_status,
        args.company_id, now, now,
    ))
    audit(conn, SKILL, "agri-add-parcel", "agricultureclaw_parcel", parcel_id,
          new_values={"name": name, "acreage": getattr(args, "acreage", None)})
    conn.commit()
    ok({"id": parcel_id, "naming_series": naming, "name": name, "parcel_status": parcel_status})


# ===========================================================================
# 2. update-parcel
# ===========================================================================
def update_parcel(conn, args):
    parcel_id = getattr(args, "id", None)
    if not parcel_id:
        err("--id is required")
    if not conn.execute("SELECT id FROM agricultureclaw_parcel WHERE id = ?", (parcel_id,)).fetchone():
        err(f"Parcel {parcel_id} not found")

    updates, params, changed = [], [], []
    for arg_name, col_name in {
        "name": "name", "acreage": "acreage", "gps_lat": "gps_lat", "gps_lon": "gps_lon",
        "soil_type": "soil_type", "owner": "owner", "lease_info": "lease_info",
    }.items():
        val = getattr(args, arg_name, None)
        if val is not None:
            updates.append(f"{col_name} = ?")
            params.append(val)
            changed.append(col_name)

    land_use = getattr(args, "land_use", None)
    if land_use is not None:
        if land_use not in VALID_LAND_USE:
            err(f"Invalid land-use: {land_use}. Must be one of: {', '.join(VALID_LAND_USE)}")
        updates.append("land_use = ?")
        params.append(land_use)
        changed.append("land_use")

    parcel_status = getattr(args, "parcel_status", None)
    if parcel_status is not None:
        if parcel_status not in VALID_PARCEL_STATUS:
            err(f"Invalid parcel-status: {parcel_status}. Must be one of: {', '.join(VALID_PARCEL_STATUS)}")
        updates.append("parcel_status = ?")
        params.append(parcel_status)
        changed.append("parcel_status")

    if not updates:
        err("No fields to update")

    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(parcel_id)
    conn.execute(f"UPDATE agricultureclaw_parcel SET {', '.join(updates)} WHERE id = ?", params)
    audit(conn, SKILL, "agri-update-parcel", "agricultureclaw_parcel", parcel_id,
          new_values={"updated_fields": changed})
    conn.commit()
    ok({"id": parcel_id, "updated_fields": changed})


# ===========================================================================
# 3. get-parcel
# ===========================================================================
def get_parcel(conn, args):
    parcel_id = getattr(args, "id", None)
    if not parcel_id:
        err("--id is required")
    row = conn.execute("SELECT * FROM agricultureclaw_parcel WHERE id = ?", (parcel_id,)).fetchone()
    if not row:
        err(f"Parcel {parcel_id} not found")
    data = row_to_dict(row)

    # Include soil tests
    soil_tests = conn.execute(
        "SELECT * FROM agricultureclaw_soil_test WHERE parcel_id = ? ORDER BY test_date DESC",
        (parcel_id,)
    ).fetchall()
    data["soil_tests"] = [row_to_dict(s) for s in soil_tests]

    # Include land use records
    land_use_recs = conn.execute(
        "SELECT * FROM agricultureclaw_land_use_record WHERE parcel_id = ? ORDER BY year DESC",
        (parcel_id,)
    ).fetchall()
    data["land_use_records"] = [row_to_dict(r) for r in land_use_recs]
    ok(data)


# ===========================================================================
# 4. list-parcels
# ===========================================================================
def list_parcels(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "parcel_status", None):
        where.append("parcel_status = ?")
        params.append(args.parcel_status)
    if getattr(args, "search", None):
        where.append("(name LIKE ?)")
        params.append(f"%{args.search}%")

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_parcel WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_parcel WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 5. add-soil-test
# ===========================================================================
def add_soil_test(conn, args):
    _validate_company(conn, args.company_id)
    parcel_id = getattr(args, "parcel_id", None)
    _validate_parcel(conn, parcel_id)

    test_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO agricultureclaw_soil_test (
            id, parcel_id, test_date, ph, nitrogen, phosphorus, potassium,
            organic_matter, lab_name, notes, company_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        test_id, parcel_id,
        getattr(args, "test_date", None),
        getattr(args, "ph", None),
        getattr(args, "nitrogen", None),
        getattr(args, "phosphorus", None),
        getattr(args, "potassium", None),
        getattr(args, "organic_matter", None),
        getattr(args, "lab_name", None),
        getattr(args, "notes", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-soil-test", "agricultureclaw_soil_test", test_id,
          new_values={"parcel_id": parcel_id})
    conn.commit()
    ok({"id": test_id, "parcel_id": parcel_id})


# ===========================================================================
# 6. list-soil-tests
# ===========================================================================
def list_soil_tests(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "parcel_id", None):
        where.append("parcel_id = ?")
        params.append(args.parcel_id)
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_soil_test WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_soil_test WHERE {where_sql} ORDER BY test_date DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 7. add-land-use-record
# ===========================================================================
def add_land_use_record(conn, args):
    _validate_company(conn, args.company_id)
    parcel_id = getattr(args, "parcel_id", None)
    _validate_parcel(conn, parcel_id)

    rec_id = str(uuid.uuid4())
    year_val = getattr(args, "year", None)
    conn.execute("""
        INSERT INTO agricultureclaw_land_use_record (
            id, parcel_id, season, year, crop_type, notes, company_id
        ) VALUES (?,?,?,?,?,?,?)
    """, (
        rec_id, parcel_id,
        getattr(args, "season", None),
        int(year_val) if year_val is not None else None,
        getattr(args, "crop_type", None),
        getattr(args, "notes", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-land-use-record", "agricultureclaw_land_use_record", rec_id,
          new_values={"parcel_id": parcel_id})
    conn.commit()
    ok({"id": rec_id, "parcel_id": parcel_id})


# ===========================================================================
# 8. list-land-use-records
# ===========================================================================
def list_land_use_records(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "parcel_id", None):
        where.append("parcel_id = ?")
        params.append(args.parcel_id)
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_land_use_record WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_land_use_record WHERE {where_sql} ORDER BY year DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 9. parcel-summary
# ===========================================================================
def parcel_summary(conn, args):
    parcel_id = getattr(args, "id", None)
    if not parcel_id:
        err("--id is required")
    row = conn.execute("SELECT * FROM agricultureclaw_parcel WHERE id = ?", (parcel_id,)).fetchone()
    if not row:
        err(f"Parcel {parcel_id} not found")
    data = row_to_dict(row)

    soil_count = conn.execute(
        "SELECT COUNT(*) FROM agricultureclaw_soil_test WHERE parcel_id = ?", (parcel_id,)
    ).fetchone()[0]
    lur_count = conn.execute(
        "SELECT COUNT(*) FROM agricultureclaw_land_use_record WHERE parcel_id = ?", (parcel_id,)
    ).fetchone()[0]
    op_count = conn.execute(
        "SELECT COUNT(*) FROM agricultureclaw_field_operation WHERE parcel_id = ?", (parcel_id,)
    ).fetchone()[0]
    harvest_count = conn.execute(
        "SELECT COUNT(*) FROM agricultureclaw_harvest_record WHERE parcel_id = ?", (parcel_id,)
    ).fetchone()[0]

    data["soil_test_count"] = soil_count
    data["land_use_record_count"] = lur_count
    data["field_operation_count"] = op_count
    data["harvest_record_count"] = harvest_count
    ok(data)


# ===========================================================================
# 10. land-utilization-report
# ===========================================================================
def land_utilization_report(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    rows = conn.execute(
        f"SELECT land_use, parcel_status, COUNT(*) as cnt FROM agricultureclaw_parcel WHERE {where_sql} GROUP BY land_use, parcel_status",
        params
    ).fetchall()

    total_parcels = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_parcel WHERE {where_sql}", params
    ).fetchone()[0]

    # Sum acreage by land_use
    acreage_rows = conn.execute(
        f"SELECT land_use, acreage FROM agricultureclaw_parcel WHERE {where_sql}", params
    ).fetchall()
    acreage_by_use = {}
    for r in acreage_rows:
        lu = r["land_use"]
        ac = r["acreage"]
        if ac:
            acreage_by_use[lu] = str(Decimal(acreage_by_use.get(lu, "0")) + Decimal(ac))

    ok({
        "total_parcels": total_parcels,
        "by_use_and_status": [row_to_dict(r) for r in rows],
        "acreage_by_land_use": acreage_by_use,
    })


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------
ACTIONS = {
    "agri-add-parcel": add_parcel,
    "agri-update-parcel": update_parcel,
    "agri-get-parcel": get_parcel,
    "agri-list-parcels": list_parcels,
    "agri-add-soil-test": add_soil_test,
    "agri-list-soil-tests": list_soil_tests,
    "agri-add-land-use-record": add_land_use_record,
    "agri-list-land-use-records": list_land_use_records,
    "agri-parcel-summary": parcel_summary,
    "agri-land-utilization-report": land_utilization_report,
}

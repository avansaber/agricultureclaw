"""AgricultureClaw -- Harvest management domain module.

Actions for harvest records, storage bins, quality grades, and reports (3 tables, 10 actions).
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

    ENTITY_PREFIXES.setdefault("harvest_record", "HRV-")
except ImportError:
    pass

SKILL = "agricultureclaw"

_now_iso = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_BIN_TYPES = ("silo", "bin", "warehouse", "other")
VALID_GRADES = ("1", "2", "3", "sample_grade")


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
# 1. add-harvest-record
# ===========================================================================
def add_harvest_record(conn, args):
    _validate_company(conn, args.company_id)
    parcel_id = getattr(args, "parcel_id", None)
    _validate_parcel(conn, parcel_id)

    planting_plan_id = getattr(args, "planting_plan_id", None)
    if planting_plan_id:
        if not conn.execute("SELECT id FROM agricultureclaw_planting_plan WHERE id = ?", (planting_plan_id,)).fetchone():
            err(f"Planting plan {planting_plan_id} not found")

    storage_bin_id = getattr(args, "storage_bin_id", None)
    if storage_bin_id:
        if not conn.execute("SELECT id FROM agricultureclaw_storage_bin WHERE id = ?", (storage_bin_id,)).fetchone():
            err(f"Storage bin {storage_bin_id} not found")

    hr_id = str(uuid.uuid4())
    conn.company_id = args.company_id
    naming = get_next_name(conn, "harvest_record", company_id=args.company_id)
    now = _now_iso()

    conn.execute("""
        INSERT INTO agricultureclaw_harvest_record (
            id, naming_series, planting_plan_id, parcel_id, harvest_date,
            yield_amount, yield_unit, moisture_content, quality_grade,
            storage_bin_id, market_price, revenue, company_id,
            created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        hr_id, naming, planting_plan_id, parcel_id,
        getattr(args, "harvest_date", None),
        getattr(args, "yield_amount", None),
        getattr(args, "yield_unit", None),
        getattr(args, "moisture_content", None),
        getattr(args, "quality_grade", None),
        storage_bin_id,
        getattr(args, "market_price", None),
        getattr(args, "revenue", None),
        args.company_id, now, now,
    ))
    audit(conn, SKILL, "agri-add-harvest-record", "agricultureclaw_harvest_record", hr_id,
          new_values={"parcel_id": parcel_id, "yield_amount": getattr(args, "yield_amount", None)})
    conn.commit()
    ok({"id": hr_id, "naming_series": naming, "parcel_id": parcel_id})


# ===========================================================================
# 2. update-harvest-record
# ===========================================================================
def update_harvest_record(conn, args):
    hr_id = getattr(args, "id", None)
    if not hr_id:
        err("--id is required")
    if not conn.execute("SELECT id FROM agricultureclaw_harvest_record WHERE id = ?", (hr_id,)).fetchone():
        err(f"Harvest record {hr_id} not found")

    updates, params, changed = [], [], []
    for arg_name, col_name in {
        "harvest_date": "harvest_date", "yield_amount": "yield_amount",
        "yield_unit": "yield_unit", "moisture_content": "moisture_content",
        "quality_grade": "quality_grade", "market_price": "market_price",
        "revenue": "revenue",
    }.items():
        val = getattr(args, arg_name, None)
        if val is not None:
            updates.append(f"{col_name} = ?")
            params.append(val)
            changed.append(col_name)

    if not updates:
        err("No fields to update")

    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(hr_id)
    conn.execute(f"UPDATE agricultureclaw_harvest_record SET {', '.join(updates)} WHERE id = ?", params)
    audit(conn, SKILL, "agri-update-harvest-record", "agricultureclaw_harvest_record", hr_id,
          new_values={"updated_fields": changed})
    conn.commit()
    ok({"id": hr_id, "updated_fields": changed})


# ===========================================================================
# 3. list-harvest-records
# ===========================================================================
def list_harvest_records(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "parcel_id", None):
        where.append("parcel_id = ?")
        params.append(args.parcel_id)
    if getattr(args, "planting_plan_id", None):
        where.append("planting_plan_id = ?")
        params.append(args.planting_plan_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_harvest_record WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_harvest_record WHERE {where_sql} ORDER BY harvest_date DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 4. add-storage-bin
# ===========================================================================
def add_storage_bin(conn, args):
    _validate_company(conn, args.company_id)
    name = getattr(args, "name", None)
    if not name:
        err("--name is required")

    bin_type = getattr(args, "bin_type", None)
    if bin_type and bin_type not in VALID_BIN_TYPES:
        err(f"Invalid bin-type: {bin_type}. Must be one of: {', '.join(VALID_BIN_TYPES)}")

    sb_id = str(uuid.uuid4())
    now = _now_iso()
    conn.execute("""
        INSERT INTO agricultureclaw_storage_bin (
            id, name, bin_type, capacity, current_quantity, crop_type,
            location, company_id, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        sb_id, name, bin_type,
        getattr(args, "capacity", None),
        getattr(args, "current_quantity", None) or "0",
        getattr(args, "crop_type", None),
        getattr(args, "location", None),
        args.company_id, now, now,
    ))
    audit(conn, SKILL, "agri-add-storage-bin", "agricultureclaw_storage_bin", sb_id,
          new_values={"name": name})
    conn.commit()
    ok({"id": sb_id, "name": name})


# ===========================================================================
# 5. list-storage-bins
# ===========================================================================
def list_storage_bins(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_storage_bin WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_storage_bin WHERE {where_sql} ORDER BY name ASC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 6. add-quality-grade
# ===========================================================================
def add_quality_grade(conn, args):
    _validate_company(conn, args.company_id)
    harvest_id = getattr(args, "harvest_id", None)
    if not harvest_id:
        err("--harvest-id is required")
    if not conn.execute("SELECT id FROM agricultureclaw_harvest_record WHERE id = ?", (harvest_id,)).fetchone():
        err(f"Harvest record {harvest_id} not found")

    grade = getattr(args, "grade", None)
    if grade and grade not in VALID_GRADES:
        err(f"Invalid grade: {grade}. Must be one of: {', '.join(VALID_GRADES)}")

    qg_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO agricultureclaw_quality_grade (
            id, harvest_id, grade, test_weight, foreign_material,
            damage_pct, notes, company_id
        ) VALUES (?,?,?,?,?,?,?,?)
    """, (
        qg_id, harvest_id, grade,
        getattr(args, "test_weight", None),
        getattr(args, "foreign_material", None),
        getattr(args, "damage_pct", None),
        getattr(args, "notes", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-quality-grade", "agricultureclaw_quality_grade", qg_id,
          new_values={"harvest_id": harvest_id, "grade": grade})
    conn.commit()
    ok({"id": qg_id, "harvest_id": harvest_id, "grade": grade})


# ===========================================================================
# 7. list-quality-grades
# ===========================================================================
def list_quality_grades(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "harvest_id", None):
        where.append("harvest_id = ?")
        params.append(args.harvest_id)
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_quality_grade WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_quality_grade WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 8. yield-analysis-report
# ===========================================================================
def yield_analysis_report(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("hr.company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    rows = conn.execute(f"""
        SELECT hr.parcel_id, p.name as parcel_name,
               COUNT(*) as harvest_count,
               hr.yield_unit
        FROM agricultureclaw_harvest_record hr
        JOIN agricultureclaw_parcel p ON hr.parcel_id = p.id
        WHERE {where_sql}
        GROUP BY hr.parcel_id, hr.yield_unit
    """, params).fetchall()

    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": len(rows),
    })


# ===========================================================================
# 9. harvest-summary
# ===========================================================================
def harvest_summary(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_harvest_record WHERE {where_sql}", params
    ).fetchone()[0]

    ok({
        "total_harvest_records": total,
    })


# ===========================================================================
# 10. crop-profitability-report
# ===========================================================================
def crop_profitability_report(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("hr.company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    rows = conn.execute(f"""
        SELECT hr.parcel_id, p.name as parcel_name,
               hr.revenue, hr.market_price, hr.yield_amount, hr.yield_unit
        FROM agricultureclaw_harvest_record hr
        JOIN agricultureclaw_parcel p ON hr.parcel_id = p.id
        WHERE {where_sql}
        ORDER BY hr.harvest_date DESC
    """, params).fetchall()

    total_revenue = Decimal("0")
    for r in rows:
        rev = r["revenue"]
        if rev:
            total_revenue += Decimal(rev)

    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": len(rows),
        "total_revenue": str(total_revenue),
    })


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------
ACTIONS = {
    "agri-add-harvest-record": add_harvest_record,
    "agri-update-harvest-record": update_harvest_record,
    "agri-list-harvest-records": list_harvest_records,
    "agri-add-storage-bin": add_storage_bin,
    "agri-list-storage-bins": list_storage_bins,
    "agri-add-quality-grade": add_quality_grade,
    "agri-list-quality-grades": list_quality_grades,
    "agri-yield-analysis-report": yield_analysis_report,
    "agri-harvest-summary": harvest_summary,
    "agri-crop-profitability-report": crop_profitability_report,
}

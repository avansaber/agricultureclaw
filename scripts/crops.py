"""AgricultureClaw -- Crops management domain module.

Actions for crop types, planting plans, growth stages, and seed lots (4 tables, 12 actions).
Imported by db_query.py (unified router).
"""
import os
import sys
import uuid
from datetime import datetime, timezone

try:
    sys.path.insert(0, os.path.expanduser("~/.openclaw/erpclaw/lib"))
    from erpclaw_lib.naming import get_next_name, ENTITY_PREFIXES
    from erpclaw_lib.response import ok, err, row_to_dict
    from erpclaw_lib.audit import audit
    from erpclaw_lib.query import Q, P, Table, Field, fn, Order, insert_row, update_row

    ENTITY_PREFIXES.setdefault("planting_plan", "PP-")
except ImportError:
    pass

SKILL = "agricultureclaw"

_now_iso = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_PLAN_STATUS = ("planned", "active", "harvested", "abandoned")


def _validate_company(conn, company_id):
    if not company_id:
        err("--company-id is required")
    if not conn.execute(Q.from_(Table("company")).select(Field("id")).where(Field("id") == P()).get_sql(), (company_id,)).fetchone():
        err(f"Company {company_id} not found")


def _validate_parcel(conn, parcel_id):
    if not parcel_id:
        err("--parcel-id is required")
    if not conn.execute(Q.from_(Table("agricultureclaw_parcel")).select(Field("id")).where(Field("id") == P()).get_sql(), (parcel_id,)).fetchone():
        err(f"Parcel {parcel_id} not found")


def _validate_crop_type(conn, crop_type_id):
    if not crop_type_id:
        err("--crop-type-id is required")
    if not conn.execute(Q.from_(Table("agricultureclaw_crop_type")).select(Field("id")).where(Field("id") == P()).get_sql(), (crop_type_id,)).fetchone():
        err(f"Crop type {crop_type_id} not found")


# ===========================================================================
# 1. add-crop-type
# ===========================================================================
def add_crop_type(conn, args):
    _validate_company(conn, args.company_id)
    name = getattr(args, "name", None)
    if not name:
        err("--name is required")

    ct_id = str(uuid.uuid4())
    days = getattr(args, "days_to_maturity", None)
    sql, _ = insert_row("agricultureclaw_crop_type", {"id": P(), "name": P(), "variety": P(), "growing_season": P(), "days_to_maturity": P(), "company_id": P()})
    conn.execute(sql, (
        ct_id, name,
        getattr(args, "variety", None),
        getattr(args, "growing_season", None),
        int(days) if days is not None else None,
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-crop-type", "agricultureclaw_crop_type", ct_id,
          new_values={"name": name})
    conn.commit()
    ok({"id": ct_id, "name": name})


# ===========================================================================
# 2. list-crop-types
# ===========================================================================
def list_crop_types(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "search", None):
        where.append("(name LIKE ? OR variety LIKE ?)")
        params.extend([f"%{args.search}%", f"%{args.search}%"])

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_crop_type WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_crop_type WHERE {where_sql} ORDER BY name ASC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 3. add-planting-plan
# ===========================================================================
def add_planting_plan(conn, args):
    _validate_company(conn, args.company_id)
    parcel_id = getattr(args, "parcel_id", None)
    _validate_parcel(conn, parcel_id)
    crop_type_id = getattr(args, "crop_type_id", None)
    _validate_crop_type(conn, crop_type_id)

    pp_id = str(uuid.uuid4())
    conn.company_id = args.company_id
    naming = get_next_name(conn, "planting_plan", company_id=args.company_id)
    now = _now_iso()
    year_val = getattr(args, "year", None)

    sql, _ = insert_row("agricultureclaw_planting_plan", {"id": P(), "naming_series": P(), "parcel_id": P(), "crop_type_id": P(), "season": P(), "year": P(), "planned_acres": P(), "seed_lot_id": P(), "planting_date": P(), "expected_harvest_date": P(), "plan_status": P(), "company_id": P(), "created_at": P(), "updated_at": P()})
    conn.execute(sql, (
        pp_id, naming, parcel_id, crop_type_id,
        getattr(args, "season", None),
        int(year_val) if year_val is not None else None,
        getattr(args, "planned_acres", None),
        getattr(args, "seed_lot_id", None),
        getattr(args, "planting_date", None),
        getattr(args, "expected_harvest_date", None),
        "planned",
        args.company_id, now, now,
    ))
    audit(conn, SKILL, "agri-add-planting-plan", "agricultureclaw_planting_plan", pp_id,
          new_values={"parcel_id": parcel_id, "crop_type_id": crop_type_id})
    conn.commit()
    ok({"id": pp_id, "naming_series": naming, "plan_status": "planned"})


# ===========================================================================
# 4. update-planting-plan
# ===========================================================================
def update_planting_plan(conn, args):
    pp_id = getattr(args, "id", None)
    if not pp_id:
        err("--id is required")
    if not conn.execute(Q.from_(Table("agricultureclaw_planting_plan")).select(Field("id")).where(Field("id") == P()).get_sql(), (pp_id,)).fetchone():
        err(f"Planting plan {pp_id} not found")

    updates, params, changed = [], [], []
    for arg_name, col_name in {
        "season": "season", "planned_acres": "planned_acres",
        "seed_lot_id": "seed_lot_id", "planting_date": "planting_date",
        "expected_harvest_date": "expected_harvest_date",
    }.items():
        val = getattr(args, arg_name, None)
        if val is not None:
            updates.append(f"{col_name} = ?")
            params.append(val)
            changed.append(col_name)

    year_val = getattr(args, "year", None)
    if year_val is not None:
        updates.append("year = ?")
        params.append(int(year_val))
        changed.append("year")

    plan_status = getattr(args, "plan_status", None)
    if plan_status is not None:
        if plan_status not in VALID_PLAN_STATUS:
            err(f"Invalid plan-status: {plan_status}. Must be one of: {', '.join(VALID_PLAN_STATUS)}")
        updates.append("plan_status = ?")
        params.append(plan_status)
        changed.append("plan_status")

    if not updates:
        err("No fields to update")

    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(pp_id)
    conn.execute(f"UPDATE agricultureclaw_planting_plan SET {', '.join(updates)} WHERE id = ?", params)
    audit(conn, SKILL, "agri-update-planting-plan", "agricultureclaw_planting_plan", pp_id,
          new_values={"updated_fields": changed})
    conn.commit()
    ok({"id": pp_id, "updated_fields": changed})


# ===========================================================================
# 5. get-planting-plan
# ===========================================================================
def get_planting_plan(conn, args):
    pp_id = getattr(args, "id", None)
    if not pp_id:
        err("--id is required")
    row = conn.execute(Q.from_(Table("agricultureclaw_planting_plan")).select(Table("agricultureclaw_planting_plan").star).where(Field("id") == P()).get_sql(), (pp_id,)).fetchone()
    if not row:
        err(f"Planting plan {pp_id} not found")
    data = row_to_dict(row)

    # Include growth stages
    stages = conn.execute(Q.from_(Table("agricultureclaw_growth_stage")).select(Table("agricultureclaw_growth_stage").star).where(Field("planting_plan_id") == P()).orderby(Field("observed_date"), order=Order.asc).get_sql(), (pp_id,)).fetchall()
    data["growth_stages"] = [row_to_dict(s) for s in stages]
    data["stage_count"] = len(stages)
    ok(data)


# ===========================================================================
# 6. list-planting-plans
# ===========================================================================
def list_planting_plans(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "parcel_id", None):
        where.append("parcel_id = ?")
        params.append(args.parcel_id)
    if getattr(args, "plan_status", None):
        where.append("plan_status = ?")
        params.append(args.plan_status)
    if getattr(args, "season", None):
        where.append("season = ?")
        params.append(args.season)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_planting_plan WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_planting_plan WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 7. add-growth-stage
# ===========================================================================
def add_growth_stage(conn, args):
    _validate_company(conn, args.company_id)
    plan_id = getattr(args, "planting_plan_id", None)
    if not plan_id:
        err("--planting-plan-id is required")
    if not conn.execute(Q.from_(Table("agricultureclaw_planting_plan")).select(Field("id")).where(Field("id") == P()).get_sql(), (plan_id,)).fetchone():
        err(f"Planting plan {plan_id} not found")

    stage_name = getattr(args, "stage_name", None)
    if not stage_name:
        err("--stage-name is required")

    gs_id = str(uuid.uuid4())
    sql, _ = insert_row("agricultureclaw_growth_stage", {"id": P(), "planting_plan_id": P(), "stage_name": P(), "observed_date": P(), "notes": P(), "company_id": P()})
    conn.execute(sql, (
        gs_id, plan_id, stage_name,
        getattr(args, "observed_date", None),
        getattr(args, "notes", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-growth-stage", "agricultureclaw_growth_stage", gs_id,
          new_values={"planting_plan_id": plan_id, "stage_name": stage_name})
    conn.commit()
    ok({"id": gs_id, "planting_plan_id": plan_id, "stage_name": stage_name})


# ===========================================================================
# 8. list-growth-stages
# ===========================================================================
def list_growth_stages(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "planting_plan_id", None):
        where.append("planting_plan_id = ?")
        params.append(args.planting_plan_id)
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_growth_stage WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_growth_stage WHERE {where_sql} ORDER BY observed_date ASC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 9. advance-growth-stage
# ===========================================================================
def advance_growth_stage(conn, args):
    """Advance planting plan status to 'active' when growth stages are recorded."""
    pp_id = getattr(args, "id", None)
    if not pp_id:
        err("--id is required")
    row = conn.execute(Q.from_(Table("agricultureclaw_planting_plan")).select(Table("agricultureclaw_planting_plan").star).where(Field("id") == P()).get_sql(), (pp_id,)).fetchone()
    if not row:
        err(f"Planting plan {pp_id} not found")
    data = row_to_dict(row)

    if data["plan_status"] == "harvested":
        err("Plan is already harvested")
    if data["plan_status"] == "abandoned":
        err("Plan is abandoned")

    stage_count = conn.execute(Q.from_(Table("agricultureclaw_growth_stage")).select(fn.Count("*")).where(Field("planting_plan_id") == P()).get_sql(), (pp_id,)).fetchone()[0]

    if stage_count == 0:
        err("No growth stages recorded. Add at least one growth stage first.")

    new_status = "active"
    conn.execute(
        "UPDATE agricultureclaw_planting_plan SET plan_status = ?, updated_at = ? WHERE id = ?",
        (new_status, _now_iso(), pp_id)
    )
    audit(conn, SKILL, "agri-advance-growth-stage", "agricultureclaw_planting_plan", pp_id,
          new_values={"plan_status": new_status, "stage_count": stage_count})
    conn.commit()
    ok({"id": pp_id, "plan_status": new_status, "stage_count": stage_count})


# ===========================================================================
# 10. add-seed-lot
# ===========================================================================
def add_seed_lot(conn, args):
    _validate_company(conn, args.company_id)
    crop_type_id = getattr(args, "crop_type_id", None)
    _validate_crop_type(conn, crop_type_id)

    sl_id = str(uuid.uuid4())
    sql, _ = insert_row("agricultureclaw_seed_lot", {"id": P(), "crop_type_id": P(), "lot_number": P(), "quantity": P(), "unit": P(), "supplier": P(), "purchase_date": P(), "expiry_date": P(), "company_id": P()})
    conn.execute(sql, (
        sl_id, crop_type_id,
        getattr(args, "lot_number", None),
        getattr(args, "quantity", None),
        getattr(args, "unit", None),
        getattr(args, "supplier", None),
        getattr(args, "purchase_date", None),
        getattr(args, "expiry_date", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-seed-lot", "agricultureclaw_seed_lot", sl_id,
          new_values={"crop_type_id": crop_type_id})
    conn.commit()
    ok({"id": sl_id, "crop_type_id": crop_type_id})


# ===========================================================================
# 11. list-seed-lots
# ===========================================================================
def list_seed_lots(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "crop_type_id", None):
        where.append("crop_type_id = ?")
        params.append(args.crop_type_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_seed_lot WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_seed_lot WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 12. crop-rotation-report
# ===========================================================================
def crop_rotation_report(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("lr.company_id = ?")
        params.append(args.company_id)
    if getattr(args, "parcel_id", None):
        where.append("lr.parcel_id = ?")
        params.append(args.parcel_id)

    where_sql = " AND ".join(where)
    rows = conn.execute(f"""
        SELECT lr.parcel_id, p.name as parcel_name, lr.year, lr.season, lr.crop_type
        FROM agricultureclaw_land_use_record lr
        JOIN agricultureclaw_parcel p ON lr.parcel_id = p.id
        WHERE {where_sql}
        ORDER BY lr.parcel_id, lr.year DESC, lr.season
    """, params).fetchall()

    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": len(rows),
    })


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------
ACTIONS = {
    "agri-add-crop-type": add_crop_type,
    "agri-list-crop-types": list_crop_types,
    "agri-add-planting-plan": add_planting_plan,
    "agri-update-planting-plan": update_planting_plan,
    "agri-get-planting-plan": get_planting_plan,
    "agri-list-planting-plans": list_planting_plans,
    "agri-add-growth-stage": add_growth_stage,
    "agri-list-growth-stages": list_growth_stages,
    "agri-advance-growth-stage": advance_growth_stage,
    "agri-add-seed-lot": add_seed_lot,
    "agri-list-seed-lots": list_seed_lots,
    "agri-crop-rotation-report": crop_rotation_report,
}

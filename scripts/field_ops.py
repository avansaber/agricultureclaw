"""AgricultureClaw -- Field operations domain module.

Actions for field operations, scouting reports, irrigation logs, and chemical
applications (4 tables, 12 actions).
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

    ENTITY_PREFIXES.setdefault("field_operation", "FOP-")
except ImportError:
    pass

SKILL = "agricultureclaw"

_now_iso = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_OPERATION_TYPES = ("planting", "spraying", "irrigation", "fertilization", "tillage", "other")
VALID_OP_STATUS = ("planned", "in_progress", "completed", "cancelled")
VALID_WEED_PRESSURE = ("none", "low", "moderate", "high")
VALID_CROP_HEALTH = ("excellent", "good", "fair", "poor")
VALID_IRRIGATION_METHODS = ("pivot", "drip", "flood", "sprinkler")
VALID_CHEM_TARGETS = ("pest", "weed", "disease", "nutrient")


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
# 1. add-field-operation
# ===========================================================================
def add_field_operation(conn, args):
    _validate_company(conn, args.company_id)
    parcel_id = getattr(args, "parcel_id", None)
    _validate_parcel(conn, parcel_id)

    operation_type = getattr(args, "operation_type", None)
    if not operation_type:
        err("--operation-type is required")
    if operation_type not in VALID_OPERATION_TYPES:
        err(f"Invalid operation-type: {operation_type}. Must be one of: {', '.join(VALID_OPERATION_TYPES)}")

    fo_id = str(uuid.uuid4())
    conn.company_id = args.company_id
    naming = get_next_name(conn, "field_operation", company_id=args.company_id)
    now = _now_iso()

    conn.execute("""
        INSERT INTO agricultureclaw_field_operation (
            id, naming_series, parcel_id, operation_type, planned_date, completed_date,
            operator, equipment, cost, notes, op_status, company_id,
            created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        fo_id, naming, parcel_id, operation_type,
        getattr(args, "planned_date", None),
        getattr(args, "completed_date", None),
        getattr(args, "operator", None),
        getattr(args, "equipment", None),
        getattr(args, "cost", None),
        getattr(args, "notes", None),
        "planned",
        args.company_id, now, now,
    ))
    audit(conn, SKILL, "agri-add-field-operation", "agricultureclaw_field_operation", fo_id,
          new_values={"parcel_id": parcel_id, "operation_type": operation_type})
    conn.commit()
    ok({"id": fo_id, "naming_series": naming, "operation_type": operation_type, "op_status": "planned"})


# ===========================================================================
# 2. update-field-operation
# ===========================================================================
def update_field_operation(conn, args):
    fo_id = getattr(args, "id", None)
    if not fo_id:
        err("--id is required")
    if not conn.execute("SELECT id FROM agricultureclaw_field_operation WHERE id = ?", (fo_id,)).fetchone():
        err(f"Field operation {fo_id} not found")

    updates, params, changed = [], [], []
    for arg_name, col_name in {
        "planned_date": "planned_date", "completed_date": "completed_date",
        "operator": "operator", "equipment": "equipment", "cost": "cost", "notes": "notes",
    }.items():
        val = getattr(args, arg_name, None)
        if val is not None:
            updates.append(f"{col_name} = ?")
            params.append(val)
            changed.append(col_name)

    op_status = getattr(args, "op_status", None)
    if op_status is not None:
        if op_status not in VALID_OP_STATUS:
            err(f"Invalid op-status: {op_status}. Must be one of: {', '.join(VALID_OP_STATUS)}")
        updates.append("op_status = ?")
        params.append(op_status)
        changed.append("op_status")

    if not updates:
        err("No fields to update")

    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(fo_id)
    conn.execute(f"UPDATE agricultureclaw_field_operation SET {', '.join(updates)} WHERE id = ?", params)
    audit(conn, SKILL, "agri-update-field-operation", "agricultureclaw_field_operation", fo_id,
          new_values={"updated_fields": changed})
    conn.commit()
    ok({"id": fo_id, "updated_fields": changed})


# ===========================================================================
# 3. get-field-operation
# ===========================================================================
def get_field_operation(conn, args):
    fo_id = getattr(args, "id", None)
    if not fo_id:
        err("--id is required")
    row = conn.execute("SELECT * FROM agricultureclaw_field_operation WHERE id = ?", (fo_id,)).fetchone()
    if not row:
        err(f"Field operation {fo_id} not found")
    ok(row_to_dict(row))


# ===========================================================================
# 4. list-field-operations
# ===========================================================================
def list_field_operations(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "parcel_id", None):
        where.append("parcel_id = ?")
        params.append(args.parcel_id)
    if getattr(args, "operation_type", None):
        where.append("operation_type = ?")
        params.append(args.operation_type)
    if getattr(args, "op_status", None):
        where.append("op_status = ?")
        params.append(args.op_status)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_field_operation WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_field_operation WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 5. complete-field-operation
# ===========================================================================
def complete_field_operation(conn, args):
    fo_id = getattr(args, "id", None)
    if not fo_id:
        err("--id is required")
    row = conn.execute("SELECT * FROM agricultureclaw_field_operation WHERE id = ?", (fo_id,)).fetchone()
    if not row:
        err(f"Field operation {fo_id} not found")

    data = row_to_dict(row)
    if data["op_status"] == "completed":
        err("Operation is already completed")
    if data["op_status"] == "cancelled":
        err("Cannot complete a cancelled operation")

    now = _now_iso()
    completed_date = getattr(args, "completed_date", None) or now[:10]
    conn.execute(
        "UPDATE agricultureclaw_field_operation SET op_status = 'completed', completed_date = ?, updated_at = ? WHERE id = ?",
        (completed_date, now, fo_id)
    )
    audit(conn, SKILL, "agri-complete-field-operation", "agricultureclaw_field_operation", fo_id,
          new_values={"op_status": "completed", "completed_date": completed_date})
    conn.commit()
    ok({"id": fo_id, "op_status": "completed", "completed_date": completed_date})


# ===========================================================================
# 6. add-scouting-report
# ===========================================================================
def add_scouting_report(conn, args):
    _validate_company(conn, args.company_id)
    parcel_id = getattr(args, "parcel_id", None)
    _validate_parcel(conn, parcel_id)

    weed_pressure = getattr(args, "weed_pressure", None)
    if weed_pressure and weed_pressure not in VALID_WEED_PRESSURE:
        err(f"Invalid weed-pressure: {weed_pressure}. Must be one of: {', '.join(VALID_WEED_PRESSURE)}")

    crop_health = getattr(args, "crop_health", None)
    if crop_health and crop_health not in VALID_CROP_HEALTH:
        err(f"Invalid crop-health: {crop_health}. Must be one of: {', '.join(VALID_CROP_HEALTH)}")

    sr_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO agricultureclaw_scouting_report (
            id, parcel_id, scout_date, pest_found, disease_found,
            weed_pressure, crop_health, notes, photos, company_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        sr_id, parcel_id,
        getattr(args, "scout_date", None),
        getattr(args, "pest_found", None),
        getattr(args, "disease_found", None),
        weed_pressure,
        crop_health,
        getattr(args, "notes", None),
        getattr(args, "photos", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-scouting-report", "agricultureclaw_scouting_report", sr_id,
          new_values={"parcel_id": parcel_id})
    conn.commit()
    ok({"id": sr_id, "parcel_id": parcel_id})


# ===========================================================================
# 7. list-scouting-reports
# ===========================================================================
def list_scouting_reports(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "parcel_id", None):
        where.append("parcel_id = ?")
        params.append(args.parcel_id)
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_scouting_report WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_scouting_report WHERE {where_sql} ORDER BY scout_date DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 8. add-irrigation-log
# ===========================================================================
def add_irrigation_log(conn, args):
    _validate_company(conn, args.company_id)
    parcel_id = getattr(args, "parcel_id", None)
    _validate_parcel(conn, parcel_id)

    method = getattr(args, "method", None)
    if method and method not in VALID_IRRIGATION_METHODS:
        err(f"Invalid method: {method}. Must be one of: {', '.join(VALID_IRRIGATION_METHODS)}")

    il_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO agricultureclaw_irrigation_log (
            id, parcel_id, irrigation_date, method, gallons, duration_hours, company_id
        ) VALUES (?,?,?,?,?,?,?)
    """, (
        il_id, parcel_id,
        getattr(args, "irrigation_date", None),
        method,
        getattr(args, "gallons", None),
        getattr(args, "duration_hours", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-irrigation-log", "agricultureclaw_irrigation_log", il_id,
          new_values={"parcel_id": parcel_id})
    conn.commit()
    ok({"id": il_id, "parcel_id": parcel_id})


# ===========================================================================
# 9. list-irrigation-logs
# ===========================================================================
def list_irrigation_logs(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "parcel_id", None):
        where.append("parcel_id = ?")
        params.append(args.parcel_id)
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_irrigation_log WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_irrigation_log WHERE {where_sql} ORDER BY irrigation_date DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 10. add-chemical-application
# ===========================================================================
def add_chemical_application(conn, args):
    _validate_company(conn, args.company_id)
    parcel_id = getattr(args, "parcel_id", None)
    _validate_parcel(conn, parcel_id)

    target = getattr(args, "target", None)
    if target and target not in VALID_CHEM_TARGETS:
        err(f"Invalid target: {target}. Must be one of: {', '.join(VALID_CHEM_TARGETS)}")

    ca_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO agricultureclaw_chemical_application (
            id, parcel_id, application_date, chemical_name, epa_reg_number,
            rate, unit, target, applicator, wind_speed, temperature, company_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        ca_id, parcel_id,
        getattr(args, "application_date", None),
        getattr(args, "chemical_name", None),
        getattr(args, "epa_reg_number", None),
        getattr(args, "rate", None),
        getattr(args, "unit", None),
        target,
        getattr(args, "applicator", None),
        getattr(args, "wind_speed", None),
        getattr(args, "temperature", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-chemical-application", "agricultureclaw_chemical_application", ca_id,
          new_values={"parcel_id": parcel_id, "chemical_name": getattr(args, "chemical_name", None)})
    conn.commit()
    ok({"id": ca_id, "parcel_id": parcel_id})


# ===========================================================================
# 11. list-chemical-applications
# ===========================================================================
def list_chemical_applications(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "parcel_id", None):
        where.append("parcel_id = ?")
        params.append(args.parcel_id)
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_chemical_application WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_chemical_application WHERE {where_sql} ORDER BY application_date DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 12. field-activity-report
# ===========================================================================
def field_activity_report(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "parcel_id", None):
        where.append("parcel_id = ?")
        params.append(args.parcel_id)

    where_sql = " AND ".join(where)

    # Operations by type and status
    ops = conn.execute(f"""
        SELECT operation_type, op_status, COUNT(*) as cnt
        FROM agricultureclaw_field_operation WHERE {where_sql}
        GROUP BY operation_type, op_status
    """, params).fetchall()

    total_ops = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_field_operation WHERE {where_sql}", params
    ).fetchone()[0]

    total_scouts = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_scouting_report WHERE {where_sql}", params
    ).fetchone()[0]

    total_irrigations = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_irrigation_log WHERE {where_sql}", params
    ).fetchone()[0]

    total_applications = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_chemical_application WHERE {where_sql}", params
    ).fetchone()[0]

    ok({
        "total_operations": total_ops,
        "total_scouting_reports": total_scouts,
        "total_irrigations": total_irrigations,
        "total_chemical_applications": total_applications,
        "operations_by_type_status": [row_to_dict(r) for r in ops],
    })


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------
ACTIONS = {
    "agri-add-field-operation": add_field_operation,
    "agri-update-field-operation": update_field_operation,
    "agri-get-field-operation": get_field_operation,
    "agri-list-field-operations": list_field_operations,
    "agri-complete-field-operation": complete_field_operation,
    "agri-add-scouting-report": add_scouting_report,
    "agri-list-scouting-reports": list_scouting_reports,
    "agri-add-irrigation-log": add_irrigation_log,
    "agri-list-irrigation-logs": list_irrigation_logs,
    "agri-add-chemical-application": add_chemical_application,
    "agri-list-chemical-applications": list_chemical_applications,
    "agri-field-activity-report": field_activity_report,
}

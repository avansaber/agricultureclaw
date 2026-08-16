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
    import importlib.util
    if importlib.util.find_spec("erpclaw_lib") is None:
        sys.path.insert(0, os.path.join(os.path.expanduser(os.environ.get("ERPCLAW_HOME", "~/.openclaw/erpclaw")), "lib"))
    from erpclaw_lib.naming import get_next_name, ENTITY_PREFIXES
    from erpclaw_lib.response import ok, err, row_to_dict
    from erpclaw_lib.audit import audit
    from erpclaw_lib.query import Q, P, Table, Field, fn, Order, LiteralValue, insert_row, update_row, dynamic_update

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
    if not conn.execute(Q.from_(Table("company")).select(Field("id")).where(Field("id") == P()).get_sql(), (company_id,)).fetchone():
        err(f"Company {company_id} not found")


def _validate_parcel(conn, parcel_id):
    if not parcel_id:
        err("--parcel-id is required")
    if not conn.execute(Q.from_(Table("agricultureclaw_parcel")).select(Field("id")).where(Field("id") == P()).get_sql(), (parcel_id,)).fetchone():
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

    sql, _ = insert_row("agricultureclaw_parcel", {"id": P(), "naming_series": P(), "name": P(), "acreage": P(), "gps_lat": P(), "gps_lon": P(), "soil_type": P(), "land_use": P(), "owner": P(), "lease_info": P(), "parcel_status": P(), "company_id": P(), "created_at": P(), "updated_at": P()})
    conn.execute(sql, (
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
    if not conn.execute(Q.from_(Table("agricultureclaw_parcel")).select(Field("id")).where(Field("id") == P()).get_sql(), (parcel_id,)).fetchone():
        err(f"Parcel {parcel_id} not found")

    data, changed = {}, []
    for arg_name, col_name in {
        "name": "name", "acreage": "acreage", "gps_lat": "gps_lat", "gps_lon": "gps_lon",
        "soil_type": "soil_type", "owner": "owner", "lease_info": "lease_info",
    }.items():
        val = getattr(args, arg_name, None)
        if val is not None:
            data[col_name] = val
            changed.append(col_name)

    land_use = getattr(args, "land_use", None)
    if land_use is not None:
        if land_use not in VALID_LAND_USE:
            err(f"Invalid land-use: {land_use}. Must be one of: {', '.join(VALID_LAND_USE)}")
        data["land_use"] = land_use
        changed.append("land_use")

    parcel_status = getattr(args, "parcel_status", None)
    if parcel_status is not None:
        if parcel_status not in VALID_PARCEL_STATUS:
            err(f"Invalid parcel-status: {parcel_status}. Must be one of: {', '.join(VALID_PARCEL_STATUS)}")
        data["parcel_status"] = parcel_status
        changed.append("parcel_status")

    if not data:
        err("No fields to update")

    data["updated_at"] = _now_iso()
    sql, params = dynamic_update("agricultureclaw_parcel", data, where={"id": parcel_id})
    conn.execute(sql, params)
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
    row = conn.execute(Q.from_(Table("agricultureclaw_parcel")).select(Table("agricultureclaw_parcel").star).where(Field("id") == P()).get_sql(), (parcel_id,)).fetchone()
    if not row:
        err(f"Parcel {parcel_id} not found")
    data = row_to_dict(row)

    # Include soil tests
    soil_tests = conn.execute(Q.from_(Table("agricultureclaw_soil_test")).select(Table("agricultureclaw_soil_test").star).where(Field("parcel_id") == P()).orderby(Field("test_date"), order=Order.desc).get_sql(), (parcel_id,)).fetchall()
    data["soil_tests"] = [row_to_dict(s) for s in soil_tests]

    # Include land use records
    land_use_recs = conn.execute(Q.from_(Table("agricultureclaw_land_use_record")).select(Table("agricultureclaw_land_use_record").star).where(Field("parcel_id") == P()).orderby(Field("year"), order=Order.desc).get_sql(), (parcel_id,)).fetchall()
    data["land_use_records"] = [row_to_dict(r) for r in land_use_recs]
    ok(data)


# ===========================================================================
# 4. list-parcels
# ===========================================================================
def list_parcels(conn, args):
    t = Table("agricultureclaw_parcel")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)
    if getattr(args, "parcel_status", None):
        q = q.where(t.parcel_status == P())
        qc = qc.where(t.parcel_status == P())
        params.append(args.parcel_status)
    if getattr(args, "search", None):
        q = q.where(t.name.like(P()))
        qc = qc.where(t.name.like(P()))
        params.append(f"%{args.search}%")

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.created_at, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
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
    sql, _ = insert_row("agricultureclaw_soil_test", {"id": P(), "parcel_id": P(), "test_date": P(), "ph": P(), "nitrogen": P(), "phosphorus": P(), "potassium": P(), "organic_matter": P(), "lab_name": P(), "notes": P(), "company_id": P()})
    conn.execute(sql, (
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
    t = Table("agricultureclaw_soil_test")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "parcel_id", None):
        q = q.where(t.parcel_id == P())
        qc = qc.where(t.parcel_id == P())
        params.append(args.parcel_id)
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.test_date, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
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
    sql, _ = insert_row("agricultureclaw_land_use_record", {"id": P(), "parcel_id": P(), "season": P(), "year": P(), "crop_type": P(), "notes": P(), "company_id": P()})
    conn.execute(sql, (
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
    t = Table("agricultureclaw_land_use_record")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "parcel_id", None):
        q = q.where(t.parcel_id == P())
        qc = qc.where(t.parcel_id == P())
        params.append(args.parcel_id)
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.year, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
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
    row = conn.execute(Q.from_(Table("agricultureclaw_parcel")).select(Table("agricultureclaw_parcel").star).where(Field("id") == P()).get_sql(), (parcel_id,)).fetchone()
    if not row:
        err(f"Parcel {parcel_id} not found")
    data = row_to_dict(row)

    soil_count = conn.execute(Q.from_(Table("agricultureclaw_soil_test")).select(fn.Count("*")).where(Field("parcel_id") == P()).get_sql(), (parcel_id,)).fetchone()[0]
    lur_count = conn.execute(Q.from_(Table("agricultureclaw_land_use_record")).select(fn.Count("*")).where(Field("parcel_id") == P()).get_sql(), (parcel_id,)).fetchone()[0]
    op_count = conn.execute(Q.from_(Table("agricultureclaw_field_operation")).select(fn.Count("*")).where(Field("parcel_id") == P()).get_sql(), (parcel_id,)).fetchone()[0]
    harvest_count = conn.execute(Q.from_(Table("agricultureclaw_harvest_record")).select(fn.Count("*")).where(Field("parcel_id") == P()).get_sql(), (parcel_id,)).fetchone()[0]

    data["soil_test_count"] = soil_count
    data["land_use_record_count"] = lur_count
    data["field_operation_count"] = op_count
    data["harvest_record_count"] = harvest_count
    ok(data)


# ===========================================================================
# 10. land-utilization-report
# ===========================================================================
def land_utilization_report(conn, args):
    t = Table("agricultureclaw_parcel")
    base_q = Q.from_(t)
    params = []
    if getattr(args, "company_id", None):
        base_q = base_q.where(t.company_id == P())
        params.append(args.company_id)

    rows = conn.execute(
        base_q.select(t.land_use, t.parcel_status, fn.Count("*").as_("cnt")).groupby(t.land_use, t.parcel_status).get_sql(),
        params
    ).fetchall()

    total_parcels = conn.execute(
        Q.from_(t).select(fn.Count("*")).where(t.company_id == P()).get_sql() if params else Q.from_(t).select(fn.Count("*")).get_sql(),
        params
    ).fetchone()[0]

    # Sum acreage by land_use
    acreage_rows = conn.execute(
        base_q.select(t.land_use, t.acreage).get_sql(),
        params
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

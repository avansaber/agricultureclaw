"""AgricultureClaw -- Harvest management domain module.

Actions for harvest records, storage bins, quality grades, and reports (3 tables, 12 actions).
Imported by db_query.py (unified router).
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

try:
    sys.path.insert(0, os.path.expanduser("~/.openclaw/erpclaw/lib"))
    from erpclaw_lib.naming import get_next_name, ENTITY_PREFIXES
    from erpclaw_lib.response import ok, err, row_to_dict
    from erpclaw_lib.audit import audit
    from erpclaw_lib.decimal_utils import to_decimal, round_currency
    from erpclaw_lib.query import Q, P, Table, Field, fn, Order, LiteralValue, insert_row, update_row, dynamic_update

    ENTITY_PREFIXES.setdefault("harvest_record", "HRV-")
except ImportError:
    pass

try:
    from erpclaw_lib.gl_posting import insert_gl_entries, reverse_gl_entries
    HAS_GL = True
except ImportError:
    HAS_GL = False

SKILL = "agricultureclaw"

_now_iso = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_BIN_TYPES = ("silo", "bin", "warehouse", "other")
VALID_GRADES = ("1", "2", "3", "sample_grade")


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
# 1. add-harvest-record
# ===========================================================================
def add_harvest_record(conn, args):
    _validate_company(conn, args.company_id)
    parcel_id = getattr(args, "parcel_id", None)
    _validate_parcel(conn, parcel_id)

    planting_plan_id = getattr(args, "planting_plan_id", None)
    if planting_plan_id:
        if not conn.execute(Q.from_(Table("agricultureclaw_planting_plan")).select(Field("id")).where(Field("id") == P()).get_sql(), (planting_plan_id,)).fetchone():
            err(f"Planting plan {planting_plan_id} not found")

    storage_bin_id = getattr(args, "storage_bin_id", None)
    if storage_bin_id:
        if not conn.execute(Q.from_(Table("agricultureclaw_storage_bin")).select(Field("id")).where(Field("id") == P()).get_sql(), (storage_bin_id,)).fetchone():
            err(f"Storage bin {storage_bin_id} not found")

    hr_id = str(uuid.uuid4())
    conn.company_id = args.company_id
    naming = get_next_name(conn, "harvest_record", company_id=args.company_id)
    now = _now_iso()

    sql, _ = insert_row("agricultureclaw_harvest_record", {"id": P(), "naming_series": P(), "planting_plan_id": P(), "parcel_id": P(), "harvest_date": P(), "yield_amount": P(), "yield_unit": P(), "moisture_content": P(), "quality_grade": P(), "storage_bin_id": P(), "market_price": P(), "revenue": P(), "sale_status": P(), "revenue_account_id": P(), "receivable_account_id": P(), "cost_center_id": P(), "company_id": P(), "created_at": P(), "updated_at": P()})
    conn.execute(sql, (
        hr_id, naming, planting_plan_id, parcel_id,
        getattr(args, "harvest_date", None),
        getattr(args, "yield_amount", None),
        getattr(args, "yield_unit", None),
        getattr(args, "moisture_content", None),
        getattr(args, "quality_grade", None),
        storage_bin_id,
        getattr(args, "market_price", None),
        getattr(args, "revenue", None),
        "draft",
        getattr(args, "revenue_account_id", None),
        getattr(args, "receivable_account_id", None),
        getattr(args, "cost_center_id", None),
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
    if not conn.execute(Q.from_(Table("agricultureclaw_harvest_record")).select(Field("id")).where(Field("id") == P()).get_sql(), (hr_id,)).fetchone():
        err(f"Harvest record {hr_id} not found")

    data, changed = {}, []
    for arg_name, col_name in {
        "harvest_date": "harvest_date", "yield_amount": "yield_amount",
        "yield_unit": "yield_unit", "moisture_content": "moisture_content",
        "quality_grade": "quality_grade", "market_price": "market_price",
        "revenue": "revenue",
    }.items():
        val = getattr(args, arg_name, None)
        if val is not None:
            data[col_name] = val
            changed.append(col_name)

    if not data:
        err("No fields to update")

    data["updated_at"] = _now_iso()
    sql, params = dynamic_update("agricultureclaw_harvest_record", data, where={"id": hr_id})
    conn.execute(sql, params)
    audit(conn, SKILL, "agri-update-harvest-record", "agricultureclaw_harvest_record", hr_id,
          new_values={"updated_fields": changed})
    conn.commit()
    ok({"id": hr_id, "updated_fields": changed})


# ===========================================================================
# 3. list-harvest-records
# ===========================================================================
def list_harvest_records(conn, args):
    t = Table("agricultureclaw_harvest_record")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)
    if getattr(args, "parcel_id", None):
        q = q.where(t.parcel_id == P())
        qc = qc.where(t.parcel_id == P())
        params.append(args.parcel_id)
    if getattr(args, "planting_plan_id", None):
        q = q.where(t.planting_plan_id == P())
        qc = qc.where(t.planting_plan_id == P())
        params.append(args.planting_plan_id)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.harvest_date, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
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
    sql, _ = insert_row("agricultureclaw_storage_bin", {"id": P(), "name": P(), "bin_type": P(), "capacity": P(), "current_quantity": P(), "crop_type": P(), "location": P(), "company_id": P(), "created_at": P(), "updated_at": P()})
    conn.execute(sql, (
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
    t = Table("agricultureclaw_storage_bin")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.name, order=Order.asc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
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
    if not conn.execute(Q.from_(Table("agricultureclaw_harvest_record")).select(Field("id")).where(Field("id") == P()).get_sql(), (harvest_id,)).fetchone():
        err(f"Harvest record {harvest_id} not found")

    grade = getattr(args, "grade", None)
    if grade and grade not in VALID_GRADES:
        err(f"Invalid grade: {grade}. Must be one of: {', '.join(VALID_GRADES)}")

    qg_id = str(uuid.uuid4())
    sql, _ = insert_row("agricultureclaw_quality_grade", {"id": P(), "harvest_id": P(), "grade": P(), "test_weight": P(), "foreign_material": P(), "damage_pct": P(), "notes": P(), "company_id": P()})
    conn.execute(sql, (
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
    t = Table("agricultureclaw_quality_grade")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "harvest_id", None):
        q = q.where(t.harvest_id == P())
        qc = qc.where(t.harvest_id == P())
        params.append(args.harvest_id)
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.created_at, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
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
    t = Table("agricultureclaw_harvest_record")
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "company_id", None):
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]

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


# ===========================================================================
# 11. submit-harvest-sale  (GL posting for direct harvest sale)
# ===========================================================================
def submit_harvest_sale(conn, args):
    """Submit a harvest record as a sale: validate revenue, post GL entries.

    GL pattern:
      DR Receivable (or Cash)    for revenue amount
      CR Agricultural Revenue    for revenue amount

    GL is OPTIONAL -- if accounts not configured, record is still
    submitted without GL entries.
    """
    hr_id = getattr(args, "id", None)
    if not hr_id:
        err("--id is required")

    record = conn.execute(Q.from_(Table("agricultureclaw_harvest_record")).select(Table("agricultureclaw_harvest_record").star).where(Field("id") == P()).get_sql(), (hr_id,)).fetchone()
    if not record:
        err(f"Harvest record {hr_id} not found")

    if record["sale_status"] != "draft":
        err(f"Harvest record {hr_id} is already '{record['sale_status']}' -- only draft records can be submitted")

    revenue_val = record["revenue"]
    if not revenue_val or to_decimal(revenue_val) <= Decimal("0"):
        err("Cannot submit: revenue must be > 0. Set revenue or market_price * yield_amount first.")

    amount = to_decimal(revenue_val)
    posting_date = record["harvest_date"] or _now_iso()[:10]
    company_id = record["company_id"]

    # Allow override from args
    revenue_account_id = getattr(args, "revenue_account_id", None) or record["revenue_account_id"]
    receivable_account_id = getattr(args, "receivable_account_id", None) or record["receivable_account_id"]
    cost_center_id = getattr(args, "cost_center_id", None) or record["cost_center_id"]

    # Persist any account overrides
    conn.execute("""
        UPDATE agricultureclaw_harvest_record
        SET revenue_account_id = ?, receivable_account_id = ?, cost_center_id = ?,
            updated_at = ?
        WHERE id = ?
    """, (revenue_account_id, receivable_account_id, cost_center_id, _now_iso(), hr_id))

    all_gl_ids = []

    if HAS_GL and revenue_account_id and receivable_account_id:
        try:
            entries = [
                {
                    "account_id": receivable_account_id,
                    "debit": str(round_currency(amount)),
                    "credit": "0",
                },
                {
                    "account_id": revenue_account_id,
                    "debit": "0",
                    "credit": str(round_currency(amount)),
                    "cost_center_id": cost_center_id,
                },
            ]
            gl_ids = insert_gl_entries(
                conn, entries,
                voucher_type="Harvest Sale",
                voucher_id=hr_id,
                posting_date=posting_date,
                company_id=company_id,
                remarks=f"Harvest sale {record['naming_series'] or hr_id}",
                entry_set="primary",
            )
            all_gl_ids.extend(gl_ids)
        except (ValueError, Exception) as e:
            sys.stderr.write(f"[{SKILL}] GL posting skipped for harvest sale: {e}\n")

    # Mark submitted
    gl_ids_str = ",".join(all_gl_ids) if all_gl_ids else None
    conn.execute("""
        UPDATE agricultureclaw_harvest_record
        SET sale_status = 'submitted', gl_entry_ids = ?, updated_at = ?
        WHERE id = ?
    """, (gl_ids_str, _now_iso(), hr_id))

    audit(conn, SKILL, "agri-submit-harvest-sale", "agricultureclaw_harvest_record", hr_id,
          new_values={"sale_status": "submitted", "gl_entry_count": len(all_gl_ids)})
    conn.commit()

    result = {
        "id": hr_id, "sale_status": "submitted",
        "revenue": str(amount), "posting_date": posting_date,
    }
    if all_gl_ids:
        result["gl_entry_ids"] = all_gl_ids
        result["gl_entry_count"] = len(all_gl_ids)
    else:
        result["gl_note"] = "No GL entries posted (accounts not configured or GL module unavailable)"
    ok(result)


# ===========================================================================
# 12. cancel-harvest-sale  (GL reversal)
# ===========================================================================
def cancel_harvest_sale(conn, args):
    """Cancel a submitted harvest sale -- reverses GL entries if any."""
    hr_id = getattr(args, "id", None)
    if not hr_id:
        err("--id is required")

    record = conn.execute(Q.from_(Table("agricultureclaw_harvest_record")).select(Table("agricultureclaw_harvest_record").star).where(Field("id") == P()).get_sql(), (hr_id,)).fetchone()
    if not record:
        err(f"Harvest record {hr_id} not found")

    if record["sale_status"] == "cancelled":
        err(f"Harvest record {hr_id} is already cancelled")
    if record["sale_status"] == "draft":
        err(f"Harvest record {hr_id} is still in draft -- no sale to cancel")

    posting_date = record["harvest_date"] or _now_iso()[:10]
    reversal_ids = []

    if HAS_GL and record["gl_entry_ids"]:
        try:
            rev_ids = reverse_gl_entries(
                conn, voucher_type="Harvest Sale",
                voucher_id=hr_id, posting_date=posting_date,
            )
            reversal_ids.extend(rev_ids)
        except (ValueError, Exception) as e:
            sys.stderr.write(f"[{SKILL}] GL reversal error for harvest sale: {e}\n")

    conn.execute("""
        UPDATE agricultureclaw_harvest_record
        SET sale_status = 'cancelled', updated_at = ?
        WHERE id = ?
    """, (_now_iso(), hr_id))

    audit(conn, SKILL, "agri-cancel-harvest-sale", "agricultureclaw_harvest_record", hr_id,
          new_values={"sale_status": "cancelled", "reversal_count": len(reversal_ids)})
    conn.commit()

    result = {"id": hr_id, "sale_status": "cancelled"}
    if reversal_ids:
        result["reversal_gl_entry_ids"] = reversal_ids
    ok(result)


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
    "agri-submit-harvest-sale": submit_harvest_sale,
    "agri-cancel-harvest-sale": cancel_harvest_sale,
    "agri-yield-analysis-report": yield_analysis_report,
    "agri-harvest-summary": harvest_summary,
    "agri-crop-profitability-report": crop_profitability_report,
}

"""AgricultureClaw -- Cooperative management domain module.

Actions for cooperative members, delivery tickets, and pool accounts (3 tables, 10 actions).
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

    ENTITY_PREFIXES.setdefault("coop_member", "COOP-")
    ENTITY_PREFIXES.setdefault("delivery_ticket", "DT-")
except ImportError:
    pass

try:
    from erpclaw_lib.gl_posting import insert_gl_entries, reverse_gl_entries
    HAS_GL = True
except ImportError:
    HAS_GL = False

SKILL = "agricultureclaw"

_now_iso = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_MEMBER_STATUS = ("active", "inactive", "suspended")
VALID_POOL_STATUS = ("open", "closed", "distributed")


def _validate_company(conn, company_id):
    if not company_id:
        err("--company-id is required")
    if not conn.execute(Q.from_(Table("company")).select(Field("id")).where(Field("id") == P()).get_sql(), (company_id,)).fetchone():
        err(f"Company {company_id} not found")


def _validate_member(conn, member_id):
    if not member_id:
        err("--member-id is required")
    if not conn.execute(Q.from_(Table("agricultureclaw_coop_member")).select(Field("id")).where(Field("id") == P()).get_sql(), (member_id,)).fetchone():
        err(f"Co-op member {member_id} not found")


# ===========================================================================
# 1. add-coop-member
# ===========================================================================
def add_coop_member(conn, args):
    _validate_company(conn, args.company_id)
    name = getattr(args, "name", None)
    if not name:
        err("--name is required")

    cm_id = str(uuid.uuid4())
    conn.company_id = args.company_id
    naming = get_next_name(conn, "coop_member", company_id=args.company_id)
    now = _now_iso()

    sql, _ = insert_row("agricultureclaw_coop_member", {"id": P(), "naming_series": P(), "name": P(), "member_number": P(), "shares": P(), "join_date": P(), "member_status": P(), "company_id": P(), "created_at": P(), "updated_at": P()})
    conn.execute(sql, (
        cm_id, naming, name,
        getattr(args, "member_number", None),
        getattr(args, "shares", None),
        getattr(args, "join_date", None),
        "active",
        args.company_id, now, now,
    ))
    audit(conn, SKILL, "agri-add-coop-member", "agricultureclaw_coop_member", cm_id,
          new_values={"name": name})
    conn.commit()
    ok({"id": cm_id, "naming_series": naming, "name": name, "member_status": "active"})


# ===========================================================================
# 2. list-coop-members
# ===========================================================================
def list_coop_members(conn, args):
    t = Table("agricultureclaw_coop_member")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)
    if getattr(args, "member_status", None):
        q = q.where(t.member_status == P())
        qc = qc.where(t.member_status == P())
        params.append(args.member_status)
    if getattr(args, "search", None):
        q = q.where((t.name.like(P())) | (t.member_number.like(P())))
        qc = qc.where((t.name.like(P())) | (t.member_number.like(P())))
        params.extend([f"%{args.search}%", f"%{args.search}%"])

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.name, order=Order.asc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 3. add-delivery-ticket
# ===========================================================================
def add_delivery_ticket(conn, args):
    _validate_company(conn, args.company_id)
    member_id = getattr(args, "member_id", None)
    _validate_member(conn, member_id)

    dt_id = str(uuid.uuid4())
    conn.company_id = args.company_id
    naming = get_next_name(conn, "delivery_ticket", company_id=args.company_id)

    # Calculate net weight if gross and tare provided
    gross = getattr(args, "gross_weight", None)
    tare = getattr(args, "tare_weight", None)
    net_weight = getattr(args, "net_weight", None)
    if gross and tare and not net_weight:
        net_weight = str(Decimal(gross) - Decimal(tare))

    # Calculate total amount if net_weight and price_per_unit provided
    price_per_unit = getattr(args, "price_per_unit", None)
    total_amount = getattr(args, "total_amount", None)
    if net_weight and price_per_unit and not total_amount:
        total_amount = str(Decimal(net_weight) * Decimal(price_per_unit))

    sql, _ = insert_row("agricultureclaw_delivery_ticket", {"id": P(), "naming_series": P(), "member_id": P(), "delivery_date": P(), "commodity": P(), "gross_weight": P(), "tare_weight": P(), "net_weight": P(), "moisture": P(), "grade": P(), "price_per_unit": P(), "total_amount": P(), "ticket_status": P(), "revenue_account_id": P(), "receivable_account_id": P(), "cogs_account_id": P(), "inventory_account_id": P(), "cost_center_id": P(), "company_id": P()})
    conn.execute(sql, (
        dt_id, naming, member_id,
        getattr(args, "delivery_date", None),
        getattr(args, "commodity", None),
        gross,
        tare,
        net_weight,
        getattr(args, "moisture", None),
        getattr(args, "grade", None),
        price_per_unit,
        total_amount,
        "draft",
        getattr(args, "revenue_account_id", None),
        getattr(args, "receivable_account_id", None),
        getattr(args, "cogs_account_id", None),
        getattr(args, "inventory_account_id", None),
        getattr(args, "cost_center_id", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-delivery-ticket", "agricultureclaw_delivery_ticket", dt_id,
          new_values={"member_id": member_id, "commodity": getattr(args, "commodity", None)})
    conn.commit()
    ok({
        "id": dt_id, "naming_series": naming, "member_id": member_id,
        "net_weight": net_weight, "total_amount": total_amount,
    })


# ===========================================================================
# 4. list-delivery-tickets
# ===========================================================================
def list_delivery_tickets(conn, args):
    t = Table("agricultureclaw_delivery_ticket")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)
    if getattr(args, "member_id", None):
        q = q.where(t.member_id == P())
        qc = qc.where(t.member_id == P())
        params.append(args.member_id)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.delivery_date, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 5. calculate-patronage
# ===========================================================================
def calculate_patronage(conn, args):
    _validate_company(conn, args.company_id)
    member_id = getattr(args, "member_id", None)
    _validate_member(conn, member_id)

    # Get all delivery tickets for this member
    dt = Table("agricultureclaw_delivery_ticket")
    tickets = conn.execute(
        Q.from_(dt).select(dt.star).where(dt.member_id == P()).where(dt.company_id == P()).get_sql(),
        (member_id, args.company_id)
    ).fetchall()

    total_delivered = Decimal("0")
    total_value = Decimal("0")
    for t in tickets:
        nw = t["net_weight"]
        if nw:
            total_delivered += Decimal(nw)
        ta = t["total_amount"]
        if ta:
            total_value += Decimal(ta)

    member = conn.execute(Q.from_(Table("agricultureclaw_coop_member")).select(Field("name")).where(Field("id") == P()).get_sql(), (member_id,)).fetchone()

    ok({
        "member_id": member_id,
        "member_name": member["name"] if member else None,
        "total_tickets": len(tickets),
        "total_delivered_weight": str(total_delivered),
        "total_value": str(total_value),
    })


# ===========================================================================
# 6. add-pool-account
# ===========================================================================
def add_pool_account(conn, args):
    _validate_company(conn, args.company_id)
    name = getattr(args, "name", None)
    if not name:
        err("--name is required")

    pool_status = getattr(args, "pool_status", None) or "open"
    if pool_status not in VALID_POOL_STATUS:
        err(f"Invalid pool-status: {pool_status}. Must be one of: {', '.join(VALID_POOL_STATUS)}")

    pa_id = str(uuid.uuid4())
    now = _now_iso()
    year_val = getattr(args, "pool_year", None)

    sql, _ = insert_row("agricultureclaw_pool_account", {"id": P(), "name": P(), "commodity": P(), "pool_year": P(), "total_quantity": P(), "total_value": P(), "members_count": P(), "pool_status": P(), "company_id": P(), "created_at": P(), "updated_at": P()})
    conn.execute(sql, (
        pa_id, name,
        getattr(args, "commodity", None),
        int(year_val) if year_val is not None else None,
        getattr(args, "total_quantity", None) or "0",
        getattr(args, "total_value", None) or "0",
        int(getattr(args, "members_count", None) or 0),
        pool_status,
        args.company_id, now, now,
    ))
    audit(conn, SKILL, "agri-add-pool-account", "agricultureclaw_pool_account", pa_id,
          new_values={"name": name})
    conn.commit()
    ok({"id": pa_id, "name": name, "pool_status": pool_status})


# ===========================================================================
# 7. list-pool-accounts
# ===========================================================================
def list_pool_accounts(conn, args):
    t = Table("agricultureclaw_pool_account")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)
    if getattr(args, "pool_status", None):
        q = q.where(t.pool_status == P())
        qc = qc.where(t.pool_status == P())
        params.append(args.pool_status)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.pool_year, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 8. cooperative-summary-report
# ===========================================================================
def cooperative_summary_report(conn, args):
    cm = Table("agricultureclaw_coop_member")
    dt_tbl = Table("agricultureclaw_delivery_ticket")
    pa = Table("agricultureclaw_pool_account")
    params = []

    q_cm = Q.from_(cm).select(fn.Count("*"))
    q_cm_active = Q.from_(cm).select(fn.Count("*")).where(cm.member_status == "active")
    q_dt = Q.from_(dt_tbl).select(fn.Count("*"))
    q_pa = Q.from_(pa).select(fn.Count("*"))

    if getattr(args, "company_id", None):
        q_cm = q_cm.where(cm.company_id == P())
        q_cm_active = q_cm_active.where(cm.company_id == P())
        q_dt = q_dt.where(dt_tbl.company_id == P())
        q_pa = q_pa.where(pa.company_id == P())
        params.append(args.company_id)

    total_members = conn.execute(q_cm.get_sql(), params).fetchone()[0]
    active_members = conn.execute(q_cm_active.get_sql(), params).fetchone()[0]
    total_tickets = conn.execute(q_dt.get_sql(), params).fetchone()[0]
    total_pools = conn.execute(q_pa.get_sql(), params).fetchone()[0]

    ok({
        "total_members": total_members,
        "active_members": active_members,
        "total_delivery_tickets": total_tickets,
        "total_pool_accounts": total_pools,
    })


# ===========================================================================
# 9. submit-delivery-ticket  (GL posting for commodity sale)
# ===========================================================================
def submit_delivery_ticket(conn, args):
    """Submit a delivery ticket: validate, post GL entries, mark submitted.

    GL pattern:
      Primary set:  DR Receivable, CR Agricultural Revenue
      COGS set:     DR Agricultural COGS, CR Inventory (optional, if both accounts given)

    GL is OPTIONAL -- if accounts not configured, ticket is still submitted
    without GL entries.
    """
    dt_id = getattr(args, "id", None)
    if not dt_id:
        err("--id is required")

    ticket = conn.execute(Q.from_(Table("agricultureclaw_delivery_ticket")).select(Table("agricultureclaw_delivery_ticket").star).where(Field("id") == P()).get_sql(), (dt_id,)).fetchone()
    if not ticket:
        err(f"Delivery ticket {dt_id} not found")

    if ticket["ticket_status"] != "draft":
        err(f"Delivery ticket {dt_id} is already '{ticket['ticket_status']}' -- only draft tickets can be submitted")

    total_amount = ticket["total_amount"]
    if not total_amount or to_decimal(total_amount) <= Decimal("0"):
        err("Cannot submit: total_amount must be > 0. Set price_per_unit and net_weight first.")

    amount = to_decimal(total_amount)
    posting_date = ticket["delivery_date"] or _now_iso()[:10]
    company_id = ticket["company_id"]

    # Allow override from args (e.g., user adds accounts at submit time)
    revenue_account_id = getattr(args, "revenue_account_id", None) or ticket["revenue_account_id"]
    receivable_account_id = getattr(args, "receivable_account_id", None) or ticket["receivable_account_id"]
    cogs_account_id = getattr(args, "cogs_account_id", None) or ticket["cogs_account_id"]
    inventory_account_id = getattr(args, "inventory_account_id", None) or ticket["inventory_account_id"]
    cost_center_id = getattr(args, "cost_center_id", None) or ticket["cost_center_id"]

    # Persist any account overrides
    sql_acct, acct_params = dynamic_update("agricultureclaw_delivery_ticket", {
        "revenue_account_id": revenue_account_id,
        "receivable_account_id": receivable_account_id,
        "cogs_account_id": cogs_account_id,
        "inventory_account_id": inventory_account_id,
        "cost_center_id": cost_center_id,
    }, where={"id": dt_id})
    conn.execute(sql_acct, acct_params)

    all_gl_ids = []

    # --- Primary GL: Revenue recognition ---
    if HAS_GL and revenue_account_id and receivable_account_id:
        try:
            primary_entries = [
                {
                    "account_id": receivable_account_id,
                    "debit": str(round_currency(amount)),
                    "credit": "0",
                    "party_type": "customer",
                    "party_id": ticket["member_id"],
                },
                {
                    "account_id": revenue_account_id,
                    "debit": "0",
                    "credit": str(round_currency(amount)),
                    "cost_center_id": cost_center_id,
                },
            ]
            gl_ids = insert_gl_entries(
                conn, primary_entries,
                voucher_type="Commodity Sale",
                voucher_id=dt_id,
                posting_date=posting_date,
                company_id=company_id,
                remarks=f"Commodity delivery ticket {ticket['naming_series'] or dt_id}",
                entry_set="primary",
            )
            all_gl_ids.extend(gl_ids)
        except (ValueError, Exception) as e:
            # GL posting failed -- still allow submit but warn
            sys.stderr.write(f"[{SKILL}] GL primary posting skipped: {e}\n")

    # --- COGS GL: Cost of goods sold (optional) ---
    if HAS_GL and cogs_account_id and inventory_account_id:
        # Use total_amount as COGS proxy -- in a full system this would be
        # the actual inventory cost, but for agriculture the delivery ticket
        # total_amount represents the commodity value at market price.
        # Farms using actual costing can override via --cogs-amount.
        cogs_amount_raw = getattr(args, "cogs_amount", None)
        cogs_amount = to_decimal(cogs_amount_raw) if cogs_amount_raw else amount
        if cogs_amount > Decimal("0"):
            try:
                cogs_entries = [
                    {
                        "account_id": cogs_account_id,
                        "debit": str(round_currency(cogs_amount)),
                        "credit": "0",
                        "cost_center_id": cost_center_id,
                    },
                    {
                        "account_id": inventory_account_id,
                        "debit": "0",
                        "credit": str(round_currency(cogs_amount)),
                    },
                ]
                cogs_gl_ids = insert_gl_entries(
                    conn, cogs_entries,
                    voucher_type="Commodity Sale",
                    voucher_id=dt_id,
                    posting_date=posting_date,
                    company_id=company_id,
                    remarks=f"COGS for delivery ticket {ticket['naming_series'] or dt_id}",
                    entry_set="cogs",
                )
                all_gl_ids.extend(cogs_gl_ids)
            except (ValueError, Exception) as e:
                sys.stderr.write(f"[{SKILL}] GL COGS posting skipped: {e}\n")

    # Mark submitted + store GL entry IDs
    gl_ids_str = ",".join(all_gl_ids) if all_gl_ids else None
    sql_sub, sub_params = dynamic_update("agricultureclaw_delivery_ticket", {
        "ticket_status": "submitted",
        "gl_entry_ids": gl_ids_str,
    }, where={"id": dt_id})
    conn.execute(sql_sub, sub_params)

    audit(conn, SKILL, "agri-submit-delivery-ticket", "agricultureclaw_delivery_ticket", dt_id,
          new_values={"ticket_status": "submitted", "gl_entry_count": len(all_gl_ids)})
    conn.commit()

    result = {
        "id": dt_id, "ticket_status": "submitted",
        "total_amount": str(amount), "posting_date": posting_date,
    }
    if all_gl_ids:
        result["gl_entry_ids"] = all_gl_ids
        result["gl_entry_count"] = len(all_gl_ids)
    else:
        result["gl_note"] = "No GL entries posted (accounts not configured or GL module unavailable)"
    ok(result)


# ===========================================================================
# 10. cancel-delivery-ticket  (GL reversal)
# ===========================================================================
def cancel_delivery_ticket(conn, args):
    """Cancel a submitted delivery ticket -- reverses GL entries if any."""
    dt_id = getattr(args, "id", None)
    if not dt_id:
        err("--id is required")

    ticket = conn.execute(Q.from_(Table("agricultureclaw_delivery_ticket")).select(Table("agricultureclaw_delivery_ticket").star).where(Field("id") == P()).get_sql(), (dt_id,)).fetchone()
    if not ticket:
        err(f"Delivery ticket {dt_id} not found")

    if ticket["ticket_status"] == "cancelled":
        err(f"Delivery ticket {dt_id} is already cancelled")
    if ticket["ticket_status"] == "draft":
        err(f"Delivery ticket {dt_id} is still in draft -- delete it instead of cancelling")

    posting_date = ticket["delivery_date"] or _now_iso()[:10]
    reversal_ids = []

    # Reverse GL entries if they exist
    if HAS_GL and ticket["gl_entry_ids"]:
        try:
            # Reverse primary entries
            try:
                primary_rev = reverse_gl_entries(
                    conn, voucher_type="Commodity Sale",
                    voucher_id=dt_id, posting_date=posting_date,
                )
                reversal_ids.extend(primary_rev)
            except ValueError:
                pass  # No primary entries to reverse

        except Exception as e:
            sys.stderr.write(f"[{SKILL}] GL reversal error: {e}\n")

    sql_cancel, cancel_params = dynamic_update("agricultureclaw_delivery_ticket", {
        "ticket_status": "cancelled",
    }, where={"id": dt_id})
    conn.execute(sql_cancel, cancel_params)

    audit(conn, SKILL, "agri-cancel-delivery-ticket", "agricultureclaw_delivery_ticket", dt_id,
          new_values={"ticket_status": "cancelled", "reversal_count": len(reversal_ids)})
    conn.commit()

    result = {"id": dt_id, "ticket_status": "cancelled"}
    if reversal_ids:
        result["reversal_gl_entry_ids"] = reversal_ids
    ok(result)


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------
ACTIONS = {
    "agri-add-coop-member": add_coop_member,
    "agri-list-coop-members": list_coop_members,
    "agri-add-delivery-ticket": add_delivery_ticket,
    "agri-list-delivery-tickets": list_delivery_tickets,
    "agri-submit-delivery-ticket": submit_delivery_ticket,
    "agri-cancel-delivery-ticket": cancel_delivery_ticket,
    "agri-calculate-patronage": calculate_patronage,
    "agri-add-pool-account": add_pool_account,
    "agri-list-pool-accounts": list_pool_accounts,
    "agri-cooperative-summary-report": cooperative_summary_report,
}

"""AgricultureClaw -- Cooperative management domain module.

Actions for cooperative members, delivery tickets, and pool accounts (3 tables, 8 actions).
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

    ENTITY_PREFIXES.setdefault("coop_member", "COOP-")
    ENTITY_PREFIXES.setdefault("delivery_ticket", "DT-")
except ImportError:
    pass

SKILL = "agricultureclaw"

_now_iso = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_MEMBER_STATUS = ("active", "inactive", "suspended")
VALID_POOL_STATUS = ("open", "closed", "distributed")


def _validate_company(conn, company_id):
    if not company_id:
        err("--company-id is required")
    if not conn.execute("SELECT id FROM company WHERE id = ?", (company_id,)).fetchone():
        err(f"Company {company_id} not found")


def _validate_member(conn, member_id):
    if not member_id:
        err("--member-id is required")
    if not conn.execute("SELECT id FROM agricultureclaw_coop_member WHERE id = ?", (member_id,)).fetchone():
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

    conn.execute("""
        INSERT INTO agricultureclaw_coop_member (
            id, naming_series, name, member_number, shares, join_date,
            member_status, company_id, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
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
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "member_status", None):
        where.append("member_status = ?")
        params.append(args.member_status)
    if getattr(args, "search", None):
        where.append("(name LIKE ? OR member_number LIKE ?)")
        params.extend([f"%{args.search}%", f"%{args.search}%"])

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_coop_member WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_coop_member WHERE {where_sql} ORDER BY name ASC LIMIT ? OFFSET ?",
        params
    ).fetchall()
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

    conn.execute("""
        INSERT INTO agricultureclaw_delivery_ticket (
            id, naming_series, member_id, delivery_date, commodity,
            gross_weight, tare_weight, net_weight, moisture, grade,
            price_per_unit, total_amount, company_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
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
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "member_id", None):
        where.append("member_id = ?")
        params.append(args.member_id)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_delivery_ticket WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_delivery_ticket WHERE {where_sql} ORDER BY delivery_date DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
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
    tickets = conn.execute(
        "SELECT * FROM agricultureclaw_delivery_ticket WHERE member_id = ? AND company_id = ?",
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

    member = conn.execute("SELECT name FROM agricultureclaw_coop_member WHERE id = ?", (member_id,)).fetchone()

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

    conn.execute("""
        INSERT INTO agricultureclaw_pool_account (
            id, name, commodity, pool_year, total_quantity, total_value,
            members_count, pool_status, company_id, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
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
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)
    if getattr(args, "pool_status", None):
        where.append("pool_status = ?")
        params.append(args.pool_status)

    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_pool_account WHERE {where_sql}", params
    ).fetchone()[0]
    params.extend([args.limit, args.offset])
    rows = conn.execute(
        f"SELECT * FROM agricultureclaw_pool_account WHERE {where_sql} ORDER BY pool_year DESC LIMIT ? OFFSET ?",
        params
    ).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 8. cooperative-summary-report
# ===========================================================================
def cooperative_summary_report(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)

    total_members = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_coop_member WHERE {where_sql}", params
    ).fetchone()[0]
    active_members = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_coop_member WHERE {where_sql} AND member_status = 'active'", params
    ).fetchone()[0]
    total_tickets = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_delivery_ticket WHERE {where_sql}", params
    ).fetchone()[0]
    total_pools = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_pool_account WHERE {where_sql}", params
    ).fetchone()[0]

    ok({
        "total_members": total_members,
        "active_members": active_members,
        "total_delivery_tickets": total_tickets,
        "total_pool_accounts": total_pools,
    })


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------
ACTIONS = {
    "agri-add-coop-member": add_coop_member,
    "agri-list-coop-members": list_coop_members,
    "agri-add-delivery-ticket": add_delivery_ticket,
    "agri-list-delivery-tickets": list_delivery_tickets,
    "agri-calculate-patronage": calculate_patronage,
    "agri-add-pool-account": add_pool_account,
    "agri-list-pool-accounts": list_pool_accounts,
    "agri-cooperative-summary-report": cooperative_summary_report,
}

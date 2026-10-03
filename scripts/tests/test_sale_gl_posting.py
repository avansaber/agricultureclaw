"""Delivery tickets and harvest sales post their ledger, or are refused.

agri-submit-delivery-ticket and agri-submit-harvest-sale posted under voucher
types the GL registry does not hold ("Commodity Sale", "Harvest Sale") and
swallowed the refusal, so a sale submitted with accounts supplied was marked
submitted with no ledger entries, and the cancel actions had nothing to
reverse. They now post and reverse under the registered journal_entry type,
and a posting or reversal failure rolls the action back and says why.
"""
import os
import sys
from decimal import Decimal

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from agri_helpers import (call_action, is_error, is_ok, load_db_query,  # noqa: E402
                          ns, seed_account)

ACTIONS = load_db_query().ACTIONS


def _gl(conn, voucher_id):
    return conn.execute(
        "SELECT id, account_id, entry_set, party_type, party_id, cost_center_id, "
        "debit, credit, voucher_type, is_cancelled, remarks FROM gl_entry "
        "WHERE voucher_id = ?",
        (voucher_id,)).fetchall()


def _net_by_account(rows):
    net = {}
    for x in rows:
        d, c = net.get(x["account_id"], (Decimal("0"), Decimal("0")))
        net[x["account_id"]] = (d + Decimal(x["debit"]), c + Decimal(x["credit"]))
    return net


def _add_ticket(conn, env, delivery_date="2026-10-20", with_accounts=True):
    member = call_action(ACTIONS["agri-add-coop-member"], conn, ns(
        company_id=env["company_id"], name="Ledger Member", member_number=None,
        shares=None, join_date=None))
    assert is_ok(member), member
    accounts = dict(
        revenue_account_id=env["revenue_account_id"],
        receivable_account_id=env["receivable_account_id"],
        cogs_account_id=env["cogs_account_id"],
        inventory_account_id=env["inventory_account_id"],
        cost_center_id=env["cost_center_id"],
    ) if with_accounts else dict(
        revenue_account_id=None, receivable_account_id=None,
        cogs_account_id=None, inventory_account_id=None, cost_center_id=None)
    dt = call_action(ACTIONS["agri-add-delivery-ticket"], conn, ns(
        company_id=env["company_id"], member_id=member["id"],
        delivery_date=delivery_date, commodity="wheat",
        gross_weight="40000", tare_weight="12000", net_weight=None,
        moisture=None, grade=None, price_per_unit="6.00", total_amount=None,
        **accounts))
    assert is_ok(dt), dt
    assert dt["total_amount"] == "168000.00"
    return dt["id"], member["id"]


def _submit_ticket(conn, dt_id, cogs_amount="100000.00"):
    return call_action(ACTIONS["agri-submit-delivery-ticket"], conn, ns(
        id=dt_id, revenue_account_id=None, receivable_account_id=None,
        cogs_account_id=None, inventory_account_id=None, cost_center_id=None,
        cogs_amount=cogs_amount))


def _ticket(conn, dt_id):
    return conn.execute(
        "SELECT ticket_status, gl_entry_ids FROM agricultureclaw_delivery_ticket "
        "WHERE id = ?", (dt_id,)).fetchone()


def _add_harvest(conn, env, receivable_account_id):
    parcel = call_action(ACTIONS["agri-add-parcel"], conn, ns(
        company_id=env["company_id"], name="Ledger Field", acreage="100",
        gps_lat=None, gps_lon=None, soil_type=None, land_use=None, owner=None,
        lease_info=None, parcel_status=None))
    assert is_ok(parcel), parcel
    hr = call_action(ACTIONS["agri-add-harvest-record"], conn, ns(
        company_id=env["company_id"], parcel_id=parcel["id"],
        planting_plan_id=None, harvest_date="2026-10-01",
        yield_amount="10000", yield_unit="bushels", moisture_content=None,
        quality_grade=None, storage_bin_id=None, market_price="5.50",
        revenue="55000.00", revenue_account_id=env["revenue_account_id"],
        receivable_account_id=receivable_account_id,
        cost_center_id=env["cost_center_id"]))
    assert is_ok(hr), hr
    return hr["id"]


def _submit_harvest(conn, hr_id):
    return call_action(ACTIONS["agri-submit-harvest-sale"], conn, ns(
        id=hr_id, revenue_account_id=None, receivable_account_id=None,
        cost_center_id=None))


def _sale_status(conn, hr_id):
    return conn.execute(
        "SELECT sale_status, gl_entry_ids FROM agricultureclaw_harvest_record "
        "WHERE id = ?", (hr_id,)).fetchone()


# ---------------------------------------------------------------------------
# Delivery ticket
# ---------------------------------------------------------------------------

def test_submit_delivery_ticket_posts_revenue_and_cogs_legs(conn, env):
    dt_id, member_id = _add_ticket(conn, env)
    r = _submit_ticket(conn, dt_id)
    assert is_ok(r), r
    assert r["gl_entry_count"] == 4

    rows = _gl(conn, dt_id)
    legs = {(x["account_id"], x["entry_set"]): (x["debit"], x["credit"]) for x in rows}
    assert legs == {
        (env["receivable_account_id"], "primary"): ("168000.00", "0.00"),
        (env["revenue_account_id"], "primary"): ("0.00", "168000.00"),
        (env["cogs_account_id"], "cogs"): ("100000.00", "0.00"),
        (env["inventory_account_id"], "cogs"): ("0.00", "100000.00"),
    }
    assert {x["voucher_type"] for x in rows} == {"journal_entry"}
    assert {x["is_cancelled"] for x in rows} == {0}
    by_account = {x["account_id"]: x for x in rows}
    receivable = by_account[env["receivable_account_id"]]
    assert (receivable["party_type"], receivable["party_id"]) == ("customer", member_id)
    assert by_account[env["revenue_account_id"]]["cost_center_id"] == env["cost_center_id"]
    assert by_account[env["cogs_account_id"]]["cost_center_id"] == env["cost_center_id"]
    assert sum(Decimal(x["debit"]) for x in rows) == Decimal("268000.00")
    assert sum(Decimal(x["credit"]) for x in rows) == Decimal("268000.00")

    ticket = _ticket(conn, dt_id)
    assert ticket["ticket_status"] == "submitted"
    assert set(ticket["gl_entry_ids"].split(",")) == {x["id"] for x in rows}


def test_submit_delivery_ticket_refused_posting_writes_nothing(conn, env):
    # 2025-10-20 falls outside the only fiscal year (2026), so GL step 9 refuses.
    dt_id, _ = _add_ticket(conn, env, delivery_date="2025-10-20")
    r = _submit_ticket(conn, dt_id)
    assert is_error(r), r
    assert "GL posting failed" in r["message"]
    assert "No open fiscal year" in r["message"]
    ticket = _ticket(conn, dt_id)
    assert ticket["ticket_status"] == "draft"
    assert ticket["gl_entry_ids"] is None
    assert _gl(conn, dt_id) == []


def test_submit_delivery_ticket_without_accounts_completes_without_gl(conn, env):
    dt_id, _ = _add_ticket(conn, env, with_accounts=False)
    r = _submit_ticket(conn, dt_id, cogs_amount=None)
    assert is_ok(r), r
    assert r["total_amount"] == "168000.00"
    ticket = _ticket(conn, dt_id)
    assert ticket["ticket_status"] == "submitted"
    assert ticket["gl_entry_ids"] is None
    assert _gl(conn, dt_id) == []


def test_cancel_delivery_ticket_mirrors_every_leg_and_nets_to_zero(conn, env):
    dt_id, _ = _add_ticket(conn, env)
    assert is_ok(_submit_ticket(conn, dt_id))
    originals = {x["id"]: x for x in _gl(conn, dt_id)}
    assert len(originals) == 4

    r = call_action(ACTIONS["agri-cancel-delivery-ticket"], conn, ns(id=dt_id))
    assert is_ok(r), r
    assert len(r["reversal_gl_entry_ids"]) == 4

    rows = _gl(conn, dt_id)
    assert len(rows) == 8
    assert {x["voucher_type"] for x in rows} == {"journal_entry"}
    assert {x["is_cancelled"] for x in rows} == {1}
    reversals = [x for x in rows if x["id"] not in originals]
    assert {x["id"] for x in reversals} == set(r["reversal_gl_entry_ids"])
    mirrored = {x["remarks"]: x for x in reversals}
    for orig_id, orig in originals.items():
        rev = mirrored[f"Reversal of {orig_id}"]
        assert (rev["account_id"], rev["entry_set"]) == (orig["account_id"], orig["entry_set"])
        assert (rev["debit"], rev["credit"]) == (orig["credit"], orig["debit"])
    net = _net_by_account(rows)
    assert net == {
        env["receivable_account_id"]: (Decimal("168000.00"), Decimal("168000.00")),
        env["revenue_account_id"]: (Decimal("168000.00"), Decimal("168000.00")),
        env["cogs_account_id"]: (Decimal("100000.00"), Decimal("100000.00")),
        env["inventory_account_id"]: (Decimal("100000.00"), Decimal("100000.00")),
    }
    assert _ticket(conn, dt_id)["ticket_status"] == "cancelled"


def test_cancel_delivery_ticket_refusals_write_nothing(conn, env):
    draft_id, _ = _add_ticket(conn, env)
    r = call_action(ACTIONS["agri-cancel-delivery-ticket"], conn, ns(id=draft_id))
    assert is_error(r), r
    assert "still in draft" in r["message"]
    assert _ticket(conn, draft_id)["ticket_status"] == "draft"
    assert _gl(conn, draft_id) == []

    dt_id, _ = _add_ticket(conn, env)
    assert is_ok(_submit_ticket(conn, dt_id))
    assert is_ok(call_action(ACTIONS["agri-cancel-delivery-ticket"], conn, ns(id=dt_id)))
    again = call_action(ACTIONS["agri-cancel-delivery-ticket"], conn, ns(id=dt_id))
    assert is_error(again), again
    assert "already cancelled" in again["message"]
    assert len(_gl(conn, dt_id)) == 8


# ---------------------------------------------------------------------------
# Harvest sale
# ---------------------------------------------------------------------------

def test_harvest_sale_to_cash_posts_and_cancel_reverses(conn, env):
    cash = seed_account(conn, env["company_id"], "Farm Cash", "asset", "cash", "1010")
    hr_id = _add_harvest(conn, env, receivable_account_id=cash)
    r = _submit_harvest(conn, hr_id)
    assert is_ok(r), r
    rows = _gl(conn, hr_id)
    assert {x["account_id"]: (x["debit"], x["credit"]) for x in rows} == {
        cash: ("55000.00", "0.00"),
        env["revenue_account_id"]: ("0.00", "55000.00"),
    }
    assert {x["voucher_type"] for x in rows} == {"journal_entry"}
    assert _sale_status(conn, hr_id)["sale_status"] == "submitted"

    c = call_action(ACTIONS["agri-cancel-harvest-sale"], conn, ns(id=hr_id))
    assert is_ok(c), c
    assert len(c["reversal_gl_entry_ids"]) == 2
    rows = _gl(conn, hr_id)
    assert len(rows) == 4
    assert {x["is_cancelled"] for x in rows} == {1}
    assert _net_by_account(rows) == {
        cash: (Decimal("55000.00"), Decimal("55000.00")),
        env["revenue_account_id"]: (Decimal("55000.00"), Decimal("55000.00")),
    }
    assert _sale_status(conn, hr_id)["sale_status"] == "cancelled"


def test_harvest_sale_to_receivable_is_refused_fail_closed(conn, env):
    # The harvest record carries no customer, so a receivable-type debit fails
    # GL step 5. The sale is refused rather than submitted without a ledger.
    hr_id = _add_harvest(conn, env, receivable_account_id=env["receivable_account_id"])
    r = _submit_harvest(conn, hr_id)
    assert is_error(r), r
    assert "GL posting failed" in r["message"]
    assert "Step 5" in r["message"]
    status = _sale_status(conn, hr_id)
    assert (status["sale_status"], status["gl_entry_ids"]) == ("draft", None)
    assert _gl(conn, hr_id) == []

    c = call_action(ACTIONS["agri-cancel-harvest-sale"], conn, ns(id=hr_id))
    assert is_error(c), c
    assert "still in draft" in c["message"]
    assert _sale_status(conn, hr_id)["sale_status"] == "draft"
    assert _gl(conn, hr_id) == []

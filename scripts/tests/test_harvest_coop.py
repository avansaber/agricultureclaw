"""L1 tests for AgricultureClaw -- Harvest and Cooperative domains.

Covers:
  - Harvest records: add, update, list
  - Storage bins: add, list
  - Quality grades: add, list
  - Harvest sale submit/cancel (status transitions, no GL in test)
  - Harvest reports: yield-analysis, harvest-summary, crop-profitability
  - Co-op members: add, list
  - Delivery tickets: add, list, submit, cancel
  - Pool accounts: add, list
  - Patronage calculation
  - Cooperative summary report
  - Status action
"""
import os
import sys
import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from agri_helpers import call_action, ns, is_ok, is_error, load_db_query

_mod = None


def _get_mod():
    global _mod
    if _mod is None:
        _mod = load_db_query()
    return _mod


def _actions():
    return _get_mod().ACTIONS


def _add_parcel(conn, env, name="Harvest Field"):
    r = call_action(_actions()["agri-add-parcel"], conn, ns(
        company_id=env["company_id"], name=name,
        acreage="100", gps_lat=None, gps_lon=None, soil_type=None,
        land_use=None, owner=None, lease_info=None, parcel_status=None,
    ))
    assert is_ok(r)
    return r["id"]


# ═══════════════════════════════════════════════════════════════════════════════
# Harvest Records
# ═══════════════════════════════════════════════════════════════════════════════

class TestHarvestRecords:
    def test_add_harvest_record(self, conn, env):
        pid = _add_parcel(conn, env)
        r = call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            planting_plan_id=None,
            harvest_date="2026-10-01",
            yield_amount="15000",
            yield_unit="bushels",
            moisture_content="15.5",
            quality_grade="1",
            storage_bin_id=None,
            market_price="5.50",
            revenue="82500.00",
            revenue_account_id=None,
            receivable_account_id=None,
            cost_center_id=None,
        ))
        assert is_ok(r)
        assert r["parcel_id"] == pid
        assert r["naming_series"] is not None

    def test_add_harvest_record_missing_parcel(self, conn, env):
        r = call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"],
            parcel_id=None,
            planting_plan_id=None,
            harvest_date=None, yield_amount=None, yield_unit=None,
            moisture_content=None, quality_grade=None,
            storage_bin_id=None, market_price=None, revenue=None,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        assert is_error(r)

    def test_update_harvest_record(self, conn, env):
        pid = _add_parcel(conn, env)
        add_r = call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            planting_plan_id=None,
            harvest_date="2026-10-01",
            yield_amount="15000", yield_unit="bushels",
            moisture_content=None, quality_grade=None,
            storage_bin_id=None, market_price=None, revenue=None,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        hr_id = add_r["id"]
        r = call_action(_actions()["agri-update-harvest-record"], conn, ns(
            id=hr_id,
            harvest_date=None,
            yield_amount="16000",
            yield_unit=None, moisture_content="14.0",
            quality_grade=None, market_price="5.75", revenue="92000.00",
        ))
        assert is_ok(r)
        assert "yield_amount" in r["updated_fields"]
        assert "revenue" in r["updated_fields"]

    def test_list_harvest_records(self, conn, env):
        pid = _add_parcel(conn, env)
        call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            planting_plan_id=None,
            harvest_date="2026-10-01",
            yield_amount="10000", yield_unit="bushels",
            moisture_content=None, quality_grade=None,
            storage_bin_id=None, market_price=None, revenue=None,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        r = call_action(_actions()["agri-list-harvest-records"], conn, ns(
            company_id=env["company_id"],
            parcel_id=None, planting_plan_id=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Storage Bins
# ═══════════════════════════════════════════════════════════════════════════════

class TestStorageBins:
    def test_add_storage_bin(self, conn, env):
        r = call_action(_actions()["agri-add-storage-bin"], conn, ns(
            company_id=env["company_id"],
            name="Bin #1",
            bin_type="silo",
            capacity="50000",
            current_quantity=None,
            crop_type="corn",
            location="North Yard",
        ))
        assert is_ok(r)
        assert r["name"] == "Bin #1"

    def test_add_storage_bin_missing_name(self, conn, env):
        r = call_action(_actions()["agri-add-storage-bin"], conn, ns(
            company_id=env["company_id"],
            name=None, bin_type=None, capacity=None,
            current_quantity=None, crop_type=None, location=None,
        ))
        assert is_error(r)

    def test_add_storage_bin_invalid_type(self, conn, env):
        r = call_action(_actions()["agri-add-storage-bin"], conn, ns(
            company_id=env["company_id"],
            name="Bad Bin",
            bin_type="pool",
            capacity=None, current_quantity=None,
            crop_type=None, location=None,
        ))
        assert is_error(r)

    def test_list_storage_bins(self, conn, env):
        call_action(_actions()["agri-add-storage-bin"], conn, ns(
            company_id=env["company_id"],
            name="Silo A", bin_type="silo",
            capacity="40000", current_quantity=None,
            crop_type=None, location=None,
        ))
        call_action(_actions()["agri-add-storage-bin"], conn, ns(
            company_id=env["company_id"],
            name="Warehouse B", bin_type="warehouse",
            capacity="100000", current_quantity=None,
            crop_type=None, location=None,
        ))
        r = call_action(_actions()["agri-list-storage-bins"], conn, ns(
            company_id=env["company_id"],
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Quality Grades
# ═══════════════════════════════════════════════════════════════════════════════

class TestQualityGrades:
    def _add_harvest(self, conn, env):
        pid = _add_parcel(conn, env, "QG Field")
        hr = call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            planting_plan_id=None,
            harvest_date="2026-10-01",
            yield_amount="10000", yield_unit="bushels",
            moisture_content=None, quality_grade=None,
            storage_bin_id=None, market_price=None, revenue=None,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        return hr["id"]

    def test_add_quality_grade(self, conn, env):
        hr_id = self._add_harvest(conn, env)
        r = call_action(_actions()["agri-add-quality-grade"], conn, ns(
            company_id=env["company_id"],
            harvest_id=hr_id,
            grade="1",
            test_weight="60.5",
            foreign_material="0.2",
            damage_pct="0.5",
            notes="Grade 1 corn",
        ))
        assert is_ok(r)
        assert r["grade"] == "1"

    def test_add_quality_grade_invalid(self, conn, env):
        hr_id = self._add_harvest(conn, env)
        r = call_action(_actions()["agri-add-quality-grade"], conn, ns(
            company_id=env["company_id"],
            harvest_id=hr_id,
            grade="premium",
            test_weight=None, foreign_material=None,
            damage_pct=None, notes=None,
        ))
        assert is_error(r)

    def test_list_quality_grades(self, conn, env):
        hr_id = self._add_harvest(conn, env)
        call_action(_actions()["agri-add-quality-grade"], conn, ns(
            company_id=env["company_id"], harvest_id=hr_id,
            grade="1", test_weight="60.0",
            foreign_material=None, damage_pct=None, notes=None,
        ))
        r = call_action(_actions()["agri-list-quality-grades"], conn, ns(
            harvest_id=hr_id, company_id=env["company_id"],
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Harvest Sale Submit / Cancel
# ═══════════════════════════════════════════════════════════════════════════════

class TestHarvestSale:
    def _add_harvest_with_revenue(self, conn, env):
        pid = _add_parcel(conn, env, "Sale Field")
        hr = call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            planting_plan_id=None,
            harvest_date="2026-10-01",
            yield_amount="10000", yield_unit="bushels",
            moisture_content=None, quality_grade=None,
            storage_bin_id=None, market_price="5.50", revenue="55000.00",
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        return hr["id"]

    def test_submit_harvest_sale(self, conn, env):
        hr_id = self._add_harvest_with_revenue(conn, env)
        r = call_action(_actions()["agri-submit-harvest-sale"], conn, ns(
            id=hr_id,
            revenue_account_id=None,
            receivable_account_id=None,
            cost_center_id=None,
        ))
        assert is_ok(r)
        assert r["sale_status"] == "submitted"
        assert r["revenue"] == "55000.00"

    def test_submit_harvest_sale_no_revenue(self, conn, env):
        pid = _add_parcel(conn, env, "No Rev Field")
        hr = call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            planting_plan_id=None,
            harvest_date="2026-10-01",
            yield_amount="10000", yield_unit="bushels",
            moisture_content=None, quality_grade=None,
            storage_bin_id=None, market_price=None, revenue=None,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        r = call_action(_actions()["agri-submit-harvest-sale"], conn, ns(
            id=hr["id"],
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        assert is_error(r)

    def test_cancel_harvest_sale(self, conn, env):
        hr_id = self._add_harvest_with_revenue(conn, env)
        call_action(_actions()["agri-submit-harvest-sale"], conn, ns(
            id=hr_id,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        r = call_action(_actions()["agri-cancel-harvest-sale"], conn, ns(id=hr_id))
        assert is_ok(r)
        assert r["sale_status"] == "cancelled"

    def test_cancel_harvest_sale_draft(self, conn, env):
        hr_id = self._add_harvest_with_revenue(conn, env)
        r = call_action(_actions()["agri-cancel-harvest-sale"], conn, ns(id=hr_id))
        assert is_error(r)

    def test_submit_already_submitted(self, conn, env):
        hr_id = self._add_harvest_with_revenue(conn, env)
        call_action(_actions()["agri-submit-harvest-sale"], conn, ns(
            id=hr_id,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        r = call_action(_actions()["agri-submit-harvest-sale"], conn, ns(
            id=hr_id,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        assert is_error(r)


# ═══════════════════════════════════════════════════════════════════════════════
# Harvest Reports
# ═══════════════════════════════════════════════════════════════════════════════

class TestHarvestReports:
    def test_harvest_summary(self, conn, env):
        pid = _add_parcel(conn, env, "Summary Field")
        call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            planting_plan_id=None,
            harvest_date="2026-10-01",
            yield_amount="5000", yield_unit="bushels",
            moisture_content=None, quality_grade=None,
            storage_bin_id=None, market_price=None, revenue=None,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        r = call_action(_actions()["agri-harvest-summary"], conn, ns(
            company_id=env["company_id"],
        ))
        assert is_ok(r)
        assert r["total_harvest_records"] == 1

    def test_yield_analysis_report(self, conn, env):
        pid = _add_parcel(conn, env, "Yield Field")
        call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            planting_plan_id=None,
            harvest_date="2026-10-01",
            yield_amount="15000", yield_unit="bushels",
            moisture_content=None, quality_grade=None,
            storage_bin_id=None, market_price=None, revenue=None,
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        r = call_action(_actions()["agri-yield-analysis-report"], conn, ns(
            company_id=env["company_id"],
        ))
        assert is_ok(r)
        assert r["total_count"] >= 1

    def test_crop_profitability_report(self, conn, env):
        pid = _add_parcel(conn, env, "Profit Field")
        call_action(_actions()["agri-add-harvest-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            planting_plan_id=None,
            harvest_date="2026-10-01",
            yield_amount="10000", yield_unit="bushels",
            moisture_content=None, quality_grade=None,
            storage_bin_id=None, market_price="5.50", revenue="55000.00",
            revenue_account_id=None, receivable_account_id=None,
            cost_center_id=None,
        ))
        r = call_action(_actions()["agri-crop-profitability-report"], conn, ns(
            company_id=env["company_id"],
        ))
        assert is_ok(r)
        assert r["total_revenue"] == "55000.00"


# ═══════════════════════════════════════════════════════════════════════════════
# Cooperative Members
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoopMembers:
    def test_add_coop_member(self, conn, env):
        r = call_action(_actions()["agri-add-coop-member"], conn, ns(
            company_id=env["company_id"],
            name="Bob Johnson",
            member_number="M-001",
            shares="100",
            join_date="2025-01-01",
        ))
        assert is_ok(r)
        assert r["name"] == "Bob Johnson"
        assert r["member_status"] == "active"

    def test_add_coop_member_missing_name(self, conn, env):
        r = call_action(_actions()["agri-add-coop-member"], conn, ns(
            company_id=env["company_id"],
            name=None, member_number=None,
            shares=None, join_date=None,
        ))
        assert is_error(r)

    def test_list_coop_members(self, conn, env):
        call_action(_actions()["agri-add-coop-member"], conn, ns(
            company_id=env["company_id"],
            name="Alice", member_number="M-001",
            shares="50", join_date=None,
        ))
        call_action(_actions()["agri-add-coop-member"], conn, ns(
            company_id=env["company_id"],
            name="Bob", member_number="M-002",
            shares="75", join_date=None,
        ))
        r = call_action(_actions()["agri-list-coop-members"], conn, ns(
            company_id=env["company_id"],
            member_status=None, search=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Delivery Tickets
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeliveryTickets:
    def _add_member(self, conn, env, name="Farmer Joe"):
        r = call_action(_actions()["agri-add-coop-member"], conn, ns(
            company_id=env["company_id"],
            name=name, member_number=None,
            shares=None, join_date=None,
        ))
        assert is_ok(r)
        return r["id"]

    def test_add_delivery_ticket(self, conn, env):
        mid = self._add_member(conn, env)
        r = call_action(_actions()["agri-add-delivery-ticket"], conn, ns(
            company_id=env["company_id"],
            member_id=mid,
            delivery_date="2026-10-15",
            commodity="corn",
            gross_weight="45000",
            tare_weight="15000",
            net_weight=None,  # should be auto-calculated
            moisture="14.5",
            grade="1",
            price_per_unit="5.50",
            total_amount=None,  # should be auto-calculated
            revenue_account_id=None,
            receivable_account_id=None,
            cogs_account_id=None,
            inventory_account_id=None,
            cost_center_id=None,
        ))
        assert is_ok(r)
        assert r["net_weight"] == "30000"
        assert r["total_amount"] == "165000.00"

    def test_add_delivery_ticket_missing_member(self, conn, env):
        r = call_action(_actions()["agri-add-delivery-ticket"], conn, ns(
            company_id=env["company_id"],
            member_id=None,
            delivery_date=None, commodity=None,
            gross_weight=None, tare_weight=None,
            net_weight=None, moisture=None, grade=None,
            price_per_unit=None, total_amount=None,
            revenue_account_id=None, receivable_account_id=None,
            cogs_account_id=None, inventory_account_id=None,
            cost_center_id=None,
        ))
        assert is_error(r)

    def test_list_delivery_tickets(self, conn, env):
        mid = self._add_member(conn, env)
        call_action(_actions()["agri-add-delivery-ticket"], conn, ns(
            company_id=env["company_id"], member_id=mid,
            delivery_date="2026-10-15", commodity="corn",
            gross_weight="45000", tare_weight="15000",
            net_weight=None, moisture=None, grade=None,
            price_per_unit="5.50", total_amount=None,
            revenue_account_id=None, receivable_account_id=None,
            cogs_account_id=None, inventory_account_id=None,
            cost_center_id=None,
        ))
        r = call_action(_actions()["agri-list-delivery-tickets"], conn, ns(
            company_id=env["company_id"], member_id=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Delivery Ticket Submit / Cancel
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeliveryTicketSubmit:
    def _add_ticket(self, conn, env):
        mr = call_action(_actions()["agri-add-coop-member"], conn, ns(
            company_id=env["company_id"],
            name="Submit Member", member_number=None,
            shares=None, join_date=None,
        ))
        mid = mr["id"]
        dt = call_action(_actions()["agri-add-delivery-ticket"], conn, ns(
            company_id=env["company_id"], member_id=mid,
            delivery_date="2026-10-20", commodity="wheat",
            gross_weight="40000", tare_weight="12000",
            net_weight=None, moisture=None, grade=None,
            price_per_unit="6.00", total_amount=None,
            revenue_account_id=None, receivable_account_id=None,
            cogs_account_id=None, inventory_account_id=None,
            cost_center_id=None,
        ))
        return dt["id"]

    def test_submit_delivery_ticket(self, conn, env):
        dt_id = self._add_ticket(conn, env)
        r = call_action(_actions()["agri-submit-delivery-ticket"], conn, ns(
            id=dt_id,
            revenue_account_id=None, receivable_account_id=None,
            cogs_account_id=None, inventory_account_id=None,
            cost_center_id=None, cogs_amount=None,
        ))
        assert is_ok(r)
        assert r["ticket_status"] == "submitted"

    def test_submit_already_submitted(self, conn, env):
        dt_id = self._add_ticket(conn, env)
        call_action(_actions()["agri-submit-delivery-ticket"], conn, ns(
            id=dt_id,
            revenue_account_id=None, receivable_account_id=None,
            cogs_account_id=None, inventory_account_id=None,
            cost_center_id=None, cogs_amount=None,
        ))
        r = call_action(_actions()["agri-submit-delivery-ticket"], conn, ns(
            id=dt_id,
            revenue_account_id=None, receivable_account_id=None,
            cogs_account_id=None, inventory_account_id=None,
            cost_center_id=None, cogs_amount=None,
        ))
        assert is_error(r)

    def test_cancel_delivery_ticket(self, conn, env):
        dt_id = self._add_ticket(conn, env)
        call_action(_actions()["agri-submit-delivery-ticket"], conn, ns(
            id=dt_id,
            revenue_account_id=None, receivable_account_id=None,
            cogs_account_id=None, inventory_account_id=None,
            cost_center_id=None, cogs_amount=None,
        ))
        r = call_action(_actions()["agri-cancel-delivery-ticket"], conn, ns(id=dt_id))
        assert is_ok(r)
        assert r["ticket_status"] == "cancelled"

    def test_cancel_draft_ticket(self, conn, env):
        dt_id = self._add_ticket(conn, env)
        r = call_action(_actions()["agri-cancel-delivery-ticket"], conn, ns(id=dt_id))
        assert is_error(r)


# ═══════════════════════════════════════════════════════════════════════════════
# Pool Accounts
# ═══════════════════════════════════════════════════════════════════════════════

class TestPoolAccounts:
    def test_add_pool_account(self, conn, env):
        r = call_action(_actions()["agri-add-pool-account"], conn, ns(
            company_id=env["company_id"],
            name="Corn Pool 2026",
            commodity="corn",
            pool_year=2026,
            total_quantity=None,
            total_value=None,
            members_count=None,
            pool_status=None,
        ))
        assert is_ok(r)
        assert r["name"] == "Corn Pool 2026"
        assert r["pool_status"] == "open"

    def test_add_pool_account_invalid_status(self, conn, env):
        r = call_action(_actions()["agri-add-pool-account"], conn, ns(
            company_id=env["company_id"],
            name="Bad Pool",
            commodity=None, pool_year=None,
            total_quantity=None, total_value=None,
            members_count=None,
            pool_status="pending",
        ))
        assert is_error(r)

    def test_list_pool_accounts(self, conn, env):
        call_action(_actions()["agri-add-pool-account"], conn, ns(
            company_id=env["company_id"],
            name="Corn Pool", commodity="corn", pool_year=2026,
            total_quantity=None, total_value=None,
            members_count=None, pool_status=None,
        ))
        call_action(_actions()["agri-add-pool-account"], conn, ns(
            company_id=env["company_id"],
            name="Wheat Pool", commodity="wheat", pool_year=2026,
            total_quantity=None, total_value=None,
            members_count=None, pool_status=None,
        ))
        r = call_action(_actions()["agri-list-pool-accounts"], conn, ns(
            company_id=env["company_id"], pool_status=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Patronage Calculation
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatronage:
    def test_calculate_patronage(self, conn, env):
        mr = call_action(_actions()["agri-add-coop-member"], conn, ns(
            company_id=env["company_id"],
            name="Patronage Farmer", member_number="M-100",
            shares=None, join_date=None,
        ))
        mid = mr["id"]
        # Two delivery tickets
        call_action(_actions()["agri-add-delivery-ticket"], conn, ns(
            company_id=env["company_id"], member_id=mid,
            delivery_date="2026-10-01", commodity="corn",
            gross_weight="40000", tare_weight="12000",
            net_weight=None, moisture=None, grade=None,
            price_per_unit="5.50", total_amount=None,
            revenue_account_id=None, receivable_account_id=None,
            cogs_account_id=None, inventory_account_id=None,
            cost_center_id=None,
        ))
        call_action(_actions()["agri-add-delivery-ticket"], conn, ns(
            company_id=env["company_id"], member_id=mid,
            delivery_date="2026-10-15", commodity="corn",
            gross_weight="38000", tare_weight="12000",
            net_weight=None, moisture=None, grade=None,
            price_per_unit="5.50", total_amount=None,
            revenue_account_id=None, receivable_account_id=None,
            cogs_account_id=None, inventory_account_id=None,
            cost_center_id=None,
        ))
        r = call_action(_actions()["agri-calculate-patronage"], conn, ns(
            company_id=env["company_id"], member_id=mid,
        ))
        assert is_ok(r)
        assert r["total_tickets"] == 2
        # net_weight: 28000 + 26000 = 54000
        assert r["total_delivered_weight"] == "54000"
        # total_amount: 28000*5.50 + 26000*5.50 = 154000 + 143000 = 297000
        assert r["total_value"] == "297000.00"


# ═══════════════════════════════════════════════════════════════════════════════
# Cooperative Summary Report
# ═══════════════════════════════════════════════════════════════════════════════

class TestCooperativeSummaryReport:
    def test_cooperative_summary(self, conn, env):
        call_action(_actions()["agri-add-coop-member"], conn, ns(
            company_id=env["company_id"],
            name="Member 1", member_number="M-001",
            shares=None, join_date=None,
        ))
        call_action(_actions()["agri-add-coop-member"], conn, ns(
            company_id=env["company_id"],
            name="Member 2", member_number="M-002",
            shares=None, join_date=None,
        ))
        r = call_action(_actions()["agri-cooperative-summary-report"], conn, ns(
            company_id=env["company_id"],
        ))
        assert is_ok(r)
        assert r["total_members"] == 2
        assert r["active_members"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Status Action
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatus:
    def test_status(self, conn, env):
        r = call_action(_actions()["status"], conn, ns())
        assert is_ok(r)
        assert r["skill"] == "agricultureclaw"
        assert r["total_tables"] == 21
        # All tables should exist (count >= 0, not -1)
        for tbl, count in r["record_counts"].items():
            assert count >= 0, f"Table {tbl} is missing (count = -1)"

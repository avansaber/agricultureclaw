"""L1 tests for AgricultureClaw -- Field Operations domain.

Covers:
  - Field operations: add, update, get, list, complete
  - Scouting reports: add, list
  - Irrigation logs: add, list
  - Chemical applications: add, list
  - Field activity report
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


def _add_parcel(conn, env, name="Ops Field"):
    r = call_action(_actions()["agri-add-parcel"], conn, ns(
        company_id=env["company_id"], name=name,
        acreage="100", gps_lat=None, gps_lon=None, soil_type=None,
        land_use=None, owner=None, lease_info=None, parcel_status=None,
    ))
    assert is_ok(r)
    return r["id"]


# ═══════════════════════════════════════════════════════════════════════════════
# Field Operations
# ═══════════════════════════════════════════════════════════════════════════════

class TestFieldOperations:
    def test_add_field_operation(self, conn, env):
        pid = _add_parcel(conn, env)
        r = call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            operation_type="planting",
            planned_date="2026-04-15",
            completed_date=None,
            operator="John",
            equipment="Planter 6-row",
            cost="500.00",
            notes="Spring planting",
            op_status=None,
        ))
        assert is_ok(r)
        assert r["operation_type"] == "planting"
        assert r["op_status"] == "planned"
        assert r["naming_series"] is not None

    def test_add_field_operation_missing_type(self, conn, env):
        pid = _add_parcel(conn, env)
        r = call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            operation_type=None,
            planned_date=None, completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        assert is_error(r)

    def test_add_field_operation_invalid_type(self, conn, env):
        pid = _add_parcel(conn, env)
        r = call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            operation_type="flying",
            planned_date=None, completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        assert is_error(r)

    def test_update_field_operation(self, conn, env):
        pid = _add_parcel(conn, env)
        add_r = call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            operation_type="tillage",
            planned_date="2026-03-20", completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        fo_id = add_r["id"]
        r = call_action(_actions()["agri-update-field-operation"], conn, ns(
            id=fo_id,
            planned_date=None, completed_date=None,
            operator="Mike", equipment="Chisel Plow",
            cost="300.00", notes=None, op_status=None,
        ))
        assert is_ok(r)
        assert "operator" in r["updated_fields"]
        assert "equipment" in r["updated_fields"]

    def test_update_field_operation_status(self, conn, env):
        pid = _add_parcel(conn, env)
        add_r = call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            operation_type="irrigation",
            planned_date="2026-06-01", completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        fo_id = add_r["id"]
        r = call_action(_actions()["agri-update-field-operation"], conn, ns(
            id=fo_id,
            planned_date=None, completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status="in_progress",
        ))
        assert is_ok(r)
        assert "op_status" in r["updated_fields"]

    def test_get_field_operation(self, conn, env):
        pid = _add_parcel(conn, env)
        add_r = call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            operation_type="spraying",
            planned_date="2026-05-01", completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        fo_id = add_r["id"]
        r = call_action(_actions()["agri-get-field-operation"], conn, ns(id=fo_id))
        assert is_ok(r)
        assert r["id"] == fo_id
        assert r["operation_type"] == "spraying"

    def test_list_field_operations(self, conn, env):
        pid = _add_parcel(conn, env)
        call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            operation_type="planting",
            planned_date=None, completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            operation_type="tillage",
            planned_date=None, completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        r = call_action(_actions()["agri-list-field-operations"], conn, ns(
            company_id=env["company_id"],
            parcel_id=None, operation_type=None, op_status=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2

    def test_complete_field_operation(self, conn, env):
        pid = _add_parcel(conn, env)
        add_r = call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            operation_type="fertilization",
            planned_date="2026-03-15", completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        fo_id = add_r["id"]
        r = call_action(_actions()["agri-complete-field-operation"], conn, ns(
            id=fo_id, completed_date="2026-03-16",
        ))
        assert is_ok(r)
        assert r["op_status"] == "completed"
        assert r["completed_date"] == "2026-03-16"

    def test_complete_already_completed(self, conn, env):
        pid = _add_parcel(conn, env)
        add_r = call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            operation_type="tillage",
            planned_date="2026-03-10", completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        fo_id = add_r["id"]
        call_action(_actions()["agri-complete-field-operation"], conn, ns(
            id=fo_id, completed_date=None,
        ))
        r = call_action(_actions()["agri-complete-field-operation"], conn, ns(
            id=fo_id, completed_date=None,
        ))
        assert is_error(r)


# ═══════════════════════════════════════════════════════════════════════════════
# Scouting Reports
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoutingReports:
    def test_add_scouting_report(self, conn, env):
        pid = _add_parcel(conn, env, "Scout Field")
        r = call_action(_actions()["agri-add-scouting-report"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            scout_date="2026-06-15",
            pest_found="Aphids",
            disease_found=None,
            weed_pressure="low",
            crop_health="good",
            notes="Minor pest presence",
            photos=None,
        ))
        assert is_ok(r)
        assert r["parcel_id"] == pid

    def test_add_scouting_report_invalid_weed(self, conn, env):
        pid = _add_parcel(conn, env, "Scout Field 2")
        r = call_action(_actions()["agri-add-scouting-report"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            scout_date=None, pest_found=None, disease_found=None,
            weed_pressure="extreme",
            crop_health=None, notes=None, photos=None,
        ))
        assert is_error(r)

    def test_list_scouting_reports(self, conn, env):
        pid = _add_parcel(conn, env, "Scout List Field")
        call_action(_actions()["agri-add-scouting-report"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            scout_date="2026-06-01", pest_found=None, disease_found=None,
            weed_pressure="none", crop_health="excellent",
            notes=None, photos=None,
        ))
        call_action(_actions()["agri-add-scouting-report"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            scout_date="2026-06-15", pest_found=None, disease_found=None,
            weed_pressure="low", crop_health="good",
            notes=None, photos=None,
        ))
        r = call_action(_actions()["agri-list-scouting-reports"], conn, ns(
            parcel_id=pid, company_id=env["company_id"],
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Irrigation Logs
# ═══════════════════════════════════════════════════════════════════════════════

class TestIrrigationLogs:
    def test_add_irrigation_log(self, conn, env):
        pid = _add_parcel(conn, env, "Irrigation Field")
        r = call_action(_actions()["agri-add-irrigation-log"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            irrigation_date="2026-07-01",
            method="pivot",
            gallons="50000",
            duration_hours="8",
        ))
        assert is_ok(r)
        assert r["parcel_id"] == pid

    def test_add_irrigation_log_invalid_method(self, conn, env):
        pid = _add_parcel(conn, env, "Irrigation Field 2")
        r = call_action(_actions()["agri-add-irrigation-log"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            irrigation_date=None,
            method="hose",
            gallons=None, duration_hours=None,
        ))
        assert is_error(r)

    def test_list_irrigation_logs(self, conn, env):
        pid = _add_parcel(conn, env, "Irrigation List")
        call_action(_actions()["agri-add-irrigation-log"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            irrigation_date="2026-07-01", method="drip",
            gallons="10000", duration_hours="4",
        ))
        r = call_action(_actions()["agri-list-irrigation-logs"], conn, ns(
            parcel_id=pid, company_id=env["company_id"],
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Chemical Applications
# ═══════════════════════════════════════════════════════════════════════════════

class TestChemicalApplications:
    def test_add_chemical_application(self, conn, env):
        pid = _add_parcel(conn, env, "Chem Field")
        r = call_action(_actions()["agri-add-chemical-application"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            application_date="2026-05-20",
            chemical_name="Roundup PowerMax",
            epa_reg_number="524-549",
            rate="32",
            unit="oz/acre",
            target="weed",
            applicator="John",
            wind_speed="5",
            temperature="72",
        ))
        assert is_ok(r)
        assert r["parcel_id"] == pid

    def test_add_chemical_application_invalid_target(self, conn, env):
        pid = _add_parcel(conn, env, "Chem Field 2")
        r = call_action(_actions()["agri-add-chemical-application"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pid,
            application_date=None,
            chemical_name=None, epa_reg_number=None,
            rate=None, unit=None,
            target="fungus",
            applicator=None, wind_speed=None, temperature=None,
        ))
        assert is_error(r)

    def test_list_chemical_applications(self, conn, env):
        pid = _add_parcel(conn, env, "Chem List Field")
        call_action(_actions()["agri-add-chemical-application"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            application_date="2026-05-20",
            chemical_name="Herbicide A", epa_reg_number="111-222",
            rate="16", unit="oz/acre",
            target="weed", applicator=None,
            wind_speed=None, temperature=None,
        ))
        call_action(_actions()["agri-add-chemical-application"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            application_date="2026-06-10",
            chemical_name="Insecticide B", epa_reg_number="333-444",
            rate="8", unit="oz/acre",
            target="pest", applicator=None,
            wind_speed=None, temperature=None,
        ))
        r = call_action(_actions()["agri-list-chemical-applications"], conn, ns(
            parcel_id=pid, company_id=env["company_id"],
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Field Activity Report
# ═══════════════════════════════════════════════════════════════════════════════

class TestFieldActivityReport:
    def test_field_activity_report(self, conn, env):
        pid = _add_parcel(conn, env, "Activity Field")
        # Add one of each type
        call_action(_actions()["agri-add-field-operation"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            operation_type="planting",
            planned_date=None, completed_date=None,
            operator=None, equipment=None, cost=None, notes=None,
            op_status=None,
        ))
        call_action(_actions()["agri-add-scouting-report"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            scout_date=None, pest_found=None, disease_found=None,
            weed_pressure=None, crop_health=None,
            notes=None, photos=None,
        ))
        call_action(_actions()["agri-add-irrigation-log"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            irrigation_date=None, method="pivot",
            gallons=None, duration_hours=None,
        ))
        call_action(_actions()["agri-add-chemical-application"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            application_date=None, chemical_name=None,
            epa_reg_number=None, rate=None, unit=None,
            target="weed", applicator=None,
            wind_speed=None, temperature=None,
        ))
        r = call_action(_actions()["agri-field-activity-report"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
        ))
        assert is_ok(r)
        assert r["total_operations"] == 1
        assert r["total_scouting_reports"] == 1
        assert r["total_irrigations"] == 1
        assert r["total_chemical_applications"] == 1

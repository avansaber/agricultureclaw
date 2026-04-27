"""L1 tests for AgricultureClaw -- Land management and Crops domain.

Covers:
  - Parcels: add, update, get, list, summary
  - Soil tests: add, list
  - Land use records: add, list
  - Crop types: add, list
  - Planting plans: add, update, get, list
  - Growth stages: add, list, advance
  - Seed lots: add, list
  - Reports: land-utilization, crop-rotation
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


# ═══════════════════════════════════════════════════════════════════════════════
# Parcels
# ═══════════════════════════════════════════════════════════════════════════════

class TestAddParcel:
    def test_add_parcel_basic(self, conn, env):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"],
            name="North Field",
            acreage="160.5",
            gps_lat="42.0",
            gps_lon="-93.5",
            soil_type="loam",
            land_use="cropland",
            owner="John Farmer",
            lease_info=None,
            parcel_status=None,
        ))
        assert is_ok(r), r
        assert r["name"] == "North Field"
        assert r["parcel_status"] == "active"
        assert "id" in r
        assert r["naming_series"] is not None

    def test_add_parcel_missing_name(self, conn, env):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"],
            name=None,
            acreage=None, gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_error(r)

    def test_add_parcel_missing_company(self, conn, env):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=None,
            name="Test Field",
            acreage=None, gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_error(r)

    def test_add_parcel_invalid_land_use(self, conn, env):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"],
            name="Bad Field",
            acreage=None, gps_lat=None, gps_lon=None, soil_type=None,
            land_use="desert",
            owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_error(r)

    def test_add_parcel_pasture(self, conn, env):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"],
            name="Pasture Field",
            acreage="80",
            gps_lat=None, gps_lon=None, soil_type=None,
            land_use="pasture",
            owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_ok(r)


class TestUpdateParcel:
    def _add_parcel(self, conn, env):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"], name="Update Field",
            acreage="100", gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_ok(r)
        return r["id"]

    def test_update_parcel_name(self, conn, env):
        pid = self._add_parcel(conn, env)
        r = call_action(_actions()["agri-update-parcel"], conn, ns(
            id=pid, name="Updated Field",
            acreage=None, gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_ok(r)
        assert "name" in r["updated_fields"]

    def test_update_parcel_status(self, conn, env):
        pid = self._add_parcel(conn, env)
        r = call_action(_actions()["agri-update-parcel"], conn, ns(
            id=pid, name=None,
            acreage=None, gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None,
            parcel_status="fallow",
        ))
        assert is_ok(r)
        assert "parcel_status" in r["updated_fields"]

    def test_update_parcel_no_fields(self, conn, env):
        pid = self._add_parcel(conn, env)
        r = call_action(_actions()["agri-update-parcel"], conn, ns(
            id=pid, name=None,
            acreage=None, gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_error(r)


class TestGetListParcel:
    def _add_parcel(self, conn, env, name="Test Field"):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"], name=name,
            acreage="50", gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_ok(r)
        return r["id"]

    def test_get_parcel(self, conn, env):
        pid = self._add_parcel(conn, env)
        r = call_action(_actions()["agri-get-parcel"], conn, ns(id=pid))
        assert is_ok(r)
        assert r["id"] == pid
        assert "soil_tests" in r
        assert "land_use_records" in r

    def test_get_parcel_not_found(self, conn, env):
        r = call_action(_actions()["agri-get-parcel"], conn, ns(id="nonexistent"))
        assert is_error(r)

    def test_list_parcels(self, conn, env):
        self._add_parcel(conn, env, "Field A")
        self._add_parcel(conn, env, "Field B")
        r = call_action(_actions()["agri-list-parcels"], conn, ns(
            company_id=env["company_id"],
            parcel_status=None, search=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2
        assert len(r["rows"]) == 2

    def test_list_parcels_with_search(self, conn, env):
        self._add_parcel(conn, env, "Alpha Field")
        self._add_parcel(conn, env, "Beta Field")
        r = call_action(_actions()["agri-list-parcels"], conn, ns(
            company_id=env["company_id"],
            parcel_status=None, search="Alpha",
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Soil Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSoilTests:
    def _add_parcel(self, conn, env):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"], name="Soil Test Field",
            acreage="40", gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_ok(r)
        return r["id"]

    def test_add_soil_test(self, conn, env):
        pid = self._add_parcel(conn, env)
        r = call_action(_actions()["agri-add-soil-test"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            test_date="2026-03-01",
            ph="6.8", nitrogen="45", phosphorus="30", potassium="150",
            organic_matter="3.2", lab_name="AgLab Inc",
            notes="Annual test",
        ))
        assert is_ok(r)
        assert r["parcel_id"] == pid

    def test_add_soil_test_missing_parcel(self, conn, env):
        r = call_action(_actions()["agri-add-soil-test"], conn, ns(
            company_id=env["company_id"], parcel_id=None,
            test_date=None, ph=None, nitrogen=None, phosphorus=None,
            potassium=None, organic_matter=None, lab_name=None, notes=None,
        ))
        assert is_error(r)

    def test_list_soil_tests(self, conn, env):
        pid = self._add_parcel(conn, env)
        call_action(_actions()["agri-add-soil-test"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            test_date="2026-01-01", ph="6.5", nitrogen=None,
            phosphorus=None, potassium=None, organic_matter=None,
            lab_name=None, notes=None,
        ))
        call_action(_actions()["agri-add-soil-test"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            test_date="2026-06-01", ph="7.0", nitrogen=None,
            phosphorus=None, potassium=None, organic_matter=None,
            lab_name=None, notes=None,
        ))
        r = call_action(_actions()["agri-list-soil-tests"], conn, ns(
            parcel_id=pid, company_id=env["company_id"],
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Land Use Records
# ═══════════════════════════════════════════════════════════════════════════════

class TestLandUseRecords:
    def _add_parcel(self, conn, env):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"], name="LUR Field",
            acreage="60", gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_ok(r)
        return r["id"]

    def test_add_land_use_record(self, conn, env):
        pid = self._add_parcel(conn, env)
        r = call_action(_actions()["agri-add-land-use-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            season="spring", year=2026, crop_type="corn",
            notes="First planting",
        ))
        assert is_ok(r)
        assert r["parcel_id"] == pid

    def test_list_land_use_records(self, conn, env):
        pid = self._add_parcel(conn, env)
        call_action(_actions()["agri-add-land-use-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            season="spring", year=2025, crop_type="soybeans", notes=None,
        ))
        call_action(_actions()["agri-add-land-use-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            season="spring", year=2026, crop_type="corn", notes=None,
        ))
        r = call_action(_actions()["agri-list-land-use-records"], conn, ns(
            parcel_id=pid, company_id=env["company_id"],
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Parcel Summary & Land Utilization Report
# ═══════════════════════════════════════════════════════════════════════════════

class TestParcelReports:
    def _add_parcel(self, conn, env, name="Report Field", acreage="100"):
        r = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"], name=name,
            acreage=acreage, gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_ok(r)
        return r["id"]

    def test_parcel_summary(self, conn, env):
        pid = self._add_parcel(conn, env)
        r = call_action(_actions()["agri-parcel-summary"], conn, ns(id=pid))
        assert is_ok(r)
        assert r["id"] == pid
        assert "soil_test_count" in r
        assert "land_use_record_count" in r
        assert "field_operation_count" in r
        assert "harvest_record_count" in r

    def test_land_utilization_report(self, conn, env):
        self._add_parcel(conn, env, "Crop1", "100")
        self._add_parcel(conn, env, "Crop2", "200")
        r = call_action(_actions()["agri-land-utilization-report"], conn, ns(
            company_id=env["company_id"],
        ))
        assert is_ok(r)
        assert r["total_parcels"] == 2
        assert "acreage_by_land_use" in r
        assert r["acreage_by_land_use"]["cropland"] == "300"


# ═══════════════════════════════════════════════════════════════════════════════
# Crop Types
# ═══════════════════════════════════════════════════════════════════════════════

class TestCropTypes:
    def test_add_crop_type(self, conn, env):
        r = call_action(_actions()["agri-add-crop-type"], conn, ns(
            company_id=env["company_id"],
            name="Corn",
            variety="Dent",
            growing_season="spring",
            days_to_maturity=120,
        ))
        assert is_ok(r)
        assert r["name"] == "Corn"

    def test_add_crop_type_missing_name(self, conn, env):
        r = call_action(_actions()["agri-add-crop-type"], conn, ns(
            company_id=env["company_id"],
            name=None, variety=None, growing_season=None,
            days_to_maturity=None,
        ))
        assert is_error(r)

    def test_list_crop_types(self, conn, env):
        call_action(_actions()["agri-add-crop-type"], conn, ns(
            company_id=env["company_id"],
            name="Wheat", variety=None, growing_season=None,
            days_to_maturity=None,
        ))
        call_action(_actions()["agri-add-crop-type"], conn, ns(
            company_id=env["company_id"],
            name="Soybeans", variety=None, growing_season=None,
            days_to_maturity=None,
        ))
        r = call_action(_actions()["agri-list-crop-types"], conn, ns(
            company_id=env["company_id"], search=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2

    def test_list_crop_types_search(self, conn, env):
        call_action(_actions()["agri-add-crop-type"], conn, ns(
            company_id=env["company_id"],
            name="Corn", variety="Sweet", growing_season=None,
            days_to_maturity=None,
        ))
        call_action(_actions()["agri-add-crop-type"], conn, ns(
            company_id=env["company_id"],
            name="Wheat", variety=None, growing_season=None,
            days_to_maturity=None,
        ))
        r = call_action(_actions()["agri-list-crop-types"], conn, ns(
            company_id=env["company_id"], search="Corn",
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Planting Plans
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlantingPlans:
    def _setup(self, conn, env):
        pr = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"], name="PP Field",
            acreage="80", gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        assert is_ok(pr)
        cr = call_action(_actions()["agri-add-crop-type"], conn, ns(
            company_id=env["company_id"],
            name="Corn", variety=None, growing_season=None,
            days_to_maturity=None,
        ))
        assert is_ok(cr)
        return pr["id"], cr["id"]

    def test_add_planting_plan(self, conn, env):
        parcel_id, crop_type_id = self._setup(conn, env)
        r = call_action(_actions()["agri-add-planting-plan"], conn, ns(
            company_id=env["company_id"],
            parcel_id=parcel_id, crop_type_id=crop_type_id,
            season="spring", year=2026,
            planned_acres="80", seed_lot_id=None,
            planting_date="2026-04-15",
            expected_harvest_date="2026-10-01",
        ))
        assert is_ok(r)
        assert r["plan_status"] == "planned"
        assert r["naming_series"] is not None

    def test_add_planting_plan_missing_parcel(self, conn, env):
        _, crop_type_id = self._setup(conn, env)
        r = call_action(_actions()["agri-add-planting-plan"], conn, ns(
            company_id=env["company_id"],
            parcel_id=None, crop_type_id=crop_type_id,
            season=None, year=None, planned_acres=None, seed_lot_id=None,
            planting_date=None, expected_harvest_date=None,
        ))
        assert is_error(r)

    def test_update_planting_plan(self, conn, env):
        parcel_id, crop_type_id = self._setup(conn, env)
        add_r = call_action(_actions()["agri-add-planting-plan"], conn, ns(
            company_id=env["company_id"],
            parcel_id=parcel_id, crop_type_id=crop_type_id,
            season="spring", year=2026,
            planned_acres="80", seed_lot_id=None,
            planting_date="2026-04-15",
            expected_harvest_date="2026-10-01",
        ))
        pp_id = add_r["id"]
        r = call_action(_actions()["agri-update-planting-plan"], conn, ns(
            id=pp_id,
            season=None, year=None, planned_acres="75",
            seed_lot_id=None, planting_date=None,
            expected_harvest_date=None, plan_status=None,
        ))
        assert is_ok(r)
        assert "planned_acres" in r["updated_fields"]

    def test_get_planting_plan(self, conn, env):
        parcel_id, crop_type_id = self._setup(conn, env)
        add_r = call_action(_actions()["agri-add-planting-plan"], conn, ns(
            company_id=env["company_id"],
            parcel_id=parcel_id, crop_type_id=crop_type_id,
            season="spring", year=2026,
            planned_acres="80", seed_lot_id=None,
            planting_date=None, expected_harvest_date=None,
        ))
        pp_id = add_r["id"]
        r = call_action(_actions()["agri-get-planting-plan"], conn, ns(id=pp_id))
        assert is_ok(r)
        assert r["id"] == pp_id
        assert "growth_stages" in r
        assert r["stage_count"] == 0

    def test_list_planting_plans(self, conn, env):
        parcel_id, crop_type_id = self._setup(conn, env)
        call_action(_actions()["agri-add-planting-plan"], conn, ns(
            company_id=env["company_id"],
            parcel_id=parcel_id, crop_type_id=crop_type_id,
            season="spring", year=2026,
            planned_acres="80", seed_lot_id=None,
            planting_date=None, expected_harvest_date=None,
        ))
        r = call_action(_actions()["agri-list-planting-plans"], conn, ns(
            company_id=env["company_id"],
            parcel_id=None, plan_status=None, season=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Growth Stages
# ═══════════════════════════════════════════════════════════════════════════════

class TestGrowthStages:
    def _setup(self, conn, env):
        pr = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"], name="GS Field",
            acreage="40", gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        cr = call_action(_actions()["agri-add-crop-type"], conn, ns(
            company_id=env["company_id"],
            name="Corn", variety=None, growing_season=None,
            days_to_maturity=None,
        ))
        pp = call_action(_actions()["agri-add-planting-plan"], conn, ns(
            company_id=env["company_id"],
            parcel_id=pr["id"], crop_type_id=cr["id"],
            season="spring", year=2026,
            planned_acres="40", seed_lot_id=None,
            planting_date=None, expected_harvest_date=None,
        ))
        return pp["id"]

    def test_add_growth_stage(self, conn, env):
        pp_id = self._setup(conn, env)
        r = call_action(_actions()["agri-add-growth-stage"], conn, ns(
            company_id=env["company_id"],
            planting_plan_id=pp_id,
            stage_name="emergence",
            observed_date="2026-04-25",
            notes="Good stand",
        ))
        assert is_ok(r)
        assert r["stage_name"] == "emergence"

    def test_add_growth_stage_missing_name(self, conn, env):
        pp_id = self._setup(conn, env)
        r = call_action(_actions()["agri-add-growth-stage"], conn, ns(
            company_id=env["company_id"],
            planting_plan_id=pp_id,
            stage_name=None,
            observed_date=None, notes=None,
        ))
        assert is_error(r)

    def test_advance_growth_stage(self, conn, env):
        pp_id = self._setup(conn, env)
        # Add a growth stage first
        call_action(_actions()["agri-add-growth-stage"], conn, ns(
            company_id=env["company_id"],
            planting_plan_id=pp_id,
            stage_name="emergence",
            observed_date="2026-04-25", notes=None,
        ))
        r = call_action(_actions()["agri-advance-growth-stage"], conn, ns(id=pp_id))
        assert is_ok(r)
        assert r["plan_status"] == "active"
        assert r["stage_count"] >= 1

    def test_advance_growth_stage_no_stages(self, conn, env):
        pp_id = self._setup(conn, env)
        r = call_action(_actions()["agri-advance-growth-stage"], conn, ns(id=pp_id))
        assert is_error(r)

    def test_list_growth_stages(self, conn, env):
        pp_id = self._setup(conn, env)
        call_action(_actions()["agri-add-growth-stage"], conn, ns(
            company_id=env["company_id"],
            planting_plan_id=pp_id,
            stage_name="emergence",
            observed_date="2026-04-25", notes=None,
        ))
        call_action(_actions()["agri-add-growth-stage"], conn, ns(
            company_id=env["company_id"],
            planting_plan_id=pp_id,
            stage_name="V6",
            observed_date="2026-05-20", notes=None,
        ))
        r = call_action(_actions()["agri-list-growth-stages"], conn, ns(
            planting_plan_id=pp_id,
            company_id=env["company_id"],
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Seed Lots
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeedLots:
    def _add_crop_type(self, conn, env):
        r = call_action(_actions()["agri-add-crop-type"], conn, ns(
            company_id=env["company_id"],
            name="Soybeans", variety="Roundup Ready",
            growing_season="spring", days_to_maturity=100,
        ))
        assert is_ok(r)
        return r["id"]

    def test_add_seed_lot(self, conn, env):
        ct_id = self._add_crop_type(conn, env)
        r = call_action(_actions()["agri-add-seed-lot"], conn, ns(
            company_id=env["company_id"],
            crop_type_id=ct_id,
            lot_number="SL-2026-001",
            quantity="5000",
            unit="lbs",
            supplier="SeedCorp",
            purchase_date="2026-02-01",
            expiry_date="2027-02-01",
        ))
        assert is_ok(r)
        assert r["crop_type_id"] == ct_id

    def test_list_seed_lots(self, conn, env):
        ct_id = self._add_crop_type(conn, env)
        call_action(_actions()["agri-add-seed-lot"], conn, ns(
            company_id=env["company_id"], crop_type_id=ct_id,
            lot_number="SL-001", quantity="1000", unit="lbs",
            supplier=None, purchase_date=None, expiry_date=None,
        ))
        r = call_action(_actions()["agri-list-seed-lots"], conn, ns(
            company_id=env["company_id"], crop_type_id=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Crop Rotation Report
# ═══════════════════════════════════════════════════════════════════════════════

class TestCropRotationReport:
    def test_crop_rotation_report(self, conn, env):
        pr = call_action(_actions()["agri-add-parcel"], conn, ns(
            company_id=env["company_id"], name="Rotation Field",
            acreage="80", gps_lat=None, gps_lon=None, soil_type=None,
            land_use=None, owner=None, lease_info=None, parcel_status=None,
        ))
        pid = pr["id"]
        call_action(_actions()["agri-add-land-use-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            season="spring", year=2024, crop_type="corn", notes=None,
        ))
        call_action(_actions()["agri-add-land-use-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            season="spring", year=2025, crop_type="soybeans", notes=None,
        ))
        call_action(_actions()["agri-add-land-use-record"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
            season="spring", year=2026, crop_type="corn", notes=None,
        ))
        r = call_action(_actions()["agri-crop-rotation-report"], conn, ns(
            company_id=env["company_id"], parcel_id=pid,
        ))
        assert is_ok(r)
        assert r["total_count"] == 3

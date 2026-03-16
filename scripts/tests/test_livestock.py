"""L1 tests for AgricultureClaw -- Livestock management domain.

Covers:
  - Animals: add, update, get, list
  - Health records: add, list
  - Feeding records: add, list
  - Weight records: add (also updates animal current_weight)
  - Herd summary report
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


def _add_animal(conn, env, species="cattle", tag="T-001"):
    r = call_action(_actions()["agri-add-animal"], conn, ns(
        company_id=env["company_id"],
        species=species,
        tag_number=tag,
        breed="Angus",
        birth_date="2024-03-15",
        gender="female",
        sire_id=None, dam_id=None,
        purchase_date=None, purchase_cost=None,
        current_weight="1000",
        animal_status=None,
    ))
    assert is_ok(r), r
    return r["id"]


# ═══════════════════════════════════════════════════════════════════════════════
# Animals
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimals:
    def test_add_animal(self, conn, env):
        r = call_action(_actions()["agri-add-animal"], conn, ns(
            company_id=env["company_id"],
            species="cattle",
            tag_number="TAG-001",
            breed="Hereford",
            birth_date="2024-01-10",
            gender="male",
            sire_id=None, dam_id=None,
            purchase_date="2024-06-01",
            purchase_cost="2500.00",
            current_weight="850",
            animal_status=None,
        ))
        assert is_ok(r)
        assert r["species"] == "cattle"
        assert r["animal_status"] == "active"
        assert r["naming_series"] is not None

    def test_add_animal_missing_species(self, conn, env):
        r = call_action(_actions()["agri-add-animal"], conn, ns(
            company_id=env["company_id"],
            species=None,
            tag_number=None, breed=None, birth_date=None,
            gender=None, sire_id=None, dam_id=None,
            purchase_date=None, purchase_cost=None,
            current_weight=None, animal_status=None,
        ))
        assert is_error(r)

    def test_add_animal_invalid_species(self, conn, env):
        r = call_action(_actions()["agri-add-animal"], conn, ns(
            company_id=env["company_id"],
            species="unicorn",
            tag_number=None, breed=None, birth_date=None,
            gender=None, sire_id=None, dam_id=None,
            purchase_date=None, purchase_cost=None,
            current_weight=None, animal_status=None,
        ))
        assert is_error(r)

    def test_add_animal_invalid_gender(self, conn, env):
        r = call_action(_actions()["agri-add-animal"], conn, ns(
            company_id=env["company_id"],
            species="cattle",
            tag_number=None, breed=None, birth_date=None,
            gender="unknown",
            sire_id=None, dam_id=None,
            purchase_date=None, purchase_cost=None,
            current_weight=None, animal_status=None,
        ))
        assert is_error(r)

    def test_add_animal_swine(self, conn, env):
        r = call_action(_actions()["agri-add-animal"], conn, ns(
            company_id=env["company_id"],
            species="swine",
            tag_number="PIG-001",
            breed="Duroc",
            birth_date="2025-06-01",
            gender="female",
            sire_id=None, dam_id=None,
            purchase_date=None, purchase_cost=None,
            current_weight="300",
            animal_status=None,
        ))
        assert is_ok(r)
        assert r["species"] == "swine"

    def test_update_animal(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-update-animal"], conn, ns(
            id=aid,
            tag_number="T-002",
            breed=None, birth_date=None,
            gender=None, purchase_date=None,
            purchase_cost=None, current_weight="1050",
            animal_status=None,
        ))
        assert is_ok(r)
        assert "tag_number" in r["updated_fields"]
        assert "current_weight" in r["updated_fields"]

    def test_update_animal_status(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-update-animal"], conn, ns(
            id=aid,
            tag_number=None, breed=None, birth_date=None,
            gender=None, purchase_date=None, purchase_cost=None,
            current_weight=None,
            animal_status="sold",
        ))
        assert is_ok(r)
        assert "animal_status" in r["updated_fields"]

    def test_update_animal_no_fields(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-update-animal"], conn, ns(
            id=aid,
            tag_number=None, breed=None, birth_date=None,
            gender=None, purchase_date=None, purchase_cost=None,
            current_weight=None, animal_status=None,
        ))
        assert is_error(r)

    def test_get_animal(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-get-animal"], conn, ns(id=aid))
        assert is_ok(r)
        assert r["id"] == aid
        assert "health_records" in r
        assert "weight_records" in r

    def test_get_animal_not_found(self, conn, env):
        r = call_action(_actions()["agri-get-animal"], conn, ns(id="nonexistent"))
        assert is_error(r)

    def test_list_animals(self, conn, env):
        _add_animal(conn, env, "cattle", "C-001")
        _add_animal(conn, env, "swine", "S-001")
        r = call_action(_actions()["agri-list-animals"], conn, ns(
            company_id=env["company_id"],
            species=None, animal_status=None, search=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2

    def test_list_animals_filter_species(self, conn, env):
        _add_animal(conn, env, "cattle", "C-001")
        _add_animal(conn, env, "swine", "S-001")
        r = call_action(_actions()["agri-list-animals"], conn, ns(
            company_id=env["company_id"],
            species="cattle", animal_status=None, search=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1

    def test_list_animals_search(self, conn, env):
        _add_animal(conn, env, "cattle", "XRAY-001")
        _add_animal(conn, env, "cattle", "ZULU-001")
        r = call_action(_actions()["agri-list-animals"], conn, ns(
            company_id=env["company_id"],
            species=None, animal_status=None, search="XRAY",
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Health Records
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthRecords:
    def test_add_health_record(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-add-health-record"], conn, ns(
            company_id=env["company_id"],
            animal_id=aid,
            record_date="2026-03-01",
            record_type="vaccination",
            description="Brucellosis vaccine",
            veterinarian="Dr. Smith",
            cost="75.00",
        ))
        assert is_ok(r)
        assert r["record_type"] == "vaccination"

    def test_add_health_record_missing_type(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-add-health-record"], conn, ns(
            company_id=env["company_id"],
            animal_id=aid,
            record_date=None, record_type=None,
            description=None, veterinarian=None, cost=None,
        ))
        assert is_error(r)

    def test_add_health_record_invalid_type(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-add-health-record"], conn, ns(
            company_id=env["company_id"],
            animal_id=aid,
            record_date=None,
            record_type="surgery",
            description=None, veterinarian=None, cost=None,
        ))
        assert is_error(r)

    def test_list_health_records(self, conn, env):
        aid = _add_animal(conn, env)
        call_action(_actions()["agri-add-health-record"], conn, ns(
            company_id=env["company_id"], animal_id=aid,
            record_date="2026-01-01", record_type="vaccination",
            description=None, veterinarian=None, cost=None,
        ))
        call_action(_actions()["agri-add-health-record"], conn, ns(
            company_id=env["company_id"], animal_id=aid,
            record_date="2026-03-01", record_type="deworming",
            description=None, veterinarian=None, cost=None,
        ))
        r = call_action(_actions()["agri-list-health-records"], conn, ns(
            animal_id=aid, company_id=env["company_id"],
            record_type=None,
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2

    def test_list_health_records_filter_type(self, conn, env):
        aid = _add_animal(conn, env)
        call_action(_actions()["agri-add-health-record"], conn, ns(
            company_id=env["company_id"], animal_id=aid,
            record_date="2026-01-01", record_type="vaccination",
            description=None, veterinarian=None, cost=None,
        ))
        call_action(_actions()["agri-add-health-record"], conn, ns(
            company_id=env["company_id"], animal_id=aid,
            record_date="2026-03-01", record_type="treatment",
            description=None, veterinarian=None, cost=None,
        ))
        r = call_action(_actions()["agri-list-health-records"], conn, ns(
            animal_id=aid, company_id=env["company_id"],
            record_type="vaccination",
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Feeding Records
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedingRecords:
    def test_add_feeding_record(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-add-feeding-record"], conn, ns(
            company_id=env["company_id"],
            animal_id=aid,
            feed_date="2026-03-01",
            feed_type="grain",
            quantity="50",
            unit="lbs",
            cost="25.00",
        ))
        assert is_ok(r)
        assert r["animal_id"] == aid

    def test_list_feeding_records(self, conn, env):
        aid = _add_animal(conn, env)
        call_action(_actions()["agri-add-feeding-record"], conn, ns(
            company_id=env["company_id"], animal_id=aid,
            feed_date="2026-03-01", feed_type="grain",
            quantity="50", unit="lbs", cost=None,
        ))
        call_action(_actions()["agri-add-feeding-record"], conn, ns(
            company_id=env["company_id"], animal_id=aid,
            feed_date="2026-03-02", feed_type="hay",
            quantity="20", unit="lbs", cost=None,
        ))
        r = call_action(_actions()["agri-list-feeding-records"], conn, ns(
            animal_id=aid, company_id=env["company_id"],
            limit=20, offset=0,
        ))
        assert is_ok(r)
        assert r["total_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Weight Records
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightRecords:
    def test_add_weight_record(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-add-weight-record"], conn, ns(
            company_id=env["company_id"],
            animal_id=aid,
            weigh_date="2026-03-01",
            weight="1050",
            unit="lbs",
            notes="Monthly weigh-in",
        ))
        assert is_ok(r)
        assert r["weight"] == "1050"

        # Verify current_weight was updated on the animal
        get_r = call_action(_actions()["agri-get-animal"], conn, ns(id=aid))
        assert is_ok(get_r)
        assert get_r["current_weight"] == "1050"

    def test_add_weight_record_missing_weight(self, conn, env):
        aid = _add_animal(conn, env)
        r = call_action(_actions()["agri-add-weight-record"], conn, ns(
            company_id=env["company_id"],
            animal_id=aid,
            weigh_date=None,
            weight=None,
            unit=None, notes=None,
        ))
        assert is_error(r)


# ═══════════════════════════════════════════════════════════════════════════════
# Herd Summary Report
# ═══════════════════════════════════════════════════════════════════════════════

class TestHerdSummaryReport:
    def test_herd_summary(self, conn, env):
        _add_animal(conn, env, "cattle", "C-001")
        _add_animal(conn, env, "cattle", "C-002")
        _add_animal(conn, env, "swine", "S-001")
        r = call_action(_actions()["agri-herd-summary-report"], conn, ns(
            company_id=env["company_id"],
        ))
        assert is_ok(r)
        assert r["total_animals"] == 3
        assert r["active_animals"] == 3
        assert len(r["by_species_status"]) >= 2

    def test_herd_summary_with_health_records(self, conn, env):
        aid = _add_animal(conn, env)
        call_action(_actions()["agri-add-health-record"], conn, ns(
            company_id=env["company_id"], animal_id=aid,
            record_date="2026-01-01", record_type="vaccination",
            description=None, veterinarian=None, cost=None,
        ))
        r = call_action(_actions()["agri-herd-summary-report"], conn, ns(
            company_id=env["company_id"],
        ))
        assert is_ok(r)
        assert r["total_health_records"] == 1

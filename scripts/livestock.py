"""AgricultureClaw -- Livestock management domain module.

Actions for animals, health records, feeding records, and weight records (4 tables, 10 actions).
Imported by db_query.py (unified router).
"""
import os
import sys
import uuid
from datetime import datetime, timezone

try:
    import importlib.util
    if importlib.util.find_spec("erpclaw_lib") is None:
        sys.path.insert(0, os.path.join(os.path.expanduser(os.environ.get("ERPCLAW_HOME", "~/.openclaw/erpclaw")), "lib"))
    from erpclaw_lib.naming import get_next_name, ENTITY_PREFIXES
    from erpclaw_lib.response import ok, err, row_to_dict
    from erpclaw_lib.audit import audit
    from erpclaw_lib.query import Q, P, Table, Field, fn, Order, LiteralValue, insert_row, update_row, dynamic_update

    ENTITY_PREFIXES.setdefault("animal", "ANM-")
except ImportError:
    pass

SKILL = "agricultureclaw"

_now_iso = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_SPECIES = ("cattle", "swine", "poultry", "sheep", "goat", "other")
VALID_GENDERS = ("male", "female")
VALID_ANIMAL_STATUS = ("active", "sold", "deceased", "transferred")
VALID_HEALTH_TYPES = ("vaccination", "treatment", "examination", "deworming")


def _validate_company(conn, company_id):
    if not company_id:
        err("--company-id is required")
    if not conn.execute(Q.from_(Table("company")).select(Field("id")).where(Field("id") == P()).get_sql(), (company_id,)).fetchone():
        err(f"Company {company_id} not found")


def _validate_animal(conn, animal_id):
    if not animal_id:
        err("--animal-id is required")
    if not conn.execute(Q.from_(Table("agricultureclaw_animal")).select(Field("id")).where(Field("id") == P()).get_sql(), (animal_id,)).fetchone():
        err(f"Animal {animal_id} not found")


# ===========================================================================
# 1. add-animal
# ===========================================================================
def add_animal(conn, args):
    _validate_company(conn, args.company_id)

    species = getattr(args, "species", None)
    if not species:
        err("--species is required")
    if species not in VALID_SPECIES:
        err(f"Invalid species: {species}. Must be one of: {', '.join(VALID_SPECIES)}")

    gender = getattr(args, "gender", None)
    if gender and gender not in VALID_GENDERS:
        err(f"Invalid gender: {gender}. Must be one of: {', '.join(VALID_GENDERS)}")

    animal_id = str(uuid.uuid4())
    conn.company_id = args.company_id
    naming = get_next_name(conn, "animal", company_id=args.company_id)
    now = _now_iso()

    sql, _ = insert_row("agricultureclaw_animal", {"id": P(), "naming_series": P(), "tag_number": P(), "species": P(), "breed": P(), "birth_date": P(), "gender": P(), "sire_id": P(), "dam_id": P(), "purchase_date": P(), "purchase_cost": P(), "current_weight": P(), "animal_status": P(), "company_id": P(), "created_at": P(), "updated_at": P()})
    conn.execute(sql, (
        animal_id, naming,
        getattr(args, "tag_number", None),
        species,
        getattr(args, "breed", None),
        getattr(args, "birth_date", None),
        gender,
        getattr(args, "sire_id", None),
        getattr(args, "dam_id", None),
        getattr(args, "purchase_date", None),
        getattr(args, "purchase_cost", None),
        getattr(args, "current_weight", None),
        "active",
        args.company_id, now, now,
    ))
    audit(conn, SKILL, "agri-add-animal", "agricultureclaw_animal", animal_id,
          new_values={"species": species, "tag_number": getattr(args, "tag_number", None)})
    conn.commit()
    ok({"id": animal_id, "naming_series": naming, "species": species, "animal_status": "active"})


# ===========================================================================
# 2. update-animal
# ===========================================================================
def update_animal(conn, args):
    animal_id = getattr(args, "id", None)
    if not animal_id:
        err("--id is required")
    if not conn.execute(Q.from_(Table("agricultureclaw_animal")).select(Field("id")).where(Field("id") == P()).get_sql(), (animal_id,)).fetchone():
        err(f"Animal {animal_id} not found")

    data, changed = {}, []
    for arg_name, col_name in {
        "tag_number": "tag_number", "breed": "breed", "birth_date": "birth_date",
        "purchase_date": "purchase_date", "purchase_cost": "purchase_cost",
        "current_weight": "current_weight",
    }.items():
        val = getattr(args, arg_name, None)
        if val is not None:
            data[col_name] = val
            changed.append(col_name)

    gender = getattr(args, "gender", None)
    if gender is not None:
        if gender not in VALID_GENDERS:
            err(f"Invalid gender: {gender}. Must be one of: {', '.join(VALID_GENDERS)}")
        data["gender"] = gender
        changed.append("gender")

    animal_status = getattr(args, "animal_status", None)
    if animal_status is not None:
        if animal_status not in VALID_ANIMAL_STATUS:
            err(f"Invalid animal-status: {animal_status}. Must be one of: {', '.join(VALID_ANIMAL_STATUS)}")
        data["animal_status"] = animal_status
        changed.append("animal_status")

    if not data:
        err("No fields to update")

    data["updated_at"] = _now_iso()
    sql, params = dynamic_update("agricultureclaw_animal", data, where={"id": animal_id})
    conn.execute(sql, params)
    audit(conn, SKILL, "agri-update-animal", "agricultureclaw_animal", animal_id,
          new_values={"updated_fields": changed})
    conn.commit()
    ok({"id": animal_id, "updated_fields": changed})


# ===========================================================================
# 3. get-animal
# ===========================================================================
def get_animal(conn, args):
    animal_id = getattr(args, "id", None)
    if not animal_id:
        err("--id is required")
    row = conn.execute(Q.from_(Table("agricultureclaw_animal")).select(Table("agricultureclaw_animal").star).where(Field("id") == P()).get_sql(), (animal_id,)).fetchone()
    if not row:
        err(f"Animal {animal_id} not found")
    data = row_to_dict(row)

    # Include health records
    health = conn.execute(Q.from_(Table("agricultureclaw_health_record")).select(Table("agricultureclaw_health_record").star).where(Field("animal_id") == P()).orderby(Field("record_date"), order=Order.desc).get_sql(), (animal_id,)).fetchall()
    data["health_records"] = [row_to_dict(h) for h in health]

    # Include weight records
    weights = conn.execute(Q.from_(Table("agricultureclaw_weight_record")).select(Table("agricultureclaw_weight_record").star).where(Field("animal_id") == P()).orderby(Field("weigh_date"), order=Order.desc).get_sql(), (animal_id,)).fetchall()
    data["weight_records"] = [row_to_dict(w) for w in weights]
    ok(data)


# ===========================================================================
# 4. list-animals
# ===========================================================================
def list_animals(conn, args):
    t = Table("agricultureclaw_animal")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)
    if getattr(args, "species", None):
        q = q.where(t.species == P())
        qc = qc.where(t.species == P())
        params.append(args.species)
    if getattr(args, "animal_status", None):
        q = q.where(t.animal_status == P())
        qc = qc.where(t.animal_status == P())
        params.append(args.animal_status)
    if getattr(args, "search", None):
        q = q.where((t.tag_number.like(P())) | (t.breed.like(P())))
        qc = qc.where((t.tag_number.like(P())) | (t.breed.like(P())))
        params.extend([f"%{args.search}%", f"%{args.search}%"])

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.created_at, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 5. add-health-record
# ===========================================================================
def add_health_record(conn, args):
    _validate_company(conn, args.company_id)
    animal_id = getattr(args, "animal_id", None)
    _validate_animal(conn, animal_id)

    record_type = getattr(args, "record_type", None)
    if not record_type:
        err("--record-type is required")
    if record_type not in VALID_HEALTH_TYPES:
        err(f"Invalid record-type: {record_type}. Must be one of: {', '.join(VALID_HEALTH_TYPES)}")

    hr_id = str(uuid.uuid4())
    sql, _ = insert_row("agricultureclaw_health_record", {"id": P(), "animal_id": P(), "record_date": P(), "record_type": P(), "description": P(), "veterinarian": P(), "cost": P(), "company_id": P()})
    conn.execute(sql, (
        hr_id, animal_id,
        getattr(args, "record_date", None),
        record_type,
        getattr(args, "description", None),
        getattr(args, "veterinarian", None),
        getattr(args, "cost", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-health-record", "agricultureclaw_health_record", hr_id,
          new_values={"animal_id": animal_id, "record_type": record_type})
    conn.commit()
    ok({"id": hr_id, "animal_id": animal_id, "record_type": record_type})


# ===========================================================================
# 6. list-health-records
# ===========================================================================
def list_health_records(conn, args):
    t = Table("agricultureclaw_health_record")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "animal_id", None):
        q = q.where(t.animal_id == P())
        qc = qc.where(t.animal_id == P())
        params.append(args.animal_id)
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)
    if getattr(args, "record_type", None):
        q = q.where(t.record_type == P())
        qc = qc.where(t.record_type == P())
        params.append(args.record_type)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.record_date, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 7. add-feeding-record
# ===========================================================================
def add_feeding_record(conn, args):
    _validate_company(conn, args.company_id)
    animal_id = getattr(args, "animal_id", None)
    _validate_animal(conn, animal_id)

    fr_id = str(uuid.uuid4())
    sql, _ = insert_row("agricultureclaw_feeding_record", {"id": P(), "animal_id": P(), "feed_date": P(), "feed_type": P(), "quantity": P(), "unit": P(), "cost": P(), "company_id": P()})
    conn.execute(sql, (
        fr_id, animal_id,
        getattr(args, "feed_date", None),
        getattr(args, "feed_type", None),
        getattr(args, "quantity", None),
        getattr(args, "unit", None),
        getattr(args, "cost", None),
        args.company_id,
    ))
    audit(conn, SKILL, "agri-add-feeding-record", "agricultureclaw_feeding_record", fr_id,
          new_values={"animal_id": animal_id})
    conn.commit()
    ok({"id": fr_id, "animal_id": animal_id})


# ===========================================================================
# 8. list-feeding-records
# ===========================================================================
def list_feeding_records(conn, args):
    t = Table("agricultureclaw_feeding_record")
    q = Q.from_(t).select(t.star)
    qc = Q.from_(t).select(fn.Count("*"))
    params = []
    if getattr(args, "animal_id", None):
        q = q.where(t.animal_id == P())
        qc = qc.where(t.animal_id == P())
        params.append(args.animal_id)
    if getattr(args, "company_id", None):
        q = q.where(t.company_id == P())
        qc = qc.where(t.company_id == P())
        params.append(args.company_id)

    total = conn.execute(qc.get_sql(), params).fetchone()[0]
    q = q.orderby(t.feed_date, order=Order.desc).limit(P()).offset(P())
    rows = conn.execute(q.get_sql(), params + [args.limit, args.offset]).fetchall()
    ok({
        "rows": [row_to_dict(r) for r in rows],
        "total_count": total, "limit": args.limit, "offset": args.offset,
        "has_more": (args.offset + args.limit) < total,
    })


# ===========================================================================
# 9. add-weight-record
# ===========================================================================
def add_weight_record(conn, args):
    _validate_company(conn, args.company_id)
    animal_id = getattr(args, "animal_id", None)
    _validate_animal(conn, animal_id)

    weight = getattr(args, "weight", None)
    if not weight:
        err("--weight is required")

    wr_id = str(uuid.uuid4())
    sql, _ = insert_row("agricultureclaw_weight_record", {"id": P(), "animal_id": P(), "weigh_date": P(), "weight": P(), "unit": P(), "notes": P(), "company_id": P()})
    conn.execute(sql, (
        wr_id, animal_id,
        getattr(args, "weigh_date", None),
        weight,
        getattr(args, "unit", None) or "lbs",
        getattr(args, "notes", None),
        args.company_id,
    ))

    # Update current_weight on the animal
    sql_uw, uw_params = dynamic_update("agricultureclaw_animal", {
        "current_weight": weight,
        "updated_at": _now_iso(),
    }, where={"id": animal_id})
    conn.execute(sql_uw, uw_params)

    audit(conn, SKILL, "agri-add-weight-record", "agricultureclaw_weight_record", wr_id,
          new_values={"animal_id": animal_id, "weight": weight})
    conn.commit()
    ok({"id": wr_id, "animal_id": animal_id, "weight": weight})


# ===========================================================================
# 10. herd-summary-report
# ===========================================================================
def herd_summary_report(conn, args):
    where, params = ["1=1"], []
    if getattr(args, "company_id", None):
        where.append("company_id = ?")
        params.append(args.company_id)

    where_sql = " AND ".join(where)

    # Count by species
    by_species = conn.execute(f"""
        SELECT species, animal_status, COUNT(*) as cnt
        FROM agricultureclaw_animal WHERE {where_sql}
        GROUP BY species, animal_status
    """, params).fetchall()

    total_animals = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_animal WHERE {where_sql}", params
    ).fetchone()[0]

    active_animals = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_animal WHERE {where_sql} AND animal_status = 'active'", params
    ).fetchone()[0]

    total_health = conn.execute(
        f"SELECT COUNT(*) FROM agricultureclaw_health_record WHERE {where_sql}", params
    ).fetchone()[0]

    ok({
        "total_animals": total_animals,
        "active_animals": active_animals,
        "total_health_records": total_health,
        "by_species_status": [row_to_dict(r) for r in by_species],
    })


# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------
ACTIONS = {
    "agri-add-animal": add_animal,
    "agri-update-animal": update_animal,
    "agri-get-animal": get_animal,
    "agri-list-animals": list_animals,
    "agri-add-health-record": add_health_record,
    "agri-list-health-records": list_health_records,
    "agri-add-feeding-record": add_feeding_record,
    "agri-list-feeding-records": list_feeding_records,
    "agri-add-weight-record": add_weight_record,
    "agri-herd-summary-report": herd_summary_report,
}

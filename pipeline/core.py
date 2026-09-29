"""Atomic batch publication with explicit data contracts and retained evidence."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTRACT = ROOT / "contracts" / "claims-payments.v1.json"
COLUMNS = ["payment_id", "policy_id", "paid_date", "amount", "currency"]

def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def transformation_sha() -> str:
    paths = [Path(__file__), Path(__file__).with_name("schema.sql"), Path(__file__).with_name("metrics.sql")]
    return digest(b"\0".join(p.name.encode() + b"\0" + p.read_bytes() for p in paths))

def contract_load(path=DEFAULT_CONTRACT):
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"contract_version", "product", "owner_role", "steward_role", "classification",
                "columns", "currencies", "policy_ids", "max_amount_cents", "max_invalid_fraction"}
    if set(c) != required:
        raise ValueError("Contract fields differ from the supported contract schema")
    if c["contract_version"] != "1.0.0" or c["columns"] != COLUMNS:
        raise ValueError("Unsupported contract version or column definition")
    if c["classification"] != "synthetic-public":
        raise ValueError("Only synthetic-public contracts are supported")
    for key in ("product", "owner_role", "steward_role"):
        if not isinstance(c[key], str) or not c[key].strip():
            raise ValueError("Contract metadata must be nonempty")
    for key in ("currencies", "policy_ids"):
        if not isinstance(c[key], list) or not c[key] or any(not isinstance(v, str) for v in c[key]):
            raise ValueError("Contract controlled values must be nonempty string lists")
    if any(not re.fullmatch(r"[A-Z]{3}", v) for v in c["currencies"]):
        raise ValueError("Invalid currency definition")
    if any(not re.fullmatch(r"SYN-POL-[0-9]{3}", v) for v in c["policy_ids"]):
        raise ValueError("Reference policies must use synthetic IDs")
    if type(c["max_amount_cents"]) is not int or not 0 < c["max_amount_cents"] <= 100000000:
        raise ValueError("Invalid amount ceiling")
    if type(c["max_invalid_fraction"]) not in (int, float) or not 0 <= c["max_invalid_fraction"] < 1:
        raise ValueError("Invalid quality threshold")
    return c

def validate(row, c):
    reasons = []
    if not re.fullmatch(r"SYN-PAY-[0-9]{5}", row["payment_id"]):
        reasons.append("PAYMENT_ID_FORMAT")
    if row["policy_id"] not in c["policy_ids"]:
        reasons.append("UNKNOWN_POLICY")
    try:
        if date.fromisoformat(row["paid_date"]).isoformat() != row["paid_date"]:
            raise ValueError()
    except ValueError:
        reasons.append("INVALID_DATE")
    cents = None
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", row["amount"]) or len(row["amount"]) > 16:
        reasons.append("AMOUNT_FORMAT")
    else:
        cents = int(Decimal(row["amount"]) * 100)
        if not 0 < cents <= c["max_amount_cents"]:
            reasons.append("AMOUNT_RANGE")
    if row["currency"] not in c["currencies"]:
        reasons.append("CURRENCY_NOT_ALLOWED")
    normalized = {**row, "amount_cents": cents}
    normalized.pop("amount")
    return normalized, reasons

def connect(path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(p, isolation_level=None, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(Path(__file__).with_name("schema.sql").read_text())
    return db

def ingest(source, database, contract=DEFAULT_CONTRACT):
    source = Path(source)
    payload = source.read_bytes()
    if len(payload) > 10_000_000:
        raise ValueError("Demo input limit is 10 MB")
    c = contract_load(contract)
    cjson = canonical(c)
    csha = digest(cjson.encode())
    tsha = transformation_sha()
    ssha = digest(payload)
    batch_id = digest((ssha + csha + tsha).encode())
    structural = ""
    records = []
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader, [])
        if header != COLUMNS:
            raise ValueError("Header must exactly match the versioned contract")
        for index, values in enumerate(reader, start=2):
            if len(values) != len(COLUMNS):
                raise ValueError("CSV record has wrong field count")
            records.append((index, dict(zip(COLUMNS, values))))
        if not records:
            raise ValueError("Empty batches cannot be published")
        if len(records) > 10000:
            raise ValueError("Demo batch limit is 10000 records")
    except (UnicodeError, csv.Error, ValueError) as exc:
        structural = str(exc)
    with closing(connect(database)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            old = db.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
            if old:
                db.rollback()
                return {**summary(old), "replayed": True}
            items = []
            groups = defaultdict(set)
            if not structural:
                for rownum, raw in records:
                    normalized, reasons = validate(raw, c)
                    rsha = digest(canonical(normalized).encode())
                    items.append([rownum, raw, normalized, reasons, rsha])
                    groups[raw["payment_id"]].add(rsha)
                for item in items:
                    rownum, raw, normalized, reasons, rsha = item
                    if len(groups[raw["payment_id"]]) > 1:
                        reasons.append("CONFLICTING_ID_IN_BATCH")
                    existing = db.execute("SELECT record_sha FROM payments WHERE payment_id=?", (raw["payment_id"],)).fetchone()
                    if existing and existing["record_sha"] != rsha:
                        reasons.append("CONFLICTING_PUBLISHED_ID")
            invalid = sum(bool(i[3]) for i in items)
            status = "BLOCKED_SCHEMA" if structural else (
                "BLOCKED_QUALITY" if invalid / len(items) > c["max_invalid_fraction"] else "PUBLISHED")
            message = structural or ("Invalid fraction exceeds contract threshold" if status == "BLOCKED_QUALITY" else "Contract checks completed")
            db.execute("INSERT INTO batches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (batch_id, source.name, ssha, payload, csha, cjson, tsha,
                        datetime.now(timezone.utc).isoformat(), status, len(records), 0, 0, invalid, message))
            inserted = duplicates = 0
            for rownum, raw, normalized, reasons, rsha in items:
                if status != "PUBLISHED" or reasons:
                    why = reasons or ["BATCH_QUALITY_GATE"]
                    db.execute("INSERT INTO quarantine VALUES (?,?,?,?)",
                               (batch_id, rownum, canonical(raw), canonical(why)))
                    continue
                if db.execute("SELECT 1 FROM payments WHERE payment_id=?", (raw["payment_id"],)).fetchone():
                    outcome = "DUPLICATE"
                    duplicates += 1
                else:
                    db.execute("INSERT INTO payments VALUES (?,?,?,?,?,?,?,?)",
                               (normalized["payment_id"], normalized["policy_id"], normalized["paid_date"],
                                normalized["amount_cents"], normalized["currency"], rsha, batch_id, rownum))
                    inserted += 1
                    outcome = "INSERTED"
                db.execute("INSERT INTO observations VALUES (?,?,?,?)", (batch_id, rownum, raw["payment_id"], outcome))
            db.execute("UPDATE batches SET inserted_rows=?, duplicate_rows=? WHERE batch_id=?", (inserted, duplicates, batch_id))
            result = summary(db.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone())
            db.commit()
            return {**result, "replayed": False}
        except BaseException:
            db.rollback()
            raise

def summary(row):
    return {key: row[key] for key in (
        "batch_id", "source_name", "source_sha", "contract_sha", "transform_sha",
        "created_at", "status", "total_rows", "inserted_rows", "duplicate_rows", "invalid_rows", "message")}

def report(database):
    if not Path(database).exists():
        raise ValueError("Database does not exist; ingest data first")
    with closing(connect(database)) as db:
        db.execute("BEGIN")
        metrics = [dict(r) for r in db.execute(Path(__file__).with_name("metrics.sql").read_text())]
        batches = [summary(r) for r in db.execute("SELECT * FROM batches ORDER BY created_at,batch_id")]
        quarantine = [dict(r) for r in db.execute("SELECT * FROM quarantine ORDER BY batch_id,source_row")]
        for row in quarantine:
            row["raw"] = json.loads(row.pop("raw_json"))
            row["reasons"] = json.loads(row.pop("reasons_json"))
        return {"product": "synthetic-claims-payments", "metrics": metrics, "batches": batches, "quarantine": quarantine}

def trace(database, paid_date, currency):
    if not Path(database).exists():
        raise ValueError("Database does not exist; ingest data first")
    with closing(connect(database)) as db:
        db.execute("BEGIN")
        rows = db.execute("""SELECT p.*, b.source_name,b.source_sha,b.contract_sha,b.contract_json,b.transform_sha
            FROM payments p JOIN batches b ON p.batch_id=b.batch_id
            WHERE paid_date=? AND currency=? ORDER BY payment_id""", (paid_date, currency)).fetchall()
        return {"paid_date": paid_date, "currency": currency, "payment_count": len(rows),
                "total_amount_cents": sum(r["amount_cents"] for r in rows),
                "contributors": [dict(r) for r in rows]}

def generate(path):
    """Twelve deterministic synthetic records: ten valid, two deliberate exceptions."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        for i in range(1, 13):
            writer.writerow([f"SYN-PAY-{i:05}", f"SYN-POL-{(i-1)%3+1:03}", "2026-01-15",
                             "-10.00" if i == 11 else f"{i * 100}.00", "USD" if i == 12 else "EUR"])


"""UPI instant payment settlement engine - local demonstration API.

Accepts simulated UPI payments, keeps them in memory, and settles PENDING
payments in batches with per-bank net totals. It never talks to a real UPI
network, bank, or NPCI switch; all identifiers are generated locally.
"""
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Flask, jsonify, request

VPA_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{2,256}@[a-zA-Z]{2,64}$")
MAX_AMOUNT = Decimal("100000.00")  # standard UPI per-transaction limit (INR)
MIN_AMOUNT = Decimal("0.01")
PAISA = Decimal("0.01")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _money(value):
    return format(value.quantize(PAISA, rounding=ROUND_HALF_UP), "f")


class SettlementEngine:
    """Thread-safe in-memory ledger of payments and settlement batches."""

    def __init__(self):
        self._lock = threading.Lock()
        self._payments = {}
        self._idempotency = {}
        self._batches = []

    def create_payment(self, payer_vpa, payee_vpa, amount, note, idempotency_key=None):
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency:
                return self._payments[self._idempotency[idempotency_key]], False
            txn_id = "TXN" + uuid.uuid4().hex[:16].upper()
            payment = {
                "txn_id": txn_id,
                "utr": "DEMO" + uuid.uuid4().hex[:8].upper(),
                "payer_vpa": payer_vpa,
                "payee_vpa": payee_vpa,
                "payee_bank": payee_vpa.split("@", 1)[1].lower(),
                "amount": amount,
                "note": note,
                "status": "PENDING",
                "created_at": _now(),
                "settled_at": None,
                "batch_id": None,
            }
            self._payments[txn_id] = payment
            if idempotency_key:
                self._idempotency[idempotency_key] = txn_id
            return payment, True

    def list_payments(self, status=None):
        with self._lock:
            items = [p for p in self._payments.values() if status is None or p["status"] == status]
        return sorted(items, key=lambda p: p["created_at"], reverse=True)

    def get_payment(self, txn_id):
        with self._lock:
            return self._payments.get(txn_id)

    def run_settlement(self):
        """Settle every PENDING payment into one batch; returns None if nothing is pending."""
        with self._lock:
            pending = [p for p in self._payments.values() if p["status"] == "PENDING"]
            if not pending:
                return None
            batch_id = "BATCH" + str(len(self._batches) + 1).zfill(4)
            settled_at = _now()
            per_bank = {}
            for p in pending:
                bank = per_bank.setdefault(p["payee_bank"], {"count": 0, "amount": Decimal("0")})
                bank["count"] += 1
                bank["amount"] += p["amount"]
                p["status"] = "SETTLED"
                p["settled_at"] = settled_at
                p["batch_id"] = batch_id
            batch = {
                "batch_id": batch_id,
                "settled_at": settled_at,
                "payment_count": len(pending),
                "gross_amount": sum((p["amount"] for p in pending), Decimal("0")),
                "per_bank": per_bank,
            }
            self._batches.append(batch)
            return batch

    def list_batches(self):
        with self._lock:
            return list(reversed(self._batches))

    def stats(self):
        with self._lock:
            payments = list(self._payments.values())
            batch_count = len(self._batches)
        pending = [p for p in payments if p["status"] == "PENDING"]
        settled = [p for p in payments if p["status"] == "SETTLED"]
        return {
            "total_payments": len(payments),
            "pending_count": len(pending),
            "pending_amount": _money(sum((p["amount"] for p in pending), Decimal("0"))),
            "settled_count": len(settled),
            "settled_amount": _money(sum((p["amount"] for p in settled), Decimal("0"))),
            "batch_count": batch_count,
        }


def _payment_json(p):
    return {**p, "amount": _money(p["amount"])}


def _batch_json(b):
    return {
        **b,
        "gross_amount": _money(b["gross_amount"]),
        "per_bank": {
            bank: {"count": v["count"], "amount": _money(v["amount"])}
            for bank, v in sorted(b["per_bank"].items())
        },
    }


def _parse_amount(raw):
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None, "amount must be a number"
    if not amount.is_finite():
        return None, "amount must be a number"
    if amount != amount.quantize(PAISA):
        return None, "amount can have at most 2 decimal places"
    if amount < MIN_AMOUNT:
        return None, "amount must be at least 0.01"
    if amount > MAX_AMOUNT:
        return None, "amount exceeds the UPI per-transaction limit of 100000.00"
    return amount, None


def create_app(settlement_core=None):
    app = Flask(__name__)
    engine = SettlementEngine()
    core_state = (settlement_core or os.environ.get("SETTLEMENT_CORE", "ACTIVE")).upper()
    app.config["SETTLEMENT_CORE"] = core_state
    app.config["ENGINE"] = engine

    def core_active():
        return app.config["SETTLEMENT_CORE"] == "ACTIVE"

    def error(message, status):
        return jsonify({"error": message}), status

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "UP",
            "service": "upi-settlement-backend",
            "settlement_core": app.config["SETTLEMENT_CORE"],
            "time": _now(),
        })

    @app.post("/api/payments")
    def create_payment():
        if not core_active():
            return error("settlement core is not ACTIVE; payments are paused", 503)
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return error("request body must be a JSON object", 400)
        payer = str(body.get("payer_vpa", "")).strip()
        payee = str(body.get("payee_vpa", "")).strip()
        note = str(body.get("note", "")).strip()[:80]
        if not VPA_PATTERN.match(payer):
            return error("payer_vpa is not a valid UPI ID (name@bank)", 400)
        if not VPA_PATTERN.match(payee):
            return error("payee_vpa is not a valid UPI ID (name@bank)", 400)
        if payer.lower() == payee.lower():
            return error("payer and payee must be different", 400)
        amount, problem = _parse_amount(body.get("amount"))
        if problem:
            return error(problem, 400)
        key = request.headers.get("Idempotency-Key") or None
        payment, created = engine.create_payment(payer, payee, amount, note, key)
        return jsonify(_payment_json(payment)), 201 if created else 200

    @app.get("/api/payments")
    def list_payments():
        status = request.args.get("status")
        if status and status not in ("PENDING", "SETTLED"):
            return error("status must be PENDING or SETTLED", 400)
        return jsonify([_payment_json(p) for p in engine.list_payments(status)])

    @app.get("/api/payments/<txn_id>")
    def get_payment(txn_id):
        payment = engine.get_payment(txn_id)
        if payment is None:
            return error("payment not found", 404)
        return jsonify(_payment_json(payment))

    @app.post("/api/settlements/run")
    def run_settlement():
        if not core_active():
            return error("settlement core is not ACTIVE; settlement is paused", 503)
        batch = engine.run_settlement()
        if batch is None:
            return jsonify({"message": "no pending payments to settle"}), 200
        return jsonify(_batch_json(batch)), 201

    @app.get("/api/settlements")
    def list_settlements():
        return jsonify([_batch_json(b) for b in engine.list_batches()])

    @app.get("/api/stats")
    def stats():
        return jsonify(engine.stats())

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))

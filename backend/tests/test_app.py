import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402


@pytest.fixture
def client():
    return create_app(settlement_core="ACTIVE").test_client()


def pay(client, amount="250.00", payer="asha@okaxis", payee="merchant@ybl", **headers):
    return client.post(
        "/api/payments",
        json={"payer_vpa": payer, "payee_vpa": payee, "amount": amount, "note": "test"},
        headers=headers,
    )


def test_health_reports_active_core(client):
    body = client.get("/api/health").get_json()
    assert body["status"] == "UP"
    assert body["settlement_core"] == "ACTIVE"


def test_create_payment_is_pending(client):
    res = pay(client)
    assert res.status_code == 201
    body = res.get_json()
    assert body["status"] == "PENDING"
    assert body["amount"] == "250.00"
    assert body["payee_bank"] == "ybl"
    assert body["txn_id"].startswith("TXN")


@pytest.mark.parametrize("payer,payee", [
    ("no-at-sign", "merchant@ybl"),
    ("asha@okaxis", "merchant@"),
    ("asha@okaxis", "asha@okaxis"),
])
def test_rejects_invalid_vpas(client, payer, payee):
    assert pay(client, payer=payer, payee=payee).status_code == 400


@pytest.mark.parametrize("amount", ["0", "-5", "100000.01", "12.345", "abc", "NaN"])
def test_rejects_invalid_amounts(client, amount):
    assert pay(client, amount=amount).status_code == 400


def test_accepts_upi_limit_exactly(client):
    assert pay(client, amount="100000.00").status_code == 201


def test_idempotency_key_returns_same_payment(client):
    first = pay(client, **{"Idempotency-Key": "abc-1"})
    second = pay(client, **{"Idempotency-Key": "abc-1"})
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.get_json()["txn_id"] == second.get_json()["txn_id"]
    assert len(client.get("/api/payments").get_json()) == 1


def test_settlement_batches_pending_with_per_bank_totals(client):
    pay(client, amount="100.10", payee="shop@ybl")
    pay(client, amount="200.20", payee="cafe@ybl")
    pay(client, amount="50.00", payee="store@okhdfcbank")
    res = client.post("/api/settlements/run")
    assert res.status_code == 201
    batch = res.get_json()
    assert batch["batch_id"] == "BATCH0001"
    assert batch["payment_count"] == 3
    assert batch["gross_amount"] == "350.30"
    assert batch["per_bank"] == {
        "okhdfcbank": {"count": 1, "amount": "50.00"},
        "ybl": {"count": 2, "amount": "300.30"},
    }
    assert client.get("/api/payments?status=PENDING").get_json() == []
    assert len(client.get("/api/payments?status=SETTLED").get_json()) == 3


def test_settlement_with_nothing_pending(client):
    res = client.post("/api/settlements/run")
    assert res.status_code == 200
    assert "no pending" in res.get_json()["message"]


def test_settled_payments_are_not_settled_twice(client):
    pay(client, amount="10.00")
    client.post("/api/settlements/run")
    pay(client, amount="20.00")
    second = client.post("/api/settlements/run").get_json()
    assert second["batch_id"] == "BATCH0002"
    assert second["gross_amount"] == "20.00"


def test_stats(client):
    pay(client, amount="10.00")
    pay(client, amount="5.50")
    client.post("/api/settlements/run")
    pay(client, amount="1.25")
    stats = client.get("/api/stats").get_json()
    assert stats == {
        "total_payments": 3,
        "pending_count": 1,
        "pending_amount": "1.25",
        "settled_count": 2,
        "settled_amount": "15.50",
        "batch_count": 1,
    }


def test_unknown_payment_is_404(client):
    assert client.get("/api/payments/TXNNOPE").status_code == 404


def test_inactive_core_pauses_payments_and_settlement():
    client = create_app(settlement_core="INACTIVE").test_client()
    assert client.get("/api/health").get_json()["settlement_core"] == "INACTIVE"
    assert pay(client).status_code == 503
    assert client.post("/api/settlements/run").status_code == 503

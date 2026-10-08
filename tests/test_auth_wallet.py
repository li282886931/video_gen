from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import app


def test_register_login_and_wallet_flow():
    client = TestClient(app)
    username = f"user_{uuid4().hex[:8]}"

    register_resp = client.post(
        "/api/auth/register",
        json={"username": username, "password": "strong-password", "display_name": "充值用户"},
    )
    assert register_resp.status_code == 200
    assert register_resp.json()["user"]["username"] == username
    assert "password" not in str(register_resp.json())

    login_resp = client.post("/api/auth/login", json={"username": username, "password": "strong-password"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == username

    wallet_resp = client.get("/api/wallet", headers=headers)
    assert wallet_resp.status_code == 200
    assert wallet_resp.json()["balance"] == 0

    recharge_resp = client.post("/api/wallet/recharge", json={"amount": 128, "note": "首次充值"}, headers=headers)
    assert recharge_resp.status_code == 200
    assert recharge_resp.json()["balance"] == 128

    consume_resp = client.post("/api/wallet/consume", json={"amount": 28, "note": "生成任务"}, headers=headers)
    assert consume_resp.status_code == 200
    assert consume_resp.json()["balance"] == 100
    assert len(consume_resp.json()["transactions"]) == 2


def test_workbench_requires_bearer_token():
    client = TestClient(app)

    assert client.get("/api/workbench/state").status_code == 401


def test_invalid_login_is_rejected():
    client = TestClient(app)

    resp = client.post("/api/auth/login", json={"username": "missing-user", "password": "bad"})

    assert resp.status_code == 401

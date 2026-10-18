# backend/tests/test_qa_conversations.py

"""AI 問答對話紀錄依帳號隔離。

過去對話存在瀏覽器的同一個 localStorage 鍵，同一台電腦換帳號登入
就會看到上一位使用者的對話。改存後端後，每個帳號只能讀寫自己的對話。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.database_models import Plan, QAConversation, User
from app.routers import qa as qa_router
from app.services.auth_service import hash_password


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestSession()
    session.add(Plan(code="pro", display_name="專業版", max_watch_keywords=5, max_history_days=90,
                     allow_all_platforms=1, monthly_qa_quota=100, allow_export=1, sort_order=1))
    for name in ("alice", "bob"):
        session.add(User(username=name, password_hash=hash_password("pw123456"),
                         display_name=name, role="user", is_active=1, plan_code="pro"))
    session.commit()
    session.close()

    yield TestClient(app), TestSession
    app.dependency_overrides.clear()


def header(c, username):
    token = c.post("/api/auth/login", json={"username": username, "password": "pw123456"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def conversation(title="玻尿酸評價", **extra):
    return {
        "title": title,
        "keyword": "玻尿酸",
        "messages": [{"id": 1, "role": "user", "text": "最近評價如何？"}],
        **extra,
    }


def listed(c, headers):
    return c.get("/api/qa/conversations", headers=headers).json()["data"]["conversations"]


def test_each_account_only_sees_its_own_conversations(client):
    c, _ = client
    alice, bob = header(c, "alice"), header(c, "bob")

    assert c.put("/api/qa/conversations/a-1", json=conversation("Alice 的對話"), headers=alice).status_code == 200
    assert c.put("/api/qa/conversations/b-1", json=conversation("Bob 的對話"), headers=bob).status_code == 200

    assert [item["title"] for item in listed(c, alice)] == ["Alice 的對話"]
    assert [item["title"] for item in listed(c, bob)] == ["Bob 的對話"]


def test_same_client_id_does_not_overwrite_another_account(client):
    """前端產生的 id 只在同一帳號內唯一；別人用到同一個 id 也不能蓋掉自己的對話。"""
    c, _ = client
    alice, bob = header(c, "alice"), header(c, "bob")

    c.put("/api/qa/conversations/same", json=conversation("Alice 的對話"), headers=alice)
    c.put("/api/qa/conversations/same", json=conversation("Bob 的對話"), headers=bob)

    assert listed(c, alice)[0]["title"] == "Alice 的對話"
    assert listed(c, bob)[0]["title"] == "Bob 的對話"


def test_cannot_delete_another_accounts_conversation(client):
    c, _ = client
    alice, bob = header(c, "alice"), header(c, "bob")
    c.put("/api/qa/conversations/a-1", json=conversation(), headers=alice)

    assert c.delete("/api/qa/conversations/a-1", headers=bob).status_code == 404
    assert len(listed(c, alice)) == 1

    assert c.delete("/api/qa/conversations/a-1", headers=alice).status_code == 200
    assert listed(c, alice) == []


def test_update_keeps_one_row_and_returns_messages(client):
    c, TestSession = client
    alice = header(c, "alice")

    c.put("/api/qa/conversations/a-1", json=conversation(), headers=alice)
    updated = conversation(messages=[{"id": 1, "role": "user", "text": "Q"}, {"id": 2, "role": "assistant", "answer": "A"}])
    c.put("/api/qa/conversations/a-1", json=updated, headers=alice)

    items = listed(c, alice)
    assert len(items) == 1
    assert items[0]["id"] == "a-1"
    assert [m["role"] for m in items[0]["messages"]] == ["user", "assistant"]

    session = TestSession()
    assert session.query(QAConversation).count() == 1
    session.close()


def test_pinned_conversations_come_first(client):
    c, _ = client
    alice = header(c, "alice")
    c.put("/api/qa/conversations/old", json=conversation("釘選", pinned=True), headers=alice)
    c.put("/api/qa/conversations/new", json=conversation("較新"), headers=alice)

    assert [item["title"] for item in listed(c, alice)] == ["釘選", "較新"]


def test_guest_cannot_read_or_write_conversations(client):
    c, _ = client

    assert c.get("/api/qa/conversations").status_code == 401
    assert c.put("/api/qa/conversations/x", json=conversation()).status_code == 401


def test_invalid_client_id_is_rejected(client):
    c, _ = client

    assert c.put("/api/qa/conversations/bad id!", json=conversation(), headers=header(c, "alice")).status_code == 422


def test_old_unpinned_conversations_are_pruned(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(qa_router, "MAX_CONVERSATIONS", 2)
    alice = header(c, "alice")

    for index in range(4):
        c.put(f"/api/qa/conversations/c{index}", json=conversation(f"對話{index}"), headers=alice)

    assert len(listed(c, alice)) == 2


def test_conversations_are_removed_with_the_account(client):
    """刪除帳號時對話一併刪除（外鍵 CASCADE）。"""
    target = Base.metadata.tables["qa_conversations"].columns["user_id"]
    assert {fk.ondelete for fk in target.foreign_keys} == {"CASCADE"}

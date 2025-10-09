import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError
from app import create_app, db
from app.models import Todo


@pytest.fixture()
def app():
    app = create_app("testing")
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------- Health Endpoint ----------
def test_health_endpoint_success(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert b"healthy" in res.data


@patch("app.routes.db.session.execute", side_effect=SQLAlchemyError("DB error"))
def test_health_endpoint_database_error(mock_exec, client):
    res = client.get("/api/health")
    assert res.status_code == 503
    assert b"unhealthy" in res.data


# ---------- Create Todo ----------
def test_create_todo_with_full_data(client):
    res = client.post("/api/todos", json={"title": "Test task"})
    assert res.status_code == 201
    assert b"Test task" in res.data


def test_create_todo_without_title(client):
    res = client.post("/api/todos", json={})
    assert res.status_code == 400
    assert b"title is required" in res.data


@patch("app.routes.db.session.commit", side_effect=SQLAlchemyError("fail"))
def test_create_todo_database_error(mock_commit, client):
    res = client.post("/api/todos", json={"title": "DB fail"})
    assert res.status_code == 500
    assert b"Internal server error" in res.data


# ---------- Get Todo ----------
def test_get_all_todos_empty(client):
    res = client.get("/api/todos")
    assert res.status_code == 200
    data = res.get_json()
    assert data == []


def test_get_all_todos_with_data(client, app):
    with app.app_context():
        todo = Todo(title="task1")
        db.session.add(todo)
        db.session.commit()

    res = client.get("/api/todos")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 1
    assert data[0]["title"] == "task1"


def test_get_single_todo_found(client, app):
    with app.app_context():
        todo = Todo(title="found")
        db.session.add(todo)
        db.session.commit()
        tid = todo.id

    res = client.get(f"/api/todos/{tid}")
    assert res.status_code == 200
    assert b"found" in res.data


def test_get_single_todo_not_found(client):
    res = client.get("/api/todos/999")
    assert res.status_code == 404


# ---------- Update Todo ----------
def test_update_todo_title(client, app):
    with app.app_context():
        todo = Todo(title="old")
        db.session.add(todo)
        db.session.commit()
        tid = todo.id

    res = client.put(f"/api/todos/{tid}", json={"title": "new"})
    assert res.status_code == 200
    assert b"new" in res.data


def test_update_todo_not_found(client):
    res = client.put("/api/todos/999", json={"title": "new"})
    assert res.status_code == 404


def test_update_todo_database_error(client, app):
    # ✅ commit จริงตอนสร้าง
    with app.app_context():
        todo = Todo(title="T")
        db.session.add(todo)
        db.session.commit()
        tid = todo.id

    # ✅ mock commit เฉพาะตอนอัปเดต
    from unittest.mock import patch
    with patch("app.routes.db.session.commit") as mock_commit:
        mock_commit.side_effect = SQLAlchemyError("fail")
        res = client.put(f"/api/todos/{tid}", json={"title": "N"})

    assert res.status_code == 500
    assert b"Internal server error" in res.data


# ---------- Delete Todo ----------
def test_delete_todo_success(client, app):
    with app.app_context():
        todo = Todo(title="del")
        db.session.add(todo)
        db.session.commit()
        tid = todo.id

    res = client.delete(f"/api/todos/{tid}")
    assert res.status_code == 200
    assert b"deleted" in res.data


def test_delete_todo_not_found(client):
    res = client.delete("/api/todos/999")
    assert res.status_code == 404


def test_delete_todo_database_error(client, app):
    # ✅ commit จริงตอนสร้าง
    with app.app_context():
        todo = Todo(title="D")
        db.session.add(todo)
        db.session.commit()
        tid = todo.id

    # ✅ mock commit เฉพาะตอนลบ
    from unittest.mock import patch
    with patch("app.routes.db.session.commit") as mock_commit:
        mock_commit.side_effect = SQLAlchemyError("fail")
        res = client.delete(f"/api/todos/{tid}")

    assert res.status_code == 500
    assert b"Internal server error" in res.data

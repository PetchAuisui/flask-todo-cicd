import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.models import db, Todo


# ---------------- Fixtures ----------------
@pytest.fixture()
def app():
    app = create_app("testing")  # ใช้ SQLite in-memory
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------- App/Factory & Handlers ----------------
class TestAppFactory:
    def test_app_created(self, app):
        assert app is not None
        assert app.config["TESTING"] is True

    def test_root_endpoint(self, client):
        res = client.get("/")
        assert res.status_code == 200
        data = res.get_json()
        # ตรงกับ app/__init__.py
        assert data["message"] == "Flask Todo API"
        assert "endpoints" in data

    def test_404_handler(self, client):
        res = client.get("/nope")
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_global_exception_handler(self, app):
        @app.route("/boom")
        def boom():
            raise Exception("boom!")
        res = app.test_client().get("/boom")
        assert res.status_code == 500
        data = res.get_json()
        assert data["success"] is False
        assert "Internal server error" in data["error"]


# ---------------- Health ----------------
class TestHealthCheck:
    def test_health_ok(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    @patch("app.routes.db.session.execute", side_effect=Exception("down"))
    def test_health_db_error(self, _mock, client):
        res = client.get("/api/health")
        assert res.status_code == 503
        data = res.get_json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "error" in data


# ---------------- Todo CRUD ----------------
class TestTodoAPI:
    # ---- GET (empty) ----
    def test_get_all_todos_empty(self, client):
        res = client.get("/api/todos")
        assert res.status_code == 200
        data = res.get_json()
        # ตรงกับ routes.get_todos()
        assert data["success"] is True
        assert data["count"] == 0
        assert data["data"] == []

    # ---- CREATE ----
    def test_create_todo_with_full_data(self, client):
        res = client.post(
            "/api/todos",
            json={"title": "Test Todo", "description": "desc"},
        )
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "Test Todo"
        assert data["data"]["description"] == "desc"
        assert data["data"]["completed"] is False
        assert "message" in data

    def test_create_todo_without_title(self, client):
        res = client.post("/api/todos", json={})
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        # ข้อความจริงใน routes.py คือ "Title is required"
        assert "Title is required" in data["error"]

    @patch("app.routes.db.session.commit", side_effect=SQLAlchemyError("fail"))
    def test_create_todo_database_error(self, _mock_commit, client):
        res = client.post("/api/todos", json={"title": "X"})
        assert res.status_code == 500
        data = res.get_json()
        # routes.py ส่ง "Failed to create todo"
        assert data["success"] is False
        assert "Failed to create todo" in data["error"]

    # ---- GET by id ----
    def test_get_todo_by_id(self, client, app):
        with app.app_context():
            todo = Todo(title="Get me", description="D")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.get(f"/api/todos/{tid}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "Get me"
        assert data["data"]["description"] == "D"

    def test_get_nonexistent_todo(self, client):
        res = client.get("/api/todos/999999")
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False

    # ---- UPDATE ----
    def test_update_todo_title(self, client, app):
        with app.app_context():
            todo = Todo(title="old")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.put(f"/api/todos/{tid}", json={"title": "new"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "new"

    def test_update_todo_description(self, client, app):
        with app.app_context():
            todo = Todo(title="t", description="old")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.put(f"/api/todos/{tid}", json={"description": "new"})
        assert res.status_code == 200
        assert res.get_json()["data"]["description"] == "new"

    def test_update_todo_completed(self, client, app):
        with app.app_context():
            todo = Todo(title="t")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.put(f"/api/todos/{tid}", json={"completed": True})
        assert res.status_code == 200
        assert res.get_json()["data"]["completed"] is True

    def test_update_nonexistent(self, client):
        res = client.put("/api/todos/999999", json={"title": "x"})
        assert res.status_code == 404
        assert res.get_json()["success"] is False

    def test_update_todo_database_error(self, client, app):
        # commit จริงตอนสร้างก่อน
        with app.app_context():
            todo = Todo(title="T")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        # mock commit เฉพาะตอนอัปเดต
        with patch("app.routes.db.session.commit") as mock_commit:
            mock_commit.side_effect = SQLAlchemyError("fail")
            res = client.put(f"/api/todos/{tid}", json={"title": "N"})

        assert res.status_code == 500
        data = res.get_json()
        # routes.py ส่ง "Failed to update todo"
        assert data["success"] is False
        assert "Failed to update todo" in data["error"]

    # ---- DELETE ----
    def test_delete_todo_success(self, client, app):
        with app.app_context():
            todo = Todo(title="del")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.delete(f"/api/todos/{tid}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "Todo deleted successfully" in data["message"]

    def test_delete_nonexistent(self, client):
        res = client.delete("/api/todos/999999")
        assert res.status_code == 404
        assert res.get_json()["success"] is False

    def test_delete_todo_database_error(self, client, app):
        # commit จริงตอนสร้างก่อน
        with app.app_context():
            todo = Todo(title="D")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        # mock commit เฉพาะตอนลบ
        with patch("app.routes.db.session.commit") as mock_commit:
            mock_commit.side_effect = SQLAlchemyError("fail")
            res = client.delete(f"/api/todos/{tid}")

        assert res.status_code == 500
        data = res.get_json()
        # routes.py ส่ง "Failed to delete todo"
        assert data["success"] is False
        assert "Failed to delete todo" in data["error"]

    # ---- GET all with data ----
    def test_get_all_todos_with_data(self, client, app):
        with app.app_context():
            db.session.add_all([Todo(title="A"), Todo(title="B"), Todo(title="C")])
            db.session.commit()

        res = client.get("/api/todos")
        assert res.status_code == 200
        payload = res.get_json()
        assert payload["success"] is True
        assert payload["count"] == 3
        titles = [t["title"] for t in payload["data"]]
        # /api/todos เรียง created_at desc → C, B, A
        assert titles[0] == "C" and titles[-1] == "A"

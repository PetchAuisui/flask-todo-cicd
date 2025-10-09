# tests/test_app.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.models import db, Todo


# ----------------------------
# Pytest fixtures
# ----------------------------
@pytest.fixture
def app():
    """Create and configure a test app instance"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner"""
    return app.test_cli_runner()


# ----------------------------
# App / Handlers
# ----------------------------
class TestAppFactory:
    """Test application factory and global handlers"""

    def test_app_creation(self, app):
        assert app is not None
        assert app.config["TESTING"] is True

    def test_root_endpoint(self, client):
        res = client.get("/")
        assert res.status_code == 200
        data = res.get_json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data

    def test_404_handler(self, client):
        res = client.get("/no-such-path")
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_global_500_handler(self, app):
        # ปิด TESTING เพื่อให้ error handler ของ Flask ทำงานตามจริง
        app.config["TESTING"] = False

        @app.route("/test-error")
        def trigger_error():
            raise Exception("boom")

        with app.test_client() as c:
            res = c.get("/test-error")
            assert res.status_code == 500
            data = res.get_json()
            assert data["success"] is False
            assert "Internal server error" in data["error"]

        # เปิดกลับ
        app.config["TESTING"] = True


# ----------------------------
# /api/health
# ----------------------------
class TestHealthCheck:
    """Test health check endpoint"""

    def test_health_endpoint_success(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    @patch("app.routes.db.session.execute")
    def test_health_endpoint_database_error(self, mock_execute, client):
        mock_execute.side_effect = Exception("DB down")
        res = client.get("/api/health")
        assert res.status_code == 503
        data = res.get_json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "error" in data


# ----------------------------
# Model methods
# ----------------------------
class TestTodoModel:
    """Test Todo model methods"""

    def test_todo_to_dict_and_repr(self, app):
        with app.app_context():
            todo = Todo(title="Test Todo", description="Test Description")
            db.session.add(todo)
            db.session.commit()

            d = todo.to_dict()
            assert d["title"] == "Test Todo"
            assert d["description"] == "Test Description"
            assert d["completed"] is False
            assert "id" in d
            assert "created_at" in d and "updated_at" in d
            r = repr(todo)
            assert "Todo" in r and "Test Todo" in r


# ----------------------------
# /api/todos CRUD + errors
# ----------------------------
class TestTodoAPI:
    """Test Todo CRUD operations and error branches"""

    def test_get_empty_todos(self, client):
        res = client.get("/api/todos")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["count"] == 0
        assert data["data"] == []

    def test_create_todo_with_full_data(self, client):
        payload = {"title": "Test Todo", "description": "This is a test todo"}
        res = client.post("/api/todos", json=payload)
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "Test Todo"
        assert data["data"]["description"] == "This is a test todo"
        assert data["data"]["completed"] is False
        assert "message" in data

    def test_create_todo_with_title_only(self, client):
        payload = {"title": "Only Title"}
        res = client.post("/api/todos", json=payload)
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "Only Title"
        assert data["data"]["description"] == ""

    def test_create_todo_without_title(self, client):
        res = client.post("/api/todos", json={})
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert "Title is required" in data["error"]

    @patch("app.routes.db.session.commit")
    def test_create_todo_database_error(self, mock_commit, client):
        mock_commit.side_effect = SQLAlchemyError("db error")
        res = client.post("/api/todos", json={"title": "X"})
        assert res.status_code == 500
        data = res.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_get_todo_by_id(self, client, app):
        with app.app_context():
            todo = Todo(title="Test Todo", description="Test Description")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.get(f"/api/todos/{tid}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "Test Todo"
        assert data["data"]["description"] == "Test Description"

    def test_get_nonexistent_todo(self, client):
        res = client.get("/api/todos/999999")
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_update_todo_title(self, client, app):
        with app.app_context():
            todo = Todo(title="Old Title")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.put(f"/api/todos/{tid}", json={"title": "New Title"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "New Title"
        assert "message" in data

    def test_update_todo_description(self, client, app):
        with app.app_context():
            todo = Todo(title="Test", description="Old Desc")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.put(f"/api/todos/{tid}", json={"description": "New Desc"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["description"] == "New Desc"

    def test_update_todo_completed_status(self, client, app):
        with app.app_context():
            todo = Todo(title="Test")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.put(f"/api/todos/{tid}", json={"completed": True})
        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["completed"] is True

    def test_update_todo_all_fields(self, client, app):
        with app.app_context():
            todo = Todo(title="Original", description="Old")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        payload = {"title": "New Title", "description": "New Desc", "completed": True}
        res = client.put(f"/api/todos/{tid}", json=payload)
        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["title"] == "New Title"
        assert data["data"]["description"] == "New Desc"
        assert data["data"]["completed"] is True

    def test_update_nonexistent_todo(self, client):
        res = client.put("/api/todos/999999", json={"title": "X"})
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False

    @patch("app.routes.db.session.commit")
    def test_update_todo_database_error(self, mock_commit, client, app):
        with app.app_context():
            todo = Todo(title="T")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        mock_commit.side_effect = SQLAlchemyError("fail")
        res = client.put(f"/api/todos/{tid}", json={"title": "N"})
        assert res.status_code == 500
        data = res.get_json()
        assert data["success"] is False

    def test_delete_todo(self, client, app):
        with app.app_context():
            todo = Todo(title="To Be Deleted")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        res = client.delete(f"/api/todos/{tid}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "message" in data

        # verify deleted
        res = client.get(f"/api/todos/{tid}")
        assert res.status_code == 404

    def test_delete_nonexistent_todo(self, client):
        res = client.delete("/api/todos/999999")
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False

    @patch("app.routes.db.session.commit")
    def test_delete_todo_database_error(self, mock_commit, client, app):
        with app.app_context():
            todo = Todo(title="D")
            db.session.add(todo)
            db.session.commit()
            tid = todo.id

        mock_commit.side_effect = SQLAlchemyError("fail")
        res = client.delete(f"/api/todos/{tid}")
        assert res.status_code == 500
        data = res.get_json()
        assert data["success"] is False

    def test_get_all_todos_ordered(self, client, app):
        """Make created_at deterministic to test ordering (desc)."""
        with app.app_context():
            t1 = Todo(
                title="Todo 1", created_at=datetime.utcnow() - timedelta(seconds=2)
            )
            t2 = Todo(
                title="Todo 2", created_at=datetime.utcnow() - timedelta(seconds=1)
            )
            t3 = Todo(title="Todo 3", created_at=datetime.utcnow())
            db.session.add_all([t1, t2, t3])
            db.session.commit()

        res = client.get("/api/todos")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["count"] == 3

        titles = [item["title"] for item in data["data"]]
        # newest first
        assert titles == ["Todo 3", "Todo 2", "Todo 1"]

    @patch("app.routes.Todo")
    def test_get_todos_database_error(self, mock_todo, client):
        # chain: Todo.query.order_by(...).all() -> raise
        mock_todo.query.order_by.return_value.all.side_effect = SQLAlchemyError(
            "DB Error"
        )
        res = client.get("/api/todos")
        assert res.status_code == 500
        data = res.get_json()
        assert data["success"] is False
        assert "error" in data


# ----------------------------
# Integration flows
# ----------------------------
class TestIntegration:
    """Integration tests for complete workflows"""

    def test_complete_todo_lifecycle(self, client):
        # Create
        create_res = client.post(
            "/api/todos",
            json={"title": "Integration Todo", "description": "Full cycle"},
        )
        assert create_res.status_code == 201
        tid = create_res.get_json()["data"]["id"]

        # Read
        read_res = client.get(f"/api/todos/{tid}")
        assert read_res.status_code == 200
        assert read_res.get_json()["data"]["title"] == "Integration Todo"

        # Update
        update_res = client.put(
            f"/api/todos/{tid}",
            json={"title": "Integration Updated", "completed": True},
        )
        assert update_res.status_code == 200
        updated = update_res.get_json()["data"]
        assert updated["title"] == "Integration Updated"
        assert updated["completed"] is True

        # Delete
        del_res = client.delete(f"/api/todos/{tid}")
        assert del_res.status_code == 200

        # Verify deletion
        verify_res = client.get(f"/api/todos/{tid}")
        assert verify_res.status_code == 404

    def test_multiple_todos_workflow(self, client):
        # Create multiple
        for i in range(5):
            r = client.post(
                "/api/todos", json={"title": f"Todo {i+1}", "completed": (i % 2 == 0)}
            )
            assert r.status_code == 201

        # Get all
        res = client.get("/api/todos")
        assert res.status_code == 200
        data = res.get_json()
        assert data["count"] == 5

        # Update first (newest)
        first_id = data["data"][0]["id"]
        r = client.put(f"/api/todos/{first_id}", json={"completed": True})
        assert r.status_code == 200

        # Delete the same
        r = client.delete(f"/api/todos/{first_id}")
        assert r.status_code == 200

        # Count decreased
        res2 = client.get("/api/todos")
        assert res2.get_json()["count"] == 4

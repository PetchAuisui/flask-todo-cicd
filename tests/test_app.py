import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError
from app import create_app
from app.models import db, Todo


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


class TestHealthCheck:
    """Test health check endpoint"""

    def test_health_endpoint_success(self, client):
        """Test health check returns 200 when database is healthy"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    @patch("app.routes.db.session.execute")
    def test_health_endpoint_database_error(self, mock_execute, client):
        """Test health check returns 503 when database is down"""
        mock_execute.side_effect = Exception("Database connection failed")

        response = client.get("/api/health")
        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "error" in data


class TestTodoAPI:
    """Test Todo CRUD operations"""

    """Test Todo CRUD operations"""

    def test_get_empty_todos(self, client):
        """Test getting todos when database is empty"""
        response = client.get("/api/todos")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["count"] == 0
        assert data["data"] == []

    def test_create_todo_with_full_data(self, client):
        """Test creating a new todo with title and description"""
        todo_data = {"title": "Test Todo", "description": "This is a test todo"}
        response = client.post("/api/todos", json=todo_data)
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "Test Todo"
        assert data["data"]["description"] == "This is a test todo"
        assert data["data"]["completed"] is False
        assert "message" in data

    def test_create_todo_with_title_only(self, client):
        """Test creating todo with only title (description is optional)"""
        todo_data = {"title": "Test Todo Only Title"}
        response = client.post("/api/todos", json=todo_data)
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "Test Todo Only Title"
        assert data["data"]["description"] == ""

    def test_create_todo_without_title(self, client):
        """Test creating todo without title fails validation"""
        response = client.post("/api/todos", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data
        assert "Title is required" in data["error"]

    def test_create_todo_with_none_data(self, client):
        """Test creating todo with None data"""
        response = client.post("/api/todos", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    @patch("app.routes.db.session.commit")
    def test_create_todo_database_error(self, mock_commit, client):
        """Test database error during todo creation"""
        mock_commit.side_effect = SQLAlchemyError("Database error")

        response = client.post("/api/todos", json={"title": "Test"})
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_get_todo_by_id(self, client, app):
        """Test getting a specific todo by ID"""
        with app.app_context():
            todo = Todo(title="Test Todo", description="Test Description")
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        response = client.get(f"/api/todos/{todo_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "Test Todo"
        assert data["data"]["description"] == "Test Description"

    def test_get_nonexistent_todo(self, client):
        """Test getting a todo that doesn't exist"""
        response = client.get("/api/todos/9999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data
        assert "not found" in data["error"].lower()

    def test_update_todo_title(self, client, app):
        """Test updating todo title"""
        with app.app_context():
            todo = Todo(title="Original Title")
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        update_data = {"title": "Updated Title"}
        response = client.put(f"/api/todos/{todo_id}", json=update_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["title"] == "Updated Title"
        assert "message" in data

    def test_update_todo_description(self, client, app):
        """Test updating todo description"""
        with app.app_context():
            todo = Todo(title="Test", description="Old Description")
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        update_data = {"description": "New Description"}
        response = client.put(f"/api/todos/{todo_id}", json=update_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["description"] == "New Description"

    def test_update_todo_completed_status(self, client, app):
        """Test updating todo completed status"""
        with app.app_context():
            todo = Todo(title="Test")
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        update_data = {"completed": True}
        response = client.put(f"/api/todos/{todo_id}", json=update_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["completed"] is True

    def test_update_todo_all_fields(self, client, app):
        """Test updating all todo fields at once"""
        with app.app_context():
            todo = Todo(title="Original", description="Old")
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        update_data = {
            "title": "New Title",
            "description": "New Description",
            "completed": True,
        }
        response = client.put(f"/api/todos/{todo_id}", json=update_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["title"] == "New Title"
        assert data["data"]["description"] == "New Description"
        assert data["data"]["completed"] is True

    def test_update_nonexistent_todo(self, client):
        """Test updating a todo that doesn't exist"""
        response = client.put("/api/todos/9999", json={"title": "Updated"})
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False

    @patch("app.routes.db.session.commit")
    def test_update_todo_database_error(self, mock_commit, client, app):
        """Test database error during todo update"""
        # สร้าง todo ก่อน (ไม่ถูก mock)
        with app.app_context():
            todo = Todo(title="Test")
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        # แล้วค่อย mock เฉพาะตอน update
        with patch("app.routes.db.session.commit") as mock_commit:
            mock_commit.side_effect = SQLAlchemyError("Database error")
            client.put(f"/api/todos/{todo_id}", json={"title": "New"})

    def test_delete_todo(self, client, app):
        """Test deleting a todo"""
        with app.app_context():
            todo = Todo(title="To Be Deleted")
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        response = client.delete(f"/api/todos/{todo_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify it's deleted
        response = client.get(f"/api/todos/{todo_id}")
        assert response.status_code == 404

    def test_delete_nonexistent_todo(self, client):
        """Test deleting a todo that doesn't exist"""
        response = client.delete("/api/todos/9999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False

    @patch("app.routes.db.session.delete")
    def test_delete_todo_database_error(self, mock_commit, client, app):
        """Test database error during todo deletion"""
        with app.app_context():
            todo = Todo(title="Test")
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        mock_commit.side_effect = SQLAlchemyError("Database error")

        response = client.delete(f"/api/todos/{todo_id}")
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False

    def test_get_all_todos_ordered(self, client, app):
        """Test getting all todos returns them in correct order"""
        with app.app_context():
            todos = [Todo(title="Todo 1"), Todo(title="Todo 2"), Todo(title="Todo 3")]
            db.session.add_all(todos)
            db.session.commit()

        response = client.get("/api/todos")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["count"] == 3
        # Should be ordered by created_at desc (newest first)
        assert data["data"][0]["title"] == "Todo 3"
        assert data["data"][2]["title"] == "Todo 1"

    @patch("app.routes.Todo.query")
    def test_get_todos_database_error(self, mock_query, client):
        """Test database error when getting todos"""
        mock_query.order_by.return_value.all.side_effect = SQLAlchemyError("DB Error")

        response = client.get("/api/todos")
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False


class TestAppFactory:
    """Test application factory and configuration"""

    def test_app_creation(self, app):
        """Test app is created successfully"""
        assert app is not None
        assert app.config["TESTING"] is True

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data

    def test_404_error_handler(self, client):
        """Test 404 error handler"""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_exception_handler(self, app):
        """Test generic exception handler"""
        # 1. ปิด TESTING mode ชั่วคราว
        app.config["TESTING"] = False

        @app.route("/test-error")
        def trigger_error():
            raise Exception("Test error")

        # 2. ทดสอบ
        with app.test_client() as test_client:
            response = test_client.get("/test-error")
            assert response.status_code == 500
            assert "Internal server error" in response.get_json()["error"]

        # 3. เปิด TESTING mode กลับ
        app.config["TESTING"] = True


class TestTodoModel:
    """Test Todo model methods"""

    def test_todo_to_dict(self, app):
        """Test todo model to_dict method"""
        with app.app_context():
            todo = Todo(title="Test Todo", description="Test Description")
            db.session.add(todo)
            db.session.commit()

            todo_dict = todo.to_dict()
            assert todo_dict["title"] == "Test Todo"
            assert todo_dict["description"] == "Test Description"
            assert todo_dict["completed"] is False
            assert "id" in todo_dict
            assert "created_at" in todo_dict
            assert "updated_at" in todo_dict

    def test_todo_repr(self, app):
        """Test todo model __repr__ method"""
        with app.app_context():
            todo = Todo(title="Test Todo")
            db.session.add(todo)
            db.session.commit()

            repr_str = repr(todo)
            assert "Todo" in repr_str
            assert "Test Todo" in repr_str


class TestIntegration:
    """Integration tests for complete workflows"""

    def test_complete_todo_lifecycle(self, client):
        """Test complete CRUD workflow"""
        # Create
        create_response = client.post(
            "/api/todos",
            json={
                "title": "Integration Test Todo",
                "description": "Testing full lifecycle",
            },
        )
        assert create_response.status_code == 201
        todo_id = create_response.get_json()["data"]["id"]

        # Read
        read_response = client.get(f"/api/todos/{todo_id}")
        assert read_response.status_code == 200
        assert read_response.get_json()["data"]["title"] == "Integration Test Todo"

        # Update
        update_response = client.put(
            f"/api/todos/{todo_id}",
            json={"title": "Updated Integration Test", "completed": True},
        )
        assert update_response.status_code == 200
        updated_data = update_response.get_json()["data"]
        assert updated_data["title"] == "Updated Integration Test"
        assert updated_data["completed"] is True

        # Delete
        delete_response = client.delete(f"/api/todos/{todo_id}")
        assert delete_response.status_code == 200

        # Verify deletion
        verify_response = client.get(f"/api/todos/{todo_id}")
        assert verify_response.status_code == 404

    def test_multiple_todos_workflow(self, client):
        """Test working with multiple todos"""
        # Create multiple todos
        for i in range(5):
            response = client.post(
                "/api/todos",
                json={
                    "title": f"Todo {i+1}",
                    "completed": i % 2 == 0,  # Alternate completed status
                },
            )
            assert response.status_code == 201

        # Get all and verify count
        response = client.get("/api/todos")
        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 5

        # Update some
        todo_id = data["data"][0]["id"]
        response = client.put(f"/api/todos/{todo_id}", json={"completed": True})
        assert response.status_code == 200

        # Delete some
        response = client.delete(f"/api/todos/{todo_id}")
        assert response.status_code == 200

        # Verify count decreased
        response = client.get("/api/todos")
        assert response.get_json()["count"] == 4
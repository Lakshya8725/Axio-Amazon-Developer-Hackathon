"""Automated tests for health check and service discovery endpoint."""

def test_service_index_json(client):
    """The API root is a discovery document, not a 404."""
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Axio"
    assert data["status"] == "online"
    assert data["tagline"] == "Your intent. In action."
    assert data["operator_ui"] == "http://127.0.0.1:3000"
    assert data["health"] == "/health"
    assert data["mcp_endpoint"] == "/mcp"
    assert data["agent"] == "/api/agent/run"


def test_service_index_html(client):
    """A browser request to the API root renders the service page."""
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "Open the operator" in body
    assert "http://127.0.0.1:3000" in body
    assert "Not Found" not in body


def test_health_check(client):
    """Verify that /health returns HTTP 200 with application metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "Axio"
    assert data["version"] == "0.1.0"
    assert data["mcp_endpoint"] == "/mcp"

"""Automated tests for health check and service discovery endpoint."""

def test_health_check(client):
    """Verify that /health returns HTTP 200 with application metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "Axio"
    assert data["version"] == "0.1.0"
    assert data["mcp_endpoint"] == "/mcp"

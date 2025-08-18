"""
Tests for health endpoints
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_health_endpoint_success(client: TestClient):
    """Test health endpoint returns success"""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "timestamp" in data
    assert "services" in data
    assert "environment" in data
    assert "project_id" in data
    assert "version" in data


@pytest.mark.unit
def test_health_endpoint_includes_all_services(client: TestClient):
    """Test health endpoint checks all required services"""
    response = client.get("/health")
    data = response.json()
    
    required_services = ["cache", "queue", "tiktok_scraper", "app_check"]
    for service in required_services:
        assert service in data["services"]


@pytest.mark.unit
def test_health_endpoint_response_structure(client: TestClient):
    """Test health endpoint response structure"""
    response = client.get("/health")
    data = response.json()
    
    # Check required fields
    assert isinstance(data["status"], str)
    assert isinstance(data["timestamp"], str)
    assert isinstance(data["environment"], str)
    assert isinstance(data["services"], dict)
    
    # Check services have status
    for service_name, service_status in data["services"].items():
        assert isinstance(service_status, str)
        # Services can be healthy, unhealthy, or have error messages
        assert (service_status in ["healthy", "unhealthy"] or 
                service_status.startswith("error:") or 
                service_status == "error")


@pytest.mark.unit
def test_status_endpoint_success(client: TestClient):
    """Test status endpoint returns operational info"""
    response = client.get("/status")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "timestamp" in data
    assert "hybrid_mode" in data
    assert "rate_limiting" in data
    assert "processing_queue" in data
    assert "cache" in data
    assert "queue" in data


@pytest.mark.unit
def test_status_endpoint_structure(client: TestClient):
    """Test status endpoint response structure"""
    response = client.get("/status")
    data = response.json()
    
    # Check hybrid mode info
    hybrid_mode = data["hybrid_mode"]
    assert hybrid_mode["enabled"] is True
    assert "direct_processing" in hybrid_mode
    assert "active" in hybrid_mode["direct_processing"]
    assert "max" in hybrid_mode["direct_processing"]
    assert "available" in hybrid_mode["direct_processing"]
    
    # Check rate limiting info
    rate_limiting = data["rate_limiting"]
    assert "active_ips" in rate_limiting
    assert "limit_per_ip" in rate_limiting
    assert "window_seconds" in rate_limiting
    
    # Check processing queue info
    processing_queue = data["processing_queue"]
    assert "available_slots" in processing_queue
    assert "total_slots" in processing_queue

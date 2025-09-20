#!/usr/bin/env python3
"""
Comprehensive test suite for the SNF Legislation Tracker API
Tests all endpoints, authentication, and functionality
"""

import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
import json
from datetime import datetime, timedelta

# Import the FastAPI app
from api.main import app
from api.config import settings

# Test configuration
TEST_BASE_URL = "http://testserver"
API_PREFIX = settings.api_prefix

class TestAPIClient:
    """Test client wrapper with authentication helpers"""

    def __init__(self):
        self.client = TestClient(app)
        self.access_token = None
        self.refresh_token = None
        self.test_user = {
            "email": "test@example.com",
            "password": "testpassword123",
            "full_name": "Test User",
            "organization": "Test SNF"
        }

    def auth_headers(self):
        """Get authorization headers"""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    def register_user(self):
        """Register test user"""
        response = self.client.post(
            f"{API_PREFIX}/auth/register",
            json=self.test_user
        )
        return response

    def login_user(self):
        """Login and store tokens"""
        response = self.client.post(
            f"{API_PREFIX}/auth/login",
            json={
                "email": self.test_user["email"],
                "password": self.test_user["password"]
            }
        )
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens["refresh_token"]
        return response

# Test fixtures
@pytest.fixture
def test_client():
    """Create test client"""
    return TestAPIClient()

# Authentication Tests
def test_root_endpoint(test_client):
    """Test root endpoint"""
    response = test_client.client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == settings.app_name
    assert data["version"] == settings.app_version
    assert data["status"] == "healthy"

def test_health_check(test_client):
    """Test health check endpoint"""
    response = test_client.client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_api_info(test_client):
    """Test API info endpoint"""
    response = test_client.client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    assert "documentation" in data

def test_user_registration(test_client):
    """Test user registration"""
    response = test_client.register_user()
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == test_client.test_user["email"]
    assert data["full_name"] == test_client.test_user["full_name"]
    assert "id" in data

def test_duplicate_registration(test_client):
    """Test duplicate user registration"""
    # Register once
    test_client.register_user()

    # Try to register again with same email
    response = test_client.register_user()
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

def test_user_login(test_client):
    """Test user login"""
    # Register user first
    test_client.register_user()

    # Login
    response = test_client.login_user()
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_invalid_login(test_client):
    """Test login with invalid credentials"""
    response = test_client.client.post(
        f"{API_PREFIX}/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

def test_protected_endpoint_without_auth(test_client):
    """Test accessing protected endpoint without authentication"""
    response = test_client.client.get(f"{API_PREFIX}/auth/me")
    assert response.status_code == 403

def test_user_profile(test_client):
    """Test getting user profile"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    # Get user profile
    response = test_client.client.get(
        f"{API_PREFIX}/auth/me",
        headers=test_client.auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_client.test_user["email"]

def test_token_refresh(test_client):
    """Test token refresh"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    # Refresh token
    response = test_client.client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": test_client.refresh_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

def test_logout(test_client):
    """Test user logout"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    # Logout
    response = test_client.client.post(
        f"{API_PREFIX}/auth/logout",
        headers=test_client.auth_headers()
    )
    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]

# Bills API Tests
def test_get_bills_public(test_client):
    """Test getting bills without authentication (if allowed)"""
    response = test_client.client.get(f"{API_PREFIX}/bills/")
    # May return 401 if authentication is required, or 200 if public access is allowed
    assert response.status_code in [200, 401]

def test_get_bills_authenticated(test_client):
    """Test getting bills with authentication"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    # Get bills
    response = test_client.client.get(
        f"{API_PREFIX}/bills/",
        headers=test_client.auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert "bills" in data
    assert "total" in data
    assert "page" in data

def test_get_bills_with_filters(test_client):
    """Test getting bills with filters"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    # Test various filters
    filters = [
        {"state": "federal"},
        {"min_relevance_score": 50},
        {"search": "medicare"},
        {"page_size": 10},
        {"sort_by": "relevance_score", "sort_order": "desc"}
    ]

    for filter_params in filters:
        response = test_client.client.get(
            f"{API_PREFIX}/bills/",
            params=filter_params,
            headers=test_client.auth_headers()
        )
        assert response.status_code == 200

def test_get_nonexistent_bill(test_client):
    """Test getting a bill that doesn't exist"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    response = test_client.client.get(
        f"{API_PREFIX}/bills/999999",
        headers=test_client.auth_headers()
    )
    assert response.status_code == 404

def test_bill_tracking(test_client):
    """Test bill tracking functionality"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    # Try to track a bill (may fail if bill doesn't exist)
    tracking_data = {
        "alert_on_changes": True,
        "alert_on_stage_transitions": True,
        "min_change_severity": "moderate"
    }

    response = test_client.client.post(
        f"{API_PREFIX}/bills/1/track",
        json=tracking_data,
        headers=test_client.auth_headers()
    )
    # May return 404 if bill doesn't exist, 200/201 if successful
    assert response.status_code in [200, 201, 404]

# Alerts API Tests
def test_get_user_alerts(test_client):
    """Test getting user alerts"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    response = test_client.client.get(
        f"{API_PREFIX}/alerts/",
        headers=test_client.auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert "alerts" in data
    assert "total" in data
    assert "unread_count" in data

def test_alerts_with_filters(test_client):
    """Test getting alerts with filters"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    filters = [
        {"unread_only": True},
        {"priority": "high"},
        {"alert_type": "change"},
        {"page_size": 5}
    ]

    for filter_params in filters:
        response = test_client.client.get(
            f"{API_PREFIX}/alerts/",
            params=filter_params,
            headers=test_client.auth_headers()
        )
        assert response.status_code == 200

def test_alert_preferences_get(test_client):
    """Test getting alert preferences"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    response = test_client.client.get(
        f"{API_PREFIX}/alerts/preferences",
        headers=test_client.auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert "email_enabled" in data
    assert "min_priority" in data

def test_alert_preferences_create(test_client):
    """Test creating/updating alert preferences"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    preferences_data = {
        "email_enabled": True,
        "email_frequency": "daily",
        "min_priority": "medium",
        "min_relevance_score": 60.0,
        "monitor_text_changes": True,
        "monitor_stage_transitions": True
    }

    response = test_client.client.post(
        f"{API_PREFIX}/alerts/preferences",
        json=preferences_data,
        headers=test_client.auth_headers()
    )
    assert response.status_code == 200

def test_mark_all_alerts_read(test_client):
    """Test marking all alerts as read"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    response = test_client.client.post(
        f"{API_PREFIX}/alerts/mark-all-read",
        headers=test_client.auth_headers()
    )
    assert response.status_code == 200

def test_alert_stats(test_client):
    """Test getting alert statistics"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    response = test_client.client.get(
        f"{API_PREFIX}/alerts/stats",
        headers=test_client.auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_alerts" in data
    assert "by_priority" in data

# Dashboard API Tests
def test_dashboard_stats(test_client):
    """Test getting dashboard statistics"""
    # Setup: register and login
    test_client.register_user()
    test_client.login_user()

    response = test_client.client.get(
        f"{API_PREFIX}/dashboard/stats",
        headers=test_client.auth_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert "bill_stats" in data
    assert "alert_stats" in data
    assert "user_activity" in data

def test_trending_bills(test_client):
    """Test getting trending bills"""
    response = test_client.client.get(f"{API_PREFIX}/dashboard/trending")
    assert response.status_code == 200
    data = response.json()
    assert "bills" in data
    assert "period" in data

def test_trending_bills_with_params(test_client):
    """Test trending bills with different parameters"""
    params_list = [
        {"period": "24h"},
        {"period": "7d", "limit": 10},
        {"period": "30d", "min_relevance_score": 70}
    ]

    for params in params_list:
        response = test_client.client.get(
            f"{API_PREFIX}/dashboard/trending",
            params=params
        )
        assert response.status_code == 200

def test_system_health(test_client):
    """Test system health endpoint"""
    response = test_client.client.get(f"{API_PREFIX}/dashboard/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data

# Error Handling Tests
def test_invalid_json(test_client):
    """Test sending invalid JSON"""
    response = test_client.client.post(
        f"{API_PREFIX}/auth/login",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422

def test_missing_required_fields(test_client):
    """Test missing required fields"""
    response = test_client.client.post(
        f"{API_PREFIX}/auth/register",
        json={"email": "test@example.com"}  # Missing required fields
    )
    assert response.status_code == 422

def test_invalid_email_format(test_client):
    """Test invalid email format"""
    response = test_client.client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": "invalid-email",
            "password": "password123",
            "full_name": "Test User"
        }
    )
    assert response.status_code == 422

# Rate Limiting Tests (these may be skipped in test environment)
@pytest.mark.skipif(settings.debug, reason="Rate limiting may be disabled in debug mode")
def test_rate_limiting():
    """Test rate limiting functionality"""
    client = TestClient(app)

    # Make many requests rapidly
    responses = []
    for i in range(settings.rate_limit_requests + 5):
        response = client.get("/health")
        responses.append(response)

    # Check that some requests were rate limited
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes  # Too Many Requests

# Performance Tests
def test_response_times(test_client):
    """Test that endpoints respond within reasonable time"""
    import time

    endpoints = [
        "/",
        "/health",
        "/info",
        f"{API_PREFIX}/dashboard/trending"
    ]

    for endpoint in endpoints:
        start_time = time.time()
        response = test_client.client.get(endpoint)
        response_time = time.time() - start_time

        # Should respond within 2 seconds
        assert response_time < 2.0, f"Endpoint {endpoint} took {response_time:.2f}s"

def run_manual_tests():
    """Run manual tests that require user interaction"""
    print("\n🧪 Running Manual API Tests")
    print("=" * 50)

    client = TestAPIClient()

    # Test sequence: Register -> Login -> Use API -> Logout
    print("1. Testing user registration...")
    reg_response = client.register_user()
    print(f"   Status: {reg_response.status_code}")
    if reg_response.status_code == 201:
        print(f"   ✅ User registered: {reg_response.json()['email']}")
    else:
        print(f"   ❌ Registration failed: {reg_response.json()}")
        return

    print("\n2. Testing user login...")
    login_response = client.login_user()
    print(f"   Status: {login_response.status_code}")
    if login_response.status_code == 200:
        print("   ✅ Login successful")
        tokens = login_response.json()
        print(f"   Access token: {tokens['access_token'][:20]}...")
    else:
        print(f"   ❌ Login failed: {login_response.json()}")
        return

    print("\n3. Testing protected endpoints...")
    endpoints_to_test = [
        ("GET", f"{API_PREFIX}/auth/me", "User profile"),
        ("GET", f"{API_PREFIX}/bills/", "Bills list"),
        ("GET", f"{API_PREFIX}/alerts/", "User alerts"),
        ("GET", f"{API_PREFIX}/dashboard/stats", "Dashboard stats")
    ]

    for method, endpoint, description in endpoints_to_test:
        if method == "GET":
            response = client.client.get(endpoint, headers=client.auth_headers())
        else:
            response = client.client.post(endpoint, headers=client.auth_headers())

        print(f"   {description}: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Success")
        else:
            print(f"   ❌ Failed: {response.json()}")

    print("\n4. Testing logout...")
    logout_response = client.client.post(
        f"{API_PREFIX}/auth/logout",
        headers=client.auth_headers()
    )
    print(f"   Status: {logout_response.status_code}")
    if logout_response.status_code == 200:
        print("   ✅ Logout successful")
    else:
        print(f"   ❌ Logout failed: {logout_response.json()}")

    print("\n🎉 Manual tests completed!")

if __name__ == "__main__":
    # Run manual tests
    run_manual_tests()

    # Run pytest tests
    print("\n" + "=" * 50)
    print("To run automated tests, use:")
    print("pytest test_api.py -v")
    print("\nOr run specific test categories:")
    print("pytest test_api.py -v -k 'test_auth'")
    print("pytest test_api.py -v -k 'test_bills'")
    print("pytest test_api.py -v -k 'test_alerts'")
    print("pytest test_api.py -v -k 'test_dashboard'")
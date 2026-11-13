"""Tests for Farmer Authentication, Registration Onboarding, and Authorization.
"""
from __future__ import annotations

import pytest


def test_farmer_registration_success(client):
    payload = {
        "name": "Ramesh Kumar",
        "email": "ramesh@farm.test",
        "phone": "9876543210",
        "password": "SecurePassword123!",
        "preferred_language": "te",
        "state": "Telangana",
        "district": "Warangal",
        "village": "Geesugonda",
        "age": 42,
        "contact_method": "phone",
        "farm_name": "Ramesh Organic Farm",
        "field_name": "East Cotton Plot",
        "area": 2.5,
        "area_unit": "acres",
        "soil_type": "Clay loam",
        "soil_ph": 6.8,
        "irrigation_method": "Drip",
        "pump_flow_rate_lpm": 300.0,
        "crop_type": "Cotton",
        "crop_variety": "Bt Cotton",
        "planting_date": "2026-06-15",
        "growth_stage": "vegetative",
        "latitude": 17.9689,
        "longitude": 79.5941,
        "location_name": "Warangal, Telangana",
    }
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    farmer = data["farmer"]
    assert farmer["name"] == "Ramesh Kumar"
    assert farmer["email"] == "ramesh@farm.test"
    assert farmer["preferred_language"] == "te"
    assert farmer["village"] == "Geesugonda"
    assert "password" not in farmer
    assert "password_hash" not in farmer

    # Verify field was created with converted area (2.5 acres -> ~1.012 hectares)
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["farmer"]["farmer_id"] == farmer["farmer_id"]
    assert len(me_data["fields"]) >= 1
    field = me_data["fields"][0]
    assert field["name"] == "East Cotton Plot"
    assert field["soil_type"] == "Clay loam"
    assert field["soil_ph"] == 6.8
    assert field["irrigation_method"] == "Drip"
    assert field["pump_flow_rate_lpm"] == 300.0
    # 2.5 * 0.404686 = 1.012 ha
    assert 1.01 <= field["area_hectares"] <= 1.02


def test_farmer_registration_duplicate_email(client):
    payload = {
        "name": "Suresh Rao",
        "email": "suresh@farm.test",
        "phone": "9876543211",
        "password": "Password123!",
    }
    resp1 = client.post("/auth/register", json=payload)
    assert resp1.status_code == 201

    # Same email, different phone
    payload2 = {
        "name": "Another Suresh",
        "email": "suresh@farm.test",
        "phone": "9876543212",
        "password": "Password123!",
    }
    resp2 = client.post("/auth/register", json=payload2)
    assert resp2.status_code == 409
    assert "email address already exists" in resp2.json()["detail"]


def test_farmer_registration_validation_errors(client):
    # Invalid email
    resp1 = client.post(
        "/auth/register",
        json={"name": "Test", "email": "invalid-email", "phone": "9876543210", "password": "pass"},
    )
    assert resp1.status_code == 422

    # Phone too short
    resp2 = client.post(
        "/auth/register",
        json={"name": "Test", "email": "valid@farm.test", "phone": "123", "password": "ValidPassword123!"},
    )
    assert resp2.status_code == 422

    # Password too short (< 6 chars)
    resp3 = client.post(
        "/auth/register",
        json={"name": "Test", "email": "valid@farm.test", "phone": "9876543210", "password": "123"},
    )
    assert resp3.status_code == 422


def test_farmer_login_email_and_phone(client):
    reg_payload = {
        "name": "Priya Sharma",
        "email": "priya@farm.test",
        "phone": "9876543219",
        "password": "SecretPassword456!",
        "preferred_language": "hi",
    }
    reg_resp = client.post("/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201

    # Login via email
    login_email = client.post(
        "/auth/login",
        json={"email_or_phone": "priya@farm.test", "password": "SecretPassword456!"},
    )
    assert login_email.status_code == 200
    assert "access_token" in login_email.json()

    # Login via phone
    login_phone = client.post(
        "/auth/login",
        json={"email_or_phone": "9876543219", "password": "SecretPassword456!"},
    )
    assert login_phone.status_code == 200
    assert "access_token" in login_phone.json()

    # Wrong password
    bad_login = client.post(
        "/auth/login",
        json={"email_or_phone": "priya@farm.test", "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401

    # Non-existent user
    non_existent = client.post(
        "/auth/login",
        json={"email_or_phone": "nobody@farm.test", "password": "AnyPassword"},
    )
    assert non_existent.status_code == 401


def test_farmer_profile_get_and_put(client):
    reg_resp = client.post(
        "/auth/register",
        json={
            "name": "Kavitha",
            "email": "kavitha@farm.test",
            "phone": "9876543222",
            "password": "Password789!",
            "preferred_language": "ta",
        },
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET /farmers/profile
    prof_resp = client.get("/farmers/profile", headers=headers)
    assert prof_resp.status_code == 200
    assert prof_resp.json()["name"] == "Kavitha"
    assert prof_resp.json()["preferred_language"] == "ta"

    # PUT /farmers/profile
    update_resp = client.put(
        "/farmers/profile",
        headers=headers,
        json={"village": "Thanjavur South", "district": "Thanjavur", "preferred_language": "ta"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["village"] == "Thanjavur South"


def test_farmer_field_authorization_isolation(client):
    # Register Farmer 1
    f1_resp = client.post(
        "/auth/register",
        json={"name": "Farmer One", "email": "f1@farm.test", "phone": "9876543231", "password": "PassWord1!"},
    )
    t1 = f1_resp.json()["access_token"]
    h1 = {"Authorization": f"Bearer {t1}"}

    # Register Farmer 2
    f2_resp = client.post(
        "/auth/register",
        json={"name": "Farmer Two", "email": "f2@farm.test", "phone": "9876543232", "password": "PassWord2!"},
    )
    t2 = f2_resp.json()["access_token"]
    h2 = {"Authorization": f"Bearer {t2}"}

    # Farmer 1 creates a new field
    field_resp = client.post(
        "/fields",
        headers=h1,
        json={"name": "F1 Secret Plot", "crop_type": "Wheat", "area_hectares": 2.0},
    )
    assert field_resp.status_code == 201
    f1_field_id = field_resp.json()["field_id"]

    # Farmer 1 can view their field
    f1_view = client.get(f"/fields/{f1_field_id}", headers=h1)
    assert f1_view.status_code == 200

    # Farmer 2 tries to view or modify Farmer 1's field -> 403 Forbidden
    f2_view = client.get(f"/fields/{f1_field_id}", headers=h2)
    assert f2_view.status_code == 403

    f2_update = client.put(f"/fields/{f1_field_id}", headers=h2, json={"name": "Hacked Plot"})
    assert f2_update.status_code == 403

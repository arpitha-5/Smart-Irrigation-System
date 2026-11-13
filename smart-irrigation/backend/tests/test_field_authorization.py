from app.models import Farmer, User
from app.services.auth_service import create_access_token


def test_field_creation_requires_auth_and_limits_owner_profiles(client, db):
    user = User(
        full_name="Owner One",
        email="owner-one@example.test",
        hashed_password="unused",
    )
    other_user = User(
        full_name="Owner Two",
        email="owner-two@example.test",
        hashed_password="unused",
    )
    db.add_all([
        user,
        other_user,
        Farmer(farmer_id="FR001", name="Owner One", email="owner-one@example.test"),
        Farmer(farmer_id="FR003", name="Owner One's Second Farm", email="owner-one@example.test"),
        Farmer(farmer_id="FR002", name="Owner Two", email="owner-two@example.test"),
    ])
    db.commit()
    db.refresh(user)

    field_data = {
        "name": "Authorized Field",
        "crop_type": "Rice",
        "area_hectares": 1,
        "location_name": "Nizamabad",
    }
    assert client.post(
        "/fields",
        json={**field_data, "farmer_id": "FR001"},
    ).status_code == 401

    owner_headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
    profile_response = client.get("/auth/me", headers=owner_headers)
    assert profile_response.status_code == 200
    assert {
        profile["farmer_id"] for profile in profile_response.json()["farmer_profiles"]
    } == {"FR001", "FR003"}

    assert client.post(
        "/fields",
        json={**field_data, "farmer_id": "FR003"},
        headers=owner_headers,
    ).status_code == 201
    assert client.post(
        "/fields",
        json={**field_data, "farmer_id": "FR001"},
        headers=owner_headers,
    ).status_code == 201

    dashboard = client.get("/farmers/me/dashboard", headers=owner_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total_fields"] == 2

    response = client.post(
        "/fields",
        json={**field_data, "farmer_id": "FR002"},
        headers=owner_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "You can only register a field to a farmer profile linked to your account."

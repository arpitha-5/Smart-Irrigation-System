from .conftest import owner_auth_headers, post_field_as_owner


def test_create_and_retrieve_farmer(client):
    r = client.post("/farmers", json={"name": "Harini", "phone": "9999900000"})
    assert r.status_code == 201
    assert r.json()["farmer_id"] == "FR001"  # auto-generated
    assert client.get("/farmers/FR001").json()["name"] == "Harini"
    assert len(client.get("/farmers").json()) == 1


def test_create_field_and_retrieve(client):
    client.post("/farmers", json={"farmer_id": "FR001", "name": "Harini"})
    r = post_field_as_owner(client, {
        "field_id": "F001", "farmer_id": "FR001", "name": "North Paddy",
        "latitude": 17.385, "longitude": 78.4867, "crop_type": "  rice ", "area_hectares": 1.5})
    assert r.status_code == 201
    body = r.json()
    assert body["crop_type"] == "Rice"  # normalised
    got = client.get("/fields/F001").json()
    assert got["farmer_id"] == "FR001" and got["latitude"] == 17.385 and got["sensors"] == []
    assert [f["field_id"] for f in client.get("/farmers/FR001").json()["fields"]] == ["F001"]
    assert len(client.get("/fields", params={"farmer_id": "FR001"}).json()) == 1


def test_field_registration_persists_field_details(client, db):
    client.post("/farmers", json={"farmer_id": "FR009", "name": "Test Farmer"})
    response = post_field_as_owner(client, {
        "farmer_id": "FR009",
        "name": "West Orchard",
        "location_name": "Nizamabad",
        "crop_type": "Mango",
        "area_hectares": 0.75,
        "soil_type": "Clay loam",
        "irrigation_method": "Drip",
        "description": "North block beside the well.",
    })

    assert response.status_code == 201
    body = response.json()
    assert body["field_id"] == "F001"
    assert body["farmer_id"] == "FR009"
    assert body["soil_type"] == "Clay loam"
    assert body["irrigation_method"] == "Drip"
    assert body["description"] == "North block beside the well."
    assert client.get("/fields/F001").json()["area_hectares"] == 0.75

    from app.models import Field

    saved = db.get(Field, "F001")
    assert saved is not None
    assert saved.farmer_id == "FR009"
    assert saved.soil_type == "Clay loam"
    assert saved.irrigation_method == "Drip"
    assert saved.description == "North block beside the well."


def test_field_requires_existing_farmer(client):
    client.post("/farmers", json={"farmer_id": "FR001", "name": "Harini"})
    headers = owner_auth_headers(client, "FR001")
    r = client.post(
        "/fields",
        json={"farmer_id": "NOPE", "name": "X", "crop_type": "Rice"},
        headers=headers,
    )
    assert r.status_code == 404 and r.json()["error"]["code"] == "farmer_not_found"


def test_duplicate_field_id_conflict(client, seeded):
    r = post_field_as_owner(client, {"field_id": "F001", "farmer_id": "FR001", "name": "Dup", "crop_type": "Rice"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_id"


def test_field_validation_errors(client, seeded):
    base = {"farmer_id": "FR001", "name": "X", "crop_type": "Rice"}
    assert post_field_as_owner(client, {**base, "latitude": 95, "longitude": 10}).status_code == 422
    assert post_field_as_owner(client, {**base, "latitude": 10}).status_code == 422  # lat without lon
    assert post_field_as_owner(client, {**base, "crop_type": "   "}).status_code == 422
    assert post_field_as_owner(client, {**base, "area_hectares": -1}).status_code == 422


def test_field_without_location_is_allowed(client, seeded):
    r = post_field_as_owner(client, {"farmer_id": "FR001", "name": "No GPS", "crop_type": "Maize"})
    assert r.status_code == 201 and r.json()["latitude"] is None and r.json()["field_id"] == "F002"


def test_assign_crop(client, seeded):
    r = client.put("/fields/F001/crop", json={"crop_type": "ragi"})
    assert r.status_code == 200 and r.json()["crop_type"] == "Ragi"
    assert client.put("/fields/NOPE/crop", json={"crop_type": "Rice"}).status_code == 404


def test_create_sensor_associated_with_field(client, seeded):
    s = client.get("/sensors/SM001").json()
    assert s["field_id"] == "F001" and s["sensor_type"] == "soil_moisture" and s["status"] == "active"
    assert [x["sensor_id"] for x in client.get("/fields/F001/sensors").json()] == ["SM001"]
    assert [x["sensor_id"] for x in client.get("/fields/F001").json()["sensors"]] == ["SM001"]
    assert len(client.get("/sensors", params={"field_id": "F001"}).json()) == 1


def test_sensor_requires_existing_field(client):
    r = client.post("/sensors", json={"sensor_id": "SM9", "field_id": "NOPE"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "field_not_found"


def test_duplicate_sensor_and_unknown_sensor(client, seeded):
    assert client.post("/sensors", json={"sensor_id": "SM001", "field_id": "F001"}).status_code == 409
    assert client.get("/sensors/NOPE").status_code == 404


def test_sensor_status_toggle(client, seeded):
    assert client.put("/sensors/SM001/status", json={"status": "inactive"}).json()["status"] == "inactive"
    assert client.put("/sensors/SM001/status", json={"status": "broken"}).status_code == 422

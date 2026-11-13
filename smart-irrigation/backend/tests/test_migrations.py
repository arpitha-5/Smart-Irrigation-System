from sqlalchemy import create_engine, inspect, text

from app.database.migrate import apply_additive_migrations


def test_field_metadata_migration_preserves_existing_rows():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE fields ("
                "field_id VARCHAR(32) PRIMARY KEY, name VARCHAR(120), "
                "location_name VARCHAR(200), latitude FLOAT, longitude FLOAT, "
                "crop_type VARCHAR(80), area_hectares FLOAT)"
            ))
            connection.execute(text(
                "INSERT INTO fields (field_id, name, location_name, crop_type, area_hectares) "
                "VALUES ('F001', 'Legacy Field', 'Hyderabad', 'Rice', 1.25)"
            ))

        apply_additive_migrations(engine)

        with engine.connect() as connection:
            row = connection.execute(text(
                "SELECT field_id, name, field_name, location_name, soil_type, "
                "irrigation_method, description, area_hectares FROM fields WHERE field_id = 'F001'"
            )).mappings().one()
            columns = {column["name"] for column in inspect(connection).get_columns("fields")}

        assert {"soil_type", "irrigation_method", "description"} <= columns
        assert row["name"] == row["field_name"] == "Legacy Field"
        assert row["location_name"] == "Hyderabad"
        assert row["area_hectares"] == 1.25
        assert row["soil_type"] is None
        assert row["irrigation_method"] is None
        assert row["description"] is None
    finally:
        engine.dispose()

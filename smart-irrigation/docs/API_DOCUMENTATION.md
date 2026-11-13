# Intelligence API

All intelligence endpoints require the existing JWT bearer token.

## `GET /intelligence/digital-twin`

Returns the authenticated farmer's fields and latest persisted sensor
telemetry. `health` is `healthy`, `moderate`, `critical`, or `unknown`.
`unknown` means no stored reading exists.

## `GET /intelligence/crop-stress`

Optional query parameter: `field_id`.

Returns explainable water-stress indicators. The result is advisory and does
not diagnose disease. A field without telemetry is returned with
`data_available: false`.

## `POST /intelligence/water-budget`

Request:

```json
{
  "available_water_liters": 100000,
  "horizon_days": 7
}
```

`available_water_liters` must be greater than zero. `horizon_days` is limited
to 1-30. The response includes estimated demand, field allocations, shortage,
remaining capacity, and the formulas/assumptions used. This endpoint is a
planning calculation and does not persist a schedule.

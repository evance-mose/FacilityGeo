from math import asin, cos, radians, sin, sqrt


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def coverage_score(staff_deployed: int, staff_approved: int, status: str) -> str:
    if status == "closed":
        return "no-service"
    if staff_approved <= 0:
        return "unknown"
    fill = staff_deployed / staff_approved
    if fill >= 0.85 and status == "operational":
        return "adequate"
    if fill >= 0.5:
        return "stretched"
    return "critical"


def facility_geojson(facility, extra: dict | None = None) -> dict:
    properties = {
        "id": facility.id,
        "code": facility.code,
        "name": facility.name,
        "facility_type": facility.facility_type,
        "owner": facility.owner,
        "status": facility.status,
        "staff_deployed": facility.staff_deployed,
        "staff_approved": facility.staff_approved,
        "staffing_gap": max(facility.staff_approved - facility.staff_deployed, 0),
        "coverage": coverage_score(facility.staff_deployed, facility.staff_approved, facility.status),
        "district": facility.district.name if facility.district else None,
        "region": facility.district.region if facility.district else None,
        "last_inspection": facility.last_inspection.isoformat() if facility.last_inspection else None,
    }
    if extra:
        properties.update(extra)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [facility.longitude, facility.latitude],
        },
        "properties": properties,
    }

from datetime import datetime

from pydantic import BaseModel, Field


class DistrictOut(BaseModel):
    id: int
    name: str
    region: str
    latitude: float
    longitude: float
    population_estimate: int
    facility_count: int = 0

    model_config = {"from_attributes": True}


class FacilityBase(BaseModel):
    name: str
    facility_type: str
    owner: str = "MoH"
    district_id: int
    latitude: float = Field(..., ge=-17.2, le=-9.2)
    longitude: float = Field(..., ge=32.5, le=36.0)
    status: str = "operational"
    staff_deployed: int = 0
    staff_approved: int = 0
    notes: str = ""


class FacilityCreate(FacilityBase):
    code: str


class FacilityUpdate(BaseModel):
    name: str | None = None
    facility_type: str | None = None
    owner: str | None = None
    district_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: str | None = None
    staff_deployed: int | None = None
    staff_approved: int | None = None
    notes: str | None = None


class FacilityOut(FacilityBase):
    id: int
    code: str
    district_name: str | None = None
    region: str | None = None
    staffing_gap: int = 0
    last_inspection: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NearbyQuery(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 15


class DeploymentCreate(BaseModel):
    event_type: str
    description: str


class DeploymentOut(BaseModel):
    id: int
    facility_id: int
    event_type: str
    description: str
    recorded_at: datetime

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    districts: int
    facilities: int
    operational: int
    limited_service: int
    closed: int
    staffing_gap: int
    understaffed_facilities: int
    coverage_radius_km: float

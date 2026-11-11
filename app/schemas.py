"""Request models. Coordinates are validated against Malawi's bounding box."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Status a user can set. 'not_in_tracker' is only ever set by the tracker load
# (a facility with no tracker row), never by hand.
Status = Literal["not_started", "in_progress", "live"]
# Values accepted by filters and analysis endpoints.
FilterStatus = Literal["not_in_tracker", "not_started", "in_progress", "live"]

# Malawi bounding box (lon first, as in ST_MakePoint(lon, lat)).
LON_MIN, LON_MAX = 32.5, 36.0
LAT_MIN, LAT_MAX = -17.2, -9.2


class FacilityCreate(BaseModel):
    facility_code: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=200)
    district: str = Field(min_length=2, max_length=60)
    facility_type: Optional[str] = Field(default=None, max_length=60)
    deployment_status: Status = "not_started"
    go_live_date: Optional[date] = None
    devices_installed: Optional[int] = Field(default=None, ge=0, le=100000)
    staff_trained: Optional[int] = Field(default=None, ge=0, le=100000)
    has_internet: Optional[bool] = None
    has_power: Optional[bool] = None
    latitude: float = Field(ge=LAT_MIN, le=LAT_MAX, description="Degrees, inside Malawi")
    longitude: float = Field(ge=LON_MIN, le=LON_MAX, description="Degrees, inside Malawi")

    @field_validator("name", "district", "facility_type", mode="before")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class StatusUpdate(BaseModel):
    deployment_status: Status

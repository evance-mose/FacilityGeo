from datetime import datetime
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    region: Mapped[str] = mapped_column(String(40))
    geom = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)

    facilities: Mapped[list["HealthFacility"]] = relationship(back_populates="district")
    officers: Mapped[list["SupportOfficer"]] = relationship(back_populates="district")


class HealthFacility(Base):
    __tablename__ = "health_facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    facility_type: Mapped[str] = mapped_column(String(80))
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    mahis_status: Mapped[str] = mapped_column(String(32), default="not_started")
    has_internet: Mapped[bool] = mapped_column(Boolean, default=False)
    has_power: Mapped[bool] = mapped_column(Boolean, default=False)
    has_trained_staff: Mapped[bool] = mapped_column(Boolean, default=False)

    district: Mapped["District"] = relationship(back_populates="facilities")
    events: Mapped[list["DeploymentEvent"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan"
    )


class SupportOfficer(Base):
    __tablename__ = "support_officers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    district_id: Mapped[Optional[int]] = mapped_column(ForeignKey("districts.id"), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)

    district: Mapped[Optional["District"]] = relationship(back_populates="officers")


class DeploymentEvent(Base):
    __tablename__ = "deployment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("health_facilities.id"))
    status: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

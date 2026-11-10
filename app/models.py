from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    region: Mapped[str] = mapped_column(String(40), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    population_estimate: Mapped[int] = mapped_column(Integer, default=0)

    facilities: Mapped[list["HealthFacility"]] = relationship(back_populates="district")


class HealthFacility(Base):
    __tablename__ = "health_facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    facility_type: Mapped[str] = mapped_column(String(80), index=True)
    owner: Mapped[str] = mapped_column(String(80), default="MoH")
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="operational", index=True)
    staff_deployed: Mapped[int] = mapped_column(Integer, default=0)
    staff_approved: Mapped[int] = mapped_column(Integer, default=0)
    last_inspection: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    district: Mapped[District] = relationship(back_populates="facilities")
    deployments: Mapped[list["DeploymentEvent"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan"
    )


class DeploymentEvent(Base):
    __tablename__ = "deployment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("health_facilities.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    facility: Mapped[HealthFacility] = relationship(back_populates="deployments")

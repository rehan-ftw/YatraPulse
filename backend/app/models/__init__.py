"""SQLAlchemy ORM models for the normalized railway data model.

Tables:
  stations           - station master (code, name, coordinates)
  trains             - train master (number, name, source/destination)
  route_stations     - ordered stops for a train, with schedule + distance
                       (this table also carries the schedule, so a separate
                       `schedules` table is intentionally omitted to avoid
                       unnecessary complexity)
  historical_delays  - per train+station historical delay statistics
  train_status       - current (simulated) live state for each train
  simulation_state   - per-train simulation lifecycle state
  operational_events - log of simulated operational events (congestion, etc.)
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    station_name: Mapped[str] = mapped_column(String(128), index=True)
    # nullable: some imported catalogue stations may lack coordinates
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)


class Train(Base):
    __tablename__ = "trains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_number: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    train_name: Mapped[str] = mapped_column(String(160), index=True)
    source_station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    destination_station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    # curated flagship demo trains (12952 etc.) vs imported catalogue trains
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    source_station: Mapped["Station"] = relationship(foreign_keys=[source_station_id])
    destination_station: Mapped["Station"] = relationship(
        foreign_keys=[destination_station_id]
    )
    route_stations: Mapped[list["RouteStation"]] = relationship(
        back_populates="train",
        order_by="RouteStation.sequence_number",
        cascade="all, delete-orphan",
    )


class RouteStation(Base):
    __tablename__ = "route_stations"
    __table_args__ = (UniqueConstraint("train_id", "sequence_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[int] = mapped_column(ForeignKey("trains.id"))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    sequence_number: Mapped[int] = mapped_column(Integer)
    scheduled_arrival: Mapped[str | None] = mapped_column(String(5), nullable=True)
    scheduled_departure: Mapped[str | None] = mapped_column(String(5), nullable=True)
    distance_from_origin: Mapped[float] = mapped_column(Float, default=0.0)

    train: Mapped["Train"] = relationship(back_populates="route_stations")
    station: Mapped["Station"] = relationship()


class HistoricalDelay(Base):
    __tablename__ = "historical_delays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[int] = mapped_column(ForeignKey("trains.id"))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    average_delay_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    punctuality_percent: Mapped[float] = mapped_column(Float, default=100.0)
    delay_category: Mapped[str] = mapped_column(String(32), default="on_time")

    station: Mapped["Station"] = relationship()


class TrainStatus(Base):
    """Current (simulated) operational state of a train."""

    __tablename__ = "train_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[int] = mapped_column(ForeignKey("trains.id"), unique=True)

    current_station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id"), nullable=True
    )
    next_station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id"), nullable=True
    )
    current_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # position along the polyline: index of the segment start + fraction [0,1]
    segment_index: Mapped[int] = mapped_column(Integer, default=0)
    segment_progress: Mapped[float] = mapped_column(Float, default=0.0)

    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_arrival_dest: Mapped[str | None] = mapped_column(String(5), nullable=True)
    current_eta: Mapped[str | None] = mapped_column(String(5), nullable=True)
    status_text: Mapped[str] = mapped_column(String(64), default="ON TIME")
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    # provenance of the current state: SCHEDULED | SIMULATED | HISTORICAL | LIVE
    source: Mapped[str] = mapped_column(String(16), default="SCHEDULED")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    current_station: Mapped["Station"] = relationship(
        foreign_keys=[current_station_id]
    )
    next_station: Mapped["Station"] = relationship(foreign_keys=[next_station_id])


class SimulationState(Base):
    __tablename__ = "simulation_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[int] = mapped_column(ForeignKey("trains.id"), unique=True)
    state: Mapped[str] = mapped_column(String(16), default="idle")  # idle/running/paused/stopped
    tick: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class TrainRoute(Base):
    """Real route polyline for a train (from the DataMeet timetable geometry).

    Stored once per train and used to draw the route and to move the simulated
    marker along the true path. `polyline` is a JSON array of [lat, lng] pairs.
    """

    __tablename__ = "train_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[int] = mapped_column(ForeignKey("trains.id"), unique=True)
    polyline: Mapped[str] = mapped_column(Text, default="[]")
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)


class OperationalEvent(Base):
    __tablename__ = "operational_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    train_id: Mapped[int] = mapped_column(ForeignKey("trains.id"))
    type: Mapped[str] = mapped_column(String(32))  # congestion / signal_hold / station_delay
    location: Mapped[str] = mapped_column(String(128), default="")
    impact_minutes: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

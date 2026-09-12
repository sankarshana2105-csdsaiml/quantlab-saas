from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserModel(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    datasets: Mapped[list["DatasetModel"]] = relationship(back_populates="owner")
    backtests: Mapped[list["BacktestModel"]] = relationship(back_populates="owner")


class DatasetModel(TimestampMixin, Base):
    __tablename__ = "datasets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    row_count: Mapped[int] = mapped_column(Integer)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bars: Mapped[list["DatasetBarModel"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", order_by="DatasetBarModel.ordinal"
    )
    owner: Mapped[UserModel] = relationship(back_populates="datasets")


class DatasetBarModel(Base):
    __tablename__ = "dataset_bars"
    __table_args__ = (
        UniqueConstraint("dataset_id", "ordinal"),
        UniqueConstraint("dataset_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    dataset: Mapped[DatasetModel] = relationship(back_populates="bars")


class BacktestModel(TimestampMixin, Base):
    __tablename__ = "backtests"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100))
    strategy_parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    backtest_parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    result_row_count: Mapped[int] = mapped_column(Integer)
    result_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metrics: Mapped["MetricModel"] = relationship(
        back_populates="backtest", cascade="all, delete-orphan", uselist=False
    )
    trades: Mapped[list["TradeModel"]] = relationship(
        back_populates="backtest", cascade="all, delete-orphan", order_by="TradeModel.ordinal"
    )
    points: Mapped[list["SeriesPointModel"]] = relationship(
        back_populates="backtest", cascade="all, delete-orphan", order_by="SeriesPointModel.ordinal"
    )
    owner: Mapped[UserModel] = relationship(back_populates="backtests")


class MetricModel(Base):
    __tablename__ = "performance_metrics"

    backtest_id: Mapped[UUID] = mapped_column(ForeignKey("backtests.id", ondelete="CASCADE"), primary_key=True)
    total_return: Mapped[float] = mapped_column(Float)
    cumulative_return: Mapped[float] = mapped_column(Float)
    annualized_return: Mapped[float] = mapped_column(Float)
    cagr: Mapped[float] = mapped_column(Float)
    sharpe_ratio: Mapped[float] = mapped_column(Float)
    sortino_ratio: Mapped[float] = mapped_column(Float)
    volatility: Mapped[float] = mapped_column(Float)
    maximum_drawdown: Mapped[float] = mapped_column(Float)
    win_rate: Mapped[float] = mapped_column(Float)
    profit_factor: Mapped[float] = mapped_column(Float)
    trade_count: Mapped[int] = mapped_column(Integer)
    exposure: Mapped[float] = mapped_column(Float)
    turnover: Mapped[float] = mapped_column(Float)
    backtest: Mapped[BacktestModel] = relationship(back_populates="metrics")


class TradeModel(Base):
    __tablename__ = "completed_trades"
    __table_args__ = (UniqueConstraint("backtest_id", "ordinal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[UUID] = mapped_column(ForeignKey("backtests.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    side: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float] = mapped_column(Float)
    commission: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float)
    backtest: Mapped[BacktestModel] = relationship(back_populates="trades")


class SeriesPointModel(Base):
    __tablename__ = "backtest_series"
    __table_args__ = (
        UniqueConstraint("backtest_id", "ordinal"),
        UniqueConstraint("backtest_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[UUID] = mapped_column(ForeignKey("backtests.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    equity: Mapped[float] = mapped_column(Float)
    drawdown: Mapped[float] = mapped_column(Float)
    backtest: Mapped[BacktestModel] = relationship(back_populates="points")

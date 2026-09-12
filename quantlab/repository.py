from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import pandas as pd
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload, sessionmaker

from .backtest import BacktestResult, TRADE_COLUMNS
from .db_models import (
    BacktestModel,
    DatasetBarModel,
    DatasetModel,
    MetricModel,
    SeriesPointModel,
    TradeModel,
    UserModel,
)


METRIC_NAMES = (
    "total_return", "cumulative_return", "annualized_return", "cagr",
    "sharpe_ratio", "sortino_ratio", "volatility", "maximum_drawdown",
    "win_rate", "profit_factor", "trade_count", "exposure", "turnover",
)


class RepositoryError(Exception):
    pass


class RecordNotFound(Exception):
    pass


class DuplicateUserRecord(Exception):
    pass


class InvalidPersistenceState(RepositoryError):
    pass


@dataclass(frozen=True)
class UserRecord:
    id: UUID
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PersistedBacktest:
    id: UUID
    dataset_id: UUID
    strategy_name: str
    strategy_parameters: dict[str, int]
    backtest_parameters: dict[str, float | int]
    result: BacktestResult
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class BacktestSummary:
    id: UUID
    dataset_id: UUID
    strategy_name: str
    strategy_parameters: dict[str, int]
    created_at: datetime
    updated_at: datetime


class SQLAlchemyRepository:
    def __init__(self, sessions: sessionmaker):
        self.sessions = sessions

    def ping(self) -> None:
        try:
            with self.sessions() as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc

    def create_user(self, email: str, password_hash: str) -> UserRecord:
        try:
            with self.sessions.begin() as session:
                user = UserModel(email=email, password_hash=password_hash)
                session.add(user)
                session.flush()
                return self._user_record(user)
        except IntegrityError:
            raise DuplicateUserRecord("Email already exists") from None
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc

    def find_user_by_email(self, email: str) -> UserRecord | None:
        try:
            with self.sessions() as session:
                user = session.scalar(select(UserModel).where(UserModel.email == email))
                return self._user_record(user) if user else None
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc

    def get_user(self, identifier: UUID) -> UserRecord:
        try:
            with self.sessions() as session:
                user = session.get(UserModel, identifier)
                if user is None:
                    raise RecordNotFound("User not found")
                return self._user_record(user)
        except RecordNotFound:
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc

    def save_dataset(self, frame: pd.DataFrame, owner_id: UUID) -> UUID:
        try:
            with self.sessions.begin() as session:
                record = DatasetModel(
                    owner_id=owner_id,
                    row_count=len(frame), start_at=frame.index[0].to_pydatetime(),
                    end_at=frame.index[-1].to_pydatetime(),
                )
                record.bars = [DatasetBarModel(
                    ordinal=ordinal, timestamp=timestamp.to_pydatetime(),
                    **{name: float(row[name]) for name in ("open", "high", "low", "close", "volume")},
                ) for ordinal, (timestamp, row) in enumerate(frame.iterrows())]
                session.add(record)
                session.flush()
                identifier = record.id
            return identifier
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc

    def get_dataset(self, identifier: UUID, owner_id: UUID) -> pd.DataFrame:
        try:
            with self.sessions() as session:
                record = session.scalar(select(DatasetModel).where(
                    DatasetModel.id == identifier, DatasetModel.owner_id == owner_id,
                ).options(selectinload(DatasetModel.bars)))
                if record is None:
                    raise RecordNotFound("Dataset not found")
                if (
                    record.row_count != len(record.bars) or not record.bars
                    or [bar.ordinal for bar in record.bars] != list(range(record.row_count))
                ):
                    raise InvalidPersistenceState("Stored dataset is incomplete")
                rows = [{
                    "timestamp": bar.timestamp, "open": bar.open, "high": bar.high,
                    "low": bar.low, "close": bar.close, "volume": bar.volume,
                } for bar in record.bars]
        except (RecordNotFound, InvalidPersistenceState):
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc
        frame = pd.DataFrame(rows).set_index("timestamp")
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True), name="timestamp")
        return frame

    def save_backtest(
        self, dataset_id: UUID, owner_id: UUID, strategy_name: str, strategy_parameters: dict[str, int],
        backtest_parameters: dict[str, float | int], result: BacktestResult,
    ) -> UUID:
        try:
            with self.sessions.begin() as session:
                record = BacktestModel(
                    dataset_id=dataset_id, owner_id=owner_id, strategy_name=strategy_name,
                    strategy_parameters=strategy_parameters, backtest_parameters=backtest_parameters,
                    result_row_count=len(result.frame), result_start_at=result.frame.index[0].to_pydatetime(),
                    result_end_at=result.frame.index[-1].to_pydatetime(), status="completed",
                )
                record.metrics = MetricModel(**result.metrics)
                record.points = [SeriesPointModel(
                    ordinal=ordinal, timestamp=timestamp.to_pydatetime(),
                    equity=float(row["equity"]), drawdown=float(row["drawdown"]),
                ) for ordinal, (timestamp, row) in enumerate(result.frame.iterrows())]
                record.trades = [TradeModel(
                    ordinal=ordinal, entry_time=pd.Timestamp(row["entry_time"]).to_pydatetime(),
                    exit_time=pd.Timestamp(row["exit_time"]).to_pydatetime(), side=int(row["side"]),
                    quantity=float(row["quantity"]), entry_price=float(row["entry_price"]),
                    exit_price=float(row["exit_price"]), commission=float(row["commission"]), pnl=float(row["pnl"]),
                ) for ordinal, row in result.trades.iterrows()]
                session.add(record)
                session.flush()
                identifier = record.id
            return identifier
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc

    def get_backtest(self, identifier: UUID, owner_id: UUID) -> PersistedBacktest:
        try:
            with self.sessions() as session:
                record = session.scalar(
                    select(BacktestModel).where(
                        BacktestModel.id == identifier, BacktestModel.owner_id == owner_id,
                    ).options(
                        selectinload(BacktestModel.metrics), selectinload(BacktestModel.trades),
                        selectinload(BacktestModel.points),
                    )
                )
                if record is None:
                    raise RecordNotFound("Backtest not found")
                return self._materialize(record)
        except (RecordNotFound, InvalidPersistenceState):
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc

    def list_backtests(self, owner_id: UUID) -> list[BacktestSummary]:
        try:
            with self.sessions() as session:
                records = session.scalars(select(BacktestModel).where(
                    BacktestModel.owner_id == owner_id,
                ).order_by(BacktestModel.created_at, BacktestModel.id)).all()
                return [BacktestSummary(
                    id=row.id, dataset_id=row.dataset_id, strategy_name=row.strategy_name,
                    strategy_parameters=dict(row.strategy_parameters),
                    created_at=self._aware(row.created_at), updated_at=self._aware(row.updated_at),
                ) for row in records]
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc

    def delete_backtest(self, identifier: UUID, owner_id: UUID) -> None:
        try:
            with self.sessions.begin() as session:
                affected = session.execute(delete(BacktestModel).where(
                    BacktestModel.id == identifier, BacktestModel.owner_id == owner_id,
                )).rowcount
                if not affected:
                    raise RecordNotFound("Backtest not found")
        except RecordNotFound:
            raise
        except SQLAlchemyError as exc:
            raise RepositoryError("Database operation failed") from exc

    @staticmethod
    def _user_record(user: UserModel) -> UserRecord:
        return UserRecord(
            user.id, user.email, user.password_hash,
            SQLAlchemyRepository._aware(user.created_at), SQLAlchemyRepository._aware(user.updated_at),
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _materialize(record: BacktestModel) -> PersistedBacktest:
        if record.status != "completed" or record.metrics is None or record.result_row_count != len(record.points) or not record.points:
            raise InvalidPersistenceState("Stored backtest is incomplete")
        if [point.ordinal for point in record.points] != list(range(record.result_row_count)):
            raise InvalidPersistenceState("Stored backtest series is inconsistent")
        index = pd.DatetimeIndex(pd.to_datetime([point.timestamp for point in record.points], utc=True), name="timestamp")
        if index.has_duplicates or not index.is_monotonic_increasing:
            raise InvalidPersistenceState("Stored backtest timestamps are inconsistent")
        frame = pd.DataFrame({
            "equity": [point.equity for point in record.points],
            "drawdown": [point.drawdown for point in record.points],
        }, index=index)
        trades = pd.DataFrame([{
            "entry_time": pd.Timestamp(row.entry_time, tz="UTC") if row.entry_time.tzinfo is None else pd.Timestamp(row.entry_time),
            "exit_time": pd.Timestamp(row.exit_time, tz="UTC") if row.exit_time.tzinfo is None else pd.Timestamp(row.exit_time),
            "side": row.side, "quantity": row.quantity, "entry_price": row.entry_price,
            "exit_price": row.exit_price, "commission": row.commission, "pnl": row.pnl,
        } for row in record.trades], columns=TRADE_COLUMNS)
        metrics = {name: getattr(record.metrics, name) for name in METRIC_NAMES}
        if any(value is None or pd.isna(value) for value in metrics.values()):
            raise InvalidPersistenceState("Stored metrics are incomplete")
        metrics["trade_count"] = int(metrics["trade_count"])
        if metrics["trade_count"] != len(trades):
            raise InvalidPersistenceState("Stored trade count is inconsistent")
        return PersistedBacktest(
            id=record.id, dataset_id=record.dataset_id, strategy_name=record.strategy_name,
            strategy_parameters=dict(record.strategy_parameters), backtest_parameters=dict(record.backtest_parameters),
            result=BacktestResult(frame=frame, metrics=metrics, trades=trades),
            created_at=SQLAlchemyRepository._aware(record.created_at),
            updated_at=SQLAlchemyRepository._aware(record.updated_at),
        )

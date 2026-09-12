from dataclasses import dataclass
import os
from uuid import UUID

import pandas as pd
from pydantic import ValidationError

from quantlab.backtest import BacktestResult, compare, run_backtest
from quantlab.database import create_database
from quantlab.data import validate_ohlcv
from quantlab.repository import (
    BacktestSummary,
    InvalidPersistenceState,
    RecordNotFound,
    RepositoryError,
    SQLAlchemyRepository,
)
from quantlab.strategies import moving_average_crossover

from .models import BacktestParameters, MovingAverageParameters, OHLCVBar, StrategyConfig


class ApiInputError(Exception):
    pass


class ResourceNotFound(Exception):
    pass


class PersistenceError(Exception):
    pass


@dataclass(frozen=True)
class StoredBacktest:
    dataset_id: UUID
    strategy: StrategyConfig
    result: BacktestResult


class QuantService:
    """Validate API input and delegate every calculation to the quant engine."""

    def __init__(
        self, repository: SQLAlchemyRepository | None = None, *, database_url: str | None = None,
        initialize_schema: bool = False,
    ) -> None:
        if repository is None:
            _, sessions = create_database(database_url, initialize=initialize_schema)
            repository = SQLAlchemyRepository(sessions)
        self.repository = repository

    def upload_dataset(self, bars: list[OHLCVBar], owner_id: UUID) -> tuple[UUID, pd.DataFrame]:
        max_bars = int(os.getenv("MAX_DATASET_BARS", "100000"))
        if len(bars) > max_bars:
            raise ApiInputError(f"Dataset exceeds the {max_bars:,}-bar limit")
        frame = pd.DataFrame([bar.model_dump() for bar in bars]).set_index("timestamp")
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True), name="timestamp")
        try:
            validate_ohlcv(frame)
        except ValueError as exc:
            raise ApiInputError(str(exc)) from None
        try:
            dataset_id = self.repository.save_dataset(frame, owner_id)
        except RepositoryError:
            raise PersistenceError("Database operation failed") from None
        return dataset_id, frame

    def health(self) -> None:
        try:
            self.repository.ping()
        except RepositoryError:
            raise PersistenceError("Database operation failed") from None

    @staticmethod
    def strategies() -> list[dict[str, object]]:
        return [{
            "name": "moving_average_crossover",
            "description": "Long when the fast closing-price average exceeds the slow average; otherwise cash.",
            "parameters": {"fast_window": "positive integer", "slow_window": "integer greater than fast_window"},
        }]

    def run(
        self, dataset_id: UUID, strategy: StrategyConfig, parameters: BacktestParameters, owner_id: UUID,
    ) -> tuple[UUID, StoredBacktest]:
        data = self._dataset(dataset_id, owner_id)
        if strategy.name != "moving_average_crossover":
            raise ApiInputError(f"Unknown strategy: {strategy.name}")
        try:
            parsed = MovingAverageParameters.model_validate(strategy.parameters)
        except ValidationError as exc:
            messages = "; ".join(error["msg"] for error in exc.errors(include_url=False))
            raise ApiInputError(f"Invalid strategy parameters: {messages}") from None
        try:
            signal = moving_average_crossover(data, **parsed.model_dump())
            result = run_backtest(data, signal, **parameters.model_dump())
        except ValueError as exc:
            raise ApiInputError(str(exc)) from None
        normalized_strategy = StrategyConfig(name=strategy.name, parameters=parsed.model_dump())
        try:
            backtest_id = self.repository.save_backtest(
                dataset_id, owner_id, strategy.name, parsed.model_dump(), parameters.model_dump(), result
            )
        except RepositoryError:
            raise PersistenceError("Database operation failed") from None
        stored = StoredBacktest(dataset_id, normalized_strategy, result)
        return backtest_id, stored

    def result(self, backtest_id: UUID, owner_id: UUID) -> StoredBacktest:
        try:
            stored = self.repository.get_backtest(backtest_id, owner_id)
        except RecordNotFound:
            raise ResourceNotFound("Backtest not found") from None
        except (RepositoryError, InvalidPersistenceState):
            raise PersistenceError("Stored backtest is unavailable") from None
        return StoredBacktest(
            stored.dataset_id,
            StrategyConfig(name=stored.strategy_name, parameters=stored.strategy_parameters),
            stored.result,
        )

    def list_backtests(self, owner_id: UUID) -> list[BacktestSummary]:
        try:
            return self.repository.list_backtests(owner_id)
        except RepositoryError:
            raise PersistenceError("Database operation failed") from None

    def delete_backtest(self, backtest_id: UUID, owner_id: UUID) -> None:
        try:
            self.repository.delete_backtest(backtest_id, owner_id)
        except RecordNotFound:
            raise ResourceNotFound("Backtest not found") from None
        except RepositoryError:
            raise PersistenceError("Database operation failed") from None

    def comparison(self, backtest_ids: list[UUID], owner_id: UUID) -> pd.DataFrame:
        if len(set(backtest_ids)) != len(backtest_ids):
            raise ApiInputError("backtest_ids must be unique")
        results = {str(identifier): self.result(identifier, owner_id).result for identifier in backtest_ids}
        return compare(results)

    def _dataset(self, dataset_id: UUID, owner_id: UUID) -> pd.DataFrame:
        try:
            return self.repository.get_dataset(dataset_id, owner_id)
        except RecordNotFound:
            raise ResourceNotFound("Dataset not found") from None
        except (RepositoryError, InvalidPersistenceState):
            raise PersistenceError("Stored dataset is unavailable") from None

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PositiveInt, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class RegisterRequest(ApiModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=12, max_length=128)]


class LoginRequest(ApiModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class TokenResponse(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserResponse(ApiModel):
    id: UUID
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class OHLCVBar(ApiModel):
    timestamp: datetime
    open: Annotated[float, Field(gt=0)]
    high: Annotated[float, Field(gt=0)]
    low: Annotated[float, Field(gt=0)]
    close: Annotated[float, Field(gt=0)]
    volume: Annotated[float, Field(ge=0)]


class DatasetUpload(ApiModel):
    bars: Annotated[list[OHLCVBar], Field(min_length=1, max_length=100_000)]

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "bars": [
                    {"timestamp": "2024-01-02T00:00:00Z", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1_000_000},
                    {"timestamp": "2024-01-03T00:00:00Z", "open": 101, "high": 103, "low": 100, "close": 102, "volume": 1_100_000},
                ]
            }]
        }
    }


class DatasetResponse(ApiModel):
    dataset_id: UUID
    rows: int
    start: datetime
    end: datetime


class MovingAverageParameters(ApiModel):
    fast_window: PositiveInt = 20
    slow_window: PositiveInt = 50

    @model_validator(mode="after")
    def validate_windows(self):
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        return self


class StrategyConfig(ApiModel):
    name: str = Field(examples=["moving_average_crossover"])
    parameters: dict[str, int] = Field(
        default_factory=dict, examples=[{"fast_window": 20, "slow_window": 80}]
    )


class BacktestParameters(ApiModel):
    initial_capital: Annotated[float, Field(gt=0)] = 10_000
    transaction_cost_bps: Annotated[float, Field(ge=0, lt=10_000)] = 0
    slippage_bps: Annotated[float, Field(ge=0, lt=10_000)] = 0
    periods_per_year: PositiveInt = 252


class BacktestRequest(ApiModel):
    dataset_id: UUID
    strategy: StrategyConfig
    backtest: BacktestParameters = Field(default_factory=BacktestParameters)

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "dataset_id": "00000000-0000-0000-0000-000000000001",
                "strategy": {"name": "moving_average_crossover", "parameters": {"fast_window": 20, "slow_window": 80}},
                "backtest": {"initial_capital": 10000, "transaction_cost_bps": 5, "slippage_bps": 2, "periods_per_year": 252},
            }]
        }
    }


class MetricsResponse(ApiModel):
    total_return: float
    cumulative_return: float
    annualized_return: float
    cagr: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    volatility: float | None
    maximum_drawdown: float
    win_rate: float
    profit_factor: float | None
    trade_count: int
    exposure: float
    turnover: float


class BacktestResponse(ApiModel):
    backtest_id: UUID
    dataset_id: UUID
    strategy: StrategyConfig
    metrics: MetricsResponse


class BacktestSummaryResponse(ApiModel):
    backtest_id: UUID
    dataset_id: UUID
    strategy: StrategyConfig
    created_at: datetime
    updated_at: datetime


class StrategyInfo(ApiModel):
    name: str
    description: str
    parameters: dict[str, str]


class EquityPoint(ApiModel):
    timestamp: datetime
    equity: float


class DrawdownPoint(ApiModel):
    timestamp: datetime
    drawdown: float


class TradeResponse(ApiModel):
    entry_time: datetime
    exit_time: datetime
    side: Literal[-1, 1]
    quantity: float
    entry_price: float
    exit_price: float
    commission: float
    pnl: float


class ComparisonRequest(ApiModel):
    backtest_ids: Annotated[list[UUID], Field(min_length=2, max_length=25)]


class ComparisonItem(ApiModel):
    backtest_id: UUID
    metrics: MetricsResponse


class ComparisonResponse(ApiModel):
    results: list[ComparisonItem]

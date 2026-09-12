import math
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from quantlab.repository import UserRecord

from .dependencies import current_user
from .models import (
    BacktestRequest,
    BacktestResponse,
    BacktestSummaryResponse,
    ComparisonItem,
    ComparisonRequest,
    ComparisonResponse,
    DatasetResponse,
    DatasetUpload,
    DrawdownPoint,
    EquityPoint,
    MetricsResponse,
    StrategyConfig,
    StrategyInfo,
    TradeResponse,
)
from .service import QuantService


router = APIRouter()


def get_service(request: Request) -> QuantService:
    return request.app.state.quant_service


def metrics_response(metrics: dict[str, float]) -> MetricsResponse:
    safe = {key: value if math.isfinite(value) else None for key, value in metrics.items()}
    return MetricsResponse.model_validate(safe)


@router.get("/health", summary="Check service and database health", tags=["system"])
def health(service: QuantService = Depends(get_service)) -> dict[str, str]:
    service.health()
    return {"status": "ok"}


@router.post(
    "/datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and validate OHLCV bars",
    description="Stores validated chronological OHLCV data in the configured database and returns its identifier.",
    tags=["datasets"],
)
def upload_dataset(
    payload: DatasetUpload, service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> DatasetResponse:
    dataset_id, frame = service.upload_dataset(payload.bars, user.id)
    return DatasetResponse(dataset_id=dataset_id, rows=len(frame), start=frame.index[0], end=frame.index[-1])


@router.get("/strategies", response_model=list[StrategyInfo], summary="List available strategies", tags=["strategies"])
def list_strategies(service: QuantService = Depends(get_service)) -> list[StrategyInfo]:
    return [StrategyInfo.model_validate(item) for item in service.strategies()]


@router.post(
    "/backtests",
    response_model=BacktestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a backtest",
    description="Runs the validated next-open cash/share engine and stores the result persistently.",
    tags=["backtests"],
)
def create_backtest(
    payload: BacktestRequest, service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> BacktestResponse:
    backtest_id, stored = service.run(payload.dataset_id, payload.strategy, payload.backtest, user.id)
    return BacktestResponse(
        backtest_id=backtest_id,
        dataset_id=stored.dataset_id,
        strategy=stored.strategy,
        metrics=metrics_response(stored.result.metrics),
    )


@router.get("/backtests", response_model=list[BacktestSummaryResponse], summary="List saved backtests", tags=["backtests"])
def list_backtests(
    service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> list[BacktestSummaryResponse]:
    return [BacktestSummaryResponse(
        backtest_id=row.id, dataset_id=row.dataset_id,
        strategy=StrategyConfig(name=row.strategy_name, parameters=row.strategy_parameters),
        created_at=row.created_at, updated_at=row.updated_at,
    ) for row in service.list_backtests(user.id)]


@router.get("/backtests/{backtest_id}", response_model=BacktestResponse, summary="Get a saved backtest", tags=["backtests"])
def get_backtest(
    backtest_id: UUID, service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> BacktestResponse:
    stored = service.result(backtest_id, user.id)
    return BacktestResponse(
        backtest_id=backtest_id, dataset_id=stored.dataset_id,
        strategy=stored.strategy, metrics=metrics_response(stored.result.metrics),
    )


@router.post("/backtests/compare", response_model=ComparisonResponse, summary="Compare backtest metrics", tags=["backtests"])
def compare_backtests(
    payload: ComparisonRequest, service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> ComparisonResponse:
    table = service.comparison(payload.backtest_ids, user.id)
    return ComparisonResponse(results=[
        ComparisonItem(backtest_id=UUID(identifier), metrics=metrics_response(row.to_dict()))
        for identifier, row in table.iterrows()
    ])


@router.get("/backtests/{backtest_id}/metrics", response_model=MetricsResponse, summary="Get performance metrics", tags=["results"])
def get_metrics(
    backtest_id: UUID, service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> MetricsResponse:
    return metrics_response(service.result(backtest_id, user.id).result.metrics)


@router.get("/backtests/{backtest_id}/equity", response_model=list[EquityPoint], summary="Get the equity curve", tags=["results"])
def get_equity(
    backtest_id: UUID, service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> list[EquityPoint]:
    frame = service.result(backtest_id, user.id).result.frame
    return [EquityPoint(timestamp=timestamp, equity=value) for timestamp, value in frame["equity"].items()]


@router.get("/backtests/{backtest_id}/drawdown", response_model=list[DrawdownPoint], summary="Get the drawdown series", tags=["results"])
def get_drawdown(
    backtest_id: UUID, service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> list[DrawdownPoint]:
    frame = service.result(backtest_id, user.id).result.frame
    return [DrawdownPoint(timestamp=timestamp, drawdown=value) for timestamp, value in frame["drawdown"].items()]


@router.get("/backtests/{backtest_id}/trades", response_model=list[TradeResponse], summary="Get completed trades", tags=["results"])
def get_trades(
    backtest_id: UUID, service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> list[TradeResponse]:
    trades = service.result(backtest_id, user.id).result.trades
    return [TradeResponse.model_validate(row) for row in trades.to_dict(orient="records")]


@router.delete("/backtests/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a saved backtest", tags=["backtests"])
def delete_backtest(
    backtest_id: UUID, service: QuantService = Depends(get_service), user: UserRecord = Depends(current_user),
) -> Response:
    service.delete_backtest(backtest_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

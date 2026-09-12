from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from .data import validate_ohlcv


TRADE_COLUMNS = ("entry_time", "exit_time", "side", "quantity", "entry_price", "exit_price", "commission", "pnl")


@dataclass(frozen=True)
class BacktestResult:
    frame: pd.DataFrame
    metrics: dict[str, float]
    trades: pd.DataFrame


def _metrics(
    returns: pd.Series,
    turnover: pd.Series,
    periods_per_year: int,
    *,
    trades: pd.DataFrame | None = None,
    positions: pd.Series | None = None,
    elapsed_years: float | None = None,
) -> dict[str, float]:
    count = len(returns)
    total_return = float((1 + returns).prod() - 1)
    with np.errstate(over="ignore", invalid="ignore"):
        annualized_return = (
            float(np.expm1(np.log1p(total_return) * periods_per_year / count))
            if count and total_return > -1 else total_return
        )
        cagr = (
            float(np.expm1(np.log1p(total_return) / elapsed_years))
            if elapsed_years and elapsed_years > 0 and total_return > -1 else float("nan")
        )
    if count < 2:
        volatility = sharpe = sortino = float("nan")
    else:
        standard_deviation = float(returns.std(ddof=1))
        mean_return = float(returns.mean())
        zero_volatility = np.isclose(standard_deviation, 0.0, atol=1e-15)
        sharpe = (
            float(np.sign(mean_return) * np.inf) if zero_volatility and mean_return
            else 0.0 if zero_volatility
            else float(mean_return / standard_deviation * sqrt(periods_per_year))
        )
        downside_deviation = float(np.sqrt(np.mean(np.minimum(returns, 0.0) ** 2)))
        sortino = (
            float(mean_return / downside_deviation * sqrt(periods_per_year))
            if not np.isclose(downside_deviation, 0.0, atol=1e-15)
            else (float("inf") if mean_return > 0 else 0.0)
        )
        volatility = standard_deviation * sqrt(periods_per_year)

    compounded = (1 + returns).cumprod()
    peaks = np.maximum.accumulate(np.concatenate(([1.0], compounded.to_numpy())))
    maximum_drawdown = float((compounded.to_numpy() / peaks[1:] - 1).min()) if count else 0.0
    trades = trades if trades is not None else pd.DataFrame(columns=TRADE_COLUMNS)
    pnls = trades["pnl"] if "pnl" in trades else pd.Series(dtype=float)
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    profit_factor = (
        float(wins.sum() / -losses.sum()) if len(losses)
        else float("inf") if len(wins)
        else 0.0
    )
    return {
        "total_return": total_return,
        "cumulative_return": total_return,
        "annualized_return": float(annualized_return),
        "cagr": float(cagr),
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "volatility": float(volatility),
        "maximum_drawdown": maximum_drawdown,
        "win_rate": float((pnls > 0).mean()) if len(pnls) else 0.0,
        "profit_factor": profit_factor,
        "trade_count": int(len(trades)),
        "exposure": float((positions != 0).mean()) if positions is not None and len(positions) else 0.0,
        "turnover": float(turnover.sum()),
    }


def _validate_frequency(index: pd.DatetimeIndex, periods_per_year: int) -> None:
    if periods_per_year == 252 and len(index) > 1:
        expected = pd.bdate_range(index[0], index[-1], tz=index.tz)
        if not index.equals(expected):
            raise ValueError("Daily data must contain every weekday; clean missing sessions explicitly")


def _empty_trades() -> pd.DataFrame:
    return pd.DataFrame(columns=TRADE_COLUMNS)


def run_backtest(
    data: pd.DataFrame,
    signal: pd.Series,
    *,
    initial_capital: float = 10_000.0,
    transaction_cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    periods_per_year: int = 252,
) -> BacktestResult:
    """Execute close-derived target sides at the next open using a cash/share ledger."""
    validate_ohlcv(data)
    parameters = (initial_capital, transaction_cost_bps, slippage_bps, periods_per_year)
    if not all(np.isfinite(value) for value in parameters):
        raise ValueError("Backtest parameters must be finite")
    if initial_capital <= 0 or min(transaction_cost_bps, slippage_bps) < 0:
        raise ValueError("Capital must be positive and costs non-negative")
    if transaction_cost_bps >= 10_000 or slippage_bps >= 10_000:
        raise ValueError("Commission and slippage must each be below 100%")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    _validate_frequency(data.index, periods_per_year)

    if signal.index.has_duplicates:
        raise ValueError("Signal timestamps must be unique")
    target = signal.reindex(data.index)
    if target.isna().any() or (~target.isin([-1.0, 0.0, 1.0])).any():
        raise ValueError("Signal must align with data and contain only -1, 0, or 1")
    warmup = int(signal.attrs.get("warmup_periods", 0))
    if warmup and len(data) <= warmup + 1:
        raise ValueError("Insufficient history for strategy warm-up and execution")

    frame = data.copy()
    frame["signal"] = target.astype(float)
    asset_return = frame["close"].pct_change().fillna(0.0)
    if not np.isfinite(asset_return.to_numpy()).all():
        raise ValueError("Price changes produce non-finite returns")

    commission_rate = transaction_cost_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    cash, shares = float(initial_capital), 0.0
    open_trade: dict[str, object] | None = None
    trade_rows: list[dict[str, object]] = []
    rows: list[dict[str, float]] = []
    previous_equity = float(initial_capital)

    for position_number, (timestamp, bar) in enumerate(frame.iterrows()):
        commission = slippage_cost = traded_notional = turnover = 0.0
        if position_number:
            open_price = float(bar["open"])
            equity_before_trade = cash + shares * open_price
            if not np.isfinite(equity_before_trade) or equity_before_trade <= 0:
                raise ValueError("A period loss exhausts capital")
            target_side = int(frame["signal"].iloc[position_number - 1])
            current_side = int(np.sign(shares))
            if target_side != current_side:
                if shares:
                    quantity = abs(shares)
                    fill = open_price * (1 - slippage_rate if shares > 0 else 1 + slippage_rate)
                    notional = quantity * fill
                    fee = notional * commission_rate
                    cash += notional - fee if shares > 0 else -(notional + fee)
                    commission += fee
                    slippage_cost += quantity * abs(fill - open_price)
                    traded_notional += quantity * open_price
                    entry = open_trade or {}
                    gross_pnl = quantity * (
                        fill - float(entry["entry_price"]) if shares > 0
                        else float(entry["entry_price"]) - fill
                    )
                    trade_rows.append({
                        "entry_time": entry["entry_time"], "exit_time": timestamp,
                        "side": current_side, "quantity": quantity,
                        "entry_price": entry["entry_price"], "exit_price": fill,
                        "commission": float(entry["entry_commission"]) + fee,
                        "pnl": gross_pnl - float(entry["entry_commission"]) - fee,
                    })
                    shares, open_trade = 0.0, None
                    if not np.isfinite(cash) or cash <= 0:
                        raise ValueError("Closing a position exhausts capital")

                if target_side:
                    fill = open_price * (1 + slippage_rate if target_side > 0 else 1 - slippage_rate)
                    quantity = cash / (fill * (1 + commission_rate))
                    if not np.isfinite(quantity) or quantity <= 0:
                        raise ValueError("Position size is infeasible")
                    notional = quantity * fill
                    fee = notional * commission_rate
                    cash += -(notional + fee) if target_side > 0 else notional - fee
                    shares = target_side * quantity
                    commission += fee
                    slippage_cost += quantity * abs(fill - open_price)
                    traded_notional += quantity * open_price
                    open_trade = {"entry_time": timestamp, "entry_price": fill, "entry_commission": fee}
                turnover = traded_notional / equity_before_trade
                equity_after_trade = cash + shares * open_price
                if not np.isfinite(equity_after_trade) or equity_after_trade <= 0:
                    raise ValueError("Execution costs exhaust capital at the fill")

        equity = cash + shares * float(bar["close"])
        strategy_return = equity / previous_equity - 1 if position_number else 0.0
        derived = (cash, shares, equity, strategy_return, commission, slippage_cost, turnover)
        if not all(np.isfinite(value) for value in derived):
            raise ValueError("Backtest produced non-finite accounting values")
        if equity <= 0 or strategy_return <= -1:
            raise ValueError("A period loss exhausts capital")
        rows.append({
            "position": float(np.sign(shares)), "shares": shares, "cash": cash,
            "asset_return": float(asset_return.iloc[position_number]),
            "traded_notional": traded_notional, "commission": commission,
            "slippage": slippage_cost, "cost": commission + slippage_cost,
            "turnover": turnover, "strategy_return": strategy_return, "equity": equity,
        })
        previous_equity = equity

    accounting = pd.DataFrame(rows, index=frame.index)
    frame = pd.concat([frame, accounting], axis=1)
    frame["drawdown"] = frame["equity"] / frame["equity"].cummax().clip(lower=initial_capital) - 1
    trades = pd.DataFrame(trade_rows, columns=TRADE_COLUMNS) if trade_rows else _empty_trades()
    returns = frame["strategy_return"].iloc[1:]
    elapsed_years = (frame.index[-1] - frame.index[0]).total_seconds() / (365.2425 * 86_400)
    metrics = _metrics(
        returns, frame["turnover"].iloc[1:], periods_per_year,
        trades=trades, positions=frame["position"].iloc[1:], elapsed_years=elapsed_years,
    )
    required_finite = (
        "total_return", "cumulative_return", "annualized_return", "cagr",
        "volatility", "maximum_drawdown", "exposure", "turnover",
    )
    if len(frame) > 2 and not all(np.isfinite(metrics[name]) for name in required_finite):
        raise ValueError("Backtest produced non-finite performance metrics")
    return BacktestResult(frame=frame, metrics=metrics, trades=trades)


def compare(results: dict[str, BacktestResult]) -> pd.DataFrame:
    """Compare named backtests with one metric per column."""
    return pd.DataFrame({name: result.metrics for name, result in results.items()}).T

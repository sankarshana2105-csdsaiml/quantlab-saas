"""Create persistent QuantLab storage."""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "datasets", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False), *timestamps(),
    )
    op.create_table(
        "dataset_bars", sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False), sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False), sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.UniqueConstraint("dataset_id", "ordinal"), sa.UniqueConstraint("dataset_id", "timestamp"),
    )
    op.create_index("ix_dataset_bars_dataset_id", "dataset_bars", ["dataset_id"])
    op.create_table(
        "backtests", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("strategy_parameters", sa.JSON(), nullable=False),
        sa.Column("backtest_parameters", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result_row_count", sa.Integer(), nullable=False),
        sa.Column("result_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result_end_at", sa.DateTime(timezone=True), nullable=False), *timestamps(),
    )
    op.create_index("ix_backtests_dataset_id", "backtests", ["dataset_id"])
    op.create_table(
        "performance_metrics", sa.Column("backtest_id", sa.Uuid(), sa.ForeignKey("backtests.id", ondelete="CASCADE"), primary_key=True),
        *[sa.Column(name, sa.Integer() if name == "trade_count" else sa.Float(), nullable=False) for name in (
            "total_return", "cumulative_return", "annualized_return", "cagr", "sharpe_ratio", "sortino_ratio",
            "volatility", "maximum_drawdown", "win_rate", "profit_factor", "trade_count", "exposure", "turnover",
        )],
    )
    op.create_table(
        "completed_trades", sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("backtest_id", sa.Uuid(), sa.ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False), sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("side", sa.Integer(), nullable=False), sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False), sa.Column("exit_price", sa.Float(), nullable=False),
        sa.Column("commission", sa.Float(), nullable=False), sa.Column("pnl", sa.Float(), nullable=False),
        sa.UniqueConstraint("backtest_id", "ordinal"),
    )
    op.create_index("ix_completed_trades_backtest_id", "completed_trades", ["backtest_id"])
    op.create_table(
        "backtest_series", sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("backtest_id", sa.Uuid(), sa.ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("equity", sa.Float(), nullable=False), sa.Column("drawdown", sa.Float(), nullable=False),
        sa.UniqueConstraint("backtest_id", "ordinal"), sa.UniqueConstraint("backtest_id", "timestamp"),
    )
    op.create_index("ix_backtest_series_backtest_id", "backtest_series", ["backtest_id"])


def downgrade() -> None:
    for table in ("backtest_series", "completed_trades", "performance_metrics", "backtests", "dataset_bars", "datasets"):
        op.drop_table(table)

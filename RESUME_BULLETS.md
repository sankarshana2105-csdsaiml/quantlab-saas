# QuantLab resume and interview notes

## FINAL_RECOMMENDED_RESUME_VERSION

- Built a Python-first quantitative research SaaS with a causally aligned next-open backtest ledger, explicit cash/share accounting, transaction costs, trade-level analytics, and leakage-safe walk-forward evaluation.
- Designed a modular FastAPI, SQLAlchemy 2.x, Alembic, and PostgreSQL backend with Argon2/JWT authentication, repository-enforced tenant isolation, persistent experiment results, and validated API contracts.
- Delivered a responsive React/TypeScript workflow for OHLCV validation, strategy configuration, interactive equity/drawdown analysis, saved experiments, and comparison; verified with 90+ automated backend/frontend checks.

## 30_SECOND_EXPLANATION

QuantLab is a full-stack research platform for uploading OHLCV data and running reproducible backtests. I focused on the failure modes that make trading results misleading: look-ahead, incorrect return ownership, short accounting, reversal costs, and trade-versus-period metrics. The validated Python engine sits behind a typed FastAPI service, PostgreSQL persistence, per-user authorization, and a React analysis UI.

## 2_MINUTE_INTERVIEW_EXPLANATION

The strategy produces a target side from information available at each close. The engine delays execution until the next open, keeps explicit cash and fixed share quantities, applies adverse slippage to fills, and charges commission on executed notional. Reversals are two economic legs. Equity is marked to market and completed-trade PnL drives win rate and profit factor. Independent ledger tests reconcile the deterministic sample within `1e-12`.

FastAPI routes validate requests and call a service layer; they never reimplement quant formulas. SQLAlchemy repositories atomically persist datasets, configurations, metrics, trades, and series. Alembic initializes SQLite for local work and PostgreSQL for production. Argon2 hashes passwords, JWT validation pins the algorithm and expiry, and owner IDs are enforced in repository queries. The React client consumes stored engine results directly and provides the upload-to-comparison workflow.

## Technologies

Python 3.12, pandas, NumPy, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, PostgreSQL, SQLite, Argon2, JWT, React 19, TypeScript, Vite, Recharts, pytest, and Vitest.

## Quantitative concepts

Execution timing, look-ahead bias, marked-to-market equity, share/notional accounting, compounding, turnover, slippage, commission, completed trades, drawdown, Sharpe/Sortino/Calmar, exposure, chronological splits, and walk-forward validation.

## Likely interview questions

1. Why does a close-time signal execute at the next open?
2. Which position owns the overnight return around an entry or exit?
3. Why is share-based short accounting safer than negating simple returns?
4. How are costs handled for a `+1` to `-1` reversal?
5. Why are win rate and profit factor computed from completed trades?
6. How did you independently reconcile the engine ledger?
7. How does walk-forward evaluation prevent parameter leakage?
8. Why enforce ownership in repository queries as well as routes?
9. How do Alembic migrations and ORM metadata serve different purposes?
10. What would you change for large datasets or production trading workloads?

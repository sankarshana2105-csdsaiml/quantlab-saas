# Learn QuantLab

## Practical study order

### MUST understand

1. `quantlab/backtest.py`: next-open timing, cash/share ledger, costs, reversals, completed trades, and metric formulas.
2. `quantlab/evaluation.py`: chronological splits, leakage prevention, walk-forward state, and OOS continuity.
3. `quantlab/data.py` and `quantlab/strategies.py`: OHLCV invariants, causal rolling signals, warm-up, and invalid inputs.
4. `quantlab/api/service.py` and `quantlab/repository.py`: one calculation path, atomic persistence, reconstruction, and owner-scoped access.
5. `quantlab/security.py`, `quantlab/auth.py`, and API dependencies: Argon2, expiring algorithm-pinned JWTs, and authorization boundaries.

### SHOULD understand

1. Pydantic contracts and FastAPI error handling in `quantlab/api/`.
2. SQLAlchemy relationships and Alembic revisions in `quantlab/db_models.py` and `migrations/`.
3. React data flow in `frontend/src/api.ts`, auth context, research, results, saved-run, and comparison pages.
4. Independent ledger reconciliation in `tests/test_phase1_audit.py` and persistence/API reconciliation tests.
5. Production configuration, CORS/host controls, upload limits, and database health checks.

### CAN understand later

1. Recharts presentation details and responsive CSS.
2. Render Blueprint mechanics and SPA rewrites.
3. Screenshot capture, synthetic sample generation, and secondary UI polish.
4. Deferred scaling options: background jobs, pagination/downsampling, refresh tokens, and rate limiting.

The sections below are the detailed file-by-file reference.

## `data.py`

- Does: cleans and validates timestamped OHLCV bars.
- Why: bad ordering, duplicates, missing values, and impossible prices invalidate research.
- Learn: OHLCV schema, time indexes, numeric coercion, validation boundaries.
- Interview questions: Why sort before backtesting? How do duplicates create bias? Drop or impute missing prices? Which OHLC relationships must hold?

## `strategies.py`

- Does: converts historical closes into target positions using moving averages.
- Why: separates a strategy's decision from execution and accounting.
- Learn: rolling windows, warm-up periods, causal signals, long/cash positions.
- Interview questions: Why can a rolling mean be causal? What is its warm-up period? Signal versus position? Why start with a simple strategy?

## `backtest.py`

- Does: delays signals, calculates positions, returns, costs, equity, drawdown, and metrics.
- Why: this is the experiment's financial accounting system.
- Learn: compounded returns, basis points, turnover, Sharpe/Sortino, drawdown, look-ahead bias.
- Interview questions: Why shift signals? How are costs charged? Arithmetic versus compounded return? How are Sharpe and Sortino different? What can inflate a backtest?
- Execution model: a close-t signal fills at open t+1. The old position owns the overnight gap; new shares earn only post-fill movement. Cash, fixed share quantity, fill notional, commission, and adverse slippage reconcile on every order. Reversals close one side before opening the other.
- Metric distinction: win rate and profit factor use completed net trade PnL. Open terminal positions remain in equity but do not count as completed trades. Sample volatility and Sharpe are undefined with fewer than two returns.
- Edge behavior: no trades produce zero ratios; profitable constant returns produce infinite Sharpe/Sortino rather than a divide-by-zero error; a period loss of 100% or more is rejected because the simple compounding model cannot represent post-bankruptcy trading.

## `evaluation.py`

- Does: runs chronological train/test and rolling walk-forward evaluations.
- Why: parameters must be chosen without seeing the period used to judge them.
- Learn: out-of-sample testing, rolling windows, parameter selection, leakage.
- Interview questions: Why not random-split market data? What is walk-forward testing? How can tuning leak test information? What does weak out-of-sample performance imply?
- Walk-forward model: indicator warm-up uses historical training observations, while the OOS account begins in cash and continues across folds. New parameters decided at a fold boundary execute at the next open, so entries, exits, and reversals all affect cash. Each custom-strategy call receives only the available prefix.

## `examples/sample_backtest.py`

- Does: creates deterministic synthetic OHLCV regimes and saves metrics plus price, equity, benchmark, and drawdown plots.
- Why: gives recruiters and developers one reproducible end-to-end demonstration without external data or API keys.
- Learn: seeded simulation, benchmark context, cost assumptions, reproducibility, honest interpretation of negative results.
- Interview questions: Why use synthetic data? Why compare against buy-and-hold? Why is negative performance still informative? Which assumptions make the example unrealistic?
- Audit status: the corrected sample returns -18.64%. An independent scalar next-open ledger reconciles all metrics, equity points, and closed trades within `1e-12`; the Phase 1 audit is PASS.

## `quantlab/api/models.py`

- Does: defines the public dataset, strategy, backtest, metric, curve, trade, and comparison contracts.
- Why: rejects malformed requests before they reach financial calculations and keeps OpenAPI accurate.
- Learn: Pydantic constraints, nested models, forbidden extra fields, schema examples, nullable non-finite ratios.
- Interview questions: Why validate both individual bars and the complete OHLCV frame? Why represent undefined or infinite ratios as `null` in JSON?

## `quantlab/api/service.py`

- Does: coordinates validation, the repository, and the Phase 1 engine without owning process-local state.
- Why: HTTP handlers should orchestrate requests, not recreate quantitative logic.
- Learn: service boundaries, dependency injection, domain-error translation, exact engine/API reconciliation.
- Interview questions: Why keep FastAPI out of the quant engine? Why place transactions below the service layer?

## `quantlab/api/routes.py` and `app.py`

- Does: exposes the API endpoints, response models, OpenAPI metadata, and safe exception responses.
- Why: transport concerns stay separate from validation, storage, and financial accounting.
- Learn: FastAPI routers, dependencies, status codes, response serialization, exception handlers, TestClient integration tests.
- Interview questions: Which failures are 422 versus 404? Why must unexpected exceptions return a generic 500? How do API tests prove the engine was not reimplemented?

## `database.py`, `db_models.py`, and `repository.py`

- Does: configures SQLAlchemy from `DATABASE_URL`, defines persistent records, and converts database rows to validated engine result objects.
- Why: persistence survives restarts while HTTP and quantitative concerns remain independent.
- Learn: SQLAlchemy 2.x sessions, UUID/JSON portability, relationships, cascades, atomic transactions, rollback, and repository boundaries.
- Interview questions: Why commit a backtest and all child results atomically? Why validate stored state during reconstruction? Why use SQLite only for isolated/local execution?

## `migrations/`

- Does: creates the complete Phase 3 schema from scratch through Alembic.
- Why: production schemas need versioned, repeatable changes rather than implicit table creation.
- Learn: migration revisions, upgrade/downgrade paths, metadata drift checks, and environment-based connection URLs.
- Interview questions: How do Alembic and ORM models differ? How do you prove a migration matches current metadata?

## `security.py` and `auth.py`

- Does: hashes passwords with Argon2 and issues/validates short-lived, algorithm-pinned JWT access tokens.
- Why: authentication secrets and credentials stay outside business and quant code.
- Learn: one-way password hashing, generic login failures, token expiry, environment secrets, and stateless authentication.
- Interview questions: Why hash instead of encrypt passwords? Why pin the JWT algorithm? Why is logout unnecessary without a revocation store?

## Ownership enforcement

- Does: scopes datasets and every backtest repository query by the authenticated user UUID.
- Why: route-only authorization is easy to bypass; the data-access boundary must enforce isolation.
- Learn: ownership foreign keys, non-enumerating 404 responses, tenant-scoped operations, and legacy-record migration.
- Interview questions: Why return 404 for another user's object? How do repository filters prevent insecure direct object references?

## `frontend/src/api.ts` and `auth-context.tsx`

- Does: centralizes typed API calls, bearer-token session storage, current-user state, logout, and expired-session recovery.
- Why: UI components never bypass backend authorization or duplicate financial calculations.
- Learn: API boundaries, 4xx error translation, protected routing, and short-lived browser sessions.
- Interview questions: Why use session storage here? Why must a 401 clear client state? Which security rules remain server-side?

## `frontend/src/pages/`

- Does: implements the landing, auth, research builder, results, saved research, deletion, and comparison journeys.
- Why: one focused workflow turns the validated engine into a demonstrable research SaaS.
- Learn: React routing, controlled forms, CSV ingestion, loading/error/empty states, responsive data tables, and lazy routes.
- Interview questions: Why validate CSV twice? Why chart raw API series instead of recomputing them? Which routes require authentication?

## `frontend/src/components/MetricGrid.tsx` and results charts

- Does: formats engine metrics and visualizes stored equity/drawdown series without changing their values.
- Why: presentation stays separate from accounting and preserves exact backend provenance.
- Learn: financial formatting, responsive charts, null metric handling, and execution-ledger presentation.
- Interview questions: Why can a ratio be undefined? Why show completed trades separately from daily returns?

## `quantlab/config.py` and production safety

- Does: validates environment mode, exact CORS origins, optional trusted hosts, token expiry, dataset limits, and PostgreSQL production configuration before serving traffic.
- Why: unsafe defaults should fail clearly at startup instead of silently reaching production.
- Learn: twelve-factor configuration, fail-fast validation, origin versus host controls, and bounded inputs.
- Interview questions: Why reject wildcard CORS? Why require PostgreSQL in production? Which values belong in environment variables?

## `render.yaml` and deployment

- Does: declares the PostgreSQL database, FastAPI service, migration/start command, health check, React static build, and SPA rewrite.
- Why: a reproducible deployment contract is safer than undocumented dashboard clicks.
- Learn: build-time versus runtime variables, ASGI startup, migrations, health checks, and client-side routing.
- Interview questions: Why run migrations before the API? Why does `VITE_API_URL` exist at build time? What should a health endpoint verify?

## PostgreSQL integration validation

- Does: the opt-in test recreates only a dedicated `quantlab_test` database, migrates it, verifies rollback, persists a sample run, recreates the service, and exactly reconciles stored output with the engine.
- Why: SQLite coverage cannot prove PostgreSQL UUID, timezone, JSON, transaction, and migration behavior.
- Learn: dialect portability, dedicated destructive test databases, transactional DDL, and restart verification.
- Interview questions: Which SQLite/PostgreSQL differences matter here? Why guard the test database name? What does exact persistence reconciliation prove?

## Phase 6 operational findings

- A 5,000-bar local SQLite sanity run took 0.540 s to upload, 0.952 s to calculate and persist, and 0.118 s to retrieve; series payload was roughly 407 KB.
- Quoted CSV fields now use a small RFC-style state machine; uploads are capped at 10 MB in the browser and 100,000 bars in both client and API validation.
- Stateless JWT revocation and large-series pagination remain intentional documented follow-ups rather than hidden production claims.

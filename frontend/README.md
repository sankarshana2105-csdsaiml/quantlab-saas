# QuantLab web

## Local development

1. Run the API on `http://127.0.0.1:8000` after `alembic upgrade head`.
2. Copy `.env.example` to `.env` only when overriding the `/api` proxy.
3. Install dependencies with `pnpm install`, then run `pnpm dev`.

The browser stores the short-lived access token in session storage. All datasets and results remain authorized by the FastAPI backend.

## Verification

- `pnpm test`
- `pnpm typecheck`
- `pnpm build`

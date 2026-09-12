# QuantLab deployment

Status: deployment-ready; a Git remote and Render account connection are required.

## One-time launch

1. Configure a Git author, commit this repository, create a private or public remote, and push `main`.
2. In Render, create a Blueprint from the repository's `render.yaml`.
3. Let Render generate `JWT_SECRET` and provision the Blueprint PostgreSQL database.
4. After Render assigns URLs, set API `CORS_ORIGINS` to the exact frontend origin and `ALLOWED_HOSTS` to the API hostname.
5. Set static-site `VITE_API_URL` to the API origin and redeploy the static site.
6. Confirm API `/health` returns `status: ok` and `database: ok`.

## Public acceptance flow

1. Register user A, upload `data/sample_ohlcv.csv`, run a backtest, and save its result ID.
2. Reload the site; confirm the result, metrics, trades, equity, and drawdown persist.
3. Register user B; confirm A's result is absent and direct read/delete attempts return 404.
4. Log back in as A; compare saved runs and delete one.
5. Confirm browser refresh routes work and no stack trace, secret, or internal database detail appears in errors.

## Exact Git commands

```bash
git config user.name "YOUR NAME"
git config user.email "YOUR EMAIL"
git add .
git commit -m "feat: complete QuantLab research SaaS"
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

Never commit `.env`; use `.env.example` only as the variable reference.

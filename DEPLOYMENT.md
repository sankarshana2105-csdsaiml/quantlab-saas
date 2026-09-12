# QuantLab deployment

Status: publicly deployed from [sankarshana2105-csdsaiml/quantlab-saas](https://github.com/sankarshana2105-csdsaiml/quantlab-saas).

- Frontend: https://quantlab-web.onrender.com
- Backend: https://quantlab-api-xhby.onrender.com
- Health: https://quantlab-api-xhby.onrender.com/health

## One-time launch

1. In Render, create a Blueprint from the public repository's `render.yaml`.
2. Let Render generate `JWT_SECRET` and provision the Blueprint PostgreSQL database.
3. After Render assigns URLs, set API `CORS_ORIGINS` to the exact frontend origin and `ALLOWED_HOSTS` to the API hostname.
4. Set static-site `VITE_API_URL` to the API origin and redeploy the static site.
5. Confirm API `/health` returns `status: ok` and `database: ok`.

## Public acceptance flow

1. Register user A, upload `data/sample_ohlcv.csv`, run a backtest, and save its result ID.
2. Reload the site; confirm the result, metrics, trades, equity, and drawdown persist.
3. Register user B; confirm A's result is absent and direct read/delete attempts return 404.
4. Log back in as A; compare saved runs and delete one.
5. Confirm browser refresh routes work and no stack trace, secret, or internal database detail appears in errors.

Never commit `.env`; use `.env.example` only as the variable reference.

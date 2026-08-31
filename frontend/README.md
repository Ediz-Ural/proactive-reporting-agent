# Frontend — Proactive Reporting Agent

React 19 + TypeScript + Vite dashboard for the reporting pipeline: login, pipeline
progress, KPI cards and charts, report viewer, and the admin panel (companies, users,
data upload).

## Development

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api to http://localhost:8000
```

The backend must be running (`uvicorn src.api:app --reload` from the project root).

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Type-check and build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | ESLint |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend base URL |

Set it in `frontend/.env.local` when the API runs elsewhere.

## Docker

`docker compose up -d` builds this app and serves `dist/` with nginx on
http://localhost:3000, proxying `/api/` to the `app` service (see `nginx.conf`).

## Structure

```
src/
├── api/          # axios client and typed API calls
├── components/   # Layout, Sidebar, KPICard, PipelineProgress, ReportViewer, charts
├── pages/        # Login, Dashboard, Pipeline, Reports, Settings, admin/
└── types/        # shared TypeScript types
```

# BharatVantage Frontend

React + Vite SPA. Connects to the Railway-deployed FastAPI backend.

## Stack
- React 18 + React Router v6
- Vite 5
- Tailwind CSS (dark mode, saffron design system)
- Recharts (revenue charts)
- Lucide React (icons)

## Quick start

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
# Opens at http://localhost:3000
```

Dev login: `dev@bharatvantage.local` / `DevPassword123`

## API connection

In dev, Vite proxies `/api` → `https://web-production-cea7d.up.railway.app`
so there are no CORS issues.

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/login` | LoginPage | Split-screen auth with identity panel |
| `/register` | RegisterPage | Account creation |
| `/dashboard` | DashboardPage | Metric overview, revenue chart |
| `/upload` | UploadPage | File upload → detect → confirm → compute |
| `/metrics/:sessionId` | MetricsPage | Full analytics report with insights |
| `/settings` | SettingsPage | Outlet config, commission rates |

## Auth flow

Matches backend exactly:
- `POST /auth/login` → stores `access_token` in sessionStorage
- Every API call includes `Authorization: Bearer <token>`
- Every API call to protected routes includes `X-Outlet-ID: <uuid>` header
- 401 response → auto-redirect to `/login`

## Deploy to Railway

```
# Add as a service in Railway
# Build command: npm run build
# Start command: npx serve dist
# Or deploy to Vercel with zero config
```

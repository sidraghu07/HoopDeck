# HoopDeck

HoopDeck is a basketball analytics app for exploring NBA and WNBA players. It renders pixel-art player cards with computed ratings and shot charts, and offers a lineup simulator and a trade machine that predicts on-court impact and checks trades against NBA CBA salary-cap rules.

Live app: https://hoop-deck.vercel.app

## Features

- **Player cards** — browse and search NBA/WNBA players by season, team, tier, and position, with per-game and advanced stats, shot-zone heat maps, and computed ratings (overall, scoring, playmaking, defense, impact).
- **Lineup simulator** — build a five-player lineup and get a predicted net rating, win percentage, and record from a Ridge regression model trained on historical roster composition.
- **Trade machine** — propose trades between two teams, including draft picks, and see:
  - CBA legality (salary matching, cap/tax/apron rules)
  - a fairness verdict based on player value
  - team fit (position needs, timeline, draft capital impact)
  - predicted lineup impact before and after the trade
- **Chart builder** — build custom stat comparison charts across players.
- Data covers NBA and WNBA across multiple seasons, including playoffs.

## Tech stack

**Backend**
- FastAPI + Uvicorn (Python 3.13)
- PostgreSQL via `psycopg`
- scikit-learn (lineup prediction model)
- `nba-api` / `basketball-reference-scraper` for data collection
- Dependency management via [uv](https://docs.astral.sh/uv/)

**Frontend**
- Next.js (App Router) + React
- TypeScript, Tailwind CSS
- Recharts for stat charts, GSAP/OGL for visual effects

## Project structure

```
api/          FastAPI backend (routers, trade/lineup engines, CBA rules, DB access)
frontend/     Next.js frontend (players, lineups, trades, charts)
data/         Scripts that scrape stats, build ratings, and load Postgres
.github/      Scheduled workflows that keep stats/rosters/salaries current
```

## Local development

### Prerequisites
- Python 3.13
- Node.js
- PostgreSQL

### Backend

```bash
uv sync
export DATABASE_URL=postgresql://localhost/nba_cards   # or leave unset for the default
uv run uvicorn api.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` to point at the backend (defaults to `http://localhost:8000`).

### Data pipeline

The `data/` scripts populate Postgres from the NBA API and Basketball Reference. Typical order for a fresh database:

```bash
uv run python data/generate_player_dataset.py
uv run python data/generate_team_dataset.py
uv run python data/generate_shot_dataset.py
uv run python data/build_card_data.py
uv run python data/fit_lineup_model.py
```

Set `LEAGUE=NBA` or `LEAGUE=WNBA` to control which league a script runs against. Scheduled GitHub Actions workflows keep production data fresh (daily stat refresh, roster updates every four hours, periodic salary updates).

## Deployment

- Frontend deploys to Vercel (`frontend/` as the root directory).
- Backend deploys to Railway as a FastAPI web service alongside a managed Postgres instance, using the `Procfile` start command.
- Required env vars: `DATABASE_URL` (backend), `ALLOWED_ORIGINS` (backend CORS), `NEXT_PUBLIC_API_URL` (frontend).

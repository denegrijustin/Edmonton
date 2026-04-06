# NHL Analytics Dashboard

A production-ready, data-first NHL analytics dashboard built with Streamlit. Defaults to the Edmonton Oilers with league-wide data for all 32 teams.

## Features

- **League-wide data** — All 32 NHL teams loaded from the NHL Web API
- **Team Profile** — Record, projected finish, momentum, last 5/next 5 games
- **Playoff Race** — Conference standings with projected seeds, opponents, and playoff odds
- **Team Comparison** — Side-by-side comparison of any two teams with season stats and MC simulation
- **Next Game Prediction** — Projected score, win probability, and simulation-driven expected outcome
- **Shot Maps** — Offensive and defensive heat maps with zone summaries (goals, shots, misses, blocks)
- **Player Ratings** — Position-specific ratings (forwards, defensemen, goalies) with trend tracking
- **Monte Carlo Game Simulation** — 10,000-simulation engine with home/away selection
- **Season Simulation** — Monte Carlo remaining-season projection for all teams
- **Data Health Panel** — Source status, refresh times, missing fields, degraded mode warnings
- **Stoplight Visuals** — Green/yellow/red indicators throughout for quick decision support
- **Team Logos** — Logo-first design using NHL CDN assets

## Architecture

```
config/       — Settings, constants, team/logo/division mappings
data/         — Data orchestration and loading
providers/    — NHL API adapter with caching, retries, rate limiting, health tracking
schemas/      — Data validation (standings, schedule, team games, projections)
features/     — Feature engineering (momentum, player ratings, team features)
models/       — Predictive models (playoff odds, seeds, opponents)
simulations/  — Monte Carlo engines (game sim, season sim)
ui/           — Streamlit UI components, charts, styles
utils/        — Shared helpers and stoplight visual logic
tests/        — Unit tests (74 tests across features, models, simulations, UI)
app.py        — Main Streamlit entry point (thin orchestration layer)
```

## Key Models

### Momentum Rate
Blends last-5 points%, last-10 points%, goal differential trend, shot differential trend, clutch index, consistency, and season points% into a 0–100 score with Hot/Steady/Slipping/Cold classification.

### Player Ratings
Position-specific formulas:
- **Forwards**: goals, assists, shots, takeaways, hits, blocks, giveaways, TOI, plus/minus, faceoff%
- **Defensemen**: blocks, hits, takeaways, giveaways, suppression, goals, assists, TOI, plus/minus
- **Goalies**: save%, goals against, saves, TOI, workload

### Playoff Projection
Combines pace-based projection, goal differential signal, current position bonus, and remaining schedule uncertainty. Monte Carlo season simulation runs 1,000+ iterations per team.

### Game Simulation
Poisson-based Monte Carlo engine using team offensive/defensive profiles, home/away splits, and momentum adjustments. Outputs win probability, projected score, score range, OT probability, and goal distributions.

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Deploy on Streamlit Community Cloud

1. Push to GitHub
2. Connect repo to Streamlit Cloud
3. Set main file path to `app.py`
4. Deploy

## Data Sources

- **NHL Web API** (`api-web.nhle.com/v1`): Standings, schedules, rosters, boxscores, play-by-play
- All data cached for 1 hour with retry/fallback behavior
- No mock data — explicit fallback states with degraded mode warnings

## Default Behavior

- Edmonton Oilers is the default focus team
- If Edmonton is mathematically eliminated, focus shifts to Western Conference playoff race
- Season state auto-detection: Regular Season → Bracket Locked → Active Playoff

# Edmonton Oilers Trends Dashboard

A Streamlit dashboard for Edmonton Oilers team trends, player grades, goal-location heat maps, and season outlook using the public NHL web API.

## Features
- lighter, cleaner UI
- no sidebar dependency for key controls
- team trends and momentum
- opponent damage profile
- player grades, consistency, and trend flags
- goal location heat maps for goals for and against
- best-effort on-ice / event-linked player heat maps
- season outlook and playoff odds proxy
- team and player game logs

## Files
- `app.py` - main Streamlit app
- `requirements.txt` - Python dependencies
- `.streamlit/config.toml` - light theme configuration

## Deploy on Streamlit Community Cloud
1. Create a new GitHub repository.
2. Upload all files, including the `.streamlit` folder.
3. Go to Streamlit Community Cloud.
4. Create a new app from your repo.
5. Set the main file path to `app.py`.
6. Deploy.

## Important notes
- The app uses public NHL web endpoints. Response shapes can change over time.
- The playoff odds figure is a proxy based on current pace, standings, and goal differential. It is not an official model.
- The on-ice player heat maps are a best-effort approximation using player IDs present on event payloads. They are directionally useful but not a full shift-chart grade of on-ice attribution.

## Next improvements you may want
- exact on-ice attribution from shift data
- score-state filters
- home/away split pages
- goalie-specific save location maps
- export buttons for filtered views

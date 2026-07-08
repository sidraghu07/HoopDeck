import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import lineups, players, stats, teams, trades

app = FastAPI()

allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(lineups.router)
app.include_router(stats.router)
app.include_router(teams.router)
app.include_router(trades.router)

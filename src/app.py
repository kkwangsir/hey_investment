import json
import os
from pathlib import Path

import jinja2
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Hey Investment Backtest Dashboard")

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR.parent / "static"

# Jinja2 templates — disable cache to avoid unhashable key issue
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
    undefined=jinja2.DebugUndefined,
    cache_size=0,
)
templates = Jinja2Templates(env=jinja_env)

# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def load_backtest_data() -> dict:
    """Load backtest data from JSON file."""
    data_path = DATA_DIR / "backtest.json"
    with open(data_path, "r") as f:
        return json.load(f)


@app.get("/api/data")
async def api_data():
    """Return full backtest data as JSON."""
    return load_backtest_data()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the dashboard homepage."""
    data = load_backtest_data()
    summary = data["summary"]
    trades = data["trades"]
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "summary": summary,
            "trades": trades,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=False)

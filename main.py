"""Compatibility entry point; application code lives in app/."""

from app.main import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=9000)

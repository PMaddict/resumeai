#!/usr/bin/env python3
"""Start the ResumeAI local server.

    python app.py

Serves the API at /api/* and, once you've run `npm run build` inside
app/frontend/, the built UI at http://localhost:8000/.
"""

import uvicorn

from app.backend.engine.config import get_settings

if __name__ == "__main__":
    settings = get_settings()["server"]
    print(f"\nResumeAI starting at http://{settings['host']}:{settings['port']}\n")
    uvicorn.run("app.backend.main:app", host=settings["host"], port=settings["port"], reload=False)

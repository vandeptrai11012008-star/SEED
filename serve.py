"""Production entrypoint. Binds 0.0.0.0 and reads $PORT (Render/Railway/Fly set it).

Local dev still uses run_server.py (127.0.0.1:8000). For production hosts:
    python serve.py
or let the platform run:
    uvicorn thermalloop.app:app --host 0.0.0.0 --port $PORT
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("thermalloop.app:app", host="0.0.0.0", port=port, reload=False)

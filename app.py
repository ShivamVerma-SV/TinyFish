"""RoleCurrent backend entrypoint.

Run this file directly for the production-style app, or use ``uvicorn backend.api:app``
during development. The compiled frontend is served automatically when ``frontend/dist``
exists.
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("backend.api:app", host="127.0.0.1", port=8000, reload=False)

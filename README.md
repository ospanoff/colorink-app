# colorink

E-paper image plugin service (POC).

## Development server

### Prerequisites

* Python **3.13**
* [uv](https://docs.astral.sh/uv/) for environments and dependencies

### Install

From the repository root:

```bash
uv sync
```

To include development tools (lint, typecheck, Granian **reload** support for `--reload`):

```bash
uv sync --extra dev
```

**Git hooks (optional):** after `uv sync --extra dev`, run once per clone so commits run ruff and `ty` via [pre-commit](https://pre-commit.com/):

```bash
uv run pre-commit install
```

### Run

Start the ASGI app with [Granian](https://github.com/emmett-framework/granian):

```bash
uv run granian --interface asgi colorink.main:app --host 127.0.0.1 --port 8000
```

* Use `--host 0.0.0.0` if you need to reach the service from other machines on the network.
* After `uv sync --extra dev`, you can add **`--reload`** to restart the process when source files change (useful while editing).

Example with reload:

```bash
uv run granian --interface asgi colorink.main:app --host 127.0.0.1 --port 8000 --reload
```

### Quick checks

| URL                          | Purpose                  |
| ---------------------------- | ------------------------ |
| http://127.0.0.1:8000/docs   | Swagger UI (try the API) |
| http://127.0.0.1:8000/redoc  | ReDoc                    |
| http://127.0.0.1:8000/health | Liveness JSON            |

### Configuration

| Environment variable     | Meaning                                                                                           |
| ------------------------ | ------------------------------------------------------------------------------------------------- |
| `COLORINK_DATABASE_PATH` | SQLite database file path (default: `data/colorink.db` relative to the process working directory) |

The `data/` directory is created automatically when the app first opens the database.

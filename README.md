# ForgeOS

ForgeOS is a local-first IT Operations data entry and inventory platform built with
FastAPI, SQLAlchemy, and SQLite. The first run creates the database and seeds a
ready-to-use dashboard with sample assets, people, assignments, and warranties.

## Development

Python 3.12 or newer is required. Run commands from the repository root so the
backend can reuse the canonical hardware profile logic in `forge/runtime/hardware.py`.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn Backend.app.main:app --reload
```

### WSL / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn Backend.app.main:app --reload
```

Open the dashboard at `http://127.0.0.1:8000/` and the OpenAPI documentation at
`http://127.0.0.1:8000/docs`.

## Tests

```bash
python -m pytest
```

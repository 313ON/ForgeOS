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

## Windows Server 2025 deployment

Use 64-bit CPython 3.12 or newer from python.org on a Windows Server 2025 VM.
Install Git for Windows, enable Python's PATH option, and run PowerShell as
the dedicated ForgeOS service account from the repository root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\Scripts\install_forgeos.ps1
```

The script checks Python and Git, creates `.venv`, installs `requirements.txt`,
and runs `compileall`. Set `FORGEOS_AUTH_SECRET` and
`FORGEOS_ADMIN_PASSWORD` as machine or service-account environment variables
before production use; do not put secrets in source control.

Start the server on the network with:

```powershell
.\Scripts\run_forgeos.ps1 -Host 0.0.0.0 -Port 8000
```

Allow the selected TCP port through Windows Defender Firewall, then browse to
`http://server-name:8000/`. Run one process while the in-process monitoring
scheduler is enabled. A Windows service wrapper such as NSSM may be configured
separately; ForgeOS does not ship third-party binaries.

Windows enrollment reports can be collected with:

```powershell
python Scripts\windows_inventory.py --output inventory.json
```

The collector uses fixed, bounded subprocess arguments and emits structured
JSON. Uploaded DxDiag/systeminfo reports remain limited to 5 MB and are
parsed offline by the existing import endpoint.

Monitoring runs in-process during FastAPI lifespan. It is suitable for a
single local ForgeOS process; use an external scheduler before deploying
multiple application workers. Website targets allow HTTP(S) only and deny
private or local destinations unless explicitly opted in.

## Tests

```bash
python -m pytest
```

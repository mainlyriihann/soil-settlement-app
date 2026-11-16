# Soil settlement web app

Enter soil properties (ks, mv, thickness, u0, drainage) -> get the Uav-Tv curve and the settlement after x hours.

```
Browser  ->  FastAPI  ->  database has (soil, force)?  --yes-->  return it
                                  |
                                  no -> queue -> ONE worker runs MATLAB -> save in DB -> return it
```

```
backend/
  app.py            API, database model, job worker
  matlab_bridge.py  how MATLAB is called (mock / batch / engine)
  matlab/run_case.m the wrapper YOU connect your MATLAB code to
  config.py         input limits, MATLAB mode, database URL
frontend/index.html the page (served by the backend at /)
```

## 1. Run it (demo mode, no MATLAB needed)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://127.0.0.1:8000. The first request for a set of inputs is computed; asking for
the same inputs again says "from database". The database is the file `backend/cases.db`.
Demo mode runs the same maths in Python, not MATLAB.

## 2. Connect your MATLAB code

Already done for `final_analytical.m`: it was turned into `backend/matlab/consolidation_model.m`
(a function), called by `backend/matlab/run_case.m`. Inputs: `ks`, `mv`, soil thickness, `u0`, drainage
(single/double). Outputs: Uav-Tv curve, and settlement (mm) = Uav * mv * u0 * thickness vs time (0-876600 hours).

Test it in MATLAB first:

```matlab
cd backend/matlab
run_case(6.28e-6, 5.6e-6, 10, 'double', 100, 'test.json')   % should create test.json
```

### Step C - choose how the backend calls MATLAB

**Option 1: batch (simplest)** - starts MATLAB once per new case (adds ~10-30 s startup).
```bash
export MATLAB_MODE=batch
export MATLAB_CMD=matlab     # or full path, e.g. /usr/local/MATLAB/R2024b/bin/matlab
uvicorn app:app
```
Windows (PowerShell): `$env:MATLAB_MODE="batch"; $env:MATLAB_CMD="C:\Program Files\MATLAB\R2024b\bin\matlab.exe"`

**Option 2: engine (fastest)** - one MATLAB session stays open. Install the engine into your venv from MATLAB's folder:
```bash
cd "<matlabroot>/extern/engines/python"     # in MATLAB, type  matlabroot  to find it
python -m pip install .
export MATLAB_MODE=engine
uvicorn app:app
```
Check the MATLAB release supports your Python version (MathWorks lists this per release).
Do not use `--reload` with engine mode and do not run more than one uvicorn worker.

**Option 3: no MATLAB on the server** - compile `run_case` with MATLAB Compiler, install the free MATLAB Runtime
on the server, and change `_run_batch` in `matlab_bridge.py` to call the compiled executable.

If MATLAB fails, the page shows MATLAB's error message, and clicking Calculate again retries.

## 3. Using PostgreSQL instead of SQLite

```bash
pip install "psycopg[binary]"
export DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/soil"
```
The table is created automatically.

## Things to know

- **One MATLAB run at a time.** A single worker thread runs the queue, so two users asking for
  the same new case share one run, and your MATLAB licence is never used twice at once.
- **Data size.** Each curve is downsampled to `MAX_POINTS` (2000) and stored zlib-compressed, one row
  per case, so the database stays small. Raise `MAX_POINTS` if you need more detail.
- **Settlement after x hours** is interpolated in the browser from the stored series, so changing x
  needs no new request.
- **Not internet-ready as is.** There are no logins or rate limits; add them before exposing it publicly.

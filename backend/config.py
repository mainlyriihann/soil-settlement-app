"""Settings."""
import os
from pathlib import Path

# Inputs of the MATLAB model (final_analytical.m). Defaults = values in the original script.
# (label, unit, default, min, max)
PARAMS = {
    "ks": {"label": "Permeability, ks", "unit": "m/s", "default": 6.28e-6, "min": 1e-12, "max": 1e-2},
    "mv": {"label": "Coeff. of volume compressibility, mv", "unit": "m²/kN", "default": 5.6e-6, "min": 1e-8, "max": 1e-1},
    "thickness": {"label": "Soil thickness", "unit": "m", "default": 10.0, "min": 0.1, "max": 200.0},
    "u0": {"label": "Initial pore pressure, u0", "unit": "kN/m²", "default": 100.0, "min": 1.0, "max": 10000.0},
}
DRAINAGE_TYPES = ["double", "single"]

# Longest time (years) the settlement curve covers (the MATLAB model runs to 100 years).
MAX_YEARS = 100

# "mock"   -> same maths in Python, no MATLAB needed (for trying the app)
# "batch"  -> runs `matlab -batch ...` for every new case (simplest real mode)
# "engine" -> keeps one MATLAB session open via the MATLAB Engine API for Python (fastest)
MATLAB_MODE = os.getenv("MATLAB_MODE", "mock")
MATLAB_CMD = os.getenv("MATLAB_CMD", "matlab")  # full path if matlab is not on PATH
MATLAB_TIMEOUT = int(os.getenv("MATLAB_TIMEOUT", "1800"))  # seconds, batch mode
MATLAB_DIR = Path(__file__).parent / "matlab"

# Each curve is downsampled to at most this many points before it is stored/sent to the browser.
MAX_POINTS = int(os.getenv("MAX_POINTS", "2000"))

# SQLite file by default. For PostgreSQL use e.g.
#   postgresql+psycopg://user:password@localhost:5432/soil
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cases.db")

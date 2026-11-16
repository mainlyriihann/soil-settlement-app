"""The only place that knows how to get numbers out of MATLAB.

Contract: MATLAB's run_case(ks, mv, th, drainage, u0, outfile) writes a JSON file:
    {"tv": [...], "uav": [...], "t_hours": [...], "settlement": [...],
     "tv_emp": [...], "uav_emp": [...]}            (the last two are optional)
    tv, uav               -> the Uav vs Tv curve (same length)
    t_hours, settlement   -> settlement (mm) vs time in hours (same length)
"""
import json
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import config

trapezoid = getattr(np, "trapezoid", None) or np.trapz  # numpy 2 renamed trapz

_eng = None
_init_error = None


def init():
    """Call once from the worker thread (the MATLAB engine must be used from the thread that started it)."""
    global _eng, _init_error
    if config.MATLAB_MODE != "engine":
        return
    try:
        import matlab.engine  # installed from MATLAB's own folder, see README

        _eng = matlab.engine.start_matlab()
        _eng.addpath(str(config.MATLAB_DIR), nargout=0)
    except Exception as exc:  # noqa: BLE001
        _init_error = f"Could not start MATLAB engine: {exc}"


def validate(params: dict) -> dict:
    """Check and normalise the inputs. Returns a clean dict; raises ValueError."""
    out = {}
    for name, spec in config.PARAMS.items():
        try:
            v = float(params[name])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"'{name}' must be a number")
        if not math.isfinite(v) or not (spec["min"] <= v <= spec["max"]):
            raise ValueError(f"{spec['label']} must be between {spec['min']:g} and {spec['max']:g} {spec['unit']}")
        out[name] = float(f"{v:.6g}")  # 6 significant digits, so 1.0 and 1.0000001 share one cache row
    if params.get("drainage") not in config.DRAINAGE_TYPES:
        raise ValueError("drainage must be 'single' or 'double'")
    out["drainage"] = params["drainage"]
    return out


def compute(params: dict) -> dict:
    p = validate(params)
    mode = config.MATLAB_MODE
    if mode == "mock":
        raw = _mock(p)
    elif mode == "batch":
        raw = _run_batch(p)
    elif mode == "engine":
        raw = _run_engine(p)
    else:
        raise ValueError(f"Unknown MATLAB_MODE '{mode}'")
    return _clean(raw)


# ---------------------------------------------------------------- real MATLAB
def _q(path) -> str:
    """Quote a value for a MATLAB single-quoted string."""
    return str(path).replace("'", "''")


def _run_batch(p):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "result.json"
        # numbers are validated floats and drainage is one of two fixed words, so this is safe
        call = (f"run_case({p['ks']:.10g},{p['mv']:.10g},{p['thickness']:.10g},"
                f"'{p['drainage']}',{p['u0']:.10g},'{_q(out)}');")
        cmd = f"addpath('{_q(config.MATLAB_DIR)}'); {call}"
        proc = subprocess.run(
            [config.MATLAB_CMD, "-batch", cmd],
            capture_output=True, text=True, timeout=config.MATLAB_TIMEOUT,
        )
        if proc.returncode != 0 or not out.exists():
            tail = (proc.stderr or proc.stdout or "no output")[-1500:]
            raise RuntimeError(f"MATLAB failed (exit {proc.returncode}): {tail}")
        return json.loads(out.read_text())


def _run_engine(p):
    if _init_error:
        raise RuntimeError(_init_error)
    if _eng is None:
        raise RuntimeError("MATLAB engine is not running")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "result.json"
        _eng.run_case(p["ks"], p["mv"], p["thickness"], p["drainage"], p["u0"], str(out), nargout=0)
        return json.loads(out.read_text())


# ---------------------------------------------------------------- demo data
def _mock(p):
    """Python port of backend/matlab/consolidation_model.m (same maths, no MATLAB needed)."""
    yw = 9.81
    cv = p["ks"] / (yw * p["mv"])
    th, u0 = p["thickness"], p["u0"]
    d = th / 2 if p["drainage"] == "double" else th
    big_h = 2 * d  # 2*d (= th for double drainage, 2*th for single drainage)
    sec_hour = 3600

    z = np.linspace(0, th, 101)[:, None]
    k = (2 * np.arange(0, 1001) + 1)[None, :]
    s = np.sin(z * k * np.pi / big_h)
    coef = (4 / np.pi) * u0 / k
    rate = (k * np.pi / big_h) ** 2 * cv

    tv_grid = np.logspace(-4, np.log10(3), 200)
    time = np.unique(np.concatenate([[0.0], tv_grid * d**2 / cv,
                                     np.logspace(-1, np.log10(config.MAX_HOURS * sec_hour), 300)]))
    uav = np.zeros(len(time))
    for i in range(1, len(time)):
        u = (s * (coef * np.exp(-rate * time[i]))).sum(axis=1)
        uav[i] = 1 - trapezoid(u, z[:, 0]) / (u0 * th)

    tv1 = cv * time / d**2
    keep_tv = tv1 <= 3
    keep_t = time <= config.MAX_HOURS * sec_hour * (1 + 1e-9)

    return {
        "tv": tv1[keep_tv].tolist(), "uav": uav[keep_tv].tolist(),
        "t_hours": (time[keep_t] / sec_hour).tolist(),
        "settlement": (uav[keep_t] * p["mv"] * u0 * th * 1000).tolist(),
        "tv_t": tv1[keep_t].tolist(), "uav_t": uav[keep_t].tolist(),
    }


# ---------------------------------------------------------------- validation
def _downsample(a: np.ndarray, b: np.ndarray):
    if len(a) <= config.MAX_POINTS:
        return a, b
    idx = np.unique(np.linspace(0, len(a) - 1, config.MAX_POINTS).round().astype(int))
    return a[idx], b[idx]


def _series(raw, xk, yk, required=True):
    if xk not in raw or yk not in raw:
        if required:
            raise ValueError(f"MATLAB output is missing '{xk}' or '{yk}'")
        return None
    x = np.atleast_1d(np.asarray(raw[xk], dtype=float)).ravel()
    y = np.atleast_1d(np.asarray(raw[yk], dtype=float)).ravel()
    if len(x) != len(y) or len(x) < 2:
        raise ValueError(f"'{xk}' and '{yk}' must have the same length (>= 2)")
    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
        raise ValueError(f"'{xk}'/'{yk}' contain NaN or Inf")
    order = np.argsort(x, kind="stable")  # np.interp in the browser needs ascending x
    return _downsample(x[order], y[order])


def _clean(raw: dict) -> dict:
    out = {}
    for xk, yk, req in (("tv", "uav", True), ("t_hours", "settlement", True), ("tv_emp", "uav_emp", False)):
        s = _series(raw, xk, yk, req)
        if s is not None:
            out[xk] = [round(float(v), 10) for v in s[0]]
            out[yk] = [round(float(v), 10) for v in s[1]]
    # Tv and Uav at each settlement time, so the page can mark the chosen time on the Uav-Tv curve
    for name in ("tv_t", "uav_t"):
        if name in raw:
            ys = _series({"x": raw["t_hours"], "y": raw[name]}, "x", "y")
            out[name] = [round(float(v), 10) for v in ys[1]]
    out["max_hours"] = math.floor(out["t_hours"][-1])
    return out

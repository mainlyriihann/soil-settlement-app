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


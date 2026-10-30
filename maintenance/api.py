import os
from functools import lru_cache
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .service import ScoringService, SensorEvent

ROOT=Path(__file__).resolve().parent.parent
app=FastAPI(title='Predictive Maintenance Lab',description='Synthetic sensor failure-risk demonstration')
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
@lru_cache
def service():
    return ScoringService(os.getenv('MODEL_PATH','runtime/model.joblib'),os.getenv('DATABASE_PATH','runtime/events.db'))
@app.get('/')
def index(): return FileResponse(ROOT/'static/index.html')
@app.get('/api/health')
def health():
    try: return {'status':'ready','model':service().bundle['version'],'synthetic':True}
    except FileNotFoundError: raise HTTPException(503,'Train a model before starting the service')
@app.get('/api/assets')
def assets(): return service().snapshot()
@app.get('/api/assets/{asset_id}/history')
def history(asset_id:str): return service().history(asset_id)
@app.get('/api/metrics')
def metrics():
    import json
    return json.loads(Path(os.getenv('METRICS_PATH','runtime/metrics.json')).read_text())
@app.post('/api/events')
def ingest(event:SensorEvent):
    try: return service().ingest(event.model_dump())
    except ValueError as e: raise HTTPException(409,str(e))

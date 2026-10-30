"""Validated, idempotent local event ingestion and model scoring."""
from collections import deque
import json
import sqlite3
from pathlib import Path
from typing import Annotated
import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from .data import FEATURES, features

Finite = Annotated[float, Field(allow_inf_nan=False)]
class SensorEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: str = Field(min_length=1,max_length=100)
    asset_id: str = Field(min_length=1,max_length=80)
    timestamp: int = Field(ge=0)
    temperature: Finite
    vibration: Finite = Field(ge=0)
    pressure: Finite = Field(ge=0)
    load: Finite = Field(ge=0,le=1)
    supplier_fault_rate: Finite = Field(ge=0,le=1)

class ScoringService:
    def __init__(self, model_path, database):
        # Trusted artifacts only. joblib deserialisation can execute code.
        self.bundle=joblib.load(model_path)
        self.database=str(database)
        Path(self.database).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS readings (event_id TEXT PRIMARY KEY, asset_id TEXT, timestamp INTEGER, event TEXT, result TEXT, UNIQUE(asset_id,timestamp))')
            db.execute('CREATE TABLE IF NOT EXISTS quarantine (id INTEGER PRIMARY KEY, reason TEXT, payload TEXT)')
    def connect(self):
        return sqlite3.connect(self.database,timeout=20)
    def ingest(self,payload):
        event=SensorEvent.model_validate(payload).model_dump()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT event,result FROM readings WHERE event_id=?',(event['event_id'],)).fetchone()
            if old:
                if json.loads(old[0]) != event: raise ValueError('Event ID already used with different data')
                return {**json.loads(old[1]),'duplicate':True}
            rows=db.execute('SELECT event FROM readings WHERE asset_id=? ORDER BY timestamp DESC LIMIT 6',(event['asset_id'],)).fetchall()
            history=[json.loads(row[0]) for row in reversed(rows)]
            if history and event['timestamp']<=history[-1]['timestamp']:
                raise ValueError('Out-of-order or duplicate timestamp for this asset')
            history.append(event)
            vector=features(history)
            frame=pd.DataFrame([vector],columns=FEATURES)
            risk=float(self.bundle['model'].predict_proba(frame)[0,1])
            threshold=self.bundle['threshold']
            # Display risk in relation to the validation-selected alert threshold.
            status='critical' if risk>=threshold else ('watch' if risk>=threshold*.5 else 'normal')
            z=(np.array(vector)-self.bundle['reference']['mean'])/self.bundle['reference']['std']
            result={**event,'risk':risk,'status':status,'alert_threshold':threshold,
                    'model_version':self.bundle['version'],'out_of_range_features':int((abs(z)>3).sum()),
                    'synthetic':True,'duplicate':False}
            db.execute('INSERT INTO readings VALUES (?,?,?,?,?)',(event['event_id'],event['asset_id'],event['timestamp'],json.dumps(event),json.dumps(result)))
            return result
    def snapshot(self):
        with self.connect() as db:
            rows=db.execute('SELECT result FROM readings r WHERE timestamp=(SELECT MAX(timestamp) FROM readings WHERE asset_id=r.asset_id) ORDER BY asset_id').fetchall()
            total=db.execute('SELECT COUNT(*) FROM readings').fetchone()[0]
            rejected=db.execute('SELECT COUNT(*) FROM quarantine').fetchone()[0]
        assets=sorted([json.loads(r[0]) for r in rows],key=lambda r:r['risk'],reverse=True)
        return {'assets':assets,'events_processed':total,'rejected_events':rejected,'synthetic':True,
                'model':self.bundle['name'],'version':self.bundle['version'],'threshold':self.bundle['threshold']}
    def history(self,asset_id):
        with self.connect() as db:
            rows=db.execute('SELECT result FROM readings WHERE asset_id=? ORDER BY timestamp DESC LIMIT 72',(asset_id,)).fetchall()
        return [json.loads(r[0]) for r in reversed(rows)]
    def reject(self,payload,reason):
        with self.connect() as db:
            db.execute('INSERT INTO quarantine(reason,payload) VALUES (?,?)',(str(reason),str(payload)[:10000]))

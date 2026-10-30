import json
import os
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from maintenance.data import generate, features, FEATURES
from maintenance.service import ScoringService, SensorEvent
from maintenance.train import train, split_assets

@pytest.fixture(scope='session')
def trained(tmp_path_factory):
    root=tmp_path_factory.mktemp('training')
    report=train(root,tracking_uri='sqlite:///'+str(root/'mlflow.db'))
    return root,report

@pytest.fixture
def scorer(trained,tmp_path):
    return ScoringService(trained[0]/'model.joblib',tmp_path/'events.db')

def test_disjoint_assets_and_excluded_future_information():
    events,frame=generate(24)
    parts=split_assets(frame)
    groups=[set(p.asset_id) for p in parts.values()]
    for i,a in enumerate(groups):
        for b in groups[i+1:]: assert a.isdisjoint(b)
    assert sum(len(p) for p in parts.values())==len(frame)
    assert not set(FEATURES)&{'failure_in_12h','asset_id','event_id','failure_hour'}
    # Prefix features cannot change when later readings exist.
    prefix=events[:5]
    np.testing.assert_allclose(features(prefix),frame.loc[4,FEATURES].to_numpy(dtype=float))

def test_batch_and_ingestion_feature_parity(scorer):
    events,frame=generate(2,seed=1042,prefix='check')
    for i,e in enumerate(events[:8]):
        actual=scorer.ingest(e)
        expected=scorer.bundle['model'].predict_proba(frame.loc[[i],FEATURES])[0,1]
        assert actual['risk']==pytest.approx(expected)

def test_duplicate_conflict_and_late_event(scorer):
    events,_=generate(1)
    first=scorer.ingest(events[0]);duplicate=scorer.ingest(events[0])
    assert duplicate['duplicate'] and duplicate['risk']==first['risk']
    assert scorer.snapshot()['events_processed']==1
    with pytest.raises(ValueError,match='different data'):
        scorer.ingest({**events[0],'temperature':100})
    with pytest.raises(ValueError,match='timestamp'):
        scorer.ingest({**events[0],'event_id':'other'})
    scorer.ingest(events[2])
    with pytest.raises(ValueError,match='Out-of-order'):
        scorer.ingest(events[1])

def test_invalid_readings():
    event=generate(1)[0][0]
    for invalid in [{'load':1.5},{'vibration':-1},{'temperature':float('nan')},{'supplier_fault_rate':-1}]:
        with pytest.raises(ValidationError): SensorEvent.model_validate({**event,**invalid})

def test_persistence_and_risk_bounds(scorer):
    e=generate(1)[0][0];result=scorer.ingest(e)
    assert 0<=result['risk']<=1
    restarted=ScoringService.__new__(ScoringService)
    restarted.bundle=scorer.bundle;restarted.database=scorer.database
    assert restarted.snapshot()['assets'][0]['event_id']==e['event_id']
    scorer.reject('bad json','invalid')
    assert scorer.snapshot()['rejected_events']==1

def test_metrics_and_mlflow(trained):
    root,report=trained
    from mlflow import MlflowClient
    client=MlflowClient(tracking_uri='sqlite:///'+str(root/'mlflow.db'))
    experiment=client.get_experiment_by_name('synthetic-predictive-maintenance')
    runs=client.search_runs([experiment.experiment_id])
    assert len(runs)==2
    assert all('test_f1' in run.data.metrics for run in runs)
    selected=report['selected_by_validation_f1']
    assert selected==max(report['models'],key=lambda n:report['models'][n]['validation']['f1'])
    for model in report['models'].values():
        assert 0<=model['test']['f1']<=1
        assert sum(map(sum,model['test']['confusion_matrix']))==report['splits']['test']['rows']
    assert (root/'model.joblib').exists()
    assert len(list((root/'mlartifacts').rglob('model.joblib')))==1
    selected_run=next(run for run in runs if run.data.tags.get('selected_by')=='validation_f1')
    restored=client.download_artifacts(selected_run.info.run_id,'model.joblib')
    assert Path(restored).is_file()

def test_api_dashboard_and_validation(scorer,trained,monkeypatch):
    from maintenance.api import app,service
    app.dependency_overrides.clear()
    # Endpoint service factory is cached; replace it with the isolated scorer.
    import maintenance.api as api
    monkeypatch.setattr(api,'service',lambda:scorer)
    monkeypatch.setenv('METRICS_PATH',str(trained[0]/'metrics.json'))
    with TestClient(app) as client:
        assert client.get('/').status_code==200
        assert 'SignalWorks' in client.get('/').text
        assert client.get('/api/health').json()['status']=='ready'
        e=generate(1)[0][0]
        assert client.post('/api/events',json=e).status_code==200
        assert client.post('/api/events',json={**e,'load':8}).status_code==422
        assert client.post('/api/events',json={**e,'temperature':200}).status_code==409
        assert len(client.get('/api/assets').json()['assets'])==1
        assert len(client.get('/api/assets/'+e['asset_id']+'/history').json())==1
        assert client.get('/api/metrics').json()['synthetic']
        assert client.get('/static/app.js').status_code==200

@pytest.mark.skipif(os.getenv('RUN_KAFKA_TEST')!='1',reason='Requires a real Kafka broker')
def test_real_kafka_transport(trained,tmp_path):
    from kafka import KafkaProducer
    bootstrap=os.getenv('KAFKA_BOOTSTRAP','localhost:9092')
    database=tmp_path/'kafka-events.db'
    env={**os.environ,'MODEL_PATH':str(trained[0]/'model.joblib'),'DATABASE_PATH':str(database)}
    process=subprocess.Popen([sys.executable,'-m','maintenance.stream','consume','--bootstrap',bootstrap],env=env)
    producer=KafkaProducer(bootstrap_servers=bootstrap,value_serializer=lambda x:json.dumps(x).encode())
    try:
        event=generate(1,seed=1043,prefix='kafka-test')[0][0]
        producer.send('sensor-readings',key=event['asset_id'].encode(),value=event).get(timeout=30)
        producer.flush()
        service=ScoringService(trained[0]/'model.joblib',database)
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if service.snapshot()['events_processed']>=1: break
            if process.poll() is not None: pytest.fail('Kafka consumer exited unexpectedly')
            time.sleep(.25)
        else: pytest.fail('Kafka event was not scored before timeout')
        assert service.snapshot()['assets'][0]['asset_id']==event['asset_id']
    finally:
        producer.close();process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill();process.wait()

def test_commit_only_after_durable_ingestion_or_quarantine(scorer):
    from types import SimpleNamespace
    from maintenance.stream import process_message
    committed=[]
    event=generate(1)[0][0]
    message=SimpleNamespace(value=json.dumps(event).encode(),offset=0)
    process_message(message,scorer,lambda:committed.append('ok'))
    assert len(committed)==1 and scorer.snapshot()['events_processed']==1
    message.value=b'not json'
    process_message(message,scorer,lambda:committed.append('quarantine'))
    assert len(committed)==2 and scorer.snapshot()['rejected_events']==1
    class BrokenStorage:
        def ingest(self,payload): raise OSError('Disk unavailable')
    message.value=json.dumps(event).encode()
    with pytest.raises(OSError): process_message(message,BrokenStorage(),lambda:committed.append('bad'))
    assert len(committed)==2

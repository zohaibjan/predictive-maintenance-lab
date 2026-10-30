"""Verify actual container-produced telemetry through the deployed FastAPI service."""
import json
import time
from urllib.request import urlopen
from maintenance.data import generate

BASE='http://127.0.0.1:8000'

def read(path):
    with urlopen(BASE+path,timeout=5) as response:
        assert response.status==200
        return json.load(response)

def main():
    events,_=generate(n_assets=12,seed=1042,prefix='stream')
    expected=len(events)
    deadline=time.monotonic()+180
    last=None
    while time.monotonic()<deadline:
        try:
            last=read('/api/assets')
            if last['events_processed']==expected and len(last['assets'])==12: break
        except OSError: pass
        time.sleep(1)
    else: raise AssertionError(f'Container scoring incomplete: expected {expected}; last response={last}')
    assert read('/api/health')['status']=='ready'
    assert last['rejected_events']==0
    assert {a['asset_id'] for a in last['assets']}=={e['asset_id'] for e in events}
    assert all(0<=a['risk']<=1 for a in last['assets'])
    for asset in last['assets']:
        history=read('/api/assets/'+asset['asset_id']+'/history')
        assert history and history[-1]['event_id']==asset['event_id']
        assert len({h['event_id'] for h in history})==len(history)
    metrics=read('/api/metrics')
    assert metrics['synthetic'] and len(metrics['models'])==2
    print(f'Full Docker stack verified: {expected} events, 12 assets, real producer → Kafka → consumer → FastAPI')
if __name__=='__main__': main()

"""Replay independent synthetic assets through the exact ingestion/scoring path."""
import argparse
from .data import generate
from .service import ScoringService

def replay(model='runtime/model.joblib', database='runtime/events.db', assets=12):
    service=ScoringService(model,database)
    events,_=generate(n_assets=assets,seed=1042,prefix='demo')
    for event in sorted(events,key=lambda e:(e['timestamp'],e['asset_id'])):
        service.ingest(event)
    return service.snapshot()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',default='runtime/model.joblib');p.add_argument('--database',default='runtime/events.db')
    args=p.parse_args();s=replay(args.model,args.database); print(f"Scored {s['events_processed']} readings across {len(s['assets'])} synthetic assets")

"""Train (if needed), replay independent synthetic telemetry, start local dashboard."""
import argparse
from pathlib import Path
import uvicorn
from maintenance.train import train
from maintenance.replay import replay

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--retrain',action='store_true')
    args=parser.parse_args()
    if args.retrain or not Path('runtime/model.joblib').exists():
        train(Path('runtime'),tracking_uri='sqlite:///runtime/mlflow.db')
    replay()
    print(f'Open http://127.0.0.1:{args.port} — synthetic data only')
    uvicorn.run('maintenance.api:app',host='127.0.0.1',port=args.port)

"""Asset-disjoint training, calibration, validation and final test evaluation."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from .data import FEATURES, generate


def split_assets(frame, seed=42):
    assets = np.array(sorted(frame.asset_id.unique()))
    np.random.default_rng(seed).shuffle(assets)
    # 50/16.7/16.7/16.7 percent, all observations from an asset stay together.
    cuts = [0, len(assets)//2, 2*len(assets)//3, 5*len(assets)//6, len(assets)]
    return {name: frame[frame.asset_id.isin(assets[a:b])].copy()
            for name, a, b in zip(['train','calibration','validation','test'], cuts[:-1], cuts[1:])}


def evaluate(y, probabilities, threshold):
    pred = probabilities >= threshold
    return {'f1': float(f1_score(y,pred,zero_division=0)),
            'precision': float(precision_score(y,pred,zero_division=0)),
            'recall': float(recall_score(y,pred,zero_division=0)),
            'roc_auc': float(roc_auc_score(y,probabilities)),
            'average_precision': float(average_precision_score(y,probabilities)),
            'brier_score': float(brier_score_loss(y,probabilities)),
            'confusion_matrix': confusion_matrix(y,pred,labels=[0,1]).tolist()}


def train(output=Path('runtime'), seed=42, tracking_uri=None):
    output = Path(output); output.mkdir(parents=True,exist_ok=True)
    _, frame = generate(seed=seed)
    parts = split_assets(frame,seed)
    models = {
        'svm': make_pipeline(StandardScaler(),SVC(C=2,class_weight='balanced',random_state=seed)),
        'neural_network': make_pipeline(StandardScaler(),MLPClassifier(
            hidden_layer_sizes=(24,12),max_iter=350,random_state=seed,early_stopping=False))}
    report = {'seed':seed,'sklearn':sklearn.__version__,'synthetic':True,
              'target':'failure within the next 12 simulated hours',
              'features':FEATURES,'splits':{k:{'assets':sorted(v.asset_id.unique().tolist()),
                                             'rows':len(v),'positive_rate':float(v.failure_in_12h.mean())}
                                           for k,v in parts.items()},'models':{}}
    calibrated = {}
    for name, pipeline in models.items():
        pipeline.fit(parts['train'][FEATURES],parts['train'].failure_in_12h)
        model = CalibratedClassifierCV(FrozenEstimator(pipeline),method='sigmoid')
        model.fit(parts['calibration'][FEATURES],parts['calibration'].failure_in_12h)
        val = model.predict_proba(parts['validation'][FEATURES])[:,1]
        candidates = np.arange(.1,.91,.05)
        threshold = float(max(candidates,key=lambda t:f1_score(parts['validation'].failure_in_12h,val>=t)))
        report['models'][name] = {'threshold':threshold,'validation':evaluate(parts['validation'].failure_in_12h,val,threshold)}
        calibrated[name] = model
    winner = max(models,key=lambda n:report['models'][n]['validation']['f1'])
    report['selected_by_validation_f1'] = winner
    # Model and threshold selection are completed before opening test labels.
    for name, model in calibrated.items():
        probability = model.predict_proba(parts['test'][FEATURES])[:,1]
        report['models'][name]['test'] = evaluate(parts['test'].failure_in_12h,probability,report['models'][name]['threshold'])
    reference = {'mean':parts['train'][FEATURES].mean().tolist(),
                 'std':parts['train'][FEATURES].std().replace(0,1).tolist()}
    bundle = {'model':calibrated[winner],'name':winner,'threshold':report['models'][winner]['threshold'],
              'features':FEATURES,'reference':reference,'version':f'synthetic-seed-{seed}-{winner}'}
    joblib.dump(bundle,output/'model.joblib')
    (output/'metrics.json').write_text(json.dumps(report,indent=2)+'\n')
    if tracking_uri:
        import mlflow
        mlflow.set_tracking_uri(tracking_uri)
        # New experiments keep artifacts under the same persistent output volume.
        experiment_name = 'synthetic-predictive-maintenance'
        client = mlflow.MlflowClient()
        experiment = client.get_experiment_by_name(experiment_name)
        if experiment is None:
            experiment_id = client.create_experiment(
                experiment_name, artifact_location=(output/'mlartifacts').resolve().as_uri())
        else:
            experiment_id = experiment.experiment_id
        mlflow.set_experiment(experiment_id=experiment_id)
        for name in models:
            with mlflow.start_run(run_name=name):
                mlflow.log_params({'model':name,'seed':seed,'synthetic':True,'horizon_hours':12,
                                   'threshold':report['models'][name]['threshold'], 'asset_disjoint':True})
                for partition in ('validation','test'):
                    mlflow.log_metrics({f'{partition}_{k}':v for k,v in report['models'][name][partition].items() if isinstance(v,float)})
                mlflow.log_artifact(str(output/'metrics.json'))
                if name==winner:
                    mlflow.log_artifact(str(output/'model.joblib'))
                    mlflow.set_tag('selected_by','validation_f1')
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('runtime'))
    p.add_argument('--tracking-uri');p.add_argument('--seed',type=int,default=42)
    args=p.parse_args(); print(json.dumps(train(args.output,args.seed,args.tracking_uri),indent=2))
if __name__=='__main__': main()

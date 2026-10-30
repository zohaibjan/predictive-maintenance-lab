# Recorded synthetic evaluation

Selected using validation F1: **neural_network**.

| Model | Test F1 | Precision | Recall | ROC-AUC |
|---|---:|---:|---:|---:|
| svm | 0.9496 | 0.9429 | 0.9565 | 0.9977 |
| neural_network | 0.9309 | 0.9343 | 0.9275 | 0.9982 |

120 synthetic assets; training 60, calibration 20, validation 20, test 20. Metrics are per reading; readings within an asset are correlated.

These are simulated-data results, not evidence of operational accuracy or downtime reduction.

![Model comparison](model_comparison.png)

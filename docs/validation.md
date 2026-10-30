# Validation evidence

## Completed locally

- Nine Python tests passed in one complete run with a real Apache Kafka 4.0.2 broker. Runtime: 15.49 seconds.
- Actual SVM and neural-network fitting, separate-asset calibration, validation threshold/model selection and held-out metrics were executed.
- MLflow SQLite tracking was exercised and both runs' recorded metrics retrieved with MlflowClient.
- Batch/stream feature parity, idempotent duplicates, conflicting IDs, late events, persistence, input validation and quarantine were tested.
- Kafka message handling was tested for commit-after-ingestion/quarantine and no commit after a storage failure.
- FastAPI endpoints, dashboard/static delivery, prediction ingestion and validation responses were tested with TestClient.
- Independent offline replay scored 800 readings across 12 synthetic assets.
- `node --check static/app.js` passed.

## Remaining checks

The managed browser-preview service lacks the Python interpreter required by the FastAPI application. Browser visual/responsive/interaction QA was therefore not completed. The API test client is not a substitute for those checks.

The [GitHub Actions validation run](https://github.com/zohaibjan/predictive-maintenance-lab/actions/runs/41017185745) passed Docker Compose startup of the Kafka broker/topic initializer and the real Kafka integration test. The complete application-container stack (train/API/producer/consumer images together) has not been exercised. The real Kafka transport test passed using an official Apache Kafka 4.0.2 binary distribution and Java 17. The distribution SHA-512 checksum was verified before execution. Broker, topic creation, producer and scoring consumer ran in one test process tree; an event was durably scored through the actual Kafka transport. This verifies transport, not Docker orchestration.

No hardware, real sensor data, real maintenance records or operational savings have been validated. CI evidence is linked above; it covers the published code and its Docker-based broker integration.


The recorded run emitted two third-party deprecation warnings from Starlette/httpx and SQLAlchemy/MLflow. No test failures remained.

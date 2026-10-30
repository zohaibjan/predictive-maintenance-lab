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

Docker Compose orchestration has not been executed in this environment because Docker is unavailable. The real Kafka transport test passed using an official Apache Kafka 4.0.2 binary distribution and Java 17. The distribution SHA-512 checksum was verified before execution. Broker, topic creation, producer and scoring consumer ran in one test process tree; an event was durably scored through the actual Kafka transport. This verifies transport, not Docker orchestration.

No hardware, real sensor data, real maintenance records or operational savings have been validated. No CI results are claimed before publication.


The recorded run emitted two third-party deprecation warnings from Starlette/httpx and SQLAlchemy/MLflow. No test failures remained.

# Validation evidence

The [extended GitHub Actions run](https://github.com/zohaibjan/predictive-maintenance-lab/actions/runs/41019549256) passed both jobs on the tested code revision.

## Completed checks

- Nine core tests across the unit/API suite and real Kafka integration.
- Complete Docker application build and execution: training container, Kafka broker, topic initializer, API, consumer and producer.
- All 800 producer readings scored and persisted across 12 independent synthetic assets; API history, risk bounds and zero quarantine records checked.
- MLflow metrics recorded and the logged selected-model artifact retained after the training container was removed. New experiments use the persistent output volume.
- Five live-service browser configurations passed: Chromium/Firefox/WebKit at 1440×1000, and Chromium/WebKit at 390×844 (mobile emulation, not physical phones).
- Browser checks cover search, empty search results, asset selection, chart presence, status filtering, model/pipeline navigation, refresh, no page-script errors and no whole-page horizontal overflow.
- [Desktop screenshot](images/dashboard-desktop.png) and [mobile screenshot](images/dashboard-mobile.png) were captured from the live container service. Full screenshots, JUnit XML and container logs are also available in the run's full-stack-browser-evidence artifact.
- Earlier batch/stream feature parity, asset-disjoint modelling, frozen-estimator calibration, duplicate/conflict/late-event handling, commit-after-durable-storage and storage-failure retry checks remain in the core suite.

## Limits

These checks validate a bounded synthetic demonstration. No real equipment data, failure-reduction benefit or production readiness is established. Mobile coverage is viewport/touch emulation, not physical device testing; the suite does not cover every browser version, accessibility requirement, load level or network failure. Range flags are basic diagnostics rather than a complete drift detector. Retraining and promotion remain manual.

The managed interactive preview uses recorded scored replay data because its host lacks Python. The automated browser checks above instead used the actual live FastAPI application connected to Kafka in Docker.

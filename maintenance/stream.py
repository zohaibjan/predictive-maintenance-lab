"""Kafka producer/consumer. Offset commits follow successful durable ingestion."""
import argparse
import json
import logging
import os
from kafka import KafkaProducer, KafkaConsumer
from pydantic import ValidationError
from .data import generate
from .service import ScoringService

TOPIC='sensor-readings'

def produce(bootstrap):
    events,_=generate(n_assets=12,seed=1042,prefix='stream')
    producer=KafkaProducer(bootstrap_servers=bootstrap,acks='all',retries=5,
                           value_serializer=lambda x:json.dumps(x).encode())
    try:
        for event in sorted(events,key=lambda x:(x['timestamp'],x['asset_id'])):
            producer.send(TOPIC,key=event['asset_id'].encode(),value=event).get(timeout=30)
        producer.flush()
    finally: producer.close()


def process_message(message, scorer, commit):
    """Commit only after scoring or durable quarantine. Storage failures propagate."""
    try:
        payload=json.loads(message.value)
        scorer.ingest(payload)
    except (ValueError,ValidationError) as error:
        scorer.reject(message.value.decode(errors='replace'),error)
        logging.warning('Quarantined event at offset %s: %s',message.offset,error)
    commit()


def consume(bootstrap):
    scorer=ScoringService(os.getenv('MODEL_PATH','runtime/model.joblib'),os.getenv('DATABASE_PATH','runtime/events.db'))
    consumer=KafkaConsumer(TOPIC,bootstrap_servers=bootstrap,group_id='maintenance-scorer',
                           enable_auto_commit=False,auto_offset_reset='earliest',max_poll_records=1)
    try:
        for message in consumer:
            process_message(message,scorer,consumer.commit)
    finally: consumer.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['produce','consume'])
    p.add_argument('--bootstrap',default=os.getenv('KAFKA_BOOTSTRAP','localhost:9092'))
    args=p.parse_args(); (produce if args.command=='produce' else consume)(args.bootstrap)

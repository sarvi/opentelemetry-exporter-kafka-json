OpenTelemetry Kafka JSON Exporter
==================================

|pypi|

.. |pypi| image:: https://badge.fury.io/py/opentelemetry-exporter-kafka-json.svg
   :target: https://pypi.org/project/opentelemetry-exporter-kafka-json/

This library allows export of tracing data to `Kafka <https://kafka.io/>`_ using JSON
for serialization.

Installation
------------

::

     pip install opentelemetry-exporter-kafka-json

Example Code
------------

Initialize Tracing with Kafka::

   import os
   import socket
   import uuid
   import time
   import logging
   import json
   import pprint
   import random
   from os import environ
   from confluent_kafka import Producer
   from opentelemetry.exporter.kafka.json import KafkaExporter, StartEndSpanExporter
   from opentelemetry.sdk.trace import TracerProvider
   from opentelemetry.sdk.resources import Resource
   from opentelemetry.trace.status import Status, StatusCode
   from opentelemetry import trace
  
   def trace_init():
       resource = Resource.create(
           attributes={
               "service.name": 'cli_synthrunner',
               "service.namespace": os.environ.get('SYNTHSERVICE'),
           })

       traceprovider = TracerProvider(resource=resource)
       trace.set_tracer_provider(traceprovider)

       kafka_exporter = KafkaExporter(
           # kafkatopic="<KAFKA Topic to send tracing to",
           # kafkanodes=[<list of Kafka Nodes>],
           # version=Protocol.V2
           # optional:
           # local_node_ipv4="192.168.0.1",
           # local_node_ipv6="2001:db8::c001",
           # local_node_port=31313,
           # max_tag_value_length=256
           # timeout=5 (in seconds)
       )

       # Create a BatchSpanProcessor and add the exporter to it
       span_processor = StartEndSpanExporter(kafka_exporter)

       traceprovider.add_span_processor(span_processor)
       
       
   def trace_start(request_type, name, instance=None):
       if isinstance(name, list):
           name = ' '.join(name)
       name = os.path.basename(name)
       tested_service_type = "cli" if request_type == "EXEC" else "rest"
       tested_service_namespace=os.environ.get('TESTEDTOOL')
       if instance is not None:
           tested_service_namespace = '.'.join([tested_service_namespace, instance])
       tested_service_name=os.path.basename(name.split(' ')[0]) if request_type == "EXEC" else tested_service_namespace.split(".")[-1]
       tested_service_name=f"{tested_service_type}_{tested_service_name}".lower()
       tested_service_method=f"{tested_service_type}/{name}".replace(" ", "/") if request_type == "EXEC" else f"{tested_service_type}/{request_type}{name}"
       assert tested_service_name is not None

       span = tracer.start_span(
           f"{tested_service_namespace}.{tested_service_name}/{tested_service_method}",
           kind=trace.SpanKind.CLIENT,
           attributes={
               "peer.service.namespace": f"{tested_service_namespace}",
               "peer.service.name": f"{tested_service_name}",
               "peer.service.method": f"{tested_service_method}",
               'location.site': environ.get('SITE', 'unknown')
           })
       return span

   def trace_end(span, status):
       span.set_status(trace.status.Status(status))
       span.end()


References
----------

* `OpenTelemetry Kafka Exporter <https://opentelemetry-python.readthedocs.io/en/latest/exporter/kafka/kafka.html>`_
* `Kafka <https://kafka.io/>`_
* `OpenTelemetry Project <https://opentelemetry.io/>`_

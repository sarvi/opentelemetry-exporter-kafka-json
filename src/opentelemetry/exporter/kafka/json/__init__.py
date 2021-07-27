# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
OpenTelemetry Kafka JSON Exporter
----------------------------------

This library allows to export tracing data to `Kafka <https://kafka.io/>`_.

Usage
-----

The **OpenTelemetry Kafka JSON Exporter** allows exporting of `OpenTelemetry`_
traces to `Kafka`_. This exporter sends traces to the configured Kafka
collector endpoint using JSON over HTTP and supports multiple versions (v1, ).

.. _Kafka: https://kafka.io/
.. _OpenTelemetry: https://github.com/open-telemetry/opentelemetry-python/
.. _Specification: https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/sdk-environment-variables.md#kafka-exporter

.. code:: python

    from opentelemetry import trace
    from opentelemetry.exporter.kafka.json import ZipkinExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)

    # create a ZipkinExporter
    zipkin_exporter = ZipkinExporter(
        # version=Protocol.V1
        # optional:
        # endpoint="http://localhost:9411/api/v2/spans",
        # local_node_ipv4="192.168.0.1",
        # local_node_ipv6="2001:db8::c001",
        # local_node_port=31313,
        # max_tag_value_length=256
        # timeout=5 (in seconds)
    )

    # Create a BatchSpanProcessor and add the exporter to it
    span_processor = BatchSpanProcessor(zipkin_exporter)

    # add to the tracer
    trace.get_tracer_provider().add_span_processor(span_processor)

    with tracer.start_as_current_span("foo"):
        print("Hello world!")

The exporter supports the following environment variable for configuration:

- :envvar:`OTEL_EXPORTER_ZIPKIN_ENDPOINT`
- :envvar:`OTEL_EXPORTER_ZIPKIN_TIMEOUT`

API
---
"""

import logging
from os import environ
from typing import Optional, Sequence
import socket
import requests

from opentelemetry.exporter.kafka.encoder import (
    DEFAULT_MAX_TAG_VALUE_LENGTH,
    Encoder,
    Protocol,
)
from opentelemetry.exporter.kafka.json.v1 import JsonV1Encoder
from opentelemetry.exporter.kafka.node_endpoint import IpInput, NodeEndpoint
# from opentelemetry.sdk.environment_variables import (
#     OTEL_EXPORTER_ZIPKIN_ENDPOINT,
#     OTEL_EXPORTER_ZIPKIN_TIMEOUT,
# )
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import (
    Span,
    format_trace_id,
)
from confluent_kafka import Producer

DEFAULT_ENDPOINT = "http://localhost:9411/api/v2/spans"
DEFAULT_KAFKATOPIC = "unknown_topic"
DEFAULT_KAFKANODES = "localhost:9092"
REQUESTS_SUCCESS_STATUS_CODES = (200, 202)

OTEL_EXPORTER_KAFKA_TOPIC="OTEL_EXPORTER_KAFKA_TOPIC"
OTEL_EXPORTER_KAFKA_NODES="OTEL_EXPORTER_KAFKA_NODES"

logger = logging.getLogger(__name__)


class KafkaExporter(SpanExporter):
    def __init__(
        self,
        kafkatopic: Optional[str] = None,
        kafkanodes: Sequence[str] = None,
        version: Protocol = Protocol.V1,
        endpoint: Optional[str] = None,
        local_node_ipv4: IpInput = None,
        local_node_ipv6: IpInput = None,
        local_node_port: Optional[int] = None,
        max_tag_value_length: Optional[int] = None,
        timeout: Optional[int] = None,
    ):
        """Kafka exporter.

        Args:
            version: The protocol version to be used.
            endpoint: The endpoint of the Kafka collector.
            local_node_ipv4: Primary IPv4 address associated with this connection.
            local_node_ipv6: Primary IPv6 address associated with this connection.
            local_node_port: Depending on context, this could be a listen port or the
                client-side of a socket.
            max_tag_value_length: Max length string attribute values can have.
            timeout: Maximum time the Kafka exporter will wait for each batch export.
                The default value is 10s.

            The tuple (local_node_ipv4, local_node_ipv6, local_node_port) is used to represent
            the network context of a node in the service graph.
        """
        if not local_node_ipv4:
            local_node_ipv4 = socket.gethostbyname(socket.gethostname())
        if not local_node_ipv6:
            try:
                local_node_ipv6 = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6)
            except socket.gaierror:
                pass
        self.local_node = NodeEndpoint(
            local_node_ipv4, local_node_ipv6, local_node_port
        )

        if kafkatopic is None:
            kafkatopic = (
                environ.get(OTEL_EXPORTER_KAFKA_TOPIC) or DEFAULT_KAFKATOPIC
            )
        self.kafkatopic = kafkatopic
        if kafkanodes is None:
            kafkanodes = (
                [x.strip() for x in (environ.get(OTEL_EXPORTER_KAFKA_NODES) or DEFAULT_KAFKANODES).split(',')]
            )
        self.kafkanodes = kafkanodes

        if version == Protocol.V1:
            self.encoder = JsonV1Encoder(max_tag_value_length)
        self._closed = False

    def export(self, spans: Sequence[Span]) -> SpanExportResult:
        # After the call to Shutdown subsequent calls to Export are
        # not allowed and should return a Failure result
        if self._closed:
            logger.warning("Exporter already shutdown, ignoring batch")
            return SpanExportResult.FAILURE

        # Populate service_name from first span
        # We restrict any SpanProcessor to be only associated with a single
        # TracerProvider, so it is safe to assume that all Spans in a single
        # batch all originate from one TracerProvider (and in turn have all
        # the same service.name)
        if spans:
            service_name = spans[0].resource.attributes.get(SERVICE_NAME)
            if service_name:
                self.local_node.service_name = service_name
        rv = None
        for span in spans:
            context = span.get_span_context()
            data=self.encoder.serialize(span, self.local_node)
            if not (self.kafkanodes and self.kafkatopic):
                # telemetry kafka config not initialized
                logger.debug("Telemetry: {}".format(data))
                logger.debug(f"Not sending telemetry. kafka_topic={self.kafkatopic} OR kafka_nodes={self.kafka_nodes} not defined. \nTelemetry")
                return
            logger.debug("Sending telemetry to {} on {}\n{}".format(self.kafkatopic, self.kafkanodes, data))
            producer = Producer({'bootstrap.servers': ','.join(self.kafkanodes)})
            rv = rv or producer.produce(self.kafkatopic, key=format_trace_id(context.trace_id), value=data)
            producer.flush()

        if rv is not None:
            logger.error("Traces cannot be uploaded; status code: %s", rv)
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        if self._closed:
            logger.warning("Exporter already shutdown, ignoring call")
            return
        self._closed = True

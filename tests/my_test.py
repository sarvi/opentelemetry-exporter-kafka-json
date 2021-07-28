from os import environ
import logging
import time
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.exporter.kafka.json import KafkaExporter, StartEndSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource

# logger.setLevel(logging.DEBUG)

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

resource = Resource.create(
    attributes={
        "service.name": 'cli_synthrunner',
        "service.namespace": 'com.cisco.devx.synthrunner',
    })

traceprovider = TracerProvider(resource=resource)
trace.set_tracer_provider(traceprovider)

# create a ZipkinExporter
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

tracer = trace.get_tracer(__name__)

tested_service_namespace='com.cisco.devx.wit'
tested_service_name='cli_wit'
tested_service_method='cli/wit/space/create'


with tracer.start_as_current_span(f"{tested_service_namespace}.{tested_service_name}{tested_service_method}", kind=trace.SpanKind.CLIENT) as span:
    span.set_attributes({
        "peer.service.namespace": f"{tested_service_namespace}",
        "peer.service.name": f"{tested_service_name}",
        "peer.service.method": f"{tested_service_method}",
        'location.site': environ.get('SITE', 'unknown')
    })
    print("Hello world!")
    time.sleep(5)
    span.set_status(Status(StatusCode.OK))
time.sleep(5)
print('Hello World')



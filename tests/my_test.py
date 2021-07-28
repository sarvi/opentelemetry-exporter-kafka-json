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
        "service.name": '.'.join(["com.cisco.devx", 'synthrunner']),
    })

traceprovider = TracerProvider(resource=resource)

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

trace.set_tracer_provider(traceprovider)

tracer = trace.get_tracer(__name__)

testedservice='A'
testedmicroservice='B'
method='C'


with tracer.start_as_current_span("com.cisco.devx.wit.cli_wit/cli/wit/space/create", kind=trace.SpanKind.CLIENT) as span:
    span.set_attributes({
        "peer.servicegroup": f"{testedservice}",
        "peer.service": f"{testedservice}.{testedmicroservice}",
        "peer.endpoint": f"{method}",
        'enduser.id': environ.get('USER', 'ngdevx'),
        'location.site': environ.get('SITE', 'unknown')
    })
    print("Hello world!")
    time.sleep(5)
    span.set_status(Status(StatusCode.OK))
time.sleep(5)
print('Hello World')



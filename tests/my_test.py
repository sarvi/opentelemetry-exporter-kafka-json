from os import environ
import logging
import time
import typing
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.exporter.kafka.json import KafkaExporter
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.context import Context, attach, detach, set_value
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY

# logger.setLevel(logging.DEBUG)

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

resource = Resource.create(attributes={
        "service.name": '.'.join(["com.cisco.devx", 'synthrunner']),
    })

trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

# create a ZipkinExporter
kafka_exporter = KafkaExporter(
    # version=Protocol.V2
    # optional:
    # endpoint="http://localhost:9411/api/v2/spans",
    # local_node_ipv4="192.168.0.1",
    # local_node_ipv6="2001:db8::c001",
    # local_node_port=31313,
    # max_tag_value_length=256
    # timeout=5 (in seconds)
)

class StartEndSpanExporter(SimpleSpanProcessor):
    def on_start(
        self, span: Span, parent_context: typing.Optional[Context] = None
    ) -> None:
        if not span.context.trace_flags.sampled:
            return
        token = attach(set_value(_SUPPRESS_INSTRUMENTATION_KEY, True))
        try:
            self.span_exporter.export((span,))
        # pylint: disable=broad-except
        except Exception:
            logger.exception("Exception while exporting Span Start.")
        detach(token)


# Create a BatchSpanProcessor and add the exporter to it
span_processor = StartEndSpanExporter(kafka_exporter)

# add to the tracer
trace.get_tracer_provider().add_span_processor(span_processor)
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



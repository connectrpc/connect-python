# connectrpc-otel

OpenTelemetry instrumentation for connect-python to generate server and client spans and metrics
for ConnectRPC requests with support for auto-instrumentation.

## Example

```python

from connectrpc_otel import OpenTelemetryInterceptor

from eliza_connect import ElizaServiceWSGIApplication, ElizaServiceClientSync

from ._service import MyElizaService

app = ElizaServiceWSGIApplication(MyElizaService(), interceptors=[OpenTelemetryInterceptor()])

def make_request():
    client = ElizaServiceClientSync("http://localhost:8080", interceptors=[OpenTelemetryInterceptor(client=True)])
    resp = client.Say(SayRequest(sentence="Hello!"))
    print(resp)
```

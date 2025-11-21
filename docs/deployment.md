# Deployment

After building a Connect service, you still need to deploy it to production. This guide covers how to
use a Python application server to run a service.

## Application Servers

Connect services are standard ASGI or WSGI applications that can be run with an off-the-shelf Python
application server. This means generally, any experience in running a Python application can be applied
to running Connect as-is.

### HTTP/1.1

Connect only requires HTTP/2 for bidirectional streaming RPCs - the vast majority of services can be run
using HTTP/1.1 without issue. Two servers have long been in use with HTTP/1.1 and have a proven track
record. If you are unsure what server to use, it is generally a safe bet to use one of them:

- [gunicorn](http://www.gunicorn.org/) for WSGI applications
- [uvicorn](https://uvicorn.dev/) for ASGI applications

### HTTP/2

If your service uses bidirectional or otherwise want to use HTTP/2, the above servers will not work.
HTTP/2 support in the Python ecosystem is still relatively young - servers known to support HTTP/2
with bidirectional streaming are:

- [granian](https://github.com/emmett-framework/granian)
- [hypercorn](https://hypercorn.readthedocs.io/en/latest/)
- [pyvoy](https://github.com/curioswitch/pyvoy)

Connect has an extensive test suite to verify compatibility of connect-python with the Connect protocol.
Unfortunately, we are only able to reliably pass the suite with pyvoy, with other servers occasionally
having hung requests or stream ordering issues. pyvoy was built with connect-python in mind but is
very new and needs more time with real-world applications to verify stability.

Keep the above in mind when picking an HTTP/2 server and let us know how it goes if you give any a try.
When in doubt, if you do not use bidirectional streaming, we recommend one of the HTTP/1.1 servers.

## CORS

Connect services are standard ASGI and WSGI applications so any CORS middleware can be used to
enable it.

For example, with an ASGI application using Starlette:

```python
from starlette.middleware.cors import CORSMiddleware
from starlette.applications import Starlette

app = Starlette()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
# Mount your Connect application
```

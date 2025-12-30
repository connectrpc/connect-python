# Get Requests and Caching

Connect supports performing idempotent, side-effect free requests using an HTTP GET-based protocol.
This makes it easier to cache certain kinds of requests in the browser, on your CDN, or in proxies and
other middleboxes.

If you are using clients to make query-style requests, you may want the ability to use Connect HTTP GET
request support. To opt-in for a given procedure, you must mark it as being side-effect free using the
`MethodOptions.IdempotencyLevel` option:

```protobuf
service ElizaService {
  rpc Say(SayRequest) returns (SayResponse) {
    option idempotency_level = NO_SIDE_EFFECTS;
  }
}
```

Services will automatically support GET requests using this option.

It is still necessary to opt-in to HTTP GET on your client, as well. Generated clients include a
`use_get` parameter for methods that are marked with `NO_SIDE_EFFECTS`.

### Async

```python
response = await client.say(SayRequest(sentence="Hello"), use_get=True)
```

### Sync

  ```python
  response = client.say(SayRequest(sentence="Hello"), use_get=True)
  ```

For other clients, see their respective documentation pages:

- [Connect Node](https://connectrpc.com/docs/node/get-requests-and-caching)
- [Connect Web](https://connectrpc.com/docs/web/get-requests-and-caching)
- [Connect Kotlin](https://connectrpc.com/docs/kotlin/get-requests-and-caching)

## Caching

Using GET requests will not necessarily automatically make browsers or proxies cache your RPCs.
To ensure that requests are allowed to be cached, a handler should also set the appropriate headers.

For example, you may wish to set the `Cache-Control` header with a `max-age` directive:

```python
ctx.response_headers()["cache-control"] = "max-age=604800"
return SayResponse()
```

This would instruct agents and proxies that the request may be cached for up to 7 days, after which
it must be re-requested. There are other [`Cache-Control` Response Directives](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control#response_directives)
that may be useful for your application as well; for example, the `private` directive would specify that
the request should only be cached in private caches, such as the user agent itself, and _not_ CDNs or reverse
proxies — this would be appropriate, for example, for authenticated requests.

## Distinguishing GET Requests

In some cases, you might want to introduce behavior that only occurs when handling HTTP GET requests.
This can be accomplished with `RequestContext.http_method`:

```python
if ctx.http_method() == "GET":
    ctx.response_headers()["cache-control"] = "max-age=604800"
return SayResponse()
```

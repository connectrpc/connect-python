# gRPC compatibility

Connect-Python currently does not support the gRPC protocol due to lack of support for HTTP/2 trailers
in the Python ecosystem. If you have an existing codebase using grpc-python and want to introduce Connect
in a transition without downtime, you will need a way for the gRPC servers to be accessible from both
gRPC and Connect clients at the same time. Envoy is a widely used proxy server with support for translating
the Connect protocol to gRPC via the [Connect-gRPC Bridge](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/connect_grpc_bridge_filter).

For example, if you have a gRPC server currently listening on port 8080, you update it to use port 8081
and expose the service for both Connect and gRPC clients on port 8080 with this config.

```yaml
admin:
  address:
    socket_address: { address: 0.0.0.0, port_value: 9090 }

static_resources:
  listeners:
    - name: listener_0
      address:
        socket_address: { address: 0.0.0.0, port_value: 8080 }
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: ingress_http
                codec_type: AUTO
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: local_service
                      domains: ["*"]
                      routes:
                        - match: { prefix: "/" }
                          route: { cluster: service_0 }
                http_filters:
                  - name: envoy.filters.http.connect_grpc_bridge
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.connect_grpc_bridge.v3.FilterConfig
                  - name: envoy.filters.http.grpc_web
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.grpc_web.v3.GrpcWeb
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
  clusters:
    - name: service_0
      connect_timeout: 0.25s
      type: STRICT_DNS
      lb_policy: ROUND_ROBIN
      load_assignment:
        cluster_name: service_0
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: 127.0.0.1
                      port_value: 8081
      typed_extension_protocol_options:
        envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
          "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
          explicit_http_config:
            http2_protocol_options:
              max_concurrent_streams: 100
```

Refer to [Envoy docs](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/security/ssl) for more configuration such
as TLS.

## Migration

Migrating from grpc-python to Connect using Envoy largely involves first adding Envoy in front of the server,
then migrating clients to Connect, and finally migrating servers to Connect and removing Envoy.

The general code structure of grpc-python and Connect are very similar - if your code is configured to use a
type checker, any changes to parameter names and such should be quite easy to spot.

1. Reconfigure your gRPC servers to include Envoy in front of the server port with a config similar to above.
   For cloud deployments, this often means using functionality for sidecar containers.

1. Begin generating code with `protoc-gen-connect-python`.

1. Migrate clients to use Connect. Replace any special configuration of `ManagedChannel` with configured `httpx.Client` or
   `httpx.AsyncClient` and switch to Connect's generated client types. If passing `metadata` at the call site, change
   to `headers` - lists of string tuples can be passed directly to a `Headers` constructor, or can be changed to a raw
   dictionary. Update any error handling to catch `ConnectError`.

1. Complete deployment of all servers using Connect client. After this is done, your gRPC servers will only
   be receiving traffic using the Connect protocol.

1. Migrate service implementations to Connect generated stubs. It is recommended to extend the protocol classes
   to have type checking find differences in method names. Change uses of `abort` to directly `raise ConnectError` -
   for Connect services, it will be uncommon to pass the `RequestContext` into business logic code.

1. Reconfigure server deployment to remove the Envoy proxy and deploy. You're done! You can stop generating code with
   gRPC.

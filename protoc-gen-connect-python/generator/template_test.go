package generator

import (
	"bytes"
	"strings"
	"testing"
)

func TestConnectTemplate(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name     string
		vars     ConnectTemplateVariables
		contains []string
	}{
		{
			name: "simple service",
			vars: ConnectTemplateVariables{
				FileName:   "test.proto",
				ModuleName: "test",
				Services: []*ConnectService{
					{
						Package: "test",
						Name:    "TestService",
						Methods: []*ConnectMethod{
							{
								Package:       "test",
								ServiceName:   "TestService",
								Name:          "TestMethod",
								PythonName:    "TestMethod",
								InputType:     "_pb2.TestRequest",
								OutputType:    "_pb2.TestResponse",
								NoSideEffects: false,
							},
						},
					},
				},
			},
			contains: []string{
				"from collections.abc import AsyncGenerator, AsyncIterator, Iterable, Iterator, Mapping",
				"class TestService(Protocol):",
				"class TestServiceASGIApplication(ConnectASGIApplication[TestService]):",
				"def TestMethod",
			},
		},
		{
			name: "service with no side effects method",
			vars: ConnectTemplateVariables{
				FileName:   "test.proto",
				ModuleName: "test",
				Services: []*ConnectService{
					{
						Package: "test",
						Name:    "TestService",
						Methods: []*ConnectMethod{
							{
								Package:       "test",
								ServiceName:   "TestService",
								Name:          "GetData",
								PythonName:    "GetData",
								InputType:     "_pb2.GetRequest",
								OutputType:    "_pb2.GetResponse",
								NoSideEffects: true,
							},
						},
					},
				},
			},
			contains: []string{
				"use_get: bool = False",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			var buf bytes.Buffer
			err := ConnectTemplate.Execute(&buf, tt.vars)
			if err != nil {
				t.Fatalf("Template execution failed: %v", err)
			}

			result := buf.String()
			for _, want := range tt.contains {
				if !strings.Contains(result, want) {
					t.Errorf("Generated code missing expected content: %q, got: %q", want, result)
				}
			}
		})
	}
}

func TestConnectTemplateRequestContextTypeParams(t *testing.T) {
	t.Parallel()

	vars := ConnectTemplateVariables{
		FileName:   "test.proto",
		ModuleName: "test",
		Services: []*ConnectService{
			{
				Package: "test",
				Name:    "TestService",
				Methods: []*ConnectMethod{
					{
						Package:     "test",
						ServiceName: "TestService",
						Name:        "Unary",
						PythonName:  "Unary",
						InputType:   "_pb2.TestRequest",
						OutputType:  "_pb2.TestResponse",
					},
					{
						Package:        "test",
						ServiceName:    "TestService",
						Name:           "Bidi",
						PythonName:     "Bidi",
						InputType:      "_pb2.StreamRequest",
						OutputType:     "_pb2.StreamResponse",
						Stream:         true,
						RequestStream:  true,
						ResponseStream: true,
					},
				},
			},
		},
	}

	var buf bytes.Buffer
	if err := ConnectTemplate.Execute(&buf, vars); err != nil {
		t.Fatalf("Template execution failed: %v", err)
	}
	result := buf.String()

	for _, want := range []string{
		"ctx: RequestContext[_pb2.TestRequest, _pb2.TestResponse]",
		"ctx: RequestContext[_pb2.StreamRequest, _pb2.StreamResponse]",
	} {
		if !strings.Contains(result, want) {
			t.Errorf("generated handler missing parameterized context %q\n--- got ---\n%s", want, result)
		}
	}

	// A bare RequestContext on a handler signature is an implicit RequestContext[Any, Any];
	// none should remain.
	for _, bad := range []string{"ctx: RequestContext)", "ctx: RequestContext,", "ctx: RequestContext "} {
		if strings.Contains(result, bad) {
			t.Errorf("generated handler still emits bare context %q\n--- got ---\n%s", bad, result)
		}
	}

	// The context's type params must be the bare message types, never the stream-wrapped
	// forms -- they have to agree with MethodInfo(input=..., output=...).
	for _, bad := range []string{"RequestContext[AsyncIterator", "RequestContext[Iterator"} {
		if strings.Contains(result, bad) {
			t.Errorf("context type params must be bare messages, not stream-wrapped: found %q\n--- got ---\n%s", bad, result)
		}
	}
}

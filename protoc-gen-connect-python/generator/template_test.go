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

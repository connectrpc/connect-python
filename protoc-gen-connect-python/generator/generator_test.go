package generator

import (
	"bytes"
	"io"
	"strings"
	"testing"

	"github.com/bufbuild/protoplugin"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/types/descriptorpb"
	"google.golang.org/protobuf/types/pluginpb"
)

func TestGenerateConnectFile(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name     string
		input    *descriptorpb.FileDescriptorProto
		wantFile string
		wantErr  bool
	}{
		{
			name: "simple service",
			input: &descriptorpb.FileDescriptorProto{
				Name:    proto.String("test.proto"),
				Package: proto.String("test"),
				Service: []*descriptorpb.ServiceDescriptorProto{
					{
						Name: proto.String("TestService"),
						Method: []*descriptorpb.MethodDescriptorProto{
							{
								Name:       proto.String("TestMethod"),
								InputType:  proto.String(".test.TestRequest"),
								OutputType: proto.String(".test.TestResponse"),
							},
						},
					},
				},
				MessageType: []*descriptorpb.DescriptorProto{
					{
						Name: proto.String("TestRequest"),
					},
					{
						Name: proto.String("TestResponse"),
					},
				},
			},
			wantFile: "test_connect.py",
			wantErr:  false,
		},
		{
			name: "service with multiple methods",
			input: &descriptorpb.FileDescriptorProto{
				Name:    proto.String("multi.proto"),
				Package: proto.String("test"),
				Service: []*descriptorpb.ServiceDescriptorProto{
					{
						Name: proto.String("MultiService"),
						Method: []*descriptorpb.MethodDescriptorProto{
							{
								Name:       proto.String("Method1"),
								InputType:  proto.String(".test.Request1"),
								OutputType: proto.String(".test.Response1"),
							},
							{
								Name:       proto.String("Method2"),
								InputType:  proto.String(".test.Request2"),
								OutputType: proto.String(".test.Response2"),
							},
						},
					},
				},
				MessageType: []*descriptorpb.DescriptorProto{
					{
						Name: proto.String("Request1"),
					},
					{
						Name: proto.String("Response1"),
					},
					{
						Name: proto.String("Request2"),
					},
					{
						Name: proto.String("Response2"),
					},
				},
			},
			wantFile: "multi_connect.py",
			wantErr:  false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			fd, err := protodesc.NewFile(tt.input, nil)
			if err != nil {
				t.Fatalf("Failed to create FileDescriptorProto: %v", err)
				return
			}
			gotName, gotContent, err := generateConnectFile(fd, Config{})
			if (err != nil) != tt.wantErr {
				t.Errorf("generateConnectFile() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err == nil {
				if gotName != tt.wantFile {
					t.Errorf("generateConnectFile() got filename = %v, want %v", gotName, tt.wantFile)
				}

				content := gotContent
				if !strings.Contains(content, "from collections.abc import AsyncGenerator, AsyncIterator, Iterable, Iterator, Mapping") {
					t.Error("Generated code missing required imports")
				}
				if !strings.Contains(content, "class "+strings.Split(tt.input.GetService()[0].GetName(), ".")[0]) {
					t.Error("Generated code missing service class")
				}
			}
		})
	}
}

func TestGenerate(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name        string
		req         *pluginpb.CodeGeneratorRequest
		wantStrings []string
		wantErr     bool
	}{
		{
			name: "empty request",
			req: &pluginpb.CodeGeneratorRequest{
				FileToGenerate: []string{},
			},
			wantErr: true,
		},
		{
			name: "valid request",
			req: &pluginpb.CodeGeneratorRequest{
				FileToGenerate: []string{"test.proto"},
				ProtoFile: []*descriptorpb.FileDescriptorProto{
					{
						Name:       proto.String("test.proto"),
						Package:    proto.String("test"),
						Dependency: []string{"other.proto"},
						Service: []*descriptorpb.ServiceDescriptorProto{
							{
								Name: proto.String("TestService"),
								Method: []*descriptorpb.MethodDescriptorProto{
									{
										Name:       proto.String("TestMethod"),
										InputType:  proto.String(".test.TestRequest"),
										OutputType: proto.String(".test.TestResponse"),
									},
									{
										Name:       proto.String("TestMethod2"),
										InputType:  proto.String(".otherpackage.OtherRequest"),
										OutputType: proto.String(".otherpackage.OtherResponse"),
									},
									// Reserved keyword
									{
										Name:       proto.String("Try"),
										InputType:  proto.String(".otherpackage.OtherRequest"),
										OutputType: proto.String(".otherpackage.OtherResponse"),
									},
								},
							},
						},
						MessageType: []*descriptorpb.DescriptorProto{
							{
								Name: proto.String("TestRequest"),
							},
							{
								Name: proto.String("TestResponse"),
							},
						},
					},
					{
						Name:    proto.String("other.proto"),
						Package: proto.String("otherpackage"),
						MessageType: []*descriptorpb.DescriptorProto{
							{
								Name: proto.String("OtherRequest"),
							},
							{
								Name: proto.String("OtherResponse"),
							},
						},
					},
				},
			},
			wantErr:     false,
			wantStrings: []string{"def try_(self"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			resp := generate(t, tt.req)
			if tt.wantErr {
				if resp.GetError() == "" {
					t.Error("generate() expected error but got none")
				}
			} else {
				if resp.GetError() != "" {
					t.Errorf("generate() unexpected error: %v", resp.GetError())
				}
				if len(resp.GetFile()) == 0 {
					t.Error("generate() returned no files")
				}
				for _, s := range tt.wantStrings {
					if !strings.Contains(resp.GetFile()[0].GetContent(), s) {
						t.Errorf("generate() missing expected string: %v", s)
					}
				}
			}
		})
	}
}

func TestEditionSupport(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name              string
		edition           descriptorpb.Edition
		protoFileName     string
		packageName       string
		serviceName       string
		wantMinEdition    descriptorpb.Edition
		wantMaxEdition    descriptorpb.Edition
		wantGeneratedFile string
		wantServiceClass  string
	}{
		{
			name:              "edition 2023",
			edition:           descriptorpb.Edition_EDITION_2023,
			protoFileName:     "test_edition2023.proto",
			packageName:       "test.edition2023",
			serviceName:       "Edition2023Service",
			wantMinEdition:    descriptorpb.Edition_EDITION_PROTO3,
			wantMaxEdition:    descriptorpb.Edition_EDITION_2024,
			wantGeneratedFile: "test_edition2023_connect.py",
			wantServiceClass:  "class Edition2023Service",
		},
		{
			name:              "edition 2024",
			edition:           descriptorpb.Edition_EDITION_2024,
			protoFileName:     "test_edition2024.proto",
			packageName:       "test.edition2024",
			serviceName:       "Edition2024Service",
			wantMinEdition:    descriptorpb.Edition_EDITION_PROTO3,
			wantMaxEdition:    descriptorpb.Edition_EDITION_2024,
			wantGeneratedFile: "test_edition2024_connect.py",
			wantServiceClass:  "class Edition2024Service",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			req := &pluginpb.CodeGeneratorRequest{
				FileToGenerate: []string{tt.protoFileName},
				ProtoFile: []*descriptorpb.FileDescriptorProto{
					{
						Name:    proto.String(tt.protoFileName),
						Package: proto.String(tt.packageName),
						Edition: tt.edition.Enum(),
						Options: &descriptorpb.FileOptions{
							Features: &descriptorpb.FeatureSet{
								FieldPresence: descriptorpb.FeatureSet_EXPLICIT.Enum(),
							},
						},
						Service: []*descriptorpb.ServiceDescriptorProto{
							{
								Name: proto.String(tt.serviceName),
								Method: []*descriptorpb.MethodDescriptorProto{
									{
										Name:       proto.String("TestMethod"),
										InputType:  proto.String("." + tt.packageName + ".TestRequest"),
										OutputType: proto.String("." + tt.packageName + ".TestResponse"),
									},
								},
							},
						},
						MessageType: []*descriptorpb.DescriptorProto{
							{
								Name: proto.String("TestRequest"),
								Field: []*descriptorpb.FieldDescriptorProto{
									{
										Name:   proto.String("message"),
										Number: proto.Int32(1),
										Label:  descriptorpb.FieldDescriptorProto_LABEL_OPTIONAL.Enum(),
										Type:   descriptorpb.FieldDescriptorProto_TYPE_STRING.Enum(),
									},
								},
							},
							{
								Name: proto.String("TestResponse"),
								Field: []*descriptorpb.FieldDescriptorProto{
									{
										Name:   proto.String("result"),
										Number: proto.Int32(1),
										Label:  descriptorpb.FieldDescriptorProto_LABEL_OPTIONAL.Enum(),
										Type:   descriptorpb.FieldDescriptorProto_TYPE_STRING.Enum(),
									},
								},
							},
						},
					},
				},
			}

			resp := generate(t, req)

			if resp.GetError() != "" {
				t.Fatalf("generate() failed for %s proto: %v", tt.name, resp.GetError())
			}

			if resp.GetSupportedFeatures()&uint64(pluginpb.CodeGeneratorResponse_FEATURE_SUPPORTS_EDITIONS) == 0 {
				t.Error("Generator should declare FEATURE_SUPPORTS_EDITIONS")
			}

			if resp.GetMinimumEdition() != int32(tt.wantMinEdition) {
				t.Errorf("Expected minimum edition %v, got %v", tt.wantMinEdition, resp.GetMinimumEdition())
			}
			if resp.GetMaximumEdition() != int32(tt.wantMaxEdition) {
				t.Errorf("Expected maximum edition %v, got %v", tt.wantMaxEdition, resp.GetMaximumEdition())
			}

			if len(resp.GetFile()) == 0 {
				t.Errorf("No files generated for %s proto", tt.name)
				return
			}

			generatedFile := resp.GetFile()[0]
			if generatedFile.GetName() != tt.wantGeneratedFile {
				t.Errorf("Expected filename %s, got %v", tt.wantGeneratedFile, generatedFile.GetName())
			}

			content := generatedFile.GetContent()
			if !strings.Contains(content, tt.wantServiceClass) {
				t.Errorf("Generated code missing %s", tt.wantServiceClass)
			}
		})
	}
}

// generate is a test helper that runs the plugin handler using [protoplugin.Run].
func generate(t *testing.T, req *pluginpb.CodeGeneratorRequest) *pluginpb.CodeGeneratorResponse {
	t.Helper()

	// Marshal request to bytes for stdin
	reqBytes, err := proto.Marshal(req)
	if err != nil {
		resp := &pluginpb.CodeGeneratorResponse{}
		resp.Error = proto.String("failed to marshal request: " + err.Error())
		return resp
	}

	// Prepare stdin and stdout
	stdin := bytes.NewReader(reqBytes)
	stdout := &bytes.Buffer{}

	// Run the plugin
	err = protoplugin.Run(
		t.Context(),
		protoplugin.Env{
			Args:    nil,
			Environ: nil,
			Stdin:   stdin,
			Stdout:  stdout,
			Stderr:  io.Discard,
		},
		protoplugin.HandlerFunc(Handle),
	)
	if err != nil {
		resp := &pluginpb.CodeGeneratorResponse{}
		resp.Error = proto.String("failed to run plugin: " + err.Error())
		return resp
	}

	// Unmarshal response
	resp := &pluginpb.CodeGeneratorResponse{}
	if err := proto.Unmarshal(stdout.Bytes(), resp); err != nil {
		errorResp := &pluginpb.CodeGeneratorResponse{}
		errorResp.Error = proto.String("failed to unmarshal response: " + err.Error())
		return errorResp
	}
	return resp
}

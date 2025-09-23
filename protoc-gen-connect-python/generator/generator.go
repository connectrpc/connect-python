package generator

import (
	"bytes"
	"fmt"
	"path"
	"slices"
	"strings"
	"unicode"

	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/types/descriptorpb"
	"google.golang.org/protobuf/types/pluginpb"
)

func Generate(r *pluginpb.CodeGeneratorRequest) *pluginpb.CodeGeneratorResponse {
	resp := &pluginpb.CodeGeneratorResponse{}

	resp.SupportedFeatures = proto.Uint64(uint64(pluginpb.CodeGeneratorResponse_FEATURE_PROTO3_OPTIONAL) | uint64(pluginpb.CodeGeneratorResponse_FEATURE_SUPPORTS_EDITIONS))
	resp.MinimumEdition = proto.Int32(int32(descriptorpb.Edition_EDITION_PROTO3))
	resp.MaximumEdition = proto.Int32(int32(descriptorpb.Edition_EDITION_2023))

	conf := parseConfig(r.GetParameter())

	files := r.GetFileToGenerate()
	if len(files) == 0 {
		resp.Error = proto.String("no files to generate")
		return resp
	}

	fds := &descriptorpb.FileDescriptorSet{
		File: r.GetProtoFile(),
	}
	reg, err := protodesc.NewFiles(fds)
	if err != nil {
		panic(err)
	}

	reg.RangeFiles(func(fd protoreflect.FileDescriptor) bool {
		if !slices.Contains(files, string(fd.Path())) {
			return true
		}

		// We don't generate any code for non-services
		if fd.Services().Len() == 0 {
			return true
		}

		connectFile, err := GenerateConnectFile(fd, conf)
		if err != nil {
			resp.Error = proto.String("File[" + fd.Path() + "][generate]: " + err.Error())
			return false
		}
		resp.File = append(resp.File, connectFile)
		return true
	})

	return resp
}

func GenerateConnectFile(fd protoreflect.FileDescriptor, conf Config) (*pluginpb.CodeGeneratorResponse_File, error) {
	filename := fd.Path()

	fileNameWithoutSuffix := strings.TrimSuffix(filename, path.Ext(filename))
	moduleName := strings.Join(strings.Split(fileNameWithoutSuffix, "/"), ".")

	vars := ConnectTemplateVariables{
		FileName:   filename,
		ModuleName: moduleName,
		Imports:    importStatements(fd, conf),
	}

	svcs := fd.Services()
	packageName := string(fd.Package())
	for i := 0; i < svcs.Len(); i++ {
		svc := svcs.Get(i)
		connectSvc := &ConnectService{
			Name:     string(svc.Name()),
			FullName: string(svc.FullName()),
			Package:  packageName,
		}

		methods := svc.Methods()
		for j := 0; j < methods.Len(); j++ {
			method := methods.Get(j)
			idempotencyLevel := "UNKNOWN"
			noSideEffects := false
			if mo, ok := method.Options().(*descriptorpb.MethodOptions); ok {
				switch mo.GetIdempotencyLevel() {
				case descriptorpb.MethodOptions_NO_SIDE_EFFECTS:
					idempotencyLevel = "NO_SIDE_EFFECTS"
				case descriptorpb.MethodOptions_IDEMPOTENT:
					idempotencyLevel = "IDEMPOTENT"
				}
			}
			endpointType := "unary"
			if method.IsStreamingClient() && method.IsStreamingServer() {
				endpointType = "bidi_stream"
			} else if method.IsStreamingClient() {
				endpointType = "client_stream"
			} else if method.IsStreamingServer() {
				endpointType = "server_stream"
			} else if idempotencyLevel == "NO_SIDE_EFFECTS" {
				noSideEffects = true
			}
			connectMethod := &ConnectMethod{
				Package:          packageName,
				ServiceName:      connectSvc.FullName,
				Name:             string(method.Name()),
				PythonName:       pythonMethodName(string(method.Name()), conf),
				InputType:        symbolName(method.Input()),
				OutputType:       symbolName(method.Output()),
				EndpointType:     endpointType,
				Stream:           method.IsStreamingClient() || method.IsStreamingServer(),
				RequestStream:    method.IsStreamingClient(),
				ResponseStream:   method.IsStreamingServer(),
				NoSideEffects:    noSideEffects,
				IdempotencyLevel: idempotencyLevel,
			}

			connectSvc.Methods = append(connectSvc.Methods, connectMethod)
		}
		vars.Services = append(vars.Services, connectSvc)
	}

	var buf = &bytes.Buffer{}
	err := ConnectTemplate.Execute(buf, vars)
	if err != nil {
		return nil, err
	}

	resp := &pluginpb.CodeGeneratorResponse_File{
		Name:    proto.String(strings.TrimSuffix(filename, path.Ext(filename)) + "_connect.py"),
		Content: proto.String(buf.String()),
	}

	return resp, nil
}

func sanitizePythonName(name string) string {
	// https://docs.python.org/3/reference/lexical_analysis.html#keywords
	// with bytes and str
	switch name {
	case "False", "await", "else", "import", "pass",
		"None", "break", "except", "in", "raise",
		"True", "class", "finally", "is", "return",
		"and", "continue", "for", "lambda", "try",
		"as", "def", "from", "nonlocal", "while",
		"assert", "del", "global", "not", "with",
		"async", "elif", "if", "or", "yield",
		"bytes", "str":
		return name + "_"
	}
	return name
}

func pythonMethodName(name string, conf Config) string {
	switch conf.Naming {
	case NamingGoogle:
		return sanitizePythonName(name)
	case NamingPEP:
		if len(name) <= 1 {
			return strings.ToLower(name)
		}
		buf := make([]byte, 0, len(name))
		buf = append(buf, byte(unicode.ToLower(rune(name[0]))))
		for i := 1; i < len(name); i++ {
			switch {
			case unicode.IsUpper(rune(name[i])):
				buf = append(buf, '_')
				buf = append(buf, byte(unicode.ToLower(rune(name[i]))))
			default:
				buf = append(buf, byte(name[i]))
			}
		}
		return sanitizePythonName(string(buf))
	default:
		panic("Unknown naming, this is a bug in protoc-gen-connect")
	}
}

// https://github.com/grpc/grpc/blob/0dd1b2cad21d89984f9a1b3c6249d649381eeb65/src/compiler/python_generator_helpers.h#L67
func moduleName(filename string) string {
	fn, ok := strings.CutSuffix(filename, ".protodevel")
	if !ok {
		fn, _ = strings.CutSuffix(filename, ".proto")
	}
	fn = strings.ReplaceAll(fn, "-", "_")
	fn = strings.ReplaceAll(fn, "/", ".")
	return fn + "_pb2"
}

// https://github.com/grpc/grpc/blob/0dd1b2cad21d89984f9a1b3c6249d649381eeb65/src/compiler/python_generator_helpers.h#L80
func moduleAlias(filename string) string {
	mn := moduleName(filename)
	mn = strings.ReplaceAll(mn, "_", "__")
	mn = strings.ReplaceAll(mn, ".", "_dot_")
	return mn
}

func symbolName(msg protoreflect.MessageDescriptor) string {
	filename := ""
	name := string(msg.Name())
	for {
		parent := msg.Parent()
		if parent == nil {
			break
		}
		switch parent := parent.(type) {
		case protoreflect.FileDescriptor:
			filename = string(parent.Path())
		case protoreflect.MessageDescriptor:
			name = fmt.Sprintf("%s.%s", string(parent.Name()), name)
			msg = parent
		}
		if filename != "" {
			break
		}
	}
	return fmt.Sprintf("%s.%s", moduleAlias(filename), name)
}

func lastPart(imp string) string {
	if dotIdx := strings.LastIndexByte(imp, '.'); dotIdx != -1 {
		return imp[dotIdx+1:]
	}
	return imp
}

func generateImport(pkg string, conf Config, isLocal bool) (string, ImportStatement) {
	name := moduleName(pkg)
	imp := ImportStatement{
		Name:  name,
		Alias: moduleAlias(pkg),
	}
	if isLocal && conf.Imports == ImportsRelative {
		name = lastPart(name)
		imp.Name = name
		imp.Relative = true
	}
	return name, imp
}

func importStatements(file protoreflect.FileDescriptor, conf Config) []ImportStatement {
	mods := map[string]ImportStatement{}
	for i := 0; i < file.Services().Len(); i++ {
		svc := file.Services().Get(i)
		for j := 0; j < svc.Methods().Len(); j++ {
			method := svc.Methods().Get(j)
			inPkg := string(method.Input().ParentFile().Path())
			inName, inImp := generateImport(inPkg, conf, method.Input().ParentFile() == file)
			mods[inName] = inImp
			outPkg := string(method.Output().ParentFile().Path())
			outName, outImp := generateImport(outPkg, conf, method.Output().ParentFile() == file)
			mods[outName] = outImp
		}
	}

	imports := make([]ImportStatement, 0, len(mods))
	for _, imp := range mods {
		imports = append(imports, imp)
	}

	slices.SortFunc(imports, func(a, b ImportStatement) int {
		return strings.Compare(a.Name, b.Name)
	})
	return imports
}

package main

import (
	"github.com/bufbuild/protoplugin"

	"github.com/connectrpc/connect-python/protoc-gen-connect-python/generator"
)

func main() {
	protoplugin.Main(protoplugin.HandlerFunc(generator.Handle))
}

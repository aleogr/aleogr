package main

import (
	"fmt"

	"github.com/aleogr/aleogr/playground/goapp/internal/app/app1/prvpkg1"
	"github.com/aleogr/aleogr/playground/goapp/internal/pkg/prvlib1"
	"github.com/aleogr/aleogr/playground/goapp/publib1"
)

func main() {
	indent := ""
	fmt.Println("app1 -> main()")

	prvpkg1.Hello(indent + "  ")
	prvlib1.Hello(indent + "  ")
	publib1.Hello(indent + "  ")
}

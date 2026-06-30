package prvpkg1

import (
	"fmt"

	"github.com/aleogr/aleogr/playground/goapp/internal/pkg/prvlib1"
	"github.com/aleogr/aleogr/playground/goapp/publib1"
)

func Hello(indent string) {
	fmt.Printf("%sprvpkg1 -> Hello()\n", indent)
	prvlib1.Hello(indent + "  ")
	publib1.Hello(indent + "  ")
}

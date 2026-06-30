package prvlib1

import (
	"fmt"

	"github.com/aleogr/aleogr/playground/goapp/publib1"
)

func Hello(indent string) {
	fmt.Printf("%sprvlib1 -> Hello()\n", indent)
	publib1.Hello(indent + "  ")
}

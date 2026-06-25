package options_test

import (
	"testing"

	"github.com/aleogr/aleogr/playground/go/pattern/options"
)

func TestRequiredAttribute(t *testing.T) {
	o := options.New(10)
	attr1 := o.Attr1
	if attr1 != 10 {
		t.Errorf("Expected: 10 | Got: %d", attr1)
	}
}

func TestDefaultAttribute(t *testing.T) {
	o := options.New(10)
	attr2 := o.Attr2
	if attr2 != "default" {
		t.Errorf("Expected: 'default' | Got: '%s'", attr2)
	}
}

func TestOptionalAttribute(t *testing.T) {
	o1 := options.New(10)
	o2 := options.New(10, options.WithAttr2("modified"))
	o3 := options.New(10)
	options.WithAttr2("modified")(o3)
	o4 := options.New(10, options.WithAttr3(true))
	o5 := options.New(10)
	options.WithAttr3(true)(o5)

	tests := []struct {
		got, want any
	}{
		{got: o1.Attr2, want: "default"},
		{got: o1.Attr3, want: false},
		{got: o2.Attr2, want: "modified"},
		{got: o3.Attr2, want: "modified"},
		{got: o4.Attr3, want: true},
		{got: o5.Attr3, want: true},
	}

	for _, tt := range tests {
		t.Run("", func(t *testing.T) {
			if tt.want != tt.got {
				t.Errorf("Expected: %v | Got: %v", tt.want, tt.got)
			}
		})
	}
}

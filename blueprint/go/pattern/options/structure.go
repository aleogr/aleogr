package options

type Structure struct {
	Attr1 int
	Attr2 string
	Attr3 bool
}

func New(attr1 int, options ...Option) *Structure {
	s := &Structure{
		Attr1: attr1,
		Attr2: "default",
	}
	for _, option := range options {
		option(s)
	}
	return s
}

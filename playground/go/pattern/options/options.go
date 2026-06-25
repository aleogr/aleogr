package options

type Option func(*Structure)

func WithAttr2(v string) Option {
	return func(s *Structure) {
		s.Attr2 = v
	}
}

func WithAttr3(v bool) Option {
	return func(s *Structure) {
		s.Attr3 = v
	}
}

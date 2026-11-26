package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestDBRoute(t *testing.T) {
	_, pattern := newMux().Handler(httptest.NewRequest(http.MethodGet, "/db", nil))
	if pattern != "GET /db" {
		t.Errorf("GET /db is handled by %q, want the pattern \"GET /db\"", pattern)
	}
}

func TestDBNotConfigured(t *testing.T) {
	for _, tc := range []struct{ instance, name, user string }{
		{"", "", ""},
		{"", "app", "app@example-project.iam"},
		{"example-project:us-central1:example", "", "app@example-project.iam"},
		{"example-project:us-central1:example", "app", ""},
	} {
		t.Setenv("DB_INSTANCE", tc.instance)
		t.Setenv("DB_NAME", tc.name)
		t.Setenv("DB_USER", tc.user)
		rec := httptest.NewRecorder()
		newMux().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/db", nil))
		if rec.Code != http.StatusServiceUnavailable {
			t.Errorf("%+v: status = %d, want %d", tc, rec.Code, http.StatusServiceUnavailable)
		}
		if got := rec.Header().Get("Content-Type"); got != "text/plain; charset=utf-8" {
			t.Errorf("%+v: Content-Type = %q, want text/plain", tc, got)
		}
		if got, want := rec.Body.String(), "database: not configured\n"; got != want {
			t.Errorf("%+v: body = %q, want %q", tc, got, want)
		}
	}
}

package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func get(t *testing.T, path string) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	newMux().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
	return rec
}

func expect(t *testing.T, rec *httptest.ResponseRecorder, body string) {
	t.Helper()
	if rec.Code != http.StatusOK {
		t.Errorf("status = %d, want %d", rec.Code, http.StatusOK)
	}
	if got := rec.Header().Get("Content-Type"); got != "text/plain; charset=utf-8" {
		t.Errorf("Content-Type = %q, want text/plain", got)
	}
	if got := rec.Body.String(); got != body {
		t.Errorf("body = %q, want %q", got, body)
	}
}

func TestRoot(t *testing.T) {
	expect(t, get(t, "/"), "webdatabasecheck: ok\n")
}

func TestHealthz(t *testing.T) {
	expect(t, get(t, "/healthz"), "ok\n")
}

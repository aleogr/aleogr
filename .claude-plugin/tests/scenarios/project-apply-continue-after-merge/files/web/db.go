package main

import (
	"context"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"time"

	"cloud.google.com/go/cloudsqlconn"
	"github.com/jackc/pgx/v5"
)

// dbTimeout bounds the whole check: the dialer, the connection and the query.
const dbTimeout = 5 * time.Second

// dbCheck answers GET /db: whether the component reaches its database.
// DB_INSTANCE is the instance's connection name (project:region:instance),
// DB_NAME the database and DB_USER the service account's database user.
// The connection uses automatic IAM database authentication as the service's
// own account. The cause of a failure goes to the log, never to the page.
func dbCheck(w http.ResponseWriter, r *http.Request) {
	instance := os.Getenv("DB_INSTANCE")
	name := os.Getenv("DB_NAME")
	user := os.Getenv("DB_USER")
	if instance == "" || name == "" || user == "" {
		writeTextStatus(w, http.StatusServiceUnavailable, "database: not configured\n")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), dbTimeout)
	defer cancel()
	if err := pingDB(ctx, instance, name, user); err != nil {
		log.Printf("database check: %v", err)
		writeTextStatus(w, http.StatusServiceUnavailable, "database: not reachable (the shared instance may be stopped)\n")
		return
	}
	writeTextStatus(w, http.StatusOK, "database: ok\n")
}

// pingDB opens one connection to the database through the Cloud SQL
// connector, runs SELECT 1 and closes the connection and the dialer.
// The refresh is lazy, as Cloud Run throttles the CPU outside a request. The
// built-in metrics are off: their export would need a role the service does
// not have, and closing the dialer would wait for their flush.
func pingDB(ctx context.Context, instance, name, user string) error {
	d, err := cloudsqlconn.NewDialer(ctx,
		cloudsqlconn.WithIAMAuthN(),
		cloudsqlconn.WithLazyRefresh(),
		cloudsqlconn.WithRefreshTimeout(dbTimeout),
		cloudsqlconn.WithBuiltInMetrics(false),
	)
	if err != nil {
		return err
	}
	defer d.Close()
	cfg, err := pgx.ParseConfig("sslmode=disable")
	if err != nil {
		return err
	}
	cfg.User = user
	cfg.Database = name
	cfg.DialFunc = func(ctx context.Context, _, _ string) (net.Conn, error) {
		return d.Dial(ctx, instance)
	}
	conn, err := pgx.ConnectConfig(ctx, cfg)
	if err != nil {
		return err
	}
	defer conn.Close(ctx)
	var one int
	return conn.QueryRow(ctx, "SELECT 1").Scan(&one)
}

func writeTextStatus(w http.ResponseWriter, code int, body string) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(code)
	if _, err := io.WriteString(w, body); err != nil {
		log.Printf("write response: %v", err)
	}
}

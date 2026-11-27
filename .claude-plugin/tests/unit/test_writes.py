"""Unit tests of what aleogr_common gives a writing skill: the writing runner and its
allowlist of writes, `--read-only`, the file helper, the copies (Backup), the waits
and their budget, and hidden values.

Run: python3 -m unittest discover -s .claude-plugin/tests/unit
No provider is reached: commands run as stand-ins in a temporary folder.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from helpers import PLUGINS, aleogr_common as common  # noqa: E402
from test_common import StandIns  # noqa: E402

REPO_GITHUB = os.path.join(PLUGINS, "aleogr-repo-github")
CLOUD = os.path.join(PLUGINS, "aleogr-cloud-gcp")
DB = os.path.join(PLUGINS, "aleogr-db-gcp-cloud-sql")
REGISTRY = os.path.join(PLUGINS, "aleogr-registry-gcp-artifact-registry")
RULESET = os.path.join(REPO_GITHUB, "files", "ruleset-main.json")
RULESET_CI = os.path.join(REPO_GITHUB, "files", "ruleset-main-ci.json")
STOP_BODY = os.path.join(DB, "files", "stop-body.json")
CLEANUP_POLICY = os.path.join(REGISTRY, "files", "cleanup-policy.json")
CRED = list(common.GIT_CREDENTIAL)
TITLE = "Change the project declaration"

# Every write shape of every skill of step 2a, as its SKILL.md writes it, with sample
# values: each must be accepted for its skill, and refused for every other skill unless
# that skill prescribes the same command.
ALLOWED = {
    "github_repo-create": [
        ["gh", "repo", "create", "example-org/example-repo", "--private", "--add-readme"],
        ["gh", "repo", "create", "example-org/example-repo", "--public", "--add-readme"],
        ["gh", "repo", "create", "example-org/example-repo", "--private", "--add-readme",
         "--description", "Status pages, per tenant"],
        ["gh", "repo", "create", "example-org/example-repo", "--public", "--add-readme",
         "--description", "Status pages"],
        ["gh", "repo", "edit", "example-org/example-repo", "--add-topic", "status-page"],
        ["gh", "repo", "edit", "example-org/example-repo", "--add-topic", "a", "--add-topic",
         "b-2"],
    ],
    "github_repo-configure": [
        ["gh", "repo", "edit", "example-org/example-repo", "--description", "New text",
         "--enable-merge-commit=true", "--enable-squash-merge=true",
         "--enable-rebase-merge=false", "--delete-branch-on-merge=true",
         "--enable-issues=true", "--enable-wiki=false", "--enable-projects=false",
         "--add-topic", "a", "--add-topic", "b", "--remove-topic", "c"],
        ["gh", "repo", "edit", "example-org/example-repo", "--enable-rebase-merge=false"],
        ["gh", "repo", "edit", "example-org/example-repo", "--remove-topic", "old"],
        # The same commands as github_repo-create's topics, when only topics are added.
        ["gh", "repo", "edit", "example-org/example-repo", "--add-topic", "status-page"],
        ["gh", "repo", "edit", "example-org/example-repo", "--add-topic", "a", "--add-topic",
         "b-2"],
        ["gh", "repo", "edit", "example-org/example-repo", "--visibility", "public",
         "--accept-visibility-change-consequences"],
        ["gh", "repo", "edit", "example-org/example-repo", "--visibility", "private",
         "--accept-visibility-change-consequences"],
    ],
    "github_branch-protect": [
        ["gh", "api", "--method", "POST", "repos/example-org/example-repo/rulesets",
         "--input", RULESET],
        ["gh", "api", "--method", "POST", "repos/example-org/example-repo/rulesets",
         "--input", RULESET_CI],
        ["gh", "api", "--method", "PUT", "repos/example-org/example-repo/rulesets/123",
         "--input", RULESET],
    ],
    "github_checkout-setup": [
        ["git", "init", "-b", "main"],
        ["git", "remote", "add", "origin", "https://github.com/example-org/example-repo.git"],
        ["git", "config", "--local", "user.name", "octo-cat"],
        ["git", "config", "--local", "user.email", "1234+octo-cat@users.noreply.github.com"],
        ["git"] + CRED + ["pull", "origin", "main"],
        ["git", "add", "--", ".aleogr/project.json"],
        ["git", "commit", "-m", "Add the project declaration", "--", ".aleogr/project.json"],
        ["git"] + CRED + ["push", "-u", "origin", "main"],
        ["git"] + CRED + ["pull", "--ff-only", "origin", "main"],
    ],
    "github_pull-request-open": [
        ["git", "config", "--local", "user.name", "octo-cat"],
        ["git", "config", "--local", "user.email", "1234+octo-cat@users.noreply.github.com"],
        ["git"] + CRED + ["pull", "--ff-only", "origin", "main"],
        ["git", "switch", "-c", "aleogr/change-ab12cd"],
        ["git", "add", "--", ".aleogr/project.json"],
        ["git", "commit", "-m", "Add the project declaration", "--", ".aleogr/project.json"],
        ["git", "add", "--", ".aleogr/project.json", "web/go.mod"],
        ["git", "commit", "-m", TITLE, "--", ".aleogr/project.json", "web/go.mod"],
        ["git"] + CRED + ["push", "-u", "origin", "aleogr/change-ab12cd"],
        ["gh", "pr", "create", "--repo", "example-org/example-repo", "--base", "main",
         "--head", "aleogr/change-ab12cd", "--title", TITLE, "--body",
         "Proposed by aleogr. It adds one topic."],
        ["git", "switch", "main"],
    ],
    "github_variables-set": [
        ["gh", "variable", "set", "GCP_REGION", "--repo", "example-org/example-repo",
         "--body", "us-central1"],
        ["gh", "secret", "set", "GCP_PROJECT_ID", "--repo", "example-org/example-repo",
         "--body", "aleogr-dev-demo-ab12"],
    ],
    "go_setup": [
        ["go", "-C", "web", "get", "cloud.google.com/go/cloudsqlconn@v1.27.1",
         "github.com/jackc/pgx/v5@v5.13.0"],
        ["go", "-C", "services/api", "get", "github.com/jackc/pgx/v5@v5.13.0",
         "cloud.google.com/go/cloudsqlconn@v1.27.1"],
        ["go", "-C", "web", "mod", "tidy"],
    ],
}

# Refused for every skill, whatever an entry of WRITE_SHAPES says.
ALWAYS_REFUSED = [
    "gh repo delete example-org/example-repo --yes",
    "gh variable delete GCP_REGION --repo example-org/example-repo",
    "gh secret delete GCP_PROJECT_ID --repo example-org/example-repo",
    "gh api -X DELETE repos/example-org/example-repo/rulesets/1",
    "gh api -XDELETE repos/example-org/example-repo/rulesets/1",
    "gh api --method DELETE repos/example-org/example-repo/rulesets/1",
    "gh api --method=delete repos/example-org/example-repo/rulesets/1",
    "gh api -iXDELETE repos/example-org/example-repo/rulesets/1",
    "gh pr merge 1 --repo example-org/example-repo",
    "gh pr merge --squash",
    "gh auth login",
    "gh auth logout",
    "gh auth token",
    "gh auth status -t",
    "gh auth setup-git",
    "gh release delete v1",
    "git push --force origin main",
    "git push -f origin main",
    "git push -uf origin main",
    "git push --force-with-lease origin main",
    "git push --force-with-lease=main origin main",
    "git push --force-if-includes origin main",
    "git push origin +main",
    "git push origin :main",
    "git push --delete origin aleogr/change-ab12cd",
    "git push -d origin aleogr/change-ab12cd",
    "git push --mirror origin",
    "git push --all origin",
    "git push --tags origin",
    "git -c credential.helper= push --force -u origin main",
    "git reset --hard",
    "git reset --hard origin/main",
    "git -C web reset --hard HEAD",
    "git clean -fdx",
    "git clean -n",
    "git branch -D aleogr/change-ab12cd",
    "git branch -d aleogr/change-ab12cd",
    "gcloud projects delete demo",
    "gcloud sql instances delete aleogr-shared",
    "gcloud projects set-iam-policy demo policy.json",
]

# Refused by the allowlist itself: writes no skill names, or a shape of a skill
# changed in one way (a flag, an order, a value).
NOT_ON_THE_LIST = {
    "github_variables-set": [
        "gh variable set GCP_REGION --repo example-org/example-repo --env dev --body x",
        "gh variable set gcp_region --repo example-org/example-repo --body x",
        "gh variable set GCP_REGION --body x --repo example-org/example-repo",
        "gh variable set GCP_REGION --repo example-org/example-repo",
        "gh variable set GCP_REGION --repo example-org/example-repo --body x --org o",
        "gh secret set GCP_REGION --repo example-org --body x",
        "gh secret set GCP_REGION --org example-org --body x",
        "gh api -X POST repos/example-org/example-repo/actions/variables",
        "git push -u origin main",
    ],
    "github_repo-create": [
        "gh repo create example-org/example-repo --internal --add-readme",
        "gh repo create example-org/example-repo --private",
        "gh repo create example-org/example-repo --private --add-readme --clone",
        "gh repo edit example-org/example-repo --remove-topic a",
        "gh repo edit example-org/example-repo --visibility public "
        "--accept-visibility-change-consequences",
        "gh repo edit example-org/example-repo",
        "gh repo edit example-org/example-repo --add-topic Bad_Topic",
    ],
    "github_repo-configure": [
        "gh repo edit example-org/example-repo --enable-rebase-merge=false --description x",
        "gh repo edit example-org/example-repo --enable-rebase-merge",
        "gh repo edit example-org/example-repo --enable-wiki=yes",
        "gh repo edit example-org/example-repo --visibility public",
        "gh repo edit example-org/example-repo --description x --visibility public "
        "--accept-visibility-change-consequences",
        "gh repo edit example-org/example-repo --remove-topic a --add-topic b",
        "gh repo edit example-org/example-repo --default-branch dev",
        "gh repo edit example-org/example-repo --enable-issues=true --enable-issues=false",
        "gh repo edit example-org/example-repo",
        "gh repo archive example-org/example-repo",
        "gh repo rename x",
    ],
    "github_branch-protect": [
        "gh api --method PATCH repos/example-org/example-repo/rulesets/123 --input " + RULESET,
        "gh api --method POST repos/example-org/example-repo/rulesets --input /tmp/body.json",
        "gh api --method POST repos/example-org/example-repo/rulesets -f name=main",
        "gh api --method POST repos/example-org/example-repo/rulesets",
        "gh api -X POST repos/example-org/example-repo/rulesets --input " + RULESET,
        "gh api --method PUT repos/example-org/example-repo/rulesets/abc --input " + RULESET,
        "gh api --method PUT repos/example-org/example-repo/collaborators/x",
        "gh api --method POST repos/example-org/example-repo/branches/main/protection",
    ],
    "github_checkout-setup": [
        "git push -u origin main",
        "git -c credential.helper= push -u origin main",
        "git remote set-url origin https://github.com/example-org/example-repo.git",
        "git remote add origin git@github.com:example-org/example-repo.git",
        "git remote add upstream https://github.com/example-org/example-repo.git",
        "git config --global user.name octo-cat",
        "git config user.name octo-cat",
        "git config --local user.email someone@example.com",
        "git config --local core.hooksPath x",
        "git add .",
        "git add -A",
        "git add -- ../outside",
        "git add -- /etc/passwd",
        "git commit -m x",
        "git commit --amend -m x -- a",
        "git fetch",
        "git clone https://github.com/example-org/example-repo.git",
        "git init",
        "git init -b -x",
        "git add -- .aleogr/project.json web/go.mod",
        "git commit -m x -- .aleogr/project.json web/go.mod",
        "git -c credential.helper= -c credential.helper=!gh_auth_git-credential push -u "
        "origin main",
        "git pull --rebase origin main",
        "git merge origin/main",
        "git checkout main",
        "git stash",
        "gh repo clone example-org/example-repo",
    ],
    "github_pull-request-open": [
        "git -c credential.helper= -c credential.helper=!gh_auth_git-credential push -u "
        "origin aleogr/change-ab12cd",
        "git switch -c aleogr/change-AB12CD",
        "git switch -c feature",
        "git switch -c aleogr/change-ab12cd7",
        "git checkout -b aleogr/change-ab12cd",
        "gh pr create --repo example-org/example-repo --base main --head main --title t "
        "--body b",
        "gh pr create --repo example-org/example-repo --base main --head aleogr/change-ab12cd "
        "--title t",
        "gh pr create --repo example-org/example-repo --base main --head aleogr/change-ab12cd "
        "--title t --body b --draft",
        "gh pr close 1",
        "gh pr comment 1 --body x",
        "git switch -",
        "git switch --discard-changes main",
        "git init -b main",
        "git remote add origin https://github.com/example-org/example-repo.git",
    ],
    "go_setup": [
        "go -C web get example.com/other@v1.0.0 github.com/jackc/pgx/v5@v5.13.0",
        "go -C web get github.com/jackc/pgx/v5@v5.13.0",
        "go -C web get github.com/jackc/pgx/v5@v5.13.0 github.com/jackc/pgx/v5@v5.13.0",
        "go -C web get github.com/jackc/pgx/v5@latest cloud.google.com/go/cloudsqlconn@v1.27.1",
        "go get cloud.google.com/go/cloudsqlconn@v1.27.1 github.com/jackc/pgx/v5@v5.13.0",
        "go -C ../web mod tidy",
        "go -C /tmp mod tidy",
        "go -C .github mod tidy",
        "go mod tidy",
        "go mod download",
        "go install example.com/x@latest",
        "go env -w GOFLAGS=-mod=mod",
        "go build ./...",
        "go run .",
    ],
    "github_ci-setup": [
        "git add -- .github/workflows/ci.yml",
        "gh api --method PUT repos/example-org/example-repo/contents/.github/workflows/ci.yml",
    ],
    "project-declare": [
        "git add -- .aleogr/project.json",
    ],
    "no-such-skill": [
        "gh variable set GCP_REGION --repo example-org/example-repo --body us-central1",
    ],
    "github_repo-describe": [
        "gh repo create example-org/example-repo --private --add-readme",
    ],
}

# Commands named by a skill only as a thing never to run, or not named at all: refused
# for every skill of step 2a.
NEVER = [
    "rm -rf web",
    "cp -p -- web/go.mod /tmp/x/go.mod",
    "mktemp -d",
    "sh -c true",
    "bash -c true",
    "cmp -s -- a b",
    "ls -1Ap -- web/",
    "sleep 30",
    "gh repo create example-org/example-repo --private --add-readme && true",
]


# ---------------------------------------------------------------------------
# Part 2b: the writes to Google Cloud. Each command as its SKILL.md writes it (a value
# the SKILL.md double-quotes is one argument, without its quotes), with sample values.

P = "aleogr-dev-demo-ab12"  # a project's own GCP project
S = "aleogr-shared-zz99"  # the shared platform's
SQL = "--project=" + S
RUN = ["--region=us-central1", "--project=" + P]
CI_SA = "demo-ci@%s.iam.gserviceaccount.com" % P
WEB_SA = "demo-web@%s.iam.gserviceaccount.com" % P
SWITCH_SA = "aleogr-shared-sql-switch@%s.iam.gserviceaccount.com" % S
SET = "^##^"
CI_CONDITION = ("assertion.repository=='example-org/example-repo' && "
                "assertion.repository_id=='123456' && assertion.repository_owner_id=='654321' "
                "&& assertion.ref=='refs/heads/main' && "
                "assertion.job_workflow_ref.startsWith("
                "'example-org/workflows/.github/workflows/deploy.yml@')")
CI_MAPPING = ("google.subject=assertion.sub,attribute.repository=assertion.repository,"
              "attribute.ref=assertion.ref,attribute.repository_id=assertion.repository_id,"
              "attribute.repository_owner_id=assertion.repository_owner_id,"
              "attribute.job_workflow_ref=assertion.job_workflow_ref")
PRINCIPAL = ("principalSet://iam.googleapis.com/projects/123456789012/locations/global/"
             "workloadIdentityPools/github/attribute.repository/example-org/example-repo")
JOB_URI = "https://sqladmin.googleapis.com/v1/projects/%s/instances/aleogr-shared" % S
HEADERS = "Content-Type=application/json,X-HTTP-Method-Override=PATCH"
SCOPE = "--oauth-token-scope=https://www.googleapis.com/auth/cloud-platform"
STOP = ["gcloud", "sql", "instances", "patch", "aleogr-shared", SQL,
        "--activation-policy=NEVER", "--quiet"]
POOL = ["gcloud", "iam", "workload-identity-pools", "create", "github", "--project=" + P,
        "--location=global", "--display-name=GitHub", "--quiet"]
ACCESS_ME = ["gcloud", "iap", "web", "add-iam-policy-binding", "--resource-type=cloud-run",
             "--service=demo-web"] + RUN + ["--member=user:demo-user@example.com",
                                            "--role=roles/iap.httpsResourceAccessor",
                                            "--condition=None", "--quiet"]
IAP_ENABLE = ["gcloud", "services", "enable", "iap.googleapis.com", "--project=" + S]


def g(text):
    """A gcloud command written as words (no value holds a space)."""
    return ["gcloud"] + text.split(" ")


GCLOUD_ALLOWED = {
    "gcp-cloud-sql_instance-stop": [STOP],
    "gcp-cloud-sql_instance-start": [
        g("sql instances patch aleogr-shared " + SQL + " --activation-policy=ALWAYS --async "
          "--quiet"),
    ],
    "gcp-cloud-sql_instance-create": [
        g("sql instances create aleogr-shared " + SQL + " --database-version=POSTGRES_17 "
          "--edition=enterprise --tier=db-f1-micro --region=southamerica-east1 "
          "--availability-type=zonal --storage-type=SSD --storage-size=10 "
          "--no-storage-auto-increase --assign-ip --backup --backup-start-time=06:00 "
          "--retained-backups-count=7 --no-enable-point-in-time-recovery "
          "--database-flags=cloudsql.iam_authentication=on --no-enable-dataplex-integration "
          "--deletion-protection --async --quiet"),
        STOP,
        g("scheduler jobs run aleogr-shared-stop-weeknight " + SQL
          + " --location=southamerica-east1 --quiet"),
    ],
    "gcp-cloud-sql_instance-switch-setup": [
        ["gcloud", "iam", "roles", "create", "aleogrSharedSqlSwitch", SQL,
         "--title=aleogr shared SQL switch",
         "--permissions=cloudsql.instances.get,cloudsql.instances.update", "--stage=GA",
         "--quiet"],
        ["gcloud", "iam", "service-accounts", "create", "aleogr-shared-sql-switch", SQL,
         "--display-name=aleogr shared SQL switch", "--quiet"],
        g("projects add-iam-policy-binding %s --member=serviceAccount:%s "
          "--role=projects/%s/roles/aleogrSharedSqlSwitch --condition=None --quiet"
          % (S, SWITCH_SA, S)),
        g("iam service-accounts add-iam-policy-binding %s %s --member=user:owner@example.com "
          "--role=roles/iam.serviceAccountUser --quiet" % (SWITCH_SA, SQL)),
        # The pool's create is the same command in gcp_ci-identity-setup: one shape.
        POOL,
        ["gcloud", "iam", "workload-identity-pools", "providers", "create-oidc", "aleogr", SQL,
         "--location=global", "--workload-identity-pool=github",
         "--issuer-uri=https://token.actions.githubusercontent.com",
         "--attribute-mapping=google.subject=assertion.sub,"
         "attribute.repository=assertion.repository,attribute.ref=assertion.ref",
         "--attribute-condition=assertion.repository=='example-org/example-repo' && "
         "assertion.ref=='refs/heads/main'", "--quiet"],
        g("iam service-accounts add-iam-policy-binding %s %s --member=%s "
          "--role=roles/iam.workloadIdentityUser --quiet" % (SWITCH_SA, SQL, PRINCIPAL)),
        ["gcloud", "scheduler", "jobs", "create", "http", "aleogr-shared-stop-weeknight", SQL,
         "--location=southamerica-east1", "--schedule=30 22 * * 0-4",
         "--time-zone=America/Sao_Paulo", "--uri=" + JOB_URI, "--http-method=POST",
         "--headers=" + HEADERS, "--message-body-from-file=" + STOP_BODY,
         "--oauth-service-account-email=" + SWITCH_SA, SCOPE, "--max-retry-attempts=5",
         "--min-backoff=5m", "--max-backoff=15m", "--max-doublings=2",
         "--attempt-deadline=60s", "--quiet"],
        ["gcloud", "scheduler", "jobs", "update", "http", "aleogr-shared-stop-weekend", SQL,
         "--location=southamerica-east1", "--schedule=0 23 * * 5,6",
         "--time-zone=America/Sao_Paulo", "--uri=" + JOB_URI, "--http-method=POST",
         "--update-headers=" + HEADERS, "--message-body-from-file=" + STOP_BODY,
         "--oauth-service-account-email=" + SWITCH_SA, SCOPE, "--quiet"],
        g("scheduler jobs resume aleogr-shared-stop-weekend " + SQL
          + " --location=southamerica-east1 --quiet"),
    ],
    "gcp-cloud-sql_database-create": [
        g("sql databases create my_app_dev --instance=aleogr-shared " + SQL + " --quiet"),
    ],
    "gcp-cloud-sql_access-grant": [
        g("sql users create demo-web@%s.iam --instance=aleogr-shared %s "
          "--type=cloud_iam_service_account --quiet" % (P, SQL)),
        g("projects add-iam-policy-binding %s --member=serviceAccount:%s "
          "--role=roles/cloudsql.client --condition=None --quiet" % (S, WEB_SA)),
        g("projects add-iam-policy-binding %s --member=serviceAccount:%s "
          "--role=roles/cloudsql.instanceUser --condition=None --quiet" % (S, WEB_SA)),
    ],
    "gcp-artifact-registry_repository-create": [
        g("artifacts repositories create demo --project=%s --location=us-central1 "
          "--repository-format=docker --labels=aleogr-project=demo,aleogr-environment=dev" % P),
    ],
    "gcp-artifact-registry_cleanup-configure": [
        g("artifacts repositories set-cleanup-policies demo --location=us-central1 "
          "--project=%s --policy=%s --no-dry-run" % (P, CLEANUP_POLICY)),
        g("artifacts repositories set-cleanup-policies demo --location=us-central1 "
          "--project=%s --policy=/tmp/aleogr-cleanup-policy-keep-3.json --no-dry-run" % P),
    ],
    "gcp-artifact-registry_access-grant": [
        g("artifacts repositories add-iam-policy-binding demo --location=us-central1 "
          "--project=%s --member=serviceAccount:%s --role=roles/artifactregistry.writer "
          "--condition=None --quiet" % (P, CI_SA)),
    ],
    "gcp_environment-create": [
        g("projects create aleogr-shared-x7k2 --organization=111111111111 --name=shared "
          "--labels=aleogr-project=shared,aleogr-platform=shared"),
        ["gcloud", "projects", "create", "aleogr-dev-my-app-x7k2", "--folder=222222222222",
         "--name=dev my-app", "--labels=aleogr-project=my-app,aleogr-environment=dev"],
        g("billing projects link %s --billing-account=0X0X0X-0X0X0X-0X0X0X" % P),
    ],
    "gcp_services-enable": [
        g("services enable run.googleapis.com artifactregistry.googleapis.com --project=" + P),
        g("services enable sqladmin.googleapis.com --project=" + P),
        IAP_ENABLE,  # the same command as gcp_login-setup's, when only the IAP API is asked
    ],
    "gcp_budget-alert-setup": [
        g("billing budgets create --billing-account=0X0X0X-0X0X0X-0X0X0X "
          "--display-name=aleogr-monthly --budget-amount=100BRL --threshold-rule=percent=0.5 "
          "--threshold-rule=percent=0.9 --threshold-rule=percent=1.0 --billing-project=" + S),
        g("billing budgets update 1b2c3d4e-0000-4f00-8a00-123456789abc "
          "--billing-account=0X0X0X-0X0X0X-0X0X0X --budget-amount=150.5BRL "
          "--clear-threshold-rules --add-threshold-rule=percent=0.5 "
          "--add-threshold-rule=percent=1 --billing-project=" + S),
    ],
    "gcp_login-setup": [
        g("organizations add-iam-policy-binding 111111111111 --member=user:owner@example.com "
          "--role=roles/iap.settingsAdmin --condition=None --quiet"),
        g("organizations add-iam-policy-binding 111111111111 "
          "--member=serviceAccount:deployer@%s.iam.gserviceaccount.com "
          "--role=roles/iap.settingsAdmin --condition=None --quiet" % S),
        IAP_ENABLE,
    ],
    "gcp_deploy-setup": [
        g("iap web remove-iam-policy-binding --resource-type=cloud-run --service=demo-web "
          "--region=us-central1 --project=%s --member=allUsers "
          "--role=roles/iap.httpsResourceAccessor --all --quiet" % P),
        g("iap web remove-iam-policy-binding --resource-type=cloud-run --service=demo-web "
          "--region=us-central1 --project=%s --member=allAuthenticatedUsers "
          "--role=projects/%s/roles/custom.viewer --all --quiet" % (P, P)),
        g("run services remove-iam-policy-binding demo-web --member=allUsers "
          "--role=roles/run.invoker --region=us-central1 --project=%s --all --quiet" % P),
        g("run services remove-iam-policy-binding demo-web --member=allAuthenticatedUsers "
          "--role=roles/viewer --region=us-central1 --project=%s --all --quiet" % P),
        g("run services update demo-web --iap --region=us-central1 --project=%s --quiet" % P),
        g("run services update demo-web --invoker-iam-check --region=us-central1 "
          "--project=%s --quiet" % P),
        ["gcloud", "iam", "service-accounts", "create", "demo-web", "--project=" + P,
         "--display-name=demo web", "--quiet"],
        ["gcloud", "iam", "service-accounts", "create", "my-app-web", "--project=" + P,
         "--display-name=my-app web", "--quiet"],
        g("iam service-accounts add-iam-policy-binding %s --member=serviceAccount:%s "
          "--role=roles/iam.serviceAccountUser --project=%s --condition=None --quiet"
          % (WEB_SA, CI_SA, P)),
        g("run deploy demo-web --image=us-docker.pkg.dev/cloudrun/container/hello:latest "
          "--no-allow-unauthenticated --iap --service-account=%s --min=0 --max=2 --cpu=1 "
          "--memory=512Mi --cpu-throttling "
          "--labels=aleogr-project=demo,aleogr-environment=dev,aleogr-component=web "
          "--region=us-central1 --project=%s --quiet" % (WEB_SA, P)),
        g("run services update demo-web --service-account=%s --min=0 --max=2 --scaling=auto "
          "--min-instances=default --cpu=2 --memory=1Gi --cpu-throttling "
          "--update-labels=aleogr-project=demo,aleogr-environment=dev,aleogr-component=web "
          "--region=us-central1 --project=%s --quiet" % (WEB_SA, P)),
        g("run services update demo-web --memory=2Gi --region=us-central1 --project=%s "
          "--quiet" % P),
        g("run services update demo-web --min=0 --max=3 --region=us-central1 --project=%s "
          "--quiet" % P),
        g("run services add-iam-policy-binding demo-web "
          "--member=serviceAccount:service-123456789012@gcp-sa-iap.iam.gserviceaccount.com "
          "--role=roles/run.invoker --region=us-central1 --project=%s --condition=None "
          "--quiet" % P),
        g("run services add-iam-policy-binding demo-web --member=serviceAccount:%s "
          "--role=roles/run.developer --region=us-central1 --project=%s --condition=None "
          "--quiet" % (CI_SA, P)),
        ACCESS_ME,
        # <me> is whatever account gcloud is logged in as, so this shape takes any
        # person's user: as gcp_access-grant's does (and a service account besides).
        g("iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-api "
          "--region=us-central1 --project=%s --member=user:demo-user+test@example.com "
          "--role=roles/iap.httpsResourceAccessor --condition=None --quiet" % P),
        g("iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
          "--region=us-central1 --project=%s "
          "--member=serviceAccount:deployer@%s.iam.gserviceaccount.com "
          "--role=roles/iap.httpsResourceAccessor --condition=None --quiet" % (P, P)),
        g("run services update demo-web --update-env-vars=" + SET + "DB_INSTANCE=" + S
          + ":southamerica-east1:aleogr-shared##DB_NAME=demo_dev##DB_USER=demo-web@" + P
          + ".iam --region=us-central1 --project=%s --quiet" % P),
        g("run services update demo-web --update-env-vars=" + SET + "DB_NAME=demo_dev "
          "--region=us-central1 --project=%s --quiet" % P),
    ],
    "gcp_access-grant": [
        ACCESS_ME,  # the same command as gcp_deploy-setup's 6f, for a person
        g("iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-api "
          "--region=us-central1 --project=%s --member=user:demo-user+test@example.com "
          "--role=roles/iap.httpsResourceAccessor --condition=None --quiet" % P),
    ],
    "gcp_ci-identity-setup": [
        ["gcloud", "iam", "service-accounts", "create", "demo-ci", "--project=" + P,
         "--display-name=demo CI", "--quiet"],
        POOL,
        ["gcloud", "iam", "workload-identity-pools", "providers", "create-oidc", "github",
         "--project=" + P, "--location=global", "--workload-identity-pool=github",
         "--issuer-uri=https://token.actions.githubusercontent.com",
         "--attribute-mapping=" + CI_MAPPING, "--attribute-condition=" + CI_CONDITION,
         "--quiet"],
        ["gcloud", "iam", "workload-identity-pools", "providers", "update-oidc", "github",
         "--project=" + P, "--location=global", "--workload-identity-pool=github",
         "--issuer-uri=https://token.actions.githubusercontent.com",
         "--attribute-mapping=" + CI_MAPPING, "--attribute-condition=" + CI_CONDITION,
         "--quiet"],
        g("iam service-accounts add-iam-policy-binding %s --project=%s --member=%s "
          "--role=roles/iam.workloadIdentityUser --quiet" % (CI_SA, P, PRINCIPAL)),
    ],
}
GCLOUD_SKILLS = sorted(GCLOUD_ALLOWED)
ALLOWED.update(GCLOUD_ALLOWED)

ALWAYS_REFUSED += [
    # any delete
    "gcloud run services delete demo-web --region=us-central1 --quiet",
    "gcloud iam service-accounts delete demo-web@x.iam.gserviceaccount.com",
    "gcloud artifacts repositories delete demo --location=us-central1",
    "gcloud scheduler jobs delete aleogr-shared-stop-weeknight --location=x",
    "gcloud sql databases delete demo_dev --instance=aleogr-shared",
    "gcloud iam workload-identity-pools providers delete github --location=global",
    # set-iam-policy
    "gcloud run services set-iam-policy demo-web policy.json",
    "gcloud iap web set-iam-policy policy.json --resource-type=cloud-run",
    "gcloud iam service-accounts set-iam-policy a@b.iam.gserviceaccount.com p.json",
    # remove-iam-policy-binding of anyone but everyone
    "gcloud projects remove-iam-policy-binding demo --member=user:x@example.com "
    "--role=roles/run.admin",
    "gcloud iap web remove-iam-policy-binding --resource-type=cloud-run --service=demo-web "
    "--region=us-central1 --project=" + P + " --member=user:x@example.com "
    "--role=roles/iap.httpsResourceAccessor --all --quiet",
    "gcloud run services remove-iam-policy-binding demo-web "
    "--member=serviceAccount:service-1@gcp-sa-iap.iam.gserviceaccount.com "
    "--role=roles/run.invoker --region=us-central1 --project=" + P + " --all --quiet",
    "gcloud run services remove-iam-policy-binding demo-web --member=allUsers "
    "--member=user:x@example.com --role=roles/run.invoker",
    "gcloud iam service-accounts remove-iam-policy-binding a@b.iam.gserviceaccount.com "
    "--member=allUsers --member=user:x@example.com",
    # a primitive role in any add-iam-policy-binding
    "gcloud projects add-iam-policy-binding demo --member=user:x@example.com --role=roles/owner",
    "gcloud projects add-iam-policy-binding demo --member=user:x@example.com --role=roles/editor",
    "gcloud projects add-iam-policy-binding demo --member=user:x@example.com --role=roles/viewer",
    "gcloud projects add-iam-policy-binding demo --member=user:x@example.com --role roles/owner",
    "gcloud organizations add-iam-policy-binding 1 --member=user:x@example.com "
    "--role=ROLES/OWNER --condition=None --quiet",
    "gcloud run services add-iam-policy-binding demo-web --member=serviceAccount:" + CI_SA
    + " --role=roles/editor --region=us-central1 --project=" + P + " --condition=None --quiet",
    # --allow-unauthenticated
    "gcloud run deploy demo-web --image=us-docker.pkg.dev/cloudrun/container/hello "
    "--allow-unauthenticated",
    "gcloud run services update demo-web --allow-unauthenticated --region=us-central1",
    "gcloud run deploy demo-web --allow-unauthenticated=true",
    # allUsers and allAuthenticatedUsers as a member
    "gcloud run services add-iam-policy-binding demo-web --member=allUsers "
    "--role=roles/run.invoker --region=us-central1 --project=" + P + " --condition=None --quiet",
    "gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
    "--region=us-central1 --project=" + P + " --member=allAuthenticatedUsers "
    "--role=roles/iap.httpsResourceAccessor --condition=None --quiet",
    "gcloud artifacts repositories add-iam-policy-binding demo --member=allUsers "
    "--role=roles/artifactregistry.reader",
    "gcloud projects add-iam-policy-binding demo --member=ALLUSERS --role=roles/run.invoker",
    # any --password* flag, set-password
    "gcloud sql users create demo --instance=aleogr-shared --password=x",
    "gcloud sql users create demo --instance=aleogr-shared --password-policy-enable-failed-attempts-check",
    "gcloud sql instances create aleogr-shared --root-password=x",
    "gcloud sql users set-password postgres --instance=aleogr-shared --prompt-for-password",
    "gcloud sql users set-password postgres --instance=aleogr-shared",
    # gcloud auth other than list
    "gcloud auth print-access-token",
    "gcloud auth print-identity-token",
    "gcloud auth login",
    "gcloud auth activate-service-account --key-file=k.json",
    "gcloud auth application-default print-access-token",
    "gcloud auth revoke",
    "gcloud auth configure-docker",
    "gcloud auth list extra",
    # gcloud config set (and every config change)
    "gcloud config set project demo",
    "gcloud config set account x@example.com",
    "gcloud config unset project",
    "gcloud config configurations activate other",
    "gcloud --project=demo config set project demo",
    # service account keys, impersonation
    "gcloud iam service-accounts keys create k.json --iam-account=" + CI_SA,
    "gcloud iam service-accounts keys list --iam-account=" + CI_SA,
    "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=NEVER --quiet "
    "--impersonate-service-account=" + CI_SA,
    "gcloud projects describe demo --impersonate-service-account=" + CI_SA,
    "gcloud --impersonate-service-account=" + CI_SA + " sql instances patch aleogr-shared",
]

NOT_ON_THE_LIST.update({
    "gcp-cloud-sql_instance-stop": [
        "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=ALWAYS --quiet",
        "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=NEVER",
        "gcloud sql instances patch aleogr-shared --activation-policy=NEVER " + SQL + " --quiet",
        "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=NEVER "
        "--async --quiet",
        "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=NEVER "
        "--tier=db-custom-4-16384 --quiet",
        "gcloud sql instances patch Aleogr " + SQL + " --activation-policy=NEVER --quiet",
        "gcloud sql instances restart aleogr-shared " + SQL,
    ],
    "gcp-cloud-sql_instance-start": [
        "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=ALWAYS --quiet",
        "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=NEVER --quiet",
        "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=ALWAYS "
        "--async --quiet --tier=db-custom-8-32768",
    ],
    "gcp-cloud-sql_instance-create": [
        "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=ALWAYS "
        "--async --quiet",
        "gcloud sql instances create aleogr-shared " + SQL + " --database-version=POSTGRES_17 "
        "--edition=enterprise --tier=db-f1-micro --region=southamerica-east1 --async --quiet",
        "gcloud sql instances create aleogr-shared " + SQL + " --database-version=POSTGRES_17 "
        "--edition=enterprise --tier=db-f1-micro --region=southamerica-east1 "
        "--availability-type=regional --storage-type=SSD --storage-size=10 "
        "--no-storage-auto-increase --assign-ip --backup --backup-start-time=06:00 "
        "--retained-backups-count=7 --no-enable-point-in-time-recovery "
        "--database-flags=cloudsql.iam_authentication=on --no-enable-dataplex-integration "
        "--deletion-protection --async --quiet",
        "gcloud sql instances create aleogr-shared " + SQL + " --database-version=POSTGRES_17 "
        "--edition=enterprise --tier=db-f1-micro --region=southamerica-east1 "
        "--availability-type=zonal --storage-type=SSD --storage-size=500 "
        "--no-storage-auto-increase --assign-ip --backup --backup-start-time=06:00 "
        "--retained-backups-count=7 --no-enable-point-in-time-recovery "
        "--database-flags=cloudsql.iam_authentication=on --no-enable-dataplex-integration "
        "--deletion-protection --async --quiet",
        "gcloud sql instances create aleogr-shared " + SQL + " --database-version=POSTGRES_17 "
        "--edition=enterprise --tier=db-f1-micro --region=southamerica-east1 "
        "--availability-type=zonal --storage-type=SSD --storage-size=10 "
        "--no-storage-auto-increase --assign-ip --authorized-networks=0.0.0.0/0 --backup "
        "--backup-start-time=06:00 --retained-backups-count=7 "
        "--no-enable-point-in-time-recovery --database-flags=cloudsql.iam_authentication=on "
        "--no-enable-dataplex-integration --deletion-protection --async --quiet",
        "gcloud sql instances create aleogr-shared " + SQL + " --database-version=POSTGRES_17 "
        "--edition=enterprise --tier=db-f1-micro --region=southamerica-east1 "
        "--availability-type=zonal --storage-type=SSD --storage-size=10 "
        "--no-storage-auto-increase --assign-ip --backup --backup-start-time=06:00 "
        "--retained-backups-count=7 --no-enable-point-in-time-recovery "
        "--database-flags=cloudsql.iam_authentication=on --no-enable-dataplex-integration "
        "--async --quiet",
        "gcloud scheduler jobs pause aleogr-shared-stop-weeknight " + SQL
        + " --location=southamerica-east1 --quiet",
    ],
    "gcp-cloud-sql_instance-switch-setup": [
        "gcloud scheduler jobs create http aleogr-other " + SQL,
        "gcloud scheduler jobs resume aleogr-other " + SQL + " --location=x --quiet",
        "gcloud scheduler jobs pause aleogr-shared-stop-weekend " + SQL + " --location=x --quiet",
        "gcloud projects add-iam-policy-binding " + S + " --member=serviceAccount:" + SWITCH_SA
        + " --role=roles/cloudsql.admin --condition=None --quiet",
        "gcloud projects add-iam-policy-binding " + S + " --member=serviceAccount:"
        + SWITCH_SA.replace(S, P) + " --role=projects/" + S
        + "/roles/aleogrSharedSqlSwitch --condition=None --quiet",
        "gcloud projects add-iam-policy-binding " + S + " --member=serviceAccount:" + SWITCH_SA
        + " --role=projects/" + S + "/roles/aleogrSharedSqlSwitch --quiet",
        "gcloud iam service-accounts add-iam-policy-binding " + SWITCH_SA + " " + SQL
        + " --member=serviceAccount:x@" + S + ".iam.gserviceaccount.com "
        "--role=roles/iam.serviceAccountUser --quiet",
        "gcloud iam service-accounts add-iam-policy-binding " + SWITCH_SA + " " + SQL
        + " --member=user:owner@example.com --role=roles/iam.serviceAccountTokenCreator --quiet",
        "gcloud iam roles update aleogrSharedSqlSwitch " + SQL
        + " --permissions=cloudsql.instances.get --quiet",
    ],
    "gcp-cloud-sql_database-create": [
        "gcloud sql databases create my_app_dev --instance=aleogr-shared " + SQL
        + " --charset=UTF8 --quiet",
        "gcloud sql databases create my_app_dev --instance=aleogr-shared " + SQL
        + " --async --quiet",
        "gcloud sql databases patch my_app_dev --instance=aleogr-shared " + SQL + " --quiet",
        "gcloud sql users create demo-web@" + P + ".iam --instance=aleogr-shared " + SQL
        + " --type=cloud_iam_service_account --quiet",
    ],
    "gcp-cloud-sql_access-grant": [
        "gcloud sql users create demo-web@" + P + ".iam --instance=aleogr-shared " + SQL
        + " --type=built_in --quiet",
        "gcloud sql users create demo-web@" + P + ".iam.gserviceaccount.com "
        "--instance=aleogr-shared " + SQL + " --type=cloud_iam_service_account --quiet",
        "gcloud sql users create demo-web@" + P + ".iam --instance=aleogr-shared " + SQL
        + " --type=cloud_iam_service_account --database-roles=pg_read_all_data --quiet",
        "gcloud projects add-iam-policy-binding " + S + " --member=serviceAccount:" + WEB_SA
        + " --role=roles/cloudsql.admin --condition=None --quiet",
        "gcloud projects add-iam-policy-binding " + S + " --member=user:x@example.com "
        "--role=roles/cloudsql.client --condition=None --quiet",
        "gcloud projects add-iam-policy-binding " + S + " --member=serviceAccount:" + WEB_SA
        + " --role=roles/cloudsql.client --quiet",
        "gcloud sql instances patch aleogr-shared " + SQL + " --activation-policy=ALWAYS "
        "--async --quiet",
    ],
    "gcp-artifact-registry_repository-create": [
        "gcloud artifacts repositories create demo --project=" + P + " --location=us-central1 "
        "--repository-format=maven --labels=aleogr-project=demo,aleogr-environment=dev",
        "gcloud artifacts repositories create demo --project=" + P + " --location=us-central1 "
        "--repository-format=docker --labels=aleogr-project=other,aleogr-environment=dev",
        "gcloud artifacts repositories create demo --project=" + P + " --location=us "
        "--repository-format=docker --labels=aleogr-project=demo,aleogr-environment=dev",
        "gcloud artifacts repositories update demo --project=" + P + " --location=us-central1",
    ],
    "gcp-artifact-registry_cleanup-configure": [
        "gcloud artifacts repositories set-cleanup-policies demo --location=us-central1 "
        "--project=" + P + " --policy=" + CLEANUP_POLICY + " --dry-run",
        "gcloud artifacts repositories set-cleanup-policies demo --location=us-central1 "
        "--project=" + P + " --policy=" + CLEANUP_POLICY,
        "gcloud artifacts repositories set-cleanup-policies demo --location=us-central1 "
        "--project=" + P + " --policy=/tmp/other.json --no-dry-run",
        "gcloud artifacts repositories set-cleanup-policies demo --location=us-central1 "
        "--project=" + P + " --policy=/tmp/aleogr-cleanup-policy-keep-51.json --no-dry-run",
        "gcloud artifacts repositories set-cleanup-policies demo --location=us-central1 "
        "--project=" + P + " --policy=aleogr-cleanup-policy-keep-3.json --no-dry-run",
        "gcloud artifacts repositories set-cleanup-policies demo --location=us-central1 "
        "--project=" + P + " --policy=/var/tmp/aleogr-cleanup-policy-keep-3.json --no-dry-run",
        "gcloud artifacts repositories set-cleanup-policies demo --location=us-central1 "
        "--project=" + P + " --policy=" + STOP_BODY + " --no-dry-run",
    ],
    "gcp-artifact-registry_access-grant": [
        "gcloud artifacts repositories add-iam-policy-binding demo --location=us-central1 "
        "--project=" + P + " --member=serviceAccount:" + CI_SA
        + " --role=roles/artifactregistry.admin --condition=None --quiet",
        "gcloud artifacts repositories add-iam-policy-binding demo --location=us-central1 "
        "--project=" + P + " --member=serviceAccount:" + CI_SA.replace(P, S)
        + " --role=roles/artifactregistry.writer --condition=None --quiet",
        "gcloud artifacts repositories add-iam-policy-binding demo --location=us-central1 "
        "--project=" + P + " --member=user:x@example.com "
        "--role=roles/artifactregistry.writer --condition=None --quiet",
        "gcloud projects add-iam-policy-binding " + P + " --member=serviceAccount:" + CI_SA
        + " --role=roles/artifactregistry.writer --condition=None --quiet",
    ],
    "gcp_environment-create": [
        ["gcloud", "projects", "create", "aleogr-dev-my-app-x7k2", "--folder=222222222222",
         "--name=hom my-app", "--labels=aleogr-project=my-app,aleogr-environment=dev"],
        ["gcloud", "projects", "create", "aleogr-dev-my-app-x7k2", "--folder=222222222222",
         "--name=dev my-app", "--labels=aleogr-project=other,aleogr-environment=dev"],
        ["gcloud", "projects", "create", "aleogr-dev-my-app-x7k2", "--folder=222222222222",
         "--name=dev my-app", "--labels=aleogr-project=my-app,aleogr-environment=hom"],
        ["gcloud", "projects", "create", "aleogr-dev-my-app-x7k2", "--organization=111111111111",
         "--name=dev my-app", "--labels=aleogr-project=my-app,aleogr-environment=dev"],
        "gcloud projects create aleogr-shared-x7k2 --folder=222222222222 --name=shared "
        "--labels=aleogr-project=shared,aleogr-platform=shared",
        "gcloud projects create other-project --organization=111111111111 --name=shared "
        "--labels=aleogr-project=shared,aleogr-platform=shared",
        "gcloud billing projects unlink " + P,
        "gcloud projects move " + P + " --folder=1",
    ],
    "gcp_services-enable": [
        "gcloud services enable --project=" + P,
        "gcloud services enable run.googleapis.com",
        "gcloud services enable example.com --project=" + P,
        "gcloud services disable run.googleapis.com --project=" + P,
    ],
    "gcp_budget-alert-setup": [
        "gcloud billing budgets create --billing-account=0X0X0X-0X0X0X-0X0X0X "
        "--display-name=x --budget-amount=0BRL --threshold-rule=percent=0.5 "
        "--billing-project=" + S,
        "gcloud billing budgets create --billing-account=0X0X0X-0X0X0X-0X0X0X "
        "--display-name=x --budget-amount=100BRL --threshold-rule=percent=1.5 "
        "--billing-project=" + S,
        "gcloud billing budgets create --billing-account=0X0X0X-0X0X0X-0X0X0X "
        "--display-name=x --budget-amount=100BRL --billing-project=" + S,
        "gcloud billing budgets update 1b2c --billing-account=0X0X0X-0X0X0X-0X0X0X "
        "--budget-amount=100BRL --add-threshold-rule=percent=0.5 --billing-project=" + S,
    ],
    "gcp_login-setup": [
        "gcloud organizations add-iam-policy-binding 111111111111 --member=user:owner@example.com "
        "--role=roles/iap.admin --condition=None --quiet",
        "gcloud organizations add-iam-policy-binding 111111111111 --member=group:g@example.com "
        "--role=roles/iap.settingsAdmin --condition=None --quiet",
        "gcloud organizations add-iam-policy-binding 111111111111 --member=user:owner@example.com "
        "--role=roles/iap.settingsAdmin --quiet",
        "gcloud iap settings set settings.yaml --organization=111111111111",
        "gcloud services enable run.googleapis.com --project=" + S,
    ],
    "gcp_deploy-setup": [
        "gcloud run services update demo-web --set-env-vars=A=1 --region=us-central1 "
        "--project=" + P + " --quiet",
        "gcloud run services update demo-web --remove-env-vars=A --region=us-central1 "
        "--project=" + P + " --quiet",
        "gcloud run services update demo-web --clear-env-vars --region=us-central1 "
        "--project=" + P + " --quiet",
        "gcloud run services update demo-web --env-vars-file=env.yaml --region=us-central1 "
        "--project=" + P + " --quiet",
        "gcloud run services update demo-web --update-env-vars=A=1,B=2 --region=us-central1 "
        "--project=" + P + " --quiet",
        "gcloud run services update demo-web --image=example.com/x --region=us-central1 "
        "--project=" + P + " --quiet",
        "gcloud run services update demo-web --memory=1Gi --update-env-vars=^##^A=1 "
        "--region=us-central1 --project=" + P + " --quiet",
        "gcloud run services update demo-web --no-iap --region=us-central1 --project=" + P
        + " --quiet",
        "gcloud run services update demo-web --no-invoker-iam-check --region=us-central1 "
        "--project=" + P + " --quiet",
        "gcloud run services update demo-web --ingress=all --region=us-central1 --project=" + P
        + " --quiet",
        "gcloud run services update demo-web --min=1 --max=2 --region=us-central1 --project="
        + P + " --quiet",
        "gcloud run services update demo-web --min-instances=1 --region=us-central1 --project="
        + P + " --quiet",
        "gcloud run services update demo-web --scaling=auto --region=us-central1 --project="
        + P + " --quiet",
        "gcloud run services update demo-web --region=us-central1 --project=" + P + " --quiet",
        "gcloud run services update demo-web --service-account=demo-api@" + P
        + ".iam.gserviceaccount.com --region=us-central1 --project=" + P + " --quiet",
        "gcloud run services update demo-web --iap --invoker-iam-check --region=us-central1 "
        "--project=" + P + " --quiet",
        "gcloud run deploy demo-web --image=example.com/other:latest --no-allow-unauthenticated "
        "--iap --service-account=" + WEB_SA + " --min=0 --max=2 --cpu=1 --memory=512Mi "
        "--cpu-throttling --labels=aleogr-project=demo,aleogr-environment=dev,"
        "aleogr-component=web --region=us-central1 --project=" + P + " --quiet",
        "gcloud run deploy demo-web --image=us-docker.pkg.dev/cloudrun/container/hello "
        "--no-allow-unauthenticated --iap --service-account=" + WEB_SA + " --min=1 --max=2 "
        "--cpu=1 --memory=512Mi --cpu-throttling --labels=aleogr-project=demo,"
        "aleogr-environment=dev,aleogr-component=web --region=us-central1 --project=" + P
        + " --quiet",
        "gcloud run deploy demo-web --image=us-docker.pkg.dev/cloudrun/container/hello "
        "--no-allow-unauthenticated --service-account=" + WEB_SA + " --min=0 --max=2 "
        "--cpu=1 --memory=512Mi --cpu-throttling --labels=aleogr-project=demo,"
        "aleogr-environment=dev,aleogr-component=web --region=us-central1 --project=" + P
        + " --quiet",
        "gcloud run deploy demo-web --image=us-docker.pkg.dev/cloudrun/container/hello "
        "--no-allow-unauthenticated --iap --service-account=demo-api@" + P
        + ".iam.gserviceaccount.com --min=0 --max=2 --cpu=1 --memory=512Mi --cpu-throttling "
        "--labels=aleogr-project=demo,aleogr-environment=dev,aleogr-component=web "
        "--region=us-central1 --project=" + P + " --quiet",
        "gcloud run deploy demo-web --image=us-docker.pkg.dev/cloudrun/container/hello "
        "--no-allow-unauthenticated --iap --service-account=" + WEB_SA + " --min=0 --max=2 "
        "--cpu=1 --memory=512Mi --cpu-throttling --labels=aleogr-project=demo,"
        "aleogr-environment=dev,aleogr-component=api --region=us-central1 --project=" + P
        + " --quiet",
        "gcloud run services add-iam-policy-binding demo-web --member=serviceAccount:" + CI_SA
        + " --role=roles/run.admin --region=us-central1 --project=" + P
        + " --condition=None --quiet",
        "gcloud run services add-iam-policy-binding demo-web --member=user:x@example.com "
        "--role=roles/run.invoker --region=us-central1 --project=" + P
        + " --condition=None --quiet",
        "gcloud projects add-iam-policy-binding " + P + " --member=serviceAccount:" + CI_SA
        + " --role=roles/run.developer --condition=None --quiet",
        "gcloud iam service-accounts add-iam-policy-binding " + WEB_SA
        + " --member=serviceAccount:" + CI_SA.replace(P, S)
        + " --role=roles/iam.serviceAccountUser --project=" + P + " --condition=None --quiet",
        ["gcloud", "iam", "service-accounts", "create", "demo-web", "--project=" + P,
         "--display-name=demo api", "--quiet"],
        "gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
        "--region=us-central1 --project=" + P + " --member=group:g@example.com "
        "--role=roles/iap.httpsResourceAccessor --condition=None --quiet",
        "gcloud iap web remove-iam-policy-binding --resource-type=cloud-run --service=demo-web "
        "--region=us-central1 --project=" + P + " --member=allUsers "
        "--role=roles/iap.httpsResourceAccessor --quiet",
    ],
    "gcp_access-grant": [
        "gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
        "--region=us-central1 --project=" + P + " --member=group:team@example.com "
        "--role=roles/iap.httpsResourceAccessor --condition=None --quiet",
        "gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
        "--region=us-central1 --project=" + P + " --member=domain:example.com "
        "--role=roles/iap.httpsResourceAccessor --condition=None --quiet",
        "gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
        "--region=us-central1 --project=" + P + " --member=serviceAccount:" + CI_SA
        + " --role=roles/iap.httpsResourceAccessor --condition=None --quiet",
        "gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
        "--region=us-central1 --project=" + P + " --member=user:" + CI_SA
        + " --role=roles/iap.httpsResourceAccessor --condition=None --quiet",
        "gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
        "--region=us-central1 --project=" + P + " --member=user:demo-user@example.com "
        "--role=roles/iap.admin --condition=None --quiet",
        "gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
        "--region=us-central1 --project=" + P + " --member=user:demo-user@example.com "
        "--role=roles/iap.httpsResourceAccessor --quiet",
        "gcloud projects add-iam-policy-binding " + P + " --member=user:demo-user@example.com "
        "--role=roles/iap.httpsResourceAccessor --condition=None --quiet",
        "gcloud run services add-iam-policy-binding demo-web --member=user:demo-user@example.com "
        "--role=roles/run.invoker --region=us-central1 --project=" + P
        + " --condition=None --quiet",
        "gcloud iap web remove-iam-policy-binding --resource-type=cloud-run --service=demo-web "
        "--region=us-central1 --project=" + P + " --member=allUsers "
        "--role=roles/iap.httpsResourceAccessor --all",
    ],
    "gcp_ci-identity-setup": [
        "gcloud projects add-iam-policy-binding " + P + " --member=serviceAccount:" + CI_SA
        + " --role=roles/run.developer --condition=None --quiet",
        "gcloud iam service-accounts add-iam-policy-binding " + CI_SA + " --project=" + P
        + " --member=" + PRINCIPAL + " --role=roles/iam.serviceAccountTokenCreator --quiet",
        "gcloud iam service-accounts add-iam-policy-binding " + CI_SA + " --project=" + S
        + " --member=" + PRINCIPAL + " --role=roles/iam.workloadIdentityUser --quiet",
        "gcloud iam service-accounts add-iam-policy-binding " + CI_SA + " --project=" + P
        + " --member=" + PRINCIPAL.replace("/github/", "/other/")
        + " --role=roles/iam.workloadIdentityUser --quiet",
        "gcloud iam service-accounts create demo-ci --project=" + P + " --quiet",
        "gcloud iam workload-identity-pools providers update-oidc github --project=" + P
        + " --location=global --workload-identity-pool=github --attribute-condition=true "
        "--quiet",
        "gcloud iam workload-identity-pools undelete github --project=" + P + " --location=global",
    ],
})


def words(cmd):
    return cmd.split(" ") if isinstance(cmd, str) else list(cmd)


def root_of(skill):
    """The folder of the plugin that holds `skill`."""
    if skill.startswith("gcp-cloud-sql_"):
        return DB
    if skill.startswith("gcp-artifact-registry_"):
        return REGISTRY
    if skill.startswith("gcp_"):
        return CLOUD
    return REPO_GITHUB


def refusal(skill, cmd):
    return common.write_refusal(skill, words(cmd), root=root_of(skill))


class TestAllowlistOfWrites(unittest.TestCase):
    def test_every_prescribed_write_is_allowed_for_its_skill(self):
        for skill, cmds in ALLOWED.items():
            for cmd in cmds:
                with self.subTest(skill=skill, cmd=" ".join(cmd)):
                    self.assertIsNone(refusal(skill, cmd))

    def test_a_write_of_one_skill_is_refused_for_the_others(self):
        for skill, cmds in ALLOWED.items():
            for cmd in cmds:
                for other in list(ALLOWED) + ["github_ci-setup", "project-declare"]:
                    if other == skill or any(cmd == c for c in ALLOWED.get(other, ())):
                        continue
                    with self.subTest(skill=other, cmd=" ".join(cmd)):
                        self.assertIsNotNone(refusal(other, cmd))

    def test_refused_always(self):
        skills = list(common.WRITE_SHAPES) + ["github_ci-setup", "project-declare"]
        for cmd in ALWAYS_REFUSED:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(common.always_refused(words(cmd)))
                for skill in skills:
                    self.assertIsNotNone(refusal(skill, cmd), skill)

    def test_refused_when_not_on_the_list(self):
        for skill, cmds in NOT_ON_THE_LIST.items():
            for cmd in cmds:
                with self.subTest(skill=skill, cmd=cmd):
                    self.assertIsNotNone(refusal(skill, cmd))

    def test_never(self):
        for skill in list(common.WRITE_SHAPES) + ["github_ci-setup", "project-declare"]:
            for cmd in NEVER:
                with self.subTest(skill=skill, cmd=cmd):
                    self.assertIsNotNone(refusal(skill, cmd))

    def test_push_to_the_default_branch(self):
        # Only github_checkout-setup pushes a branch that is not aleogr/change-<random>
        # (the birth of the repository); github_pull-request-open never does.
        push_main = ["git"] + CRED + ["push", "-u", "origin", "main"]
        push_change = ["git"] + CRED + ["push", "-u", "origin", "aleogr/change-ab12cd"]
        self.assertIsNone(refusal("github_checkout-setup", push_main))
        self.assertIsNotNone(refusal("github_pull-request-open", push_main))
        self.assertIsNone(refusal("github_pull-request-open", push_change))
        pushers = [s for s, cmds in ALLOWED.items()
                   if any("push" in c for c in cmds)]
        self.assertEqual(sorted(pushers), ["github_checkout-setup", "github_pull-request-open"])

    def test_ruleset_input_must_be_the_plugin_file(self):
        cmd = ALLOWED["github_branch-protect"][0]
        self.assertIsNotNone(common.write_refusal("github_branch-protect", cmd))  # no root
        other = os.path.join(PLUGINS, "aleogr", "files", "ruleset-main.json")
        self.assertIsNotNone(refusal("github_branch-protect", cmd[:-1] + [other]))

    def test_no_read_is_a_write_and_no_write_is_a_read(self):
        for skill, cmds in ALLOWED.items():
            for cmd in cmds:
                with self.subTest(cmd=" ".join(cmd)):
                    self.assertIsNotNone(common.read_refusal(cmd))

    def test_a_refused_write_is_not_shown_and_not_run(self):
        with StandIns() as s:
            for cmd in ALWAYS_REFUSED + NOT_ON_THE_LIST["github_variables-set"]:
                with self.subTest(cmd=cmd):
                    err = io.StringIO()
                    with self.assertRaises(common.WriteRefused):
                        common.run_write("github_variables-set", words(cmd), stream=err)
                    self.assertEqual(err.getvalue(), "")
            self.assertEqual(s.ran(), [])

    def test_an_allowed_write_is_shown_then_run(self):
        with StandIns() as s:
            err = io.StringIO()
            c = common.run_write("github_variables-set", ALLOWED["github_variables-set"][0],
                                 stream=err)
            self.assertEqual(c.code, 3)
            self.assertEqual(err.getvalue(), "+ gh variable set GCP_REGION --repo "
                                             "example-org/example-repo --body us-central1\n")
            self.assertEqual(len(s.ran()), 1)


class TestPerSkillIsolation(unittest.TestCase):
    """For each of the 16 skills of part 2b, one test: every write another skill
    prescribes is refused for it, unless it prescribes the very same command."""


def _isolation_test(skill):
    def test(self):
        own = ALLOWED[skill]
        for other, cmds in ALLOWED.items():
            if other == skill:
                continue
            for cmd in cmds:
                if any(cmd == c for c in own):
                    continue
                with self.subTest(other=other, cmd=" ".join(cmd)):
                    self.assertIsNotNone(refusal(skill, cmd))
        # Its own writes are accepted, and only with its plugin's files.
        for cmd in own:
            self.assertIsNone(refusal(skill, cmd), " ".join(cmd))
    return test


for _s in GCLOUD_SKILLS:
    setattr(TestPerSkillIsolation, "test_" + _s.replace("-", "_"), _isolation_test(_s))
del _s


class TestGoogleCloudWrites(unittest.TestCase):
    def test_sixteen_skills_have_gcloud_shapes(self):
        self.assertEqual(len(GCLOUD_SKILLS), 16)
        for s in GCLOUD_SKILLS:
            self.assertEqual(common.WRITE_TOOLS[s], "gcloud", s)
            self.assertTrue(common.WRITE_SHAPES[s], s)

    def test_activation_policy_only_where_the_skill_writes_it(self):
        always = GCLOUD_ALLOWED["gcp-cloud-sql_instance-start"][0]
        for skill in common.WRITE_SHAPES:
            with self.subTest(skill=skill):
                if skill == "gcp-cloud-sql_instance-start":
                    self.assertIsNone(refusal(skill, always))
                else:
                    self.assertIsNotNone(refusal(skill, always))
                if skill in ("gcp-cloud-sql_instance-stop", "gcp-cloud-sql_instance-create"):
                    self.assertIsNone(refusal(skill, STOP))
                else:
                    self.assertIsNotNone(refusal(skill, STOP))

    def test_who_may_grant_which_role(self):
        # Every add-iam-policy-binding of part 2b, by role: only the skills that name
        # that role grant it.
        roles = {}
        for skill, cmds in GCLOUD_ALLOWED.items():
            for cmd in cmds:
                if "add-iam-policy-binding" in cmd:
                    role = [a for a in cmd if a.startswith("--role=")][0]
                    roles.setdefault(role.split("=", 1)[1], set()).add(skill)
        self.assertEqual(roles, {
            "projects/%s/roles/aleogrSharedSqlSwitch" % S: {"gcp-cloud-sql_instance-switch-setup"},
            "roles/iam.serviceAccountUser": {"gcp-cloud-sql_instance-switch-setup",
                                             "gcp_deploy-setup"},
            "roles/iam.workloadIdentityUser": {"gcp-cloud-sql_instance-switch-setup",
                                               "gcp_ci-identity-setup"},
            "roles/cloudsql.client": {"gcp-cloud-sql_access-grant"},
            "roles/cloudsql.instanceUser": {"gcp-cloud-sql_access-grant"},
            "roles/artifactregistry.writer": {"gcp-artifact-registry_access-grant"},
            "roles/iap.settingsAdmin": {"gcp_login-setup"},
            "roles/run.invoker": {"gcp_deploy-setup"},
            "roles/run.developer": {"gcp_deploy-setup"},
            "roles/iap.httpsResourceAccessor": {"gcp_deploy-setup", "gcp_access-grant"},
        })

    def test_the_plugin_files_must_be_this_plugin_s(self):
        create = GCLOUD_ALLOWED["gcp-cloud-sql_instance-switch-setup"][7]
        self.assertIsNone(refusal("gcp-cloud-sql_instance-switch-setup", create))
        self.assertIsNotNone(common.write_refusal("gcp-cloud-sql_instance-switch-setup", create))
        other = [a.replace(DB, REGISTRY) for a in create]
        self.assertIsNotNone(refusal("gcp-cloud-sql_instance-switch-setup", other))
        policy = GCLOUD_ALLOWED["gcp-artifact-registry_cleanup-configure"][0]
        self.assertIsNotNone(common.write_refusal("gcp-artifact-registry_cleanup-configure",
                                                  policy, root=DB))

    def test_the_temporary_policy_file_is_in_the_temporary_folder(self):
        top = tempfile.mkdtemp()
        try:
            cmd = g("artifacts repositories set-cleanup-policies demo --location=us-central1 "
                    "--project=%s --policy=%s --no-dry-run"
                    % (P, os.path.join(top, "aleogr-cleanup-policy-keep-7.json")))
            skill = "gcp-artifact-registry_cleanup-configure"
            self.assertIsNone(common.write_refusal(skill, cmd, root=REGISTRY, temp=top))
            self.assertIsNotNone(common.write_refusal(skill, cmd, root=REGISTRY))
        finally:
            shutil.rmtree(top)

    def test_the_scheduler_job_names_this_project(self):
        create = list(GCLOUD_ALLOWED["gcp-cloud-sql_instance-switch-setup"][7])
        skill = "gcp-cloud-sql_instance-switch-setup"
        for i, a in enumerate(create):
            if a.startswith("--uri="):
                bad = create[:i] + [a.replace(S, P)] + create[i + 1:]
                self.assertIsNotNone(refusal(skill, bad))
            if a.startswith("--oauth-service-account-email="):
                bad = create[:i] + [a.replace(S, P)] + create[i + 1:]
                self.assertIsNotNone(refusal(skill, bad))

    def test_no_write_of_part_2b_is_a_read(self):
        for skill, cmds in GCLOUD_ALLOWED.items():
            for cmd in cmds:
                with self.subTest(cmd=" ".join(cmd)):
                    self.assertIsNotNone(common.read_refusal(cmd))


# Every read the 16 skills of part 2b prescribe (both modes), as their SKILL.md writes
# it: the read-only runner accepts each.
READS_2B = [
    g("sql instances describe aleogr-shared --project=%s --format=json" % S),
    g("sql operations list --instance=aleogr-shared --project=%s --filter=status!=DONE "
      "--limit=10 --format=value(operationType,status)" % S),
    g("sql databases list --instance=aleogr-shared --project=%s --format=value(name)" % S),
    g("sql users list --instance=aleogr-shared --project=%s --format=value(name)" % S),
    g("projects get-iam-policy %s --format=json" % S),
    g("projects describe %s --format=value(projectNumber)" % S),
    g("config get-value account"),
    g("iam roles describe aleogrSharedSqlSwitch --project=%s --format=value(includedPermissions)"
      % S),
    g("iam service-accounts describe %s --project=%s --format=value(email)" % (SWITCH_SA, S)),
    ["gcloud", "projects", "get-iam-policy", S, "--flatten=bindings[].members",
     "--filter=bindings.role:roles/aleogrSharedSqlSwitch", "--format=value(bindings.members)"],
    g("iam service-accounts get-iam-policy %s --project=%s --format=json" % (SWITCH_SA, S)),
    g("iam workload-identity-pools describe github --project=%s --location=global "
      "--format=value(state)" % S),
    g("iam workload-identity-pools providers describe aleogr --project=%s --location=global "
      "--workload-identity-pool=github --format=value(attributeCondition)" % S),
    g("iam workload-identity-pools providers list --workload-identity-pool=github "
      "--project=%s --location=global --format=value(name)" % P),
    g("scheduler jobs describe aleogr-shared-stop-weeknight --project=%s "
      "--location=southamerica-east1 --format=value(schedule,timeZone,state,httpTarget.uri,"
      "httpTarget.oauthToken.serviceAccountEmail,httpTarget.httpMethod,httpTarget.headers,"
      "httpTarget.body,httpTarget.oauthToken.scope,lastAttemptTime,status.code)" % S),
    g("artifacts repositories describe demo --location=us-central1 --project=%s "
      "--format=json(name,format,labels)" % P),
    g("artifacts repositories describe demo --location=us-central1 --project=%s --format=json"
      % P),
    g("artifacts repositories get-iam-policy demo --location=us-central1 --project=%s "
      "--format=json" % P),
    g("organizations list --format=value(name)"),
    g("resource-manager folders list --organization=111111111111 --filter=displayName=dev "
      "--format=value(name)"),
    g("resource-manager folders list --folder=333333333333 --filter=displayName=dev "
      "--format=value(name)"),
    ["gcloud", "projects", "list", "--filter=parent.type=folder AND parent.id=222222222222 AND "
     "labels.aleogr-project=demo AND labels.aleogr-environment=dev", "--format=value(projectId)"],
    g("billing projects describe %s --format=value(billingEnabled)" % P),
    g("billing accounts list --filter=open=true --format=value(name)"),
    g("projects describe %s --format=value(lifecycleState)" % P),
    g("services list --enabled --project=%s --format=value(config.name)" % P),
    g("billing budgets list --billing-account=0X0X0X-0X0X0X-0X0X0X --billing-project=%s "
      "--format=value(displayName,name)" % S),
    g("billing budgets describe 1b2c --billing-account=0X0X0X-0X0X0X-0X0X0X "
      "--billing-project=%s --format=json" % S),
    ["gcloud", "organizations", "get-iam-policy", "111111111111",
     "--flatten=bindings[].members",
     "--filter=bindings.role=roles/iap.settingsAdmin AND bindings.members=user:o@example.com",
     "--format=value(bindings.members)"],
    g("services list --enabled --project=%s --filter=config.name=iap.googleapis.com "
      "--format=value(config.name)" % S),
    g("iap settings get --organization=111111111111 --billing-project=%s --format=json" % S),
    g("run services describe demo-web --project=%s --region=us-central1 --format=json" % P),
    g("run services describe demo-web --project=%s --region=us-central1 "
      "--format=value(metadata.name)" % P),
    g("run services get-iam-policy demo-web --project=%s --region=us-central1 --format=json"
      % P),
    g("iap web get-iam-policy --resource-type=cloud-run --service=demo-web --region=us-central1 "
      "--project=%s --format=json" % P),
    g("iam service-accounts describe %s --project=%s --format=value(email)" % (CI_SA, P)),
    g("iam workload-identity-pools describe github --project=%s --location=global --format=json"
      % P),
    ["sleep", "30"],
]

READS_REFUSED_2B = [
    "gcloud config get-value project",
    "gcloud config get-value account extra",
    "gcloud config set project demo",
    "gcloud auth print-access-token",
    "gcloud auth print-identity-token",
    "gcloud projects describe demo --impersonate-service-account=" + CI_SA,
    "gcloud --impersonate-service-account=" + CI_SA + " projects describe demo",
    "gcloud iam service-accounts keys list --iam-account=" + CI_SA,
    "gcloud scheduler jobs run aleogr-shared-stop-weeknight --location=x",
]


class TestReadsOfPart2b(unittest.TestCase):
    def test_every_read_is_accepted(self):
        for cmd in READS_2B:
            with self.subTest(cmd=" ".join(cmd)):
                self.assertIsNone(common.read_refusal(cmd))

    def test_refused_reads(self):
        for cmd in READS_REFUSED_2B:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(common.read_refusal(words(cmd)))

    def test_a_name_is_not_a_flag(self):
        # A resource may be named after the owner's project: only flags and the
        # set-password command are refused, not a name that holds the word.
        argv = g("sql databases create password_dev --instance=aleogr-shared " + SQL
                 + " --quiet")
        self.assertIsNone(refusal("gcp-cloud-sql_database-create", argv))

    def test_auth_list_and_version_stay_reads(self):
        for cmd in ("gcloud auth list --filter=status:ACTIVE --format=value(account)",
                    "gcloud --version", "gcloud.cmd --version"):
            self.assertIsNone(common.read_refusal(words(cmd)), cmd)
            self.assertIsNone(common.always_refused(words(cmd)), cmd)


class TestTemporaryFile(unittest.TestCase):
    SKILL = "gcp-artifact-registry_cleanup-configure"
    NAME = "aleogr-cleanup-policy-keep-7.json"

    def setUp(self):
        self.top = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.top)

    def test_writes_the_exact_content_and_says_so(self):
        err = io.StringIO()
        path = common.write_temp_file(self.SKILL, self.NAME, "[\n  1\n]\n", stream=err,
                                      folder=self.top)
        self.assertEqual(path, os.path.join(self.top, self.NAME))
        self.assertEqual(err.getvalue(), "+ write %s\n" % path)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"[\n  1\n]\n")
        common.write_temp_file(self.SKILL, self.NAME, "x", stream=io.StringIO(), folder=self.top)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"x")  # its whole content replaced

    def test_refuses_another_name_before_showing_it(self):
        for name in ("aleogr-cleanup-policy-keep-51.json", "other.json", "../x.json",
                     "sub/aleogr-cleanup-policy-keep-7.json", ""):
            err = io.StringIO()
            with self.assertRaises(common.WriteRefused):
                common.write_temp_file(self.SKILL, name, "x", stream=err, folder=self.top)
            self.assertEqual(err.getvalue(), "")
        with self.assertRaises(common.WriteRefused):
            common.write_temp_file("gcp_deploy-setup", self.NAME, "x", stream=io.StringIO(),
                                   folder=self.top)
        self.assertEqual(os.listdir(self.top), [])

    def test_a_link_at_that_name_is_not_followed(self):
        target = os.path.join(self.top, "target")
        with open(target, "w") as f:
            f.write("kept")
        os.symlink(target, os.path.join(self.top, self.NAME))
        self.assertIsNone(common.write_temp_file(self.SKILL, self.NAME, "x",
                                                 stream=io.StringIO(), folder=self.top))
        with open(target) as f:
            self.assertEqual(f.read(), "kept")

    def test_ctx_only_when_the_run_may_write(self):
        ctx = common.Context("aleogr-registry-gcp-artifact-registry", REGISTRY, self.SKILL,
                             Writer, "plan", {})
        with self.assertRaises(common.WriteRefused):
            ctx.write_temp_file(self.NAME, "x")

    def test_the_system_temporary_folder(self):
        if os.name != "nt":
            self.assertEqual(common.system_temp_dir(), "/tmp")


class TestBodiesAndNames(unittest.TestCase):
    def test_the_stop_body_as_its_skill_names_it(self):
        b64 = common.base64_of_file(STOP_BODY)
        self.assertEqual(b64, "eyJzZXR0aW5ncyI6eyJhY3RpdmF0aW9uUG9saWN5IjoiTkVWRVIifX0=")
        self.assertEqual(common.json_from_base64(b64),
                         {"settings": {"activationPolicy": "NEVER"}})
        self.assertEqual(common.json_from_base64(" eyJhIjox\nfQ== \n"), {"a": 1})
        for bad in ("", "not base64!", "bm90IGpzb24=", None):
            self.assertIsNone(common.json_from_base64(bad), bad)
        self.assertIsNone(common.base64_of_file(os.path.join(DB, "files", "nothing.json")))

    def test_random_name_part(self):
        got = {common.random_name_part() for _ in range(20)}
        self.assertTrue(all(len(x) == 4 and x.isalnum() and x == x.lower() for x in got))
        self.assertGreater(len(got), 1)
        self.assertEqual(len(common.random_name_part(6)), 6)


class TestCallPluginRefused(unittest.TestCase):
    def test_a_refused_callee_keeps_its_answer(self):
        result = {"aleogr-result": 1, "action": "x", "status": "failed", "outputs": {},
                  "answer": [common.REFUSED_SENTENCE, common.REFUSED_NOTHING_WRITTEN]}
        with StandIns() as s:
            p = os.path.join(s.dir, "aleogr-fake")
            with open(p, "w") as f:
                f.write("#!/bin/sh\necho '%s'\nexit 70\n" % json.dumps(result))
            os.chmod(p, 0o755)
            got = common.call_plugin("aleogr-fake", "x")
            self.assertEqual(got["answer"], result["answer"])
            self.assertEqual((got["status"], got["callError"]), ("failed", "refused"))
            with open(p, "w") as f:
                f.write("#!/bin/sh\necho not json\nexit 70\n")
            self.assertEqual(common.call_plugin("aleogr-fake", "x")["callError"], "no-result")
            with open(p, "w") as f:
                f.write("#!/bin/sh\necho '%s'\nexit 1\n" % json.dumps(result))
            self.assertEqual(common.call_plugin("aleogr-fake", "x")["callError"], "no-result")

    def test_with_a_real_command_stopped_by_a_refusal(self):
        # The dispatcher of a real plugin: a module whose write is refused exits 70
        # after its failed result, and the caller gets that result.
        top = tempfile.mkdtemp()
        try:
            plugin = os.path.join(top, "aleogr-demo")
            os.makedirs(os.path.join(plugin, "scripts", "skills"))
            os.makedirs(os.path.join(plugin, "bin"))
            shutil.copy(os.path.join(PLUGINS, "aleogr", "scripts", "aleogr_common.py"),
                        os.path.join(plugin, "scripts"))
            shutil.copy(os.path.join(PLUGINS, "aleogr", "bin", "aleogr"),
                        os.path.join(plugin, "bin", "aleogr-demo"))
            with open(os.path.join(plugin, "scripts", "skills", "__init__.py"), "w"):
                pass
            with open(os.path.join(plugin, "scripts", "skills", "demo_x.py"), "w") as f:
                f.write("FAMILY = 'cloud'\nPROVIDER = 'gcp'\nACTION = 'x'\nWRITES = True\n"
                        "def run(args, ctx):\n"
                        "    ctx.write(['gcloud', 'projects', 'delete', 'demo'])\n")
            env = dict(os.environ, PATH=os.path.join(plugin, "bin") + os.pathsep
                       + os.environ.get("PATH", ""), PYTHONDONTWRITEBYTECODE="1")
            old = os.environ.copy()
            os.environ.update(env)
            saved = os.dup(2)  # the callee's stderr goes through to ours: keep it quiet
            try:
                with open(os.devnull, "w") as null:
                    os.dup2(null.fileno(), 2)
                    got = common.call_plugin("aleogr-demo", "demo_x", {"mode": "apply"})
            finally:
                os.dup2(saved, 2)
                os.close(saved)
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(got["callError"], "refused")
            self.assertEqual(got["answer"], [common.REFUSED_SENTENCE,
                                             common.REFUSED_NOTHING_WRITTEN])
            self.assertEqual(got["mode"], "apply")
        finally:
            shutil.rmtree(top)


class Writer(object):
    FAMILY = "repo"
    PROVIDER = "github"
    ACTION = "variables-set"
    WRITES = True


class Reader(object):
    FAMILY = "repo"
    PROVIDER = "github"
    ACTION = "variables-set"


SET = ["gh", "variable", "set", "GCP_REGION", "--repo", "example-org/example-repo", "--body",
       "us-central1"]


class TestWritingRunnerOfTheContext(unittest.TestCase):
    def ctx(self, module=Writer, mode="apply", read_only=False, skill="github_variables-set"):
        return common.Context("aleogr-repo-github", REPO_GITHUB, skill, module, mode, {},
                              read_only=read_only)

    def test_writable_only_in_apply_without_read_only(self):
        self.assertTrue(self.ctx().writable)
        self.assertFalse(self.ctx(mode="plan").writable)
        self.assertFalse(self.ctx(mode="later").writable)
        self.assertFalse(self.ctx(read_only=True).writable)
        self.assertFalse(self.ctx(module=Reader).writable)
        self.assertEqual(self.ctx(mode="plan").read_only, True)

    def test_refused_outside_apply_before_anything_runs(self):
        with StandIns() as s:
            for ctx in (self.ctx(mode="plan"), self.ctx(read_only=True),
                        self.ctx(module=Reader)):
                with self.assertRaises(common.WriteRefused):
                    ctx.write(SET)
                with self.assertRaises(common.ReadRefused):
                    ctx.run(SET)
            self.assertEqual(s.ran(), [])

    def test_ctx_write_checks_the_skill_s_list(self):
        with StandIns() as s, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(common.WriteRefused):
                self.ctx(skill="github_repo-create").write(SET)
            with self.assertRaises(common.WriteRefused):
                self.ctx().write(["gh", "pr", "merge", "1"])
            self.assertEqual(s.ran(), [])
            c = self.ctx().write(SET)
            self.assertEqual(c.code, 3)
            c = self.ctx().run(SET)  # ctx.run routes a write to ctx.write
            self.assertEqual(len(s.ran()), 2)

    def test_reads_stay_on_the_read_only_runner_in_apply(self):
        with StandIns() as s, contextlib.redirect_stderr(io.StringIO()):
            ctx = self.ctx()
            ctx.read(["gh", "variable", "list", "--repo", "o/r", "--json", "name,value"])
            with self.assertRaises(common.ReadRefused):
                ctx.read(SET)
            self.assertEqual(len(s.ran()), 1)


class TestHiddenValues(unittest.TestCase):
    def test_shown_as_value_and_run_with_the_value(self):
        argv = SET[:-1] + [common.Hidden("us-central1")]
        self.assertEqual(common.show_command(argv),
                         "gh variable set GCP_REGION --repo example-org/example-repo --body "
                         "<value>")
        self.assertEqual(common._plain(argv)[-1], "us-central1")
        self.assertEqual(str(argv[-1]), "<value>")
        self.assertEqual(repr(argv[-1]), "<value>")
        self.assertNotIn("us-central1", "%s %r" % (argv[-1], argv))

    def test_runner_shows_value_and_runs_with_the_value(self):
        with StandIns() as s:
            err = io.StringIO()
            common.run_write("github_variables-set", SET[:-1] + [common.Hidden("s3cr3t x")],
                             stream=err)
            self.assertEqual(err.getvalue(), "+ gh variable set GCP_REGION --repo "
                                             "example-org/example-repo --body <value>\n")
            self.assertEqual(s.ran()[0].split(" ", 1)[1],
                             "variable set GCP_REGION --repo example-org/example-repo --body "
                             "s3cr3t x")

    def test_shown_text_of_choice(self):
        argv = ["git", "config", "--local", "user.name", common.Hidden("octo", "<login>")]
        self.assertEqual(common.show_command(argv), "git config --local user.name <login>")
        self.assertIsNone(common.write_refusal("github_checkout-setup", argv))

    def test_a_refusal_does_not_show_the_value(self):
        argv = ["gh", "variable", "delete", common.Hidden("s3cr3t")]
        with self.assertRaises(common.WriteRefused) as e:
            common.run_write("github_variables-set", argv)
        self.assertNotIn("s3cr3t", str(e.exception))
        argv = ["gh", "variable", "set", "A", "--repo", "o/r", "--body", common.Hidden("s3cr3t")]
        with self.assertRaises(common.ReadRefused) as e:
            common.run_read(argv)
        self.assertNotIn("s3cr3t", str(e.exception))


class Folder(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.top = tempfile.mkdtemp()
        self.dir = os.path.join(self.top, "work")
        self.outside = os.path.join(self.top, "outside")
        os.makedirs(self.dir)
        os.makedirs(self.outside)
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.top)

    def read(self, path):
        with open(path, "rb") as f:
            return f.read()


class TestWriteFile(Folder):
    def test_writes_exact_bytes_creating_folders_and_says_so(self):
        err = io.StringIO()
        text = "line one\r\nline two\n\ttab é\n"
        self.assertTrue(common.write_file("github_ci-setup", ".github/workflows/ci.yml",
                                          text, stream=err))
        self.assertEqual(err.getvalue(), "+ write .github/workflows/ci.yml\n")
        self.assertEqual(self.read(".github/workflows/ci.yml"), text.encode("utf-8"))
        self.assertTrue(common.write_file("go_setup", "web/main.go", b"package main\n",
                                          stream=io.StringIO()))
        self.assertEqual(self.read("web/main.go"), b"package main\n")
        common.write_file("go_setup", "web/main.go", b"x", stream=io.StringIO())
        self.assertEqual(self.read("web/main.go"), b"x")

    def refused(self, skill, path):
        err = io.StringIO()
        with self.assertRaises(common.WriteRefused):
            common.write_file(skill, path, "x", stream=err)
        self.assertEqual(err.getvalue(), "", "a refused write is not shown")

    def test_refuses_an_absolute_path(self):
        self.refused("project-declare", os.path.join(self.dir, ".aleogr", "project.json"))
        self.refused("project-declare", "/.aleogr/project.json")
        self.assertEqual(os.listdir(self.dir), [])

    def test_refuses_a_path_that_leaves_the_folder(self):
        self.refused("go_setup", "../outside/go.mod")
        self.refused("go_setup", "web/../../outside/go.mod")
        self.refused("go_setup", "web/./go.mod")
        self.refused("go_setup", "web//go.mod")
        self.assertEqual(os.listdir(self.outside), [])

    def test_refuses_a_link_that_leads_outside(self):
        os.symlink(self.outside, os.path.join(self.dir, "web"))
        self.refused("go_setup", "web/go.mod")
        os.makedirs(".github")
        os.symlink(self.outside, os.path.join(self.dir, ".github", "workflows"))
        self.refused("github_ci-setup", ".github/workflows/ci.yml")
        os.makedirs(".aleogr")
        os.symlink(os.path.join(self.outside, "project.json"),
                   os.path.join(self.dir, ".aleogr", "project.json"))  # dangling, outside
        self.refused("project-declare", ".aleogr/project.json")
        self.assertEqual(os.listdir(self.outside), [])

    def test_a_link_that_stays_inside_is_refused(self):
        # Through a link that stays inside the folder a skill would write a path it does
        # not name: a file under .git, another skill's file.
        os.makedirs("real")
        os.symlink(os.path.join(self.dir, "real"), os.path.join(self.dir, "web"))
        self.refused("go_setup", "web/go.mod")
        self.assertEqual(os.listdir("real"), [])
        os.makedirs(".git/hooks")
        os.makedirs(".github/workflows")
        os.symlink("../../.git/hooks/pre-commit",
                   os.path.join(self.dir, ".github", "workflows", "ci.yml"))
        self.refused("github_ci-setup", ".github/workflows/ci.yml")
        self.assertEqual(os.listdir(".git/hooks"), [])

    def test_refuses_a_file_the_skill_does_not_name(self):
        self.refused("github_ci-setup", ".github/workflows/deploy.yml")
        self.refused("project-declare", "project.json")
        self.refused("go_setup", "web/other.go")
        self.refused("go_setup", ".github/go.mod")
        self.refused("github_variables-set", "x.txt")
        self.refused("no-such-skill", ".aleogr/project.json")

    def test_a_system_refusal_is_false(self):
        with open("web", "w") as f:
            f.write("a file where a folder is wanted")
        self.assertFalse(common.write_file("go_setup", "web/go.mod", "x",
                                           stream=io.StringIO()))

    def test_ctx_write_file_only_when_the_run_may_write(self):
        for mode, read_only in (("plan", False), ("apply", True)):
            ctx = common.Context("aleogr", "/x", "project-declare", Writer, mode, {},
                                 read_only=read_only)
            with self.assertRaises(common.WriteRefused):
                ctx.write_file(".aleogr/project.json", "{}\n")
        self.assertEqual(os.listdir(self.dir), [])
        ctx = common.Context("aleogr", "/x", "project-declare", Writer, "apply", {})
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertTrue(ctx.write_file(".aleogr/project.json", "{}\n"))
        self.assertEqual(err.getvalue(), "+ write .aleogr/project.json\n")


class TestBackup(Folder):
    def setUp(self):
        Folder.setUp(self)
        os.makedirs("web")
        with open("web/go.mod", "wb") as f:
            f.write(b"module x\n\ngo 1.27\n")
        os.chmod("web/go.mod", 0o640)
        os.utime("web/go.mod", (1000000000, 1000000000))

    def test_copies_and_puts_back_byte_for_byte(self):
        err = io.StringIO()
        b = common.Backup("go_setup", ["web/go.mod", "web/go.sum"], stream=err)
        self.assertTrue(b.ok)
        self.assertTrue(os.path.isdir(b.dir))
        self.assertTrue(b.existed("web/go.mod"))
        self.assertFalse(b.existed("web/go.sum"))
        self.assertEqual(os.listdir(b.dir), ["go.mod"])
        with open("web/go.mod", "wb") as f:
            f.write(b"module x\n\ngo 1.28\n")
        with open("web/go.sum", "wb") as f:
            f.write(b"sum\n")
        self.assertTrue(b.restore())
        self.assertEqual(self.read("web/go.mod"), b"module x\n\ngo 1.27\n")
        self.assertEqual(os.stat("web/go.mod").st_mode & 0o777, 0o640)
        self.assertEqual(int(os.stat("web/go.mod").st_mtime), 1000000000)
        self.assertFalse(os.path.exists("web/go.sum"))
        backup = b.dir
        b.discard()
        self.assertFalse(os.path.exists(backup))
        self.assertIsNone(b.dir)
        self.assertEqual(err.getvalue().splitlines(), [
            "+ backup web/go.mod web/go.sum", "+ restore web/go.mod web/go.sum",
            "+ remove " + backup])

    def test_go_sum_that_existed_is_put_back(self):
        with open("web/go.sum", "wb") as f:
            f.write(b"old sum\n")
        b = common.Backup("go_setup", ["web/go.mod", "web/go.sum"], stream=io.StringIO())
        with open("web/go.sum", "wb") as f:
            f.write(b"new sum\n")
        self.assertTrue(b.restore())
        self.assertEqual(self.read("web/go.sum"), b"old sum\n")
        b.discard()

    def test_a_file_that_cannot_be_copied(self):
        os.makedirs("web/go.sum")  # a folder: it cannot be copied as a file
        b = common.Backup("go_setup", ["web/go.mod", "web/go.sum"], stream=io.StringIO())
        self.assertFalse(b.ok)
        self.assertIsNone(b.dir)
        self.assertFalse(b.restore())

    def test_a_restore_that_fails_keeps_the_copies(self):
        b = common.Backup("go_setup", ["web/go.mod"], stream=io.StringIO())
        os.remove("web/go.mod")
        os.makedirs("web/go.mod")  # a folder where the file goes back
        self.assertFalse(b.restore())
        self.assertTrue(os.path.isfile(os.path.join(b.dir, "go.mod")))
        b.discard()

    def test_refuses_the_paths_the_file_helper_refuses(self):
        for paths in (["../outside/go.mod"], ["web/other.go"], ["/tmp/go.mod"],
                      ["web/go.mod", "api/go.mod"]):
            with self.subTest(paths=paths):
                err = io.StringIO()
                with self.assertRaises(common.WriteRefused):
                    common.Backup("go_setup", paths, stream=err)
                self.assertEqual(err.getvalue(), "")

    def test_ctx_backup_only_when_the_run_may_write(self):
        ctx = common.Context("aleogr-stack-go", "/x", "go_setup", Writer, "plan", {})
        with self.assertRaises(common.WriteRefused):
            ctx.backup(["web/go.mod"])


class TestWaits(unittest.TestCase):
    def setUp(self):
        common.reset_wait_budget()

    def tearDown(self):
        common.reset_wait_budget()

    def test_sixteen_waits_of_thirty_seconds_then_the_budget_is_spent(self):
        ctx = common.Context("aleogr-cloud-gcp", "/x", "gcp_login-setup", Writer, "apply", {})
        with StandIns() as s, contextlib.redirect_stderr(io.StringIO()):
            got = [ctx.wait() for _ in range(18)]
            self.assertEqual(got, [True] * 16 + [False] * 2)
            self.assertEqual([line.split(" ", 1)[1] for line in s.ran()], ["30"] * 16)
            self.assertTrue(all(line.endswith("/sleep 30") for line in s.ran()))
        self.assertEqual(common.waited_seconds(), 480)
        self.assertEqual(common.WAIT_BUDGET_SECONDS, 480)
        self.assertFalse(common.wait_allowed())

    def test_the_wait_is_shown_and_in_plan_too(self):
        ctx = common.Context("aleogr-cloud-gcp", "/x", "gcp_login-setup", Reader, "plan", {})
        shown = []

        def execute(argv, timeout=None):
            shown.append(common.show_command(argv))
            return common.Completed(0, "", "")

        ctx.execute = execute
        self.assertTrue(ctx.wait())
        self.assertEqual(shown, ["sleep 30"])

    def test_the_budget_counts_across_contexts_of_one_process(self):
        a = common.Context("p", "/x", "a", Writer, "apply", {})
        b = common.Context("p", "/x", "b", Writer, "apply", {})
        a.execute = b.execute = lambda argv, timeout=None: common.Completed(0, "", "")
        for _ in range(10):
            self.assertTrue(a.wait())
        self.assertEqual([b.wait() for _ in range(7)], [True] * 6 + [False])

    def test_fixed_sentence_and_item(self):
        self.assertIn("eight minutes", common.WAIT_BUDGET_SENTENCE)
        self.assertEqual(common.wait_budget_item("gcp_login-setup"), {
            "item": "run again", "reason": "manual",
            "how": "run gcp_login-setup again with the same arguments: it goes on from "
                   "where this run stopped"})
        ctx = common.Context("p", "/x", "go_setup", Writer, "apply", {})
        self.assertEqual(ctx.wait_budget_item(), common.wait_budget_item("go_setup"))


class TestReadOnlyOption(unittest.TestCase):
    def test_command_line(self):
        for argv in (["--read-only", "--json", "s"], ["--json", "--read-only", "s"]):
            inv = common.parse_command_line(argv + ["mode=apply"])
            self.assertEqual((inv.read_only, inv.json, inv.skill, inv.args),
                             (True, True, "s", {"mode": "apply"}))
        inv = common.parse_command_line(["--read-only", "s"])
        self.assertEqual((inv.read_only, inv.json), (True, False))
        self.assertFalse(common.parse_command_line(["s"]).read_only)
        for bad in (["--read-only"], ["--read-only", "--read-only", "s"],
                    ["--json", "--json", "s"], ["--read-only", "--has", "s"]):
            with self.subTest(argv=bad):
                with self.assertRaises(common.UsageError):
                    common.parse_command_line(bad)

    def command(self, *args, **kw):
        """Run aleogr-repo-github with stand-ins of gh and git that record each call."""
        plugin = "aleogr-repo-github"
        with StandIns() as s:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       PATH=s.dir + os.pathsep + os.path.dirname(sys.executable))
            p = subprocess.run([sys.executable, os.path.join(PLUGINS, plugin, "bin", plugin)]
                               + list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env, cwd=tempfile.gettempdir())
            return p.returncode, p.stdout.decode(), p.stderr.decode(), s.ran()

    def test_apply_is_refused_and_nothing_runs(self):
        args = ["github_variables-set", "owner=example-org", "name=example-repo",
                "variables=GCP_REGION=us-central1", "mode=apply"]
        code, out, err, ran = self.command("--read-only", *args)
        self.assertEqual((code, err, ran), (0, "", []))
        self.assertTrue(out.startswith(common.READ_ONLY_APPLY_SENTENCE + "\n\n```aleogr-result\n"))
        self.assertIn('"status": "failed"', out)
        self.assertIn('"mode": "apply"', out)
        self.assertIn('"cost": { "fixed": false, "notes": "nothing was run" }', out)
        self.assertNotIn("us-central1", out)
        code, out, err, ran = self.command("--json", "--read-only", *args)
        obj = json.loads(out)
        self.assertEqual((code, obj["status"], obj["answer"], obj["action"], ran),
                         (0, "failed", [common.READ_ONLY_APPLY_SENTENCE], "variables-set", []))

    def test_plan_runs_as_without_it(self):
        args = ["github_variables-set", "owner=example-org", "name=example-repo",
                "variables=GCP_REGION=us-central1"]
        a = self.command("--read-only", *args)
        b = self.command(*args)
        self.assertEqual(a[:3], b[:3])
        self.assertEqual([x.split("/gh ", 1)[1] for x in a[3]],
                         ["variable list --repo example-org/example-repo --json name,value"])
        self.assertEqual(len(b[3]), 1)

    def test_call_plugin_passes_it_on(self):
        with StandIns() as s:
            p = os.path.join(s.dir, "aleogr-fake")
            with open(p, "w") as f:
                f.write('#!/bin/sh\necho \'{"aleogr-result": 1, "args": "\'"$*"\'"}\'\n')
            os.chmod(p, 0o755)
            self.assertEqual(common.call_plugin("aleogr-fake", "x", {"a": "1"},
                                                read_only=True)["args"],
                             "--read-only --json x a=1")
            ctx = common.Context("p", "/x", "s", Reader, "plan", {}, read_only=True)
            self.assertEqual(ctx.call("aleogr-fake", "x")["args"], "--read-only --json x")
            ctx = common.Context("p", "/x", "s", Reader, "plan", {})
            self.assertEqual(ctx.call("aleogr-fake", "x")["args"], "--json x")


class TestDirectModeWithFiles(unittest.TestCase):
    """run.sh in the direct mode checks FILE, SAME_FILE, NO_FILE and FILE_NOT lines
    against the scenario's working folder after the command wrote in it. Checked on a
    copy of the harness with a stand-in plugin whose command writes and removes files."""

    def test_file_lines_see_what_the_command_wrote(self):
        tests = os.path.normpath(os.path.join(HERE, ".."))
        top = tempfile.mkdtemp()
        try:
            t = os.path.join(top, ".claude-plugin", "tests")
            shutil.copytree(os.path.join(tests, "bin"), os.path.join(t, "bin"))
            shutil.copy(os.path.join(tests, "run.sh"), t)
            bin_dir = os.path.join(top, ".claude-plugin", "plugins", "demo", "bin")
            os.makedirs(bin_dir)
            with open(os.path.join(bin_dir, "demo"), "w") as f:
                f.write("#!/bin/sh\n[ \"$1\" = write ] || exit 64\nmkdir -p out\n"
                        "printf 'hello\\n' > out/a.txt\nrm -f gone.txt\n"
                        "echo '```aleogr-result'\necho '{}'\necho '```'\n")
            os.chmod(os.path.join(bin_dir, "demo"), 0o755)
            with open(os.path.join(top, "ref.txt"), "w") as f:
                f.write("hello\n")
            sc = os.path.join(t, "scenarios", "demo-write")
            os.makedirs(os.path.join(sc, "files"))
            with open(os.path.join(sc, "files", "gone.txt"), "w") as f:
                f.write("x\n")
            with open(os.path.join(sc, "prompt.txt"), "w") as f:
                f.write("/demo:write mode=apply\n")
            with open(os.path.join(sc, "expect.txt"), "w") as f:
                f.write("FILE out/a.txt ^hello$\nSAME_FILE out/a.txt ref.txt\n"
                        "NO_FILE gone.txt\nFILE_NOT out/a.txt bye\nNOT_CALLED .\n")
            env = dict(os.environ, RUN_MODE="direct")
            p = subprocess.run(["bash", os.path.join(t, "run.sh"), "demo-write"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            self.assertEqual((p.returncode, p.stdout.decode()), (0, "PASS demo-write\n"))
            with open(os.path.join(sc, "expect.txt"), "w") as f:
                f.write("FILE out/a.txt ^bye$\n")
            p = subprocess.run(["bash", os.path.join(t, "run.sh"), "demo-write"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            self.assertEqual(p.returncode, 1)
        finally:
            shutil.rmtree(top)


if __name__ == "__main__":
    unittest.main()

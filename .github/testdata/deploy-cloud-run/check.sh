#!/usr/bin/env bash
# Static check of the reusable deploy workflow.
#
# Usage: check.sh [path]   (default: .github/workflows/deploy-cloud-run.yml)
#
# Parses the file as YAML with the system Python and PyYAML (/usr/bin/python3
# and the Ubuntu package python3-yaml; a missing PyYAML is a failure, never a
# skip). Duplicate keys, anchors, aliases and more than one document are
# refused, so what is checked is what GitHub reads.
#
# Fails unless:
#   - the raw text names none of the forbidden strings (another trigger that
#     runs with the base repository's rights, a create of the service or a
#     change of who may reach it, `secrets: inherit`, a whole-context dump);
#   - the top-level keys are `name`, `on`, `permissions`, `jobs`; `on` holds
#     only `workflow_call`, with exactly the four inputs and the four secrets;
#   - `permissions` is `contents: read`, `id-token: write`, at the top and on
#     the one job; the job has only the expected keys (no `if`, no `uses`);
#   - the job has exactly eight steps: the masking and validation script,
#     checkout, auth, login, Buildx, build and push, setup-gcloud, the update;
#     each action is the expected one pinned by a 40-character SHA with its
#     version in a comment; no step has `if`, `continue-on-error` or `shell`;
#   - every action step's `id`, `with` and `env` are exactly the reviewed
#     ones (no other key, no other expression): so the build writes no
#     summary, uploads no build record, makes no annotation, and Buildx is
#     not cached;
#   - no `run:` script holds `${{`, a line continuation or an `add-mask` with
#     no value; all scripts together invoke `gcloud` once;
#   - `secrets` is read only as one of the four names;
#   - the two scripts and their `env` are exactly the reviewed text below, so
#     the digest test precedes the update and the update is the last command.
#
# What it cannot prove: how GitHub, the runner or the actions behave at run
# time (that a value passed as a secret is masked, that an action's defaults
# do what its README says, that a SHA is the version its comment names), nor
# anything about the caller (that its job runs only on push to the default
# branch). Changing a script means changing this file in the same pull request.

set -u

file="${1:-.github/workflows/deploy-cloud-run.yml}"
py=/usr/bin/python3

if ! "$py" -I -c 'import yaml' 2>/dev/null; then
  echo "FAIL: $py with PyYAML (python3-yaml) is required"
  exit 1
fi

exec "$py" -I - "$file" <<'PY'
import re
import sys

import yaml

path = sys.argv[1]
failures = []


def fail(message):
    failures.append(message)


def finish():
    for message in failures:
        print(f"FAIL: {message}")
    if failures:
        print(f"{len(failures)} check(s) failed for {path}")
        sys.exit(1)
    print(f"OK: {path}")
    sys.exit(0)


try:
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
except OSError:
    fail("cannot read the file")
    finish()
if not text.strip():
    fail("the file is empty")
    finish()

# 1. Raw text, comments included.
FORBIDDEN = [
    "pull_request_target", "workflow_run", "run deploy", "--iap", "no-iap",
    "allow-unauthenticated", "add-iam-policy-binding", "set-iam-policy",
    "setIamPolicy", "allUsers", "allAuthenticatedUsers", "secrets: inherit",
    "toJSON", "fromJSON",
]
for forbidden in FORBIDDEN:
    if forbidden in text:
        fail(f"contains the forbidden string '{forbidden}'")


# 2. Parse: one document, no duplicate key, no anchor or alias.
class StrictLoader(yaml.SafeLoader):
    pass


def construct_mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)

try:
    for event in yaml.parse(text, Loader=StrictLoader):
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None):
            fail("anchors and aliases are not allowed")
            break
    documents = list(yaml.load_all(text, Loader=StrictLoader))
except yaml.YAMLError as error:
    fail(f"not valid YAML for this check: {str(error).splitlines()[0]}")
    finish()
if len(documents) != 1 or not isinstance(documents[0], dict):
    fail("expected one YAML document holding a mapping")
    finish()
doc = documents[0]

INPUTS = {"working-directory", "service", "region", "image-name"}
SECRETS = {"project-id", "workload-identity-provider", "service-account", "image-path"}
PERMISSIONS = {"contents": "read", "id-token": "write"}

# 3. Top level and trigger. PyYAML reads an unquoted `on` as True.
on_keys = [k for k in doc if k is True or k == "on"]
other = [k for k in doc if not (k is True or k == "on")]
if len(on_keys) != 1:
    fail("expected exactly one 'on' key")
if set(other) != {"name", "permissions", "jobs"}:
    fail(f"unexpected top-level keys: {sorted(map(str, other))}")
on = doc[on_keys[0]] if on_keys else None
if not isinstance(on, dict) or list(on) != ["workflow_call"]:
    keys = list(on) if isinstance(on, dict) else on
    fail(f"the triggers are {keys!r}, expected only 'workflow_call'")
    call = {}
else:
    call = on["workflow_call"] or {}
if not isinstance(call, dict) or set(call) != {"inputs", "secrets"}:
    fail("workflow_call must hold exactly 'inputs' and 'secrets'")
    call = {}
inputs = call.get("inputs") or {}
secrets = call.get("secrets") or {}
for name in sorted(set(inputs) & SECRETS):
    fail(f"the identifier {name} is declared as an input")
if set(inputs) != INPUTS:
    fail(f"the inputs are {sorted(inputs)}, expected {sorted(INPUTS)}")
for name, spec in inputs.items():
    if spec.get("type") != "string" or spec.get("required") is not True:
        fail(f"the input {name} is not a required string")
if set(secrets) != SECRETS:
    fail(f"the secrets are {sorted(secrets)}, expected {sorted(SECRETS)}")
for name, spec in secrets.items():
    if not isinstance(spec, dict) or spec.get("required") is not True:
        fail(f"the secret {name} is not required")
if doc.get("permissions") != PERMISSIONS:
    fail("the top-level permissions are not exactly contents: read, id-token: write")

# 4. `secrets` read only as one of the four names; `secrets` as a key only in
#    on.workflow_call; no identifier read from inputs.
SECRET_REF = re.compile(r"\bsecrets\b(\.([A-Za-z0-9_-]+))?")


def walk(node, where):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "secrets" and where != "on.workflow_call":
                fail(f"a 'secrets' key at {where}")
            walk(value, f"{where}.{key}" if where else str(key if key is not True else "on"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk(value, f"{where}[{index}]")
    elif isinstance(node, str):
        for match in SECRET_REF.finditer(node):
            if match.group(2) not in SECRETS:
                fail(f"secrets read other than by one of the four names at {where}: {match.group(0)}")
        for name in SECRETS:
            if f"inputs.{name}" in node:
                fail(f"the identifier {name} is read from inputs at {where}")


walk(doc, "")

# 5. One job.
jobs = doc.get("jobs")
if not isinstance(jobs, dict) or len(jobs) != 1:
    fail("expected exactly one job")
    finish()
job = next(iter(jobs.values()))
if not isinstance(job, dict):
    fail("the job is not a mapping")
    finish()
JOB_KEYS = {"runs-on", "timeout-minutes", "permissions", "concurrency", "steps"}
if set(job) != JOB_KEYS:
    fail(f"the job's keys are {sorted(job)}, expected {sorted(JOB_KEYS)}")
if job.get("permissions") != PERMISSIONS:
    fail("the job's permissions are not exactly contents: read, id-token: write")
if job.get("concurrency") != {"group": "deploy-${{ inputs.service }}", "cancel-in-progress": False}:
    fail("the job's concurrency is not deploy-<service>, never cancelled")

# 6. Steps.
EXPECTED_USES = [
    None,
    "actions/checkout",
    "google-github-actions/auth",
    "docker/login-action",
    "docker/setup-buildx-action",
    "docker/build-push-action",
    "google-github-actions/setup-gcloud",
    None,
]
STEP_KEYS = {"name", "id", "uses", "with", "env", "run"}
steps = job.get("steps")
if not isinstance(steps, list) or len(steps) != len(EXPECTED_USES):
    fail(f"expected exactly {len(EXPECTED_USES)} steps")
    finish()
for index, (step, expected) in enumerate(zip(steps, EXPECTED_USES)):
    if not isinstance(step, dict):
        fail(f"step {index + 1} is not a mapping")
        continue
    extra = set(step) - STEP_KEYS
    if extra:
        fail(f"step {index + 1} has forbidden keys {sorted(extra)}")
    uses = step.get("uses")
    if expected is None:
        if uses is not None or "run" not in step:
            fail(f"step {index + 1} must be a script, not an action")
    elif not isinstance(uses, str) or not re.fullmatch(re.escape(expected) + r"@[0-9a-f]{40}", uses):
        fail(f"step {index + 1} must be {expected} pinned by a 40-character commit SHA, found {uses!r}")

# Every `uses` line of the text carries a version comment (block style only:
# a flow-style step already fails above).
for line in text.splitlines():
    if re.match(r"^\s*(-\s+)?uses:", line) and not re.search(r"@[0-9a-f]{40} # v\d", line):
        fail(f"a 'uses' line without its pin and version comment: {line.strip()}")


def false(value):
    return str(value).lower() == "false"


buildx, build = steps[4], steps[5]
if not false((buildx.get("with") or {}).get("cache-binary")):
    fail("setup-buildx-action must have cache-binary: false")
build_env = build.get("env") or {}
for name in ["DOCKER_BUILD_SUMMARY", "DOCKER_BUILD_RECORD_UPLOAD", "DOCKER_BUILD_CHECKS_ANNOTATIONS"]:
    if not false(build_env.get(name)):
        fail(f"the build step must set {name}: false")
build_with = build.get("with") or {}
if build.get("id") != "build" or build_with.get("push") is not True:
    fail("the build step must have id 'build' and push: true")
if build_with.get("context") != "${{ inputs.working-directory }}":
    fail("the build context must be the working directory")
if build_with.get("tags") != "${{ secrets.image-path }}/${{ inputs.image-name }}:${{ github.sha }}":
    fail("the build must tag <image-path>/<image-name>:<commit SHA>")
if (steps[1].get("with") or {}).get("persist-credentials") is not False:
    fail("checkout must have persist-credentials: false")

# Every action step's `id`, `with` and `env` exactly as reviewed: no other key,
# no other expression (the login's registry and password, auth's identity,
# the build's context and tags all hold or reach the credential).
ACTION_STEPS = {
    1: (None, {"persist-credentials": False}, None),
    2: ("auth", {
        "token_format": "access_token",
        "workload_identity_provider": "${{ secrets.workload-identity-provider }}",
        "service_account": "${{ secrets.service-account }}",
    }, None),
    3: (None, {
        "registry": "${{ inputs.region }}-docker.pkg.dev",
        "username": "oauth2accesstoken",
        "password": "${{ steps.auth.outputs.access_token }}",
    }, None),
    4: (None, {"cache-binary": False}, None),
    5: ("build", {
        "context": "${{ inputs.working-directory }}",
        "push": True,
        "provenance": False,
        "sbom": False,
        "tags": "${{ secrets.image-path }}/${{ inputs.image-name }}:${{ github.sha }}",
    }, {
        "DOCKER_BUILD_SUMMARY": False,
        "DOCKER_BUILD_RECORD_UPLOAD": False,
        "DOCKER_BUILD_CHECKS_ANNOTATIONS": False,
    }),
    6: (None, None, None),
}
for index, (step_id, step_with, step_env) in ACTION_STEPS.items():
    step = steps[index]
    label = f"step {index + 1} ({EXPECTED_USES[index]})"
    if step.get("id") != step_id:
        fail(f"{label}: id is {step.get('id')!r}, expected {step_id!r}")
    if step.get("with") != step_with:
        fail(f"{label}: 'with' is not exactly the reviewed one")
    if step.get("env") != step_env:
        fail(f"{label}: 'env' is not exactly the reviewed one")

# 7. Scripts.
scripts = [step["run"] for step in steps if isinstance(step, dict) and isinstance(step.get("run"), str)]
gcloud_count = 0
for script in scripts:
    if "${{" in script:
        fail("an expression inside a run script")
    if re.search(r"\\\s*$", script, re.MULTILINE):
        fail("a line continuation inside a run script")
    if re.search(r"::add-mask::(?!\$\{?[A-Za-z_])", script):
        fail("an add-mask with no value")
    gcloud_count += len(re.findall(r"\bgcloud\b", script))
if gcloud_count != 1:
    fail(f"the run scripts invoke gcloud {gcloud_count} times, expected once")

UPDATE = 'gcloud run services update "$SERVICE" --project="$PROJECT" --region="$REGION" --image="$IMAGE@$DIGEST" --quiet'
DIGEST_TEST = 'if [[ ! "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then'

MASK_ENV = {
    "PROJECT_ID": "${{ secrets.project-id }}",
    "SERVICE_ACCOUNT": "${{ secrets.service-account }}",
    "WIF_PROVIDER": "${{ secrets.workload-identity-provider }}",
    "IMAGE_PATH": "${{ secrets.image-path }}",
    "WORKING_DIRECTORY": "${{ inputs.working-directory }}",
    "SERVICE": "${{ inputs.service }}",
    "REGION": "${{ inputs.region }}",
    "IMAGE_NAME": "${{ inputs.image-name }}",
}
MASK_RUN = r'''if [ -z "$PROJECT_ID" ] || [ -z "$SERVICE_ACCOUNT" ] || [ -z "$WIF_PROVIDER" ] || [ -z "$IMAGE_PATH" ]; then
  echo "::error::An identifier is empty."
  exit 1
fi
echo "::add-mask::$PROJECT_ID"
echo "::add-mask::$SERVICE_ACCOUNT"
echo "::add-mask::$WIF_PROVIDER"
echo "::add-mask::$IMAGE_PATH"
project_number="${WIF_PROVIDER#projects/}"
project_number="${project_number%%/*}"
if [[ "$WIF_PROVIDER" != projects/* ]] || [[ ! "$project_number" =~ ^[0-9]+$ ]]; then
  echo "::error::The workload identity provider is not a path that starts with projects/<number>/."
  exit 1
fi
echo "::add-mask::$project_number"
if [[ ! "$WORKING_DIRECTORY" =~ ^[A-Za-z0-9_-][A-Za-z0-9._/-]*$ ]] || [[ "/$WORKING_DIRECTORY/" == */../* ]]; then
  echo "::error::The input working-directory is not a folder inside the repository."
  exit 1
fi
if [[ ! "$SERVICE" =~ ^[a-z][a-z0-9-]{0,48}$ ]]; then
  echo "::error::The input service is not a valid name."
  exit 1
fi
if [[ ! "$IMAGE_NAME" =~ ^[a-z][a-z0-9-]{0,48}$ ]]; then
  echo "::error::The input image-name is not a valid name."
  exit 1
fi
if [[ ! "$REGION" =~ ^[a-z]+-[a-z]+[0-9]{1,2}$ ]]; then
  echo "::error::The input region is not a valid region."
  exit 1
fi
'''
DEPLOY_ENV = {
    "SERVICE": "${{ inputs.service }}",
    "PROJECT": "${{ secrets.project-id }}",
    "REGION": "${{ inputs.region }}",
    "IMAGE": "${{ secrets.image-path }}/${{ inputs.image-name }}",
    "DIGEST": "${{ steps.build.outputs.digest }}",
}
DEPLOY_RUN = DIGEST_TEST + '''
  echo "::error::The build returned no sha256 digest."
  exit 1
fi
''' + UPDATE + "\n"

first, last = steps[0], steps[-1]
if first.get("env") != MASK_ENV:
    fail("the first step's env is not the four secrets and four inputs")
if first.get("run") != MASK_RUN:
    fail("the first step's script is not the reviewed masking and validation script")
if last.get("env") != DEPLOY_ENV:
    fail("the update step's env is not the reviewed one")
deploy_lines = [l.strip() for l in str(last.get("run", "")).splitlines() if l.strip() and not l.strip().startswith("#")]
if not deploy_lines or deploy_lines[-1] != UPDATE:
    fail("the update by digest is not the last command of the last step")
if DIGEST_TEST not in deploy_lines or (UPDATE in deploy_lines and deploy_lines.index(DIGEST_TEST) > deploy_lines.index(UPDATE)):
    fail("the digest test does not precede the update in the same script")
if last.get("run") != DEPLOY_RUN:
    fail("the update step's script is not the reviewed script")

finish()
PY

---
description: Google Cloud (GCP) login describe. Use to learn whether the login of the organization is prepared - whether the organization's Identity-Aware Proxy (IAP) setting names a custom OAuth client, which the services of a standalone organization owned by a personal Google account need to let anyone in. Read-only; the platform's plan calls it.
---

# gcp_login-describe

Reads the organization's IAP setting and says whether the login is prepared: the setting names an OAuth client. A service behind IAP inherits that client; without it, Google's managed client refuses a personal Google account. It never creates, changes or deletes anything and has no `mode`. The client's secret is never read: the setting shows only the client's id and a hash of the secret, and the answer repeats neither.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | Optional. The shared platform project: the read is counted against it (`--billing-project`), so that its IAP API, which `gcp_login-setup` enables, is the one used. The platform's plan passes it. Without it, the read is counted against the terminal's current project. |

Validate before any command, and never ask for anything. When `projectId` is given and does not match `^[a-z][a-z0-9-]{4,28}[a-z0-9]$` (6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter, not ending with `-`), end with the result block, `status` `failed`, the one sentence `projectId is not a valid GCP project id.` and no `gcloud` call. Any other argument is ignored.

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone (its exit code and its text decide the next step). On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Organization:

   ```
   gcloud organizations list --format="value(name)"
   ```

   `gcloud` returns the name as `organizations/<id>`; `<organizationId>` is the bare id, the part after the slash.

   - Exit 0 and one line: that is the organization; `organization` is true. Go to step 2.
   - A non-zero exit, or empty output: say exactly `No organization was found. Check that the active gcloud account is signed in and belongs to an organization.` Run nothing else and end with `status` `failed`, `organization` false.
   - More than one line: say exactly `<n> organizations were found and none was picked.`, with `<n>` the number of lines and no identifier. Do not pick one. Run nothing else and end with `status` `failed`, `organization` false.

2. The organization's IAP setting:

   ```
   gcloud iap settings get --organization=<organizationId> --format=json
   ```

   With `projectId`, the same command with `--billing-project=<projectId>`, and nothing else changed:

   ```
   gcloud iap settings get --organization=<organizationId> --billing-project=<projectId> --format=json
   ```

   - Exit 0: read the JSON. `prepared` is true when `accessSettings.oauthSettings.clientId` is a non-empty string, and false otherwise: an object with only `name`, an empty object, an empty output, settings without `accessSettings`, without `oauthSettings` or without `clientId` (for example only `loginHint`, or only `reauthSettings`) are all "not prepared", a normal answer, not a failure.
   - A non-zero exit whose text contains `NOT_FOUND`: the organization has no setting stored. `prepared` is false, a normal answer, not a failure.
   - A non-zero exit whose text contains `PERMISSION_DENIED` (which `IAM_PERMISSION_DENIED` also contains) and does not contain `SERVICE_DISABLED`: the active account may not read the setting yet. On an organization whose login was never prepared that is the expected answer, because the role that reads it, `roles/iap.settingsAdmin`, is granted by `gcp_login-setup`. It is not a failure: `prepared` is false and `readable` is false. Say exactly `The login of the organization could not be read yet; /aleogr:platform-apply prepares it.` Never explain which text decided this, and repeat no word of `gcloud`'s answer. End with `status` `unchanged`.
   - Any other non-zero exit (an API not enabled, which the text `SERVICE_DISABLED` marks, `gcloud` not signed in, a network error, anything else) is a failure of the read, never "not prepared". Say exactly `The organization's login setting could not be read. Check that the active gcloud account is signed in and may read the organization's IAP settings.` Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only the sentence above about the failure. End with `status` `failed`, `organization` true, `prepared` `null`.

   A refusal is decided by the exit code together with the text: a text without a non-zero exit is never a refusal.

Then answer in a few lines: whether the login of the organization is prepared, or could not be read yet (when it is not prepared, that `/aleogr:platform-apply` prepares it), and the result block. The answer prints no organization id, no client id and no hash of a secret: not in the prose and not in the result block.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "login-describe",
  "mode": "plan",
  "status": "unchanged",
  "resources": [],
  "outputs": {
    "prepared": true,
    "readable": true,
    "organization": true
  },
  "cost": { "fixed": false, "notes": "read-only" },
  "pending": []
}
```

- `mode` is always `plan`: the skill only reads. `resources` is always empty.
- `status` is `unchanged` whenever the setting was read, prepared or not (`NOT_FOUND` included), and when the read was refused for lack of permission (`prepared` false, `readable` false). It is `failed` when `projectId` is invalid or no single organization was found (`prepared` `null`, `readable` `null`, `organization` false) or the read failed for any other reason (`prepared` `null`, `readable` `null`, `organization` true).
- `readable` is false only when the read was refused for lack of permission, `null` on `failed`, and true in every other case.
- `pending` is always empty.

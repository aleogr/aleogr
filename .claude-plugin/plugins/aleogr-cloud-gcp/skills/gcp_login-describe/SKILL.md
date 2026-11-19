---
description: Google Cloud (GCP) login describe. Use to learn whether the login of the organization is prepared - whether the organization's Identity-Aware Proxy (IAP) setting names a custom OAuth client, which the services of a standalone organization owned by a personal Google account need to let anyone in. Read-only; the platform's plan calls it.
---

# gcp_login-describe

Reads the organization's IAP setting and says whether the login is prepared: the setting names an OAuth client. A service behind IAP inherits that client; without it, Google's managed client refuses a personal Google account. It never creates, changes or deletes anything, takes no argument and has no `mode`. The client's secret is never read: the setting shows only the client's id and a hash of the secret, and the answer repeats neither.

## Arguments

None. Anything after the skill name is ignored.

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

   - Exit 0: read the JSON. `prepared` is true when `accessSettings.oauthSettings.clientId` is a non-empty string, and false otherwise: an object with only `name`, an empty object, an empty output, settings without `accessSettings`, without `oauthSettings` or without `clientId` (for example only `loginHint`, or only `reauthSettings`) are all "not prepared", a normal answer, not a failure.
   - A non-zero exit whose text contains `NOT_FOUND`: the organization has no setting stored. `prepared` is false, a normal answer, not a failure.
   - Any other non-zero exit (permission denied, an API not enabled, `gcloud` not signed in, a network error, anything else) is a failure of the read, never "not prepared". Say exactly `The organization's login setting could not be read. Check that the active gcloud account is signed in and may read the organization's IAP settings.` Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only the sentence above about the failure. End with `status` `failed`, `organization` true, `prepared` `null`.

Then answer in a few lines: whether the login of the organization is prepared (when it is not, that `gcp_login-setup` prepares it), and the result block. The answer prints no organization id, no client id and no hash of a secret: not in the prose and not in the result block.

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
    "organization": true
  },
  "cost": { "fixed": false, "notes": "read-only" },
  "pending": []
}
```

- `mode` is always `plan`: the skill only reads. `resources` is always empty.
- `status` is `unchanged` whenever the setting was read, prepared or not (`NOT_FOUND` included). It is `failed` when no single organization was found (`prepared` `null`, `organization` false) or the read failed (`prepared` `null`, `organization` true).
- `pending` is always empty.

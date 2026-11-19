---
description: Google Cloud (GCP) login setup. Use to prepare the login of the organization - the custom OAuth client that the organization's Identity-Aware Proxy (IAP) setting names, so that a personal Google account can get into the services. Does what a command can do (grants the active account the role that changes the organization's IAP setting, enables the IAP API in the shared project) and prints the short list of what is left to the owner - the consent screen and the client in the console, and one command to paste in a terminal. Never sees the client's secret. Idempotent; plan by default.
---

# gcp_login-setup

Prepares the login of the organization as far as a command can. Google has no command that creates a consent screen or an OAuth client, so those are a few clicks in the console; this skill does everything else: it grants the active `gcloud` account `roles/iap.settingsAdmin` on the organization when it lacks it, enables `iap.googleapis.com` in the shared project when it is off, and prints the list of what is left. It has no cost.

The client's secret never passes through this skill. The skill prints the one command that takes the secret as text for the owner to paste in a terminal; it never runs that command, never fills a value into it, never asks for the client id or the secret, and never reads a file that could hold them.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | Required. The shared platform project, which holds the consent screen and the client. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check the arguments. A missing `projectId` ends the skill with the result block, `status` `failed`, the one sentence `projectId is missing.` and no `gcloud` call; an invalid value ends it the same way, with one sentence saying which argument is wrong. Never ask for anything.

- `projectId` matches `^[a-z][a-z0-9-]{4,28}[a-z0-9]$` (6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter, not ending with `-`).
- `mode` is `plan` or `apply`.

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone (its exit code and its text decide the next step). On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. Every sentence of failure below is said exactly as written: never explain which text decided it, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons).

1. Organization (both modes):

   ```
   gcloud organizations list --format="value(name)"
   ```

   `gcloud` returns the name as `organizations/<id>`; `<organizationId>` is the bare id, the part after the slash.

   - Exit 0 and one line: go on.
   - A non-zero exit, or empty output: say `No organization was found. Check that the active gcloud account is signed in and belongs to an organization.` and end with `failed`.
   - More than one line: say `<n> organizations were found and none was picked.`, with no identifier, and end with `failed`. Do not pick one.

2. Is the login prepared (both modes):

   ```
   gcloud iap settings get --organization=<organizationId> --format=json
   ```

   - Exit 0 and `accessSettings.oauthSettings.clientId` is a non-empty string: the login is prepared. Run nothing else, print no list, and end with `unchanged`.
   - Exit 0 with anything else (an object with only `name`, an empty object or output, settings without a client), or a non-zero exit whose text contains `NOT_FOUND`: not prepared. Go on.
   - Any other non-zero exit: say `The organization's login setting could not be read. Check that the active gcloud account is signed in and may read the organization's IAP settings.` and end with `failed`.

3. The active account (both modes):

   ```
   gcloud config get-value account
   ```

   A non-zero exit, or empty output: say `The active gcloud account could not be read. Run gcloud auth login.` and end with `failed`. Otherwise `<member>` is `serviceAccount:<account>` when the account ends with `.gserviceaccount.com`, and `user:<account>` otherwise.

4. Does the account have the role (both modes):

   ```
   gcloud organizations get-iam-policy <organizationId> --flatten="bindings[].members" --filter="bindings.role=roles/iap.settingsAdmin AND bindings.members=<member>" --format="value(bindings.members)"
   ```

   - Exit 0 and a line equal to `<member>`: the role is present.
   - Exit 0 and no such line: the role is missing.
   - A non-zero exit: say `The organization's access could not be read. Check that the active gcloud account may read the organization's access.` and end with `failed`.

5. Is the IAP API on (both modes):

   ```
   gcloud services list --enabled --project=<projectId> --filter="config.name=iap.googleapis.com" --format="value(config.name)"
   ```

   - Exit 0 and a line `iap.googleapis.com`: the API is on.
   - Exit 0 and no such line: the API is off.
   - A non-zero exit: say `The APIs of the GCP project <projectId> could not be read. Check that the project exists and that the active gcloud account may read it.` and end with `failed`.

6. `plan` ends here, changing nothing: say whether the role and the API are present, print the list of what is left (below), and end with `would-update` when the role or the API is missing, or `pending` when both are present (only the clicks are left).

7. `apply`: run the command of each part that is missing, in this order; a part that is present is skipped.

   ```
   gcloud organizations add-iam-policy-binding <organizationId> --member="<member>" --role="roles/iap.settingsAdmin" --condition=None --quiet
   gcloud services enable iap.googleapis.com --project=<projectId>
   ```

   - The role is granted with `--condition=None`, to the active account only, on the organization only. Never run `gcloud iap settings set`, and never remove a binding.
   - A non-zero exit of the grant: say `The role that changes the organization's login could not be granted; nothing was changed. The active gcloud account must be an administrator of the organization.` and end with `failed`; the API is not enabled then.
   - A non-zero exit of the enable when the grant did not run: say `The IAP API could not be enabled in <projectId>; nothing was changed.` and end with `failed`.
   - A non-zero exit of the enable after this run granted the role: say `The IAP API could not be enabled in <projectId>.`, end with `updated`, and add to `pending`, before the item `login`, the item `{ "item": "api", "reason": "The IAP API could not be enabled.", "how": "gcloud services enable iap.googleapis.com --project=<projectId>" }`.

   Then print the list of what is left, and end with `updated` when something was granted or enabled, or `pending` when both were already present (nothing was changed; only the clicks are left).

## The list of what is left

Whenever the login is not prepared (every status but `unchanged` and `failed`), print these lines for the owner, as written, with `<projectId>` filled in and nothing else filled in. `<client id>` stays as written: the owner builds that address from the id the console shows.

```
1. Consent screen: open https://console.cloud.google.com/auth/branding?project=<projectId> and create it with app name aleogr, your own e-mail as the support and contact e-mail, and audience External. Add no logo and publish nothing.
2. Client: open https://console.cloud.google.com/auth/clients?project=<projectId> and create a client of type Web application named iap. Then add to it the authorized redirect URI https://iap.googleapis.com/v1/oauth/clientIds/<client id>:handleRedirect, with the client id the console shows in place of <client id>.
3. Paste this command in a terminal. It asks for the client id and, without showing it, the client secret, and sets the login on the organization:
read -p "Client id: " CID; read -s -p "Client secret: " CSEC; echo; O=$(gcloud organizations list --format="value(name)" | sed 's#.*/##'); F=$(mktemp); printf 'accessSettings:\n  oauthSettings:\n    clientId: %s\n    clientSecret: %s\n' "$CID" "$CSEC" > "$F"; gcloud iap settings set "$F" --organization="$O"; rm -f "$F"; unset CSEC
4. Run /aleogr:platform-apply again; it confirms the login.
```

Print the command of item 3 byte for byte as above, on a line of its own, in a fenced `bash` block that starts at the beginning of the line: no value filled in, no character changed, added or removed. It is text for the owner, never a command of this skill: do not run it.

Then answer in a few lines: whether the login is prepared, whether the role and the API were present, granted or enabled, the list when it applies, and the result block. The answer prints no organization id and no e-mail outside the commands shown before running them.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "login-setup",
  "mode": "apply",
  "status": "updated",
  "resources": [],
  "outputs": {
    "prepared": false,
    "roleGranted": true,
    "apiEnabled": true,
    "steps": [
      "1. Consent screen: open https://console.cloud.google.com/auth/branding?project=<projectId> and ...",
      "2. Client: open https://console.cloud.google.com/auth/clients?project=<projectId> and ...",
      "3. Paste this command in a terminal. ...",
      "<the command of item 3, unfilled>",
      "4. Run /aleogr:platform-apply again; it confirms the login."
    ]
  },
  "cost": { "fixed": false, "notes": "the role and the API are free" },
  "pending": [
    { "item": "login", "reason": "manual", "how": "In the Google Cloud console of <projectId>, create the consent screen aleogr (External) and the web application client iap with its redirect address, paste the printed command in a terminal, then run /aleogr:platform-apply" }
  ]
}
```

- `mode` echoes the mode used. `status` is one of `unchanged` (already prepared: nothing done, no list), `would-update` (plan: the role or the API is missing), `updated` (this run granted the role or enabled the API), `pending` (the role and the API were already present and only the clicks are left: nothing was changed), `failed`.
- `outputs.prepared` is whether the organization's setting names a client (`null` when it was not read). `outputs.roleGranted` is true when this run granted the role (in `plan`: would grant it), false otherwise. `outputs.apiEnabled` is true when this run enabled the API (in `plan`: would enable it), false otherwise.
- `outputs.steps` holds the lines of the list, one string per line, in order, with `<projectId>` filled in, the command of item 3 as its own line, unfilled, and `<client id>` as written; `[]` when the status is `unchanged` or `failed`.
- `pending` holds, whenever the login is not prepared and the status is not `failed`, the one item `login` above, with `<projectId>` filled in (after the item `api`, when there is one). It is empty otherwise.
- `failed`: `resources` is empty, `outputs` is `{ "prepared": <as read, or null>, "roleGranted": false, "apiEnabled": false, "steps": [] }`, and `pending` is empty.
- The result block holds no organization id, no e-mail and no client id.

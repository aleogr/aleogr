---
description: Google Cloud (GCP) access grant. Use to let one person in, through the login (IAP), to the Cloud Run services of an aleogr project's components in the GCP project of an environment - by granting that person's e-mail, as `user:<e-mail>` only, the role that passes the login on each service, never on the project - or to list how many people each service lets in. Never grants a group, a domain, a service account or everyone, and removes nothing. Idempotent; plan by default. No cost.
---

# gcp_access-grant

Lets one person in to each component's Cloud Run service `<project>-<component>` through the login (IAP): it grants `user:<person>` the role `roles/iap.httpsResourceAccessor` on the login policy of each service, never on the GCP project, and reads each policy before and after. A service that already lets the person in is left alone. With `list=yes` instead of `person`, it only reads, and says who each service lets in.

The member is always `user:<person>`: never a group, a domain, a service account, `allUsers` or `allAuthenticatedUsers`. Nothing is ever removed here: the answer of `list=yes` gives the one command that removes a person. It never creates a service: create it first with `gcp_deploy-setup`. There is no cost: letting a person through the login costs nothing.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`; exactly one of `person` and `list` is given.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project of the project and environment (from `gcp_environment-describe`). |
| `project=<name>` | The aleogr project name. |
| `region=<region>` | The region of the services, for example `us-central1`. |
| `components=<name>[,<name>…]` | The components, in the declaration's order; each runs as the service `<project>-<name>`. |
| `person=<e-mail>` | The e-mail address of the one person to let in. |
| `list=yes` | In place of `person`: only read, and say how many people, and who, each service lets in. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. With `list=yes` nothing is changed in either mode. |

## Validate first

Before any command, check every argument, and never ask for anything. Each argument that is missing or breaks its rule gives its one sentence below, one per line; when there is at least one, the skill ends with the result block, `status` `failed`, those sentences and no `gcloud` call.

- A missing required argument: `<argument> is missing.` When neither `person` nor `list` is given: `person is missing (or give list=yes).` When both are given: `Give either person or list=yes, not both.`
- `projectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `projectId is not a GCP project id.`
- `project` has 1 to 14 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `project must have 1 to 14 lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen.`
- `region` is a Google Cloud region name: lowercase letters, then one or more `-<letters>` parts, then digits (`us-central1`, `southamerica-east1`). Otherwise: `region is not a Google Cloud region name (such as us-central1).`
- `components` holds one or more names separated by `,`, with no space and no empty name. Each name has 1 to 20 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise, for each name that breaks it: `component <name> must have 1 to 20 lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen.` A name given twice: `component <name> is given twice.`
- For each component, `<project>-<name>` has 6 to 30 characters. Otherwise: `<project>-<name> has <n> characters: a service's name must have 6 to 30.`
- `person` is the e-mail address of one person, and all of these hold:
  - it has exactly one `@`, with 1 to 64 characters before it of `A-Z`, `a-z`, `0-9`, `.`, `_`, `%`, `+` and `-`;
  - after the `@` comes a domain: two or more parts separated by `.`, each of 1 to 63 characters of `A-Z`, `a-z`, `0-9` and `-`, not starting or ending with `-`, the last of letters only;
  - it has no space, no `:` (so no `user:`, `group:`, `serviceAccount:`, `domain:` or any other prefix), no `,`, no quote;
  - it is not `allUsers` or `allAuthenticatedUsers`, and its domain does not end with `gserviceaccount.com` (a service account is not a person).

  Otherwise: `person must be the e-mail address of one person (such as name@example.com): not a group, a domain, a service account or everyone.` An address that passes these rules is still only ever the member `user:<person>`, which names one account.
- `list` is `yes`. Otherwise: `list must be yes.`
- `mode` is `plan` or `apply`. Otherwise: `mode must be plan or apply.`

## Names

For each component `<name>`:

- `<service>` is `<project>-<name>`.
- `<member>` is `user:<person>`, always with this prefix. It is used only as the `--member` of the command of step 4: it is never written in a label, a file or the result block.
- `has` is true when a binding of the service's login policy whose `role` is exactly `roles/iap.httpsResourceAccessor` and that has no `condition` lists `<member>` in its `members` (compared without regard to case); otherwise false (also when the policy has no `bindings`). A binding of another role does not count.
- `people` is the number of distinct members of every binding of `roles/iap.httpsResourceAccessor` in the service's login policy, whatever their kind (`0` when there is none).

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. A value written in double quotes below keeps its quotes. The text of a non-zero exit is read to decide and is never quoted: never explain which text decided, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons). Each failure is said with its sentence below and nothing else about it.

1. Read each service, in the order of `components`, each command alone (both modes):

   ```
   gcloud run services describe <service> --project=<projectId> --region=<region> --format="value(metadata.name)"
   ```

   - Exit 0: the service exists.
   - A non-zero exit whose text contains `Cannot find service`, `NOT_FOUND` or `could not be found`: the service does not exist. Say `The service of the component <name> (<service>) does not exist in <region>: create it first with gcp_deploy-setup.` for each such component, change nothing, run nothing else and end with `failed`.
   - Any other non-zero exit: say `The service <service> or its access could not be read; nothing was changed. Check that the Cloud Run and IAP APIs are enabled in <projectId> and that the active gcloud account may read its services and their access.` and end with `failed`. Never treat it as missing.

2. Read each service's login policy, in the order of `components`, each command alone (both modes):

   ```
   gcloud iap web get-iam-policy --resource-type=cloud-run --service=<service> --region=<region> --project=<projectId> --format=json
   ```

   Exit 0: decide `has` (with `person`) or `people` (with `list=yes`) as "Names" says. Any non-zero exit: the sentence of the read failure of step 1, and end with `failed`.

3. `list=yes` ends here, in both modes, changing nothing, with `status` `unchanged`. `plan` with `person` ends here too, changing nothing: `would-update` when some service does not let the person in, `unchanged` when every one does.

4. `apply` with `person`: for each component whose `has` is false, in the order of `components`, grant the role on its service's login policy:

   ```
   gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=<service> --region=<region> --project=<projectId> --member="user:<person>" --role="roles/iap.httpsResourceAccessor" --condition=None --quiet
   ```

   - Only on the service's login policy: never run `gcloud projects add-iam-policy-binding`, `gcloud run services add-iam-policy-binding` or any `set-iam-policy`, and never pass a member other than `user:<person>`.
   - There is no wait and no retry. A non-zero exit stops the work at once, with the sentence `The person could not be let in to the service <service> through the login. Check that the active gcloud account may change who gets in to the project's services.` No later command of 4.
   - A stop at the first command of 4: nothing was changed; end with `failed`. A stop after a grant made by this run: what was made stays (nothing is removed); go on with 5, and each component not granted gets a `pending` item.

5. Read back, with the command of step 2, alone, each service on which step 4 ran its command successfully. `has` must now be true. A read that fails, or `has` still false, gives a `pending` item for that component, and the answer says what could not be confirmed.

   Each `pending` item is `{ "item": "<name>: access", "reason": "<one sentence, no raw error text>", "how": "/aleogr-cloud-gcp:gcp_access-grant projectId=<projectId> project=<project> region=<region> components=<name> person=<e-mail> mode=apply" }`, where `person=<e-mail>` is written exactly so, as a placeholder, never with the address.

6. Status of `apply`: `updated` (this run granted at least one service, even when `pending` has items), `unchanged` (every service already let the person in), `failed` (validation, a read of steps 1 and 2, or a stop at the first command of 4).

Then answer in a few lines, and the result block:

- With `person`: for each component, whether the person already had access, was let in by this run, or would be (plan); the sentence of each failure; and that the person opens each service's address and signs in with that Google account. The answer may name the person (the owner gave the address), but no other member of a policy.
- With `list=yes`: for each component, how many people its service lets in and, in the text of the answer only, who (each member as the policy lists it). Then the one command that removes a person, for the owner to run by hand:

  ```
  gcloud iap web remove-iam-policy-binding --resource-type=cloud-run --service=<service> --region=<region> --project=<projectId> --member="user:<e-mail>" --role="roles/iap.httpsResourceAccessor" --condition=None
  ```

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "access-grant",
  "mode": "apply",
  "status": "updated",
  "resources": [
    { "type": "run-service", "id": "<projectId>/<region>/<project>-web", "name": "<project>-web" },
    { "type": "run-service", "id": "<projectId>/<region>/<project>-api", "name": "<project>-api" }
  ],
  "outputs": {
    "granted": ["web"],
    "already": ["api"],
    "people": null
  },
  "cost": { "fixed": false, "notes": "letting a person through the login has no cost" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-update` (plan), `updated`, `unchanged`, `failed`.
- `outputs.granted` names the components whose service this run let the person in to (in `apply`), or would (in `plan`); `outputs.already` names those whose service already let the person in, as of step 2. Both in the order of `components`, written on one line. Both are `[]` with `list=yes`.
- `outputs.people` is, with `list=yes`, a map of each component to its `people` count (`{ "web": 1, "api": 2 }`), and `null` with `person`. It holds numbers only.
- `resources` lists each service read as existing, as above.
- `failed` from validation or from steps 1 and 2: `resources` is empty and `outputs` is `{ "granted": [], "already": [], "people": null }`. `failed` from step 4: `resources` lists the services, `granted` is `[]`, `already` is as read.
- `pending` holds the items of steps 4 and 5; it is empty otherwise.
- The result block holds no e-mail at all: never `<person>`, `<member>` or any member of a policy, not even inside a `how`.

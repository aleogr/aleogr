---
description: aleogr project access. Use in a project's folder to let one person in, through the login of the organization, to the Cloud Run services of the project's components in each declared environment (person=<e-mail>), or to see how many people each service lets in (list=yes). Reads the declaration `.aleogr/project.json`, finds the GCP project of each environment and invokes gcp_access-grant. Grants only the role that passes the login, on each service, never on the project; never a group, a domain, a service account or everyone; removes nothing. No confirmation is needed: it costs nothing and one command undoes it.
---

# project-access

Lets one person in to the project's services. For each environment the declaration `.aleogr/project.json` (in the folder the skill runs in) declares, it finds the GCP project of that environment (`aleogr-cloud-gcp:gcp_environment-describe`) and invokes `aleogr-cloud-gcp:gcp_access-grant` with the declaration's components, which grants `user:<person>` the role that passes the login on each component's service, and never on the GCP project. With `list=yes` it only reads, and says how many people each service lets in.

No `confirm` is asked: letting a person through the login of a service costs nothing, exposes the service to that one person only, and is undone by one command, which the answer gives. The skill runs no `gh`, `git` or `gcloud` command itself, and it does not create a service: `/aleogr:project-apply confirm=yes` does.

## Arguments

Free text after the skill name, as `key=value` pairs. Exactly one of `person` and `list` is given.

| Argument | Meaning |
|---|---|
| `person=<e-mail>` | The e-mail address of the one person to let in: a person's Google account. |
| `list=yes` | In place of `person`: only read, and say how many people, and who, each service lets in. |

## Validate first

Before invoking anything, check the arguments, and never ask for anything. When one breaks a rule, end with its one sentence, written exactly as below as plain text (no backticks, no other formatting), then the result block, `status` `failed`, with no skill invoked and no file read.

- Neither `person` nor `list` given: `person is missing (or give list=yes).` Both given: `Give either person or list=yes, not both.` Any other argument: `<argument> is not an argument of project-access: give person=<e-mail> or list=yes.`
- `person` is the e-mail address of one person, and all of these hold:
  - it has exactly one `@`, with 1 to 64 characters before it of `A-Z`, `a-z`, `0-9`, `.`, `_`, `+` and `-`;
  - after the `@` comes a domain: two or more parts separated by `.`, each of 1 to 63 characters of `A-Z`, `a-z`, `0-9` and `-`, not starting or ending with `-`, the last of letters only;
  - it has no space, no `:` (so no `user:`, `group:`, `serviceAccount:`, `domain:` or any other prefix), no `,`, no quote;
  - it is not `allUsers` or `allAuthenticatedUsers`, and its domain does not end with `gserviceaccount.com` (a service account is not a person).

  Otherwise: `person must be the e-mail address of one person (such as name@example.com): not a group, a domain, a service account or everyone.` An address that passes these rules is still only ever the member `user:<person>`, which names one account.

  The address must be a person's Google account: a group's address is not supported and would let nobody in. The answer of a grant says this sentence too.
- `list` is `yes`. Otherwise: `list must be yes.`

The rule on `person` is the one of `gcp_access-grant`, word for word: this skill checks it first, so that a wrong address never reaches a cloud skill.

## Steps

Show each skill invocation before making it. The skills below end with their own `aleogr-result` block: use those blocks only as input, never repeat them, and after each one go on with the next step: a skill's block is never the end of this answer, which always ends with this skill's own block. Invoke only the skills these steps list, in this order, and run no command yourself (no `gh`, no `git`, no `gcloud`, no `ls`, no `cat`).

1. Read `.aleogr/project.json` in the current folder with the Read tool. It does not exist: `failed`, with the sentence `There is no .aleogr/project.json in this folder: declare the project first with /aleogr:project-declare.` It is not valid JSON: `failed`, one sentence saying so. It has no `environments`: `failed`, with the sentence `The declaration has no environment: there is no service to let anyone in to.` It has no `components` (absent or `[]`): `failed`, with the sentence `The declaration has no component: there is no service to let anyone in to.` Otherwise take `name` (`<project>`), `cloud.region` (`<region>`), the components' names sorted by `name`, joined by `,` (`<components>`), and the environments' names, sorted (only `dev` exists today). The declaration's other rules are the plan's: this skill reads only these keys.
2. For each environment, in order:

   ```
   aleogr-cloud-gcp:gcp_environment-describe project=<project> environment=<environment>
   ```

   - `failed`: stop with `failed` and the sentence `The GCP project of <environment> could not be read; nothing was changed. Run /aleogr:project-plan to see why.`
   - `outputs.exists` false: stop with `failed` and the sentence `The GCP project of <environment> does not exist yet: run /aleogr:project-apply confirm=yes first.`
   - Otherwise take its `outputs.projectId` (`<projectId>`) and go on at once with step 3 for this environment: your next output is that invocation; write nothing before it.
3. For the same environment:

   ```
   aleogr-cloud-gcp:gcp_access-grant projectId=<projectId> project=<project> region=<region> components=<components> person=<person> mode=apply
   ```

   with `list=yes` in place of `person=<person>` when `list=yes` was given (`gcp_access-grant` then only reads, in either mode). Read its block without writing it (its lines and its block are input only, never part of this answer), take its `status`, `outputs` and `pending`, and go on with the next environment (step 2), or, after the last one, with the answer: your next output is that invocation, or this skill's answer starting with its first line (`dev: updated`); write nothing before it, and never copy the block of `gcp_access-grant` or of `gcp_environment-describe`. A `failed` ending does not stop the other environments; it is that environment's status. When it failed because a component's service does not exist (its answer says to create it first), the answer says, for that environment, exactly `The service of <component> does not exist yet in <environment>: run /aleogr:project-apply confirm=yes first, then this skill again.` (one sentence per such component), and never the name of a nested skill as the thing to run.

## Answer

Whichever step led here, the last skill invoked is over: your next output is this skill's answer, with nothing before it, not that skill's lines or block. The answer contains exactly one fenced block, this skill's own, at its end.

The answer is short, in this order, and nothing else:

1. One line per environment: its name and the status of `gcp_access-grant` (`dev: updated`).
2. With `person`: for each component, whether the person already had access, was let in by this run, or could not be (from `granted`, `already` and `pending`); that the person opens each service's address and signs in with that Google account, with the line `The addresses are in the answer of /aleogr:project-plan.` (no read this skill makes gives them: `gcp_access-grant` reads only each service's name, and this skill makes no other read); and the sentence `The address must be a person's Google account: a group's address is not supported and would let nobody in.` The answer may name the person (the owner gave the address).
3. With `list=yes`: for each component, how many people its service lets in, and the members `gcp_access-grant` listed, as it listed them.
4. When `gcp_access-grant` reported a service open to anyone signed in to a Google account (its `outputs.open` is not empty): its warning, repeated in plain words, for each such service: anyone signed in to a Google account gets through the login of the service `<project>-<component>`; then the remove command it gave, exactly.
5. The command that undoes a grant, for the owner to run by hand (with `person`): `gcloud iap web remove-iam-policy-binding --resource-type=cloud-run --service=<project>-<component> --region=<region> --project=<projectId> --member="user:<e-mail>" --role="roles/iap.httpsResourceAccessor" --condition=None`, written with `<e-mail>` as it is here.
6. On `failed`: the sentence of the failure instead of 1 to 5 (for a missing service, the sentence of step 3).
7. The result block, the one block of the answer.

## Result block

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "project-access",
  "mode": "apply",
  "status": "updated",
  "resources": [],
  "outputs": {
    "project": "demo",
    "environments": [
      { "name": "dev", "status": "updated", "granted": ["api", "web"], "already": [], "people": null, "open": ["web"] }
    ]
  },
  "cost": { "fixed": false, "notes": "letting a person through the login has no cost" },
  "pending": []
}
```

Write each item of `outputs.environments` on one line, as in the example.

- `mode` is always `apply`.
- `status`: `failed` when an argument broke a rule, the declaration is missing or invalid or has no environment or no component, a GCP project could not be read or does not exist, or every `gcp_access-grant` ended `failed`; `updated` when some `gcp_access-grant` ended `updated`; `unchanged` otherwise (every service already let the person in, or `list=yes`).
- `outputs.project` is the declaration's `name` (`null` before it was read). `outputs.environments` has one item per environment for which `gcp_access-grant` was invoked, with its `status` and its `granted`, `already`, `people` and `open`, as it gave them; `[]` otherwise.
- `pending`: the items of each `gcp_access-grant`, as it gave them (their `how` names no e-mail); for each component whose service does not exist, `{ "item": "<component>: service", "reason": "manual", "how": "run /aleogr:project-apply confirm=yes first, then /aleogr:project-access again" }`; and, on `failed`, one item `{ "item": "<arguments, declaration or environment <name>>", "reason": "manual", "how": "<the fix, as in the sentence>" }`.
- `cost` is always `{ "fixed": false, "notes": "letting a person through the login has no cost" }`.
- The result block holds no e-mail at all: never the person's address, not even inside a `how`.

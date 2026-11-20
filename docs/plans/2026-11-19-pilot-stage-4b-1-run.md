# Reference project, stage 4b-1: checklist for the real run

For the owner, in Google Cloud Shell ([`cloud-shell.md`](../cloud-shell.md)). It proves three things: the platform's plan reads the login of the organization as `prepared`; a second Google account gets into a service after **one** command; and the spike of 2026-11-19 is removed, leaving `pilot` with `nothing to do`. Nothing here costs money, and nothing new is created in Google Cloud (step 2 may turn on the IAP API of the shared project, which is free).

Source of truth: [`2026-11-19-pilot-stage-4b-design.md`](2026-11-19-pilot-stage-4b-design.md) (part 4b-1) and [`DESIGN.md`](../DESIGN.md) sections 6.3, 6.8 and 10.4.

**Never paste in the conversation with Claude:** the login's client secret, a login code, what `gcloud auth list` or `gh auth status` print, the second account's e-mail, a service's address, or any id or number. In what you send back, write `<id>` in their place.

## What to have ready

- The pull request of stage 4b-1 is merged into `main` of `aleogr/aleogr`.
- `gcloud` and `gh` are signed in (in the terminal, `gcloud auth list` shows an active account and `gh auth status` a logged-in one; do not paste what they print).
- A **second Google account** (any Gmail account that is not yours), and a browser where you can open a private window (Chrome: Ctrl+Shift+N).
- Two values for the terminal commands of steps 3 and 4. Paste these two lines in the Cloud Shell terminal, outside Claude Code (the first prints nothing):

  ```bash
  P=$(gcloud projects list --filter="labels.aleogr-project=pilot AND labels.aleogr-environment=dev" --format="value(projectId)")
  gcloud run services list --project="$P"
  ```

  The second line lists `spike-iap` and `spike-iap2` with their `REGION` (expected `us-central1`). Then set it: `R=us-central1` (or the region it showed). If Cloud Shell reconnects, paste these lines again.

## Where you stop, and why

Claude Code runs none of steps 3 and 4: they are yours. Step 3 names a person's e-mail, which goes only in your terminal. Step 4 deletes, which cannot be undone. Everything else is one skill and its answer.

## 1. Update the plugins

In the terminal, outside Claude Code, one at a time:

```bash
claude plugin marketplace update aleogr
```

```bash
for p in aleogr aleogr-cloud-gcp aleogr-db-gcp-cloud-sql aleogr-registry-gcp-artifact-registry aleogr-repo-github aleogr-stack-go; do claude plugin update "$p@aleogr"; done
```

Expected: `claude plugin list` shows, all enabled: `aleogr` 0.10.2, `aleogr-cloud-gcp` 0.5.1, `aleogr-db-gcp-cloud-sql` 0.4.1, `aleogr-registry-gcp-artifact-registry` 0.1.2, `aleogr-repo-github` 0.5.2, `aleogr-stack-go` 0.1.1.

## 2. The platform's plan: the login is prepared

```bash
cd ~/aleogr && claude
```

```
/aleogr:platform-plan
```

Allow the `gcloud` reads it shows (`organizations list`, `iap settings get`, and the others); the read of `defaults.json` is **"Yes, but ask again next time"**.

Expected: the other rows as before (`shared project` `ready`, `services` `all enabled`, `budget alert` `exists`, `database switch` `ready`, `database instance` `exists, stopped`), and one of two answers. The setting the read shows holds the client's id: do not paste it.

- `status` `unchanged`, the line `nothing to do`, and the last row `login` `prepared` / `none`.
- Or the last row `login` `not prepared` / `prepare` (or `not checked` / `prepare`), status `would-update`. This is possible: the login was set by hand during the spikes, but the plan's read of it is counted against the shared project, whose IAP API may be off. When `login` is the only row with an action, run `/aleogr:platform-apply confirm=yes`: it turns the IAP API on (and grants your account the role `roles/iap.settingsAdmin` when it lacks it; both free), reads the login again, finds it, and ends with the row `login` `prepared` and the line `nothing to do`. There is nothing to click. If its answer has a `Login` section, or if another row also has an action, stop and send the answer.

`/exit` when done.

## 3. A second account gets in after one command

In the terminal, outside Claude Code.

1. The service's address:

   ```bash
   gcloud run services describe spike-iap2 --region="$R" --project="$P" --format='value(status.url)'
   ```

   Expected: one address ending in `.run.app`.
2. Open a **private window**, paste the address, and sign in with the **second account**. Expected: Google's sign-in, then a page "You don't have access". Note whether any other screen appeared first (a warning that the app is not verified, or a consent screen).
3. Let it in. Paste these two lines in the terminal, one at a time; the first asks for the second account's e-mail (type it there only, never in the chat):

   ```bash
   read -r -p "Second account's e-mail: " M
   ```

   ```bash
   gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=spike-iap2 --region="$R" --project="$P" --member="user:$M" --role=roles/iap.httpsResourceAccessor
   ```

   Expected: it prints the new policy (do not paste it).
4. Wait a minute, then reload the private window. Expected: the service's own page, with no warning screen. If it still says "You don't have access", wait two more minutes and reload once more.

## 4. Remove the spike

In the terminal. Each delete asks to confirm: answer `y`.

```bash
gcloud run services delete spike-iap --region="$R" --project="$P"
```

```bash
gcloud run services delete spike-iap2 --region="$R" --project="$P"
```

```bash
gcloud iam service-accounts delete "spike-iap@$P.iam.gserviceaccount.com" --project="$P"
```

Expected: each says it deleted. Then `gcloud run services list --project="$P"` lists nothing. The second account's access went with `spike-iap2`. The APIs the spike enabled stay: they cost nothing, and stage 4b-2 uses them.

The spike's OAuth client is removed in the console (no command exists for it):

1. Open `https://console.cloud.google.com/auth/clients?project=<project id of pilot>` (run `echo "$P"` in the terminal to see the id; type it in the address only).
2. Check the project picker at the top: it must show the project of `pilot` (`dev pilot`). **If it shows the shared project, stop**: the consent screen `aleogr` and the client `iap` there are the organization's login, and every service needs them. Never touch them.
3. Under **Google Auth Platform → Clients**, the project of `pilot` has the one client the spike made. Before deleting it, check that it is not the organization's login: in the terminal, run

   ```bash
   gcloud iap settings get --organization="$(gcloud organizations list --format="value(name)" | sed 's#.*/##')" --format="value(accessSettings.oauthSettings.clientId)"
   ```

   and compare the id it prints with the client id the console shows for the client about to be deleted (do not paste either). **If they are the same, stop**: the organization's login uses that client. If they differ, open its menu, **Delete**, confirm.

The consent screen `aleogr dev` of that project stays: a consent screen cannot be removed, and it is harmless.

## 5. `pilot` still has nothing to do

```bash
cd ~/pilot && claude
```

```
/aleogr:project-plan
```

Expected: `status` `unchanged`, the line `nothing to do`, and the eleven rows of [step 11 of stage 4a](2026-11-19-pilot-stage-4a-run.md#step-11-everything-is-as-declared), all `none`.

## If something differs

Stop at that step and send its whole answer (or the terminal's text), with every id, number, e-mail and address replaced by `<id>`.

## Results

| Step | Expected | Result |
|---|---|---|
| Ready | 4b-1 merged; `gcloud` and `gh` signed in; a second account; `spike-iap` and `spike-iap2` listed | |
| 1. Plugins | the six versions above | |
| 2. Platform plan | `unchanged`, `nothing to do`, `login` `prepared` / `none`; or `login` `not prepared`, then `platform-apply confirm=yes` ends with `login` `prepared`, no `Login` section | |
| 3.1 Address | one `.run.app` address | |
| 3.2 Before the grant | "You don't have access"; any other screen first? | |
| 3.3 The grant | the policy printed | |
| 3.4 After the grant | the service's page, no warning; minutes it took | |
| 4. Services and account | three deletes; no service listed | |
| 4. Console | the client of the project of `pilot` deleted; the shared project untouched | |
| 5. Project plan | `unchanged`, `nothing to do`, eleven rows `none` | |

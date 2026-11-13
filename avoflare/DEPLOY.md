# Deploying Avoflare

Clinical decision support prototype on synthetic data. Deployment here means a supervised pilot/demo environment, not clinical use.

## 1. Test run (before every deployment)
```bash
cd avoflare
AVOFLARE_DEMO_LOGIN=1 python -m uvicorn server:app --port 8000      # test environment only
python predeploy_check.py                                             # wait ~3 min after start so patients have events
```
Read `results/PREDEPLOY_REPORT.md`. Deploy only when every requirement is PASS or an accepted, written exception.

## 2. Build and run
```bash
docker build -t avoflare .                    # from the mineareana/ folder
docker run -d --name avoflare -p 8000:8000 -v avoflare_state:/app/avoflare/state \
  -e NTFY_URL=https://ntfy.example.org -e HAPI_URL=https://hapi.example.org/fhir avoflare
```
- `state/` holds generated credentials, device keys, the record store, notifications and audit log. Keep it on a persistent, backed-up volume. Never commit it.
- First start writes `state/initial_credentials.txt`. Distribute passwords privately, then delete the file.
- Do not set `AVOFLARE_DEMO_LOGIN` in production. It enables one-click sign-in and the screenshot login route.

## 3. Required before going live
- [ ] HTTPS reverse proxy (Nginx/Caddy) in front of port 8000, with WebSocket upgrade for `/ws`. Session cookie must travel over HTTPS only.
- [ ] Replace `care_teams.json` with the real roster, shifts and ntfy topics; each person subscribes to their topic on phone and watch.
- [ ] `NTFY_URL` set (otherwise only in-app and browser notifications are delivered). Verify one test push per person.
- [ ] `HAPI_URL` set if records must reach the hospital FHIR server; verify persistence in Evaluation › System health.
- [ ] Credentials rotated; operator account restricted.
- [ ] Single worker only (`uvicorn` without `--workers`): live state is in process memory.
- [ ] Backups of the `state` volume scheduled.
- [ ] Clinical sign-off of the tuned rules (PERS-2, reliable score, ACT-1/2) and of the provisional twin equations.

## 4. Known open items (from the test run)
- Twin uncertainty bands under-cover RR and SpO2.
- SBP score over-flags a young patient (no personal BP baseline).
- Push delivery needs `NTFY_URL`.

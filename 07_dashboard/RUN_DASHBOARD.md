# Run the dashboard

The React and TypeScript application lives in `src/`. Use Node.js 22 or newer.

```powershell
cd 07_dashboard
npm ci
npm run dev
```

Open the local URL printed by Vite. For a production build, run `npm run build` and `npm run preview`. Run `npm test` to check the replay fixtures.

## Run the bundled build without npm

From the extracted `07_dashboard` folder, run `python -m http.server 4173 --bind 127.0.0.1 --directory dist`, then open http://127.0.0.1:4173/. If port 4173 is occupied, use another port in the command and URL.

## Round-two walkthrough

Open **Scenario replay**, select **Slow deterioration**, and click **Start replay**. Open **Patient monitoring** to show the four trends and scripted Watch, Review and Urgent statuses. Run **Probe removal** to show a missing SpO₂ reading and the separate technical alert in **Clinical alerts**.

The temporary source is `src/fixtures.ts`. It uses fictional patient IDs and reproducible vital values. Scenario checkpoints emit scripted alerts. The app does not calculate clinical scores, authenticate users, write to FHIR or produce measured evaluation results.

## Backend handoff

The proposed observation ingest operation in the backend handoff is producer-facing. It does not return clinical decisions. Connect the clinician dashboard to authorized read and subscription operations once actual OpenAPI and WebSocket payloads are available.

| UI | Backend operation required |
| --- | --- |
| Overview and profile | Authorized patient/session list and context snapshot |
| Monitoring | Identity-scoped history and stream for observations, quality, partial score and decisions |
| Alert center | Alert episode list and authorized lifecycle actions |
| Scenario replay | Simulator control and run status, plus measured result retrieval |
| FHIR records | Scoped Observation retrieval and persistence/validation status |
| Digital twin and intelligence | Versioned manifest, estimates, forecast and expert/trust evidence |
| Clinical reports | Generated reports with evidence and provenance |

The standalone `Avoflare_Round2_Demo.html` is the earlier prototype. Use the Vite application for this dashboard.

# Frontend browser-check plan

The frontend can be reviewed before FastAPI is available. Serve the static page (`python3 -m http.server 8080 --directory frontend`) and use `mock_research_result.json`; opening `frontend/index.html` directly also has a bundled fallback. The preview is illustrative only.

## Browser journey

1. Load the page without an API URL. Confirm the mock report, partial-coverage gap, calculation record, three judge findings, four claim statuses, evidence items, warning/conflict list and partial-results panel appear.
2. Select the verified, calculated, unresolved and blocked claims. Confirm each selection opens the referenced evidence. Check source ID, document ID/version, date and page/section locator.
3. Select a different source in the evidence list. Confirm the viewer switches to that source excerpt.
4. Switch between company discovery and PDF upload. Company mode collects company, ticker, jurisdiction, period range and question. Upload mode accepts multiple PDFs and displays chosen filenames; missing, non-PDF and files over 25 MB should be rejected before a request is sent.
5. Leave the API URL empty. Start research in company mode and confirm the page remains an explicit mock preview. In upload mode, confirm the user must add a PDF first.

## API contract checks with a local stub

Use the included standard-library mock server to exercise the API path before FastAPI is available:

```sh
python3 tests/frontend/mock_api.py --scenario completed_with_warnings
```

Open `http://127.0.0.1:8081`, enter that same origin as the API base URL in **Research settings**, and submit the form. This serves the frontend and the contract stub from one origin; uploaded file bytes are accepted only by this local mock server. Choose `--scenario completed` or `--scenario failed` to review terminal-state rendering. Each run walks through queued and running before its selected terminal state.

The UI uses the same renderer for JSON fixtures and live results. The stub exercises these requests:

- Company: `GET /api/health` → `POST /api/company/discover` → `POST /api/runs` → poll `GET /api/runs/{run_id}` → `GET /api/runs/{run_id}/result`.
- Upload: `GET /api/health` → multipart `POST /api/documents/upload` → `POST /api/runs` with returned `document_ids` → same status and result routes.
- Run status fixtures: `queued`, `running` with `current_stage`, `completed`, `completed_with_warnings`, and `failed`. For a failed run, return a partial result when available; also check the no-result failure response.
- Result fixtures: all six shared claim statuses, `financial_calculations`, three `judge_reviews`, evidence provenance, `source_coverage` gaps, warnings and `failed_nodes`.

For every fixture, check that labels and details are rendered from response fields. The frontend must not compute or upgrade a claim status. No backend, retrieval or model behavior is exercised by these browser checks.

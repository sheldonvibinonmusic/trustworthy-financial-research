# Financial research frontend

Static HTML/CSS/JavaScript interface for the research API described in `../API_CONTRACT.md`. The page opens on illustrative mock data; all example companies, values, excerpts, calculations, and verdicts are explicitly mock data.

You can open `index.html` directly as a local file. Since browsers block `fetch()` for sibling files under `file://`, that mode uses a bundled preview fallback. When served over HTTP, the interface loads `mock_research_result.json` as its primary mock source.

## Run the mock preview

From the repository root, serve this folder over HTTP to load the full `mock_research_result.json`:

```sh
python3 -m http.server 8080 --directory frontend
```

Then open `http://localhost:8080`. The initial report is a UI preview only. With the API base URL left empty, **Start research** does not submit company data or uploaded files.

## Connect the FastAPI backend

Open **Research settings**, enter the backend origin (for example `http://localhost:8000`), and start a research request. The client uses the contract endpoints:

- `GET /api/health`
- `POST /api/company/discover` for company mode
- `POST /api/documents/upload` for PDF mode
- `POST /api/runs`, followed by polling `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/result` when complete

The backend must allow cross-origin requests from the frontend origin when they differ. A default API origin can also be set before loading the page as `window.FINANCIAL_RESEARCH_API_BASE`.

Before FastAPI is ready, exercise the same request flow with the local contract stub in [`tests/frontend/README.md`](../tests/frontend/README.md). It simulates queued, running and selectable terminal statuses while reusing the same result renderer.

## Basic manual/browser checks

1. Load the page over HTTP. Confirm the mock report, four claim statuses, partial source coverage, warnings, and source list appear.
2. Select each claim. Confirm the evidence panel changes to its cited mock passage; select a source in the source list and confirm the passage changes.
3. Switch to upload mode. Confirm PDF selection/drop lists the chosen files; non-PDF and over-25-MB files are rejected on submission.
4. Leave the API URL blank and start research. Confirm the page clearly says this is a preview and no request was sent.
5. With a compatible FastAPI backend and CORS enabled, set the API URL and submit each mode. Confirm status polling and the API result render with backend-supplied statuses.

There is no client-side financial reasoning, claim verification, retrieval, or AI call. Preview content is mock-only; the full preview is loaded from `mock_research_result.json` over HTTP, with a small bundled fallback for direct `file://` use.

/* UI rendering and HTTP transport only. Financial analysis and claim verdicts belong to the API. */
const STATUS_LABELS = {
  verified_source: "VERIFIED SOURCE",
  calculated_checked: "CALCULATED · CHECKED",
  interpretation_supported: "SUPPORTED INTERPRETATION",
  unresolved: "UNRESOLVED",
  blocked: "BLOCKED",
  not_evaluated: "NOT EVALUATED"
};

const STATUS_COPY = {
  queued: ["Research queued", "Your request is in the queue."],
  running: ["Research in progress", "The backend is processing this research run."],
  completed: ["Research complete", "The report is ready for review."],
  completed_with_warnings: ["Research complete with warnings", "Review source coverage and unresolved items before relying on this report."],
  failed: ["Research could not be completed", "The backend reported an error for this run."]
};

// A small inline copy keeps the preview usable when opened directly as file://,
// where browsers block fetch() of sibling files. Over HTTP, the JSON file remains primary.
const FILE_PROTOCOL_MOCK_FALLBACK = {
  mock_data: true,
  run_id: "demo_meridian_file_preview",
  status: "completed_with_warnings",
  company: { name: "Meridian Energy", ticker: "MRE", jurisdiction: "US" },
  periods: { start_year: 2023, end_year: 2025, label: "FY2023–FY2025" },
  generated_at: "2026-10-24T09:30:00Z",
  question: "Assess revenue growth, cash flow quality and debt risks over the selected periods.",
  source_coverage: { status: "partial", summary: "3 illustrative sources reviewed · 1 expected source not available in this mock example", gaps: ["FY2025 quarterly filing unavailable (mock example)"] },
  report_sections: [
    { section_id: "overview", title: "Executive overview", body: "This mock preview illustrates how a future backend result separates sourced statements, deterministic calculations, uncertainty and blocked conclusions. It is not a real analysis of Meridian Energy.", claim_ids: ["claim-verified", "claim-calculated", "claim-interpretation", "claim-conflict", "claim-blocked", "claim-not-evaluated"] },
    { section_id: "risk", title: "Cash flow & risk signals", body: "The example includes a difference between two mock source excerpts and one claim blocked by missing unit and scope context.", claim_ids: ["claim-conflict", "claim-blocked"] }
  ],
  claims: [
    { claim_id: "claim-verified", text: "FY2025 revenue was $4.8 billion.", status: "verified_source", evidence_ids: ["evidence-annual-2025"], period: "FY2025" },
    { claim_id: "claim-calculated", text: "Revenue increased approximately 9.1% from FY2024 to FY2025.", status: "calculated_checked", evidence_ids: ["evidence-annual-2025", "evidence-annual-2024"], period: "FY2024–FY2025", calculation: "($4.8B − $4.4B) ÷ $4.4B = 9.1%" },
    { claim_id: "claim-interpretation", text: "The filing describes service revenue as one contributor to FY2025 growth.", status: "interpretation_supported", evidence_ids: ["evidence-service-growth-2025"], period: "FY2025" },
    { claim_id: "claim-conflict", text: "FY2025 operating cash flow was $620 million.", status: "unresolved", evidence_ids: ["evidence-annual-2025", "evidence-presentation-2025"], period: "FY2025", conflict: "The mock annual filing excerpt says $620M; the mock investor presentation excerpt says $590M. Definitions and consolidation scope have not been confirmed." },
    { claim_id: "claim-not-evaluated", text: "The company’s next-year outlook will be achieved.", status: "not_evaluated", evidence_ids: [], period: "FY2026", explanation: "This illustrative forward-looking statement was not evaluated in the mock report." },
    { claim_id: "claim-blocked", text: "Net debt was 2.1× EBITDA in FY2025.", status: "blocked", evidence_ids: ["evidence-annual-2025"], period: "FY2025", explanation: "The example lacks confirmed unit, accounting definition and reporting scope." }
  ],
  evidence_items: [
    { evidence_id: "evidence-annual-2025", document_id: "mock-doc-annual-2025", document_version: "mock-v1", filename: "meridian_annual_report_fy2025_mock.pdf", title: "Annual report · FY2025 (mock)", source_type: "MOCK ANNUAL FILING", page: 42, section: "Consolidated statements of operations", published_at: "2026-02-18", locator: "Page 42 · Revenue, FY2025", quote: "For the year ended December 31, 2025, total revenue was $4.8 billion. Operating cash flow was $620 million.", url: "#mock-evidence-annual-2025" },
    { evidence_id: "evidence-service-growth-2025", document_id: "mock-doc-annual-2025", document_version: "mock-v1", filename: "meridian_annual_report_fy2025_mock.pdf", title: "Annual report · FY2025 (mock)", source_type: "MOCK ANNUAL FILING", page: 15, section: "Revenue by segment", published_at: "2026-02-18", locator: "Page 15 · Service revenue, FY2025", quote: "In this illustrative mock excerpt, service revenue growth contributed to the year-over-year change.", url: "#mock-evidence-service-growth-2025" },
    { evidence_id: "evidence-annual-2024", document_id: "mock-doc-annual-2024", document_version: "mock-v1", filename: "meridian_annual_report_fy2024_mock.pdf", title: "Annual report · FY2024 (mock)", source_type: "MOCK ANNUAL FILING", page: 39, section: "Consolidated statements of operations", published_at: "2025-02-19", locator: "Page 39 · Revenue, FY2024", quote: "For the year ended December 31, 2024, total revenue was $4.4 billion.", url: "#mock-evidence-annual-2024" },
    { evidence_id: "evidence-presentation-2025", document_id: "mock-doc-presentation-2025", document_version: "mock-v1", filename: "meridian_investor_presentation_fy2025_mock.pdf", title: "Investor presentation · FY2025 (mock)", source_type: "MOCK PRESENTATION", page: 18, section: "Cash generation overview", published_at: "2026-03-03", locator: "Page 18 · Cash generation", quote: "Operating cash flow for fiscal 2025 was $590 million, excluding discontinued operations.", url: "#mock-evidence-presentation-2025" }
  ],
  financial_calculations: [{ calculation_id: "calc-revenue-growth", claim_id: "claim-calculated", formula: "(current_period - prior_period) / prior_period", inputs: ["$4.8B FY2025 revenue", "$4.4B FY2024 revenue"], result: "9.1%", status: "mock_checked", evidence_ids: ["evidence-annual-2025", "evidence-annual-2024"] }],
  judge_reviews: [
    { review_id: "mock-review-evidence", role: "Evidence and citation auditor", verdict: "illustrative_pass", findings: "Mock finding: the quoted revenue excerpt directly matches the example claim. No live audit was performed.", claim_id: "claim-verified", evidence_ids: ["evidence-annual-2025"] },
    { review_id: "mock-review-financial-integrity", role: "Financial integrity auditor", verdict: "illustrative_review", findings: "Mock finding: the growth calculation record points to two illustrative annual inputs; period, units and accounting context still require backend validation.", claim_id: "claim-calculated", evidence_ids: ["evidence-annual-2025", "evidence-annual-2024"] },
    { review_id: "mock-review-adversarial", role: "Adversarial skeptic", verdict: "illustrative_conflict", findings: "Mock finding: another example source gives a different operating cash flow amount and a scope caveat. The conflict remains unresolved.", claim_id: "claim-conflict", evidence_ids: ["evidence-annual-2025", "evidence-presentation-2025"] }
  ],
  failed_nodes: [{ node: "quarterly_source_discovery", status: "mock_partial", reason: "One quarterly source is unavailable in this illustrative run." }],
  warnings: [
    { type: "source_coverage", title: "Incomplete source coverage", message: "This mock run has 3 illustrative sources for 4 expected items. One quarterly filing is marked unavailable in the example." },
    { type: "unresolved_conflict", title: "Operating cash flow differs across mock sources", message: "The mock annual filing excerpt reports $620M while a mock investor presentation reports $590M. The excerpts cite different scopes; review the original documents before relying on either value." },
    { type: "blocked_claim", title: "Leverage ratio not validated", message: "The example lacks comparable debt and EBITDA values with confirmed unit, definition and reporting scope, so the ratio remains blocked." }
  ],
  mock_notice: "Illustrative interface data only. These company figures, source excerpts, claim statuses and calculations are fabricated examples."
};

class ResearchApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  async request(path, options = {}) {
    const response = await fetch(`${this.baseUrl}${path}`, options);
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = payload && typeof payload === "object" ? (payload.detail || payload.message) : payload;
      throw new Error((typeof detail === "string" ? detail : displayValue(detail)) || `Request failed (${response.status})`);
    }
    return payload;
  }

  health() { return this.request("/api/health"); }

  uploadDocuments(files) {
    const form = new FormData();
    for (const file of files) form.append("files", file);
    return this.request("/api/documents/upload", { method: "POST", body: form });
  }

  discoverCompany(input) {
    return this.request("/api/company/discover", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input)
    });
  }

  createRun(input) {
    return this.request("/api/runs", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input)
    });
  }

  getRun(runId) { return this.request(`/api/runs/${encodeURIComponent(runId)}`); }
  getResult(runId) { return this.request(`/api/runs/${encodeURIComponent(runId)}/result`); }
}

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const html = (value = "") => String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const state = { mode: "company", result: null, selectedClaimId: null, selectedEvidenceId: null, discoveryWarnings: [], toastTimer: null };

function warningMessage(item) {
  return typeof item === "string" ? item : item?.message || item?.detail || displayValue(item);
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? String(value) : new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(date);
}

function displayValue(value) {
  if (value === undefined || value === null || value === "") return "";
  if (Array.isArray(value)) return value.map(displayValue).filter(Boolean).join(" · ");
  if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${key}: ${displayValue(item)}`).join(" · ");
  return String(value);
}

function renderEvidenceLinks(ids = []) {
  return ids.filter(Boolean).map(id => `<button type="button" data-show-evidence="${html(id)}">Evidence ${html(id)}</button>`).join("");
}

function renderCoverage(coverage) {
  const gaps = coverage.gaps || coverage.missing_documents || coverage.missing_required_documents || coverage.missing_sources || [];
  const gapText = Array.isArray(gaps) ? gaps.map(item => typeof item === "string" ? item : item.title || item.document_type || item.filename || item.name || displayValue(item)).filter(Boolean).join(" · ") : displayValue(gaps);
  const counts = [
    coverage.available !== undefined ? `${coverage.available} available` : "",
    coverage.expected !== undefined ? `${coverage.expected} expected` : ""
  ].filter(Boolean).join(" / ");
  const summary = [coverage.summary, counts].filter(Boolean).join(" · ");
  $("#coverage-text").textContent = summary || "Source coverage details were not provided.";
  $("#coverage-gaps").textContent = gapText ? `Coverage gaps: ${gapText}` : "";
  const coverageStatus = String(coverage.status || "unknown").toLowerCase();
  $("#coverage-strip .coverage-badge").textContent = coverageStatus.replaceAll("_", " ").toUpperCase();
  $("#coverage-strip .coverage-badge").className = `coverage-badge ${html(coverageStatus)}`;
}

function renderCalculations(records = []) {
  $("#calculation-count").textContent = String(records.length);
  $("#calculations-list").innerHTML = records.length ? records.map(record => {
    const title = record.title || record.name || record.label || record.metric || record.calculation_name || record.calculation_id || "Financial calculation";
    const formula = record.formula || record.method || record.calculation;
    const inputs = displayValue(record.inputs || record.input_values);
    const output = displayValue(record.result ?? record.output ?? record.value);
    const details = [formula ? `Formula: ${displayValue(formula)}` : "", inputs ? `Inputs: ${inputs}` : "", output ? `Result: ${output}${record.units ? ` ${displayValue(record.units)}` : ""}` : "", record.claim_id ? `Claim: ${record.claim_id}` : ""].filter(Boolean);
    return `<article class="detail-row"><div class="detail-row-head"><strong>${html(title)}</strong>${record.status ? `<span class="detail-status ${html(String(record.status).toLowerCase())}">${html(displayValue(record.status).replaceAll("_", " ").toUpperCase())}</span>` : ""}</div>${details.length ? `<p>${html(details.join(" · "))}</p>` : `<p>Calculation record returned without formula details.</p>`}${record.evidence_ids?.length ? `<div class="detail-evidence">${renderEvidenceLinks(record.evidence_ids)}</div>` : ""}</article>`;
  }).join("") : `<div class="empty-detail">No financial calculation records were returned.</div>`;
}

function renderJudges(reviews = []) {
  $("#judge-count").textContent = `${reviews.length} / 3`;
  $("#judges-list").innerHTML = reviews.length ? reviews.map(review => {
    const role = review.role || review.judge_role || review.judge_name || review.reviewer || review.name || "Judge review";
    const verdict = review.verdict || review.status || review.result;
    const findings = displayValue(review.findings || review.finding || review.summary || review.reasoning || review.detail);
    const extra = [review.review_id ? `Review: ${review.review_id}` : "", review.claim_id ? `Claim: ${review.claim_id}` : ""].filter(Boolean).join(" · ");
    return `<article class="detail-row"><div class="detail-row-head"><strong>${html(role)}</strong>${verdict ? `<span class="judge-verdict ${html(String(verdict).toLowerCase())}">${html(displayValue(verdict).replaceAll("_", " ").toUpperCase())}</span>` : ""}</div>${findings ? `<p>${html(findings)}</p>` : `<p>No finding details were included in this review.</p>`}${extra ? `<div class="detail-meta">${html(extra)}</div>` : ""}${review.evidence_ids?.length ? `<div class="detail-evidence">${renderEvidenceLinks(review.evidence_ids)}</div>` : ""}</article>`;
  }).join("") : `<div class="empty-detail">No judge findings were returned.</div>`;
}

function renderPartialResults(result) {
  const failedNodes = Array.isArray(result.failed_nodes) ? result.failed_nodes : [];
  const partial = result.partial === true || result.is_partial === true || String(result.status || "").toLowerCase() === "failed" || failedNodes.length > 0;
  const panel = $("#partial-results");
  panel.classList.toggle("hidden", !partial);
  if (!partial) return;
  const summary = result.partial_results_summary || result.partial_summary || (failedNodes.length ? "Some workflow steps did not complete. Available sections and claims are shown with their returned statuses." : "The run ended before a complete report was available.");
  const nodes = failedNodes.map(node => {
    const name = typeof node === "string" ? node : node.node || node.node_name || node.name || "Workflow step";
    const reason = typeof node === "string" ? "" : node.error || node.reason || node.message || node.status || "";
    return `<div class="partial-node"><strong>${html(name)}</strong><span>${html(displayValue(reason) || "This step did not complete.")}</span></div>`;
  }).join("");
  $("#partial-results-list").innerHTML = `<p class="partial-note">${html(summary)}</p>${nodes || `<div class="partial-node"><strong>Run status</strong><span>${html(String(result.status || "partial").replaceAll("_", " "))}</span></div>`}`;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

function setStatus({ title, description, status = "idle", stage = "intake", runId = "" }) {
  const icon = $("#status-icon");
  const pill = $("#status-pill");
  const steps = $$(".status-steps .step");
  const order = ["intake", "sources", "analysis", "report"];
  const aliases = { complete: "completed", warning: "completed_with_warnings", error: "failed" };
  const normalized = aliases[status] || status;
  const activeIndex = Math.max(order.indexOf(stage), 0);
  icon.className = `status-icon ${normalized}`;
  icon.textContent = normalized === "running" ? "◌" : normalized === "completed" || normalized === "completed_with_warnings" ? "✓" : normalized === "failed" ? "!" : "◷";
  $("#status-title").textContent = title;
  $("#status-description").textContent = description;
  pill.className = `status-pill ${normalized}`;
  pill.textContent = ({ idle: "MOCK PREVIEW", queued: "QUEUED", running: "RUNNING", completed: "COMPLETED", completed_with_warnings: "COMPLETED · WARNINGS", failed: "FAILED" })[normalized] || normalized.toUpperCase();
  const progress = normalized === "idle" ? 0 : normalized === "queued" ? 4 : normalized === "running" ? Math.round((activeIndex + 1) / order.length * 85) : normalized === "failed" ? Math.round(activeIndex / order.length * 85) : 100;
  $("#progress-bar").style.width = `${progress}%`;
  steps.forEach((step, index) => {
    step.classList.toggle("active", index === activeIndex && (normalized === "running" || normalized === "queued"));
    step.classList.toggle("done", index < activeIndex || ((normalized === "completed" || normalized === "completed_with_warnings") && index <= activeIndex));
  });
  $("#status-run-id").textContent = normalized === "idle" ? (runId || "DEMO RESULT") : runId ? `RUN ${runId}` : "";
}

function renderReport(result) {
  state.result = result;
  state.selectedClaimId = null;
  state.selectedEvidenceId = null;
  const company = result.company || {};
  const periods = result.periods || {};
  const isMock = result.mock_data === true || String(result.run_id || "").startsWith("demo_");
  $("#report-title").textContent = company.name || "Research report";
  const periodLabel = periods.label || [periods.start_year, periods.end_year].filter(Boolean).join("–");
  const subtitle = [result.question || "Research report", periodLabel, result.generated_at ? `Generated ${formatDate(result.generated_at)}` : ""].filter(Boolean);
  $("#report-subtitle").innerHTML = subtitle.map(html).join(" <span>·</span> ");
  $("#report-status").innerHTML = `<i></i> ${isMock ? "MOCK EXAMPLE" : html(String(result.status || "RESULT").replaceAll("_", " ").toUpperCase())}`;

  renderCoverage(result.source_coverage || {});

  const sections = Array.isArray(result.report_sections) ? result.report_sections : [];
  $("#report-sections").innerHTML = sections.map(section => {
    const claims = (section.claim_ids || []).map(id => (result.claims || []).find(claim => claim.claim_id === id)).filter(Boolean);
    const claimRefs = claims.slice(0, 3).map(claim => `<button class="section-source" type="button" data-claim="${html(claim.claim_id)}">↗ ${html(claim.status_label || STATUS_LABELS[claim.status] || "CLAIM")}</button>`).join(" ");
    const bullets = Array.isArray(section.bullets) && section.bullets.length ? `<ul>${section.bullets.map(bullet => `<li>${html(bullet)}</li>`).join("")}</ul>` : "";
    const summary = section.body || section.summary || "";
    return `<article class="report-card"><span class="section-kicker">${html(section.kicker || "RESEARCH FINDING")}</span><h3>${html(section.title || "Report section")}</h3>${summary ? `<p>${html(summary)}</p>` : ""}${bullets}${claimRefs ? `<div class="section-claim-refs">${claimRefs}</div>` : ""}</article>`;
  }).join("") || `<article class="report-card"><h3>No report sections returned</h3><p>The backend result did not include report sections. Claim, evidence and warning details are shown below when available.</p></article>`;

  const claims = Array.isArray(result.claims) ? result.claims : [];
  $("#claim-count").textContent = `${claims.length} claim${claims.length === 1 ? "" : "s"}`;
  $("#claims-list").innerHTML = claims.length ? claims.map(claim => {
    const status = claim.status || "not_evaluated";
    const label = claim.status_label || STATUS_LABELS[status] || status.replaceAll("_", " ").toUpperCase();
    const detail = [claim.period, (claim.evidence_ids || []).length ? `${claim.evidence_ids.length} source${claim.evidence_ids.length === 1 ? "" : "s"}` : "No cited source"].filter(Boolean).join(" · ");
    return `<button class="claim-row" type="button" data-claim="${html(claim.claim_id)}"><i class="claim-dot ${html(status)}"></i><span class="claim-copy"><strong>${html(claim.text || claim.statement || "Claim")}</strong><small>${html(detail)}</small></span><span class="claim-status ${html(status)}">${html(label)}</span><span class="claim-arrow">›</span></button>`;
  }).join("") : `<div class="empty-claims">No claims were returned for this report.</div>`;

  renderPartialResults(result);
  renderCalculations(Array.isArray(result.financial_calculations) ? result.financial_calculations : []);
  renderJudges(Array.isArray(result.judge_reviews) ? result.judge_reviews : []);
  renderWarnings(result);
  renderSources(result);
  $("#evidence-count").textContent = `${(result.evidence_items || []).length} ITEMS`;
  $("#source-count").textContent = String((result.evidence_items || []).length);
  $("#evidence-detail").innerHTML = `<div class="empty-evidence"><span>↖</span><strong>Select a claim</strong><p>Its supporting source and relevant passage will appear here.</p></div>`;
  $$("[data-claim]").forEach(button => button.addEventListener("click", () => selectClaim(button.dataset.claim)));
  $$(`[data-show-evidence]`).forEach(button => button.addEventListener("click", () => selectEvidence(button.dataset.showEvidence)));
}

function renderWarnings(result) {
  const warnings = Array.isArray(result.warnings) ? result.warnings : [];
  const unresolved = (result.claims || []).filter(claim => claim.status === "unresolved" && claim.conflict);
  const entries = [
    ...warnings.map(warning => typeof warning === "string" ? ({ kind: "warning", message: warning }) : ({ kind: (warning.type || "warning").replaceAll("_", " "), title: warning.title, message: warning.message || warning.detail || "" })),
    ...unresolved.filter(claim => !warnings.some(warning => String(warning.type || "").includes("unresolved_conflict"))).map(claim => ({ kind: "unresolved conflict", title: claim.text, message: claim.conflict || claim.explanation || "This claim remains unresolved." }))
  ];
  $("#warnings-list").innerHTML = entries.length ? entries.map(item => `<div class="warning-entry"><span class="warning-kind">${html(item.kind)}</span><p>${item.title ? `<strong>${html(item.title)}. </strong>` : ""}${html(item.message)}</p></div>`).join("") : `<div class="warning-entry"><p>No warnings were returned.</p></div>`;
}

function renderSources(result) {
  const evidence = Array.isArray(result.evidence_items) ? result.evidence_items : [];
  $("#source-list").innerHTML = evidence.map(item => `<div class="source-item" role="button" tabindex="0" data-evidence="${html(item.evidence_id)}"><span class="source-file-icon">PDF</span><span class="source-copy"><strong>${html(item.title || item.filename || "Source document")}</strong><small>${html(item.locator || [item.section, item.page ? `Page ${item.page}` : ""].filter(Boolean).join(" · "))}</small></span><span class="source-open">↗</span></div>`).join("") || `<div class="source-copy"><small>No source items were returned.</small></div>`;
  $$("[data-evidence]").forEach(item => {
    item.addEventListener("click", () => selectEvidence(item.dataset.evidence));
    item.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectEvidence(item.dataset.evidence); } });
  });
}

function selectClaim(claimId) {
  const claim = (state.result?.claims || []).find(item => item.claim_id === claimId);
  if (!claim) return;
  state.selectedClaimId = claimId;
  state.selectedEvidenceId = (claim.evidence_ids || [])[0] || null;
  $$(".claim-row").forEach(row => row.classList.toggle("selected", row.dataset.claim === claimId));
  if (state.selectedEvidenceId) renderEvidenceDetail(state.selectedEvidenceId, claim);
  else $("#evidence-detail").innerHTML = `<div class="empty-evidence"><span>↖</span><strong>No evidence attached</strong><p>${html(claim.explanation || "The backend did not return a supporting source for this claim.")}</p></div>`;
  $("#evidence-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function selectEvidence(evidenceId) {
  state.selectedEvidenceId = evidenceId;
  const claim = (state.result?.claims || []).find(item => item.claim_id === state.selectedClaimId);
  renderEvidenceDetail(evidenceId, claim);
}

function renderEvidenceDetail(evidenceId, claim) {
  const item = (state.result?.evidence_items || []).find(evidence => evidence.evidence_id === evidenceId);
  if (!item) {
    $("#evidence-detail").innerHTML = `<div class="empty-evidence"><span>↖</span><strong>Evidence unavailable</strong><p>The referenced evidence item was not included in the result.</p></div>`;
    return;
  }
  let quote = item.quote || item.text || item.excerpt || "No excerpt was provided by the backend.";
  if (claim?.calculation && claim.evidence_ids?.length > 1) quote += `\n\nCalculation returned by backend: ${claim.calculation}`;
  const link = item.url && item.url !== "#" ? `<a class="evidence-open" href="${html(item.url)}" target="_blank" rel="noopener noreferrer">Open source reference ↗</a>` : "";
  const provenance = [item.filename, item.document_id ? `Document ${item.document_id}` : "", item.document_version ? `Version ${item.document_version}` : "", item.published_at ? formatDate(item.published_at) : "", item.jurisdiction ? `Jurisdiction ${item.jurisdiction}` : ""].filter(Boolean).join(" · ");
  $("#evidence-detail").innerHTML = `<div class="evidence-source-type"><span class="pdf-icon">PDF</span>${html(item.source_type || "SOURCE")}</div><h4>${html(item.title || item.filename || "Evidence source")}</h4><div class="evidence-meta">${html(provenance)}</div><blockquote class="evidence-quote">${html(quote)}</blockquote><div class="evidence-locator"><span>${html(item.locator || [item.section, item.page ? `Page ${item.page}` : ""].filter(Boolean).join(" · "))}</span><span>${html(item.evidence_id)}</span></div>${link}`;
}

function setMode(mode) {
  state.mode = mode;
  $$(".mode-tab").forEach(tab => {
    const active = tab.dataset.mode === mode;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  $("#company-fields").classList.toggle("hidden", mode !== "company");
  $("#upload-fields").classList.toggle("hidden", mode !== "upload");
  $("#company-name").required = mode === "company";
  $("#pdf-files").required = mode === "upload";
}

function setupPeriods() {
  const start = $("#start-year");
  const end = $("#end-year");
  const current = new Date().getFullYear();
  for (let year = current; year >= current - 12; year -= 1) {
    start.add(new Option(`FY ${year}`, year));
    end.add(new Option(`FY ${year}`, year));
  }
  start.value = String(current - 3);
  end.value = String(current - 1);
}

function updateFiles() {
  const files = [...$("#pdf-files").files];
  $("#file-list").innerHTML = files.map(file => `<span class="file-chip">${html(file.name)} · ${(file.size / 1024 / 1024).toFixed(1)} MB</span>`).join("");
}

function validateFiles(files) {
  if (!files.length) throw new Error("Add at least one PDF to start research.");
  const invalid = files.find(file => file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf"));
  if (invalid) throw new Error(`${invalid.name} is not a PDF file.`);
  const tooLarge = files.find(file => file.size > 25 * 1024 * 1024);
  if (tooLarge) throw new Error(`${tooLarge.name} is larger than 25 MB.`);
}

function collectRequest(documentIds = []) {
  const uploadMode = state.mode === "upload";
  const companyName = uploadMode ? $("#upload-company").value.trim() : $("#company-name").value.trim();
  const jurisdiction = uploadMode ? $("#upload-jurisdiction").value : $("#jurisdiction").value;
  const checked = $$(".analysis-options input:checked").map(input => input.value);
  return {
    input_mode: uploadMode ? "upload" : "company",
    ...(companyName ? { company_name: companyName } : {}),
    ...(!uploadMode && $("#ticker").value.trim() ? { ticker: $("#ticker").value.trim() } : {}),
    jurisdiction,
    start_year: Number($("#start-year").value),
    end_year: Number($("#end-year").value),
    question: $("#research-question").value.trim(),
    ...(documentIds.length ? { document_ids: documentIds } : {}),
    requested_analyses: checked
  };
}

async function pollRun(client, runId) {
  const started = Date.now();
  let lastStage = "intake";
  while (Date.now() - started < 10 * 60 * 1000) {
    const run = await client.getRun(runId);
    const status = run.status || "running";
    const stageName = String(run.current_stage || "").toLowerCase();
    lastStage = stageName.includes("report") ? "report" : stageName.includes("retriev") || stageName.includes("source") || stageName.includes("ingest") ? "sources" : stageName.includes("verif") || stageName.includes("analys") || stageName.includes("judge") ? "analysis" : lastStage;
    if (status === "completed" || status === "completed_with_warnings") {
      const result = await client.getResult(runId);
      const runWarnings = (run.warnings || []).map(item => ({ type: "run_status", title: "Run status", message: warningMessage(item) }));
      result.warnings = [...state.discoveryWarnings.map(message => ({ type: "company_discovery", title: "Company discovery", message })), ...(result.warnings || []), ...runWarnings];
      renderReport(result);
      const [title, description] = STATUS_COPY[status];
      setStatus({ title, description, status, stage: "report", runId });
      $("#report").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (status === "failed") {
      let partialResult = null;
      try { partialResult = await client.getResult(runId); } catch { /* A failed run may not have a report payload. */ }
      if (partialResult) {
        partialResult.warnings = [...state.discoveryWarnings.map(message => ({ type: "company_discovery", title: "Company discovery", message })), ...(partialResult.warnings || []), ...(run.warnings || []).map(item => ({ type: "run_status", title: "Run failed", message: warningMessage(item) }))];
        renderReport({ ...partialResult, status: "failed" });
      } else {
        renderPartialResults({ status: "failed", failed_nodes: [], partial_summary: "The backend marked this run failed before returning a report." });
        const warnings = [...state.discoveryWarnings, ...(Array.isArray(run.warnings) ? run.warnings : [])];
        $("#warnings-list").innerHTML = warnings.length ? warnings.map(item => {
          const message = warningMessage(item);
          return `<div class="warning-entry"><span class="warning-kind">run failure</span><p>${html(message)}</p></div>`;
        }).join("") : `<div class="warning-entry"><p>The backend marked this run failed and returned no additional detail.</p></div>`;
      }
      const failureText = (run.warnings || []).map(item => typeof item === "string" ? item : item.message || item.detail || displayValue(item)).filter(Boolean).join(" ");
      setStatus({ title: STATUS_COPY.failed[0], description: failureText || STATUS_COPY.failed[1], status: "failed", stage: lastStage, runId });
      $("#report").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    const [title, description] = STATUS_COPY[status] || STATUS_COPY.running;
    const stage = stageName || lastStage;
    const runWarnings = (run.warnings || []).map(item => typeof item === "string" ? item : item.message || item.detail || displayValue(item)).join(" ");
    setStatus({ title, description: [description, runWarnings].filter(Boolean).join(" "), status, stage: stage.includes("report") ? "report" : stage.includes("retriev") || stage.includes("source") ? "sources" : stage.includes("analys") ? "analysis" : lastStage, runId });
    await new Promise(resolve => setTimeout(resolve, 1800));
  }
  throw new Error("This run is taking longer than expected. Check the run status and try again.");
}

function showPendingReport() {
  $("#report-status").innerHTML = "<i></i> LIVE API REQUEST";
  $("#report-title").textContent = state.mode === "upload" ? ($("#upload-company").value.trim() || "Uploaded documents") : $("#company-name").value.trim();
  $("#report-subtitle").textContent = "Waiting for the backend research result.";
  $("#coverage-text").textContent = "Source coverage will be shown when the backend returns.";
  $("#coverage-gaps").textContent = "";
  $("#coverage-strip .coverage-badge").textContent = "PENDING";
  $("#report-sections").innerHTML = "<article class=\"report-card\"><h3>Research in progress</h3><p>Report sections and claim statuses will appear here when the backend returns them.</p></article>";
  $("#partial-results").classList.add("hidden");
  $("#claims-list").innerHTML = "<div class=\"empty-detail\">Waiting for backend claims.</div>";
  $("#warnings-list").innerHTML = "<div class=\"warning-entry\"><p>Warnings and unresolved conflicts will be shown if returned by the backend.</p></div>";
  $("#source-list").innerHTML = "<div class=\"empty-detail\">Waiting for backend evidence items.</div>";
  $("#source-count").textContent = "0";
  $("#evidence-count").textContent = "0 ITEMS";
  $("#evidence-detail").innerHTML = "<div class=\"empty-evidence\"><span>◌</span><strong>Waiting for evidence</strong><p>The evidence viewer will populate from the backend result.</p></div>";
  renderCalculations([]);
  renderJudges([]);
}

async function startLiveResearch(client) {
  const button = $(".start-button");
  button.disabled = true;
  state.discoveryWarnings = [];
  showPendingReport();
  try {
    setStatus({ title: "Connecting to research API", description: "Checking the backend and preparing your request.", status: "running", stage: "intake" });
    await client.health();
    let documentIds = [];
    if (state.mode === "upload") {
      const files = [...$("#pdf-files").files];
      validateFiles(files);
      setStatus({ title: "Uploading documents", description: `${files.length} PDF${files.length === 1 ? "" : "s"} being sent to the backend.`, status: "running", stage: "intake" });
      const uploaded = await client.uploadDocuments(files);
      documentIds = (uploaded.documents || []).map(document => document.document_id).filter(Boolean);
      if (!documentIds.length) throw new Error("The upload response did not include document IDs.");
      const uploadWarnings = (uploaded.documents || []).flatMap(document => document.warnings || []);
      if (uploadWarnings.length) showToast(uploadWarnings.join(" "));
    } else {
      setStatus({ title: "Checking company sources", description: "Requesting approved-source discovery from the backend.", status: "running", stage: "sources" });
      const discovery = await client.discoverCompany({
        company_name: $("#company-name").value.trim(),
        ticker: $("#ticker").value.trim() || undefined,
        jurisdiction: $("#jurisdiction").value,
        start_year: Number($("#start-year").value),
        end_year: Number($("#end-year").value)
      });
      state.discoveryWarnings = (discovery.warnings || []).map(warningMessage).filter(Boolean);
      const sourceCount = (discovery.sources || []).length;
      const discoverySummary = [`${sourceCount} source${sourceCount === 1 ? "" : "s"} returned`, state.discoveryWarnings.length ? `${state.discoveryWarnings.length} discovery warning${state.discoveryWarnings.length === 1 ? "" : "s"}` : "no discovery warnings"].join(" · ");
      setStatus({ title: "Company discovery complete", description: `${discoverySummary}. Creating the research run.`, status: "running", stage: "sources" });
    }
    const response = await client.createRun(collectRequest(documentIds));
    if (!response.run_id) throw new Error("The API did not return a run ID.");
    const firstStatus = response.status || "queued";
    const [firstTitle, firstDescription] = STATUS_COPY[firstStatus] || STATUS_COPY.queued;
    setStatus({ title: firstTitle, description: firstDescription, status: firstStatus, stage: "intake", runId: response.run_id });
    await pollRun(client, response.run_id);
  } catch (error) {
    setStatus({ title: "Could not start research", description: error.message || "Check the API URL, backend availability and request details.", status: "error", stage: "intake" });
    $("#warnings-list").innerHTML = `<div class="warning-entry"><span class="warning-kind">API error</span><p>${html(error.message || "Could not reach the research API.")}</p></div>`;
    showToast(error.message || "Research request failed.");
  } finally {
    button.disabled = false;
  }
}

async function startResearch(event) {
  event.preventDefault();
  const question = $("#research-question").value.trim();
  if (!question) { $("#research-question").focus(); return; }
  if (question.length > 500) { showToast("Keep the research question to 500 characters or fewer."); return; }
  if (state.mode === "company" && !$("#company-name").value.trim()) { showToast("Enter a company name to continue."); $("#company-name").focus(); return; }
  const apiBase = $("#api-base").value.trim() || window.FINANCIAL_RESEARCH_API_BASE || "";
  if (!apiBase) {
    if (state.mode === "upload") {
      try { validateFiles([...$("#pdf-files").files]); } catch (error) { showToast(error.message); return; }
    }
    setStatus({ title: "Mock preview loaded", description: "No request was sent. This illustrative report stays visible as a UI preview until a backend API URL is configured.", status: "idle", stage: "intake", runId: "DEMO RESULT" });
    showToast("Preview only — add a backend API URL to submit research.");
    return;
  }
  await startLiveResearch(new ResearchApiClient(apiBase));
}

async function loadMockResult() {
  try {
    const response = await fetch("mock_research_result.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Mock result returned ${response.status}`);
    const mock = await response.json();
    renderReport(mock);
  } catch (error) {
    if (location.protocol === "file:") {
      renderReport(FILE_PROTOCOL_MOCK_FALLBACK);
      showToast("Standalone file preview loaded with bundled mock data.");
    } else {
      $("#report-sections").innerHTML = `<article class="report-card"><h3>Mock report unavailable</h3><p>Could not load mock_research_result.json. ${html(error.message)}</p></article>`;
      showToast("Could not load the mock JSON report.");
    }
  }
}

function bindEvents() {
  $$(".mode-tab").forEach(tab => tab.addEventListener("click", () => setMode(tab.dataset.mode)));
  $("#research-form").addEventListener("submit", startResearch);
  $("#browse-files").addEventListener("click", () => $("#pdf-files").click());
  $("#pdf-files").addEventListener("change", updateFiles);
  const dropZone = $("#drop-zone");
  ["dragenter", "dragover"].forEach(type => dropZone.addEventListener(type, event => { event.preventDefault(); dropZone.classList.add("drag-over"); }));
  ["dragleave", "drop"].forEach(type => dropZone.addEventListener(type, event => { event.preventDefault(); dropZone.classList.remove("drag-over"); }));
  dropZone.addEventListener("drop", event => {
    const transfer = new DataTransfer();
    [...event.dataTransfer.files].filter(file => file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")).forEach(file => transfer.items.add(file));
    $("#pdf-files").files = transfer.files;
    updateFiles();
    if (transfer.files.length !== event.dataTransfer.files.length) showToast("Only PDF files can be uploaded.");
  });
  $("#research-question").addEventListener("input", event => { $("#char-count").textContent = `${event.target.value.length} / 500`; });
  $("#char-count").textContent = `${$("#research-question").value.length} / 500`;
  $("#start-year").addEventListener("change", () => { if (Number($("#end-year").value) < Number($("#start-year").value)) $("#end-year").value = $("#start-year").value; });
  $("#end-year").addEventListener("change", () => { if (Number($("#start-year").value) > Number($("#end-year").value)) $("#start-year").value = $("#end-year").value; });
  $("#copy-link").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href.split("#")[0] + "#report"); showToast("Report link copied."); }
    catch { showToast("Copy the page address to share this report view."); }
  });
  $(".status-chevron").addEventListener("click", () => $(".status-card").classList.toggle("status-collapsed"));
}

setupPeriods();
bindEvents();
loadMockResult();

# Phase 5 UAT Test Cases (HF Space + Chainlit + FastAPI)

Date: 2026-02-20  
Owner: Product/QA  
Target build: Phase 5 increment 1

## 1) Purpose

This document defines manual UAT scenarios for Phase 5 production behavior on Hugging Face Spaces, including Chainlit chat UX, API routes, readiness/health checks, runtime key handling, and fallback behavior.

## 2) Test Environments

- Runtime app domain (required for route tests): `https://sunkistcat-lattice.hf.space`
- Hub page (metadata/repo page only): `https://huggingface.co/spaces/sunkistCAT/lattice`

Important:
- Route checks like `/health`, `/ready`, and `/chainlit` must be tested on `*.hf.space`.
- The Hub page URL is not the runtime route host.

## 3) Preconditions

- Space status is `Running`.
- Space secrets configured (as applicable):
  - `GEMINI_API_KEY` or `GOOGLE_API_KEY`
  - `SUPABASE_URL`, `SUPABASE_KEY`
  - `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
- Space variables configured (as applicable):
  - `USE_REAL_SUPABASE`, `USE_REAL_NEO4J`, `ALLOW_SEEDED_FALLBACK`
  - `PUBLIC_DEMO_QUERY_LIMIT`
- Tester has browser + terminal (`curl`) access.

## 4) Execution Notes

- Use one browser tab for anonymous/public demo behavior.
- Use a separate fresh/incognito tab to verify session isolation.
- Record status code + body snippet for all API checks.
- Mark each case as `Pass` / `Fail` / `Blocked`.

## 5) UAT Cases

## A. Domain and Routing

| ID | Action | Expected Result |
|---|---|---|
| UAT-A01 | Open `https://huggingface.co/spaces/sunkistCAT/lattice` | Hub page loads (repo-style page), not app routes. |
| UAT-A02 | Open `https://huggingface.co/spaces/sunkistCAT/lattice/health` | Not app response (likely 404/Hub page behavior). |
| UAT-A03 | Open `https://sunkistcat-lattice.hf.space/` | Redirects to `/docs` (307 redirect behavior acceptable). |
| UAT-A04 | Open `https://sunkistcat-lattice.hf.space/docs` | FastAPI Swagger docs page loads. |
| UAT-A05 | Open `https://sunkistcat-lattice.hf.space/chainlit` | Chainlit UI loads without server error. |

## B. Health and Readiness APIs

| ID | Action | Expected Result |
|---|---|---|
| UAT-B01 | `GET /health` | HTTP 200, JSON contains `{"ok": true}`. |
| UAT-B02 | `GET /ready` in seeded-only mode | HTTP 200, `ready: true`, connector modes show `seeded_only` or `seeded_fallback`. |
| UAT-B03 | `GET /ready` with real connectors configured | HTTP 200, `ready: true`, connector modes may show `real`. |
| UAT-B04 | `GET /ready` with real connectors enabled but missing creds and fallback disabled | HTTP 503, `ready: false`, connector mode includes `misconfigured`. |
| UAT-B05 | `GET /ready` response body | Includes `connectors.supabase`, `connectors.neo4j`, `retriever_mode`, `gemini`. |
| UAT-B06 | `GET /health/data` when connectors reachable | HTTP 200, connector status reports usable diagnostics. |
| UAT-B07 | `GET /health/data` when connectors unreachable and fallback disabled | HTTP 503 with clear reason fields in body. |

## C. API Query Endpoint

| ID | Action | Expected Result |
|---|---|---|
| UAT-C01 | `POST /api/prototype/query` with valid JSON question | HTTP 200; JSON has `question`, `route`, `answer`, `snippets`. |
| UAT-C02 | Send question: `How does the project timeline compare to graph dependencies?` | Answer returns with sources/snippets list (may be seeded or real). |
| UAT-C03 | Send question with direct-intent greeting | Route may resolve to `direct`; response stays well-formed. |
| UAT-C04 | Send empty question payload `{"question":""}` | Validation error (422) with field-level details. |
| UAT-C05 | Send malformed payload `{}` | Validation error (422). |
| UAT-C06 | Use `X-Gemini-Api-Key` header on one request only | Request succeeds; no persistence implied in subsequent requests without header. |
| UAT-C07 | Submit very long question (>=500 chars) | Request handled without crash; response remains valid JSON contract. |
| UAT-C08 | Trigger low-confidence retrieval scenario | Response still returns; quality guardrails text/citations appear as designed. |

## D. Chainlit Onboarding and Commands

| ID | Action | Expected Result |
|---|---|---|
| UAT-D01 | Open `/chainlit` fresh session | Welcome message includes quota and command guidance. |
| UAT-D02 | Type `/help` and press Send button | Command list appears with `/setkey`, `/clearkey`, `/help`. |
| UAT-D03 | Type `/setkey <valid-looking-key>` | Confirmation message appears with masked key (not full plaintext). |
| UAT-D04 | Type `/clearkey` after setkey | Session key removal confirmation appears. |
| UAT-D05 | Type normal user message and click Send | Router step appears; answer returns with `Sources:` block. |
| UAT-D06 | Press Enter to submit message (without clicking Send) | Message sends and response behavior matches Send button path. |
| UAT-D07 | Use command with extra spaces `/setkey    abc123` | Key still accepted after trimming or clear guidance shown. |
| UAT-D08 | Type `/setkey` without value | No crash; handled as normal text or graceful guidance response. |
| UAT-D09 | Ask multiple questions anonymously | Footer shows decreasing remaining public demo queries. |
| UAT-D10 | Reach anonymous quota limit | App blocks further anonymous questions and prompts `/setkey`. |
| UAT-D11 | After quota reached, set key then ask again | Query allowed; footer indicates session key mode active. |
| UAT-D12 | Clear key after quota reached, ask again | Quota behavior re-applies for anonymous state. |
| UAT-D13 | Open second incognito session | Demo quota starts fresh and key session is isolated. |
| UAT-D14 | Refresh browser in same session | Session behavior remains consistent with Chainlit session handling. |
| UAT-D15 | Copy/paste multiline question and send | Response still includes answer + sources without UI breakage. |

## E. Source Grounding and Quality UX

| ID | Action | Expected Result |
|---|---|---|
| UAT-E01 | Ask for factual response requiring retrieval | Output includes source references (`Sources:` and snippet lines). |
| UAT-E02 | Ask unsupported/off-domain question | Graceful fallback message, no stack trace/internal error leak. |
| UAT-E03 | Ask ambiguous question then clarify | Second response reflects clarified intent and updated snippets. |
| UAT-E04 | Scenario with no snippets | User receives explicit no-context guidance text. |
| UAT-E05 | Moderate/low confidence scenario | Confidence guidance note appears when applicable; no malformed text. |

## F. Security and Secrets Handling (UAT-Level)

| ID | Action | Expected Result |
|---|---|---|
| UAT-F01 | Review repository files in deployed revision | No production secret values committed in files. |
| UAT-F02 | Use `/setkey` then inspect chat output | Key appears masked; full key not echoed back. |
| UAT-F03 | Trigger retrieval/config error | User-facing output does not expose sensitive internals/credentials. |
| UAT-F04 | API request with invalid key header value | Request fails gracefully or uses fallback path; no server crash. |
| UAT-F05 | Confirm key not persisted across new sessions | New session has no inherited runtime key. |

## G. Deployment and Operational Runbook Validation

| ID | Action | Expected Result |
|---|---|---|
| UAT-G01 | Deploy via `./scripts/deploy_hf.sh` | Deployment command completes; Space rebuild starts. |
| UAT-G02 | Wait for Space status to return `Running` | Runtime routes become available on `*.hf.space`. |
| UAT-G03 | Run post-deploy quick checks (`/health`, `/ready`, `/chainlit`) | All pass according to runbook expectations. |
| UAT-G04 | Validate `/docs` availability post-deploy | API docs load without runtime errors. |
| UAT-G05 | Validate one end-to-end chat question | UI returns answer + source list after deploy. |

## H. Negative and Resilience Cases

| ID | Action | Expected Result |
|---|---|---|
| UAT-H01 | Send rapid repeated messages (3-5 quickly) | No UI crash; responses remain coherent and session survives. |
| UAT-H02 | Temporarily disable one connector env (test env) | System continues with fallback behavior when configured. |
| UAT-H03 | Disable fallback and keep connector misconfigured (test env) | `/ready` reports not ready (503), errors remain graceful. |
| UAT-H04 | Submit unexpected unicode/symbol-heavy question | Response remains valid; no encoding/server errors. |
| UAT-H05 | Browser back/forward between `/docs` and `/chainlit` | Navigation remains stable; routes resolve correctly. |

## 6) Suggested Test Messages

Use these exact prompts in Chainlit and API tests:

1. `How does the project timeline compare to graph dependencies?`
2. `Show ownership links for the onboarding deliverables.`
3. `What are the key risks and mitigations in this prototype?`
4. `Hello` (direct-route style check)
5. `Summarize evidence for Phase 5 readiness.`
6. `What is the capital of Mars?` (unsupported/fallback behavior)

## 7) API Curl Snippets

```bash
# Health
curl -i https://sunkistcat-lattice.hf.space/health

# Readiness
curl -i https://sunkistcat-lattice.hf.space/ready

# Data health
curl -i https://sunkistcat-lattice.hf.space/health/data

# Prototype query
curl -i -X POST https://sunkistcat-lattice.hf.space/api/prototype/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How does the project timeline compare to graph dependencies?"}'

# Prototype query with runtime key override
curl -i -X POST https://sunkistcat-lattice.hf.space/api/prototype/query \
  -H "Content-Type: application/json" \
  -H "X-Gemini-Api-Key: YOUR_RUNTIME_KEY" \
  -d '{"question":"Summarize evidence for Phase 5 readiness."}'
```

## 8) UAT Sign-Off Checklist

- [ ] Domain routing behavior validated (`hub` vs `hf.space`).
- [ ] Core runtime endpoints pass (`/health`, `/ready`, `/health/data`).
- [ ] `/chainlit` onboarding + commands pass in normal and edge flows.
- [ ] Quota flow and key escalation behavior validated end-to-end.
- [ ] API contract remains stable for valid and invalid payloads.
- [ ] Error/fallback behavior is graceful and non-leaky.
- [ ] Post-deploy runbook checks all pass.
- [ ] UAT defects (if any) logged with reproduction steps and screenshots.

## 9) Defect Log Template

```markdown
### DEFECT-ID: UAT-XXX
- Test case: UAT-<ID>
- Environment: <hf.space / local>
- Steps to reproduce:
  1. ...
  2. ...
- Expected:
- Actual:
- Severity: <Blocker/High/Medium/Low>
- Evidence: <screenshot/log/curl output>
- Status: <Open/In Progress/Resolved>
```

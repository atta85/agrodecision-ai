# 🌱 AgroDecision AI

Human-in-the-loop, multi-agent **decision support** for crop-health problems.
Built with **CrewAI + Groq + Streamlit**. Free tools only. The farmer/manager always makes the final decision.

> This is a research prototype. It supports decisions; it does not replace an agronomist.
> Any chemical use must be confirmed by an expert and checked against local rules.

---

## What it does

1. **Intake** (English, Urdu, Punjabi/Shahmukhi, Sindhi, Roman Urdu): location (country → province → city → geocoded), crop, symptoms,
   how many plants look affected (marked as a *farmer estimate*), optional photos (1–3, JPG/PNG/PDF, ≤10 MB each) and optional camera.
2. **Confirm understanding**: the app reads back what it understood in your language before spending any AI quota.
3. **Evidence gathering** (deterministic tools, no AI guessing): Open-Meteo weather, SoilGrids soil estimate, optional Tavily web search on an
   allow-list of trusted domains, optional OpenAlex papers. Every item gets a **source ID** (U1, W1, S1, P1, T1, R1, O1, D1).
4. **Seven agents (CrewAI)**: Monitoring → Diagnosis → Intervention → Cost/Economic → Supply/Operations → Risk/Compliance → Critic
   (+ a plain-language report writer). Agents may cite **only** the evidence block; invented IDs are stripped and a "verified" flag without a
   source is downgraded to "needs confirmation".
5. **Deterministic maths**: `C_total = materials + labour + equipment + operation (+ diagnostics)` and `EC = C_intervention + P_loss × C_loss`.
   Cost and Supply are computed by plain Python (auditable). In "Full review notes" mode their agents also write short notes.
6. **Human decision gate**: APPROVE · MODIFY (edit quantities and P(loss), live recalculation) · REJECT · MORE INFORMATION (re-run with new facts).
7. **History**: decisions and later outcomes are stored (SQLite) with JSON/Markdown downloads.

Optional own documents (SOP PDF/TXT, price CSV, inventory CSV) can be added. Without them the app uses built-in **placeholder** prices and
generic rules, and says so on screen.

---

## Deployment – step by step (no local code needed)

### Step 0 – Accounts (all free)
| Need | Where |
|---|---|
| GitHub account | https://github.com/signup |
| Groq API key | https://console.groq.com/keys |
| Streamlit Community Cloud | https://share.streamlit.io (sign in with GitHub) |
| *(optional)* Tavily key for web search | https://app.tavily.com |

### Step 1 – Unzip
Unzip `agrodecision-ai.zip` on your computer. You get a folder `agrodecision-ai/` containing `app.py`, `requirements.txt`, `agrodecision/`, `data/`, `tests/`, `.streamlit/` …

### Step 2 – Create a NEW GitHub repository (important: use a fresh, empty one)
Stale files from earlier attempts are the most common reason for repeated errors, so start clean: use a **new repository** (or delete all old files first).
1. On GitHub click **+ → New repository**. Name: `agrodecision-ai`. Choose **Private** (recommended) or Public. Do **not** add a README/.gitignore. Click **Create repository**.
2. On the new empty repo page click **uploading an existing file**.
3. Open the unzipped folder and drag **the contents** (not the folder itself) into the browser: `app.py`, `requirements.txt`, `README.md`, `agrodecision/`, `data/`, `tests/`, and the hidden items `.streamlit/`, `.gitignore`, `.python-version`.
4. Click **Commit changes**.
5. **Check** that `app.py` is at the *top level* of the repo and that `agrodecision/` and `data/` show their files. Some browsers skip hidden folders when dragging: if `.streamlit/config.toml` is missing, click **Add file → Create new file**, type `.streamlit/config.toml` as the name and paste the file's contents. (The app still works without it; it enforces the 10 MB limit itself.)

*(Alternative: GitHub Desktop or `git add . && git commit && git push`.)*

### Step 3 – Deploy on Streamlit Community Cloud
1. Go to https://share.streamlit.io → **Create app** → **Deploy a public app from GitHub** (private repos work after you authorise GitHub access).
2. Repository: `your-user/agrodecision-ai` · Branch: `main` · Main file path: `app.py`.
3. Click **Advanced settings**:
   * **Python version: 3.12** (choose it *before* deploying – it cannot be changed afterwards without redeploying). Only 3.12 is supported; the app shows an error on any other version.
   * **Secrets**: paste the block below (see also `.streamlit/secrets.toml.example`).
4. Click **Deploy**. The first build installs CrewAI and takes a few minutes.
5. **Verify you are running the right code:** open the sidebar (top-left arrow). The bottom must say **`Build 0.2.0 | Python 3.12`**. If it shows another build, the old files are still deployed – re-upload and reboot.

```toml
GROQ_API_KEY = "gsk_your_key_here"
APP_ACCESS_CODE = "choose-a-code"      # strongly recommended: protects your free Groq quota
# TAVILY_API_KEY = "tvly-..."          # optional web search
# OPENALEX_MAILTO = "you@example.com"  # optional
# DEMO_MODE = "false"
```
To change secrets later: app menu (⋮) → **Settings → Secrets**, then reboot the app.

### Step 4 – First check with Demo Mode (no key needed)
Set `DEMO_MODE = "true"` in Secrets, open the app, fill the form, **Continue → Yes → …** You should see a sample citrus analysis, the cost table,
and the decision buttons. Then set `DEMO_MODE = "false"` and reboot.

### Step 5 – First real run
Use a small case (1 photo, English). Expect **3–6 minutes** on the free tier: the app deliberately spaces requests to stay under Groq's
tokens-per-minute cap (default 8,000 – set `TPM_LIMIT` if your Groq console shows a different number).
If a model name is rejected, open https://console.groq.com/docs/rate-limits, pick current model IDs, and set `MODEL_REASONING`, `MODEL_LIGHT`, `MODEL_VISION`, `MODEL_TRANSLATE` in Secrets.

### Step 6 – Share
Send the app URL (and the access code) to your users. Free apps go to sleep after a period of inactivity; opening the link wakes them.

---

## References, citation check and PDF (build 0.3.0)
* **Curated reference library** – `data/references.json` holds vetted documents (FAO, WHO, university extension, peer-reviewed). Each entry lists publisher, year, link and a short description of what the document covers. The app searches it by keyword and gives matching entries source IDs `L1, L2 ...`. **Add your own entries** in the same format after an agronomist has reviewed the source. The starter list was checked for existence and scope only.
* **Paper search needs a free OpenAlex key** (since Feb 2026): create one at openalex.org/settings/api and add `OPENALEX_API_KEY` to Secrets. Without it the app skips papers when OpenAlex answers `429 Too Many Requests` and carries on.
* **Web and paper references** – trusted-domain web search (Tavily, optional) now runs up to three searches per case (symptoms, leading cause, second cause); web results are labelled by type (UN agency, government, university, other). OpenAlex papers are labelled as abstract-only.
* **Citation check** – every statement that cites sources gets a traceability level (supported / partial / weak / no source) from a keyword-overlap check. It shows whether the wording can be traced to the cited text; it is **not proof** that the source supports the claim.
* **PDF report** – press **Prepare PDF report**, then **Download PDF** (also available for old cases in History). It contains summary, data quality, causes, options and cost breakdown, risk flags, critic review, decision record, citation check and a full bibliography. Urdu, Punjabi (Shahmukhi) and Roman Urdu summaries are included; the Sindhi summary is not printed because the built-in PDF font cannot draw all Sindhi letters.

## Optional document formats
* **Prices CSV** – columns `key,label,unit,category,unit_cost` (only `key,unit_cost` required). Keys must match the catalogue in `data/default_prices.json`
  (you can add new keys; the Intervention agent only sees catalogue keys). See `data/sample_prices.csv`. You can also edit prices directly in the sidebar.
* **Inventory CSV** – `key,on_hand,lead_time_days,min_order_qty`. See `data/sample_inventory.csv`.
* **SOP** – PDF (with a text layer) or TXT. It is searched by simple keyword matching (no embeddings) and the best excerpts are shown to the Risk agent.

## Free-tier facts to keep in mind
* **Groq**: limits are per organisation; the tokens-per-minute cap is usually hit first. One analysis uses roughly 15–25K tokens (photos ≈ 2K each).
  With ~200K tokens/day you can expect on the order of 8–12 analyses per day. Check current limits in the Groq console.
* **Streamlit Community Cloud storage is temporary**: the SQLite history is wiped when the app restarts or redeploys. Use the download buttons in **History**.
* **SoilGrids** public REST API is beta, rate-limited and sometimes paused. The app continues without it and says so. It has no salinity layer – salinity needs a lab test.
* **Open-Meteo** is free for non-commercial use (attribution required). Check their terms before commercial use.
* **Tavily** free plan: about 1,000 credits/month; each case uses about 2.

## Honest limitations
* The code was tested against a strict local imitation of Groq's API (using the real `groq` SDK and real CrewAI), not against the live Groq service. The first real run may still need model-ID tweaks (see Troubleshooting).
* Translations of interface labels are a **first draft**. Have native speakers (especially Punjabi and Sindhi) review `agrodecision/i18n.py`. Model translation quality for Urdu/Punjabi/Sindhi varies; that is why the app shows a read-back and lets the user correct it.
* Voice input is **not** included (speech models are weak on Punjabi/Sindhi/Urdu). It can be added later.
* Photo analysis describes what is visible; it is not a diagnosis. Farmer percentages are estimates and are labelled as such.
* Placeholder prices are not market prices. Replace them before trusting any cost comparison.
* P(loss) values are model assumptions the human can edit; treat all economic numbers as scenario estimates, not forecasts.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Error mentioning `chroma_server_nofile` or a Python-version message | The app is not on Python 3.12. Delete the app, recreate it and choose 3.12 in Advanced settings. |
| Error mentioning `cache_breakpoint` | Fixed in build 0.2.0 (the app talks to Groq directly and sends only `role` and `content`). If you still see it, the OLD code is deployed: check the sidebar build stamp. |
| Build fails on Streamlit Cloud | Confirm **Python 3.12** in Advanced settings; check `requirements.txt` is at the repo root. |
| "GROQ_API_KEY is missing" | Add it under Settings → Secrets (TOML syntax, quotes around the value), reboot. |
| "model not found / decommissioned" | Update model IDs in Secrets (see Step 5). |
| Request too large / rate limit | Lower `TPM_LIMIT` to match your account, use fewer/smaller photos, keep "Full review notes" off. |
| Error mentioning `reasoning_effort` | Set `REASONING_EFFORT = ""` in Secrets. |
| No soil data | SoilGrids is down or paused; the app continues. Enter soil type manually. |
| Urdu/Sindhi text looks cramped | Adjust the CSS in `inject_css()` in `app.py` (font/line-height). |
| History disappeared | Streamlit Cloud storage is temporary; download regularly. |

## Project layout
```
app.py                     Streamlit UI (form, confirm, run, decision gate, history)
agrodecision/
  agents.py                CrewAI agents + prompts (each agent = single-task Crew)
  pipeline.py              orchestrator: evidence -> agents -> costs -> report
  costing.py               deterministic cost / supply maths
  llm.py                   direct Groq SDK calls, CrewAI adapter (GroqLLM), token-per-minute limiter, JSON extraction
  translate.py  media.py   language read-back / summary translation; photos & PDFs
  sources.py    schemas.py source registry (citations) and Pydantic schemas
  rag_lite.py   storage.py keyword SOP retrieval; SQLite history
  i18n.py       demo.py    UI text in 5 languages; demo mode
  tools/                   weather (Open-Meteo), soil (SoilGrids), search (Tavily), scholar (OpenAlex)
data/                      placeholder prices, generic rules, allowed domains, glossary, sample CSVs
tests/                     offline tests (mock LLM, headless UI)
```
Optional local check (Python 3.12): `pip install -r requirements.txt pytest && python -m pytest -q`. The tests include a strict local imitation of the Groq API.

## Data attribution
Weather: Open-Meteo.com (CC BY 4.0). Soil: ISRIC SoilGrids (CC BY 4.0). Papers: OpenAlex. Web: Tavily search restricted to `data/allowed_domains.json`.

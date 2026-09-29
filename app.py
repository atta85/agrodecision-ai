"""AgroDecision AI - Streamlit front end.

Flow: form -> confirm understanding -> agents run -> results + HUMAN DECISION GATE -> history.
"""
from __future__ import annotations

import hmac
import json
import sys
import traceback

import pandas as pd
import streamlit as st

st.set_page_config(page_title="AgroDecision AI", page_icon="🌱", layout="centered")

# This app is built and tested for Python 3.12 only (CrewAI's dependencies break on 3.14).
if sys.version_info[:2] != (3, 12):
    st.error(
        f"This app is running on Python {sys.version_info.major}.{sys.version_info.minor}, but it needs Python 3.12. "
        "On Streamlit Community Cloud: delete the app, create it again, and in 'Advanced settings' choose "
        "Python 3.12 (the version cannot be changed after deployment). See README, Step 3."
    )
    st.stop()

import agrodecision  # noqa: E402
from agrodecision import costing, i18n, storage  # noqa: E402
from agrodecision.config import COUNTRIES, settings  # noqa: E402
from agrodecision.export import to_markdown  # noqa: E402
from agrodecision.llm import MissingKeyError, set_status_callback  # noqa: E402
from agrodecision.citations import summarize as summarize_checks  # noqa: E402
from agrodecision.media import pdf_extract  # noqa: E402
from agrodecision.pdf_report import build_pdf  # noqa: E402
from agrodecision.pipeline import Uploads, run_analysis  # noqa: E402
from agrodecision.schemas import CaseInput, FarmerSummary, Report  # noqa: E402
from agrodecision.tools import weather  # noqa: E402
from agrodecision.translate import translate_summary, understand_input  # noqa: E402

S = settings()

FORM_KEYS = ["f_country", "f_province", "f_city", "f_geo_idx", "f_lat", "f_lon", "f_crop", "f_crop_other", "f_stage",
             "f_area", "f_unit", "f_symptoms", "f_affected", "f_onset", "f_spread", "f_irrigation", "f_soil",
             "f_desc", "f_currency", "f_value", "f_ec", "f_ph", "f_temp"]


# ------------------------------------------------------------------------------------- helpers
def T(key: str) -> str:
    return i18n.t(key, st.session_state.lang)


def init_state() -> None:
    d = st.session_state
    d.setdefault("lang", "en")
    d.setdefault("stage", "form")
    d.setdefault("files", [])
    d.setdefault("uploads", {"sop_text": "", "prices_upload": None, "inventory": None})
    d.setdefault("case", None)
    d.setdefault("form_view", {})
    d.setdefault("form_saved", {})
    d.setdefault("geo_results", None)
    d.setdefault("understood", None)
    d.setdefault("report", None)
    d.setdefault("case_id", None)
    d.setdefault("run_error", None)


def inject_css(lang: str) -> None:
    css = """<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic:wght@400;700&family=Noto+Nastaliq+Urdu:wght@400;700&display=swap');
    .block-container {padding-top: 2rem; padding-bottom: 4rem;}
    </style>"""
    if lang in i18n.RTL:
        font = "'Noto Naskh Arabic'" if lang == "sd" else "'Noto Nastaliq Urdu'"
        lh = "1.9" if lang != "sd" else "1.7"
        css += f"""<style>
        .stApp label, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp li, .stApp textarea,
        .stApp input, .stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stAlertContainer"] {{
            direction: rtl; text-align: right; font-family: {font}, 'Segoe UI', sans-serif; line-height: {lh};
        }}
        </style>"""
    st.markdown(css, unsafe_allow_html=True)


def price_table_to_dict(df: pd.DataFrame) -> dict:
    out = {}
    for r in df.itertuples():
        out[str(r.key)] = {"label": r.label, "unit": r.unit, "category": r.category, "unit_cost": float(r.unit_cost)}
    return out


def price_override() -> dict | None:
    """Rows edited in the sidebar table + rows from an uploaded CSV (upload wins)."""
    base = costing.default_prices()
    edited = st.session_state.get("prices_current")
    override: dict = {}
    if edited is not None:
        for k, v in price_table_to_dict(edited).items():
            if k not in base or abs(base[k]["unit_cost"] - v["unit_cost"]) > 1e-9:
                override[k] = v
    up = st.session_state.uploads.get("prices_upload")
    if up:
        override.update(up)
    return override or None


def effective_prices() -> dict:
    return costing.merge_prices(costing.default_prices(), price_override())


def structured_en(case: CaseInput) -> str:
    return (f"crop={case.crop}; stage={case.growth_stage}; symptoms={case.symptoms}; affected={case.affected_range}; "
            f"onset={case.onset}; spreading={case.spread}; irrigation={case.irrigation}; soil={case.soil_texture_user}")


def reset_case() -> None:
    for k in list(st.session_state.keys()):
        if k.startswith(("f_", "res_", "mod_", "dec_", "geo_")):
            del st.session_state[k]
    st.session_state.update(stage="form", files=[], case=None, form_view={}, form_saved={}, geo_results=None,
                            understood=None, report=None, case_id=None, run_error=None,
                            uploads={"sop_text": "", "prices_upload": None, "inventory": None})


# ------------------------------------------------------------------------------------- sidebar
def render_sidebar() -> None:
    with st.sidebar:
        st.header("⚙️ Settings")
        if S.demo_mode:
            st.warning("DEMO MODE is ON: the app shows a sample analysis and calls no external service.")
        elif not S.groq_api_key:
            st.error("GROQ_API_KEY is missing. Add it in the app's Secrets (or set DEMO_MODE = \"true\").")
        st.checkbox("Full review notes (Cost & Supply agents also write notes; uses more free tokens)",
                    key="full_notes", value=False)
        st.subheader("Unit prices")
        st.caption("PLACEHOLDER prices, not market prices. Edit the numbers - results update immediately.")
        base = costing.default_prices()
        df = pd.DataFrame([{"key": k, "label": v["label"], "unit": v["unit"], "category": v["category"],
                            "unit_cost": v["unit_cost"]} for k, v in base.items()])
        edited = st.data_editor(df, hide_index=True, disabled=["key", "label", "unit", "category"],
                                key="prices_editor", width="stretch")
        st.session_state["prices_current"] = edited
        st.caption(f"Build {agrodecision.__version__} | Python {sys.version_info.major}.{sys.version_info.minor}")
        if not S.demo_mode and st.button("🔧 Test Groq connection", key="btn_selftest"):
            from agrodecision.selftest import run_selftest

            with st.spinner("Testing..."):
                for name, ok, detail in run_selftest():
                    (st.success if ok else st.error)(f"{name}: {detail}")
        st.caption(f"Models: {S.model_reasoning} / {S.model_light} / vision {S.model_vision}")


# ------------------------------------------------------------------------------------- form
def restore_form() -> None:
    for k, v in st.session_state.form_saved.items():
        if k not in st.session_state:
            st.session_state[k] = v


def read_docs(sop_file, price_file, inv_file) -> tuple[dict, list[str]]:
    errs: list[str] = []
    up = {"sop_text": "", "prices_upload": None, "inventory": None}
    try:
        if sop_file is not None:
            raw = sop_file.getvalue()
            if sop_file.name.lower().endswith(".pdf"):
                text, _ = pdf_extract(raw, max_pages=20, min_text_chars=1)
                up["sop_text"] = text
            else:
                up["sop_text"] = raw.decode("utf-8", errors="ignore")
        if price_file is not None:
            up["prices_upload"] = costing.parse_prices_csv(price_file.getvalue())
        if inv_file is not None:
            up["inventory"] = costing.parse_inventory_csv(inv_file.getvalue())
    except Exception as e:  # noqa: BLE001
        errs.append(f"Could not read a document: {e}")
    return up, errs


def render_form(lang: str) -> None:
    restore_form()
    st.subheader(T("step1"))
    st.caption(T("tagline"))

    # ---- location
    st.markdown(f"**{T('region')}**")
    country = st.selectbox(T("country"), list(COUNTRIES), key="f_country")
    province = st.text_input(T("province"), key="f_province")
    city = st.text_input(T("city"), key="f_city")
    if st.button(T("find_place"), key="btn_geo"):
        if city.strip():
            try:
                res = weather.geocode(city.strip(), COUNTRIES[country])
                p = province.strip().lower()
                if p:
                    res.sort(key=lambda r: 0 if p in (r.get("admin1", "") or "").lower() else 1)
                st.session_state.geo_results = res
                st.session_state.pop("f_geo_idx", None)
            except Exception as e:  # noqa: BLE001
                st.warning(f"Location lookup failed ({e}). You can continue without location.")
                st.session_state.geo_results = []
        else:
            st.warning("Please type a city / town / village first.")
    lat = lon = None
    res = st.session_state.geo_results
    if res:
        labels = [f"{r['name']}, {r.get('admin1', '')}, {r.get('country', '')} ({r['lat']:.2f}, {r['lon']:.2f})" for r in res]
        idx = st.selectbox(T("pick_place"), list(range(len(res))), format_func=lambda i: labels[i], key="f_geo_idx")
        lat, lon = res[idx]["lat"], res[idx]["lon"]
    elif res is not None:
        st.info(T("no_place"))
        c1, c2 = st.columns(2)
        lat = c1.number_input("Latitude", value=None, min_value=-90.0, max_value=90.0, format="%.4f", key="f_lat")
        lon = c2.number_input("Longitude", value=None, min_value=-180.0, max_value=180.0, format="%.4f", key="f_lon")

    # ---- crop
    st.divider()
    fmt = lambda g: (lambda k: i18n.opt_label(g, k, lang))  # noqa: E731
    crop_key = st.selectbox(T("crop"), i18n.opt_keys("crop"), format_func=fmt("crop"), key="f_crop")
    crop_other = st.text_input(T("crop_other"), key="f_crop_other") if crop_key == "other" else ""
    stage_key = st.selectbox(T("stage"), i18n.opt_keys("stage"), format_func=fmt("stage"), key="f_stage", index=5)
    a1, a2 = st.columns([2, 1])
    area = a1.number_input(T("area"), min_value=0.0, value=None, step=0.5, key="f_area")
    unit = a2.selectbox(T("area_unit"), i18n.AREA_UNITS, key="f_unit")

    # ---- symptoms
    st.divider()
    symptoms = st.multiselect(T("symptoms"), i18n.opt_keys("symptoms"), format_func=fmt("symptoms"), key="f_symptoms")
    affected = st.selectbox(T("affected"), i18n.opt_keys("affected"), format_func=fmt("affected"), key="f_affected", index=4)
    onset = st.selectbox(T("onset"), i18n.opt_keys("onset"), format_func=fmt("onset"), key="f_onset", index=3)
    spread = st.selectbox(T("spread"), i18n.opt_keys("spread"), format_func=fmt("spread"), key="f_spread", index=3)
    irrigation = st.selectbox(T("irrigation"), i18n.opt_keys("irrigation"), format_func=fmt("irrigation"), key="f_irrigation", index=4)
    soil_key = st.selectbox(T("soil"), i18n.opt_keys("soil"), format_func=fmt("soil"), key="f_soil", index=4)
    desc = st.text_area(T("describe"), height=140, help=T("describe_help"), key="f_desc")

    # ---- photos
    st.divider()
    st.markdown(f"**{T('photos_hdr')}**")
    st.caption(T("photos_help"))
    uploads = st.file_uploader(T("photos_hdr"), type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True,
                               label_visibility="collapsed", key="f_files")
    with st.expander(T("camera")):
        cam = st.camera_input(T("camera"), label_visibility="collapsed", key="f_cam")
    if st.session_state.files and not uploads and not cam:
        st.caption("Already attached: " + ", ".join(n for n, _ in st.session_state.files) + " (choose new files to replace them)")

    # ---- money + measurements + documents
    st.divider()
    st.markdown(f"**{T('money_hdr')}**")
    m1, m2 = st.columns(2)
    currency = m1.selectbox(T("currency"), i18n.CURRENCIES, key="f_currency")
    value = m2.number_input(T("value_at_risk"), min_value=0.0, value=None, step=1000.0, key="f_value")
    with st.expander(T("measure_hdr")):
        ec = st.number_input(T("ec"), min_value=0.0, value=None, key="f_ec")
        ph = st.number_input(T("ph"), min_value=0.0, max_value=14.0, value=None, key="f_ph")
        temp = st.number_input(T("temp"), value=None, key="f_temp")
    with st.expander(T("docs_hdr")):
        sop_file = st.file_uploader(T("sop"), type=["pdf", "txt"], key="f_sop")
        price_file = st.file_uploader(T("prices"), type=["csv"], key="f_pricecsv")
        inv_file = st.file_uploader(T("inventory"), type=["csv"], key="f_invcsv")
        st.caption("Sample formats are in the repository's data/ folder (sample_prices.csv, sample_inventory.csv).")

    st.caption(T("disclaimer"))

    if st.button(T("continue"), type="primary", key="btn_continue"):
        errors: list[str] = []
        if not symptoms and not desc.strip():
            errors.append("Please select at least one symptom or describe the problem.")
        crop_en = crop_other.strip() if crop_key == "other" else i18n.opt_en("crop", crop_key)
        if crop_key == "other" and not crop_en:
            errors.append("Please type the crop name.")
        files: list[tuple[str, bytes]] = []
        for f in (uploads or []):
            files.append((f.name, f.getvalue()))
        if cam is not None:
            files.append(("camera.jpg", cam.getvalue()))
        if not files and st.session_state.files:
            files = list(st.session_state.files)
        if len(files) > S.max_images:
            errors.append(f"Please attach at most {S.max_images} photos/files (you attached {len(files)}).")
        for n, b in files:
            if len(b) > S.max_upload_mb * 1024 * 1024:
                errors.append(f"{n} is larger than {S.max_upload_mb} MB.")
        docs, derrs = read_docs(sop_file, price_file, inv_file)
        errors += derrs
        if errors:
            for e in errors:
                st.error(e)
        else:
            case = CaseInput(
                language=lang, country=country, country_code=COUNTRIES[country], province=province.strip(), city=city.strip(),
                lat=lat, lon=lon, crop=crop_en, growth_stage=i18n.opt_en("stage", stage_key),
                area=area, area_unit=unit, symptoms=[i18n.opt_en("symptoms", k) for k in symptoms],
                affected_range=i18n.opt_en("affected", affected), onset=i18n.opt_en("onset", onset),
                spread=i18n.opt_en("spread", spread), irrigation=i18n.opt_en("irrigation", irrigation),
                soil_texture_user=i18n.opt_en("soil", soil_key), description=desc.strip(), currency=currency,
                crop_value_at_risk=value, ec_ds_m=ec, ph=ph, temp_c=temp)
            st.session_state.case = case.model_dump()
            st.session_state.form_view = dict(crop=crop_key, stage=stage_key, symptoms=symptoms, affected=affected,
                                              onset=onset, spread=spread, irrigation=irrigation, soil=soil_key)
            st.session_state.files = files
            st.session_state.uploads = docs
            st.session_state.form_saved = {k: st.session_state[k] for k in FORM_KEYS if k in st.session_state}
            st.session_state.understood = None
            st.session_state.stage = "confirm"
            st.rerun()


# ------------------------------------------------------------------------------------- confirm
def render_confirm(lang: str) -> None:
    case = CaseInput(**st.session_state.case)
    fv = st.session_state.form_view
    st.subheader(T("confirm_hdr"))
    if st.session_state.understood is None:
        with st.spinner("..."):
            try:
                st.session_state.understood = understand_input(lang, case.description, structured_en(case))
            except Exception as e:  # noqa: BLE001
                st.warning(f"Translation step failed ({e}). The original text will be used as it is.")
                st.session_state.understood = {"english_text": case.description, "understood_local": ""}
    u = st.session_state.understood
    L = lambda g, k: i18n.opt_label(g, k, lang)  # noqa: E731
    lines = [
        f"**{T('crop')}:** {case.crop} ({L('stage', fv['stage'])})",
        f"**{T('symptoms')}** " + (", ".join(L("symptoms", k) for k in fv["symptoms"]) or "-"),
        f"**{T('affected')}** {L('affected', fv['affected'])}",
        f"**{T('onset')}** {L('onset', fv['onset'])}  |  **{T('spread')}** {L('spread', fv['spread'])}",
        f"**{T('irrigation')}** {L('irrigation', fv['irrigation'])}  |  **{T('soil')}** {L('soil', fv['soil'])}",
        f"**{T('region')}** " + (", ".join(x for x in [case.city, case.province, case.country] if x) or "-")
        + ("" if case.lat is not None else "  (no coordinates)"),
        f"**{T('photos_hdr')}** {len(st.session_state.files)}",
    ]
    st.markdown("\n\n".join(lines))
    if u.get("understood_local"):
        st.markdown(f"**{T('we_understood')}**")
        st.info(u["understood_local"])
    if lang != "en" and u.get("english_text"):
        st.caption(T("english_used"))
        st.write(u["english_text"])
    c1, c2 = st.columns(2)
    if c1.button(T("yes_run"), type="primary", key="btn_yes"):
        case.description_en = u.get("english_text") or case.description
        st.session_state.case = case.model_dump()
        st.session_state.run_error = None
        st.session_state.stage = "run"
        st.rerun()
    if c2.button(T("no_edit"), key="btn_no"):
        st.session_state.stage = "form"
        st.rerun()


# ------------------------------------------------------------------------------------- run
def render_run(lang: str) -> None:
    case = CaseInput(**st.session_state.case)
    d = st.session_state.uploads
    up = Uploads(files=st.session_state.files, sop_text=d.get("sop_text", ""), prices_override=price_override(),
                 inventory=d.get("inventory"), lite=not st.session_state.get("full_notes", False))
    if st.session_state.run_error:
        st.error(st.session_state.run_error)
        if st.session_state.get("run_trace"):
            with st.expander("Technical details (send this to the developer)"):
                st.code(st.session_state.run_trace)
        c1, c2 = st.columns(2)
        if c1.button("Try again", key="btn_retry"):
            st.session_state.run_error = None
            st.rerun()
        if c2.button(T("no_edit"), key="btn_back2"):
            st.session_state.run_error = None
            st.session_state.stage = "form"
            st.rerun()
        return
    st.info(T("running"))
    bar = st.progress(0.0, text="Starting...")
    last = {"p": 0.0}

    def cb(p: float, msg: str) -> None:
        last["p"] = p
        bar.progress(min(1.0, p), text=msg)

    set_status_callback(lambda m: bar.progress(min(1.0, last["p"]), text=m))
    try:
        report = run_analysis(case, up, progress=cb)
        if lang != "en":
            try:
                cb(0.97, "Translating the summary")
                local = translate_summary(lang, report.summary_en.model_dump())
                report.summary_local = FarmerSummary.model_validate(local)
            except Exception as e:  # noqa: BLE001
                report.warnings.append(f"Summary could not be translated ({e}); showing English.")
        cid = storage.new_case_id()
        storage.save_case(cid, case.model_dump(), report.model_dump())
        st.session_state.report = report.model_dump()
        st.session_state.case_id = cid
        st.session_state.stage = "results"
        st.rerun()
    except MissingKeyError as e:
        st.session_state.run_error = str(e)
        st.rerun()
    except Exception as e:  # noqa: BLE001
        st.session_state.run_error = (f"The analysis stopped: [{type(e).__name__}] {str(e) or '(no message)'}\n\n"
                                      "Tips: click 'Test Groq connection' in the sidebar; check model names and your Groq key/limits in Secrets.")
        st.session_state.run_trace = traceback.format_exc()[-3500:]
        st.rerun()
    finally:
        set_status_callback(None)


# ------------------------------------------------------------------------------------- results
def cite(ids: list[str]) -> str:
    return f"`[{', '.join(ids)}]`" if ids else "*(model reasoning, no source)*"


def render_references(rep: Report) -> None:
    """Bibliography with source type/reliability + the keyword citation check."""
    kinds: dict[str, int] = {}
    for x in rep.sources:
        kinds[x.get("kind", "")] = kinds.get(x.get("kind", ""), 0) + 1
    ext = kinds.get("library", 0) + kinds.get("web", 0) + kinds.get("scholar", 0)
    cs = summarize_checks(rep.citation_checks)
    st.caption(f"Sources used: {len(rep.sources)} total, {ext} external references "
               f"(library {kinds.get('library', 0)}, web {kinds.get('web', 0)}, papers {kinds.get('scholar', 0)}). "
               f"Citation check: {cs['supported']} of {cs['total']} statements well traceable, {cs['partial']} partly, "
               f"{cs['weak']} weakly, {cs['unsourced']} without a source.")
    with st.expander("References & citation check"):
        st.markdown("**Bibliography** (external references first)")
        order = {"library": 0, "web": 1, "scholar": 2, "soil": 3, "weather": 4, "org": 5, "user": 6, "photo": 7, "default": 8, "calc": 9}
        for x in sorted(rep.sources, key=lambda r: (order.get(r.get("kind", ""), 9), r["id"])):
            cite_txt = x.get("citation") or x["title"]
            meta = " | ".join(v for v in [x.get("source_type", ""), x.get("reliability", ""), "retrieved " + x.get("retrieved", "")] if v)
            link = f" - [{x['url']}]({x['url']})" if x.get("url") else ""
            st.markdown(f"**[{x['id']}]** {cite_txt}{link}  \n*{meta}*")
        st.markdown("**Citation check** - keyword overlap between each statement and the sources it cites. "
                    "It shows traceability, not proof: read the sources.")
        if rep.citation_checks:
            icon = {"supported": "🟢 supported", "partial": "🟠 partial", "weak": "🔴 weak", "unsourced": "⚪ no source"}
            st.dataframe(pd.DataFrame([{"Where": c["section"], "Statement": c["claim"], "Cited": ", ".join(c["source_ids"]) or "-",
                                        "Traceability": f"{icon[c['level']]} ({c['score']:.2f})"} for c in rep.citation_checks]),
                         hide_index=True, width="stretch")


def pdf_controls(rep: Report, costs, cid: str, decisions: list[dict], key_prefix: str) -> None:
    """Two-step PDF: prepare (builds the file) then download."""
    lang = rep.case.language
    if st.button("📄 Prepare PDF report", key=f"{key_prefix}_prep_{cid}"):
        try:
            with st.spinner("Building PDF..."):
                st.session_state[f"{key_prefix}_pdf_{cid}"] = build_pdf(rep, costs, decisions, cid, lang)
        except Exception as e:  # noqa: BLE001
            st.error(f"PDF could not be created: {e}")
    data = st.session_state.get(f"{key_prefix}_pdf_{cid}")
    if data:
        st.download_button("⬇️ Download PDF", data, file_name=f"agrodecision_{cid}.pdf", mime="application/pdf",
                           key=f"{key_prefix}_dl_{cid}")
    st.caption("Tip: save your decision first, then prepare the PDF so the decision is included.")


def render_results(lang: str) -> None:
    rep = Report.model_validate(st.session_state.report)
    cid = st.session_state.case_id
    cur = rep.case.currency
    prices = effective_prices()
    inventory = st.session_state.uploads.get("inventory")

    if rep.demo:
        st.warning("DEMO MODE - this is a sample analysis, not based on your data.")
    summ = rep.summary_local or rep.summary_en

    st.subheader(T("summary_hdr"))
    if summ.headline:
        st.info(summ.headline)
    if summ.likely_cause_plain:
        st.write(summ.likely_cause_plain)
    for w in summ.warnings:
        st.warning(w)
    if summ.next_steps:
        st.markdown(f"**{T('next_steps')}**")
        st.markdown("\n".join(f"- {x}" for x in summ.next_steps))

    with st.expander("Data quality - what this analysis is based on", expanded=True):
        for q in rep.data_quality:
            st.markdown(f"- {q}")
        for w in rep.warnings:
            st.markdown(f"- ⚠️ {w}")

    dg = rep.diagnosis
    st.markdown(f"**{T('cause_hdr')}:** {dg.primary_hypothesis or '-'}  \n*Evidence confidence: {dg.evidence_confidence}*")

    # ---- options with live cost recalculation
    st.subheader(T("options_hdr"))
    var = st.number_input(T("value_at_risk"), min_value=0.0, step=1000.0,
                          value=float(rep.case.crop_value_at_risk or 0.0), key=f"res_var_{cid}")
    costs = [costing.cost_for_option(o, var, prices) for o in rep.options]
    supply = [costing.check_supply(o, inventory, prices) for o in rep.options]
    if not var:
        st.warning("Enter the value of the crop at risk to include expected losses in the comparison.")
    rows = []
    for o, c, sp in zip(rep.options, costs, supply):
        rows.append({"Option": o.key, "What": o.title, f"Intervention cost ({cur})": round(c.c_total),
                     "P(loss)": round(c.p_loss, 2), f"Expected loss ({cur})": round(c.expected_loss),
                     f"Total exposure ({cur})": round(c.exposure), "Delay (days)": sp.est_delay_days,
                     "Main uncertainty": o.main_uncertainty})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if rows and var:
        best = min(costs, key=lambda c: c.exposure)
        st.caption(f"Lowest estimated exposure: option {best.option_key}. Estimates use editable prices and assumed P(loss) - "
                   "not guarantees.")
    st.caption(f"Prices: {rep.prices_source}")
    for o in rep.options:
        with st.expander(f"Option {o.key}: {o.title}"):
            st.write(o.description)
            st.markdown("**Actions**\n" + "\n".join(f"- {a}" for a in o.actions))
            if o.assumptions:
                st.markdown("**Assumptions**\n" + "\n".join(f"- {a}" for a in o.assumptions))
            st.markdown(f"Sources: {cite(o.source_ids)}")
            c = next(x for x in costs if x.option_key == o.key)
            if c.lines:
                st.dataframe(pd.DataFrame([{"Item": ln.label, "Qty": ln.quantity, "Unit": ln.unit,
                                            "Unit cost": ln.unit_cost, "Category": ln.category, "Cost": round(ln.cost)}
                                           for ln in c.lines]), hide_index=True, width="stretch")
            if c.unknown_items:
                st.warning("Items not in the price list (not costed): " + ", ".join(c.unknown_items))
            sp = next(x for x in supply if x.option_key == o.key)
            for n in sp.notes:
                st.markdown(f"- {n}")

    with st.expander("Possible causes (with evidence)"):
        for h in dg.hypotheses:
            st.markdown(f"**{h.name}** - {h.likelihood} {cite(h.source_ids)}")
            st.markdown("\n".join([f"- for: {e}" for e in h.evidence_for] + [f"- against: {e}" for e in h.evidence_against]))
        if dg.additional_evidence_needed:
            st.markdown("**Evidence that would help**\n" + "\n".join(f"- {x}" for x in dg.additional_evidence_needed))
    if rep.monitoring.findings:
        with st.expander("Monitoring findings"):
            for f in rep.monitoring.findings:
                st.markdown(f"- {f.text} {cite(f.source_ids)}")
            for g in rep.monitoring.data_gaps:
                st.markdown(f"- missing: {g}")
    with st.expander("Risk & compliance flags"):
        for po in rep.risk.per_option:
            st.markdown(f"**Option {po.option_key}**")
            for f in po.flags:
                icon = "✅ verified" if f.status == "verified" else "⚠️ needs human / regulatory confirmation"
                st.markdown(f"- {icon}: {f.text} {cite(f.source_ids)}")
        for n in rep.risk.overall_notes:
            st.markdown(f"- {n}")
    with st.expander("Critic review"):
        for i in rep.critic.issues:
            st.markdown(f"- **{i.severity}**: {i.text}")
        if rep.critic.missing_data:
            st.markdown("**Missing data:** " + "; ".join(rep.critic.missing_data))
        if rep.critic.note_to_reviewer:
            st.info(rep.critic.note_to_reviewer)
    if rep.cost_notes or rep.supply_notes:
        with st.expander("Cost & supply review notes"):
            for n in rep.cost_notes + rep.supply_notes:
                st.markdown(f"- {n}")
    if rep.photo_notes:
        with st.expander("What the photo analysis saw (not a diagnosis)"):
            st.json(rep.photo_notes)
    render_references(rep)

    # ---- HUMAN DECISION GATE
    st.divider()
    st.subheader(T("decision_hdr"))
    st.caption(T("disclaimer"))
    choice_keys = ["approve", "modify", "reject", "more"]
    choice_labels = [T("approve"), T("modify"), T("reject"), T("more_info")]
    picked = st.radio("decision", choice_labels, horizontal=True, label_visibility="collapsed",
                      key=f"dec_choice_{cid}_{lang}")
    choice = choice_keys[choice_labels.index(picked)]
    keys = [o.key for o in rep.options]
    if choice in ("approve", "modify") and keys:
        opt_key = st.selectbox(T("choose_option"), keys, key=f"dec_opt_{cid}_{choice}",
                               format_func=lambda k: f"{k}: " + next(o.title for o in rep.options if o.key == k))
    else:
        opt_key = ""

    modified = None
    if choice == "modify" and opt_key:
        base = next(o for o in rep.options if o.key == opt_key)
        df = pd.DataFrame([{"item": k, "quantity": v} for k, v in base.quantities.items()] or [{"item": None, "quantity": 0.0}])
        ed = st.data_editor(df, num_rows="dynamic", hide_index=True, key=f"mod_{cid}_{opt_key}", width="stretch",
                            column_config={"item": st.column_config.SelectboxColumn("Item", options=list(prices.keys()), required=True),
                                           "quantity": st.column_config.NumberColumn("Quantity", min_value=0.0)})
        p_loss = st.slider("P(loss) with this option", 0.0, 1.0, float(base.p_loss), 0.05, key=f"mod_p_{cid}_{opt_key}")
        q: dict[str, float] = {}
        for r in ed.itertuples():
            if r.item and r.quantity and r.quantity > 0:
                q[str(r.item)] = q.get(str(r.item), 0.0) + float(r.quantity)
        cb = costing.compute_cost(opt_key, q, p_loss, var, prices)
        m1, m2 = st.columns(2)
        m1.metric(f"Intervention cost ({cur})", f"{cb.c_total:,.0f}")
        m2.metric(f"Total exposure ({cur})", f"{cb.exposure:,.0f}")
        modified = {"quantities": q, "p_loss": p_loss, "cost": cb.model_dump()}

    if choice == "more":
        if dg.follow_up_questions or dg.additional_evidence_needed:
            st.markdown("**Helpful to know / add:**")
            for x in dg.follow_up_questions + dg.additional_evidence_needed:
                st.markdown(f"- {x}")
        extra = st.text_area("Add information (English or your language)", key=f"dec_extra_{cid}")
        if st.button("Re-run the analysis with this information", key=f"dec_rerun_{cid}") and extra.strip():
            storage.save_decision(cid, "MORE_INFO", "", extra.strip())
            case = CaseInput(**st.session_state.case)
            case.extra_info = (case.extra_info + " " + extra.strip()).strip()
            st.session_state.case = case.model_dump()
            st.session_state.stage = "run"
            st.rerun()
    else:
        reason = st.text_area(T("reason"), key=f"dec_reason_{cid}_{choice}")
        if st.button(T("save_decision"), type="primary", key=f"dec_save_{cid}"):
            label = {"approve": "APPROVE", "modify": "MODIFY", "reject": "REJECT"}[choice]
            storage.save_decision(cid, label, opt_key, reason.strip(), modified)
            st.success(T("saved"))

    st.divider()
    pdf_controls(rep, costs, cid, (storage.get_case(cid) or {}).get("decisions", []), "res")
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Report (Markdown)", to_markdown(rep, costs), file_name=f"agrodecision_{cid}.md", key=f"dl_md_{cid}")
    d2.download_button("⬇️ Data (JSON)", json.dumps(rep.model_dump(), ensure_ascii=False, indent=2),
                       file_name=f"agrodecision_{cid}.json", key=f"dl_js_{cid}")
    if st.button(T("new_case"), key="btn_new"):
        reset_case()
        st.rerun()


# ------------------------------------------------------------------------------------- history
def render_history() -> None:
    cases = storage.list_cases()
    if not cases:
        st.info("No saved cases yet. Finished analyses and decisions appear here.")
        return
    st.caption("Storage is temporary on Streamlit Community Cloud (cleared when the app restarts). Download regularly.")
    st.dataframe(pd.DataFrame(cases), hide_index=True, width="stretch")
    sel = st.selectbox("Open a case", [c["id"] for c in cases], key="hist_sel",
                       format_func=lambda i: next(f"{c['id']} - {c['created']} - {c['crop']}" for c in cases if c["id"] == i))
    data = storage.get_case(sel)
    if not data:
        return
    rep = Report.model_validate(data["report"])
    st.markdown(f"**{rep.diagnosis.primary_hypothesis or '-'}** ({rep.diagnosis.evidence_confidence})")
    if data["decisions"]:
        st.dataframe(pd.DataFrame(data["decisions"])[["decided", "decision", "option_key", "reason"]], hide_index=True, width="stretch")
    for o in data["outcomes"]:
        st.markdown(f"- Outcome ({o['recorded']}): {o['note']}")
    note = st.text_area("Record the observed outcome (for example: symptoms decreased after 72 hours)", key=f"hist_note_{sel}")
    if st.button("Save outcome", key=f"hist_save_{sel}") and note.strip():
        storage.save_outcome(sel, note.strip())
        st.success("Outcome saved.")
        st.rerun()
    if st.button("Open this case in the results view", key=f"hist_open_{sel}"):
        st.session_state.update(report=data["report"], case=data["input"], case_id=sel, stage="results")
        st.success("Loaded - open the first tab to see it.")
    pdf_controls(rep, rep.costs, sel, data["decisions"], "hist")
    st.download_button("⬇️ This case (JSON)", json.dumps(data, ensure_ascii=False, indent=2), file_name=f"case_{sel}.json", key=f"hist_dl_{sel}")
    st.download_button("⬇️ All cases (JSON)", json.dumps(storage.export_all(), ensure_ascii=False, indent=2), file_name="all_cases.json", key="hist_dl_all")


# ------------------------------------------------------------------------------------- main
def main() -> None:
    init_state()
    st.title("🌱 AgroDecision AI")
    st.caption(f"Build {agrodecision.__version__} | Python {sys.version_info.major}.{sys.version_info.minor}")
    st.selectbox("🌐 Language / زبان", i18n.LANGS, format_func=lambda c: i18n.LANG_LABELS[c], key="lang")
    lang = st.session_state.lang
    inject_css(lang)
    render_sidebar()

    if S.access_code and not st.session_state.get("authed"):
        code = st.text_input(T("access_code"), type="password", key="access_input")
        if code and hmac.compare_digest(code, S.access_code):
            st.session_state.authed = True
            st.rerun()
        st.stop()

    tab_case, tab_hist = st.tabs([T("new_case"), T("history")])
    with tab_case:
        stage = st.session_state.stage
        if stage == "form":
            render_form(lang)
        elif stage == "confirm":
            render_confirm(lang)
        elif stage == "run":
            render_run(lang)
        else:
            render_results(lang)
    with tab_hist:
        render_history()


main()

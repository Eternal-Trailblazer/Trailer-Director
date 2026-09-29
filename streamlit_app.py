#!/usr/bin/env python
"""
Streamlit Web Interface for Autonomous Trailer Director — Gemini API mode.
Run with: streamlit run streamlit_app.py
"""

import streamlit as st
import json
import tempfile
import os
import sys
from pathlib import Path
import subprocess
import zipfile
import io
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

st.set_page_config(
    page_title="Autonomous Trailer Director",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Keep the interface preference across Streamlit reruns.  The default is the
# cinematic dark canvas, with a light alternative for brighter workspaces.
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
dark_mode = st.session_state.dark_mode

theme = {
    "bg": "#100B0B" if dark_mode else "#FFF8F1",
    "surface": "#1B1213" if dark_mode else "#FFFFFF",
    "surface_hover": "#261819" if dark_mode else "#FFF0E4",
    "text": "#FFF7ED" if dark_mode else "#2B1513",
    "text_dim": "#CBB9AE" if dark_mode else "#765D56",
    "sidebar": "#150E0F" if dark_mode else "#FFF4EB",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━ GOLDEN AMBER THEME ━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
    :root {
        --gold: #E8A317;
        --gold-soft: #F5C96B;
        --gold-deep: #B87F0F;
        --ember: #E14B4B;
        --ember-deep: #C0392B;
        --bg: %(bg)s;
        --bg-card: %(surface)s;
        --bg-card-hover: %(surface_hover)s;
        --text: %(text)s;
        --text-dim: %(text_dim)s;
        --border: rgba(232, 163, 23, 0.22);
    }

    /* ── Global background ── */
    .stApp {
        background: radial-gradient(ellipse at 20%% 0%%, rgba(181, 46, 35, .20) 0%%, transparent 38%%),
                    radial-gradient(ellipse at 90%% 8%%, rgba(232, 163, 23, .14) 0%%, transparent 32%%), var(--bg) fixed;
        color: var(--text);
    }
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        background:
            radial-gradient(circle at 85%% 15%%, rgba(225, 75, 75, 0.06), transparent 45%%),
            radial-gradient(circle at 10%% 90%%, rgba(232, 163, 23, 0.05), transparent 40%%);
        pointer-events: none;
    }

    /* ── Hero header ── */
    .hero {
        position: relative;
        padding: 1.6rem 2rem 1.3rem;
        margin-bottom: 1.2rem;
        border-radius: 22px;
        background: linear-gradient(125deg, rgba(232,163,23,0.20), rgba(193,57,43,0.17) 52%%, var(--bg-card));
        border: 1px solid var(--border);
        overflow: hidden;
    }
    .hero::after {
        content: "";
        position: absolute; left: 0; right: 0; bottom: 0; height: 2px;
        background: linear-gradient(90deg, transparent, var(--gold), var(--ember), transparent);
    }
    .hero-title {
        font-size: 2.1rem; font-weight: 800; letter-spacing: -0.5px;
        background: linear-gradient(90deg, #F5C96B, #E8A317 45%%, #E14B4B);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .hero-sub {
        color: var(--text-dim); font-size: 0.95rem; margin: 0.35rem 0 0;
        font-weight: 400;
    }

    /* ── Cards ── */
    .gold-card {
        background: linear-gradient(160deg, var(--bg-card), rgba(30,21,16,0.65));
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1.1rem 1.25rem;
        margin-bottom: 0.9rem;
        transition: border-color .2s ease, transform .2s ease;
    }
    .gold-card:hover { border-color: rgba(232,163,23,0.5); transform: translateY(-1px); }

    /* ── Sidebar command center ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, %(sidebar)s 0%%, var(--bg) 100%%) !important;
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: .6rem; }
    .brand-lockup { padding: .7rem .2rem 1rem; }
    .brand-mark {
        display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px;
        border-radius: 12px; margin-right: .55rem; vertical-align: middle; font-size: 1.15rem;
        background: linear-gradient(135deg, var(--gold), var(--ember)); box-shadow: 0 7px 20px rgba(193,57,43,.22);
    }
    .brand-name { color: var(--text); font-size: .95rem; font-weight: 800; letter-spacing: .2px; }
    .brand-caption { color: var(--text-dim); font-size: .72rem; margin: .32rem 0 0 2px; }
    .side-caption { color: var(--text-dim); font-size: .7rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin: .9rem 0 .35rem; }

    /* ── Section headers ── */
    .section-header {
        font-size: 1.15rem; font-weight: 700; color: var(--gold-soft);
        letter-spacing: 0.3px;
        padding-bottom: 0.45rem; margin: 0.2rem 0 0.9rem;
        border-bottom: 1px solid var(--border);
        display: flex; align-items: center; gap: 0.5rem;
    }

    [data-testid="stSidebar"] .section-header { font-size: .78rem; margin: .5rem 0 .45rem; color: var(--gold-soft); border-bottom: 0; text-transform: uppercase; letter-spacing: 1px; }
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        border: 1px solid var(--border); border-radius: 12px; background: rgba(232,163,23,.035); margin-bottom: .45rem; overflow: hidden;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary { font-weight: 700; color: var(--text) !important; padding: .1rem .2rem; }

    /* ── Status pills ── */
    .pill {
        display: inline-block; padding: 0.18rem 0.7rem; border-radius: 999px;
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.6px; text-transform: uppercase;
    }
    .pill-pass   { background: rgba(232,163,23,0.16);  color: #F5C96B; border: 1px solid rgba(232,163,23,0.45); }
    .pill-warn   { background: rgba(225,75,75,0.14);   color: #F08A8A; border: 1px solid rgba(225,75,75,0.4); }
    .pill-fail   { background: rgba(193,57,43,0.22);   color: #FF9B9B; border: 1px solid rgba(193,57,43,0.65); }
    .pill-muted  { background: rgba(184,169,154,0.12); color: #B8A99A; border: 1px solid rgba(184,169,154,0.3); }

    /* ── Stat tiles ── */
    .stat-tile {
        background: var(--bg-card); border: 1px solid var(--border);
        border-radius: 12px; padding: 0.9rem 1rem; text-align: center;
    }
    .stat-num { font-size: 1.5rem; font-weight: 800; color: var(--gold); }
    .stat-label { font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 1px; margin-top: 0.15rem; }

    /* ── API status banner ── */
    .api-ok  { color: #F5C96B; }
    .api-bad { color: #FF9B9B; }

    /* ── Buttons / widgets ── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(100deg, var(--ember-deep), var(--gold)) !important;
        border: none !important; color: #120D0A !important; font-weight: 700 !important;
        border-radius: 10px !important; padding: 0.55rem 1.2rem !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(90deg, var(--gold), var(--gold-soft)) !important;
        box-shadow: 0 0 18px rgba(232,163,23,0.35) !important;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 2px; border-bottom: 1px solid var(--border); }
    .stTabs [data-baseweb="tab"] {
        background: transparent; border-radius: 10px 10px 0 0; padding: 0.55rem 1.1rem;
        color: var(--text-dim) !important; font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(180deg, rgba(232,163,23,0.14), transparent) !important;
        color: var(--gold-soft) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { background: linear-gradient(90deg, var(--gold), var(--ember)) !important; height: 2px !important; }

    .stToggle label { color: var(--text) !important; font-weight: 600; }
    [data-testid="stFileUploader"] { background: rgba(232,163,23,.025); border-radius: 14px; padding: .35rem; }
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, textarea {
        background-color: var(--bg-card) !important; color: var(--text) !important; border-color: var(--border) !important;
    }
    [data-testid="stMarkdownContainer"] p, label, [data-testid="stWidgetLabel"] p { color: var(--text) !important; }

    /* ── Data frames / tables ── */
    [data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 10px !important; }

    /* ── Inputs ── */
    .stTextArea, .stNumberInput, .stTextInput, div[data-baseweb="select"] > div {
        border-radius: 10px !important;
    }

    /* ── Expanders ── */
    .streamlit-expanderHeader {
        background: var(--bg-card); border-radius: 10px !important;
        border: 1px solid var(--border); font-weight: 600;
    }

    /* ── Footer ── */
    .footer {
        margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border);
        color: var(--text-dim); font-size: 0.8rem; text-align: center;
    }
</style>
""" % theme, unsafe_allow_html=True)


def pill(status: str) -> str:
    """Render a status pill from a validation status string."""
    s = (status or "").upper()
    css = "pill-pass" if s == "PASS" else "pill-warn" if "WARN" in s else "pill-fail" if "FAIL" in s else "pill-muted"
    return f'<span class="pill {css}">{status}</span>'


def hero(title: str, sub: str):
    st.markdown(
        f'<div class="hero"><h1 class="hero-title">{title}</h1><p class="hero-sub">{sub}</p></div>',
        unsafe_allow_html=True,
    )


def trailer_keys(results: dict) -> list[str]:
    """Return the primary trailer plans, excluding their extended copies."""
    return [name for name in results if name.startswith("trailer_") and not name.endswith("_extended")]


def render_downloads(results: dict):
    """Keep result exports beside the plans they belong to."""
    def to_text(name, data):
        if isinstance(data, (dict, list)):
            return json.dumps(data, indent=2), "json"
        if isinstance(data, bytes):
            return data, "bin"
        if isinstance(data, str):
            return data, "json" if name.endswith(".json") else "md"
        return str(data), "json"

    with st.expander("📥 Export results", expanded=False):
        st.markdown("**Individual files**")
        dl_cols = st.columns(3)
        for i, (name, data) in enumerate(results.items()):
            content, ext = to_text(name, data)
            with dl_cols[i % 3]:
                st.download_button(f"📥 {name}.{ext}", data=content, file_name=f"{name}.{ext}",
                                   use_container_width=True)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in results.items():
                content, ext = to_text(name, data)
                zf.writestr(f"{name}.{ext}", content)
            if st.session_state.run_logs:
                zf.writestr("pipeline_logs.txt", st.session_state.run_logs)
        st.download_button("📦 Download complete package", data=zip_buffer.getvalue(),
                           file_name="trailer_director_results.zip", mime="application/zip",
                           type="primary", use_container_width=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━ API KEY CHECK ━━━━━━━━━━━━━━━━━━━━━━━━━

@st.cache_data(ttl=600, show_spinner=False)
def check_api_key() -> dict:
    """Validate the Gemini API key from config/env with a tiny live call."""
    try:
        import google.generativeai as genai
    except ImportError:
        return {"ok": False, "msg": "google-generativeai not installed", "model": "—"}

    cfg_path = Path(__file__).parent / "config" / "default_config.yaml"
    api_key, model = None, "gemini-3.8-flash"
    try:
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            gem = next((p for p in cfg.get("providers", []) if p.get("provider_id") == "gemini"), None)
            if gem:
                model = gem.get("model", model)
                api_key = gem.get("api_key") or os.getenv(gem.get("api_key_env", "GEMINI_API_KEY"))
    except Exception:
        pass
    api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {"ok": False, "msg": "No API key found", "model": model}

    try:
        import warnings
        warnings.filterwarnings("ignore")
        genai.configure(api_key=api_key)
        resp = genai.GenerativeModel(model).generate_content("Reply: OK")
        if resp.text:
            return {"ok": True, "msg": "Connected", "model": model}
        return {"ok": False, "msg": "Empty response", "model": model}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120], "model": model}


# ━━━━━━━━━━━━━━━━━━━━━━━━━ HEADER ━━━━━━━━━━━━━━━━━━━━━━━━━
hero("Autonomous Trailer Director", "Compliant, creative trailer plans for multiple audiences — powered by Gemini")

# ━━━━━━━━━━━━━━━━━━━━━━━━━ SIDEBAR ━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.markdown(
        '<div class="brand-lockup"><span class="brand-mark">▶</span><span class="brand-name">TRAILER STUDIO</span>'
        '<p class="brand-caption">Creative control, clearly organized.</p></div>',
        unsafe_allow_html=True,
    )
    st.toggle("Dark cinema mode", key="dark_mode", help="Switch between the cinematic dark canvas and a bright workspace.")
    st.markdown('<div class="side-caption">Command center</div>', unsafe_allow_html=True)

    # API status
    api_status = check_api_key()
    if api_status["ok"]:
        st.markdown(
            f'<div class="gold-card api-ok">🔑 <b>Gemini API:</b> Connected<br>'
            f'<span style="font-size:0.78rem;color:var(--text-dim)">Model: {api_status["model"]}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="gold-card api-bad">🔑 <b>Gemini API:</b> {api_status["msg"]}<br>'
            f'<span style="font-size:0.78rem;color:var(--text-dim)">Add api_key to config/default_config.yaml</span></div>',
            unsafe_allow_html=True,
        )

    with st.expander("💰  Budget & limits", expanded=False):
        budget_usd = st.number_input("Total Budget (USD)", 0.01, 100.0, 10.0, 0.5)
        model_call_limit = st.number_input("Model Call Limit", 10, 1000, 200, 10)
        media_processing_limit = st.number_input("Media Processing Limit", 5, 200, 50, 5)

    with st.expander("🎬  Trailer direction", expanded=True):
        min_duration = st.number_input("Min Duration (s)", 10, 120, 20)
        max_duration = st.number_input("Max Duration (s)", 20, 300, 60)
        min_segments = st.number_input("Min Segments", 1, 20, 3)
        max_segments = st.number_input("Max Segments", 3, 30, 12)
        diversity_threshold = st.slider("Diversity Threshold", 0.0, 1.0, 0.4, 0.05)

    with st.expander("🛡️  Safety & repair", expanded=False):
        late_episode_threshold = st.slider("Late Episode Threshold", 0.0, 1.0, 0.7, 0.05)
        confidence_threshold = st.slider("Confidence Threshold", 0.0, 1.0, 0.6, 0.05)
        max_repair_iterations = st.number_input("Max Repair Iterations", 1, 10, 3)

    st.markdown('<div class="side-caption">Audience brief</div>', unsafe_allow_html=True)
    default_audiences = [
        {
            "audience_id": "family", "name": "Family viewers",
            "description": "General family audience seeking wholesome entertainment",
            "goal": "Communicate warmth, stakes and broad entertainment value",
            "special_care": ["Follow the strictest rating rules", "Avoid frightening or suggestive context"],
            "rating_policy_ids": ["policy_family"], "age_range": [0, 100],
            "territories": ["IN", "US", "GB"], "languages": ["en", "hi"],
        },
        {
            "audience_id": "young_adult", "name": "Young adult viewers",
            "description": "Young adult audience seeking engaging character-driven stories",
            "goal": "Highlight pace, humour, identity and character conflict",
            "special_care": ["Do not use misleading intensity", "Do not reveal the central twist"],
            "rating_policy_ids": ["policy_young_adult"], "age_range": [16, 30],
            "territories": ["IN", "US", "GB"], "languages": ["en", "hi"],
        },
        {
            "audience_id": "dialect_region", "name": "Dialect-region viewers",
            "description": "Hindi dialect-speaking regional audience",
            "goal": "Show that the release understands their language and cultural context",
            "special_care": ["Do not reduce the audience to stereotypes", "Do not treat dialect as a comic device"],
            "rating_policy_ids": ["policy_dialect_region"], "age_range": [18, 60],
            "territories": ["IN"], "languages": ["hi"],
        },
    ]
    with st.expander("👥  Audience profiles", expanded=False):
        audiences_json = st.text_area("Audiences (JSON)", value=json.dumps(default_audiences, indent=2), height=260)
    try:
        audiences = json.loads(audiences_json)
    except json.JSONDecodeError as e:
        st.error(f"Invalid audiences JSON: {e}")
        audiences = default_audiences

# ━━━━━━━━━━━━━━━━━━━━━━━━━ TABS ━━━━━━━━━━━━━━━━━━━━━━━━━
tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Run", "📊 Results", "📋 Validation", "📖 Docs"])

if "pipeline_results" not in st.session_state:
    st.session_state.pipeline_results = None
if "run_logs" not in st.session_state:
    st.session_state.run_logs = ""

# ─────────────── Tab 1: Upload & Run ───────────────
with tab1:
    st.markdown('<div class="section-header">📤 Episode Materials</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Required**")
        episode_package = st.file_uploader(
            "Episode Package", type=["mp4", "mkv", "mov", "json", "zip"],
            help="Video file, clip directory (zip), or JSON manifest",
        )
        st.markdown("**Optional**")
        scene_descriptions = st.file_uploader("Scene Descriptions", type=["json", "csv", "txt", "md", "pdf"])
        dialogue = st.file_uploader("Dialogue & Subtitles", type=["srt", "vtt", "ass", "json", "csv"])
    with col2:
        policies = st.file_uploader("Rating Policies", type=["json", "yaml", "yml", "pdf", "txt"])
        contracts = st.file_uploader("Contracts", type=["json", "yaml", "yml", "pdf", "txt"])
        audience_profiles = st.file_uploader("Audience Profiles (override)", type=["json", "csv", "yaml", "yml"])
        historic_data = st.file_uploader("Historic Performance", type=["json", "csv"])
        cost_sheet = st.file_uploader("Cost Sheet", type=["json", "yaml", "yml", "csv"])

    st.divider()
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        run_button = st.button("🚀 Run Pipeline", type="primary", use_container_width=True, disabled=episode_package is None)
    if episode_package is None:
        st.markdown('<span class="pill pill-warn">Upload an episode package to run</span>', unsafe_allow_html=True)
    elif not api_status["ok"]:
        st.markdown('<span class="pill pill-fail">Gemini API key invalid — fix config to run</span>', unsafe_allow_html=True)

# ─────────────── Pipeline execution ───────────────
if run_button and episode_package and api_status["ok"]:
    progress_bar = st.progress(0, text="Starting pipeline…")
    log_container = st.empty()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_dir = tmpdir / "output"
        output_dir.mkdir()

        def save_uploaded_file(f, name):
            if f:
                p = tmpdir / name
                p.write_bytes(f.read())
                return p
            return None

        if episode_package.name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(episode_package.read()), "r") as z:
                z.extractall(tmpdir / "episode_package")
            package_path = tmpdir / "episode_package"
        else:
            package_path = save_uploaded_file(episode_package, episode_package.name)

        scenes_p = save_uploaded_file(scene_descriptions, "scenes" + Path(scene_descriptions.name).suffix) if scene_descriptions else None
        dialogue_p = save_uploaded_file(dialogue, "dialogue" + Path(dialogue.name).suffix) if dialogue else None
        policies_p = save_uploaded_file(policies, "policies" + Path(policies.name).suffix) if policies else None
        contracts_p = save_uploaded_file(contracts, "contracts" + Path(contracts.name).suffix) if contracts else None
        audiences_p = save_uploaded_file(audience_profiles, "audiences" + Path(audience_profiles.name).suffix) if audience_profiles else None
        history_p = save_uploaded_file(historic_data, "history" + Path(historic_data.name).suffix) if historic_data else None
        costs_p = save_uploaded_file(cost_sheet, "costs" + Path(cost_sheet.name).suffix) if cost_sheet else None

        # Carry the working provider config into the temp config so the CLI uses it
        base_cfg = {}
        cfg_file = Path(__file__).parent / "config" / "default_config.yaml"
        if cfg_file.exists():
            try:
                base_cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
            except Exception:
                base_cfg = {}

        config = {
            "audiences": audiences,
            "budget": {"total_usd": budget_usd, "model_call_limit": model_call_limit,
                       "media_processing_limit": media_processing_limit, "warn_at_percent": 80},
            "trailer": {"min_duration_seconds": min_duration, "max_duration_seconds": max_duration,
                        "min_segments": min_segments, "max_segments": max_segments,
                        "diversity_threshold": diversity_threshold},
            "spoiler": {"late_episode_threshold": late_episode_threshold,
                        "confidence_threshold": confidence_threshold},
            "repair": {"max_iterations": max_repair_iterations, "escalation_on_failure": True},
        }
        if base_cfg.get("providers"):
            config["providers"] = base_cfg["providers"]

        config_path = tmpdir / "config.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        cmd = [sys.executable, "-m", "src.cli", "run",
               "--package", str(package_path), "--config", str(config_path), "--output", str(output_dir)]
        for flag, p in [("--scenes", scenes_p), ("--dialogue", dialogue_p), ("--policies", policies_p),
                        ("--contracts", contracts_p), ("--audiences", audiences_p),
                        ("--history", history_p), ("--costs", costs_p)]:
            if p:
                cmd.extend([flag, str(p)])

        try:
            process = subprocess.Popen(cmd, cwd=Path(__file__).parent, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, bufsize=1)
            logs = []
            for i, line in enumerate(iter(process.stdout.readline, "")):
                logs.append(line)
                if i % 5 == 0:
                    log_container.code("\n".join(logs[-40:]), language="bash")
                    progress_bar.progress(min(10 + i * 2, 90), text="Running…")
            process.wait()
            progress_bar.progress(100, text="Finished")

            if process.returncode == 0:
                st.session_state.run_logs = "\n".join(logs)
                results = {}
                for f in output_dir.glob("*"):
                    if f.suffix == ".json":
                        try:
                            results[f.stem] = json.loads(f.read_text(encoding="utf-8"))
                        except Exception:
                            results[f.stem] = f.read_text(encoding="utf-8")
                    elif f.suffix == ".md":
                        results[f.stem] = f.read_text(encoding="utf-8")
                st.session_state.pipeline_results = {"results": results, "output_dir": str(output_dir)}
                st.balloons()
            else:
                st.session_state.run_logs = "\n".join(logs)
                st.error(f"Pipeline failed (exit code {process.returncode})")
                log_container.code("\n".join(logs[-80:]), language="bash")
        except Exception as e:
            st.error(f"Error running pipeline: {e}")

# ─────────────── Tab 2: Results ───────────────
with tab2:
    st.markdown('<div class="section-header">📊 Generated Trailers</div>', unsafe_allow_html=True)

    if st.session_state.pipeline_results:
        results = st.session_state.pipeline_results["results"]
        trailer_files = trailer_keys(results)

        # Keep exports at the top of Results so they are immediately discoverable.
        render_downloads(results)
        st.divider()

        if trailer_files:
            n = max(len(trailer_files), 1)
            cols = st.columns(min(n, 3))
            for i, tf in enumerate(trailer_files):
                t = results[tf]
                meta = t.get("metadata", {})
                status = t.get("validation_summary", {}).get("overall_status", "UNKNOWN")
                with cols[i % min(n, 3)]:
                    st.markdown(
                        f'<div class="stat-tile"><div class="stat-num">{meta.get("duration_seconds", 0):.1f}s</div>'
                        f'<div class="stat-label">{meta.get("audience", tf)}</div></div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(pill(status) + f'<span class="pill pill-muted">{meta.get("segment_count", 0)} seg</span>',
                                unsafe_allow_html=True)

            st.divider()
            selected_trailer = st.selectbox("Select Trailer", trailer_files)
            if selected_trailer:
                t = results[selected_trailer]
                a, b = st.columns(2)
                with a:
                    st.markdown("**Creative Brief**")
                    ap = t.get("creative_brief", {}).get("audience_promise", {})
                    st.write(f"**Promise:** {ap.get('promise_text', 'N/A')}")
                    st.write(f"**Tone:** {ap.get('tone', 'N/A')}")
                    st.write(f"**Arc:** {' → '.join(ap.get('narrative_arc', []))}")
                    st.write(f"**Emotions:** {', '.join(ap.get('intended_emotions', []))}")
                    st.write(f"**Avoid:** {', '.join(ap.get('avoid', []))}")
                with b:
                    st.markdown("**EDL**")
                    for seg in t.get("edl", []):
                        with st.expander(f"Segment {seg['sequence_order']}: {seg['source']['scene_id']}"):
                            st.write(f"**Reason:** {seg['creative_reason']}")
                            st.write(f"**Audio:** {seg['audio']['type']}")
                            if seg.get("subtitle"):
                                st.write(f"**Subtitle:** {seg['subtitle']}")
                            if seg.get("text_card"):
                                st.write(f"**Text Card:** {seg['text_card']}")
        else:
            st.warning("The pipeline finished, but it did not return any trailer plans. Check Validation for details.")
    else:
        st.markdown('<div class="gold-card">🎬 <b>Your trailer plans will appear here after a run.</b><br>'
                    '<span style="color:var(--text-dim)">Upload episode material in Upload & Run to get started.</span></div>',
                    unsafe_allow_html=True)

# ─────────────── Tab 3: Validation ───────────────
with tab3:
    st.markdown('<div class="section-header">📋 Validation Details</div>', unsafe_allow_html=True)

    if st.session_state.pipeline_results:
        results = st.session_state.pipeline_results["results"]
        trailer_files = trailer_keys(results)
        if trailer_files:
            selected = st.selectbox("Select Trailer", trailer_files, key="val_sel")
            t = results[selected]
            val = t.get("validation_summary", {})
            status = val.get("overall_status", "UNKNOWN")
            st.markdown(f"### {pill(status)}", unsafe_allow_html=True)

            checks = val.get("checks", [])
            if checks:
                st.markdown("**Checks**")
                st.dataframe(
                    [{"Check": c.get("check_id", ""), "Type": c.get("check_type", ""),
                      "Verdict": c.get("verdict", ""), "Details": c.get("details", "")[:160]} for c in checks],
                    use_container_width=True, hide_index=True,
                )

            for w in val.get("warnings", []):
                st.warning(w)
            for f in val.get("failures", []):
                st.error(f)
            for a in val.get("human_approvals_required", []):
                st.info(f"Approval needed: {a}")
    else:
        st.info("Run the pipeline to see validation details.")

# ─────────────── Tab 4: Docs ───────────────
with tab4:
    st.markdown('<div class="section-header">📖 Documentation</div>', unsafe_allow_html=True)
    doc_tabs = st.tabs(["Architecture", "AI Collaboration", "Known Limitations", "CLI Reference"])

    with doc_tabs[0]:
        st.markdown("### System Architecture")
        st.markdown("""
        **Pipeline Flow:**
        ```
        INGEST → NORMALIZE → STORY MAP → SPOILER MAP → CONSTRAINT COMPILATION
            → AUDIENCE STRATEGY → CANDIDATE GENERATION → INDEPENDENT VERIFICATION
            → REPAIR / REJECT → EDL EMISSION → CHANGE HANDLING
        ```

        **Key Components:**
        - **Adapter Layer**: Parses 7+ input formats (JSON, SRT, VTT, CSV, PDF, etc.)
        - **Quarantine Gate**: Detects/neutralizes prompt injections in untrusted text
        - **Story Mapper**: Builds canonical StoryMap (scenes, entities, events, emotional arc)
        - **Spoiler Engine**: 3-layer detection (direct, ordering, inferential) with evidence
        - **Rule Compiler**: LLM extracts DSL rules from policies/contracts
        - **Rule Evaluator**: Pure Python deterministic enforcement
        - **Bias Auditor**: Statistical checks before personalisation
        - **Audience Strategist**: Plans promise BEFORE clip selection
        - **Trailer Generator**: Arc-structured selection with diversity enforcement
        - **Verifier**: Deterministic checks first, LLM judges second
        - **Repair Engine**: Max 3 iterations, targeted re-verification
        - **Change Handler**: Dependency graph → selective replan
        """)

    with doc_tabs[1]:
        st.markdown("### AI Collaboration Log")
        st.markdown("""
        **Delegation Patterns:**
        - ✅ Pydantic schemas, adapters, test scaffolding, docs → AI generated
        - ⚠️ Spoiler heuristics, creative prompts → AI drafted, human verified
        - ❌ RuleEvaluator, safety-critical logic → Human written

        **5 "Plausible but Wrong" Instances Caught:**
        1. Keyword-based spoiler detection → Replaced with story-map-derived 3-layer detection
        2. Engagement-score-based scene selection → Violates §11 anti-pattern
        3. Policy text in LLM system prompt → Violates §8 constraint-reasoning requirement
        4. Vacuous test assertions → Fixed with mutation testing
        5. Demographic stereotypes in test data → Triggered own BiasAuditor
        """)

    with doc_tabs[2]:
        st.markdown("### Known Limitations")
        st.markdown("""
        **Architectural:**
        - No real video analysis (text-only mode)
        - LLM verification scales linearly with scenes
        - Rule extraction accuracy on complex contracts

        **Creative:**
        - Fixed arc template (Setup→Tension→Hook)
        - No NLG polish on creative brief text
        - Jaccard diversity on scene IDs only

        **Safety:**
        - Conservative defaults may over-block (DENY all if no contracts)
        - Dialect drift quality depends on LLM language proficiency
        - Bias auditor statistical checks only
        """)

    with doc_tabs[3]:
        st.markdown("### CLI Reference")
        st.code("""
# Full pipeline (Gemini API — key from config/default_config.yaml or GEMINI_API_KEY env)
python run.py run --package ./test_episode --config ./config/default_config.yaml --output ./output

# Override budget
python run.py run --package ./test_episode --output ./output --budget 5.00

# Other commands
python run.py verify --plans ./output
python run.py apply-change --event ./change.json --plans ./output
python run.py report --plans ./output --output ./report.md
        """, language="bash")

# ━━━━━━━━━━━━━━━━━━━━━━━━━ FOOTER ━━━━━━━━━━━━━━━━━━━━━━━━━
if st.session_state.run_logs:
    with st.expander("🔧 Pipeline Logs"):
        st.code(st.session_state.run_logs[-5000:], language="bash")

st.markdown('<div class="footer">Autonomous Trailer Director · OTT Dialect Platform Assignment · Gemini API mode</div>', unsafe_allow_html=True)

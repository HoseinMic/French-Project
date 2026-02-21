import csv
import io
import re
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
import json
import sqlite3
import textwrap
import base64
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple, Optional

import requests
import streamlit as st
import streamlit.components.v1 as components

# =========================
# Config
# =========================
APP_TITLE = "Charlot"
DB_PATH = "charlot.sqlite3"

DICTAPI_BASE = "https://api.dictionaryapi.dev/api/v2/entries"
WIKTIONARY_BASE = {"fr": "https://fr.wiktionary.org", "en": "https://en.wiktionary.org"}

HTTP_HEADERS = {
    "User-Agent": "Charlot/9.0 (Streamlit; educational app)",
    "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
}

st.set_page_config(page_title=APP_TITLE, page_icon="🇫🇷", layout="wide")

# st.set_page_config(layout="wide")  # keep wide, then cap container with CSS

st.markdown("""
<style>
/* Main content container max width */
section.main > div { max-width: 1080px; margin: 0 auto; }

/* Optional: reduce side padding */
section.main { padding-left: 1rem; padding-right: 1rem; }
</style>
""", unsafe_allow_html=True)

# =========================
# Theme tokens
# =========================
THEMES = {
    "Dark": {
        "bg": "#0b0f17",
        "bg2": "#0f1623",
        "surface": "rgba(255,255,255,.06)",
        "surface2": "rgba(255,255,255,.04)",
        "txt": "rgba(255,255,255,.92)",
        "mut": "rgba(255,255,255,.66)",
        "mut2": "rgba(255,255,255,.46)",
        "line": "rgba(255,255,255,.10)",
        "brand": "#58cc02",
        "brand2": "#1cb0f6",
        "warn": "#ffcc00",
        "danger": "#ff4b4b",
        "shadow": "0 14px 40px rgba(0,0,0,.45)",
        "shadow2": "0 10px 26px rgba(0,0,0,.35)",
        "chip": "rgba(255,255,255,.08)",
        "chip_border": "rgba(255,255,255,.12)",
    },
    "Light": {
        "bg": "#f7f8fb",
        "bg2": "#eef2f8",
        "surface": "rgba(255,255,255,1.0)",
        "surface2": "rgba(255,255,255,.72)",
        "txt": "rgba(12,16,20,.94)",
        "mut": "rgba(12,16,20,.66)",
        "mut2": "rgba(12,16,20,.48)",
        "line": "rgba(12,16,20,.10)",
        "brand": "#58cc02",
        "brand2": "#1cb0f6",
        "warn": "#ffcc00",
        "danger": "#ff4b4b",
        "shadow": "0 14px 34px rgba(16,24,40,.12)",
        "shadow2": "0 10px 22px rgba(16,24,40,.10)",
        "chip": "rgba(12,16,20,.06)",
        "chip_border": "rgba(12,16,20,.10)",
    },
}

PAGES = [
    ("🏠", "Home"),
    ("📚", "Dictionary"),
    ("🧠", "Review"),
    ("🗂️", "Cards"),
    ("📝", "Notes"),
    ("🔁", "Import/Export"),
    ("⚙️", "Settings"),
    ("❓", "About"),
]

# =========================
# Session state
# =========================
def init_session_state() -> None:
    ss = st.session_state
    ss.setdefault("nav", "Home")
    ss.setdefault("theme", "Dark")
    ss.setdefault("xp", 0)
    ss.setdefault("streak", 1)
    ss.setdefault("last_xp_date", iso_date(today_utc_date()))
    ss.setdefault("review_idx", 0)
    ss.setdefault("edit_card_id", None)
    ss.setdefault("selected_card_id", None)
    ss.setdefault("scroll_to_selected_card", False)
    ss.setdefault("scroll_to_editor", False)
    ss.setdefault("delete_confirm_id", None)
    ss.setdefault("cards_page", 1)
    ss.setdefault("cards_page_size", 18)
    ss.setdefault("global_query", "")
    ss.setdefault("nb_pdf_book_id", None)
    ss.setdefault("nb_pdf_page", 1)
    ss.setdefault("nb_pdf_zoom", 100)
    ss.setdefault("nb_vocab_q", "")
    ss.setdefault("nb_pdf_text_cache_page", None)
    ss.setdefault("nb_pdf_extracted_text", "")

# =========================
# Responsive breakpoint
# =========================
def detect_breakpoint(breakpoint_px: int = 760) -> str:
    """Return 'm' (mobile) or 'd' (desktop) using a query-param probe."""
    try:
        bp = st.query_params.get("bp", None)
    except Exception:
        bp = st.experimental_get_query_params().get("bp", [None])[0]

    components.html(
        f"""
<script>
(function() {{
  const bp = (window.innerWidth <= {breakpoint_px}) ? "m" : "d";
  const url = new URL(window.location.href);
  const cur = url.searchParams.get("bp");
  if (!cur || cur !== bp) {{
    url.searchParams.set("bp", bp);
    window.location.href = url.toString();
  }}
}})();
</script>
""",
        height=0,
    )
    return bp or "d"

# =========================
# CSS
# =========================
def inject_global_css(theme_name: str) -> None:
    t = THEMES.get(theme_name, THEMES["Dark"])
    css = f"""
<style>
:root {{
  --bg:{t["bg"]};
  --bg2:{t["bg2"]};
  --surface:{t["surface"]};
  --surface2:{t["surface2"]};
  --line:{t["line"]};
  --txt:{t["txt"]};
  --mut:{t["mut"]};
  --mut2:{t["mut2"]};
  --brand:{t["brand"]};
  --brand2:{t["brand2"]};
  --warn:{t["warn"]};
  --danger:{t["danger"]};
  --chip:{t["chip"]};
  --chipb:{t["chip_border"]};
  --sh:{t["shadow"]};
  --sh2:{t["shadow2"]};
  --r12:12px;
  --r16:16px;
  --r20:20px;
  --r24:24px;
  --r28:28px;
}}

html, body, [class*="css"] {{
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
}}
.stApp {{
  background:
    radial-gradient(900px 520px at 12% -10%, rgba(28,176,246,.18), transparent 60%),
    radial-gradient(900px 520px at 88% 0%, rgba(88,204,2,.14), transparent 55%),
    linear-gradient(180deg, var(--bg) 0%, var(--bg2) 100%);
  color: var(--txt);
}}

.block-container {{
  padding-top: .9rem;
  padding-bottom: 4.0rem;
  max-width: 1200px;
}}

header[data-testid="stHeader"]{{ background: rgba(0,0,0,0); }}
div[data-testid="stToolbar"]{{ visibility: hidden; height: 0px; }}
footer{{ visibility:hidden; }}

::selection {{ background: rgba(88,204,2,.22); }}

/* Prevent button labels from wrapping character-by-character on narrow cards */
div.stButton > button, div.stButton > button * {{
  white-space: nowrap !important;
}}

@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to   {{ opacity: 1; transform: translateY(0px); }}
}}
.page {{ animation: fadeIn .18s ease-out; }}

.card {{
  background: linear-gradient(180deg, var(--surface), var(--surface2));
  border: 1px solid var(--line);
  border-radius: var(--r24);
  box-shadow: var(--sh2);
  padding: 18px 18px;
}}
.card-tight {{ border-radius: var(--r20); padding: 14px 16px; }}
.h-title {{ font-weight: 950; font-size: 18px; letter-spacing: .2px; }}
.h-sub {{ color: var(--mut); margin-top: 2px; font-size: 13px; line-height: 1.35; }}

.chip {{
  display:inline-flex; align-items:center; gap:8px;
  background: var(--chip);
  border: 1px solid var(--chipb);
  border-radius: 999px;
  padding: 7px 12px;
  color: var(--mut);
  font-size: 13px;
  font-weight: 850;
}}
.chip b {{ color: var(--txt); font-weight: 1000; }}
.small {{ font-size: 13px; color: var(--mut); }}

.statline {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; }}
.statlabel {{ font-weight: 850; color: var(--txt); }}
.statvalue {{ font-weight: 900; font-size: 20px; color: var(--txt); }}

hr {{ border-color: var(--line) !important; }}

div[data-testid="stWidgetLabel"] label {{
  color: var(--mut) !important;
  font-weight: 850 !important;
}}

/* ===== Inputs: simple + flat ===== */
.stTextInput input,
.stTextArea textarea,
.stDateInput input,
.stNumberInput input {{
  color: var(--txt) !important;
  background: var(--surface) !important;
  border: 1px solid var(--line) !important;
  border-radius: var(--r12) !important;
  box-shadow: none !important;
}}

.stTextInput input:focus,
.stTextArea textarea:focus,
.stDateInput input:focus,
.stNumberInput input:focus {{
  border-color: var(--brand2) !important;
  outline: none !important;
  box-shadow: none !important;
}}

/* Select boxes: match inputs */
div[data-baseweb="select"] > div {{
  border-radius: var(--r12) !important;
  background: var(--surface) !important;
  border: 1px solid var(--line) !important;
  box-shadow: none !important;
}}
div[data-baseweb="select"] * {{ color: var(--txt) !important; }}

/* Buttons — Duolingo-like (chunky + pressed) */
.stButton>button, .stDownloadButton>button{{
  border-radius: 16px !important;
  border: 2px solid rgba(0,0,0,0) !important;
  background: linear-gradient(180deg, var(--surface), var(--surface2)) !important;
  color: var(--txt) !important;
  font-weight: 1000 !important;
  letter-spacing: .2px !important;
  padding: .58rem 1.05rem !important;
  min-height: 44px !important;
  box-shadow:
    0 6px 0 rgba(0,0,0,.22),
    0 16px 26px rgba(0,0,0,.18) !important;
  transition: transform .08s ease, filter .10s ease, box-shadow .10s ease !important;
}}
.stButton>button:hover, .stDownloadButton>button:hover{{
  transform: translateY(-1px);
  filter: brightness(1.05);
}}
.stButton>button:active, .stDownloadButton>button:active{{
  transform: translateY(2px);
  box-shadow:
    0 3px 0 rgba(0,0,0,.22),
    0 10px 18px rgba(0,0,0,.16) !important;
}}

/* Primary CTA */
.stButton>button[kind="primary"]{{
  background: linear-gradient(180deg, rgba(88,204,2,1), rgba(58,184,0,1)) !important;
  color: #07110a !important;
  border: 2px solid rgba(255,255,255,.12) !important;
  box-shadow:
    0 6px 0 rgba(0,0,0,.28),
    0 18px 34px rgba(88,204,2,.18) !important;
}}
.stButton>button[kind="primary"]:active{{
  box-shadow:
    0 3px 0 rgba(0,0,0,.28),
    0 12px 22px rgba(88,204,2,.16) !important;
}}

/* Compact buttons (used in per-card action bars) */
.card-action-row .stButton > button{{
  padding: 0.35rem 0.70rem !important;
  font-size: 0.86rem !important;
  min-height: 38px !important;
  border-radius: 14px !important;
  box-shadow:
    0 5px 0 rgba(0,0,0,.22),
    0 12px 18px rgba(0,0,0,.16) !important;
}}


/* Tabs */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  gap: 8px;
  padding: 6px 8px;
  background: linear-gradient(180deg, var(--surface), var(--surface2));
  border: 1px solid var(--line);
  border-radius: 999px;
  box-shadow: var(--sh2);
}}
div[data-testid="stTabs"] [data-baseweb="tab"] {{
  border-radius: 999px !important;
  padding: 10px 14px !important;
  font-weight: 950 !important;
  color: var(--mut) !important;
}}
div[data-testid="stTabs"] [aria-selected="true"] {{
  background: linear-gradient(180deg, rgba(28,176,246,.20), rgba(88,204,2,.14)) !important;
  color: var(--txt) !important;
}}

/* Sticky action footer */
.sticky-bottom {{
  position: sticky;
  bottom: 0;
  z-index: 50;
  padding-top: 10px;
  padding-bottom: 10px;
  background: linear-gradient(180deg, rgba(0,0,0,0), var(--bg2) 35%);
}}

/* Desktop segmented nav (radio) */
div[data-testid="stRadio"] > div {{
  background: linear-gradient(180deg, var(--surface), var(--surface2));
  border: 1px solid var(--line);
  border-radius: 30px;
  padding: 8px 10px;
  box-shadow: var(--sh2);
}}

/* Remove radio circle + dot */
div[data-testid="stRadio"] input[type="radio"] {{
  position: absolute !important;
  opacity: 0 !important;
  width: 0 !important;
  height: 0 !important;
  pointer-events: none !important;
}}
div[data-testid="stRadio"] label > div:first-child {{ display: none !important; }}
div[data-testid="stRadio"] label {{
  background: transparent;
  border-radius: 999px;
  padding: 10px 14px;
  margin: 4px 6px;
  transition: transform .10s ease, background .12s ease, filter .12s ease;
  color: var(--mut);
  font-weight: 950;
}}
div[data-testid="stRadio"] label:hover {{
  transform: translateY(-1px);
  background: rgba(28,176,246,.10);
  color: var(--txt);
}}
div[data-testid="stRadio"] label:has(input:checked) {{
  background: linear-gradient(180deg, rgba(28,176,246,.20), rgba(88,204,2,.14));
  color: var(--txt);
  box-shadow: 0 10px 22px rgba(0,0,0,.10);
}}
div[data-testid="stRadio"] label * {{ color: inherit !important; }}

/* Cards page: bordered container "tiles" */
div[data-testid="stVerticalBlockBorderWrapper"] {{
  border-radius: 16px !important;
  overflow: hidden !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  box-shadow: 0 12px 34px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.06) !important;
  transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease, filter 160ms ease !important;
  background: transparent !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{
  background:
    radial-gradient(520px 240px at 18% 18%, rgba(28,176,246,0.16), transparent 60%),
    radial-gradient(520px 240px at 86% 86%, rgba(88,204,2,0.12), transparent 62%),
    linear-gradient(180deg, rgba(255,255,255,0.10), rgba(255,255,255,0.05)) !important;
  padding: 16px 16px 14px 16px !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
  transform: translateY(-3px) !important;
  border-color: rgba(255,255,255,0.20) !important;
  box-shadow: 0 16px 44px rgba(0,0,0,0.36), 0 0 0 1px rgba(255,255,255,0.04), inset 0 1px 0 rgba(255,255,255,0.07) !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:hover > div {{
  filter: brightness(1.06) !important;
}}

a {{ color: var(--brand2); }}

/* === Horizontal control rows: align mixed widgets (buttons/inputs/selects) === */
.ctl-label {{
  height: 18px;            /* reserve a consistent label slot */
  margin-bottom: 6px;
  display: flex;
  align-items: flex-end;
  font-weight: 950;
  font-size: 13px;
  color: var(--mut);
}}

/* Card action buttons: compact sizing */
.card-action-row .stButton > button {{
  padding: 0.18rem 0.55rem !important;
  font-size: 0.82rem !important;
  line-height: 1.05 !important;
  min-height: 32px !important;
  border-radius: 999px !important;
}}
.card-action-row .stButton {{margin: 0 !important; }}
.card-action-row [data-testid="column"] {{ padding-left: 0 !important; padding-right: 0 !important; }}

</style>
"""
    st.markdown(textwrap.dedent(css).lstrip(), unsafe_allow_html=True)

# =========================
# Utils
# =========================
def today_utc_date() -> date:
    return datetime.utcnow().date()

def iso_date(d: date) -> str:
    return d.isoformat()

def clamp_int(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(x)))

def norm_text(s: str) -> str:
    return (s or "").strip()

def norm_word(s: str) -> str:
    return (s or "").strip().lower()

def safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

def toast(msg: str, icon: str = "✅") -> None:
    # st.toast exists in newer Streamlit; fallback to st.success.
    fn = getattr(st, "toast", None)
    if callable(fn):
        fn(msg, icon=icon)
    else:
        st.success(msg)

# =========================
# Gamification
# =========================
def level_from_xp(xp: int) -> Tuple[int, int, int]:
    xp = max(0, int(xp))
    level = xp // 10
    xp_in_level = xp % 10
    xp_need = 10
    return level, xp_in_level, xp_need


def copy_to_clipboard_button(text: str, label: str = "Copy text") -> None:
    """
    Renders a small button that copies `text` to clipboard (browser-side).
    """
    safe = (text or "").replace("\\", "\\\\").replace("`", "\\`")
    b64 = base64.b64encode((text or "").encode("utf-8")).decode("utf-8")
    components.html(
        f"""
<div style="display:flex; gap:10px; align-items:center; margin-top:6px;">
  <button id="copyBtn" style="
    padding:8px 12px; border-radius:12px; border:1px solid var(--line);
    background: var(--surface); color: var(--txt); cursor:pointer;">
    {label}
  </button>
  <span id="copyMsg" style="color: var(--mut); font-size: 13px;"></span>
</div>
<script>
(function() {{
  const btn = document.getElementById("copyBtn");
  const msg = document.getElementById("copyMsg");
  btn.onclick = async () => {{
    try {{
      const txt = atob("{b64}");
      await navigator.clipboard.writeText(txt);
      msg.textContent = "Copied ✓";
      setTimeout(()=>msg.textContent="", 1200);
    }} catch(e) {{
      msg.textContent = "Copy failed (browser blocked)";
      setTimeout(()=>msg.textContent="", 1800);
    }}
  }};
}})();
</script>
""",
        height=55,
    )



def carrots_and_croissants() -> Tuple[int, int, int]:
    carrots = int(st.session_state.get("xp", 0) or 0)
    carrots = max(0, carrots)
    croissants = carrots // 10
    toward = carrots % 10
    return carrots, croissants, toward

def bump_xp(amount: int) -> None:
    amount = int(amount)
    if amount <= 0:
        return

    today = iso_date(today_utc_date())
    last = st.session_state.get("last_xp_date", today)

    try:
        last_d = datetime.fromisoformat(last).date()
    except Exception:
        last_d = today_utc_date()

    if last_d == today_utc_date():
        pass
    elif last_d == today_utc_date() - timedelta(days=1):
        st.session_state.streak = int(st.session_state.get("streak", 1)) + 1
    else:
        st.session_state.streak = 1

    st.session_state.last_xp_date = today
    st.session_state.xp = int(st.session_state.get("xp", 0)) + amount

    try:
        set_user_state(
            xp=int(st.session_state.get("xp", 0) or 0),
            streak=int(st.session_state.get("streak", 1) or 1),
            last_xp_date=str(st.session_state.get("last_xp_date") or today),
        )
    except Exception:
        pass

def cigarettes_from_xp(xp: int):
    """5 croissants => 1 cigarette. (1 croissant = 10 carrots) so 1 cigarette = 50 carrots.
    Returns (cigarettes, croissants_toward_next_cigarette).
    """
    carrots = max(0, int(xp or 0))
    croissants = carrots // 10
    cigarettes = croissants // 5
    toward = croissants % 5
    return cigarettes, toward


# =========================
# DB Layer
# =========================
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db() -> None:
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            language TEXT NOT NULL DEFAULT 'fr',
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '',
            example TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            card_id INTEGER PRIMARY KEY,
            due_date TEXT NOT NULL,
            interval_days INTEGER NOT NULL DEFAULT 0,
            repetitions INTEGER NOT NULL DEFAULT 0,
            ease REAL NOT NULL DEFAULT 2.5,
            last_reviewed_at TEXT,
            last_quality INTEGER,
            FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
        );
        """
    )

    # Migration safety (older DB)
    try:
        cur.execute("PRAGMA table_info(reviews);")
        cols = [r[1] for r in cur.fetchall()]
        if "last_quality" not in cols:
            cur.execute("ALTER TABLE reviews ADD COLUMN last_quality INTEGER;")
    except Exception:
        pass

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            xp INTEGER NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 1,
            last_xp_date TEXT NOT NULL
        );
        """
    )
    cur.execute("SELECT id FROM user_state WHERE id = 1;")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO user_state(id, xp, streak, last_xp_date) VALUES(1, 0, 1, ?);",
            (iso_date(today_utc_date()),),
        )

    
    # =========================


    # =========================
    # Notebook PDF + Vocab
    # =========================
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pdf_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            data BLOB NOT NULL,
            uploaded_at TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pdf_vocab (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            meaning TEXT NOT NULL DEFAULT '',
            context TEXT NOT NULL DEFAULT '',
            page INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(book_id) REFERENCES pdf_books(id) ON DELETE CASCADE
        );
        """
    )

    conn.commit()
    conn.close()



def get_user_state() -> Dict[str, Any]:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT xp, streak, last_xp_date FROM user_state WHERE id=1;")
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"xp": 0, "streak": 1, "last_xp_date": iso_date(today_utc_date())}
    xp, streak, last_xp_date = row
    return {"xp": int(xp or 0), "streak": int(streak or 1), "last_xp_date": str(last_xp_date or iso_date(today_utc_date()))}

def set_user_state(xp: int, streak: int, last_xp_date: str) -> None:
    xp_i = int(xp)
    streak_i = int(streak)
    last_s = str(last_xp_date)

    last_err: Optional[Exception] = None
    for _ in range(3):
        try:
            conn = db()
            conn.execute(
                """
                INSERT INTO user_state(id, xp, streak, last_xp_date)
                VALUES(1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    xp=excluded.xp,
                    streak=excluded.streak,
                    last_xp_date=excluded.last_xp_date;
                """,
                (xp_i, streak_i, last_s),
            )
            conn.commit()
            conn.close()
            return
        except Exception as e:
            last_err = e
            try:
                conn.close()
            except Exception:
                pass
            import time as _time
            _time.sleep(0.05)
    if last_err:
        raise last_err

def sync_session_from_db() -> None:
    s = get_user_state()
    db_xp = int(s.get("xp", 0) or 0)
    db_streak = int(s.get("streak", 1) or 1)
    db_last = str(s.get("last_xp_date") or iso_date(today_utc_date()))

    cur_xp = int(st.session_state.get("xp", 0) or 0)
    cur_streak = int(st.session_state.get("streak", 1) or 1)

    if "xp" not in st.session_state or db_xp > cur_xp:
        st.session_state.xp = db_xp
    if "streak" not in st.session_state or db_streak > cur_streak:
        st.session_state.streak = db_streak
    st.session_state.last_xp_date = db_last

def count_cards_db() -> int:
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards;")
        n = cur.fetchone()[0]
        conn.close()
        return int(n or 0)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 0

def reconcile_carrots_with_cards() -> None:
    """Ensure carrots (XP) is at least the number of cards ever created."""
    try:
        total_cards = count_cards_db()
        cur_xp = int(st.session_state.get("xp", 0) or 0)
        if total_cards > cur_xp:
            st.session_state.xp = total_cards
            today = iso_date(today_utc_date())
            st.session_state.setdefault("streak", 1)
            st.session_state.setdefault("last_xp_date", today)
            set_user_state(
                xp=int(st.session_state.get("xp", 0) or 0),
                streak=int(st.session_state.get("streak", 1) or 1),
                last_xp_date=str(st.session_state.get("last_xp_date") or today),
            )
    except Exception:
        pass

def upsert_review_defaults(card_id: int) -> None:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT card_id FROM reviews WHERE card_id=?", (card_id,))
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """
            INSERT INTO reviews(card_id, due_date, interval_days, repetitions, ease, last_reviewed_at)
            VALUES(?, ?, 0, 0, 2.5, NULL)
            """,
            (card_id, iso_date(today_utc_date())),
        )
    conn.commit()
    conn.close()

def create_card(language: str, front: str, back: str, tags: str, example: str, notes: str) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO cards(language, front, back, tags, example, notes, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (norm_text(language), norm_text(front), norm_text(back), norm_text(tags),
         norm_text(example), norm_text(notes), now, now),
    )
    card_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    upsert_review_defaults(card_id)
    return card_id

def update_card(card_id: int, language: str, front: str, back: str, tags: str, example: str, notes: str) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = db()
    conn.execute(
        """
        UPDATE cards
        SET language=?, front=?, back=?, tags=?, example=?, notes=?, updated_at=?
        WHERE id=?
        """,
        (norm_text(language), norm_text(front), norm_text(back), norm_text(tags),
         norm_text(example), norm_text(notes), now, card_id),
    )
    conn.commit()
    conn.close()
    upsert_review_defaults(card_id)

def delete_card(card_id: int) -> None:
    conn = db()
    conn.execute("DELETE FROM cards WHERE id=?", (card_id,))
    conn.commit()
    conn.close()

def fetch_cards(filter_text: str = "", tag: str = "", order_by: str = "updated_desc") -> List[Dict[str, Any]]:
    """Fetch cards with optional free-text filter, tag filter, and stable ordering.

    order_by:
      - updated_desc (default)
      - due_asc
      - created_desc
      - front_asc
    """
    conn = db()
    cur = conn.cursor()
    q = """
    SELECT c.id, c.language, c.front, c.back, c.tags, c.example, c.notes, c.created_at, c.updated_at,
           r.due_date, r.interval_days, r.repetitions, r.ease, r.last_quality, r.last_reviewed_at
    FROM cards c
    LEFT JOIN reviews r ON r.card_id = c.id
    WHERE 1=1
    """
    params: List[Any] = []
    if norm_text(filter_text):
        q += " AND (c.front LIKE ? OR c.back LIKE ? OR c.example LIKE ? OR c.notes LIKE ?)"
        like = f"%{norm_text(filter_text)}%"
        params.extend([like, like, like, like])
    if norm_text(tag):
        q += " AND (',' || REPLACE(c.tags,' ', '') || ',') LIKE ?"
        params.append(f"%,{norm_text(tag).replace(' ', '')},%")

    order_sql = {
        "updated_desc": "c.updated_at DESC, c.id DESC",
        "created_desc": "c.created_at DESC, c.id DESC",
        "due_asc": "date(COALESCE(r.due_date, c.created_at)) ASC, c.id ASC",
        "front_asc": "LOWER(c.front) ASC, c.id ASC",
    }.get(norm_word(order_by), "c.updated_at DESC, c.id DESC")

    q += f" ORDER BY {order_sql}"
    cur.execute(q, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return rows


def fetch_card_by_id(card_id: int) -> Optional[Dict[str, Any]]:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.id, c.language, c.front, c.back, c.tags, c.example, c.notes, c.created_at, c.updated_at,
               r.due_date, r.interval_days, r.repetitions, r.ease, r.last_quality, r.last_reviewed_at
        FROM cards c
        LEFT JOIN reviews r ON r.card_id = c.id
        WHERE c.id = ?
        LIMIT 1
        """,
        (card_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    cols = [d[0] for d in cur.description]
    conn.close()
    return dict(zip(cols, row))

def fetch_cards_created_on(d: date) -> List[Dict[str, Any]]:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.id, c.language, c.front, c.back, c.tags, c.example, c.notes, c.created_at, c.updated_at,
               r.due_date, r.interval_days, r.repetitions, r.ease, r.last_quality, r.last_reviewed_at
        FROM cards c
        LEFT JOIN reviews r ON r.card_id = c.id
        WHERE substr(c.created_at, 1, 10) = ?
        ORDER BY c.created_at DESC
        """,
        (d.isoformat(),),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return rows

def fetch_due_cards(on_date: date) -> List[Dict[str, Any]]:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.id, c.language, c.front, c.back, c.tags, c.example, c.notes,
               r.due_date, r.interval_days, r.repetitions, r.ease, r.last_quality, r.last_reviewed_at
        FROM cards c
        JOIN reviews r ON r.card_id = c.id
        WHERE date(r.due_date) <= date(?)
        ORDER BY date(r.due_date) ASC, c.id ASC
        """,
        (iso_date(on_date),),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return rows

def update_review_state(card_id: int, due_date: date, interval_days: int, repetitions: int, ease: float, last_quality: Optional[int] = None) -> None:
    conn = db()
    conn.execute(
        """
        UPDATE reviews
        SET due_date=?, interval_days=?, repetitions=?, ease=?, last_quality=?, last_reviewed_at=?
        WHERE card_id=?
        """,
        (iso_date(due_date), int(interval_days), int(repetitions), float(ease),
         (None if last_quality is None else int(last_quality)),
         datetime.utcnow().isoformat(timespec="seconds"), card_id),
    )
    conn.commit()
    conn.close()

def all_tags() -> List[str]:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT tags FROM cards")
    raw = [r[0] for r in cur.fetchall()]
    conn.close()
    tags = set()
    for t in raw:
        for part in (t or "").split(","):
            part = part.strip()
            if part:
                tags.add(part)
    return sorted(tags)
# =========================
# Notebook PDF helpers
# =========================
def pdf_book_upsert(name: str, data: bytes) -> int:
    """Insert a PDF book. If same name exists, replace its data."""
    name = norm_text(name) or "book.pdf"
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM pdf_books WHERE name=? LIMIT 1;", (name,))
    row = cur.fetchone()
    if row:
        book_id = int(row[0])
        cur.execute("UPDATE pdf_books SET data=?, uploaded_at=? WHERE id=?;", (sqlite3.Binary(data), now, book_id))
    else:
        cur.execute("INSERT INTO pdf_books(name, data, uploaded_at) VALUES(?,?,?);", (name, sqlite3.Binary(data), now))
        book_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return book_id

def pdf_books_list() -> List[Dict[str, Any]]:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, uploaded_at FROM pdf_books ORDER BY uploaded_at DESC, id DESC;")
    rows = [{"id": int(r[0]), "name": str(r[1]), "uploaded_at": str(r[2])} for r in cur.fetchall()]
    conn.close()
    return rows

def pdf_book_get(book_id: int) -> Optional[Dict[str, Any]]:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, data, uploaded_at FROM pdf_books WHERE id=? LIMIT 1;", (int(book_id),))
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    return {"id": int(r[0]), "name": str(r[1]), "data": bytes(r[2]), "uploaded_at": str(r[3])}

def pdf_book_delete(book_id: int) -> None:
    conn = db()
    conn.execute("DELETE FROM pdf_books WHERE id=?;", (int(book_id),))
    conn.commit()
    conn.close()

def pdf_vocab_add(book_id: int, word: str, meaning: str, context: str, page: Optional[int]) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pdf_vocab(book_id, word, meaning, context, page, created_at) VALUES(?,?,?,?,?,?);",
        (int(book_id), norm_text(word), norm_text(meaning), norm_text(context), (None if page is None else int(page)), now),
    )
    vid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return vid

def pdf_vocab_list(book_id: int, q: str = "") -> List[Dict[str, Any]]:
    conn = db()
    cur = conn.cursor()
    qn = norm_text(q)
    sql = "SELECT id, book_id, word, meaning, context, page, created_at FROM pdf_vocab WHERE book_id=?"
    params: List[Any] = [int(book_id)]
    if qn:
        sql += " AND (word LIKE ? OR meaning LIKE ? OR context LIKE ?)"
        like = f"%{qn}%"
        params.extend([like, like, like])
    sql += " ORDER BY created_at DESC, id DESC"
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return rows

def pdf_vocab_delete(vocab_id: int) -> None:
    conn = db()
    conn.execute("DELETE FROM pdf_vocab WHERE id=?;", (int(vocab_id),))
    conn.commit()
    conn.close()

@st.cache_data(show_spinner=False)
def render_pdf_page_png(pdf_bytes: bytes, page: int, zoom: int) -> bytes:
    """Render a PDF page to PNG bytes (server-side) using PyMuPDF."""
    if fitz is None:
        return b""
    p = max(1, int(page)) - 1
    z = max(50, min(300, int(zoom))) / 100.0
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        p = min(p, max(0, doc.page_count - 1))
        pg = doc.load_page(p)
        pix = pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()

@st.cache_data(show_spinner=False)
def extract_pdf_page_text(pdf_bytes: bytes, page: int) -> str:
    """Extract selectable text from one PDF page using PyMuPDF."""
    if fitz is None:
        return ""
    p = max(1, int(page)) - 1
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        p = min(p, max(0, doc.page_count - 1))
        pg = doc.load_page(p)
        txt = pg.get_text("text") or ""
        txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
        return txt
    finally:
        doc.close()


@st.cache_data(show_spinner=False)
def google_translate(text: str, source_lang: str = "fr", target_lang: str = "en") -> str:
    """Translate text using a lightweight Google Translate endpoint.

    This uses the public "translate_a/single" endpoint (no API key). It may break
    if Google changes it; the UI also provides a direct link to translate.google.com.
    """
    text = (text or "").strip()
    if not text:
        return ""
    sl = norm_word(source_lang) or "auto"
    tl = norm_word(target_lang) or "en"
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": sl,
                "tl": tl,
                "dt": "t",
                "q": text,
            },
            headers=HTTP_HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            return ""
        data = r.json()
        # data[0] is a list of translated segments: [["translated","original",...], ...]
        if not isinstance(data, list) or not data:
            return ""
        segs = data[0]
        if not isinstance(segs, list):
            return ""
        out = "".join([(s[0] if isinstance(s, list) and s else "") for s in segs])
        return (out or "").strip()
    except Exception:
        return ""


# =========================
# SRS (SM-2)
# =========================
def sm2_next(review: Dict[str, Any], quality: int) -> Tuple[int, int, float]:
    q = clamp_int(quality, 0, 5)
    reps = int(review.get("repetitions", 0) or 0)
    interval = int(review.get("interval_days", 0) or 0)
    ease = float(review.get("ease", 2.5) or 2.5)
    if q < 3:
        reps = 0
        interval = 1
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = int(round(interval * ease)) if interval > 0 else int(round(6 * ease))



    ease = ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ease = max(1.3, ease)
    return interval, reps, ease


def pdf_selectable_viewer(pdf_bytes: bytes, page: int = 1, zoom: int = 100, height: int = 820) -> None:
    """
    Render a selectable PDF page inside Streamlit using PDF.js (text layer enabled),
    so the user can highlight/copy text directly from the PDF view.

    Notes:
    - Works when the PDF actually contains text (not only scanned images).
    - Uses a JS renderer to avoid Chrome blocking data: PDFs in iframes.
    """
    try:
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception:
        st.error("Could not load PDF bytes for preview.")
        return

    pg = max(1, int(page))
    zm = max(50, min(300, int(zoom)))
    h = int(height)

    # PDF.js viewer (single-page) with selectable text layer
    components.html(
        f"""
<div id="pdfjs-root" style="width:100%; height:{h}px; position:relative; border-radius:16px; overflow:hidden; border:1px solid rgba(255,255,255,.10);">
  <div id="pdfjs-scroll" style="width:100%; height:100%; overflow:auto; background: rgba(0,0,0,.02);">
    <div id="pdfjs-pagewrap" style="position:relative; margin:16px auto; width:fit-content;">
      <canvas id="pdfjs-canvas" style="display:block;"></canvas>
      <div id="pdfjs-textLayer" class="textLayer" style="position:absolute; inset:0;"></div>
    </div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<script>
(async () => {{
  const b64 = "{b64}";
  const pageNum = {pg};
  const scale = {zm} / 100.0;

  // Configure worker
  if (window['pdfjsLib']) {{
    pdfjsLib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  }} else {{
    const root = document.getElementById("pdfjs-root");
    root.innerHTML = "<div style='padding:16px; font-family:system-ui;'>PDF.js failed to load.</div>";
    return;
  }}

  // Decode base64 → Uint8Array
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

  const loadingTask = pdfjsLib.getDocument({{ data: bytes }});
  const pdf = await loadingTask.promise;
  const page = await pdf.getPage(pageNum);

  const viewport = page.getViewport({{ scale }});
  const canvas = document.getElementById("pdfjs-canvas");
  const ctx = canvas.getContext("2d", {{ alpha: false }});

  // HiDPI / devicePixelRatio handling for crisp rendering AND correct text-layer alignment.
  const outputScale = window.devicePixelRatio || 1;

  // Set actual pixel buffer size
  canvas.width = Math.floor(viewport.width * outputScale);
  canvas.height = Math.floor(viewport.height * outputScale);

  // Set CSS size (layout size in CSS pixels)
  canvas.style.width = Math.floor(viewport.width) + "px";
  canvas.style.height = Math.floor(viewport.height) + "px";

  // Scale drawing operations to match CSS pixels
  ctx.setTransform(outputScale, 0, 0, outputScale, 0, 0);

  // Render page to canvas
  await page.render({{ canvasContext: ctx, viewport }}).promise;

  // Render selectable text layer
  const textLayer = document.getElementById("pdfjs-textLayer");
  textLayer.innerHTML = "";
  textLayer.style.width = Math.floor(viewport.width) + \"px\";
  textLayer.style.height = Math.floor(viewport.height) + \"px\";

  const textContent = await page.getTextContent();
  await pdfjsLib.renderTextLayer({{
    textContent,
    container: textLayer,
    viewport,
    textDivs: []
  }}).promise;

}})().catch((err) => {{
  const root = document.getElementById("pdfjs-root");
  root.innerHTML = "<div style='padding:16px; font-family:system-ui;'>Could not render PDF page: " + String(err) + "</div>";
}});
</script>

<style>
/* IMPORTANT:
   - Canvas is the readable page.
   - TextLayer sits on top for selection/copy.
   - We hide glyph paint (transparent text), but keep the layer interactive. */
#pdfjs-canvas {{ pointer-events: none; }}

.textLayer {{
  opacity: 1;                 /* must be visible for selection in some browsers */
  line-height: 1.0;
  transform-origin: 0 0;
  pointer-events: auto;       /* allow click/drag selection */
  user-select: text;
}}

.textLayer span {{
  position: absolute;
  white-space: pre;
  transform-origin: 0% 0%;
  color: transparent !important;                 /* hide text paint */
  -webkit-text-fill-color: transparent !important;
}}

.textLayer ::selection {{
  background: rgba(88, 204, 2, 0.28);
}}
</style>
        """,
        height=h,
    )

def difficulty_bucket(card_row: Dict[str, Any]) -> str:
    q = card_row.get("last_quality", None)
    if q is None:
        return "new"
    try:
        q = int(q)
    except Exception:
        return "new"
    if q <= 0:
        return "difficult"
    if q >= 4:
        return "difficult"
    if q == 3:
        return "meh"
    return "easy"

# =========================
# Dictionary backends
# =========================
@st.cache_data(show_spinner=False)
def dictapi_lookup(lang: str, word: str) -> Tuple[bool, Any, int]:
    lang = norm_word(lang)
    word = norm_text(word)
    if not lang or not word:
        return False, {"error": "Missing lang or word"}, 0
    url = f"{DICTAPI_BASE}/{lang}/{word}"
    try:
        r = requests.get(url, timeout=10)
        status = r.status_code
        try:
            payload = r.json()
        except Exception:
            payload = {"raw_text": r.text}
        return (status == 200), payload, status
    except Exception as e:
        return False, {"error": str(e)}, 0

def parse_dictapi_payload(payload: Any) -> Dict[str, Any]:
    out = {"phonetics": [], "meanings": []}
    if not isinstance(payload, list) or not payload:
        return out
    entry = payload[0]
    if not isinstance(entry, dict):
        return out
    for p in (entry.get("phonetics", []) or []):
        if isinstance(p, dict):
            out["phonetics"].append({"text": p.get("text") or "", "audio": p.get("audio") or ""})
    for m in (entry.get("meanings", []) or []):
        if not isinstance(m, dict):
            continue
        defs: List[Dict[str, Any]] = []
        for d in (m.get("definitions", []) or []):
            if not isinstance(d, dict):
                continue
            defs.append(
                {"definition": d.get("definition") or "", "example": d.get("example") or "", "synonyms": d.get("synonyms") or []}
            )
        out["meanings"].append({"partOfSpeech": m.get("partOfSpeech") or "", "definitions": defs})
    return out

@st.cache_data(show_spinner=False)
def wiktionary_summary(lang: str, word: str) -> Tuple[bool, Dict[str, Any]]:
    lang = norm_word(lang)
    word = norm_text(word)
    if not lang or not word:
        return False, {"error": "Missing lang or word"}
    base = WIKTIONARY_BASE.get(lang, WIKTIONARY_BASE["fr"])
    title_enc = requests.utils.quote(word, safe="")
    url = f"{base}/api/rest_v1/page/summary/{title_enc}"
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=12)
        status = r.status_code
        try:
            j = r.json()
        except Exception:
            return False, {"error": f"Non-JSON response (status={status})", "raw_text": r.text[:2000], "source": url}
        if status != 200:
            return False, {"error": f"HTTP {status}", "raw": j, "source": url}
        title = j.get("title") or word
        extract = (j.get("extract") or "").strip()
        if not extract:
            return False, {"error": "Empty extract", "raw": j, "source": url}
        return True, {"title": title, "extract": extract, "source": url}
    except Exception as e:
        return False, {"error": str(e), "source": url}

@st.cache_data(show_spinner=False)
def wiktionary_extract(lang: str, word: str) -> Tuple[bool, Dict[str, Any]]:
    lang = norm_word(lang)
    word = norm_text(word)
    if not lang or not word:
        return False, {"error": "Missing lang or word"}
    base = WIKTIONARY_BASE.get(lang, WIKTIONARY_BASE["fr"])
    api = f"{base}/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "explaintext": 1,
        "exsectionformat": "plain",
        "redirects": 1,
        "titles": word,
    }
    try:
        r = requests.get(api, params=params, headers=HTTP_HEADERS, timeout=12)
        status = r.status_code
        try:
            j = r.json()
        except Exception:
            return False, {"error": f"Non-JSON response (status={status})", "raw_text": r.text[:2000], "source": api}
        if status != 200:
            return False, {"error": f"HTTP {status}", "raw": j, "source": api}
        pages = (j.get("query", {}) or {}).get("pages", {}) or {}
        if not pages:
            return False, {"error": "No pages in response", "raw": j, "source": api}
        page = next(iter(pages.values()))
        if not isinstance(page, dict):
            return False, {"error": "Bad page format", "raw": j, "source": api}
        if "missing" in page:
            return False, {"error": "Not found", "raw": page, "source": api}
        title = page.get("title") or word
        extract = (page.get("extract") or "").strip()
        if not extract:
            return False, {"error": "Empty extract", "raw": page, "source": api}
        return True, {"title": title, "extract": extract, "source": api}
    except Exception as e:
        return False, {"error": str(e), "source": api}

def summarize_extract(extract: str, max_lines: int = 18, max_chars: int = 1400) -> str:
    text = (extract or "").strip()
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    snippet = "\n".join(lines[:max_lines]).strip()
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rstrip() + "…"
    return snippet

def best_dictionary_result(lang: str, word: str) -> Tuple[str, Dict[str, Any]]:
    lang = norm_word(lang)
    word = norm_text(word)

    if lang == "en":
        ok, payload, status = dictapi_lookup(lang, word)
        parsed = parse_dictapi_payload(payload) if ok else {"phonetics": [], "meanings": []}
        if ok and parsed["meanings"]:
            return "dictapi", {"status": status, "raw": payload, "parsed": parsed}

    ok, data = wiktionary_summary(lang, word)
    if ok:
        return "wiktionary_summary", data

    ok2, data2 = wiktionary_extract(lang, word)
    if ok2:
        return "wiktionary_extract", data2

    ok3, payload3, status3 = dictapi_lookup(lang, word)
    parsed3 = parse_dictapi_payload(payload3) if ok3 else {"phonetics": [], "meanings": []}
    if ok3 and parsed3["meanings"]:
        return "dictapi", {"status": status3, "raw": payload3, "parsed": parsed3}

    return "none", {"errors": {"wiktionary_summary": data, "wiktionary_extract": data2, "dictapi": {"status": status3, "raw": payload3}}}

# =========================
# UI helpers
# =========================
def chip(icon: str, label: str, value: str) -> str:
    return f"<span class='chip'>{icon} <b>{label}</b> {value}</span>"

def badge_row(items: List[Tuple[str, str]]) -> None:
    html = " ".join([f"<span class='chip'>{ic} <b>{txt}</b></span>" for ic, txt in items])
    st.markdown(html, unsafe_allow_html=True)


def app_header(bp: str) -> None:
    carrots, croissants, toward = carrots_and_croissants()
    streak = int(st.session_state.get("streak", 1))
    level, xp_in, xp_need = level_from_xp(carrots)
    total_cards = count_cards_db()
    due_today = len(fetch_due_cards(today_utc_date()))
    cigarettes, cig_toward = cigarettes_from_xp(carrots)

    # Header
    with st.container():
        st.markdown(
            f"""
<div class="card" style="padding:14px 14px; margin-bottom:10px;">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">
    <div>
      <div style="font-weight:1000; font-size:22px; letter-spacing:.2px;">Charlot</div>
      <div class="h-sub">Dictionary • Flashcards • Review • Notes</div>
    </div>
    <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
      {chip("🥕","XP", str(carrots))}
      {chip("🥐","Level", str(level))}
      {chip("🚬","Cig", str(cigarettes))}
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )


def render_quick_find_results(query: str) -> None:
    q = query.strip()
    cards = fetch_cards(q.replace("tag:", "").strip() if q.startswith("tag:") else q)

    # Special: #id direct open
    if q.startswith("#"):
        try:
            cid = int(q[1:])
            c = fetch_card_by_id(cid)
            if c:
                st.session_state.selected_card_id = cid
                st.session_state.nav = "Cards"
                st.rerun()
        except Exception:
            pass

    # Tag quick filter
    if q.lower().startswith("tag:"):
        tag = q.split(":", 1)[1].strip()
        cards = fetch_cards("", tag)

    if not cards:
        st.caption("No matches.")
        return

    st.caption(f"Matches: {min(len(cards), 8)} / {len(cards)}")
    for c in cards[:8]:
        title = (c.get("front") or "").strip() or f"Card #{c['id']}"
        cols = st.columns([1.0, 3.0, 1.0])
        with cols[0]:
            st.markdown(f"<span class='chip'>#{c['id']}</span>", unsafe_allow_html=True)
        with cols[1]:
            st.write(title)
            if c.get("tags"):
                st.caption(c.get("tags"))
        with cols[2]:
            if st.button("Open", key=f"qf_open_{c['id']}", use_container_width=True):
                st.session_state.selected_card_id = int(c["id"])
                st.session_state.nav = "Cards"
                st.rerun()

def top_nav(bp: str) -> str:
    cur = st.session_state.get("nav", "Home")
    page_names = [name for _, name in PAGES]
    page_labels = [f"{ic} {name}" for ic, name in PAGES]
    label_to_name = {f"{ic} {name}": name for ic, name in PAGES}

    if bp == "m":
        with st.expander("☰ Menu", expanded=False):
            idx = page_names.index(cur) if cur in page_names else 0
            pick = st.selectbox("Menu", page_labels, index=idx, label_visibility="collapsed", key="nav_mobile_select")
            st.session_state.nav = label_to_name[pick]
    else:
        idx = page_names.index(cur) if cur in page_names else 0
        pick = st.radio("Navigation", page_labels, index=idx, horizontal=True, label_visibility="collapsed", key="nav_desktop_radio")
        st.session_state.nav = label_to_name[pick]
    return st.session_state.nav

# =========================
# Flashcard renderer
# =========================
def render_flashcard_html(front: str, back: str, meta_left: str = "", meta_right: str = "", height: int = 380, theme: str = "Dark") -> None:
    t = THEMES.get(theme, THEMES["Dark"])

    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    cid = f"fc_{abs(hash((front, back, meta_left, meta_right, theme))) % 10_000_000}"
    front_html = esc(front)
    back_html = esc(back).replace("\n", "<br/>")
    meta_left = esc(meta_left)
    meta_right = esc(meta_right)

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  :root {{
    --txt: {t["txt"]};
    --mut: {t["mut"]};
    --line: {t["line"]};
    --brand: {t["brand"]};
    --brand2: {t["brand2"]};
    --surface: {t["surface"]};
    --surface2: {t["surface2"]};
    --sh: {t["shadow"]};
  }}
  html, body {{
    margin:0; padding:0;
    background: transparent;
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
    color: var(--txt);
  }}
  @keyframes enter {{
    from {{ opacity:0; transform: translateY(10px) scale(.992); }}
    to   {{ opacity:1; transform: translateY(0) scale(1); }}
  }}

  .wrap {{ display:flex; justify-content:center; animation: enter .18s ease-out; }}
  .flip {{
    width: min(860px, 100%);
    height: 320px;
    perspective: 1400px;
    margin: 8px auto 6px auto;
  }}
  .flip input {{
    position:absolute; opacity:0; pointer-events:none; width:1px; height:1px;
  }}
  .flip-card {{
    width:100%; height:100%;
    position:relative;
    transform-style:preserve-3d;
    transition: transform .58s cubic-bezier(.2,.9,.2,1);
  }}
  .flip input:checked + .flip-card {{ transform: rotateY(180deg); }}

  .face {{
    position:absolute; inset:0;
    border-radius: 28px;
    border: 1px solid var(--line);
    box-shadow: var(--sh);
    backface-visibility:hidden;
    overflow:hidden;
  }}
  .front {{
    background:
      radial-gradient(600px 260px at 18% 10%, rgba(28,176,246,.20), transparent 60%),
      radial-gradient(620px 280px at 86% 86%, rgba(88,204,2,.14), transparent 62%),
      linear-gradient(180deg, var(--surface), var(--surface2));
  }}
  .back {{
    transform: rotateY(180deg);
    background:
      radial-gradient(650px 300px at 20% 20%, rgba(88,204,2,.18), transparent 62%),
      radial-gradient(650px 300px at 86% 86%, rgba(28,176,246,.14), transparent 62%),
      linear-gradient(180deg, var(--surface), var(--surface2));
  }}

  .inner {{
    height:100%;
    padding: 22px 24px;
    display:flex;
    flex-direction:column;
    justify-content:center;
    gap: 12px;
  }}
  .top {{
    display:flex; justify-content:space-between; align-items:center;
    color: var(--mut);
    font-size: 13px;
    margin-bottom: 4px;
    font-weight: 800;
  }}
  .pill {{
    display:inline-flex; align-items:center; gap:8px;
    padding: 7px 11px;
    border-radius: 999px;
    background: rgba(0,0,0,.06);
    border: 1px solid var(--line);
  }}

  .title {{
    font-size: clamp(28px, 3.2vw, 48px);
    font-weight: 1000;
    letter-spacing: .2px;
    line-height: 1.05;
  }}
  .body {{
    font-size: 16px;
    color: var(--txt);
    line-height: 1.55;
  }}
  .hint {{
    display:inline-flex; align-items:center; gap:8px;
    color: var(--mut);
    font-size: 13px;
    padding-top: 8px;
    font-weight: 800;
  }}
  kbd {{
    background: rgba(0,0,0,.12);
    border:1px solid var(--line);
    border-bottom-color: rgba(0,0,0,.22);
    border-radius: 9px;
    padding: 2px 8px;
    font-size: 12px;
    color: var(--txt);
  }}
</style>
</head>
<body>
  <div class="wrap">
    <label class="flip" for="{cid}" title="Click to flip">
      <input id="{cid}" type="checkbox"/>
      <div class="flip-card">
        <div class="face front">
          <div class="inner">
            <div class="top">
              <span class="pill">🏷️ {meta_left}</span>
              <span class="pill">⏳ {meta_right}</span>
            </div>
            <div class="title">{front_html}</div>
            <div class="hint">Tap to flip <kbd>Space</kbd> or click</div>
          </div>
        </div>

        <div class="face back">
          <div class="inner">
            <div class="top">
              <span class="pill">✅ Answer</span>
              <span class="pill">🧠 Recall</span>
            </div>
            <div class="body">{back_html}</div>
            <div class="hint">Tap to flip back</div>
          </div>
        </div>
      </div>
    </label>
  </div>
</body>
</html>"""
    components.html(html, height=height, scrolling=False)

def select_card(card_id: int) -> None:
    st.session_state.selected_card_id = int(card_id)
    st.session_state.scroll_to_selected_card = True

def render_selected_card_viewer(title: str = "Selected card") -> None:
    cid = st.session_state.get("selected_card_id")
    if not cid:
        return
    card = fetch_card_by_id(int(cid))
    if not card:
        st.session_state.selected_card_id = None
        return

    anchor_id = f"card_viewer_{card['id']}"
    st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)

    if st.session_state.get("scroll_to_selected_card", False):
        st.session_state.scroll_to_selected_card = False  # one-shot
        components.html(
            f"""
<script>
(function() {{
  const id = "{anchor_id}";
  function go() {{
    const el = window.parent.document.getElementById(id) || document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({{ behavior: "smooth", block: "start" }});
    setTimeout(() => window.parent.scrollBy(0, -80), 120);
  }}
  setTimeout(go, 60);
}})();
</script>
            """,
            height=0,
        )

    st.markdown(f"### {title} • #{card['id']}")
    st.caption(f"lang: {card.get('language','')} • created: {card.get('created_at','—')[:19]} • due: {card.get('due_date','—')}")
    if card.get("tags"):
        st.markdown(f"<span class='chip'>🏷️ <b>{card['tags']}</b></span>", unsafe_allow_html=True)

    if st.button("Close", key=f"close_card_{card['id']}_viewer"):
        st.session_state.selected_card_id = None
        st.rerun()

    meta_left = f"#{card['id']} • {card.get('language','fr')}"
    meta_right = f"due {card.get('due_date','—')}"
    render_flashcard_html(front=card.get("front", "") or "", back=card.get("back", "") or "", meta_left=meta_left, meta_right=meta_right, height=360, theme=st.session_state.get("theme", "Dark"))

    extra = []
    if (card.get("example") or "").strip():
        extra.append(("Example", card.get("example", "")))
    if (card.get("notes") or "").strip():
        extra.append(("Notes", card.get("notes", "")))
    if extra:
        with st.expander("More", expanded=False):
            for k, v in extra:
                st.markdown(f"**{k}**")
                st.write(v)

# =========================
# Pages
# =========================
def progress_ring_html(pct: int, label: str, sub: str) -> str:
    pct = max(0, min(100, int(pct)))
    return f"""
<div style="display:flex; align-items:center; gap:14px;">
  <div style="
      width:64px; height:64px; border-radius:999px;
      background: conic-gradient(var(--brand) {pct}%, rgba(0,0,0,.10) 0);
      display:grid; place-items:center;
      box-shadow: var(--sh2);
      border:1px solid var(--line);
  ">
    <div style="
        width:48px; height:48px; border-radius:999px;
        background: linear-gradient(180deg, var(--surface), var(--surface2));
        display:grid; place-items:center;
        font-weight:1000;
    ">{pct}%</div>
  </div>
  <div>
    <div style="font-weight:1000; font-size:16px;">{label}</div>
    <div class="small">{sub}</div>
  </div>
</div>
"""

def build_due_calendar_html(days: int = 14) -> str:
    start = today_utc_date()
    counts = []
    maxc = 1
    for i in range(days):
        d = start + timedelta(days=i)
        c = len(fetch_due_cards(d))
        counts.append((d, c))
        maxc = max(maxc, c)

    t = THEMES.get(st.session_state.get("theme", "Dark"), THEMES["Dark"])

    items = []
    for d, c in counts:
        size = 8 + int(14 * (c / maxc)) if maxc > 0 else 8
        op = 0.30 + 0.60 * (c / maxc) if maxc > 0 else 0.30
        label = d.strftime("%a %d")
        items.append(
            f"""
<div class="cell" title="{label}: {c} due">
  <div class="day">{label}</div>
  <div class="dot" style="width:{size}px;height:{size}px;opacity:{op};"></div>
  <div class="num">{c}</div>
</div>
            """
        )

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<style>
  :root {{
    --txt: {t["txt"]};
    --mut: {t["mut"]};
    --line: {t["line"]};
    --surface: {t["surface"]};
    --surface2: {t["surface2"]};
  }}
  html, body {{ margin:0; padding:0; background: transparent; font-family: ui-sans-serif, system-ui; color: var(--txt); }}
  .grid {{
    display:grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 10px;
    padding: 8px 6px;
  }}
  .cell {{
    background: linear-gradient(180deg, var(--surface), var(--surface2));
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 10px 8px;
    text-align:center;
  }}
  .day {{ font-size: 12px; color: var(--mut); margin-bottom: 6px; font-weight: 900; }}
  .dot {{
    margin: 0 auto;
    border-radius: 999px;
    background: radial-gradient(circle at 30% 30%, rgba(28,176,246,.95), rgba(88,204,2,.95));
    box-shadow: 0 10px 22px rgba(0,0,0,.14);
  }}
  .num {{ margin-top: 6px; font-size: 12px; color: var(--mut); font-weight: 900; }}
</style></head>
<body>
  <div class="grid">
    {''.join(items)}
  </div>
</body></html>
"""
    return html

def home_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Home")

    cards_total = count_cards_db()
    due_today = len(fetch_due_cards(today_utc_date()))
    carrots = int(st.session_state.get("xp", 0) or 0)
    cigarettes, cig_toward = cigarettes_from_xp(carrots)
    level, xp_in, xp_need = level_from_xp(carrots)
    pct = 0 if xp_need <= 0 else int(100 * (xp_in / xp_need))

    left, right = st.columns([1.35, 1.0], gap="large")

    with left:
        st.markdown(
            f"""
<div class="card">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
    <div>
      <div class="h-title">Today’s plan</div>
      <div class="h-sub">Keep momentum with small, consistent actions.</div>
    </div>
    <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
      <span class="chip">🗂️ <b>Total</b> {cards_total}</span>
      <span class="chip">📌 <b>Due</b> {due_today}</span>
    </div>
  </div>
  <hr/>
  {progress_ring_html(pct, f"🥐 Level {level}", f"{xp_in}/{xp_need} 🥕 to next 🥐")}
</div>
""",
            unsafe_allow_html=True,
        )

        # Spacer so the primary actions don’t visually “stick” to the card above.
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1.1, 1.1, 1.0])
        with c1:
            if st.button("Start review", type="primary", use_container_width=True):
                st.session_state.nav = "Review"
                st.rerun()
        with c2:
            if st.button("Add a new card", use_container_width=True):
                st.session_state.nav = "Cards"
                st.session_state.edit_card_id = None
                st.rerun()
        with c3:
            if st.button("Dictionary", use_container_width=True):
                st.session_state.nav = "Dictionary"
                st.rerun()

        st.markdown("")
        st.markdown(
            """
<div class="card">
  <div class="h-title">Review calendar</div>
  <div class="h-sub">How many cards are due each day (next 14 days).</div>
</div>
""",
            unsafe_allow_html=True,
        )
        components.html(build_due_calendar_html(14), height=220, scrolling=False)

    with right:
        carrots, croissants, _ = carrots_and_croissants()
        cigarettes, _cig_toward = cigarettes_from_xp(carrots)
        st.markdown(
            f"""
<div class="card">
  <div class="h-title">Stats</div>
  <div class="h-sub">A quick snapshot.</div>
  <hr/>
  <div style="display:flex; flex-direction:column; gap:12px;">
    <div>
      <div class="statline"><span class="statlabel">🔥 Streak</span><span class="statvalue">{int(st.session_state.get("streak", 1) or 1)}</span></div>
      <div class="small">Consecutive days you earned at least 1 🥕.</div>
    </div>
    <div>
      <div class="statline"><span class="statlabel">🥕 Carrots</span><span class="statvalue">{carrots}</span></div>
      <div class="small">Your XP — you earn 🥕 mainly by creating new cards.</div>
    </div>
    <div>
      <div class="statline"><span class="statlabel">🥐 Croissants</span><span class="statvalue">{croissants}</span></div>
      <div class="small">Every 10 🥕 becomes 1 🥐 (level-up).</div>
    </div>
    <div>
      <div class="statline"><span class="statlabel">🚬 Cigarettes</span><span class="statvalue">{cigarettes}</span></div>
      <div class="small">Every 5 🥐 becomes 1 🚬 (50 🥕 total).</div>
    </div>
    <div>
      <div class="statline"><span class="statlabel">📌 Due today</span><span class="statvalue">{due_today}</span></div>
      <div class="small">Cards scheduled to review today.</div>
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

def dictionary_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Dictionary")

    st.markdown(
        """
<div class="card">
  <div class="h-title">Lookup a word</div>
  <div class="h-sub">Fast definitions + save as flashcards.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.form("dict_search_form", clear_on_submit=False):
        colA, colB, colC = st.columns([2.2, 1.0, 1.0])
        with colA:
            word = st.text_input("Word / expression", placeholder="ex: faire, pourtant, un peu…")
        with colB:
            lang = st.selectbox("Language", ["fr", "en"], index=0, help="Lookup language.")
        with colC:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            do = st.form_submit_button("Search", type="primary", use_container_width=True)

    if word.strip():
        w = requests.utils.quote(word.strip())
        st.markdown(
            f"""
<div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:10px;">
  <a href="https://www.wordreference.com/fren/{w}" target="_blank" style="text-decoration:none;"><span class="chip">WordReference ↗</span></a>
  <a href="https://context.reverso.net/translation/french-english/{w}" target="_blank" style="text-decoration:none;"><span class="chip">Reverso ↗</span></a>
  <a href="https://www.larousse.fr/dictionnaires/francais/{w}" target="_blank" style="text-decoration:none;"><span class="chip">Larousse ↗</span></a>
</div>
""",
            unsafe_allow_html=True,
        )

    if not (do and word.strip()):
        return

    with st.spinner("Looking up…"):
        source, data = best_dictionary_result(lang, word)

    st.markdown("---")
    if source == "dictapi":
        parsed = data["parsed"]
        st.success("Source: dictionaryapi.dev")

        if parsed["phonetics"]:
            st.markdown("### 🔊 Pronunciation")
            for p in parsed["phonetics"][:5]:
                cols = st.columns([1, 2])
                with cols[0]:
                    if p["text"]:
                        st.write(f"`{p['text']}`")
                with cols[1]:
                    if p["audio"]:
                        st.audio(p["audio"])

        st.markdown("### 📌 Meanings")
        primary_def = ""
        for m in parsed["meanings"]:
            st.markdown(f"**{m['partOfSpeech'] or '—'}**")
            defs = m["definitions"] or []
            for i, d in enumerate(defs[:6], start=1):
                st.markdown(f"**{i}.** {d['definition']}")
                if d["example"]:
                    st.markdown(f"> _{d['example']}_")
            if not primary_def and defs:
                primary_def = defs[0]["definition"]

        st.markdown("### ➕ Save as flashcard")
        with st.form("add_from_dictapi", clear_on_submit=False):
            front = st.text_input("Front", value=word.strip())
            back = st.text_area("Back", value=primary_def, height=110)
            tags = st.text_input("Tags (comma-separated)", value="dictionary")
            example = st.text_area("Example sentence", value="", height=70)
            notes = st.text_area("Notes", value="", height=70)
            submitted = st.form_submit_button("Add flashcard", type="primary")
            if submitted:
                if not front.strip() or not back.strip():
                    st.warning("Front and Back are required.")
                else:
                    cid = create_card(lang, front, back, tags, example, notes)
                    bump_xp(1)
                    toast(f"Saved card #{cid}. +1 🥕", icon="🥕")
        return

    if source.startswith("wiktionary"):
        st.success(f"Source: Wiktionary ({'REST summary' if source=='wiktionary_summary' else 'extract'})")
        title = data.get("title") or word.strip()
        extract = data.get("extract") or ""
        snippet = summarize_extract(extract)

        st.markdown(f"### {title}")
        st.write(snippet)
        with st.expander("Show full text"):
            st.write(extract)
        st.caption(f"Endpoint: {data.get('source','')}")

        st.markdown("### ➕ Save as flashcard")
        with st.form("add_from_wiktionary", clear_on_submit=False):
            front = st.text_input("Front", value=word.strip())
            back = st.text_area("Back", value=snippet, height=140)
            tags = st.text_input("Tags (comma-separated)", value="wiktionary")
            example = st.text_area("Example sentence", value="", height=70)
            notes = st.text_area("Notes", value=f"Source: {data.get('source','Wiktionary')}", height=70)
            submitted = st.form_submit_button("Add flashcard", type="primary")
            if submitted:
                if not front.strip() or not back.strip():
                    st.warning("Front and Back are required.")
                else:
                    cid = create_card(lang, front, back, tags, example, notes)
                    bump_xp(1)
                    toast(f"Saved card #{cid}. +1 🥕", icon="🥕")
        return

    st.error("No result from any dictionary backend.")
    st.code(safe_json(data), language="json")

def review_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Review")

    # Which bucket list (if any) the user is browsing in Review.
    st.session_state.setdefault("review_bucket_view", "")

    allc = fetch_cards()
    buckets: Dict[str, List[Dict[str, Any]]] = {"new": [], "difficult": [], "meh": [], "easy": []}
    for row in allc:
        buckets.setdefault(difficulty_bucket(row), []).append(row)

    badge_row([
        ("🆕", f"New {len(buckets['new'])}"),
        ("😵", f"Difficult {len(buckets['difficult'])}"),
        ("😐", f"Meh {len(buckets['meh'])}"),
        ("😌", f"Easy {len(buckets['easy'])}"),
    ])

    
    # Browse buckets (tabs)
    due_today = fetch_due_cards(today_utc_date())

    def _render_bucket_list(cards: List[Dict[str, Any]], key_prefix: str, empty_msg: str):
        q = st.text_input("Find", value="", placeholder="Type to filter…", key=f"{key_prefix}_q")
        qn = q.strip().lower()
        shown = 0
        for r in cards:
            front = (r.get("front", "") or "").strip()
            back = (r.get("back", "") or "").strip()
            tags = (r.get("tags", "") or "").strip()
            title = front if front else f"Card #{r.get('id')}"
            hay = f"{front} {back} {tags}".lower()
            if qn and qn not in hay:
                continue
            shown += 1
            cols = st.columns([1.6, 1.0, 0.7])
            with cols[0]:
                st.markdown(f"**{title}**")
                if back:
                    st.caption(textwrap.shorten(back, width=140, placeholder="…"))
            with cols[1]:
                st.caption(f"#{r.get('id')} • {tags or '—'}")
            with cols[2]:
                if st.button("Open", key=f"{key_prefix}_open_{r.get('id')}", use_container_width=True):
                    select_card(int(r.get("id")))
                    st.rerun()
            st.divider()
        if shown == 0:
            st.info(empty_msg)

    tabs = st.tabs([
        f"All due ({len(due_today)})",
        f"🆕 New ({len(buckets['new'])})",
        f"😵 Difficult ({len(buckets['difficult'])})",
        f"😐 Meh ({len(buckets['meh'])})",
        f"😌 Easy ({len(buckets['easy'])})",
    ])

    with tabs[0]:
        _render_bucket_list(
            due_today,
            "tab_due",
            "No cards are due right now."
        )

    with tabs[1]:
        _render_bucket_list(
            buckets.get("new", []),
            "tab_new",
            "No cards in New."
        )

    with tabs[2]:
        _render_bucket_list(
            buckets.get("difficult", []),
            "tab_diff",
            "No cards in Difficult."
        )

    with tabs[3]:
        _render_bucket_list(
            buckets.get("meh", []),
            "tab_meh",
            "No cards in Meh."
        )

    with tabs[4]:
        _render_bucket_list(
            buckets.get("easy", []),
            "tab_easy",
            "No cards in Easy."
        )


    st.markdown("")
    colA, colB, colC = st.columns([1.6, 1.0, 1.0])
    with colA:
        created_on = st.date_input("Browse cards created on", value=today_utc_date())
    with colB:
        st.write("")
        if st.button("Restart queue", use_container_width=True):
            st.session_state.review_idx = 0
            toast("Review queue restarted.", icon="🔁")
            st.rerun()
    with colC:
        st.write("")
        if st.button("Go to Cards", use_container_width=True):
            st.session_state.nav = "Cards"
            st.rerun()

    with st.expander(f"📅 Cards created on {created_on.isoformat()} ({len(fetch_cards_created_on(created_on))})", expanded=False):
        created_cards = fetch_cards_created_on(created_on)
        if not created_cards:
            st.info("No cards were created on this date.")
        else:
            for r in created_cards[:200]:
                label = (r.get("front", "") or "").strip() or f"Card #{r.get('id')}"
                if st.button(label, key=f"created_open_{r.get('id')}", use_container_width=True):
                    select_card(int(r.get("id")))
                    st.rerun()
                st.caption(f"#{r.get('id')} • tags: {r.get('tags','')} • created: {r.get('created_at','—')[:19]}")
                st.divider()

    if st.session_state.get("selected_card_id"):
        render_selected_card_viewer(title="Selected card")

    st.markdown("---")

    due = fetch_due_cards(today_utc_date())
    if not due:
        st.success("No cards due. 🎉")
        st.caption("Add more words in Dictionary or Cards.")
        return

    idx = int(st.session_state.review_idx)
    idx = max(0, min(idx, len(due) - 1))
    card = due[idx]

    badge_row([
        ("📌", f"Queue {len(due)}"),
        ("🧾", f"Card {idx+1}/{len(due)}"),
        ("⏱️", f"Interval {card.get('interval_days',0)}d"),
        ("⚖️", f"Ease {float(card.get('ease',2.5)):.2f}"),
    ])

    meta_left = f"#{card['id']} • {card.get('language','fr')}"
    meta_right = f"due {card.get('due_date','')}"
    render_flashcard_html(front=card["front"], back=card["back"], meta_left=meta_left, meta_right=meta_right, height=390, theme=st.session_state.get("theme", "Dark"))

    if (card.get("example") or "").strip() or (card.get("notes") or "").strip():
        c1, c2 = st.columns([1.2, 1.2])
        with c1:
            if (card.get("example") or "").strip():
                st.markdown("**Example**")
                st.markdown(f"> _{card['example']}_")
        with c2:
            if (card.get("notes") or "").strip():
                st.markdown("**Notes**")
                st.write(card["notes"])

    st.markdown("### 🎯 Grade your recall")
    st.caption("5 = very difficult • 1 = very easy (we convert it internally to SM‑2 quality).")
    q_user = st.radio("Difficulty", [1, 2, 3, 4, 5], index=2, horizontal=True)
    q_sm2 = 6 - int(q_user)

    st.markdown('<div class="sticky-bottom">', unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns([1.2, 1.1, 1.1, 1.0])
    with b1:
        if st.button("Submit grade", type="primary", use_container_width=True):
            interval, reps, ease = sm2_next(card, q_sm2)
            next_due = today_utc_date() + timedelta(days=interval)
            update_review_state(card["id"], next_due, interval, reps, ease, last_quality=int(q_user))
            bump_xp(1)

            st.session_state.review_idx = idx + 1
            if st.session_state.review_idx >= len(due):
                st.balloons()
                st.session_state.review_idx = 0
                toast("Queue complete!", icon="🎉")
            st.rerun()
    with b2:
        if st.button("Skip", use_container_width=True):
            st.session_state.review_idx = idx + 1
            if st.session_state.review_idx >= len(due):
                st.session_state.review_idx = 0
            st.rerun()
    with b3:
        if st.button("Back", use_container_width=True):
            st.session_state.review_idx = max(0, idx - 1)
            st.rerun()
    with b4:
        if st.button("Open card", use_container_width=True):
            select_card(int(card["id"]))
            st.session_state.nav = "Cards"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)



def manage_cards_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Cards")
    st.caption("Search, filter, and manage your flashcards. Tip: type **#123** or **tag:food** in the search box.")

    bp = detect_breakpoint(760)
    is_mobile = (bp == "m")

    tags_list = [""] + all_tags()
    sort_labels = {
        "Recently updated": "updated_desc",
        "Due soon": "due_asc",
        "Newest": "created_desc",
        "A → Z (front)": "front_asc",
    }

    with st.container(border=True):
        f1, f2, f3, f4, f5 = st.columns([2.2, 1.2, 1.1, 1.1, 1.0])
        with f1:
            q = st.text_input(
                "Search",
                placeholder="front/back/example/notes…  (examples: #42, tag:verbs)",
                key="cards_search",
            )
        with f2:
            tag = st.selectbox("Tag", tags_list, index=0, key="cards_tag")
        with f3:
            sort_pick = st.selectbox("Sort", list(sort_labels.keys()), index=0, key="cards_sort")
            order_by = sort_labels.get(sort_pick, "updated_desc")
        with f4:
            st.session_state.cards_page_size = st.selectbox(
                "Page size",
                [12, 18, 24, 36],
                index=[12, 18, 24, 36].index(int(st.session_state.get("cards_page_size", 18))),
                key="cards_page_size_sel",
            )
        with f5:
            st.write("")
            if st.button("＋ New", type="primary", use_container_width=True):
                st.session_state.edit_card_id = None
                st.session_state.selected_card_id = None
                st.session_state.delete_confirm_id = None
                st.session_state.scroll_to_editor = True
                st.rerun()

    # Reset pagination if filters changed
    prev = st.session_state.get("_cards_filters_prev", None)
    cur = (q, tag, order_by, int(st.session_state.get("cards_page_size", 18)))
    if prev != cur:
        st.session_state.cards_page = 1
        st.session_state._cards_filters_prev = cur

    # Quick jump / quick tag filter
    q_eff = q.strip()
    if q_eff.startswith("#"):
        try:
            cid = int(q_eff[1:])
            c = fetch_card_by_id(cid)
            if c:
                select_card(cid)
                st.session_state.edit_card_id = None
                st.session_state.cards_search = ""
                toast(f"Opened card #{cid}.", icon="📌")
        except Exception:
            pass
        q_eff = ""
    elif q_eff.lower().startswith("tag:"):
        tag_from_q = q_eff.split(":", 1)[1].strip()
        if tag_from_q:
            st.session_state.cards_tag = tag_from_q
            tag = tag_from_q
        q_eff = ""

    cards = fetch_cards(q_eff, tag, order_by=order_by)
    total = len(cards)

    # Pagination
    page_size = int(st.session_state.get("cards_page_size", 18))
    pages = max(1, (total + page_size - 1) // page_size)
    st.session_state.cards_page = max(1, min(int(st.session_state.get("cards_page", 1)), pages))

    top_row = st.columns([1.0, 2.4, 1.0])
    with top_row[0]:
        if st.button("◀ Prev", use_container_width=True, disabled=(st.session_state.cards_page <= 1)):
            st.session_state.cards_page -= 1
            st.rerun()
    with top_row[1]:
        if total == 0:
            st.markdown("<div class='small' style='text-align:center; padding-top:6px;'>No cards found.</div>", unsafe_allow_html=True)
        else:
            a = (st.session_state.cards_page - 1) * page_size + 1
            b = min(total, st.session_state.cards_page * page_size)
            st.markdown(
                f"<div class='small' style='text-align:center; padding-top:6px;'>Showing <b>{a}</b>–<b>{b}</b> of <b>{total}</b> • Page <b>{st.session_state.cards_page}</b> / {pages}</div>",
                unsafe_allow_html=True,
            )
    with top_row[2]:
        if st.button("Next ▶", use_container_width=True, disabled=(st.session_state.cards_page >= pages)):
            st.session_state.cards_page += 1
            st.rerun()

    start = (st.session_state.cards_page - 1) * page_size
    end = min(total, start + page_size)
    rows = cards[start:end]

    def editor_panel() -> None:
        editor_anchor_id = "cards_editor_anchor"
        st.markdown(f"<div id='{editor_anchor_id}'></div>", unsafe_allow_html=True)

        # One-shot smooth scroll (triggered by ＋ New)
        if st.session_state.get("scroll_to_editor", False):
            st.session_state.scroll_to_editor = False
            components.html(
                f"""
<script>
(function() {{
  const id = "{editor_anchor_id}";
  function go() {{
    const el = window.parent.document.getElementById(id) || document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({{ behavior: "smooth", block: "start" }});
    // compensate for Streamlit header spacing
    setTimeout(() => window.parent.scrollBy(0, -80), 120);
  }}
  setTimeout(go, 60);
}})();
</script>
""",
                height=0,
            )

        st.markdown("### ✍️ Editor")
        edit_id = st.session_state.get("edit_card_id", None)
        if edit_id is None:
            st.caption("Create a new card.")
            editor_card = {"id": None, "language": "fr", "front": "", "back": "", "tags": "", "example": "", "notes": ""}
        else:
            editor_card = fetch_card_by_id(int(edit_id))
            if not editor_card:
                st.warning("Card not found.")
                st.session_state.edit_card_id = None
                st.rerun()

        form_key = f"card_editor__{edit_id if edit_id is not None else 'new'}__cards_page_v10"
        with st.form(key=form_key, clear_on_submit=False):
            language = st.selectbox("Language", ["fr", "en"], index=0 if editor_card.get("language") == "fr" else 1)
            front = st.text_input("Front", value=editor_card.get("front", ""))
            back = st.text_area("Back", value=editor_card.get("back", ""), height=110)
            tags = st.text_input("Tags (comma-separated)", value=editor_card.get("tags", ""))
            example = st.text_area("Example sentence", value=editor_card.get("example", ""), height=70)
            notes = st.text_area("Notes", value=editor_card.get("notes", ""), height=70)

            submitted = st.form_submit_button("Save", type="primary")
            if submitted:
                if not front.strip() or not back.strip():
                    st.warning("Front and Back are required.")
                else:
                    if editor_card["id"] is None:
                        cid = create_card(language, front, back, tags, example, notes)
                        bump_xp(1)
                        toast(f"Created card #{cid}. +1 🥕", icon="🥕")
                        select_card(cid)
                    else:
                        update_card(int(editor_card["id"]), language, front, back, tags, example, notes)
                        bump_xp(1)
                        toast("Updated. +1 🥕", icon="🥕")
                        select_card(int(editor_card["id"]))
                    st.session_state.edit_card_id = None
                    st.rerun()

    def inspector_panel() -> None:
        with st.container(border=True):
            st.markdown("### Inspector")
            if st.session_state.get("selected_card_id"):
                render_selected_card_viewer(title="Selected card")
            else:
                st.caption("Select a card to preview it here.")
                st.markdown(
                    "<div class='small'>Pro tips:<br/>• Search <b>#id</b> to jump<br/>• Search <b>tag:xxx</b> to filter<br/>• Keep fronts short; put context in example/notes</div>",
                    unsafe_allow_html=True,
                )
            st.markdown("---")
            editor_panel()

    def render_tile(c: Dict[str, Any], key_prefix: str = "") -> None:
        title = (c.get("front", "") or "").strip() or f"Card #{c['id']}"
        due = c.get("due_date") or "—"
        lang = c.get("language", "fr")

        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(f"#{c['id']} • {lang} • due: {due}")

            if c.get("tags"):
                st.markdown(f"<span class='chip'>🏷️ <b>{c['tags']}</b></span>", unsafe_allow_html=True)

            back = (c.get("back") or "").strip()
            if back:
                st.markdown("<div class='small' style='margin-top:8px; font-weight:850;'>Back</div>", unsafe_allow_html=True)
                st.write(back[:180] + ("…" if len(back) > 180 else ""))

            confirm_id = st.session_state.get("delete_confirm_id")
            if confirm_id == c["id"]:
                st.warning("Delete this card? This cannot be undone.")
                d1, d2 = st.columns(2)
                with d1:
                    if st.button("Yes, delete", key=f"{key_prefix}confirm_del_{c['id']}", use_container_width=True):
                        delete_card(c["id"])
                        st.session_state.delete_confirm_id = None
                        if st.session_state.get("selected_card_id") == c["id"]:
                            st.session_state.selected_card_id = None
                        toast("Deleted.", icon="🗑️")
                        st.rerun()
                with d2:
                    if st.button("Cancel", key=f"{key_prefix}cancel_del_{c['id']}", use_container_width=True):
                        st.session_state.delete_confirm_id = None
                        st.rerun()
            else:
                # On mobile widths, short labels + icons prevent awkward wrapping.
                # Desktop keeps full labels.
                if is_mobile:
                    st.markdown('<div class="card-action-row">', unsafe_allow_html=True)
                    a1, a2, a3 = st.columns([1, 1, 1], gap="small")
                    with a1:
                        if st.button("🟢 Open", help="Open this card", key=f"{key_prefix}cards_open_{c['id']}", type="primary", use_container_width=True):
                            select_card(int(c["id"]))
                            st.session_state.edit_card_id = None
                            st.rerun()
                    with a2:
                        if st.button("✏️ Edit", help="Edit this card", key=f"{key_prefix}cards_edit_{c['id']}", use_container_width=True):
                            st.session_state.edit_card_id = int(c["id"])
                            select_card(int(c["id"]))
                            st.session_state.delete_confirm_id = None
                            st.rerun()
                    with a3:
                        if st.button("🗑️ Del", help="Delete (confirm)", key=f"{key_prefix}cards_del_{c['id']}", use_container_width=True):
                            st.session_state.delete_confirm_id = int(c["id"])
                            st.rerun()

                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    a1, a2, a3 = st.columns([1.2, 1.0, 1.0])
                    with a1:
                        if st.button("Open", key=f"{key_prefix}cards_open_{c['id']}", type="primary", use_container_width=True):
                            select_card(int(c["id"]))
                            st.session_state.edit_card_id = None
                            st.rerun()
                    with a2:
                        if st.button("Edit", key=f"{key_prefix}cards_edit_{c['id']}", use_container_width=True):
                            st.session_state.edit_card_id = int(c["id"])
                            select_card(int(c["id"]))
                            st.session_state.delete_confirm_id = None
                            st.rerun()
                    with a3:
                        if st.button("Delete", key=f"{key_prefix}cards_del_{c['id']}", use_container_width=True):
                            st.session_state.delete_confirm_id = int(c["id"])
                            st.rerun()

    def grid_panel() -> None:
        if not rows:
            st.info("No cards matched your filters. Create your first one with **＋ New**.")
            return
        ncol = 1 if is_mobile else 3
        for i in range(0, len(rows), ncol):
            cols = st.columns(ncol, gap="large")
            for j in range(ncol):
                k = i + j
                if k >= len(rows):
                    break
                with cols[j]:
                    render_tile(rows[k], key_prefix=f"t_{rows[k]['id']}_")

    # UX change: keep Cards as the primary content.
    # Inspector + Editor appear *under* the grid (not as a right-side column).
    grid_panel()
    st.markdown("---")
    inspector_panel()

def notebook_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Notebook")

    tabs = st.tabs(["📄 PDF reader", "📝 Notes from cards"])

    with tabs[0]:
        st.caption("Upload a PDF book, read it here, and save vocabulary as you go.")

        up = st.file_uploader("Upload a PDF", type=["pdf"], key="nb_pdf_uploader")
        if up is not None:
            data = up.read()
            if data:
                book_id = pdf_book_upsert(up.name, data)
                st.session_state.nb_pdf_book_id = book_id
                st.session_state.nb_pdf_page = 1
                toast(f"Saved PDF: {up.name}", icon="📄")

        books = pdf_books_list()
        if not books:
            st.info("No PDF uploaded yet. Upload one above.")
            return

        book_labels = [f"{b['name']}  ·  {b['uploaded_at'][:19]}" for b in books]
        id_by_label = {label: b["id"] for label, b in zip(book_labels, books)}
        cur_id = st.session_state.get("nb_pdf_book_id") or books[0]["id"]
        cur_idx = next((i for i, b in enumerate(books) if b["id"] == cur_id), 0)
        pick = st.selectbox("Library", book_labels, index=cur_idx, key="nb_pdf_pick")
        st.session_state.nb_pdf_book_id = int(id_by_label[pick])

        book = pdf_book_get(int(st.session_state.nb_pdf_book_id))
        if not book:
            st.warning("Could not load that PDF.")
            return

        # Helpers (callbacks) — keep Prev/Next reliable even with widgets on the same row
        def _nb_prev() -> None:
            st.session_state.nb_pdf_page = max(1, int(st.session_state.get("nb_pdf_page", 1)) - 1)

        def _nb_next() -> None:
            st.session_state.nb_pdf_page = int(st.session_state.get("nb_pdf_page", 1)) + 1

        # Controls row
        # NOTE: Remove +/- micro-buttons; keep only Prev/Next + direct page input + zoom dropdown.
        c1, c2, c3, c4, c5 = st.columns([0.95, 0.95, 1.35, 1.45, 1.05], gap="small")
        with c1:
            st.markdown("<div class='ctl-label'>&nbsp;</div>", unsafe_allow_html=True)
            st.button("◀ Prev", use_container_width=True, on_click=_nb_prev)
        with c2:
            st.markdown("<div class='ctl-label'>&nbsp;</div>", unsafe_allow_html=True)
            st.button("Next ▶", use_container_width=True, on_click=_nb_next)
        with c3:
            st.markdown("<div class='ctl-label'>Page</div>", unsafe_allow_html=True)
            st.number_input(
                "Page",
                min_value=1,
                step=1,
                key="nb_pdf_page",
                label_visibility="collapsed",
            )
        with c4:
            st.markdown("<div class='ctl-label'>Zoom</div>", unsafe_allow_html=True)
            zoom_opts = [80, 90, 100, 110, 125, 140, 160]
            curz = int(st.session_state.get("nb_pdf_zoom", 100))
            if curz not in zoom_opts:
                st.session_state.nb_pdf_zoom = 100
                curz = 100
            st.selectbox(
                "Zoom",
                zoom_opts,
                index=zoom_opts.index(int(st.session_state.get("nb_pdf_zoom", curz))),
                key="nb_pdf_zoom",
                label_visibility="collapsed",
            )
        with c5:
            st.markdown("<div class='ctl-label'>&nbsp;</div>", unsafe_allow_html=True)
            if st.button("Delete PDF", use_container_width=True):
                pdf_book_delete(int(book["id"]))
                st.session_state.nb_pdf_book_id = None
                st.session_state.nb_pdf_extracted_text = ""
                st.session_state.nb_pdf_text_cache_page = None
                st.rerun()

        # Clamp page after any controls/callbacks
        page = max(1, int(st.session_state.get("nb_pdf_page", 1)))
        # NOTE: do NOT assign to st.session_state.nb_pdf_page here (it is bound to the number_input widget).
        zoom = int(st.session_state.get("nb_pdf_zoom", 100))

        use_native = st.toggle(
            "Selectable PDF view (copy directly from the PDF)",
            value=st.session_state.get("nb_pdf_use_native", True),
            key="nb_pdf_use_native",
            help="Shows the original PDF in your browser so you can highlight/copy text without extracting. Works only if the PDF has a text layer.",
        )

        if use_native:
            pdf_selectable_viewer(book["data"], page=page, zoom=zoom, height=820)
        else:
            png = render_pdf_page_png(book["data"], page, zoom)
            if png:
                st.image(png, use_container_width=True)
            else:
                st.warning("PNG preview needs PyMuPDF. Install it with: `pip install pymupdf`")

        st.markdown("### Selectable text (copy)")
        if fitz is None:
            st.caption("Install PyMuPDF to extract text: `pip install pymupdf`")
        else:
            if st.button("Extract text from this page", use_container_width=True):
                st.session_state.nb_pdf_text_cache_page = page
                st.session_state.nb_pdf_extracted_text = extract_pdf_page_text(book["data"], page)

            extracted = st.session_state.get("nb_pdf_extracted_text", "")
            if extracted and st.session_state.get("nb_pdf_text_cache_page") == page:
                st.text_area("Page text", value=extracted, height=220)
                st.download_button(
                    "Download extracted text (.txt)",
                    data=extracted.encode("utf-8"),
                    file_name=f"{book['name']}_page_{page}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

            # (Google Translate UI is rendered below, always visible)
            else:
                st.caption("Click the button to extract text from the current page (optional).")

        # === Google Translate (always available; independent of Extract Text) ===
        st.markdown("#### Google Translate")
        st.caption("Translate any word/phrase and auto-fill the Save Vocab form.")

        tcol1, tcol2, tcol3 = st.columns([1.45, 0.6, 0.95], gap="small")
        with tcol1:
            st.markdown("<div class='ctl-label'>&nbsp;</div>", unsafe_allow_html=True)
            to_translate = st.text_input(
                "Text to translate",
                value=st.session_state.get("nb_translate_text", ""),
                key="nb_translate_text",
                placeholder="ex: pourtant / se rendre compte / une fois…",
                label_visibility="collapsed",
            )
        with tcol2:
            st.markdown("<div class='ctl-label'>Target</div>", unsafe_allow_html=True)
            tgt = st.selectbox(
                "Target",
                ["en", "de", "fr", "fa"],
                index=0,
                key="nb_translate_tgt",
                label_visibility="collapsed",
            )
        with tcol3:
            st.markdown("<div class='ctl-label'>&nbsp;</div>", unsafe_allow_html=True)
            do_tr = st.button("Translate", key="nb_translate_btn", type="primary", use_container_width=True)

        if do_tr and to_translate.strip():
            translation = google_translate(to_translate, source_lang="fr", target_lang=tgt)
            st.session_state.nb_translate_last = (translation or "").strip()
            if translation:
                st.success(translation)

                # Auto-fill "Save vocab" inputs so the user can save/tag immediately.
                st.session_state["nb_vocab_word"] = to_translate.strip()
                st.session_state["nb_vocab_meaning"] = translation.strip()
                st.session_state["nb_vocab_page"] = int(page)
            else:
                st.info("Could not fetch an instant translation. Use the Google Translate link below.")

        if to_translate.strip():
            import urllib.parse as _urlparse
            q = _urlparse.quote(to_translate.strip())
            st.markdown(
                f"[Open in Google Translate ↗](https://translate.google.com/?sl=fr&tl={tgt}&text={q}&op=translate)",
                unsafe_allow_html=False,
            )

        st.markdown("---")
        st.markdown("### 📌 Save vocabulary from this PDF")
        with st.form("nb_vocab_form", clear_on_submit=True):
            colA, colB = st.columns([1.0, 1.2])
            with colA:
                word = st.text_input(
                    "Word / expression",
                    placeholder="ex: pourtant, se rendre compte…",
                    key="nb_vocab_word",
                    value=st.session_state.get("nb_vocab_word", ""),
                )
                meaning = st.text_input(
                    "Meaning (EN)",
                    placeholder="quick meaning…",
                    key="nb_vocab_meaning",
                    value=st.session_state.get("nb_vocab_meaning", ""),
                )
            with colB:
                context = st.text_area(
                    "Context / sentence (optional)",
                    height=90,
                    placeholder="Paste the sentence from the book…",
                    key="nb_vocab_context",
                    value=st.session_state.get("nb_vocab_context", ""),
                )
            page_in = st.number_input(
                "Page (auto)",
                min_value=1,
                value=int(st.session_state.get("nb_vocab_page", page)),
                step=1,
                key="nb_vocab_page",
            )
            tags_for_cards = st.text_input("Tags for cards (optional)", value="pdf", key="nb_vocab_tags")
            save = st.form_submit_button("Save vocab", type="primary")
            if save:
                if not word.strip():
                    st.warning("Word is required.")
                else:
                    pdf_vocab_add(int(book["id"]), word, meaning, context, int(page_in))
                    toast("Saved vocab", icon="📌")

        st.markdown("### 📚 Saved vocabulary")
        q = st.text_input("Search vocab", value=st.session_state.get("nb_vocab_q", ""), key="nb_vocab_q")
        rows = pdf_vocab_list(int(book["id"]), q=q)
        if not rows:
            st.caption("No vocabulary saved yet for this PDF.")
        else:
            for r in rows[:200]:
                with st.container(border=True):
                    top = st.columns([1.6, 1.1, 0.8, 0.6])
                    with top[0]:
                        st.markdown(f"**{r.get('word','')}**")
                        if (r.get("meaning") or "").strip():
                            st.caption(r.get("meaning"))
                    with top[1]:
                        st.caption(f"p. {r.get('page') or '—'} • {str(r.get('created_at',''))[:19]}")
                    with top[2]:
                        if st.button("➕ Card", key=f"v2c_{r['id']}", use_container_width=True):
                            front = (r.get("word") or "").strip()
                            back = (r.get("meaning") or "").strip() or (r.get("context") or "").strip() or "—"
                            notes = (r.get("context") or "").strip()
                            cid = create_card("fr", front, back, norm_text(tags_for_cards), "", notes)
                            bump_xp(1)
                            toast(f"Created card #{cid}. +1 🥕", icon="🥕")
                    with top[3]:
                        if st.button("🗑️", key=f"vdel_{r['id']}", use_container_width=True):
                            pdf_vocab_delete(int(r["id"]))
                            st.rerun()

                    if (r.get("context") or "").strip():
                        st.markdown("**Context**")
                        st.write(r.get("context"))

    with tabs[1]:
        st.caption("A clean view of saved examples + notes from your flashcards.")
        q = st.text_input("Search notebook", placeholder="type anything…", key="nb_search")
        only_with_notes = st.checkbox("Only show items that have example/notes", value=True)

        cards = fetch_cards(q)
        shown = 0
        for c in cards[:500]:
            has_any = bool((c.get("example") or "").strip() or (c.get("notes") or "").strip())
            if only_with_notes and not has_any:
                continue
            shown += 1
            with st.container(border=True):
                st.markdown(f"**{c['front']}**")
                st.caption(f"#{c['id']} • tags: {c.get('tags','')} • due: {c.get('due_date','—')}")
                cols = st.columns(2)
                with cols[0]:
                    if c.get("example"):
                        st.markdown("**Example**")
                        st.markdown(f"> _{c['example']}_")
                with cols[1]:
                    if c.get("notes"):
                        st.markdown("**Notes**")
                        st.write(c["notes"])
                if st.button("Open", key=f"nb_open_{c['id']}"):
                    select_card(int(c["id"]))
                    st.session_state.nav = "Cards"
                    st.rerun()

        if shown == 0:
            st.info("No notebook entries matched your filters.")

def import_export_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Import / Export (CSV)")
    st.caption("CSV columns: language, front, back, tags, example, notes")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("### Export")
        cards = fetch_cards()
        if st.button("Generate CSV export", type="primary", use_container_width=True):
            out = io.StringIO()
            w = csv.writer(out)
            w.writerow(["language", "front", "back", "tags", "example", "notes"])
            for c in cards:
                w.writerow([c.get("language", "fr"), c["front"], c["back"], c.get("tags", ""), c.get("example", ""), c.get("notes", "")])
            st.download_button(
                "Download CSV",
                data=out.getvalue().encode("utf-8"),
                file_name="charlot_cards.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with col2:
        st.markdown("### Import")
        up = st.file_uploader("Upload CSV", type=["csv"])
        if up is not None:
            try:
                content = up.read().decode("utf-8")
                r = csv.DictReader(io.StringIO(content))
                rows = list(r)
                st.write(f"Rows detected: {len(rows)}")
                if st.button("Import now", type="primary", use_container_width=True):
                    created = 0
                    for row in rows:
                        language = norm_text(row.get("language") or "fr") or "fr"
                        front = norm_text(row.get("front") or "")
                        back = norm_text(row.get("back") or "")
                        if not front or not back:
                            continue
                        tags = norm_text(row.get("tags") or "")
                        example = norm_text(row.get("example") or "")
                        notes = norm_text(row.get("notes") or "")
                        create_card(language, front, back, tags, example, notes)
                        created += 1
                    bump_xp(min(80, created))
                    toast(f"Imported {created} cards. (+XP)", icon="📥")
                    st.rerun()
            except Exception as e:
                st.error(f"Import failed: {e}")

def settings_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Settings")

    st.markdown("### Appearance")
    theme_pick = st.selectbox("Theme", ["Light", "Dark"], index=0 if st.session_state.get("theme") == "Light" else 1)
    if theme_pick != st.session_state.get("theme"):
        st.session_state.theme = theme_pick
        st.rerun()

    st.markdown("---")
    st.markdown("### Database")
    st.write(f"DB file: `{DB_PATH}`")

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("Initialize DB", use_container_width=True):
            init_db()
            toast("Initialized.", icon="🗄️")
    with c2:
        if st.button("Clear Streamlit cache", use_container_width=True):
            st.cache_data.clear()
            toast("Cache cleared.", icon="🧹")
    with c3:
        st.info("Tip: DB is local. If you deploy, use persistent storage (volume / cloud DB).")

    st.markdown("---")
    st.markdown("### Gamification")
    c4, c5 = st.columns(2)
    with c4:
        if st.button("Reset XP / streak", use_container_width=True):
            st.session_state.xp = 0
            st.session_state.streak = 1
            st.session_state.last_xp_date = iso_date(today_utc_date())
            try:
                set_user_state(0, 1, st.session_state.last_xp_date)
            except Exception:
                pass
            toast("Reset.", icon="♻️")
            st.rerun()
    with c5:
        lvl, _, _ = level_from_xp(int(st.session_state.get("xp", 0)))
        st.markdown(
            f"{chip('🏅','Level', str(lvl))} {chip('🥕','Carrots', str(int(st.session_state.get('xp',0) or 0)))} {chip('🥐','Croissants', str(int(st.session_state.get('xp',0) or 0)//10))} {chip('🚬','Cigarettes', str(int(st.session_state.get('xp',0) or 0)//50))}",
            unsafe_allow_html=True,
        )

def about_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## About")

    st.markdown(
        """
<div class="card">
  <div class="h-title">Charlot</div>
  <div class="h-sub">A lightweight French study hub: dictionary → flashcards → spaced repetition.</div>
  <hr/>
  <div class="small" style="margin-bottom:10px;">
    • Dictionary: Wiktionary + DictionaryAPI fallbacks<br/>
    • Flashcards: local SQLite storage<br/>
    • Review: SM‑2 scheduling (spaced repetition)<br/>
    • Gamification: 🥕 carrots (XP), 🥐 croissants (levels), 🔥 streak
  </div>
  <div class="small">Tip: keep cards short, add an example sentence, and review daily.</div>
</div>
""",
        unsafe_allow_html=True,
    )

# =========================
# Main
# =========================
def main() -> None:
    init_db()
    init_session_state()
    sync_session_from_db()
    reconcile_carrots_with_cards()

    inject_global_css(st.session_state.get("theme", "Dark"))
    bp = detect_breakpoint(760)

    app_header(bp)
    nav = top_nav(bp)

    if nav == "Home":
        home_page()
    elif nav == "Dictionary":
        dictionary_page()
    elif nav == "Review":
        review_page()
    elif nav == "Cards":
        manage_cards_page()
    elif nav == "Notes":
        notebook_page()
    elif nav == "Import/Export":
        import_export_page()
    elif nav == "Settings":
        settings_page()
    elif nav == "About":
        about_page()
    else:
        home_page()

if __name__ == "__main__":
    main()
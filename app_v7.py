import csv
import io
import json
import sqlite3
import textwrap
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

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
    "User-Agent": "FrenchStudyHub/4.0 (Streamlit; educational app)",
    "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
}

st.set_page_config(page_title=APP_TITLE, page_icon="🇫🇷", layout="wide")

# =========================
# Theme (Modern / Clean)
# =========================
THEMES = {
    "Dark": {
        "bg": "#0b0f17",
        "bg2": "#0f1623",
        "surface": "rgba(255,255,255,.06)",
        "surface2": "rgba(255,255,255,.04)",
        "txt": "rgba(255,255,255,.92)",
        "mut": "rgba(255,255,255,.66)",
        "mut2": "rgba(255,255,255,.48)",
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


def init_session_state() -> None:
    if "nav" not in st.session_state:
        st.session_state.nav = "Home"
    if "theme" not in st.session_state:
        st.session_state.theme = "Dark"
    if "xp" not in st.session_state:
        st.session_state.xp = 0
    if "streak" not in st.session_state:
        st.session_state.streak = 1
    if "last_xp_date" not in st.session_state:
        st.session_state.last_xp_date = iso_date(today_utc_date())
    if "review_idx" not in st.session_state:
        st.session_state.review_idx = 0
    if "edit_card_id" not in st.session_state:
        st.session_state.edit_card_id = None



def detect_breakpoint(breakpoint_px: int = 760) -> str:
    """
    Returns "m" (mobile) or "d" (desktop) based on a client-side width probe stored in URL query param `bp`.
    We update `bp` with a tiny JS snippet that reloads ONLY when crossing the breakpoint.
    """
    import streamlit.components.v1 as components

    # Read current bp from query params (supports old/new Streamlit APIs)
    try:
        bp = st.query_params.get("bp", None)
    except Exception:
        bp = st.experimental_get_query_params().get("bp", [None])[0]

    # JS computes bp and reloads only if it changed (crossed breakpoint or missing)
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

    # If bp is missing, we just triggered a reload; return a safe default for this run
    return bp or "d"

def inject_global_css(theme_name: str) -> None:
    t = THEMES.get(theme_name, THEMES["Light"])

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
  padding-top: 1.0rem;
  padding-bottom: 4.0rem;
  max-width: 1200px;
}}

header[data-testid="stHeader"]{{ background: rgba(0,0,0,0); }}
div[data-testid="stToolbar"]{{ visibility: hidden; height: 0px; }}
footer{{ visibility:hidden; }}

::selection {{
  background: rgba(88,204,2,.22);
}}

@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to   {{ opacity: 1; transform: translateY(0px); }}
}}
.page {{ animation: fadeIn .20s ease-out; }}

.card {{
  background: linear-gradient(180deg, var(--surface), var(--surface2));
  border: 1px solid var(--line);
  border-radius: var(--r24);
  box-shadow: var(--sh2);
  padding: 18px 18px;
}}
.card-tight {{
  border-radius: var(--r20);
  padding: 14px 16px;
}}
.card-header {{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:12px;
}}
.h-title {{
  font-weight: 950;
  font-size: 18px;
  letter-spacing: .2px;
}}
.h-sub {{
  color: var(--mut);
  margin-top: 2px;
  font-size: 13px;
  line-height: 1.35;
}}

.chip {{
  display:inline-flex; align-items:center; gap:8px;
  background: var(--chip);
  border: 1px solid var(--chipb);
  border-radius: 999px;
  padding: 7px 12px;
  color: var(--mut);
  font-size: 13px;
  font-weight: 800;
}}
.chip b {{ color: var(--txt); font-weight: 950; }}

hr {{ border-color: var(--line) !important; }}

/* Inputs + form controls */
div[data-testid="stWidgetLabel"] label {{
  color: var(--mut) !important;
  font-weight: 850 !important;
}}
div[data-testid="stWidgetLabel"] label p,
div[data-testid="stWidgetLabel"] label span {{
  color: var(--mut) !important;
}}

.stTextInput input,
.stTextArea textarea,
.stDateInput input,
.stNumberInput input {{
  color: var(--txt) !important;
  background: linear-gradient(180deg, var(--surface), var(--surface2)) !important;
  border: 1px solid var(--line) !important;
  border-radius: var(--r12) !important;
}}
.stTextInput input::placeholder,
.stTextArea textarea::placeholder {{
  color: var(--mut2) !important;
}}

div[data-baseweb="select"] > div {{
  border-radius: var(--r12) !important;
  background: linear-gradient(180deg, var(--surface), var(--surface2)) !important;
  border: 1px solid var(--line) !important;
}}
div[data-baseweb="select"] * {{
  color: var(--txt) !important;
}}

/* Buttons (clean + tactile) */
.stButton>button, .stDownloadButton>button {{
  border-radius: 999px !important;
  border: 1px solid var(--chipb) !important;
  background: var(--chip) !important;
  color: var(--txt) !important;
  box-shadow: 0 10px 22px rgba(0,0,0,.12);
  transition: transform .10s ease, filter .10s ease, background .12s ease;
  font-weight: 900 !important;
}}
.stButton>button:hover, .stDownloadButton>button:hover {{
  transform: translateY(-1px);
  filter: brightness(1.04);
}}
.stButton>button:active, .stDownloadButton>button:active {{
  transform: translateY(0px) scale(.99);
}}
.stButton>button[kind="primary"] {{
  border: none !important;
  background: linear-gradient(180deg, rgba(88,204,2,1), rgba(40,160,0,1)) !important;
  color: #07110a !important;
  box-shadow: 0 16px 34px rgba(88,204,2,.20);
}}

/* Tabs-as-nav (Streamlit radio) — ONLY for desktop navbar */
div[data-testid="stRadio"] > div{{
  background: linear-gradient(180deg, var(--surface), var(--surface2));
  border: 1px solid var(--line);
  border-radius: 30px;
  padding: 8px 10px;
  box-shadow: var(--sh2);
}}




/* Mobile: ONLY hamburger */
@media (max-width: 760px){{
  .desktop-nav-wrap{{ display:none !important; }}
}}

/* Desktop: ONLY navbar (hide hamburger) */
@media (min-width: 761px){{
  }}

/* Hamburger list items (more list-like) */

/* --- Nav: remove radio circle + selected dot ---
   Streamlit/BaseWeb renders a circular control inside each label.
   We keep the label clickable, but hide that control so navigation
   happens with a single click on the icon/text only.
*/
div[data-testid="stRadio"] input[type="radio"] {{
  position: absolute !important;
  opacity: 0 !important;
  width: 0 !important;
  height: 0 !important;
  pointer-events: none !important;
}}
div[data-testid="stRadio"] label > div:first-child {{
  display: none !important;  /* the circle + dot wrapper */
}}
div[data-testid="stRadio"] label {{
  background: transparent;
  border-radius: 999px;
  padding: 10px 14px;
  margin: 4px 4px;
  transition: transform .10s ease, background .12s ease, filter .12s ease;
  color: var(--mut);
  font-weight: 950;
}}
div[data-testid="stRadio"] label:hover {{
  transform: translateY(-1px);
  background: rgba(28,176,246,.10);
  color: var(--txt);
}}
/* best-effort "active" look (BaseWeb markup changes sometimes) */
div[data-testid="stRadio"] label:has(input:checked) {{
  background: linear-gradient(180deg, rgba(28,176,246,.20), rgba(88,204,2,.14));
  color: var(--txt);
  box-shadow: 0 10px 22px rgba(0,0,0,.10);
}}


/* ---------- Fix light-mode unreadable text (metrics + some widgets/nav) ---------- */

/* Widget labels: be aggressive (Streamlit DOM differs by widget) */
[data-testid="stWidgetLabel"], 
[data-testid="stWidgetLabel"] * {{
  color: var(--mut) !important;
  font-weight: 850 !important;
}}

/* Metrics (st.metric): label/value/delta colors */
div[data-testid="stMetric"] {{
  color: var(--txt) !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricLabel"],
div[data-testid="stMetric"] [data-testid="stMetricLabel"] * {{
  color: var(--mut) !important;
  font-weight: 900 !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"],
div[data-testid="stMetric"] [data-testid="stMetricValue"] * {{
  color: var(--txt) !important;
  font-weight: 1000 !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricDelta"],
div[data-testid="stMetric"] [data-testid="stMetricDelta"] * {{
  color: var(--mut) !important;
}}

/* Nav (radio): ensure the visible text inherits our color (sometimes stays white in light mode) */
div[data-testid="stRadio"] label * {{
  color: inherit !important;
}}

/* Reduce yellow-ish selection artifacts in some themes */
div[data-testid="stAppViewContainer"] a {{
  color: var(--brand2);
}}

.small {{
  font-size: 13px;
  color: var(--mut);
}}
</style>
"""
    st.markdown(textwrap.dedent(css).lstrip(), unsafe_allow_html=True)


def badge_row(items: List[Tuple[str, str]]) -> None:
    chips = " ".join([f"<span class='chip'>{icon} <b>{label}</b></span>" for icon, label in items])
    st.markdown(chips, unsafe_allow_html=True)


def select_card(card_id: int) -> None:
    st.session_state.selected_card_id = int(card_id)


def render_selected_card_viewer(title: str = "Selected card") -> None:
    """Render the selected card using the same flip-card UI as the review queue."""
    cid = st.session_state.get("selected_card_id")
    if not cid:
        return
    card = fetch_card_by_id(int(cid))
    if not card:
        st.session_state.selected_card_id = None
        return

    topL, topR = st.columns([6, 1])
    with topL:
        st.markdown(f"### {title} • #{card['id']}")
        st.caption(
            f"lang: {card.get('language','')} • created: {card.get('created_at','—')[:19]} • due: {card.get('due_date','—')}"
        )
        if card.get("tags"):
            st.markdown(f"<span class='chip'>🏷️ <b>{card['tags']}</b></span>", unsafe_allow_html=True)
    with topR:
        st.write("")
        if st.button("Close", key=f"close_card_{card['id']}_viewer"):
            st.session_state.selected_card_id = None
            st.rerun()

    meta_left = f"#{card['id']} • {card.get('language','fr')}"
    meta_right = f"due {card.get('due_date','—')}"
    render_flashcard_html(
        front=card.get("front", "") or "",
        back=card.get("back", "") or "",
        meta_left=meta_left,
        meta_right=meta_right,
        height=360,
        theme=st.session_state.get("theme", "Light"),
    )

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

    st.markdown("</div>", unsafe_allow_html=True)


def stat_pill(icon: str, label: str, value: str) -> str:
    return f"<span class='chip'>{icon} <b>{label}</b> {value}</span>"


def app_header() -> None:
    carrots, croissants, toward = carrots_and_croissants()
    xp = carrots
    streak = int(st.session_state.get("streak", 1))
    level, _, _ = level_from_xp(xp)
    total_cards = len(fetch_cards())

    html = f"""
<div class="card" style="padding:16px 18px; margin-bottom:12px;">
  <div class="card-header">
    <div>
      <div style="display:flex; align-items:center; gap:10px;">
        <div>
          <div style="font-weight:1000; font-size:22px; letter-spacing:.2px;">Charlot</div>
          <div class="h-sub">Dictionary • Flashcards • Notes </div>
        </div>
      </div>
    </div>
    <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
      {stat_pill("🔥","Streak", str(streak))}
      {stat_pill("🥕","XP", str(carrots))}
      {stat_pill("🥐","Level", str(level))}
      {stat_pill("🗂️","Cards", str(total_cards))}
    </div>
  </div>
</div>
"""
    st.markdown(textwrap.dedent(html).lstrip(), unsafe_allow_html=True)


def top_nav() -> str:
    pages = [
        ("🏠", "Home"),
        ("📚", "Dictionary"),
        ("🧠", "Review"),
        ("🗂️", "Cards"),
        ("📝", "Notebook"),
        ("🔁", "Import/Export"),
        ("⚙️", "Settings"),
        ("❓", "About"),
    ]

    cur = st.session_state.get("nav", "Home")
    page_names = [name for _, name in pages]
    page_labels = [f"{ic} {name}" for ic, name in pages]
    name_to_label = {name: f"{ic} {name}" for ic, name in pages}
    label_to_name = {f"{ic} {name}": name for ic, name in pages}

    bp = detect_breakpoint(760)  # "m" or "d"

    if bp == "m":
        # Mobile: hamburger only (use selectbox to avoid "radio panel" styling)
        with st.expander("☰ Menu", expanded=False):
            idx = page_names.index(cur) if cur in page_names else 0
            pick = st.selectbox(
                "Menu",
                page_labels,
                index=idx,
                label_visibility="collapsed",
                key="nav_mobile_select",
            )
            st.session_state.nav = label_to_name[pick]
    else:
        # Desktop: horizontal nav bar only
        idx = page_names.index(cur) if cur in page_names else 0
        pick = st.radio(
            "Navigation",
            page_labels,
            index=idx,
            horizontal=True,
            label_visibility="collapsed",
            key="nav_desktop_radio",
        )
        st.session_state.nav = label_to_name[pick]

    return st.session_state.nav




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

    # Persist (so XP/carrots doesn't reset on rerun)
    try:
        set_user_state(
            xp=int(st.session_state.get("xp", 0) or 0),
            streak=int(st.session_state.get("streak", 1) or 1),
            last_xp_date=str(st.session_state.get("last_xp_date") or today),
        )
    except Exception:
        # Never break UI because of a persistence failure.
        pass




def count_cards_db() -> int:
    """Return total number of cards in DB (fast COUNT(*)).

    Used to ensure carrots (XP) reflect cards already created, even if the user
    created them before we implemented carrot persistence.
    """
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
    """Ensure carrots (XP) is at least the number of cards ever created.

    Rule: creating a card grants +1 🥕 carrot. Deleting a card should NOT remove
    already-earned carrots, so we only *increase* XP when needed.
    """
    try:
        total_cards = count_cards_db()
        cur_xp = int(st.session_state.get("xp", 0) or 0)

        if total_cards > cur_xp:
            st.session_state.xp = total_cards
            # Keep streak/last date sane for persistence
            today = iso_date(today_utc_date())
            if "streak" not in st.session_state:
                st.session_state.streak = 1
            if "last_xp_date" not in st.session_state:
                st.session_state.last_xp_date = today

            # Persist so it stays correct on rerun
            set_user_state(
                xp=int(st.session_state.get("xp", 0) or 0),
                streak=int(st.session_state.get("streak", 1) or 1),
                last_xp_date=str(st.session_state.get("last_xp_date") or today),
            )
    except Exception:
        # Never break UI because of a reconciliation/persistence issue.
        pass

def level_from_xp(xp: int) -> Tuple[int, int, int]:
    """Leveling based on carrots (XP).

    - XP is the total number of 🥕 carrots collected.
    - Level is the number of 🥐 croissants earned.
    - Every 10 carrots => +1 croissant (level up).
    Returns: (level, xp_in_level, xp_need)
    where xp_need is always 10.
    """
    xp = max(0, int(xp))
    level = xp // 10
    xp_in_level = xp % 10
    xp_need = 10
    return level, xp_in_level, xp_need



def carrots_and_croissants() -> Tuple[int, int, int]:
    """Return (carrots_total, croissants, carrots_toward_next_croissant)."""
    carrots = int(st.session_state.get("xp", 0) or 0)
    carrots = max(0, carrots)
    croissants = carrots // 10
    toward = carrots % 10
    return carrots, croissants, toward


def difficulty_bucket(card_row: Dict[str, Any]) -> str:
    """Bucket cards into: new, difficult, meh, easy.

    We use the *last submitted grade* (quality) for bucketing:

    - new: never graded OR last_quality missing
    - difficult: last_quality in {4, 5}
    - meh: last_quality == 3
    - easy: last_quality in {1, 2}

    (If some older data contains 0, it is treated as difficult.)
    """
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
# DB Layer
# =========================
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn



def get_user_state() -> Dict[str, Any]:
    """Load persistent user state from DB (singleton row id=1)."""
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
    """Persist user state to DB (robust against transient 'database is locked')."""
    xp_i = int(xp)
    streak_i = int(streak)
    last_s = str(last_xp_date)

    # Try a couple times in case another connection briefly holds the write lock.
    last_err: Exception | None = None
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
            # small backoff
            import time as _time
            _time.sleep(0.05)

    if last_err:
        raise last_err


def sync_session_from_db() -> None:
    """One-way sync: DB -> session_state (call once at startup).

    We avoid overwriting in-memory progress with older DB values (e.g. if a write
    was temporarily locked during the previous run).
    """
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


def init_db() -> None:
    conn = db()
    cur = conn.cursor()

    # Cards
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

    # Reviews (SM-2 metadata + last_quality for difficulty buckets)
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

    # --- lightweight migration: add last_quality to reviews (existing DBs) ---
    try:
        cur.execute("PRAGMA table_info(reviews);")
        cols = [r[1] for r in cur.fetchall()]
        if "last_quality" not in cols:
            cur.execute("ALTER TABLE reviews ADD COLUMN last_quality INTEGER;")
    except Exception:
        # If anything goes wrong here, we don't want to break app startup.
        pass

    
    # User state (persistent carrots/XP + streak)
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS user_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            xp INTEGER NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 1,
            last_xp_date TEXT NOT NULL
        );
        '''
    )
    # Ensure singleton row exists
    cur.execute("SELECT id FROM user_state WHERE id = 1;")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO user_state(id, xp, streak, last_xp_date) VALUES(1, 0, 1, ?);",
            (iso_date(today_utc_date()),),
        )

    conn.commit()
    conn.close()


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
        (norm_text(language), norm_text(front), norm_text(back), norm_text(tags), norm_text(example), norm_text(notes), now, now),
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
        (norm_text(language), norm_text(front), norm_text(back), norm_text(tags), norm_text(example), norm_text(notes), now, card_id),
    )
    conn.commit()
    conn.close()
    upsert_review_defaults(card_id)


def delete_card(card_id: int) -> None:
    conn = db()
    conn.execute("DELETE FROM cards WHERE id=?", (card_id,))
    conn.commit()
    conn.close()


def fetch_cards(filter_text: str = "", tag: str = "") -> List[Dict[str, Any]]:
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

    q += " ORDER BY c.updated_at DESC"
    cur.execute(q, params)

    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return rows


def fetch_card_by_id(card_id: int) -> Dict[str, Any] | None:
    conn = db()
    cur = conn.cursor()
    q = """
    SELECT c.id, c.language, c.front, c.back, c.tags, c.example, c.notes, c.created_at, c.updated_at,
           r.due_date, r.interval_days, r.repetitions, r.ease, r.last_quality, r.last_reviewed_at
    FROM cards c
    LEFT JOIN reviews r ON r.card_id = c.id
    WHERE c.id = ?
    LIMIT 1
    """
    cur.execute(q, (card_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    cols = [d[0] for d in cur.description]
    conn.close()
    return dict(zip(cols, row))


def fetch_cards_created_on(d: date) -> List[Dict[str, Any]]:
    """Cards whose created_at date equals the selected date (created_at stored as ISO string)."""
    conn = db()
    cur = conn.cursor()
    q = """
    SELECT c.id, c.language, c.front, c.back, c.tags, c.example, c.notes, c.created_at, c.updated_at,
           r.due_date, r.interval_days, r.repetitions, r.ease, r.last_quality, r.last_reviewed_at
    FROM cards c
    LEFT JOIN reviews r ON r.card_id = c.id
    WHERE substr(c.created_at, 1, 10) = ?
    ORDER BY c.created_at DESC
    """
    cur.execute(q, (d.isoformat(),))
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
               r.due_date, r.interval_days, r.repetitions, r.ease
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


def update_review_state(card_id: int, due_date: date, interval_days: int, repetitions: int, ease: float, last_quality: int = None) -> None:
    conn = db()
    conn.execute(
        """
        UPDATE reviews
        SET due_date=?, interval_days=?, repetitions=?, ease=?, last_quality=?, last_reviewed_at=?
        WHERE card_id=?
        """,
        (iso_date(due_date), int(interval_days), int(repetitions), float(ease), (None if last_quality is None else int(last_quality)), datetime.utcnow().isoformat(timespec="seconds"), card_id),
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
                {
                    "definition": d.get("definition") or "",
                    "example": d.get("example") or "",
                    "synonyms": d.get("synonyms") or [],
                }
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
# Flashcard HTML (iframe-safe)
# =========================
def render_flashcard_html(
    front: str,
    back: str,
    meta_left: str = "",
    meta_right: str = "",
    height: int = 380,
    theme: str = "Light",
) -> None:
    t = THEMES.get(theme, THEMES["Light"])

    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    cid = f"fc_{abs(hash((front, back, meta_left, meta_right, theme))) % 10_000_000}"
    front_html = esc(front)
    back_html = esc(back).replace("\n", "<br/>")
    meta_left = esc(meta_left)
    meta_right = esc(meta_right)

    # Keep borders/text correct in BOTH modes
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

  .wrap {{ display:flex; justify-content:center; animation: enter .20s ease-out; }}
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


# =========================
# Pages
# =========================
def build_due_calendar_html(days: int = 14) -> str:
    start = today_utc_date()
    counts = []
    maxc = 1
    for i in range(days):
        d = start + timedelta(days=i)
        c = len(fetch_due_cards(d))
        counts.append((d, c))
        maxc = max(maxc, c)

    t = THEMES.get(st.session_state.get("theme", "Light"), THEMES["Light"])

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


def progress_ring_html(pct: int, label: str, sub: str) -> str:
    pct = max(0, min(100, int(pct)))
    # Conic-gradient ring
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


def home_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Home")

    cards_total = len(fetch_cards())
    due_today = len(fetch_due_cards(today_utc_date()))
    level, xp_in, xp_need = level_from_xp(int(st.session_state.get("xp", 0)))
    pct = 0 if xp_need <= 0 else int(100 * (xp_in / xp_need))

    left, right = st.columns([1.35, 1.0], gap="large")

    with left:
        st.markdown(
            f"""
<div class="card-header">
  <div>
    <div class="h-title">Today’s plan</div>
    <div class="h-sub">Quick actions to keep momentum.</div>
  </div>
  <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
    <span class="chip">🗂️ <b>Total</b> {cards_total}</span>
    <span class="chip">📌 <b>Due</b> {due_today}</span>
  </div>
</div>
<hr/>
{progress_ring_html(pct, f"🥐 Level {level}", f"{xp_in}/{xp_need} 🥕 to next 🥐")}
""",
            unsafe_allow_html=True,
        )

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

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
<div class="card-header">
  <div>
    <div class="h-title">Review calendar</div>
    <div class="h-sub">How many cards will be due each day (next 14 days).</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        components.html(build_due_calendar_html(14), height=220, scrolling=False)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.metric("🔥 Streak", int(st.session_state.get("streak", 1)))
        carrots, croissants, _ = carrots_and_croissants()
        st.metric("🥕 XP", carrots)
        st.metric("🥐 Level", croissants)
        st.metric("📌 Due today", due_today)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def dictionary_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Dictionary")

    # st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        """
<div class="card-header">
  <div>
    <div class="h-title">Lookup a word</div>
    <div class="h-sub">Fast definitions + save as flashcards.</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.form("dict_search_form", clear_on_submit=False):
        colA, colB, colC = st.columns([2.2, 1.0, 1.0])
        with colA:
            word = st.text_input("Word / expression", placeholder="ex: faire, pourtant, un peu…")
        with colB:
            lang = st.selectbox("Language code", ["fr", "en"], index=0, help="Lookup language.")
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

    st.markdown("</div>", unsafe_allow_html=True)

    if not (do and word.strip()):
        st.markdown("</div>", unsafe_allow_html=True)
        return

    source, data = best_dictionary_result(lang, word)

    # st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    if source == "dictapi":
        parsed = data["parsed"]
        st.success("Source: dictionaryapi.dev (structured)")

        if parsed["phonetics"]:
            st.markdown("### 🔊 Phonetics / audio")
            for p in parsed["phonetics"][:5]:
                cols = st.columns([1, 2])
                with cols[0]:
                    if p["text"]:
                        st.write(f"`{p['text']}`")
                with cols[1]:
                    if p["audio"]:
                        st.audio(p["audio"])

        st.markdown("### 📌 Meanings")
        for m in parsed["meanings"]:
            st.markdown(f"**{m['partOfSpeech'] or '—'}**")
            defs = m["definitions"] or []
            for i, d in enumerate(defs[:8], start=1):
                st.markdown(f"**{i}.** {d['definition']}")
                if d["example"]:
                    st.markdown(f"> _{d['example']}_")

        default_back = ""
        if parsed["meanings"] and parsed["meanings"][0]["definitions"]:
            default_back = parsed["meanings"][0]["definitions"][0]["definition"]

        st.markdown("---")
        st.markdown("### ➕ Save as flashcard")
        with st.form("add_from_dictapi", clear_on_submit=False):
            front = st.text_input("Front", value=word.strip())
            back = st.text_area("Back", value=default_back, height=110)
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
                    st.success(f"Saved card #{cid} and scheduled for review. (+1 🥕)")

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
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

        st.markdown("---")
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
                    st.success(f"Saved card #{cid} and scheduled for review. (+1 🥕)")

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.error("No result from any dictionary backend.")
    st.code(safe_json(data), language="json")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def review_page() -> None:
    st.markdown("## Review")

    # --- Difficulty buckets (based on last grade) ---
    allc = fetch_cards()
    buckets: Dict[str, List[Dict[str, Any]]] = {"new": [], "difficult": [], "meh": [], "easy": []}
    for row in allc:
        b = difficulty_bucket(row)
        buckets.setdefault(b, []).append(row)

    badge_row([
        ("🆕", f"New {len(buckets['new'])}"),
        ("😵", f"Difficult {len(buckets['difficult'])}"),
        ("😐", f"Meh {len(buckets['meh'])}"),
        ("😌", f"Easy {len(buckets['easy'])}"),
    ])

    t_new, t_diff, t_meh, t_easy = st.tabs(["🆕 New", "😵 Difficult", "😐 Meh", "😌 Easy"])

    def _list_bucket(rows: List[Dict[str, Any]], key_prefix: str) -> None:
        if not rows:
            st.info("No cards in this bucket.")
            return
        for r in rows[:250]:
            due = r.get("due_date") or "—"
            label = (r.get("front", "") or "").strip()
            if not label:
                label = f"Card #{r.get('id')}"
            if st.button(label, key=f"{key_prefix}_open_{r.get('id')}"):
                select_card(int(r.get("id")))
                st.rerun()
            st.caption(f"#{r.get('id')} • due: {due} • tags: {r.get('tags','')}")
            st.divider()

    with t_new:
        _list_bucket(buckets["new"], "rev_new")
    with t_diff:
        _list_bucket(buckets["difficult"], "rev_diff")
    with t_meh:
        _list_bucket(buckets["meh"], "rev_meh")
    with t_easy:
        _list_bucket(buckets["easy"], "rev_easy")

    st.markdown("</div>", unsafe_allow_html=True)

    render_selected_card_viewer(title="Selected card")
    colA, colB, colC = st.columns([1.6, 1.0, 1.0])
    with colA:
        created_on = st.date_input("Show cards created on", value=today_utc_date())
    with colB:
        st.write("")
        if st.button("Restart queue", use_container_width=True):
            st.session_state.review_idx = 0
            st.rerun()
    with colC:
        st.write("")
        if st.button("Go to Cards", use_container_width=True):
            st.session_state.nav = "Cards"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


    # --- Browse cards by creation date ---
    created_cards = fetch_cards_created_on(created_on)
    with st.expander(f"📅 Cards created on {created_on.isoformat()} ({len(created_cards)})", expanded=False):
        if not created_cards:
            st.info("No cards were created on this date.")
        else:
            for r in created_cards[:250]:
                label = (r.get("front", "") or "").strip() or f"Card #{r.get('id')}"
                if st.button(label, key=f"created_open_{r.get('id')}", use_container_width=True):
                    select_card(int(r.get("id")))
                    st.rerun()
                st.caption(f"#{r.get('id')} • tags: {r.get('tags','')} • created: {r.get('created_at','—')[:19]}")
                st.divider()


    # SM-2 queue is always based on today
    due = fetch_due_cards(today_utc_date())
    if not due:
        st.success("No cards due. 🎉")
        st.caption("Add more words in Dictionary or Cards.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    idx = int(st.session_state.review_idx)
    idx = max(0, min(idx, len(due) - 1))
    card = due[idx]

    # Stats row
    badge_row([
        ("📌", f"Queue {len(due)}"),
        ("🧾", f"Card {idx+1}/{len(due)}"),
        ("⏱️", f"Interval {card['interval_days']}d"),
        ("⚖️", f"Ease {float(card['ease']):.2f}"),
    ])
    st.markdown("</div>", unsafe_allow_html=True)

    meta_left = f"#{card['id']} • {card.get('language','fr')}"
    meta_right = f"due {card.get('due_date','')}"
    render_flashcard_html(
        front=card["front"],
        back=card["back"],
        meta_left=meta_left,
        meta_right=meta_right,
        height=390,
        theme=st.session_state.get("theme", "Light"),
    )

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
        st.markdown("</div>", unsafe_allow_html=True)

    # st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown("### 🎯 Grade your recall")
    st.caption("Pick how hard it felt: 5 = very difficult • 1 = very easy")
    q_user = st.radio("Difficulty", [1, 2, 3, 4, 5], index=2, horizontal=True)
    q_sm2 = 6 - int(q_user)  # convert user-facing difficulty (5 hard → 1 easy) into SM-2 quality (1 bad → 5 good)

    b1, b2, b3 = st.columns([1.2, 1.2, 1.0])
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
            st.rerun()
    with b2:
        if st.button("Skip (no grade)", use_container_width=True):
            st.session_state.review_idx = idx + 1
            if st.session_state.review_idx >= len(due):
                st.session_state.review_idx = 0
            st.rerun()
    with b3:
        if st.button("Back", use_container_width=True):
            st.session_state.review_idx = max(0, idx - 1)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def manage_cards_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Cards")

    # st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2.0, 1.0, 1.0])
    with col1:
        q = st.text_input("Search", placeholder="search front/back/example/notes…")
    with col2:
        tags = [""] + all_tags()
        tag = st.selectbox("Filter by tag", tags, index=0)
    with col3:
        st.write("")
        if st.button("New card", type="primary", use_container_width=True):
            st.session_state.edit_card_id = None
    st.markdown("</div>", unsafe_allow_html=True)

    cards = fetch_cards(q, tag)
    st.caption(f"Cards: {len(cards)}")

    # st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    for c in cards[:200]:
        st.markdown('<div class="card card-tight" style="margin-bottom:10px;">', unsafe_allow_html=True)
        left, mid, right = st.columns([2.2, 1.6, 1.0])
        with left:
            label = (c.get("front","") or "").strip() or f"Card #{c['id']}"
            if st.button(label, key=f"cards_open_{c['id']}", use_container_width=True):
                select_card(int(c["id"]))
                st.rerun()
            st.caption(f"#{c['id']} • lang: {c.get('language','')} • due: {c.get('due_date','—')}")
            if c.get("tags"):
                st.markdown(f"<span class='chip'>🏷️ <b>{c['tags']}</b></span>", unsafe_allow_html=True)
        with mid:
            st.markdown("**Back**")
            b = c.get("back") or ""
            st.write(b[:240] + ("…" if len(b) > 240 else ""))
        with right:
            if st.button("Edit", key=f"edit_{c['id']}", use_container_width=True):
                st.session_state.edit_card_id = c["id"]
                st.rerun()
            if st.button("Delete", key=f"del_{c['id']}", use_container_width=True):
                delete_card(c["id"])
                st.success("Deleted.")
                st.rerun()

    # Full card viewer (opens when you click a card in any list above)
    render_selected_card_viewer(title="Selected card")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### ✍️ Editor")
    # st.markdown('<div class="card">', unsafe_allow_html=True)

    edit_id = st.session_state.get("edit_card_id", None)
    if edit_id is None:
        st.info("Create a new card below.")
        editor_card = {"id": None, "language": "fr", "front": "", "back": "", "tags": "", "example": "", "notes": ""}
    else:
        rows = [x for x in fetch_cards() if x["id"] == edit_id]
        if not rows:
            st.warning("Card not found.")
            st.session_state.edit_card_id = None
            st.rerun()
        editor_card = rows[0]

    with st.form("card_editor", clear_on_submit=False):
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
                    st.success(f"Created card #{cid}. (+1 🥕)")
                else:
                    update_card(editor_card["id"], language, front, back, tags, example, notes)
                    bump_xp(1)
                    st.success("Updated. (+1 🥕)")
                st.session_state.edit_card_id = None
                st.rerun()


    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def notebook_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Notebook")
    st.caption("A clean view over saved examples + notes.")

    # st.markdown('<div class="card">', unsafe_allow_html=True)
    q = st.text_input("Search notebook", placeholder="type anything…")
    only_with_notes = st.checkbox("Only show items that have example/notes", value=True)
    st.markdown("</div>", unsafe_allow_html=True)

    cards = fetch_cards(q)
    shown = 0

    # st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    for c in cards[:500]:
        has_any = bool((c.get("example") or "").strip() or (c.get("notes") or "").strip())
        if only_with_notes and not has_any:
            continue
        shown += 1

        st.markdown('<div class="card card-tight" style="margin-bottom:10px;">', unsafe_allow_html=True)
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
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if shown == 0:
        st.info("No notebook entries matched your filters.")

    st.markdown("</div>", unsafe_allow_html=True)


def import_export_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Import / Export (CSV)")
    st.caption("CSV columns: language, front, back, tags, example, notes")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        # st.markdown('<div class="card">', unsafe_allow_html=True)
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
                file_name="french_study_hub_cards.csv",
                mime="text/csv",
                use_container_width=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        # st.markdown('<div class="card">', unsafe_allow_html=True)
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
                    bump_xp(min(80, created * 2))
                    st.success(f"Imported {created} cards. (+XP)")
                    st.rerun()
            except Exception as e:
                st.error(f"Import failed: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def settings_page() -> None:
    st.markdown('<div class="page">', unsafe_allow_html=True)
    st.markdown("## Settings")

    # st.markdown('<div class="card">', unsafe_allow_html=True)
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
            st.success("Initialized.")
    with c2:
        if st.button("Clear Streamlit cache", use_container_width=True):
            st.cache_data.clear()
            st.success("Cache cleared.")
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
            st.success("Reset.")
            st.rerun()
    with c5:
        lvl, _, _ = level_from_xp(int(st.session_state.get("xp", 0)))
        st.markdown(
            f"<span class='chip'>🏅 <b>Level</b> {lvl}</span> <span class='chip'>🥕 <b>Carrots</b> {int(st.session_state.get('xp',0) or 0)}</span> <span class='chip'>🥐 <b>Croissants</b> {int(st.session_state.get('xp',0) or 0)//10}</span>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# Main
# =========================
def main() -> None:
    init_db()
    init_session_state()
    sync_session_from_db()

    # Carrots (XP) should reflect cards already created.
    reconcile_carrots_with_cards()

    inject_global_css(st.session_state.get("theme", "Light"))

    app_header()
    nav = top_nav()

    if nav == "Home":
        home_page()
    elif nav == "Dictionary":
        dictionary_page()
    elif nav == "Review":
        review_page()
    elif nav == "Cards":
        manage_cards_page()
    elif nav == "Notebook":
        notebook_page()
    elif nav == "Import/Export":
        import_export_page()
    elif nav == "Settings":
        settings_page()
    else:
        home_page()


if __name__ == "__main__":
    main()

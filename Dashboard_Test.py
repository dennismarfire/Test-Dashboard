import streamlit as st
from streamlit.connections import SQLConnection
import pandas as pd
import altair as alt
from datetime import date
from sqlalchemy import text  # WICHTIG: fuer die korrekte Ausfuehrung von SQL

# ==========================================================
# 1. SEITEN-KONFIGURATION  (MUSS der erste Streamlit-Befehl sein!)
# ==========================================================
st.set_page_config(page_title="Kostenanalyse", page_icon="💰", layout="wide")

# ---- Farben & Kategorien -------------------------------------------------
INK     = "#0c241c"
ACCENT  = "#0b6b4f"
ACCENT2 = "#0a4f8c"
EINNAHME_KAT = {"Gehalt","Rückzahlung"}   # Diese Kategorien werden addiert, nicht subtrahiert
FIXKOSTEN_KAT = {"Investment", "Fixkosten", "Miete"}  # zaehlen als Fixkosten (nicht variable Ausgabe)
KATEGORIEN = ["", "Feiern", "Einkauf", "Produktivität", "Fixkosten", "Investment", "Miete", "Mittagessen","Freizeit","Gehalt", "Rückzahlung"]
# Stark unterscheidbare Palette (warm/kalt abwechselnd, damit Nachbarsegmente klar trennen)
TORTE_FARBEN = [
    "#e6194B",  # rot
    "#4363d8",  # blau
    "#3cb44b",  # gruen
    "#f58231",  # orange
    "#911eb4",  # violett
    "#42d4f4",  # cyan
    "#f032e6",  # magenta
    "#bfef45",  # limette
    "#469990",  # petrol
    "#9A6324",  # braun
]

# ---- Spalten-Mapping: Datenbank <-> App/Anzeige --------------------------
# DB-Spalte (englisch/klein)  ->  Anzeige-Spalte (deutsch, wie im alten Code)
SPALTEN_DB_ZU_APP = {
    "datum":        "Datum",
    "beschreibung": "Produkt",
    "betrag":       "Preis",
    "kategorie":    "Kategorie",
}
# Umkehrung: Anzeige-Spalte  ->  DB-Spalte
SPALTEN_APP_ZU_DB = {v: k for k, v in SPALTEN_DB_ZU_APP.items()}

# ==========================================================
# 2. DATENBANK-VERBINDUNG & HILFSFUNKTIONEN
# ==========================================================
# Liest die Zugangsdaten aus .streamlit/secrets.toml -> [connections.postgresql]
conn = st.connection("postgresql", type=SQLConnection)


@st.cache_resource
def init_datenbank():
    """Legt die Tabellen 'transaktionen' und 'einstellungen' an (laeuft dank Cache nur 1x pro Sitzung)."""
    with conn.session as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS transaktionen (
                id           SERIAL PRIMARY KEY,
                datum        DATE NOT NULL,
                betrag       NUMERIC(10, 2) NOT NULL,
                kategorie    TEXT NOT NULL,
                beschreibung TEXT,
                zeitstempel  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS einstellungen (
                schluessel TEXT PRIMARY KEY,
                wert       TEXT NOT NULL
            );
        """))
        session.commit()
    return True


# Verbindung testen / Tabelle anlegen – mit verstaendlicher Fehlermeldung
try:
    init_datenbank()
except Exception as e:
    st.error(
        "❌ Verbindung zur Datenbank fehlgeschlagen.\n\n"
        "Bitte pruefe `.streamlit/secrets.toml`:\n"
        "- Abschnitt **[connections.postgresql]** vorhanden?\n"
        "- **url = \"...\"** korrekt (Passwort URL-kodiert)?\n"
        "- Internet-/Supabase-Verbindung aktiv?"
    )
    st.exception(e)
    st.stop()


def lade_transaktionen() -> pd.DataFrame:
    """Liest alle Transaktionen aus der DB und benennt die Spalten auf Anzeigenamen um."""
    df = conn.query(
        "SELECT id, datum, beschreibung, betrag, kategorie "
        "FROM transaktionen ORDER BY datum DESC, id DESC;",
        ttl=600,  # 10 Min. Cache – wird nach jedem Schreibvorgang geleert
    )
    df = df.rename(columns=SPALTEN_DB_ZU_APP)
    if not df.empty:
        df["id"]    = df["id"].astype(int)
        df["Preis"] = df["Preis"].astype(float)      # NUMERIC -> float
        df["Datum"] = pd.to_datetime(df["Datum"])
    return df


def fuege_transaktion_hinzu(datum, betrag, kategorie, beschreibung):
    """Eine neue Zeile in die DB schreiben (INSERT)."""
    with conn.session as session:
        session.execute(
            text("""
                INSERT INTO transaktionen (datum, betrag, kategorie, beschreibung)
                VALUES (:datum, :betrag, :kategorie, :beschreibung);
            """),
            {"datum": datum, "betrag": float(betrag),
             "kategorie": kategorie, "beschreibung": beschreibung},
        )
        session.commit()


def aktualisiere_felder(trans_id, db_felder: dict):
    """UPDATE – nur die tatsaechlich geaenderten Spalten einer Zeile schreiben.
       (Spaltennamen stammen aus unserem festen Mapping, daher kein Injection-Risiko.)"""
    if not db_felder:
        return
    set_klausel = ", ".join(f"{spalte} = :{spalte}" for spalte in db_felder)
    params = dict(db_felder)
    params["id"] = int(trans_id)
    with conn.session as session:
        session.execute(text(f"UPDATE transaktionen SET {set_klausel} WHERE id = :id;"), params)
        session.commit()


def loesche_transaktion(trans_id):
    """DELETE – eine Zeile anhand ihrer id loeschen."""
    with conn.session as session:
        session.execute(text("DELETE FROM transaktionen WHERE id = :id;"),
                        {"id": int(trans_id)})
        session.commit()


def lade_einstellung(schluessel: str, standard: float) -> float:
    """Liest einen persistenten Einstellungswert aus der DB (kein Cache)."""
    df = conn.query(
        "SELECT wert FROM einstellungen WHERE schluessel = :key;",
        params={"key": schluessel},
        ttl=0,
    )
    if df.empty:
        return standard
    return float(df.iloc[0]["wert"])


def lade_einstellung_text(schluessel: str, standard: str = "") -> str:
    """Liest einen Text-Einstellungswert aus der DB (kein Cache)."""
    df = conn.query(
        "SELECT wert FROM einstellungen WHERE schluessel = :key;",
        params={"key": schluessel},
        ttl=0,
    )
    if df.empty:
        return standard
    return str(df.iloc[0]["wert"])


def speichere_einstellung(schluessel: str, wert: float):
    """Schreibt oder aktualisiert einen Einstellungswert in der DB."""
    with conn.session as session:
        session.execute(text("""
            INSERT INTO einstellungen (schluessel, wert)
            VALUES (:key, :val)
            ON CONFLICT (schluessel) DO UPDATE SET wert = :val;
        """), {"key": schluessel, "val": str(wert)})
        session.commit()


def _konvertiere(db_spalte, wert):
    """Bringt einen Wert aus dem Daten-Editor in das passende DB-Format."""
    if wert is None or wert == "":
        return None
    if db_spalte == "datum":
        return pd.to_datetime(wert).date()
    if db_spalte == "betrag":
        return float(wert)
    return wert  # kategorie / beschreibung bleiben Text


def verarbeite_editor_aenderungen(delta: dict, df_anzeige: pd.DataFrame) -> int:
    """Wendet Bearbeiten/Loeschen/Hinzufuegen aus dem Daten-Editor auf die DB an.
       'delta' ist st.session_state[editor_key] und enthaelt:
         edited_rows  = {zeilen_position: {spalte: neuer_wert}}
         deleted_rows = [zeilen_position, ...]
         added_rows   = [{spalte: wert}, ...]
       Die Zeilen-Position wird ueber df_anzeige.iloc[pos] in die echte id uebersetzt.
       Rueckgabe: Anzahl der vorgenommenen Aenderungen."""
    anzahl = 0

    # 1) Bearbeitete Zeilen  ->  UPDATE
    for pos, aenderungen in delta.get("edited_rows", {}).items():
        trans_id = df_anzeige.iloc[int(pos)]["id"]
        db_felder = {
            SPALTEN_APP_ZU_DB[spalte]: _konvertiere(SPALTEN_APP_ZU_DB[spalte], wert)
            for spalte, wert in aenderungen.items()
            if spalte in SPALTEN_APP_ZU_DB
        }
        if db_felder:
            aktualisiere_felder(trans_id, db_felder)
            anzahl += 1

    # 2) Geloeschte Zeilen  ->  DELETE
    for pos in delta.get("deleted_rows", []):
        loesche_transaktion(df_anzeige.iloc[int(pos)]["id"])
        anzahl += 1

    # 3) Neu hinzugefuegte Zeilen  ->  INSERT
    for neue_zeile in delta.get("added_rows", []):
        produkt = (neue_zeile.get("Produkt") or "").strip()
        if not produkt:                      # Zeilen ohne Bezeichnung ueberspringen
            continue
        datum     = _konvertiere("datum", neue_zeile.get("Datum")) or date.today()
        betrag    = _konvertiere("betrag", neue_zeile.get("Preis")) or 0.0
        kategorie = neue_zeile.get("Kategorie") or "Keine"
        fuege_transaktion_hinzu(datum, betrag, kategorie, produkt)
        anzahl += 1

    return anzahl


def nach_aenderung():
    """Nach jedem Schreibvorgang: Cache leeren, Editor zuruecksetzen, App neu laden."""
    st.cache_data.clear()              # erzwingt frische Daten beim naechsten lade_transaktionen()
    st.session_state.editor_v += 1     # neuer Editor-Key -> verwirft alte Editor-Eingaben
    st.rerun()


def setze_flash(nachricht, typ="success"):
    """Nachricht zwischenspeichern, damit sie ein st.rerun() 'ueberlebt'."""
    st.session_state["flash"] = (typ, nachricht)


# ==========================================================
# 3. STYLING (CSS) – unveraendert uebernommen
# ==========================================================
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=Space+Grotesk:wght@300;400;500;600&display=swap');

:root{{
  --ink:{INK};
  --accent:{ACCENT};
  --accent2:{ACCENT2};
  --glass:rgba(255,255,255,0.42);
  --glass-strong:rgba(255,255,255,0.78);
  --glass-border:rgba(255,255,255,0.85);
}}

[data-testid="stAppViewContainer"] * {{ font-family:'Space Grotesk', sans-serif; }}

[data-testid="stAppViewContainer"]{{
  background:linear-gradient(160deg, #e8fbef 0%, #b9f0cf 45%, #6fce9b 100%);
  background-attachment:fixed; color:var(--ink);
}}
[data-testid="stHeader"]{{ background:transparent; }}
.block-container{{ padding-top:2.5rem; max-width:1200px; }}

/* 1) SIDEBAR-TOGGLE: "keyboard_double"-Text ausblenden, Pfeil einsetzen */
[data-testid="stSidebarCollapseButton"]{{
  overflow:hidden !important;
  background:var(--glass-strong) !important;
  border:1px solid var(--glass-border) !important;
  border-radius:10px !important;
}}
[data-testid="stSidebarCollapseButton"] span,
[data-testid="stSidebarCollapseButton"] p {{ font-size:0 !important; color:transparent !important; }}
[data-testid="stSidebarCollapseButton"] svg {{ display:none !important; }}
[data-testid="stSidebarCollapseButton"]::after{{
  content:"◀"; font-size:1rem; color:var(--ink);
  display:flex; align-items:center; justify-content:center;
  width:100%; height:100%;
}}

/* Seitenleiste */
[data-testid="stSidebar"]{{
  background:var(--glass);
  backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px);
  border-right:1px solid var(--glass-border);
}}
[data-testid="stSidebar"] *{{ color:var(--ink) !important; }}

/* Überschriften */
h1{{
  font-family:'Orbitron',sans-serif !important; font-weight:800; letter-spacing:2px;
  background:linear-gradient(90deg,var(--accent),var(--accent2));
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}}
h2,h3{{ font-family:'Orbitron',sans-serif !important; letter-spacing:1px; color:var(--ink); }}
p, label, .stMarkdown, [data-testid="stWidgetLabel"]{{ color:var(--ink) !important; }}

/* 2) STEPPER-BUTTONS ausblenden */
button[data-testid="stNumberInputStepDown"],
button[data-testid="stNumberInputStepUp"]{{ display:none !important; }}
[data-baseweb="spin-button"]{{ display:none !important; }}

/* Eingabefelder */
[data-baseweb="base-input"],
[data-baseweb="input"],
[data-baseweb="select"] > div{{
  background:var(--glass-strong) !important;
  -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px);
  border:1px solid var(--glass-border) !important;
  border-radius:14px !important;
  box-shadow:0 4px 18px rgba(11,107,79,0.12), inset 0 1px 0 rgba(255,255,255,0.8);
}}
.stTextInput input, .stNumberInput input, .stDateInput input,
[data-baseweb="base-input"] input,
[data-baseweb="select"] div{{
  background:transparent !important;
  color:var(--ink) !important;
  -webkit-text-fill-color:var(--ink) !important;
}}
.stTextInput input::placeholder{{ color:#4a6b5e !important; }}

/* Dropdown + Kalender */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="popover"] > div > div,
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="menu"],
[data-baseweb="select-dropdown"],
[data-baseweb="calendar"],
[data-baseweb="datepicker"],
ul[role="listbox"]{{
  background:var(--glass-strong) !important;
  -webkit-backdrop-filter:blur(18px); backdrop-filter:blur(18px);
  border-radius:14px !important;
}}
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="calendar"],
[data-baseweb="select-dropdown"]{{
  border:1px solid var(--glass-border) !important;
  box-shadow:0 12px 34px rgba(12,36,28,0.18) !important;
}}
[data-baseweb="popover"] *,
[data-baseweb="menu"] *,
[data-baseweb="select-dropdown"] *,
ul[role="listbox"] *{{
  color:var(--ink) !important;
  -webkit-text-fill-color:var(--ink) !important;
  background-color:transparent !important;
}}
ul[role="listbox"] li,
li[role="option"],
[data-baseweb="menu"] li{{ background:transparent !important; color:var(--ink) !important; }}
ul[role="listbox"] li:hover,
li[role="option"]:hover,
[data-baseweb="menu"] li:hover{{ background:rgba(11,107,79,0.16) !important; }}

/* Kalender (hochspezifisch) */
[data-baseweb="calendar"] div,[data-baseweb="calendar"] span,
[data-baseweb="calendar"] table,[data-baseweb="calendar"] thead,
[data-baseweb="calendar"] tbody,[data-baseweb="calendar"] tr,
[data-baseweb="calendar"] td,[data-baseweb="calendar"] th,
[data-baseweb="calendar"] [role="grid"],[data-baseweb="calendar"] [role="row"],
[data-baseweb="calendar"] [role="gridcell"],
[data-baseweb="datepicker"] div,[data-baseweb="datepicker"] table,
[data-baseweb="datepicker"] td,[data-baseweb="datepicker"] th{{
  background:transparent !important; background-color:transparent !important;
  color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important;
}}
[data-baseweb="calendar"] ul,[data-baseweb="datepicker"] ul,
[data-baseweb="calendar"] ol{{ list-style:none !important; padding-left:0 !important; margin:0 !important; }}
[data-baseweb="calendar"] button,[data-baseweb="datepicker"] button{{
  background:transparent !important; background-color:transparent !important;
  color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important; border:none !important;
}}
[data-baseweb="calendar"] [aria-current="date"],
[data-baseweb="calendar"] button[aria-current="date"]{{
  background:transparent !important; outline:2px solid var(--accent) !important;
  border-radius:50% !important;
}}
[data-baseweb="calendar"] [role="gridcell"] [aria-selected="true"],
[data-baseweb="calendar"] [role="row"] [aria-selected="true"],
[data-baseweb="calendar"] button[aria-selected="true"],
[data-baseweb="calendar"] [aria-selected="true"]{{
  background:var(--accent) !important; background-color:var(--accent) !important;
  color:#fff !important; -webkit-text-fill-color:#fff !important;
  border-radius:50% !important; border:none !important; outline:none !important;
}}
[data-baseweb="calendar"] [aria-selected="true"] span,
[data-baseweb="calendar"] [aria-selected="true"] div,
[data-baseweb="calendar"] button[aria-selected="true"] span,
[data-baseweb="calendar"] button[aria-selected="true"] div{{
  color:#fff !important; -webkit-text-fill-color:#fff !important; background:transparent !important;
}}
[data-baseweb="calendar"] button:not([aria-selected="true"]):not([aria-current="date"]):hover{{
  background:rgba(11,107,79,0.16) !important; border-radius:50% !important;
}}
[data-baseweb="select"] svg,[data-baseweb="base-input"] svg,
[data-baseweb="calendar"] svg,[data-baseweb="datepicker"] svg{{
  fill:var(--ink) !important; color:var(--ink) !important;
}}

/* Buttons */
div.stButton > button, div.stFormSubmitButton > button{{
  width:100%;
  background:linear-gradient(135deg, rgba(11,107,79,0.85), rgba(10,79,140,0.85));
  -webkit-backdrop-filter:blur(10px); backdrop-filter:blur(10px);
  border:1px solid var(--glass-border); color:#fff; border-radius:16px;
  font-weight:600; padding:0.6rem 1rem; letter-spacing:1px; transition:all .2s ease;
  box-shadow:0 6px 20px rgba(11,107,79,0.25), inset 0 1px 0 rgba(255,255,255,0.5);
}}
div.stButton > button:hover, div.stFormSubmitButton > button:hover{{
  transform:translateY(-1px); box-shadow:0 10px 26px rgba(11,107,79,0.35);
}}

/* Formular */
[data-testid="stForm"]{{
  background:var(--glass);
  -webkit-backdrop-filter:blur(20px); backdrop-filter:blur(20px);
  border:1px solid var(--glass-border); border-radius:24px;
  padding:8px 24px 6px;
  box-shadow:0 12px 40px rgba(12,36,28,0.12), inset 0 1px 0 rgba(255,255,255,0.6);
}}

/* Metrik-Karten */
[data-testid="stMetric"]{{
  background:var(--glass-strong);
  -webkit-backdrop-filter:blur(16px); backdrop-filter:blur(16px);
  border:1px solid var(--glass-border); border-radius:20px; padding:18px 20px;
  box-shadow:0 8px 28px rgba(12,36,28,0.12), inset 0 1px 0 rgba(255,255,255,0.6);
}}
[data-testid="stMetricValue"]{{ font-family:'Orbitron',sans-serif; color:var(--accent); }}
[data-testid="stMetricLabel"]{{ color:#22483b; }}

/* 3) Data-Editor Glas-Styling */
[data-testid="stDataEditor"]{{
  background:var(--glass) !important;
  -webkit-backdrop-filter:blur(16px); backdrop-filter:blur(16px);
  border:1px solid var(--glass-border) !important;
  border-radius:18px !important;
  box-shadow:0 8px 28px rgba(12,36,28,0.12) !important;
  overflow:hidden;
}}

/* Diagramm-Rahmen */
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"]{{
  background:var(--glass);
  -webkit-backdrop-filter:blur(14px); backdrop-filter:blur(14px);
  border:1px solid var(--glass-border); border-radius:18px; padding:10px;
  box-shadow:0 8px 28px rgba(12,36,28,0.10), inset 0 1px 0 rgba(255,255,255,0.5);
  overflow:hidden !important;
}}

/* Slider */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"]{{
  background:var(--glass-strong) !important;
  border:1px solid var(--accent) !important;
  box-shadow:0 2px 10px rgba(11,107,79,0.35);
}}
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stSliderTrack"] > div{{
  background:var(--accent) !important;
}}

hr{{ border:none; height:2px;
  background:linear-gradient(90deg,transparent,rgba(11,107,79,0.5),transparent); }}

[data-testid="stAlert"]{{
  background:var(--glass-strong) !important;
  -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px);
  border-radius:16px; color:var(--ink) !important;
}}
[data-testid="stAlert"] *{{ color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important; }}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# 4. CHART-FUNKTIONEN (ALTAIR) – unveraendert uebernommen
# ==========================================================
def _ax(grid=False, fmt=None, angle=0, tick_count=None):
    kw = dict(labelColor=INK, titleColor=INK, labelFontSize=12, titleFontSize=13,
              domainColor=INK, tickColor=INK, labelAngle=angle)
    if grid:
        kw["gridColor"] = "rgba(12,36,28,0.12)"
    if fmt:
        kw["format"] = fmt
    if tick_count:
        kw["tickCount"] = tick_count
    return alt.Axis(**kw)


def _torte_farben(n):
    """Gibt n stark unterscheidbare Farben aus TORTE_FARBEN (zyklisch) zurück."""
    return (TORTE_FARBEN * ((n // len(TORTE_FARBEN)) + 1))[:n]


def torte(data, kat_feld, wert_feld, selection=None):
    """Donut-Diagramm: glässig (durchscheinend), ohne Legende,
       Beschriftung mit Pfeil aussen an den Segmenten."""
    kategorien = list(data[kat_feld].astype(str).values)
    n = max(len(kategorien), 1)
    farben = _torte_farben(n)

    # Glassig = durchscheinend, aber Segmente durch weisse Trennlinien klar erkennbar
    opacity_enc = (
        alt.condition(selection, alt.value(0.62), alt.value(0.16))
        if selection else alt.value(0.62)
    )

    base = (
        alt.Chart(data)
        .transform_calculate(_lbl=f'"→ " + datum["{kat_feld}"]')
        .encode(theta=alt.Theta(f"{wert_feld}:Q", stack=True))
    )

    arc = base.mark_arc(
        innerRadius=48, outerRadius=100,
        stroke="rgba(255,255,255,0.92)", strokeWidth=2.5,
    ).encode(
        color=alt.Color(
            f"{kat_feld}:N",
            scale=alt.Scale(domain=kategorien, range=farben),
            legend=None,                       # keine Legende
        ),
        opacity=opacity_enc,
        tooltip=[kat_feld, alt.Tooltip(f"{wert_feld}:Q", format=".2f")],
    )

    # Beschriftung mit Pfeil, aussen neben dem jeweiligen Segment
    labels = base.mark_text(
        radius=122, fontSize=12, fontWeight=600, fill=INK,
    ).encode(text=alt.Text("_lbl:N"))

    chart = (arc + labels).properties(height=320, background="transparent")
    if selection:
        chart = chart.add_params(selection)
    return chart.configure_view(fill=None, stroke=None)


def torte_mit_drilldown(spalte, titel, gruppen_df, quelle_df, chart_v_schluessel, sel_name):
    """Rendert in 'spalte' einen Donut + (bei Klick) Produkt-Drilldown."""
    with spalte:
        st.subheader(titel)
        if gruppen_df.empty:
            st.caption("Keine Daten in dieser Gruppe.")
            return

        sel        = alt.selection_point(fields=["Kategorie"], name=sel_name)
        chart_key  = f"{sel_name}_{st.session_state[chart_v_schluessel]}"
        event      = st.altair_chart(
            torte(gruppen_df, "Kategorie", "Preis", selection=sel),
            use_container_width=True,
            on_select="rerun",
            key=chart_key,
        )

        selected = None
        try:
            pts = event.selection.get(sel_name, [])
            if pts:
                selected = pts[0].get("Kategorie")
        except Exception:
            pass

        if selected:
            prod_df = (quelle_df[quelle_df["Kategorie"] == selected]
                       .groupby("Produkt", as_index=False)["Preis"].sum())
            titel_col, close_col = st.columns([6, 1])
            with titel_col:
                st.markdown(f"**↳ {selected}**")
            with close_col:
                if st.button("✕", key=f"close_{sel_name}", help="Drilldown schließen"):
                    st.session_state[chart_v_schluessel] += 1
                    st.rerun()
            st.altair_chart(
                torte(prod_df, "Produkt", "Preis"),
                use_container_width=True,
            )


def glas_linie(data, x_feld, y_feld, farbe, tag_marker=None):
    if data.empty:
        return None
    x_min = data[x_feld].min()
    x_max = data[x_feld].max()
    x_scale = alt.Scale(
        domain=[
            (x_min - pd.Timedelta(hours=12)).isoformat(),
            (x_max + pd.Timedelta(hours=12)).isoformat(),
        ],
        nice=False,
    )
    enc_x = alt.X(f"{x_feld}:T", axis=_ax(fmt="%d.%m.", angle=-45, tick_count="day"),
                  scale=x_scale)
    enc_y = alt.Y(f"{y_feld}:Q", axis=_ax(grid=True), scale=alt.Scale(zero=False))

    def _gruppe(subset, fl_op, li_op):
        b = alt.Chart(subset).encode(x=enc_x, y=enc_y)
        return [
            b.mark_area(opacity=fl_op, color=farbe, clip=True),
            b.mark_line(color=farbe, strokeWidth=2.5, opacity=li_op, clip=True),
            b.mark_point(color=farbe, filled=True, size=50, opacity=li_op, clip=True),
        ]

    if tag_marker is not None:
        tag_ts = pd.Timestamp(tag_marker)
        verg = data[data[x_feld] <= tag_ts]
        zuku = data[data[x_feld] > tag_ts]
    else:
        verg, zuku = data, data.iloc[0:0]

    alle = _gruppe(verg if not verg.empty else data, 0.35, 1.0)
    if not zuku.empty:
        alle += _gruppe(zuku, 0.08, 0.25)

    if tag_marker is not None and x_min != x_max:
        regel_df = pd.DataFrame({x_feld: [pd.Timestamp(tag_marker)]})
        alle.append(
            alt.Chart(regel_df)
            .mark_rule(color=ACCENT, strokeDash=[8, 4], strokeWidth=2)
            .encode(x=alt.X(f"{x_feld}:T", scale=x_scale))
        )

    return (
        alt.layer(*alle)
        .properties(height=300, background="transparent")
        .configure_view(fill=None, stroke=None)
    )


# ==========================================================
# 5. SESSION-STATE INITIALISIEREN
# ==========================================================
if "editor_v" not in st.session_state:      # Versionsnummer fuer den Daten-Editor
    st.session_state.editor_v = 0
if "fix_chart_v" not in st.session_state:    # Versionsnummer fuer den Fixkosten-Chart
    st.session_state.fix_chart_v = 0
if "var_chart_v" not in st.session_state:    # Versionsnummer fuer den Variable-Ausgaben-Chart
    st.session_state.var_chart_v = 0

# ==========================================================
# 6. TITEL & FLASH-NACHRICHTEN
# ==========================================================
st.title("◈ KOSTENANALYSE")
st.write("Trage deine Ausgaben ein und behalte deinen Kontostand im Blick.")

# Nach einem st.rerun() hinterlegte Meldung anzeigen
if "flash" in st.session_state:
    f_typ, f_txt = st.session_state.pop("flash")
    getattr(st, f_typ)(f_txt)   # z. B. st.success(...) / st.info(...)

# ==========================================================
# 7. SIDEBAR
# ==========================================================
with st.sidebar:
    st.header("⚙ Konto")
    startkontostand_gespeichert = lade_einstellung("startkontostand", 1000.0)
    startkontostand = st.number_input(
        "Startkontostand (€)", min_value=0.0,
        value=startkontostand_gespeichert, step=10.0, format="%.2f",
    )
    if st.button("💾 Startkontostand speichern"):
        speichere_einstellung("startkontostand", startkontostand)
        setze_flash(f"Startkontostand auf {startkontostand:.2f} € gespeichert!", "success")
        st.rerun()
    st.caption("Ausgaben werden abgezogen · Gehalt wird addiert.")
    st.divider()
    if st.button("🔄 Daten neu laden"):
        st.cache_data.clear()
        st.rerun()

# ==========================================================
# 8. FORMULAR  ->  NEUE TRANSAKTION IN SUPABASE SPEICHERN
# ==========================================================
with st.form("ausgaben_form", clear_on_submit=True):
    st.subheader("Neue Ausgabe hinzufügen")
    produkt   = st.text_input("Was hast du gekauft / Einnahme-Quelle?")
    preis     = st.number_input("Wie viel (in €)?", min_value=0.0, step=0.01, format="%.2f")
    kaufdatum = st.date_input("Wann?", value=date.today())
    kategorie = st.selectbox("Kategorie", KATEGORIEN)
    submit_button = st.form_submit_button("Hinzufügen")

if submit_button and produkt:
    fuege_transaktion_hinzu(kaufdatum, preis, kategorie, produkt)
    setze_flash(f"'{produkt}' für {preis:.2f} € erfolgreich gespeichert!", "success")
    nach_aenderung()   # Cache leeren, Editor zuruecksetzen, neu laden

# ==========================================================
# 9. DATEN LADEN & DASHBOARD
# ==========================================================
df_db = lade_transaktionen()

if df_db.empty:
    st.divider()
    st.info("Noch keine Transaktionen in der Datenbank vorhanden. "
            "Nutze das Formular oben, um Daten zu speichern!")
else:
    # ---- Metriken berechnen --------------------------------------------
    ist_einnahme  = df_db["Kategorie"].isin(EINNAHME_KAT)
    ist_fix       = df_db["Kategorie"].isin(FIXKOSTEN_KAT)
    ist_variabel  = ~ist_einnahme & ~ist_fix     # alles ausser Einnahmen & Fixkosten

    einnahmen_sum = df_db.loc[ist_einnahme, "Preis"].sum()
    fixkosten_sum = df_db.loc[ist_fix,      "Preis"].sum()
    variabel_sum  = df_db.loc[ist_variabel, "Preis"].sum()

    # Kontostand: Einnahmen rauf, ALLE Ausgaben (variabel + fix) runter
    aktueller_stand = startkontostand + einnahmen_sum - variabel_sum - fixkosten_sum
    netto_delta     = einnahmen_sum - variabel_sum - fixkosten_sum

    # Variable Ausgaben (netto, Einnahmen mindern sie)
    variable_netto = variabel_sum - einnahmen_sum
    # Gesamtausgaben = Variable Ausgaben + Fixkosten
    gesamtausgaben = variable_netto + fixkosten_sum
    tage_eingetragen = df_db["Datum"].dt.normalize().nunique()
    # Taeglicher Durchschnitt NUR aus den variablen Kosten
    taeglicher_durchschnitt = (
        variable_netto / tage_eingetragen if tage_eingetragen > 0 else 0.0
    )

    st.divider()
    # Obere Reihe: Kontostand links, Gesamtausgaben-Block rechts
    top_l, top_r = st.columns(2)
    with top_l:
        st.metric("Aktueller Kontostand", f"{aktueller_stand:.2f} €",
                  delta=f"{netto_delta:+.2f} €")
    with top_r:
        st.markdown(f"""
        <div style="background:var(--glass-strong);
                    -webkit-backdrop-filter:blur(16px); backdrop-filter:blur(16px);
                    border:1px solid var(--glass-border); border-radius:20px;
                    padding:14px 30px; text-align:center; height:100%;
                    box-shadow:0 8px 28px rgba(12,36,28,0.12), inset 0 1px 0 rgba(255,255,255,0.6);">
          <div style="font-size:0.82rem; color:#22483b; letter-spacing:1.5px;">GESAMTAUSGABEN</div>
          <div style="font-family:'Space Grotesk',sans-serif; font-weight:500;
                      font-size:1.9rem; color:var(--accent);">{gesamtausgaben:.2f} €</div>
          <div style="font-size:0.8rem; color:#22483b;">∅ täglich · {taeglicher_durchschnitt:.2f} €</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Aufsteigend sortierte Kopie fuer die Diagramme
    df = df_db.sort_values("Datum").reset_index(drop=True)

    # ---- Pfeil-Fächer: von oben nach unten in die beiden Torten ---------
    st.markdown(f"""
    <svg viewBox="0 0 600 70" width="100%" height="70"
         preserveAspectRatio="xMidYMid meet" style="display:block;">
      <defs>
        <marker id="pfeil" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="{ACCENT}"></path>
        </marker>
      </defs>
      <path d="M300,4 C300,38 175,30 150,60" fill="none" stroke="{ACCENT}"
            stroke-width="3" marker-end="url(#pfeil)"></path>
      <path d="M300,4 C300,38 425,30 450,60" fill="none" stroke="{ACCENT}"
            stroke-width="3" marker-end="url(#pfeil)"></path>
    </svg>
    """, unsafe_allow_html=True)

    # ---- Tortendiagramme: Fixkosten links | Variable Ausgaben rechts ----
    fix_col, var_col = st.columns(2)

    # Fixkosten-Gruppe (Investment, Fixkosten, Miete)
    fix_summe = (df[df["Kategorie"].isin(FIXKOSTEN_KAT)]
                 .groupby("Kategorie", as_index=False)["Preis"].sum())
    # Variable Ausgaben = alles ausser Einnahmen & Fixkosten
    var_summe = (df[~df["Kategorie"].isin(EINNAHME_KAT) & ~df["Kategorie"].isin(FIXKOSTEN_KAT)]
                 .groupby("Kategorie", as_index=False)["Preis"].sum())

    torte_mit_drilldown(fix_col, f"Fixkosten · {fixkosten_sum:.2f} €", fix_summe, df,
                        "fix_chart_v", "fix_sel")
    torte_mit_drilldown(var_col, f"Variable Ausgaben · {variable_netto:.2f} €", var_summe, df,
                        "var_chart_v", "var_sel")

    # ---- Tabelle (editierbar, unter den Diagrammen) --------------------
    st.divider()
    with st.container():
        st.subheader("Übersicht")
        # Nur die relevanten Spalten in fester Reihenfolge; id wird ausgeblendet,
        # bleibt aber fuer die Zuordnung Zeile -> Datenbank-id erhalten.
        df_anzeige = df_db[["id", "Datum", "Produkt", "Preis", "Kategorie"]].reset_index(drop=True)
        editor_key = f"ausgaben_editor_{st.session_state.editor_v}"

        st.data_editor(
            df_anzeige,
            column_config={
                "id": None,  # ID ausblenden
                "Datum":     st.column_config.DateColumn("Datum", format="DD.MM.YYYY"),
                "Produkt":   st.column_config.TextColumn("Produkt/Beschreibung"),
                "Preis":     st.column_config.NumberColumn("Betrag (€)", format="%.2f",
                                                           min_value=0.0),
                "Kategorie": st.column_config.SelectboxColumn("Kategorie", options=KATEGORIEN),
            },
            num_rows="dynamic",     # erlaubt Zeilen hinzufuegen & loeschen
            use_container_width=True,
            hide_index=True,
            key=editor_key,
        )

        col_save, col_hint = st.columns([1, 2])
        with col_save:
            if st.button("💾 Änderungen speichern", key="save_edits"):
                delta = st.session_state.get(editor_key, {})
                n = verarbeite_editor_aenderungen(delta, df_anzeige)
                setze_flash(
                    f"{n} Änderung(en) in Supabase gespeichert." if n
                    else "Keine Änderungen zum Speichern.",
                    "success" if n else "info",
                )
                nach_aenderung()
        with col_hint:
            st.caption("Zellen bearbeiten, Zeilen per 🗑 löschen oder unten neu "
                       "anlegen – danach **Änderungen speichern**.")

    # ---- Kontostand-Verlauf --------------------------------------------
    if not df.empty:
        st.divider()
        st.subheader("Kontostand über die Zeit")

        # Gehalt addieren, alle anderen subtrahieren
        df["_netto"] = df.apply(
            lambda r: r["Preis"] if r["Kategorie"] in EINNAHME_KAT else -r["Preis"],
            axis=1,
        )
        taeglich       = df.groupby(df["Datum"].dt.normalize())["_netto"].sum().sort_index()
        voller_bereich = pd.date_range(taeglich.index.min(), taeglich.index.max(), freq="D")
        taeglich       = taeglich.reindex(voller_bereich, fill_value=0.0)
        kontostand_serie = startkontostand + taeglich.cumsum()

        min_d = kontostand_serie.index.min().date()
        max_d = kontostand_serie.index.max().date()

        if min_d < max_d:
            tag = st.slider("Tag auswählen", min_value=min_d, max_value=max_d,
                            value=max_d, format="DD.MM.YYYY")
        else:
            tag = min_d
            st.caption(f"Es liegen nur Daten für den {tag:%d.%m.%Y} vor.")

        stand_am_tag = float(kontostand_serie.loc[pd.Timestamp(tag)])
        st.metric(f"Kontostand am {tag:%d.%m.%Y}", f"{stand_am_tag:.2f} €")

        verlauf = kontostand_serie.reset_index()
        verlauf.columns = ["Datum", "Kontostand"]
        chart = glas_linie(verlauf, "Datum", "Kontostand", ACCENT2, tag_marker=tag)
        if chart:
            st.altair_chart(chart, use_container_width=True)

# ==========================================================
# 10. VERBESSERUNGSVORSCHLÄGE
# ==========================================================
st.divider()
st.subheader("Verbesserungsvorschläge")
st.caption("Schreib hier deine Ideen und Wünsche für die Webseite auf – sie werden gespeichert.")

verbesserungen_geladen = lade_einstellung_text("verbesserungen", "")
verbesserungen_text = st.text_area(
    label="Deine Vorschläge:",
    value=verbesserungen_geladen,
    height=180,
    placeholder="z. B. Neue Kategorie hinzufügen, Diagramm anpassen, ...",
    label_visibility="collapsed",
)
if st.button("💾 Vorschläge speichern", key="save_verbesserungen"):
    speichere_einstellung("verbesserungen", verbesserungen_text)
    st.success("Vorschläge wurden gespeichert!")

# streamlit run "C:\Users\Oliver Dennis\PycharmProjects\PythonProject\Test-Dashboard\Dashboard_Test.py"

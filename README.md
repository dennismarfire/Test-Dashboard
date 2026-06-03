import streamlit as st
import pandas as pd
import altair as alt
from datetime import date

# ─────────────────────────────────────────────────────────────
# Grundeinstellungen
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Kostenanalyse", page_icon="💰", layout="wide")

# Farben zentral
INK = "#0c241c"        # dunkles Grün-Schwarz (Text)
ACCENT = "#0b6b4f"     # sattes Grün
ACCENT2 = "#0a4f8c"    # kontrastierendes Blau

# ─────────────────────────────────────────────────────────────
# Liquid-Glass-Design auf grünem Verlauf (CSS)
# ─────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=Space+Grotesk:wght@300;400;500;600&display=swap');

:root{{
  --ink:{INK};
  --accent:{ACCENT};
  --accent2:{ACCENT2};
  --glass:rgba(255,255,255,0.42);
  --glass-strong:rgba(255,255,255,0.70);
  --glass-border:rgba(255,255,255,0.85);
}}

[data-testid="stAppViewContainer"] * {{ font-family:'Space Grotesk', sans-serif; }}

/* Hintergrund: heller Grünverlauf */
[data-testid="stAppViewContainer"]{{
  background:linear-gradient(160deg, #e8fbef 0%, #b9f0cf 45%, #6fce9b 100%);
  background-attachment:fixed;
  color:var(--ink);
}}
[data-testid="stHeader"]{{ background:transparent; }}
.block-container{{ padding-top:2.5rem; max-width:1150px; }}

/* Seitenleiste als Glasfläche */
[data-testid="stSidebar"]{{
  background:var(--glass);
  backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px);
  border-right:1px solid var(--glass-border);
}}
/* Seitenleisten-Überschrift kräftig dunkel */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3{{ color:var(--ink) !important; opacity:1 !important; }}
[data-testid="stSidebar"] *{{ color:var(--ink) !important; }}

/* Überschriften */
h1{{
  font-family:'Orbitron',sans-serif !important; font-weight:800; letter-spacing:2px;
  background:linear-gradient(90deg,var(--accent),var(--accent2));
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}}
h2,h3{{ font-family:'Orbitron',sans-serif !important; letter-spacing:1px; color:var(--ink); }}
p, label, .stMarkdown, [data-testid="stWidgetLabel"]{{ color:var(--ink) !important; }}

/* ---------- Liquid Glass: Eingabefelder (glasig weiß) ---------- */
[data-baseweb="base-input"],
[data-baseweb="input"],
[data-baseweb="select"] > div{{
  background:var(--glass-strong) !important;
  -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px);
  border:1px solid var(--glass-border) !important;
  border-radius:14px !important;
  box-shadow:0 4px 18px rgba(11,107,79,0.12), inset 0 1px 0 rgba(255,255,255,0.8);
}}
/* die eigentlichen Eingabe-Elemente transparent, damit die Glasfläche durchscheint */
.stTextInput input, .stNumberInput input, .stDateInput input,
[data-baseweb="base-input"] input,
[data-baseweb="select"] div{{
  background:transparent !important;
  color:var(--ink) !important;
  -webkit-text-fill-color:var(--ink) !important;
}}
.stTextInput input::placeholder{{ color:#4a6b5e !important; }}
/* +/- Knöpfe am Zahlenfeld glasig */
.stNumberInput button{{
  background:var(--glass-strong) !important; color:var(--ink) !important;
  border:1px solid var(--glass-border) !important;
}}
[data-baseweb="popover"], [data-baseweb="popover"] *{{ color:var(--ink) !important; }}

/* ---------- Liquid Glass: Buttons ---------- */
div.stButton > button, div.stFormSubmitButton > button{{
  width:100%;
  background:linear-gradient(135deg, rgba(11,107,79,0.85), rgba(10,79,140,0.85));
  -webkit-backdrop-filter:blur(10px); backdrop-filter:blur(10px);
  border:1px solid var(--glass-border); color:#ffffff; border-radius:16px;
  font-weight:600; padding:0.6rem 1rem; letter-spacing:1px; transition:all .2s ease;
  box-shadow:0 6px 20px rgba(11,107,79,0.25), inset 0 1px 0 rgba(255,255,255,0.5);
}}
div.stButton > button:hover, div.stFormSubmitButton > button:hover{{
  transform:translateY(-1px); box-shadow:0 10px 26px rgba(11,107,79,0.35);
}}

/* ---------- Liquid Glass: Formular-Karte ---------- */
[data-testid="stForm"]{{
  background:var(--glass);
  -webkit-backdrop-filter:blur(20px); backdrop-filter:blur(20px);
  border:1px solid var(--glass-border); border-radius:24px;
  padding:8px 24px 6px;
  box-shadow:0 12px 40px rgba(12,36,28,0.12), inset 0 1px 0 rgba(255,255,255,0.6);
}}

/* ---------- Liquid Glass: Metrik-Karten ---------- */
[data-testid="stMetric"]{{
  background:var(--glass-strong);
  -webkit-backdrop-filter:blur(16px); backdrop-filter:blur(16px);
  border:1px solid var(--glass-border); border-radius:20px; padding:18px 20px;
  box-shadow:0 8px 28px rgba(12,36,28,0.12), inset 0 1px 0 rgba(255,255,255,0.6);
}}
[data-testid="stMetricValue"]{{ font-family:'Orbitron',sans-serif; color:var(--accent); }}
[data-testid="stMetricLabel"]{{ color:#22483b; }}

/* ---------- Liquid Glass: Tabelle ---------- */
[data-testid="stDataFrame"]{{
  background:var(--glass-strong);
  -webkit-backdrop-filter:blur(14px); backdrop-filter:blur(14px);
  border:1px solid var(--glass-border); border-radius:18px; padding:6px;
  box-shadow:0 8px 28px rgba(12,36,28,0.10);
}}
[data-testid="stDataFrame"] *{{ color:var(--ink) !important; }}

/* ---------- Glas-Rahmen um die Diagramme ---------- */
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"]{{
  background:var(--glass);
  -webkit-backdrop-filter:blur(14px); backdrop-filter:blur(14px);
  border:1px solid var(--glass-border); border-radius:18px; padding:14px;
  box-shadow:0 8px 28px rgba(12,36,28,0.10), inset 0 1px 0 rgba(255,255,255,0.5);
}}

/* ---------- Liquid Glass: Slider ---------- */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"]{{
  background:var(--glass-strong) !important;
  border:1px solid var(--accent) !important;
  box-shadow:0 2px 10px rgba(11,107,79,0.35);
}}

hr{{ border:none; height:2px;
  background:linear-gradient(90deg,transparent,rgba(11,107,79,0.5),transparent); }}

[data-testid="stAlert"]{{
  -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px);
  border-radius:16px;
}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Hilfsfunktionen: durchscheinende Glas-Diagramme mit Altair
# ─────────────────────────────────────────────────────────────
def glas_balken(data, x_feld, y_feld, farbe):
    """Balkendiagramm: halbtransparente Balken, kräftiger Rand, dunkle Achsen."""
    achse_x = alt.Axis(labelColor=INK, titleColor=INK, labelFontSize=12,
                       titleFontSize=13, domainColor=INK, tickColor=INK)
    achse_y = alt.Axis(labelColor=INK, titleColor=INK, labelFontSize=12,
                       titleFontSize=13, domainColor=INK, tickColor=INK,
                       gridColor="rgba(12,36,28,0.12)")
    return (
        alt.Chart(data)
        .mark_bar(opacity=0.55, color=farbe, stroke=farbe, strokeWidth=2,
                  cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
        .encode(
            x=alt.X(f"{x_feld}:N", axis=achse_x, sort="-y"),
            y=alt.Y(f"{y_feld}:Q", axis=achse_y),
            tooltip=[x_feld, alt.Tooltip(f"{y_feld}:Q", format=".2f")],
        )
        .properties(height=300, background="transparent")
        .configure_view(fill=None, stroke=None)
    )

def glas_linie(data, x_feld, y_feld, farbe):
    """Linien-/Flächendiagramm mit halbtransparenter Glasfläche."""
    achse_x = alt.Axis(labelColor=INK, titleColor=INK, domainColor=INK, tickColor=INK)
    achse_y = alt.Axis(labelColor=INK, titleColor=INK, domainColor=INK, tickColor=INK,
                       gridColor="rgba(12,36,28,0.12)")
    basis = alt.Chart(data).encode(
        x=alt.X(f"{x_feld}:T", axis=achse_x),
        y=alt.Y(f"{y_feld}:Q", axis=achse_y, scale=alt.Scale(zero=False)),
    )
    flaeche = basis.mark_area(opacity=0.30, color=farbe)
    linie = basis.mark_line(color=farbe, strokeWidth=3)
    punkte = basis.mark_point(color=farbe, filled=True, size=60)
    return (
        (flaeche + linie + punkte)
        .properties(height=300, background="transparent")
        .configure_view(fill=None, stroke=None)
    )

# ─────────────────────────────────────────────────────────────
# Titel
# ─────────────────────────────────────────────────────────────
st.title("◈ KOSTENANALYSE")
st.write("Trage deine Ausgaben ein und behalte deinen Kontostand im Blick.")

# ─────────────────────────────────────────────────────────────
# Session State initialisieren
# ─────────────────────────────────────────────────────────────
if "ausgaben" not in st.session_state:
    st.session_state.ausgaben = []

# ─────────────────────────────────────────────────────────────
# Startkontostand – in der Seitenleiste festlegen
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙ Konto")
    startkontostand = st.number_input(
        "Startkontostand (€)", min_value=0.0, value=1000.0, step=10.0, format="%.2f"
    )
    st.caption("Jede Ausgabe wird automatisch davon abgezogen.")

# ─────────────────────────────────────────────────────────────
# Eingabeformular
# ─────────────────────────────────────────────────────────────
with st.form("ausgaben_form", clear_on_submit=True):
    st.subheader("Neue Ausgabe hinzufügen")

    produkt = st.text_input("Was hast du gekauft?")
    preis = st.number_input("Wie viel hast du bezahlt (in €)?",
                            min_value=0.0, step=0.01, format="%.2f")
    kaufdatum = st.date_input("Wann hast du es gekauft?", value=date.today())
    kategorie = st.selectbox("Kategorie", ["Keine", "Feiern", "Einkauf"])

    submit_button = st.form_submit_button("Hinzufügen")

if submit_button and produkt:
    st.session_state.ausgaben.append({
        "Produkt": produkt,
        "Preis": preis,
        "Datum": kaufdatum,
        "Kategorie": kategorie,
    })
    st.success(f"'{produkt}' für {preis:.2f} € am {kaufdatum:%d.%m.%Y} hinzugefügt!")

# ─────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────
if st.session_state.ausgaben:
    df = pd.DataFrame(st.session_state.ausgaben)
    df["Datum"] = pd.to_datetime(df["Datum"])
    df = df.sort_values("Datum")

    gesamt_kosten = df["Preis"].sum()
    aktueller_stand = startkontostand - gesamt_kosten

    st.divider()

    # Kennzahlen
    m1, m2 = st.columns(2)
    with m1:
        st.metric("Aktueller Kontostand", f"{aktueller_stand:.2f} €",
                  delta=f"-{gesamt_kosten:.2f} €")
    with m2:
        st.metric("Gesamtausgaben", f"{gesamt_kosten:.2f} €")

    # Tabelle
    st.subheader("Übersicht")
    anzeige_df = df.copy()
    anzeige_df["Datum"] = anzeige_df["Datum"].dt.strftime("%d.%m.%Y")
    anzeige_df["Kategorie"] = anzeige_df["Kategorie"].replace("Keine", "—")
    st.dataframe(anzeige_df, use_container_width=True, hide_index=True)

    if st.button("Alle Daten löschen"):
        st.session_state.ausgaben = []
        st.rerun()

    # Produkt- und Kategorie-Diagramm nebeneinander (Glas)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Nach Produkten")
        produkt_summe = df.groupby("Produkt", as_index=False)["Preis"].sum()
        st.altair_chart(glas_balken(produkt_summe, "Produkt", "Preis", ACCENT2),
                        use_container_width=True)
    with col2:
        st.subheader("Nach Kategorie")
        kat_summe = df.groupby("Kategorie", as_index=False)["Preis"].sum()
        st.altair_chart(glas_balken(kat_summe, "Kategorie", "Preis", ACCENT),
                        use_container_width=True)

    # Kontostand-Verlauf mit Tages-Slider
    st.divider()
    st.subheader("Kontostand über die Zeit")

    taeglich = df.groupby(df["Datum"].dt.normalize())["Preis"].sum().sort_index()
    voller_bereich = pd.date_range(taeglich.index.min(), taeglich.index.max(), freq="D")
    taeglich = taeglich.reindex(voller_bereich, fill_value=0.0)

    kontostand_serie = startkontostand - taeglich.cumsum()

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
    st.altair_chart(glas_linie(verlauf, "Datum", "Kontostand", ACCENT2),
                    use_container_width=True)

else:
    st.info("Noch keine Ausgaben eingetragen. Nutze das Formular oben, um zu starten.")

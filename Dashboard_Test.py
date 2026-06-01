import streamlit as st
import pandas as pd
from datetime import date

# 1. Dashboard Titel & Erklärung
st.title("💰 Meine interaktive Kostenanalyse")
st.write("Trage deine Ausgaben ein, um die Übersicht direkt im Dashboard zu sehen.")

# 2. Session State initialisieren
# NEU: Liste von Einträgen statt Dictionary.
# Vorteil: Jeder Eintrag kann ein eigenes Datum haben und das gleiche
# Produkt darf mehrfach (an verschiedenen Tagen) vorkommen.
if "ausgaben" not in st.session_state:
    st.session_state.ausgaben = []

# 3. Interaktives Formular für die Eingabe
with st.form("ausgaben_form", clear_on_submit=True):
    st.subheader("Neue Ausgabe hinzufügen")

    # Eingabefelder (ersetzt input())
    produkt = st.text_input("Was hast du gekauft?")

    # st.number_input erlaubt direkt Kommazahlen und fängt Fehler ab
    preis = st.number_input(
        "Wie viel hast du bezahlt (in €)?",
        min_value=0.0, step=0.01, format="%.2f"
    )

    # NEU: Datumseingabe – Standardwert ist das heutige Datum
    kaufdatum = st.date_input("Wann hast du es gekauft?", value=date.today())

    # Absendeknopf für das Formular
    submit_button = st.form_submit_button("Hinzufügen")

# Wenn der Button gedrückt wird, fügen wir die Daten zum "Speicher" hinzu
if submit_button and produkt:
    st.session_state.ausgaben.append({
        "Produkt": produkt,
        "Preis": preis,
        "Datum": kaufdatum,
    })
    st.success(f"'{produkt}' für {preis:.2f} € am {kaufdatum:%d.%m.%Y} hinzugefügt!")

# 4. Dashboard-Inhalte anzeigen, sobald Daten vorhanden sind
if st.session_state.ausgaben:
    # DataFrame direkt aus der Liste bauen
    df = pd.DataFrame(st.session_state.ausgaben)

    # Datum in echtes datetime umwandeln (wichtig für Sortierung & Zeit-Diagramm)
    df["Datum"] = pd.to_datetime(df["Datum"])
    df = df.sort_values("Datum")

    gesamt_kosten = df["Preis"].sum()

    st.divider()  # Trennlinie

    # Gesamtkosten groß als Zahl (Metric) anzeigen
    st.metric(label="Deine Gesamtkosten", value=f"{gesamt_kosten:.2f} €")

    # Zwei Spalten nebeneinander für die Übersicht erstellen
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Übersicht als Tabelle")
        # Datum hübsch formatiert (TT.MM.JJJJ) für die Anzeige
        anzeige_df = df.copy()
        anzeige_df["Datum"] = anzeige_df["Datum"].dt.strftime("%d.%m.%Y")
        st.dataframe(anzeige_df, use_container_width=True, hide_index=True)

        # Option zum Zurücksetzen der Daten
        if st.button("Alle Daten löschen"):
            st.session_state.ausgaben = []
            st.rerun()

    with col2:
        st.subheader("Ausgaben nach Produkten")
        # Gleiche Produkte aufsummieren, damit jedes Produkt nur einmal erscheint
        produkt_summe = df.groupby("Produkt", as_index=False)["Preis"].sum()
        st.bar_chart(data=produkt_summe, x="Produkt", y="Preis", color="#FF4B4B")

    # NEU: Zeitlicher Verlauf der Ausgaben
    st.divider()
    st.subheader("Ausgaben im zeitlichen Verlauf")
    # Pro Tag und Produkt summieren -> gestapelte Balken pro Datum,
    # eingefärbt nach Produkt. So siehst du WANN du WAS ausgegeben hast.
    zeit_df = df.groupby(["Datum", "Produkt"], as_index=False)["Preis"].sum()
    st.bar_chart(data=zeit_df, x="Datum", y="Preis", color="Produkt")

else:
    st.info("Noch keine Ausgaben eingetragen. Nutze das Formular oben, um zu starten.")
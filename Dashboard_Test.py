import streamlit as st
import pandas as pd

# 1. Dashboard Titel & Erklärung
st.title("💰 Meine interaktive Kostenanalyse")
st.write("Trage deine Ausgaben ein, um die Übersicht direkt im Dashboard zu sehen.")

# 2. Session State initialisieren (Speichert Daten auch beim Neuladen der App)
if "ausgaben" not in st.session_state:
    st.session_state.ausgaben = {}

# 3. Interaktives Formular für die Eingabe
with st.form("ausgaben_form", clear_on_submit=True):
    st.subheader("Neue Ausgabe hinzufügen")

    # Eingabefelder (ersetzt input())
    produkt = st.text_input("Was hast du gekauft?")

    # st.number_input erlaubt direkt Kommazahlen und fängt Fehler ab
    preis = st.number_input("Wie viel hast du bezahlt (in €)?", min_value=0.0, step=0.01, format="%.2f")

    # Absendeknopf für das Formular
    submit_button = st.form_submit_button("Hinzufügen")

# Wenn der Button gedrückt wird, fügen wir die Daten zum "Speicher" hinzu
if submit_button and produkt:
    st.session_state.ausgaben[produkt] = preis
    st.success(f"'{produkt}' für {preis:.2f} € erfolgreich hinzugefügt!")

# 4. Dashboard-Inhalte anzeigen, sobald Daten vorhanden sind
if st.session_state.ausgaben:
    kosten_liste = st.session_state.ausgaben
    gesamt_kosten = sum(kosten_liste.values())

    st.divider()  # Trennlinie

    # Gesamtkosten groß als Zahl (Metric) anzeigen
    st.metric(label="Deine Gesamtkosten", value=f"{gesamt_kosten:.2f} €")

    # Daten für Diagramme in eine Tabelle (DataFrame) umwandeln
    df = pd.DataFrame(list(kosten_liste.items()), columns=["Produkt", "Preis"])

    # Zwei Spalten nebeneinander für die Übersicht erstellen
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Übersicht als Tabelle")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Option zum Zurücksetzen der Daten
        if st.button("Alle Daten löschen"):
            st.session_state.ausgaben = {}
            st.rerun()

    with col2:
        st.subheader("Ausgaben nach Produkten")
        # Interaktives Balkendiagramm von Streamlit (ersetzt das Matplotlib-Pie-Chart)
        st.bar_chart(data=df, x="Produkt", y="Preis", color="#FF4B4B")

else:
    st.info("Noch keine Ausgaben eingetragen. Nutze das Formular oben, um zu starten.")

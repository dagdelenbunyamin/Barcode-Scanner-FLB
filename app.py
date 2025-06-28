import streamlit as st
import sqlite3
import cv2
from pyzbar.pyzbar import decode
import numpy as np
from datetime import datetime
from fpdf import FPDF
import pandas as pd

USER_CREDENTIALS = {"admin": "flb23"}

def initialize_database():
    with sqlite3.connect('students.db') as connection:
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                name TEXT,
                date TEXT,
                time TEXT,
                action TEXT
            )
        ''')
        connection.commit()

def add_student(barcode_id, student_name):
    try:
        with sqlite3.connect('students.db') as connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO students (id, name) VALUES (?, ?)", (barcode_id, student_name))
            connection.commit()
            return f"Schüler {student_name} mit Barcode-ID {barcode_id} erfolgreich hinzugefügt."
    except sqlite3.IntegrityError:
        return "Fehler: Diese Barcode-ID existiert bereits."
    except sqlite3.Error as e:
        return f"Datenbankfehler: {e}"

def get_student_name(barcode_id):
    with sqlite3.connect('students.db') as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM students WHERE id = ?", (barcode_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def log_scan(student_id, name, action):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")
    with sqlite3.connect('students.db') as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO log (student_id, name, date, time, action) VALUES (?, ?, ?, ?, ?)",
                       (student_id, name, date, time, action))
        connection.commit()

def start_scanner(mode):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        st.error("Kamera konnte nicht geöffnet werden.")
        return

    st.write(f"**Modus: {mode} – Drücke 'Scanner stoppen' zum Beenden.**")
    stop_button = st.button("Scanner stoppen")
    frame_placeholder = st.empty()

    while not stop_button:
        ret, frame = cap.read()
        if not ret:
            st.error("Fehler beim Lesen des Kamerabildes.")
            break

        barcodes = decode(frame)
        for barcode in barcodes:
            barcode_data = barcode.data.decode('utf-8')
            student_name = get_student_name(barcode_data)
            text = f"{student_name} ({barcode_data})" if student_name else f"Unbekannt ({barcode_data})"
            cv2.putText(frame, text, (barcode.rect.left, barcode.rect.top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
            if student_name:
                log_scan(barcode_data, student_name, mode)
                stop_button = True
                st.success(f"{mode} registriert: **{student_name}** um {datetime.now().strftime('%H:%M:%S')}")
                break

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)

    cap.release()
    cv2.destroyAllWindows()
    st.info("Scanner gestoppt.")

def export_filtered_log_to_pdf(logs, selected_date):
    if not logs:
        st.warning("Keine Daten zum Exportieren.")
        return

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Schüler-Logbuch für {selected_date}", ln=True, align='C')
    pdf.ln(10)

    for log in logs:
        line = f"{log[2]} {log[3]} - {log[1]} ({log[0]}) - {log[4]}"
        pdf.cell(200, 10, txt=line, ln=True)

    filename = f"logbuch_{selected_date}.pdf"
    pdf.output(filename)
    with open(filename, "rb") as f:
        st.download_button("📄 PDF herunterladen", data=f, file_name=filename, mime="application/pdf")

def logbuch_mit_filter():
    st.subheader("📅 Logbuch filtern & exportieren")
    selected_date = st.date_input("Datum auswählen")
    if selected_date:
        date_str = selected_date.strftime("%Y-%m-%d")
        with sqlite3.connect("students.db") as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT student_id, name, date, time, action FROM log WHERE date = ? ORDER BY time ASC", (date_str,))
            logs = cursor.fetchall()

        if logs:
            st.success(f"{len(logs)} Einträge gefunden für {date_str}")
            df = pd.DataFrame(logs, columns=["Barcode-ID", "Name", "Datum", "Uhrzeit", "Aktion"])
            st.dataframe(df, use_container_width=True)

            export_filtered_log_to_pdf(logs, date_str)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 CSV-Datei herunterladen",
                data=csv,
                file_name=f"logbuch_{date_str}.csv",
                mime="text/csv"
            )
        else:
            st.warning("Keine Einträge für dieses Datum.")

def schueler_verwalten():
    st.subheader("👨‍🏫 Schüler bearbeiten oder löschen")
    with sqlite3.connect("students.db") as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT id, name FROM students ORDER BY name ASC")
        schueler_liste = cursor.fetchall()

    if not schueler_liste:
        st.info("Noch keine Schüler in der Datenbank.")
        return

    auswahl = st.selectbox("Schüler auswählen", [f"{s[1]} ({s[0]})" for s in schueler_liste])
    ausgewählte_id = auswahl.split("(")[-1].strip(")")

    new_name = st.text_input("Neuer Name (optional):")
    if st.button("Namen aktualisieren"):
        if new_name.strip():
            with sqlite3.connect("students.db") as connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE students SET name = ? WHERE id = ?", (new_name.strip(), ausgewählte_id))
                connection.commit()
                st.success(f"Name aktualisiert auf: {new_name}")
                st.rerun()
        else:
            st.error("Bitte neuen Namen eingeben.")

    if st.button("❌ Schüler löschen"):
        with sqlite3.connect("students.db") as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM students WHERE id = ?", (ausgewählte_id,))
            connection.commit()
        st.success("Schüler gelöscht.")
        st.rerun()

def impressum():
    st.title("📄 Impressum")
    st.markdown("""
    **Verantwortlich:**  
    Bünyamin Dagdelen  
    Deutschland  
    E-Mail: ...
    """)

def datenschutz():
    st.title("🔒 Datenschutz")
    st.markdown("""
    Diese Anwendung speichert personenbezogene Daten (Name, Barcode-ID, Zeitstempel) lokal auf dem Server 
    in einer SQLite-Datenbank. Sie können jederzeit die gespeicherten Daten einsehen, ändern oder löschen.
    """)

def cookies_notice():
    if "cookies_accepted" not in st.session_state:
        st.session_state["cookies_accepted"] = False
    if not st.session_state["cookies_accepted"]:
        st.warning("🍪 Diese Anwendung verwendet Cookies.")
        if st.button("Akzeptieren"):
            st.session_state["cookies_accepted"] = True
            st.rerun()

def login_page():
    st.title("🔐 Login")
    username = st.text_input("Benutzername:")
    password = st.text_input("Passwort:", type="password")
    if st.button("Login"):
        if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("Falscher Benutzername oder Passwort!")

def main():
    initialize_database()
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        login_page()
        return

    cookies_notice()
    st.title("📷 Schülerregistrierung mit Barcode-Scanner")
    menu = [
        "Schüler hinzufügen", 
        "Barcode scannen", 
        "📅 Logbuch filtern & exportieren", 
        "👨‍🏫 Schüler verwalten", 
        "📄 Impressum", 
        "🔒 Datenschutz"
    ]
    choice = st.sidebar.selectbox("Menü auswählen", menu)

    if choice == "Schüler hinzufügen":
        st.subheader("🧑 Neuer Schüler")
        barcode_id = st.text_input("Barcode-ID:")
        student_name = st.text_input("Name:")
        if st.button("Hinzufügen"):
            if barcode_id and student_name:
                result = add_student(barcode_id, student_name)
                st.success(result)
            else:
                st.error("Bitte alle Felder ausfüllen.")
    elif choice == "Barcode scannen":
        st.subheader("🎦 Barcode scannen")
        mode = st.radio("Modus:", ["Anmeldung", "Abmeldung"])
        st.info(f"Modus: **{mode}** – Jetzt Barcode scannen.")
        if st.button("Scanner starten"):
            start_scanner(mode)
    elif choice == "📅 Logbuch filtern & exportieren":
        logbuch_mit_filter()
    elif choice == "👨‍🏫 Schüler verwalten":
        schueler_verwalten()
    elif choice == "📄 Impressum":
        impressum()
    elif choice == "🔒 Datenschutz":
        datenschutz()

if __name__ == "__main__":
    main()


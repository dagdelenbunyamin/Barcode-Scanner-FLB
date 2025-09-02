import streamlit as st
import sqlite3
from pyzbar.pyzbar import decode
import numpy as np
from datetime import datetime
from fpdf import FPDF
import pandas as pd
from PIL import Image
import io
import base64

# ----------------------------
# Konfiguration & Login
# ----------------------------
st.set_page_config(page_title="Barcode-Scanner FLB", page_icon="📷", layout="wide")
USER_CREDENTIALS = {"admin": "flb23"}

# ----------------------------
# Datenbank-Helfer
# ----------------------------
DB_PATH = "students.db"

def initialize_database():
    with sqlite3.connect(DB_PATH) as connection:
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
        with sqlite3.connect(DB_PATH) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO students (id, name) VALUES (?, ?)",
                (barcode_id.strip(), student_name.strip())
            )
            connection.commit()
            return f"Schüler {student_name} mit Barcode-ID {barcode_id} erfolgreich hinzugefügt."
    except sqlite3.IntegrityError:
        return "Fehler: Diese Barcode-ID existiert bereits."
    except sqlite3.Error as e:
        return f"Datenbankfehler: {e}"

def get_student_name(barcode_id):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM students WHERE id = ?", (barcode_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def log_scan(student_id, name, action):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO log (student_id, name, date, time, action) VALUES (?, ?, ?, ?, ?)",
            (student_id, name, date, time, action)
        )
        connection.commit()

def fetch_logs_by_date(date_str):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT student_id, name, date, time, action FROM log WHERE date = ? ORDER BY time ASC",
            (date_str,)
        )
        return cursor.fetchall()

def fetch_all_students():
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT id, name FROM students ORDER BY name ASC")
        return cursor.fetchall()

def update_student_name(student_id, new_name):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE students SET name = ? WHERE id = ?", (new_name, student_id))
        connection.commit()

def delete_student(student_id):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        connection.commit()

# ----------------------------
# UI-Komponenten
# ----------------------------
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
    username = st.text_input("Benutzername:", value="admin")
    password = st.text_input("Passwort:", type="password")
    if st.button("Login"):
        if USER_CREDENTIALS.get(username) == password:
            st.session_state["logged_in"] = True
            st.success("Erfolgreich angemeldet.")
            st.rerun()
        else:
            st.error("Falscher Benutzername oder Passwort!")

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
        # log = (student_id, name, date, time, action)
        line = f"{log[2]} {log[3]} - {log[1]} ({log[0]}) - {log[4]}"
        pdf.cell(200, 10, txt=line, ln=True)

    filename = f"logbuch_{selected_date}.pdf"
    pdf_bytes = pdf.output(dest="S").encode("latin-1", "ignore")

    st.download_button(
        "📄 PDF herunterladen",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True
    )

# ----------------------------
# Scanner (Browser-Kamera)
# ----------------------------
def decode_barcodes_from_image(pil_image):
    """pyzbar kann direkt auf PIL-Images arbeiten."""
    results = decode(pil_image)
    out = []
    for r in results:
        try:
            data = r.data.decode("utf-8", errors="ignore")
        except Exception:
            data = str(r.data)
        out.append({"type": r.type, "data": data})
    return out

def scanner_view():
    st.subheader("🎦 Barcode scannen (Browser-Kamera)")
    mode = st.radio("Modus:", ["Anmeldung", "Abmeldung"], horizontal=True)
    st.caption("Hinweis: Die Kamera läuft im **Browser**. Jede Person nutzt ihre **eigene Webcam**.")

    # st.camera_input nimmt ein Foto auf (Snapshot). Für „Live-Scan“ bräuchte man JS/streamlit-webrtc.
    img_file = st.camera_input("Kamera freigeben und Foto aufnehmen")

    if img_file is not None:
        pil_img = Image.open(img_file)
        results = decode_barcodes_from_image(pil_img)

        if not results:
            st.warning("Kein Barcode/QR erkannt. Bitte näher ran oder besseres Licht.")
            return

        st.success(f"{len(results)} Code(s) erkannt:")
        for res in results:
            st.write(f"- **{res['type']}**: `{res['data']}`")
            code = res["data"]
            student_name = get_student_name(code)
            if student_name:
                log_scan(code, student_name, mode)
                st.info(f"✅ {mode} registriert: **{student_name}** ({code}) um {datetime.now().strftime('%H:%M:%S')}")
            else:
                st.warning("Kein Schüler mit diesem Barcode gefunden. Lege ihn im Menü 'Schüler hinzufügen' an.")

        st.button("Neues Foto machen", type="primary")

# ----------------------------
# Schüler-Verwaltung
# ----------------------------
def schueler_hinzufuegen_view():
    st.subheader("🧑 Neuer Schüler")
    barcode_id = st.text_input("Barcode-ID:")
    student_name = st.text_input("Name:")
    if st.button("Hinzufügen"):
        if barcode_id.strip() and student_name.strip():
            result = add_student(barcode_id, student_name)
            if result.startswith("Fehler"):
                st.error(result)
            elif result.startswith("Datenbankfehler"):
                st.error(result)
            else:
                st.success(result)
        else:
            st.error("Bitte alle Felder ausfüllen.")

def schueler_verwalten_view():
    st.subheader("👨‍🏫 Schüler bearbeiten oder löschen")
    schueler_liste = fetch_all_students()

    if not schueler_liste:
        st.info("Noch keine Schüler in der Datenbank.")
        return

    auswahl = st.selectbox("Schüler auswählen", [f"{name} ({sid})" for sid, name in schueler_liste])
    ausgewählte_id = auswahl.split("(")[-1].strip(")")

    new_name = st.text_input("Neuer Name (optional):")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Namen aktualisieren"):
            if new_name.strip():
                update_student_name(ausgewählte_id, new_name.strip())
                st.success(f"Name aktualisiert auf: {new_name}")
                st.rerun()
            else:
                st.error("Bitte neuen Namen eingeben.")
    with col2:
        if st.button("❌ Schüler löschen"):
            delete_student(ausgewählte_id)
            st.success("Schüler gelöscht.")
            st.rerun()

# ----------------------------
# Logbuch & Export
# ----------------------------
def logbuch_mit_filter_view():
    st.subheader("📅 Logbuch filtern & exportieren")
    selected_date = st.date_input("Datum auswählen")
    if not selected_date:
        return
    date_str = selected_date.strftime("%Y-%m-%d")

    logs = fetch_logs_by_date(date_str)
    if logs:
        st.success(f"{len(logs)} Einträge gefunden für {date_str}")
        df = pd.DataFrame(
            logs,
            columns=["Barcode-ID", "Name", "Datum", "Uhrzeit", "Aktion"]
        )
        st.dataframe(df, use_container_width=True)
        # PDF & CSV
        export_filtered_log_to_pdf(logs, date_str)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 CSV-Datei herunterladen",
            data=csv,
            file_name=f"logbuch_{date_str}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.warning("Keine Einträge für dieses Datum.")

# ----------------------------
# Impressum & Datenschutz
# ----------------------------
def impressum_view():
    st.title("📄 Impressum")
    st.markdown("""
**Verantwortlich:**  
Bünyamin Dagdelen  
Deutschland  
E-Mail: ...
""")

def datenschutz_view():
    st.title("🔒 Datenschutz")
    st.markdown("""
Diese Anwendung speichert personenbezogene Daten (Name, Barcode-ID, Zeitstempel)
lokal auf dem Server in einer SQLite-Datenbank. Daten können eingesehen, geändert oder gelöscht werden.
""")

# ----------------------------
# App
# ----------------------------
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
        "🔒 Datenschutz",
    ]
    choice = st.sidebar.selectbox("Menü auswählen", menu)

    if choice == "Schüler hinzufügen":
        schueler_hinzufuegen_view()
    elif choice == "Barcode scannen":
        scanner_view()
    elif choice == "📅 Logbuch filtern & exportieren":
        logbuch_mit_filter_view()
    elif choice == "👨‍🏫 Schüler verwalten":
        schueler_verwalten_view()
    elif choice == "📄 Impressum":
        impressum_view()
    elif choice == "🔒 Datenschutz":
        datenschutz_view()

if __name__ == "__main__":
    main()

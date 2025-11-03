import os
import time
from typing import Optional
from datetime import datetime, date, timedelta

import streamlit as st
import sqlite3
import pandas as pd
from fpdf import FPDF
from PIL import Image
from pyzbar.pyzbar import decode

# ============= Konfiguration / Zugangsdaten =============

# Bitte diese Zugangsdaten sicher in einer .env-Datei ablegen!
STUDENT_ID   = "5186600"  # Schulnummer
SCHOOL_NAME  = "flbk-bonn"
SERVER_URL   = "ajax.webuntis.com"
UNTIS_USER   = "Vorname.Nachname"
UNTIS_PASS   = ".."  # Passwort
UNTIS_AGENT  = "WebUntis"

# Für streamlit Benutzer-Login:
USER_CREDENTIALS = {"admin": "flb23"}

DB_PATH = "students.db"

# ============= Streamlit Grundkonfiguration =============
st.set_page_config(page_title="Barcode-Scanner FLB (WebUntis)", page_icon="📷", layout="wide")


# ============= DB Setup =============
def initialize_database():
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                untis_student_id TEXT,
                klass TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                name TEXT,
                date TEXT,
                time TEXT,
                action TEXT
            )
        """)
        connection.commit()


# ============= WebUntis Hilfen =============
@st.cache_data(show_spinner=False, ttl=300)
def untis_login_cached(server, school, user, pwd, ua) -> dict:
    import webuntis
    last_err = None
    for attempt in range(3):
        try:
            s = webuntis.Session(
                server=server,
                school=school,
                username=user,
                password=pwd,
                useragent=ua or "WebUntis"
            ).login()
            s.logout()
            return {"server": server, "school": school, "username": user, "password": pwd, "useragent": ua}
        except Exception as e:
            last_err = e
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"WebUntis-Login fehlgeschlagen: {last_err}")

def untis_session(ticket: dict):
    import webuntis
    return webuntis.Session(
        server=ticket["server"],
        school=ticket["school"],
        username=ticket["username"],
        password=ticket["password"],
        useragent=ticket.get("useragent") or "WebUntis",
    ).login()

@st.cache_data(show_spinner=False, ttl=300)
def untis_list_classes(ticket: dict) -> list:
    s = untis_session(ticket)
    try:
        return sorted([k.name for k in s.klassen()])
    finally:
        try: s.logout()
        except: pass

@st.cache_data(show_spinner=False, ttl=300)
def untis_list_students(ticket: dict) -> pd.DataFrame:
    cols = ["untis_student_id", "name", "klass"]
    try:
        s = untis_session(ticket)
    except Exception:
        return pd.DataFrame(columns=cols)
    try:
        rows = []
        studs = s.students()
        for st_obj in studs:
            sid = str(getattr(st_obj, "id", "")) or None
            long_name = getattr(st_obj, "long_name", None)
            short_name = getattr(st_obj, "name", None)
            fname = getattr(st_obj, "forename", "") or ""
            sname = getattr(st_obj, "surname", "") or ""
            nm = long_name or short_name or f"{fname} {sname}".strip() or "Unbekannt"
            klasse = getattr(st_obj, "klasse", None) or getattr(st_obj, "class_name", None)
            rows.append({"untis_student_id": sid, "name": nm, "klass": klasse})
        return pd.DataFrame(rows, columns=cols)
    finally:
        try: s.logout()
        except: pass

@st.cache_data(show_spinner=False, ttl=120)
def untis_timetable_for_class(ticket: dict, class_name: str, start: date, end: date) -> pd.DataFrame:
    import pandas as pd
    s = untis_session(ticket)
    try:
        klassen = {k.name: k for k in s.klassen()}
        if class_name not in klassen:
            raise ValueError(f"Klasse '{class_name}' nicht gefunden.")
        k = klassen[class_name]
        tt = s.timetable(klasse=k, start=start, end=end)
        if hasattr(tt, "to_table"):
            return tt.to_table()
        return pd.DataFrame(tt)
    finally:
        try: s.logout()
        except: pass

# ============= Mapping- und Log-DB-Funktionen =============
def add_mapping(barcode_id: str, name: str, klass: Optional[str], untis_student_id: Optional[str]):
    barcode_id = (barcode_id or "").strip()
    if not barcode_id:
        return "Fehler: leere Barcode-ID."
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT 1 FROM students WHERE id = ?", (barcode_id,))
        if cur.fetchone():
            cur.execute(
                "UPDATE students SET name=?, klass=?, untis_student_id=? WHERE id=?",
                (name, klass, untis_student_id, barcode_id)
            )
        else:
            cur.execute(
                "INSERT INTO students (id, name, klass, untis_student_id) VALUES (?,?,?,?)",
                (barcode_id, name, klass, untis_student_id)
            )
        con.commit()
    return f"Mapping gespeichert: {name} ⇄ {barcode_id}"

def get_mapped_name(barcode_id: str):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT name FROM students WHERE id = ?", (barcode_id,))
        r = cur.fetchone()
        return r[0] if r else None

def log_scan(student_id: str, name: str, action: str):
    now = datetime.now()
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO log (student_id, name, date, time, action) VALUES (?,?,?,?,?)",
            (student_id, name, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), action)
        )
        con.commit()

def fetch_logs_by_date(date_str: str):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT student_id, name, date, time, action FROM log WHERE date=? ORDER BY time ASC",
            (date_str,)
        )
        return cur.fetchall()

def fetch_all_mappings():
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT id, name, klass, untis_student_id FROM students ORDER BY name ASC")
        return cur.fetchall()

def delete_mapping(barcode_id: str):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("DELETE FROM students WHERE id = ?", (barcode_id,))
        con.commit()

# ============= UI: Cookies & Login ============
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

# ============= PDF Export =============
def export_filtered_log_to_pdf(logs, selected_date):
    if not logs:
        st.warning("Keine Daten zum Exportieren.")
        return
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Schüler-Logbuch für {selected_date}", ln=True, align='C')
    pdf.ln(10)
    for student_id, name, d, t, action in logs:
        pdf.cell(200, 8, txt=f"{d} {t} - {name} ({student_id}) - {action}", ln=True)
    filename = f"logbuch_{selected_date}.pdf"
    pdf_bytes = pdf.output(dest="S").encode("latin-1", "ignore")
    st.download_button("📄 PDF herunterladen", data=pdf_bytes, file_name=filename, mime="application/pdf")

# ============= Barcode Scanner =============
def decode_barcodes_from_image(pil_image):
    out = []
    for r in decode(pil_image):
        try:
            data = r.data.decode("utf-8", errors="ignore")
        except Exception:
            data = str(r.data)
        out.append({"type": r.type, "data": data})
    return out

def scanner_view():
    st.subheader("🎦 Barcode scannen (Browser-Kamera)")
    mode = st.radio("Modus:", ["Anmeldung", "Abmeldung"], horizontal=True)
    st.caption("Hinweis: Die Kamera läuft im **Browser**. Für Live-Scan wäre streamlit-webrtc nötig; hier Snapshots.")
    img_file = st.camera_input("Kamera freigeben und Foto aufnehmen")
    if img_file is None:
        return
    pil_img = Image.open(img_file)
    results = decode_barcodes_from_image(pil_img)
    if not results:
        st.warning("Kein Barcode erkannt. Bitte näher ran oder besseres Licht.")
        return
    st.success(f"{len(results)} Code(s) erkannt:")
    for res in results:
        code = res["data"]
        st.write(f"- **{res['type']}**: `{code}`")
        name = get_mapped_name(code)
        if name:
            log_scan(code, name, mode)
            st.info(f"✅ {mode} registriert: **{name}** ({code}) um {datetime.now().strftime('%H:%M:%S')}")
        else:
            st.warning("Kein Mapping für diesen Barcode gefunden. Bitte im Menü 'WebUntis & Mappings' zuordnen.")

# ============= WebUntis & Mappings UI =============
def webuntis_and_mapping_view():
    st.subheader("🌐 WebUntis & Barcode-Mappings")
    colA, colB = st.columns([2,1])
    with colA:
        st.caption("Verbindungseinstellungen:")
        st.code(
            f"SERVER={SERVER_URL}\nSCHOOL={SCHOOL_NAME}\nUSER={UNTIS_USER}\nUA={UNTIS_AGENT}",
            language="bash"
        )
    with colB:
        if st.button("🔌 Mit WebUntis verbinden"):
            try:
                _ = untis_login_cached(SERVER_URL, SCHOOL_NAME, UNTIS_USER, UNTIS_PASS, UNTIS_AGENT)
                st.success("Login erfolgreich ✅")
                st.session_state["untis_ok"] = True
            except Exception as e:
                st.error(f"Login fehlgeschlagen: {e}")
                st.session_state["untis_ok"] = False
    ticket = None
    if st.session_state.get("untis_ok"):
        ticket = {
            "server": SERVER_URL,
            "school": SCHOOL_NAME,
            "username": UNTIS_USER,
            "password": UNTIS_PASS,
            "useragent": UNTIS_AGENT
        }

    st.markdown("---")
    left, right = st.columns(2)
    with left:
        st.markdown("#### 1) Klasse wählen & (falls möglich) Schüler laden")
        klass_list = []
        if ticket:
            try:
                klass_list = untis_list_classes(ticket)
            except Exception as e:
                st.warning(f"Klassen konnten nicht geladen werden: {e}")
        klass = st.selectbox("Klasse", options=(klass_list if klass_list else [""]))
        df_students = pd.DataFrame(columns=["untis_student_id", "name", "klass"])
        if ticket and klass:
            if st.button("Schülerliste abrufen"):
                try:
                    df_all = untis_list_students(ticket)
                    if len(df_all) == 0:
                        st.warning("API hat keine Schülerliste geliefert (Schüler-Login?). Du kannst unten trotzdem Mappings anlegen.")
                    else:
                        if klass != "":
                            df_students = df_all[df_all["klass"] == klass].copy()
                        else:
                            df_students = df_all
                        st.success(f"{len(df_students)} Schüler geladen.")
                except Exception as e:
                    st.error(f"Schüler konnten nicht geladen werden: {e}")
        if len(df_students) > 0:
            st.dataframe(df_students, use_container_width=True, height=300)

    with right:
        st.markdown("#### 2) Barcode einem Schüler zuordnen")
        name_input = st.text_input("Schülername (frei eingeben, falls Liste nicht verfügbar)")
        untis_id_input = st.text_input("Untis-Schüler-ID (optional)")
        barcode_input = st.text_input("Barcode-ID scannen/eingeben")
        if st.button("Mapping speichern"):
            if not barcode_input or not name_input:
                st.error("Bitte mindestens **Name** und **Barcode** angeben.")
            else:
                msg = add_mapping(barcode_input, name_input, klass if klass else None, untis_id_input or None)
                st.success(msg)

    st.markdown("---")
    st.markdown("#### 3) Bestehende Mappings")
    rows = fetch_all_mappings()
    if rows:
        df_map = pd.DataFrame(rows, columns=["Barcode-ID", "Name", "Klasse", "Untis-ID"])
        st.dataframe(df_map, use_container_width=True)
        to_del = st.text_input("Barcode-ID zum Löschen")
        if st.button("❌ Mapping löschen"):
            if to_del.strip():
                delete_mapping(to_del.strip())
                st.success("Mapping gelöscht.")
                st.rerun()
    else:
        st.info("Noch keine Mappings vorhanden.")

# ============= Logbuch & Export UI =============
def logbuch_mit_filter_view():
    st.subheader("📅 Logbuch filtern & exportieren")
    selected_date = st.date_input("Datum auswählen", value=date.today())
    if not selected_date:
        return
    date_str = selected_date.strftime("%Y-%m-%d")
    logs = fetch_logs_by_date(date_str)
    if logs:
        st.success(f"{len(logs)} Einträge gefunden für {date_str}")
        df = pd.DataFrame(logs, columns=["Barcode-ID", "Name", "Datum", "Uhrzeit", "Aktion"])
        st.dataframe(df, use_container_width=True)
        export_filtered_log_to_pdf(logs, date_str)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 CSV-Datei herunterladen", data=csv, file_name=f"logbuch_{date_str}.csv", mime="text/csv")
    else:
        st.warning("Keine Einträge für dieses Datum.")

# ============= Impressum/Datenschutz =============
def impressum_view():
    st.title("📄 Impressum")
    st.markdown("**Verantwortlich:** Bünyamin Dagdelen – Deutschland")

def datenschutz_view():
    st.title("🔒 Datenschutz")
    st.markdown("Daten werden lokal in SQLite gespeichert (Mappings & Logbuch). Keine Cloud-Übertragung.")

def main():
    initialize_database()
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        login_page()
        return
    cookies_notice()
    st.title("📷 Schülerregistrierung – WebUntis Datenquelle")
    menu = [
        "🌐 WebUntis & Mappings",
        "🎦 Barcode scannen",
        "📅 Logbuch & Export",
        "📄 Impressum",
        "🔒 Datenschutz",
    ]
    choice = st.sidebar.selectbox("Menü auswählen", menu)
    if choice == "🌐 WebUntis & Mappings":
        webuntis_and_mapping_view()
    elif choice == "🎦 Barcode scannen":
        scanner_view()
    elif choice == "📅 Logbuch & Export":
        logbuch_mit_filter_view()
    elif choice == "📄 Impressum":
        impressum_view()
    elif choice == "🔒 Datenschutz":
        datenschutz_view()

if __name__ == "__main__":
    main()

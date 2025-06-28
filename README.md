# 🎓 Barcode-Scanner für Schülerregistrierung

Dieses Projekt ist eine Streamlit-Webanwendung zur Verwaltung von Schülerdaten mittels Barcodes. Lehrkräfte können Schüler mit einem Barcode scannen, erfassen und Abmeldungen automatisch dokumentieren.

## ✨ Funktionen

- ✅ **Schüler hinzufügen**: Barcode-ID + Name werden in der Datenbank gespeichert  
- 📷 **Live-Scanner mit Webcam**: Barcodes werden automatisch erkannt  
- 🕒 **Abmeldelogs speichern**: Datum + Uhrzeit beim Scan werden aufgezeichnet  
- 🧾 **Export als PDF**: Alle Abmeldungen können als PDF heruntergeladen werden  
- 🔐 **Login-System**: Nur berechtigte Benutzer können auf die App zugreifen  
- 📚 **Impressum & Datenschutz**: DSGVO-konform umgesetzt  

## 🛠️ Technologien

- [Streamlit](https://streamlit.io/) – Web-Frontend  
- [OpenCV](https://opencv.org/) – Kamerazugriff  
- [pyzbar](https://pypi.org/project/pyzbar/) – Barcode-Erkennung  
- [SQLite3](https://www.sqlite.org/) – Datenbank für Schüler & Scans  
- [FPDF](https://pyfpdf.github.io/fpdf2/) – PDF-Export  

## 🗂️ Projektstruktur

```
Barcode-Scanner/
├── app.py             # Hauptanwendung (Streamlit)
├── students.db        # SQLite-Datenbank
├── .gitignore         # Ignorierte Dateien wie venv/
└── requirements.txt   # Python-Abhängigkeiten
```

## ⚙️ Einrichtung

```bash
# Virtuelle Umgebung (empfohlen)
python -m venv venv
source venv/bin/activate     # (Linux/macOS)
# venv\Scripts\activate      # (Windows)

# Abhängigkeiten installieren
pip install streamlit opencv-python pyzbar numpy fpdf


# Anwendung starten
streamlit run app.py

# Passwort & Benutzer
-- Passwort: flb23
-- Benutzername: admin

## 🛡️ Datenschutz

Alle personenbezogenen Daten (z. B. Schülernamen) werden lokal in einer gesicherten SQLite-Datenbank gespeichert. Der Zugriff erfolgt nur für autorisierte Benutzer.

## 📋 Lizenz

MIT License – frei nutzbar für Bildungseinrichtungen.

## 👤 Autor

**Bünyamin Dagdelen**  
📧 [dagdelenbunyamin023@gmail.com]  
📍 Deutschland


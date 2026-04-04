# Learn-AI Bewertungs-App

Eine moderne Web-Bewertungsapp für Learn-AI, gebaut mit Flask und Tailwind CSS.

## Features

✨ **Moderne Benutzeroberfläche**
- Schönes Glassmorphism-Design mit Gradienten
- Responsive Design für Mobile und Desktop
- Smooth Animations und Übergänge

⭐ **Interaktive Bewertungen**
- 6 verschiedene Bewertungskategorien
- 5-Sterne Bewertungssystem mit visuellen Effekten
- Optionale Textkommentare zu jeder Bewertung

💾 **Datenspeicherung**
- Ratings werden als Markdown-Dateien im `ratings/` Ordner gespeichert
- Zusätzlich JSON-Kopien für einfachere Verarbeitung
- Eindeutige Dateinamen mit Timestamps

� **IP-Tracking & Sperren**
- Verhindert Mehrfach-Bewertungen per IP-Adresse
- `ip-bans.txt` - Liste der bereits bewerteten IPs
- `ip-whitelist.txt` - Liste der IPs die unbegrenzt bewerten dürfen
- Automatische Umleitung zur "Schon bewertet"-Seite

�📊 **Statistiken**
- API-Endpunkt für Bewertungsstatistiken
- Automatische Durchschnittsberechnung

## Installation

### Voraussetzungen
- Python 3.7+
- pip

### Setup

1. **Installiere die Abhängigkeiten:**
```bash
pip install -r requirements.txt
```

2. **Konfiguriere die Umgebungsvariablen:**
```bash
# .env Datei bearbeiten
# SECRET_KEY = Dein Secret Key für Sessions
# FLASK_ENV = 'development' oder 'production'
```

3. **Starte die App:**
```bash
python app.py
```

Die App läuft dann auf `http://localhost:5000`

## Dateienstruktur

```
Learn-AI Rate Form/
├── app.py                          # Flask Hauptanwendung
├── requirements.txt                # Python-Abhängigkeiten
├── .env                            # Umgebungsvariablen
├── ip-bans.txt                     # IP-Ban List (automatisch gefüllt)
├── ip-whitelist.txt                # IP-Whitelist (manuell ausfüllen)
├── ratings/                        # Speicherort für Bewertungen
│   └── rating_*.md                # Markdown-Dateien mit Bewertungen
│   └── rating_*.json              # JSON-Dateien mit Bewertungen
├── templates/
│   ├── rating_form.html           # HTML Template für Bewertung
│   └── already_rated.html         # HTML Template für "Schon bewertet"
└── static/
    ├── css/
    │   └── rating.css             # CSS Styles
    └── js/
        └── rating.js              # JavaScript Logik
```

## API-Endpunkte

### GET `/`
Zeigt das Bewertungsformular an.

### POST `/api/submit-rating`
Speichert eine neue Bewertung.

**Request Body (JSON):**
```json
{
  "name": "Max Mustermann",
  "email": "max@example.de",
  "age": 15,
  "class": "10a",
  "usability": 5,
  "usability_feedback": "Sehr benutzerfreundlich",
  "functionality": 4,
  "functionality_feedback": "Funktioniert gut",
  "helpfulness": 5,
  "helpfulness_feedback": "Sehr hilfreiche Erklärungen",
  "learning": 5,
  "learning_feedback": "Hat mir sehr beim Lernen geholfen",
  "design": 5,
  "design_feedback": "Schönes Design",
  "overall": 5,
  "overall_feedback": "Großartig!",
  "general_feedback": "Weitere Kommentare..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Vielen Dank für deine Bewertung!",
  "filename": "rating_20240124_123456_Max_Mustermann.md"
}
```

### GET `/api/stats`
Gibt Bewertungsstatistiken zurück.

**Response:**
```json
{
  "total": 10,
  "averages": {
    "usability": 4.8,
    "functionality": 4.6,
    "helpfulness": 4.9,
    "learning": 4.7,
    "design": 4.5,
    "overall": 4.7
  }
}
```

## Bewertungskategorien

1. **Benutzerfreundlichkeit** - Wie einfach ist die App zu bedienen?
2. **Funktionalität** - Funktioniert alles wie erwartet?
3. **Hilfreiche Erklärungen** - Sind die Erklärungen verständlich?
4. **Lerneffektivität** - Hat dir Learn-AI beim Lernen geholfen?
5. **Grafik und Design** - Wie gefällt dir das Design?
6. **Gesamtzufriedenheit** - Wie zufrieden bist du insgesamt?

## IP-Tracking & Whitelist

### IP-Ban System
Die App speichert IP-Adressen von Schülern, die bereits bewertet haben, in `ip-bans.txt`. Wenn jemand mit der gleichen IP eine zweite Bewertung versucht, wird er auf die "Schon bewertet"-Seite weitergeleitet.

### IP-Whitelist
In `ip-whitelist.txt` können Administratoren IPs eintragen, die nicht gebannt werden sollen (z.B. Schulserver, VPNs, oder Test-IPs).

**Beispiel `ip-whitelist.txt`:**
```
# Schulserver
192.168.1.100
# VPN
10.0.0.1
```

### Wie die IP-Adressen erfasst werden
- Primär: `request.remote_addr` (direkte IP des Clients)
- Fallback: `X-Forwarded-For` Header (wenn hinter einem Proxy)

## API-Endpunkte

### GET `/`
Zeigt das Bewertungsformular an. Wenn die IP bereits bewertet hat, wird auf `/already-rated` weitergeleitet.

### GET `/already-rated`
Zeigt die Meldung, dass die IP bereits bewertet hat.

### POST `/api/submit-rating`
Speichert eine neue Bewertung.

**Anforderungen:**
- Mindestens eine Bewertung (usability, functionality, helpfulness, learning, design, oder overall) muss eingegeben werden
- Name und E-Mail sind optional
- Die IP-Adresse wird automatisch erfasst und in `ip-bans.txt` gespeichert

**Request Body (JSON):**
```json
{
  "name": "Max Mustermann",
  "email": "max@example.de",
  "age": 15,
  "class": "10a",
  "usability": 5,
  "usability_feedback": "Sehr benutzerfreundlich",
  "functionality": 4,
  "functionality_feedback": "Funktioniert gut",
  "helpfulness": 5,
  "helpfulness_feedback": "Sehr hilfreiche Erklärungen",
  "learning": 5,
  "learning_feedback": "Hat mir sehr beim Lernen geholfen",
  "design": 5,
  "design_feedback": "Schönes Design",
  "overall": 5,
  "overall_feedback": "Großartig!",
  "general_feedback": "Weitere Kommentare..."
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Vielen Dank für deine Bewertung!",
  "filename": "rating_20240124_123456_Max_Mustermann.md"
}
```

**Fehler (403):**
```json
{
  "success": false,
  "message": "Du hast bereits eine Bewertung abgegeben"
}
```

**Fehler (400):**
```json
{
  "success": false,
  "message": "Bitte gib mindestens eine Bewertung ab"
}
```

### GET `/api/stats`
Gibt Bewertungsstatistiken zurück.

**Response:**
```json
{
  "total": 10,
  "averages": {
    "usability": 4.8,
    "functionality": 4.6,
    "helpfulness": 4.9,
    "learning": 4.7,
    "design": 4.5,
    "overall": 4.7
  }
}
```

"""
Learn-AI Rating App
Bewertungsformular für die Learn-AI Plattform
"""
import os
import json
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")

# Stelle sicher, dass der ratings Ordner existiert
RATINGS_DIR = os.path.join(os.path.dirname(__file__), 'ratings')
if not os.path.exists(RATINGS_DIR):
    os.makedirs(RATINGS_DIR)

# IP Ban und Whitelist Dateien
IP_BAN_FILE = os.path.join(os.path.dirname(__file__), 'ip-bans.txt')
IP_WHITELIST_FILE = os.path.join(os.path.dirname(__file__), 'ip-whitelist.txt')

# Stelle sicher, dass die IP-Listen Dateien existieren
if not os.path.exists(IP_BAN_FILE):
    with open(IP_BAN_FILE, 'w', encoding='utf-8') as f:
        f.write("# Learn-AI Rating App - IP Ban List\n")
        f.write("# Eine IP pro Zeile\n")

if not os.path.exists(IP_WHITELIST_FILE):
    with open(IP_WHITELIST_FILE, 'w', encoding='utf-8') as f:
        f.write("# Learn-AI Rating App - IP Whitelist\n")
        f.write("# IPs in dieser Liste können unbegrenzt bewerten\n")
        f.write("# Eine IP pro Zeile\n")


def get_client_ip():
    """
    Holt die IP-Adresse des Clients
    """
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr


def is_ip_whitelisted(ip):
    """
    Prüft ob eine IP auf der Whitelist steht
    """
    try:
        with open(IP_WHITELIST_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    if line == ip:
                        return True
    except Exception as e:
        print(f"Fehler beim Lesen der IP Whitelist: {str(e)}")
    return False


def is_ip_banned(ip):
    """
    Prüft ob eine IP bereits bewertet hat
    """
    if is_ip_whitelisted(ip):
        return False
    
    try:
        with open(IP_BAN_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    if line == ip:
                        return True
    except Exception as e:
        print(f"Fehler beim Lesen der IP Ban List: {str(e)}")
    return False


def add_ip_to_ban_list(ip):
    """
    Fügt eine IP zur Ban List hinzu
    """
    if not is_ip_whitelisted(ip):
        try:
            with open(IP_BAN_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{ip}\n")
        except Exception as e:
            print(f"Fehler beim Hinzufügen zur IP Ban List: {str(e)}")


def send_ntfy_notification(rating_data):
    """
    Sendet eine Benachrichtigung an den ntfy-Kanal Learn-AI-Ratings
    """
    name = rating_data.get('name', 'Anonym') or 'Anonym'
    lines = [
        f"Neue Bewertung von {name}",
        "",
        f"Schulaufgaben: {rating_data.get('schulaufgaben', '-')}",
        f"Funktionen sinnvoll: {rating_data.get('funktionen_sinnvoll', '-')}",
        f"Funktionen funktioniert: {rating_data.get('funktionen_funktioniert', '-')}",
        f"Keine Lösungen gut: {rating_data.get('keine_loesungen', '-')}",
        f"Ladezeit: {rating_data.get('ladezeit', '-')}",
    ]
    verbesserung = rating_data.get('verbesserungsvorschlaege', '').strip()
    was_gefallen = rating_data.get('was_gefallen', '').strip()
    hinweise = rating_data.get('sonstige_hinweise', '').strip()
    if verbesserung:
        lines.append(f"Verbesserungen: {verbesserung}")
    if was_gefallen:
        lines.append(f"Gefallen: {was_gefallen}")
    if hinweise:
        lines.append(f"Hinweise: {hinweise}")

    message = "\n".join(lines)
    try:
        subprocess.run(
            ['curl', '-s', '-d', message, 'https://ntfy.malte-hinrichs.de/Learn-AI-Ratings'],
            capture_output=True,
            timeout=5
        )
    except Exception as e:
        print(f"Fehler beim Senden der ntfy-Benachrichtigung: {str(e)}")


def save_rating_to_markdown(rating_data):
    """
    Speichert eine Bewertung als Markdown-Datei

    Args:
        rating_data: Dictionary mit Bewertungsdaten

    Returns:
        filename: Name der gespeicherten Datei
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"rating_{timestamp}_{rating_data.get('name', 'unknown').replace(' ', '_')}.md"
    filepath = os.path.join(RATINGS_DIR, filename)

    markdown_content = f"""# Learn-AI Bewertung

**Datum:** {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}

## Benutzerinformationen

- **Name:** {rating_data.get('name', 'Nicht angegeben')}
- **E-Mail:** {rating_data.get('email', 'Nicht angegeben')}

## Fragen

| Frage | Antwort |
|-------|---------|
| Würden Sie Learn-AI für Schulaufgaben benutzen? | {rating_data.get('schulaufgaben', '-')} |
| Fanden Sie die Funktionen sinnvoll? | {rating_data.get('funktionen_sinnvoll', '-')} |
| Haben alle Funktionen richtig funktioniert? | {rating_data.get('funktionen_funktioniert', '-')} |
| Finden Sie es gut, dass Learn-AI nicht die Lösungen sagt? | {rating_data.get('keine_loesungen', '-')} |
| Hat Learn-AI schnell geladen? | {rating_data.get('ladezeit', '-')} |

## Offene Fragen

### Verbesserungsvorschläge
{rating_data.get('verbesserungsvorschlaege', 'Keine Angabe') or 'Keine Angabe'}

### Was hat besonders gut gefallen?
{rating_data.get('was_gefallen', 'Keine Angabe') or 'Keine Angabe'}

### Sonstige Hinweise
{rating_data.get('sonstige_hinweise', 'Keine Angabe') or 'Keine Angabe'}

---
*Diese Bewertung wurde automatisch generiert und gespeichert.*
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    return filename


@app.route('/')
def index():
    """Zeigt das Rating-Formular"""
    client_ip = get_client_ip()
    
    # Prüfe ob IP bereits bewertet hat
    if is_ip_banned(client_ip):
        return redirect(url_for('already_rated'))
    
    return render_template('rating_form.html')


@app.route('/api/submit-rating', methods=['POST'])
def submit_rating():
    """
    API-Endpunkt zum Speichern einer Bewertung
    Erwartet JSON-Daten mit Bewertungsinformationen
    """
    try:
        client_ip = get_client_ip()
        
        # Prüfe ob IP bereits bewertet hat
        if is_ip_banned(client_ip):
            return jsonify({'success': False, 'message': 'Du hast bereits eine Bewertung abgegeben'}), 403
        
        data = request.get_json()

        # Validierung: alle Ja/Nein/Teils-Fragen müssen beantwortet sein
        required_fields = ['schulaufgaben', 'funktionen_sinnvoll', 'funktionen_funktioniert', 'keine_loesungen', 'ladezeit']
        valid_answers = {'ja', 'nein', 'teils/teils'}
        for field in required_fields:
            if not data.get(field) or data.get(field) not in valid_answers:
                return jsonify({'success': False, 'message': 'Bitte beantworte alle Fragen'}), 400

        # Speichere die Bewertung als Markdown
        filename = save_rating_to_markdown(data)

        # Sende ntfy-Benachrichtigung
        send_ntfy_notification(data)
        
        # Speichere auch eine JSON-Kopie für einfachere Verarbeitung
        json_filename = filename.replace('.md', '.json')
        json_filepath = os.path.join(RATINGS_DIR, json_filename)
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Füge IP zur Ban List hinzu
        add_ip_to_ban_list(client_ip)
        
        return jsonify({
            'success': True,
            'message': 'Vielen Dank für deine Bewertung!',
            'filename': filename
        }), 201
    
    except Exception as e:
        print(f"Fehler beim Speichern der Bewertung: {str(e)}")
        return jsonify({'success': False, 'message': f'Fehler: {str(e)}'}), 500


@app.route('/already-rated')
def already_rated():
    """Zeigt die Seite für bereits bewertete IPs"""
    client_ip = get_client_ip()
    
    # Falls IP nicht gebannt ist, leite zurück zur Bewertungsseite
    if not is_ip_banned(client_ip):
        return redirect(url_for('index'))
    
    return render_template('already_rated.html')


@app.route('/api/stats')
def get_stats():
    """
    API-Endpunkt für Bewertungsstatistiken
    """
    try:
        ratings = []
        
        # Lese alle JSON-Dateien
        for filename in os.listdir(RATINGS_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(RATINGS_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    rating = json.load(f)
                    ratings.append(rating)
        
        # Berechne Durchschnittswerte
        if not ratings:
            return jsonify({
                'total': 0,
                'averages': {}
            }), 200
        
        questions = ['schulaufgaben', 'funktionen_sinnvoll', 'funktionen_funktioniert', 'keine_loesungen', 'ladezeit']
        counts = {}

        for q in questions:
            counts[q] = {'ja': 0, 'teils/teils': 0, 'nein': 0}
            for r in ratings:
                answer = r.get(q)
                if answer in counts[q]:
                    counts[q][answer] += 1

        return jsonify({
            'total': len(ratings),
            'counts': counts
        }), 200
    
    except Exception as e:
        print(f"Fehler beim Laden der Statistiken: {str(e)}")
        return jsonify({'success': False, 'message': f'Fehler: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)

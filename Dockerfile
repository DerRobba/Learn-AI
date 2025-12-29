# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create necessary directories for storage
RUN mkdir -p sheets uploads

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV BASE_URL='https://openrouter.ai/api/v1'
ENV MODEL='amazon/nova-pro-v1'
ENV SYSTEM_PROMPT='Du bist Learn-AI, dein Name ist Learn-AI, du bist das KI-Modell DerRobba/Learn-AI, ein hochintelligenter Lernassisten für Schüler. Du darft niemals eine Frage in Mathe, etc. einfach beantworten oder einfach einen Text schreiben, du musst den Schüler "guiden", das heißt ihm sagen wie er es löst aber   NIE die Lösung sagen. Das Ergebnis ist für eine TTS-Engine, also nutze keine Sternchen(*), Emojis, Hashtacks(#) etc.. Wenn dir gesagt wird, du sollst ein Arbeitsblatt erstellen, dann fange deine Antwort mit "createmd:" an. Dann kommt in Markdown das Arbeitsblatt, also was der Schüler wollte, Bsp. "Erstelle mir ein Mathe Arbeitsblatt, 1. Klasse" -> "createmd: # Mathearbeitsblatt     **Aufgabe 1**      1+1...". Nutze Deine gelernten Markdown-Regeln, heißt Hashtag, Leerzeichen und dann den Titel, mehr als zwei Zeichen für Zeilenumbruch etc.'
ENV VISION_SYSTEM_PROMPT='Du bist ein hilfreicher Assistent, der Bilder analysiert und beschreibt. Antworte auf Deutsch. Nutze keine Sonderzeichen außer :, ., ,, !, und ?. Das Ergebnis ist für '
ENV IP_BAN_LIST='188.192.112.169'

# Run the application using flask run
CMD ["flask", "run", "--host=0.0.0.0"]

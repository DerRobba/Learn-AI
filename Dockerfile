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
ENV SYSTEM_PROMPT='Du bist Learn-AI, ein hochintelligenter Lernassistent für Schüler. Du darfst niemals eine Frage in Mathe etc. einfach beantworten, sondern musst den Schüler "guiden". Das Ergebnis ist für eine TTS-Engine, also nutze keine Emojis oder Hashtags (#) im Fließtext. Wenn du ein Arbeitsblatt erstellen sollst, nutze AUSSCHLIESSLICH das Format: <action>{"type": "worksheet_creation", "content": "MARKDOWN_INHALT"}</action> am Ende deiner Nachricht.'
ENV VISION_SYSTEM_PROMPT='Du bist ein hilfreicher Assistent, der Bilder analysiert und beschreibt. Antworte auf Deutsch. Nutze keine Sonderzeichen außer :, ., ,, !, und ?. Das Ergebnis ist für '
ENV IP_BAN_LIST='188.192.112.169'

# Run the application using flask run
CMD ["flask", "run", "--host=0.0.0.0"]

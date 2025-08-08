document.addEventListener('DOMContentLoaded', function() {
    const recordButton = document.getElementById('record-button');
    const chatHistory = document.getElementById('chat-history');
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        alert("Spracherkennung wird in deinem Browser nicht unterstützt. Bitte verwende Chrome, Edge oder Safari.");
        return;
    }
    
    const recognition = new SpeechRecognition();
    recognition.lang = 'de-DE';
    recognition.continuous = false;
    recognition.interimResults = false;
    
    let isRecording = false;
    
    // Überwache manuelle Scroll-Events
    let userScrolled = false;
    chatHistory.addEventListener('scroll', function() {
        const isAtBottom = chatHistory.scrollHeight - chatHistory.scrollTop <= chatHistory.clientHeight + 5;
        userScrolled = !isAtBottom;
    });
    
    // Funktion zum Scrollen zum Ende
    function scrollToBottom() {
        if (!userScrolled) {
            chatHistory.scrollTo({
                top: chatHistory.scrollHeight,
                behavior: 'smooth'
            });
        }
    }
    
    recordButton.addEventListener('click', () => {
        if (isRecording) {
            recognition.stop();
            isRecording = false;
            updateRecordButton(false);
        } else {
            recognition.start();
            isRecording = true;
            updateRecordButton(true);
        }
    });
    
    function updateRecordButton(recording) {
        if (recording) {
            recordButton.innerHTML = '<i class="fa-microphone"></i><span>Aufnahme stoppen</span>';
            recordButton.classList.add('recording');
        } else {
            recordButton.innerHTML = '<i class="fa-microphone"></i><span>Aufnahme starten</span>';
            recordButton.classList.remove('recording');
        }
    }
    
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        addUserMessage(transcript);
        sendToServer(transcript);
    };
    
    recognition.onerror = (event) => {
        console.error('Speech recognition error', event.error);
        isRecording = false;
        updateRecordButton(false);
        
        let errorMessage = "Es gab einen Fehler bei der Spracherkennung. ";
        if (event.error === 'no-speech') {
            errorMessage += "Keine Sprache erkannt. Bitte versuche es erneut.";
        } else if (event.error === 'audio-capture') {
            errorMessage += "Mikrofon konnte nicht gefunden werden. Bitte überprüfe deine Einstellungen.";
        } else if (event.error === 'not-allowed') {
            errorMessage += "Zugriff auf das Mikrofon wurde verweigert. Bitte erlaube den Zugriff.";
        } else {
            errorMessage += "Bitte versuche es erneut.";
        }
        
        addBotMessage(errorMessage);
    };
    
    recognition.onend = () => {
        isRecording = false;
        updateRecordButton(false);
    };
    
    function sendToServer(text) {
        // Zeige ein "Denk"-Indikator an
        const thinkingIndicator = document.createElement('div');
        thinkingIndicator.className = 'message bot-message';
        thinkingIndicator.innerHTML = `
            <div class="bot-avatar">
                <i class="fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="bot-name">KI-Assistent</span>
                    <span class="message-time">${formatTime(new Date())}</span>
                </div>
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        chatHistory.appendChild(thinkingIndicator);
        
        // Scrollen zum Ende
        scrollToBottom();
        
        fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question: text })
        })
        .then(response => response.json())
        .then(data => {
            // Entferne den "Denk"-Indikator
            chatHistory.removeChild(thinkingIndicator);
            
            // Füge die tatsächliche Antwort hinzu
            addBotMessage(data.answer);
            speak(data.answer);
        })
        .catch(error => {
            console.error('Error sending request:', error);
            chatHistory.removeChild(thinkingIndicator);
            addBotMessage("Es gab ein Problem bei der Verarbeitung deiner Anfrage. Bitte versuche es später noch einmal.");
        });
    }
    
    function addUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message user-message';
        messageElement.innerHTML = `
            <div class="bot-avatar user-avatar">
                <i class="fa-user"></i>
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="bot-name user-name">Du</span>
                    <span class="message-time">${formatTime(new Date())}</span>
                </div>
                <p>${message}</p>
            </div>
        `;
        chatHistory.appendChild(messageElement);
        
        // Scrollen zum Ende nach Hinzufügen der Nachricht
        setTimeout(scrollToBottom, 100);
    }
    
    function addBotMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message bot-message';
        messageElement.innerHTML = `
            <div class="bot-avatar">
                <i class="fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="bot-name">KI-Assistent</span>
                    <span class="message-time">${formatTime(new Date())}</span>
                </div>
                <p>${message}</p>
            </div>
        `;
        chatHistory.appendChild(messageElement);
        
        // Scrollen zum Ende nach Hinzufügen der Nachricht
        setTimeout(scrollToBottom, 100);
    }
    
    function speak(text) {
        speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'de-DE';
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        speechSynthesis.speak(utterance);
    }
    
    function formatTime(date) {
        return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    }
});

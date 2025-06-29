const recordButton = document.getElementById('record-button');
const chatHistory = document.getElementById('chat-history');

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = new SpeechRecognition();
recognition.lang = 'de-DE';

let isRecording = false;

recordButton.addEventListener('click', () => {
    if (isRecording) {
        recognition.stop();
        isRecording = false;
        recordButton.textContent = 'Aufnahme starten';
        recordButton.classList.remove('recording');
    } else {
        recognition.start();
        isRecording = true;
        recordButton.textContent = 'Aufnahme stoppen';
        recordButton.classList.add('recording');
    }
});

recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    addUserMessage(transcript);
    sendToServer(transcript);
};

function sendToServer(text) {
    fetch('/ask', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ question: text })
    })
    .then(response => response.json())
    .then(data => {
        addBotMessage(data.answer);
        speak(data.answer);
    });
}

function speak(text) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'de-DE';
    speechSynthesis.speak(utterance);
}

function addUserMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.textContent = `Du: ${message}`;
    chatHistory.appendChild(messageElement);
}

function addBotMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.textContent = `Assistent: ${message}`;
    chatHistory.appendChild(messageElement);
}

/**
 * Learn-AI Rating App JavaScript
 */

// Answer Button Selection
document.querySelectorAll('.answer-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const field = btn.dataset.field;
        const value = btn.dataset.value;

        // Deselect all buttons for this field
        document.querySelectorAll(`.answer-btn[data-field="${field}"]`).forEach(b => {
            b.classList.remove('selected-ja', 'selected-teils', 'selected-nein');
        });

        // Select this button
        btn.classList.add(`selected-${value === 'teils/teils' ? 'teils' : value}`);

        // Set hidden input value
        document.getElementById(field).value = value;
    });
});

// Form Submission
document.getElementById('ratingForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(document.getElementById('ratingForm'));
    const data = Object.fromEntries(formData);

    // Validate all yes/no/partly questions are answered
    const questions = {
        'schulaufgaben': 'Würden Sie Learn-AI für Schulaufgaben benutzen?',
        'funktionen_sinnvoll': 'Fanden Sie die Funktionen sinnvoll?',
        'funktionen_funktioniert': 'Haben alle Funktionen richtig funktioniert?',
        'keine_loesungen': 'Finden Sie es gut, dass Learn-AI nicht die Lösungen sagt?',
        'ladezeit': 'Hat Learn-AI schnell geladen?'
    };

    for (const [field, label] of Object.entries(questions)) {
        if (!data[field]) {
            showError(`Bitte beantworte: "${label}"`);
            return;
        }
    }

    // Disable submit button
    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="material-symbols-outlined">hourglass_empty</span><span>Wird gespeichert...</span>';

    try {
        const response = await fetch('/api/submit-rating', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
            showSuccess();
        } else {
            showError(result.message || 'Ein Fehler ist aufgetreten.');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span class="material-symbols-outlined">send</span><span>Bewertung absenden</span>';
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Ein Fehler ist aufgetreten. Bitte versuche es später erneut.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="material-symbols-outlined">send</span><span>Bewertung absenden</span>';
    }
});

function showSuccess() {
    document.getElementById('successMessage').classList.remove('hidden');
}

function showError(message) {
    document.getElementById('errorText').textContent = message;
    document.getElementById('errorMessage').classList.remove('hidden');
}

document.addEventListener('DOMContentLoaded', () => {

    // --- DOM Elements ---
    // Add Vocab
    const vocabTextInput = document.getElementById('vocab-text-input');
    const addTextVocabBtn = document.getElementById('add-text-vocab-btn');

    // Quiz
    const vocabCount = document.getElementById('vocab-count');
    const vocabStartScreen = document.getElementById('vocab-start-screen');
    const vocabStartBtn = document.getElementById('vocab-start-btn');
    const vocabQuizScreen = document.getElementById('vocab-quiz-screen');
    const vocabWord = document.getElementById('vocab-word');
    const vocabInput = document.getElementById('vocab-input');
    const vocabCheckBtn = document.getElementById('vocab-check-btn');
    const vocabFeedback = document.getElementById('vocab-feedback');
    const vocabResultsScreen = document.getElementById('vocab-results-screen');
    const vocabScore = document.getElementById('vocab-score');
    const vocabRestartBtn = document.getElementById('vocab-restart-btn');

    // Display Current Vocab
    const currentVocabList = document.getElementById('current-vocab-list');
    const emptyVocabMessage = document.getElementById('empty-vocab-message');

    // Manage Lists
    const listNameInput = document.getElementById('list-name-input');
    const saveListBtn = document.getElementById('save-list-btn');
    const savedListsSelect = document.getElementById('saved-lists-select');
    const loadListBtn = document.getElementById('load-list-btn');
    const deleteListBtn = document.getElementById('delete-list-btn');

    // --- State ---
    let vocabulary = [];
    let currentWordIndex = 0;
    let score = 0;
    let shuffledVocab = [];
    let vocabularyLists = {}; // Stores named lists

    // --- API Communication ---
    async function fetchVocabulary() {
        try {
            const response = await fetch('/get-vocabulary');
            const data = await response.json();
            vocabulary = data.vocabulary || [];
            updateVocabCount();
            fetchVocabularyLists(); // Also fetch list names
        } catch (error) {
            console.error('Error fetching vocabulary:', error);
        }
    }

    async function fetchVocabularyLists() {
        try {
            const response = await fetch('/get-vocabulary-lists');
            const data = await response.json();
            vocabularyLists = data.lists || {};
            updateSavedListsSelect();
        } catch (error) {
            console.error('Error fetching vocabulary lists:', error);
        }
    }

    function updateVocabCount() {
        vocabCount.textContent = `${vocabulary.length} Vokabeln geladen.`;
        if (vocabulary.length > 0) {
            vocabStartBtn.disabled = false;
            saveListBtn.disabled = false; // Enable save if there's vocab
        } else {
            vocabStartBtn.disabled = true;
            saveListBtn.disabled = true;
        }
        displayCurrentVocabulary();
    }

    function displayCurrentVocabulary() {
        currentVocabList.innerHTML = '';
        if (vocabulary.length === 0) {
            emptyVocabMessage.classList.remove('hidden');
            return;
        }
        emptyVocabMessage.classList.add('hidden');

        vocabulary.forEach(word => {
            const listItem = document.createElement('li');
            listItem.className = 'flex items-center justify-between bg-gray-50 p-3 rounded-lg';
            listItem.innerHTML = `
                <span>${word.german}: ${word.english}</span>
                <button class="delete-vocab-btn text-red-500 hover:text-red-700 material-symbols-outlined">delete</button>
            `;
            const deleteButton = listItem.querySelector('.delete-vocab-btn');
            deleteButton.addEventListener('click', () => deleteVocabulary(word));
            currentVocabList.appendChild(listItem);
        });
    }

    async function deleteVocabulary(wordToDelete) {
        try {
            const response = await fetch('/delete-vocabulary', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ word: wordToDelete })
            });
            const data = await response.json();
            if (data.success) {
                fetchVocabulary();
            } else {
                alert(data.message || 'Fehler beim Löschen der Vokabel.');
            }
        } catch (error) {
            console.error('Error deleting vocabulary:', error);
        }
    }

    async function addVocabulary(vocabData) {
        try {
            const response = await fetch('/add-vocabulary', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ vocabulary: vocabData })
            });
            const data = await response.json();
            if (data.success) {
                fetchVocabulary();
            } else {
                alert(data.message || 'Fehler beim Hinzufügen der Vokabeln.');
            }
        } catch (error) {
            console.error('Error adding vocabulary:', error);
        }
    }

    async function saveCurrentList() {
        const listName = listNameInput.value.trim();
        if (!listName) {
            alert('Bitte gib einen Namen für die Liste ein.');
            return;
        }
        try {
            const response = await fetch('/save-vocabulary-list', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name: listName, vocabulary: vocabulary })
            });
            const data = await response.json();
            if (data.success) {
                listNameInput.value = '';
                fetchVocabularyLists();
            } else {
                alert(data.message || 'Fehler beim Speichern der Liste.');
            }
        } catch (error) {
            console.error('Error saving list:', error);
        }
    }

    async function loadSelectedList() {
        const listName = savedListsSelect.value;
        if (!listName) return;
        try {
            const response = await fetch('/load-vocabulary-list', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name: listName })
            });
            const data = await response.json();
            if (data.success) {
                fetchVocabulary(); // This will update current vocab and UI
            } else {
                alert(data.message || 'Fehler beim Laden der Liste.');
            }
        } catch (error) {
            console.error('Error loading list:', error);
        }
    }

    async function deleteSelectedList() {
        const listName = savedListsSelect.value;
        if (!listName) return;
        if (!confirm(`Möchtest du die Liste \'${listName}\' wirklich löschen?`)) return;
        try {
            const response = await fetch('/delete-vocabulary-list', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name: listName })
            });
            const data = await response.json();
            if (data.success) {
                fetchVocabularyLists();
            } else {
                alert(data.message || 'Fehler beim Löschen der Liste.');
            }
        } catch (error) {
            console.error('Error deleting list:', error);
        }
    }

    function updateSavedListsSelect() {
        savedListsSelect.innerHTML = '<option value="">-- Liste auswählen --</option>';
        const listNames = Object.keys(vocabularyLists);
        listNames.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            savedListsSelect.appendChild(option);
        });

        if (listNames.length > 0) {
            savedListsSelect.disabled = false;
        } else {
            savedListsSelect.disabled = true;
        }
        // Disable load/delete buttons until a list is selected
        loadListBtn.disabled = true;
        deleteListBtn.disabled = true;
    }

    // --- Event Handlers ---

    // Add from text
    addTextVocabBtn.addEventListener('click', () => {
        const text = vocabTextInput.value.trim();
        if (!text) return;

        const pairs = text.split(',').map(p => p.trim());
        const newVocab = pairs.map(p => {
            const [german, english] = p.split(':').map(w => w.trim());
            if (german && english) {
                return { german, english };
            }
            return null;
        }).filter(Boolean);

        if (newVocab.length > 0) {
            addVocabulary(newVocab);
            vocabTextInput.value = '';
        }
    });

    // Quiz Logic Event Listeners
    vocabStartBtn.addEventListener('click', startQuiz);
    vocabCheckBtn.addEventListener('click', checkAnswer);
    vocabRestartBtn.addEventListener('click', startQuiz);
    vocabInput.addEventListener('keyup', handleEnter);

    // List Management Event Listeners
    listNameInput.addEventListener('input', () => {
        saveListBtn.disabled = listNameInput.value.trim().length === 0 || vocabulary.length === 0;
    });
    saveListBtn.addEventListener('click', saveCurrentList);

    savedListsSelect.addEventListener('change', () => {
        const selectedList = savedListsSelect.value;
        loadListBtn.disabled = !selectedList;
        deleteListBtn.disabled = !selectedList;
    });
    loadListBtn.addEventListener('click', loadSelectedList);
    deleteListBtn.addEventListener('click', deleteSelectedList);

    // --- Initial Load ---
    fetchVocabulary();
});
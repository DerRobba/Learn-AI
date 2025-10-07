document.addEventListener('DOMContentLoaded', function() {
    const recordButton = document.getElementById('record-button');
    const chatHistory = document.getElementById('chat-history');
    const imageUploadButton = document.getElementById('image-upload-button');
    const imageInput = document.getElementById('image-input');
    const imagePreview = document.getElementById('image-preview');
    const previewImage = document.getElementById('preview-image');
    const analyzeButton = document.getElementById('analyze-image');
    const cacheButton = document.getElementById('cache-image');
    const removeButton = document.getElementById('remove-image');
    const clearCacheButton = document.getElementById('clear-cache-button');
    const cachedImageIndicator = document.getElementById('cached-image-indicator');
    const newChatBtn = document.getElementById('new-chat-btn');
    const chatSessions = document.getElementById('chat-sessions');
    const chatInput = document.getElementById('chat-input');

    // Mobile Navigation
    const sidebar = document.getElementById('sidebar');
    const sidebarMenuBtn = document.getElementById('sidebar-menu-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar');
    const mobileOverlay = document.getElementById('mobile-overlay');

    // Sidebar Tabs
    const chatsTabBtn = document.getElementById('chats-tab-btn');
    const assignmentsTabBtn = document.getElementById('assignments-tab-btn');
    const chatSessionsContainer = document.getElementById('chat-sessions-container');
    const assignmentListContainer = document.getElementById('assignment-list-container');

    let uploadedImage = null;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (chatInput) {
        chatInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                const message = chatInput.value.trim();
                if (message) {
                    addUserMessage(message);
                    sendToServer(message);
                    chatInput.value = '';
                    chatInput.style.height = 'auto';
                }
            }
        });

        chatInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }

    if (!SpeechRecognition) {
        console.log("Spracherkennung wird in diesem Browser nicht unterstützt.");
    } else {
        const recognition = new SpeechRecognition();
        recognition.lang = 'de-DE';
        recognition.continuous = false;
        recognition.interimResults = false;

        let isRecording = false;

        // Speech Recognition Event Handlers
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
                recordButton.innerHTML = '<span class="material-symbols-outlined">stop</span>';
                recordButton.classList.remove('bg-purple-600', 'hover:bg-purple-700');
                recordButton.classList.add('bg-red-600', 'hover:bg-red-700');
            } else {
                recordButton.innerHTML = '<span class="material-symbols-outlined">mic</span>';
                recordButton.classList.remove('bg-red-600', 'hover:bg-red-700');
                recordButton.classList.add('bg-purple-600', 'hover:bg-purple-700');
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
    }

    // Mobile Navigation Functions
    if (sidebarMenuBtn) {
        sidebarMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleSidebar();
        });
    }

    if (closeSidebarBtn) {
        closeSidebarBtn.addEventListener('click', toggleSidebar);
    }

    function toggleSidebar() {
        const isOpen = sidebar.classList.contains('translate-x-0');

        if (isOpen) {
            sidebar.classList.remove('translate-x-0');
            sidebar.classList.add('-translate-x-full');
            sidebarMenuBtn.classList.remove('active');
            mobileOverlay.classList.add('hidden');
        } else {
            sidebar.classList.remove('-translate-x-full');
            sidebar.classList.add('translate-x-0');
            sidebarMenuBtn.classList.add('active');
            mobileOverlay.classList.remove('hidden');
        }
    }

    // Close sidebars when clicking overlay
    mobileOverlay.addEventListener('click', toggleSidebar);

    // Close sidebars on window resize to desktop
    window.addEventListener('resize', () => {
        if (window.innerWidth >= 768) {
            toggleSidebar();
        }
    });

    if (chatsTabBtn) {
        chatsTabBtn.addEventListener('click', () => {
            chatsTabBtn.classList.add('bg-purple-100', 'text-purple-700');
            chatsTabBtn.classList.remove('text-gray-500', 'hover:bg-gray-100');

            assignmentsTabBtn.classList.add('text-gray-500', 'hover:bg-gray-100');
            assignmentsTabBtn.classList.remove('bg-purple-100', 'text-purple-700');

            chatSessionsContainer.classList.remove('hidden');
            assignmentListContainer.classList.add('hidden');
        });
    }

    if (assignmentsTabBtn) {
        assignmentsTabBtn.addEventListener('click', () => {
            assignmentsTabBtn.classList.add('bg-purple-100', 'text-purple-700');
            assignmentsTabBtn.classList.remove('text-gray-500', 'hover:bg-gray-100');

            chatsTabBtn.classList.add('text-gray-500', 'hover:bg-gray-100');
            chatsTabBtn.classList.remove('bg-purple-100', 'text-purple-700');

            assignmentListContainer.classList.remove('hidden');
            chatSessionsContainer.classList.add('hidden');
        });
    }

    // Scroll management
    let userScrolled = false;
    if (chatHistory) {
        chatHistory.addEventListener('scroll', function() {
            const isAtBottom = chatHistory.scrollHeight - chatHistory.scrollTop <= chatHistory.clientHeight + 5;
            userScrolled = !isAtBottom;
        });
    }

    function scrollToBottom() {
        if (!userScrolled && chatHistory) {
            chatHistory.scrollTo({
                top: chatHistory.scrollHeight,
                behavior: 'smooth'
            });
        }
    }

    function sendToServer(text) {
        const thinkingIndicator = document.createElement('div');
        thinkingIndicator.className = 'flex space-x-3 p-4 bg-gradient-to-r from-gray-50 to-gray-100 rounded-2xl';
        thinkingIndicator.innerHTML = `
            <div class="w-10 h-10 bg-gradient-to-r from-purple-600 to-pink-500 rounded-full flex items-center justify-center flex-shrink-0">
                <span class="material-symbols-outlined text-white text-lg">adb</span>
            </div>
            <div class="flex-1">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-sm font-semibold text-purple-700">KI-Assistent</span>
                    <span class="text-xs text-gray-500">${formatTime(new Date())}</span>
                </div>
                <div class="flex space-x-1">
                    <div class="w-2 h-2 bg-purple-500 rounded-full animate-bounce"></div>
                    <div class="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                    <div class="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                </div>
            </div>
        `;
        chatHistory.appendChild(thinkingIndicator);
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
            chatHistory.removeChild(thinkingIndicator);
            addBotMessage(data.answer);
            speak(data.answer);
        })
        .catch(error => {
            console.error('Error sending request:', error);
            chatHistory.removeChild(thinkingIndicator);
            addBotMessage("Es gab ein Problem bei der Verarbeitung deiner Anfrage. Bitte versuche es später noch einmal.");
        });
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

    function addUserMessage(message, timestamp = null) {
        const messageElement = document.createElement('div');
        messageElement.className = 'flex space-x-3 justify-end chat-message';
        const time = timestamp ? new Date(timestamp) : new Date();
        messageElement.innerHTML = `
            <div class="flex flex-col items-end max-w-xs md:max-w-md">
                <div class="bg-gradient-to-r from-purple-600 to-pink-500 text-white p-3 rounded-2xl rounded-br-sm">
                    <p class="text-sm">${message}</p>
                </div>
                <span class="text-xs text-gray-500 mt-1">Du • ${formatTime(time)}</span>
            </div>
            <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-green-500 rounded-full flex items-center justify-center flex-shrink-0">
                <span class="material-symbols-outlined text-white text-sm">person</span>
            </div>
        `;
        chatHistory.appendChild(messageElement);
        setTimeout(scrollToBottom, 100);
    }

    function addBotMessage(message, timestamp = null) {
        const messageElement = document.createElement('div');
        messageElement.className = 'flex space-x-3 p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl chat-message';
        const time = timestamp ? new Date(timestamp) : new Date();
        messageElement.innerHTML = `
            <div class="w-10 h-10 bg-gradient-to-r from-purple-600 to-pink-500 rounded-full flex items-center justify-center flex-shrink-0">
                <span class="material-symbols-outlined text-white text-lg">adb</span>
            </div>
            <div class="flex-1">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-sm font-semibold text-purple-700">KI-Assistent</span>
                    <span class="text-xs text-gray-500">${formatTime(time)}</span>
                </div>
                <p class="text-gray-700 text-sm leading-relaxed">${message}</p>
            </div>
        `;
        chatHistory.appendChild(messageElement);
        setTimeout(scrollToBottom, 100);
    }

    // Image upload functionality
    if (imageUploadButton) {
        imageUploadButton.addEventListener('click', () => {
            imageInput.click();
        });
    }

    if (imageInput) {
        imageInput.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file && file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    previewImage.src = e.target.result;
                    uploadedImage = file;
                    imagePreview.classList.remove('hidden');
                };
                reader.readAsDataURL(file);
            }
        });
    }

    if (analyzeButton) {
        analyzeButton.addEventListener('click', () => {
            if (uploadedImage) {
                sendImageToServer(uploadedImage);
            }
        });
    }

    if (cacheButton) {
        cacheButton.addEventListener('click', () => {
            if (uploadedImage) {
                cacheImageOnServer(uploadedImage);
            }
        });
    }

    if (clearCacheButton) {
        clearCacheButton.addEventListener('click', () => {
            clearImageCache();
        });
    }

    if (removeButton) {
        removeButton.addEventListener('click', () => {
            uploadedImage = null;
            previewImage.src = '';
            imagePreview.classList.add('hidden');
            imageInput.value = '';
        });
    }

    function sendImageToServer(imageFile) {
        const formData = new FormData();
        formData.append('image', imageFile);

        const thinkingIndicator = document.createElement('div');
        thinkingIndicator.className = 'flex space-x-3 p-4 bg-gradient-to-r from-gray-50 to-gray-100 rounded-2xl';
        thinkingIndicator.innerHTML = `
            <div class="w-10 h-10 bg-gradient-to-r from-purple-600 to-pink-500 rounded-full flex items-center justify-center flex-shrink-0">
                <span class="material-symbols-outlined text-white text-lg">adb</span>
            </div>
            <div class="flex-1">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-sm font-semibold text-purple-700">KI-Assistent</span>
                    <span class="text-xs text-gray-500">${formatTime(new Date())}</span>
                </div>
                <div class="flex space-x-1">
                    <div class="w-2 h-2 bg-purple-500 rounded-full animate-bounce"></div>
                    <div class="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                    <div class="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                </div>
            </div>
        `;
        chatHistory.appendChild(thinkingIndicator);
        scrollToBottom();

        addUserMessage('📷 Bild zur Analyse hochgeladen');

        fetch('/analyze-image', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            chatHistory.removeChild(thinkingIndicator);
            addBotMessage(data.analysis);
            speak(data.analysis);
            removeButton.click();
        })
        .catch(error => {
            console.error('Error analyzing image:', error);
            chatHistory.removeChild(thinkingIndicator);
            addBotMessage("Es gab ein Problem bei der Analyse des Bildes. Bitte versuche es später noch einmal.");
        });
    }

    function cacheImageOnServer(imageFile) {
        const formData = new FormData();
        formData.append('image', imageFile);

        addUserMessage('💾 Bild zum Zwischenspeicher hinzugefügt');

        fetch('/cache-image', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            addBotMessage(data.message);
            speak(data.message);
            cachedImageIndicator.classList.remove('hidden');
            clearCacheButton.classList.remove('hidden');
            clearCacheButton.classList.add('flex');
            removeButton.click();
        })
        .catch(error => {
            console.error('Error caching image:', error);
            addBotMessage("Es gab ein Problem beim Zwischenspeichern des Bildes. Bitte versuche es später noch einmal.");
        });
    }

    function clearImageCache() {
        fetch('/clear-cache', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            addBotMessage(data.message);
            speak(data.message);
            cachedImageIndicator.classList.add('hidden');
            clearCacheButton.classList.add('hidden');
            clearCacheButton.classList.remove('flex');
        })
        .catch(error => {
            console.error('Error clearing cache:', error);
            addBotMessage("Es gab ein Problem beim Leeren des Zwischenspeichers.");
        });
    }

    // Chat session management
    function loadChatHistory() {
        fetch('/get-chat-history')
        .then(response => response.json())
        .then(data => {
            if (data.chat_history && data.chat_history.length > 0) {
                chatHistory.innerHTML = '';
                data.chat_history.forEach(msg => {
                    if (msg.message_type === 'user') {
                        addUserMessage(msg.content, msg.created_at);
                    } else if (msg.message_type === 'assistant') {
                        addBotMessage(msg.content, msg.created_at);
                    }
                });
            }
        })
        .catch(error => {
            console.error('Error loading chat history:', error);
        });
    }

    if (newChatBtn) {
        newChatBtn.addEventListener('click', () => {
            fetch('/new-chat', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                location.reload();
            })
            .catch(error => {
                console.error('Error creating new chat:', error);
            });
        });
    }

    // Load chat session when clicked
    if (chatSessions) {
        chatSessions.addEventListener('click', (e) => {
            const sessionElement = e.target.closest('.chat-session');

            if (sessionElement) {
                const sessionId = sessionElement.dataset.sessionId;

                fetch(`/load-chat/${sessionId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    chatHistory.innerHTML = '';

                    if (data.chat_history && data.chat_history.length > 0) {
                        data.chat_history.forEach(msg => {
                            if (msg.message_type === 'user') {
                                addUserMessage(msg.content, msg.created_at);
                            } else if (msg.message_type === 'assistant') {
                                addBotMessage(msg.content, msg.created_at);
                            }
                        });
                    } else {
                        chatHistory.innerHTML = `
                            <div class="flex space-x-3 p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl">
                                <div class="w-10 h-10 bg-gradient-to-r from-purple-600 to-pink-500 rounded-full flex items-center justify-center flex-shrink-0">
                                    <span class="material-symbols-outlined text-white text-lg">adb</span>
                                </div>
                                <div class="flex-1">
                                    <div class="flex items-center space-x-2 mb-1">
                                        <span class="text-sm font-semibold text-purple-700">KI-Assistent</span>
                                        <span class="text-xs text-gray-500">Jetzt</span>
                                    </div>
                                    <p class="text-gray-700">Hi! Ich bin dein persönlicher Lernassistent. Sprich mit mir oder schreibe mir deine Fragen!</p>
                                </div>
                            </div>
                        `;
                    }

                    document.querySelectorAll('.chat-session').forEach(s => {
                        s.classList.remove('bg-purple-100', 'border-purple-300');
                        s.classList.add('bg-gray-50');
                    });
                    sessionElement.classList.remove('bg-gray-50');
                    sessionElement.classList.add('bg-purple-100', 'border-purple-300');

                    // Close sidebar on mobile after selecting chat
                    if (window.innerWidth < 768) {
                        toggleSidebar();
                    }
                })
                .catch(error => {
                    console.error('Error loading chat session:', error);
                });
            }
        });
    }

    // Context Menus
    const chatContextMenu = document.getElementById('chat-context-menu');
    const renameChatOption = document.getElementById('rename-chat');
    const deleteChatOption = document.getElementById('delete-chat');
    const assignmentContextMenu = document.getElementById('assignment-context-menu');
    const deleteAssignmentOption = document.getElementById('delete-assignment');
    const assignmentList = document.getElementById('assignment-list');

    let activeSessionId = null;
    let activeAssignmentId = null;

    const userType = document.getElementById('user-type').value;

    if (chatSessions) {
        chatSessions.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            const sessionElement = e.target.closest('.chat-session');
            if (sessionElement) {
                activeSessionId = sessionElement.dataset.sessionId;
                chatContextMenu.classList.remove('hidden');
                chatContextMenu.style.top = `${e.pageY}px`;
                chatContextMenu.style.left = `${e.pageX}px`;
            }
        });
    }

    if (userType === 'teacher' && assignmentList) {
        assignmentList.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            const assignmentElement = e.target.closest('.assignment-item');
            if (assignmentElement) {
                activeAssignmentId = assignmentElement.href.split('/').pop();
                assignmentContextMenu.classList.remove('hidden');
                assignmentContextMenu.style.top = `${e.pageY}px`;
                assignmentContextMenu.style.left = `${e.pageX}px`;
            }
        });
    }

    window.addEventListener('click', () => {
        if (chatContextMenu) chatContextMenu.classList.add('hidden');
        if (assignmentContextMenu) assignmentContextMenu.classList.add('hidden');
    });

    if (renameChatOption) {
        renameChatOption.addEventListener('click', () => {
            if (activeSessionId) {
                const sessionElement = document.querySelector(`.chat-session[data-session-id="${activeSessionId}"]`);
                const currentTitle = sessionElement.querySelector('.session-title').textContent;
                const newName = prompt('Neuer Name für den Chat:', currentTitle);

                if (newName && newName.trim() !== '') {
                    fetch(`/rename-chat/${activeSessionId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ new_name: newName.trim() })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            sessionElement.querySelector('.session-title').textContent = newName.trim();
                        } else {
                            alert(data.error || 'Fehler beim Umbenennen des Chats.');
                        }
                    })
                    .catch(error => {
                        console.error('Error renaming chat:', error);
                        alert('Ein Fehler ist aufgetreten.');
                    });
                }
            }
        });
    }

    if (deleteChatOption) {
        deleteChatOption.addEventListener('click', () => {
            if (activeSessionId) {
                if (confirm('Möchten Sie diesen Chat wirklich löschen?')) {
                    fetch(`/delete-chat/${activeSessionId}`, { method: 'POST' })
                    .then(() => location.reload());
                }
            }
        });
    }

    if (deleteAssignmentOption) {
        deleteAssignmentOption.addEventListener('click', () => {
            if (activeAssignmentId) {
                if (confirm('Möchten Sie diese Aufgabe wirklich löschen?')) {
                    fetch(`/delete-assignment/${activeAssignmentId}`, { method: 'POST' })
                    .then(() => location.reload());
                }
            }
        });
    }

    // Load current chat history on page load
    loadChatHistory();
});
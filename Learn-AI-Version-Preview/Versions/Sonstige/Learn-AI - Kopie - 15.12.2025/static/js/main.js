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
    const chatInput = document.getElementById('chat-input');
    const muteTtsButton = document.getElementById('mute-tts-button');

    // TTS Mute State
    let isMuted = localStorage.getItem('isMuted') === 'true';

    function updateMuteButtonUI() {
        if (muteTtsButton) {
            const icon = muteTtsButton.querySelector('.material-symbols-outlined');

            // Remove all color classes first
            muteTtsButton.classList.remove('bg-purple-600', 'hover:bg-purple-700', 'bg-gray-300', 'text-gray-800', 'hover:bg-gray-400', 'bg-green-500', 'hover:bg-green-600');
            icon.classList.remove('text-white', 'text-gray-800');

            if (isMuted) {
                icon.textContent = 'volume_off';
                muteTtsButton.classList.add('bg-gray-300', 'hover:bg-gray-400');
                icon.classList.add('text-gray-800');
            } else {
                icon.textContent = 'volume_up';
                muteTtsButton.classList.add('bg-green-500', 'hover:bg-green-600');
                icon.classList.add('text-white');
            }
        }
    }

    // Initial UI update for mute button
    updateMuteButtonUI();

    if (muteTtsButton) {
        muteTtsButton.addEventListener('click', () => {
            isMuted = !isMuted;
            localStorage.setItem('isMuted', isMuted);
            updateMuteButtonUI();
        });
    }

    // --- Unified Navigation Logic ---
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const sidebarMenuBtn = document.getElementById('sidebar-menu-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar');
    const mobileOverlay = document.getElementById('mobile-overlay');

    // Sidebar Tabs
    const chatsTabBtn = document.getElementById('chats-tab-btn');
    const assignmentsTabBtn = document.getElementById('assignments-tab-btn');
    const chatSessionsContainer = document.getElementById('chat-sessions-container');
    const assignmentListContainer = document.getElementById('assignment-list-container');

    function toggleSidebar() {
        const isOpen = sidebar.classList.contains('translate-x-0');

        if (isOpen) {
            // CLOSE
            sidebar.classList.remove('translate-x-0');
            sidebar.classList.add('-translate-x-full');
            sidebarMenuBtn.classList.remove('active');
            mobileOverlay.classList.add('hidden');
            if (mainContent) {
                mainContent.style.marginLeft = '0';
            }
        } else {
            // OPEN
            sidebar.classList.remove('-translate-x-full');
            sidebar.classList.add('translate-x-0');
            sidebarMenuBtn.classList.add('active');
            if (window.innerWidth < 768) {
                mobileOverlay.classList.remove('hidden');
            } else {
                if (mainContent) {
                    mainContent.style.marginLeft = '20rem'; // w-80
                }
            }
        }
    }

    if (sidebarMenuBtn) {
        sidebarMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleSidebar();
        });
    }

    if (closeSidebarBtn) {
        closeSidebarBtn.addEventListener('click', toggleSidebar);
    }

    if (mobileOverlay) {
        mobileOverlay.addEventListener('click', toggleSidebar);
    }

    window.addEventListener('resize', () => {
        const isOpen = sidebar.classList.contains('translate-x-0');
        if (isOpen) {
            if (window.innerWidth < 768) {
                // Desktop to Mobile
                mobileOverlay.classList.remove('hidden');
                if (mainContent) {
                    mainContent.style.marginLeft = '0';
                }
            } else {
                // Mobile to Desktop
                mobileOverlay.classList.add('hidden');
                if (mainContent) {
                    mainContent.style.marginLeft = '20rem';
                }
            }
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

        const botMessageElement = document.createElement('div');
        botMessageElement.className = 'flex space-x-3 p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl chat-message';
        const time = new Date();
        botMessageElement.innerHTML = `
            <div class="w-10 h-10 bg-gradient-to-r from-purple-600 to-pink-500 rounded-full flex items-center justify-center flex-shrink-0">
                <span class="material-symbols-outlined text-white text-lg">adb</span>
            </div>
            <div class="flex-1">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-sm font-semibold text-purple-700">KI-Assistent</span>
                    <span class="text-xs text-gray-500">${formatTime(time)}</span>
                </div>
                <p class="text-gray-700 text-sm leading-relaxed"></p>
            </div>
        `;

        const eventSource = new EventSource(`/ask?question=${encodeURIComponent(text)}`);
        let fullAnswer = '';
        let botMessageAppended = false;

        eventSource.onmessage = function(event) {
            if (!botMessageAppended) {
                if (thinkingIndicator && thinkingIndicator.parentNode) {
                    thinkingIndicator.parentNode.removeChild(thinkingIndicator);
                }
                chatHistory.appendChild(botMessageElement);
                botMessageAppended = true;
            }
            
            const content = event.data;
            console.log(content);
            if (content.startsWith("WORKSHEET_DOWNLOAD_LINK:")) {
                const worksheet_filename = content.substring("WORKSHEET_DOWNLOAD_LINK:".length);
                const downloadButton = document.createElement('a');
                downloadButton.href = `/download-worksheet/${worksheet_filename}`;
                downloadButton.className = 'mt-2 inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500';
                downloadButton.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">download</span> Arbeitsblatt herunterladen';
                botMessageElement.querySelector('.flex-1').appendChild(downloadButton);
            } else if (content.toLowerCase().startsWith("createmd:")) {
                // Do nothing, hide this from the user
            } else {
                fullAnswer += content;
                botMessageElement.querySelector('p').innerHTML = marked.parse(fullAnswer);
            }
            scrollToBottom();
        };

        eventSource.onerror = function(error) {
            console.error('EventSource failed:', error);
            eventSource.close();
            if (thinkingIndicator && thinkingIndicator.parentNode) {
                thinkingIndicator.parentNode.removeChild(thinkingIndicator);
            }
            if (fullAnswer) {
                speak(fullAnswer);
            } else {
                addBotMessage("Es gab ein Problem bei der Verarbeitung deiner Anfrage. Bitte versuche es später noch einmal.");
            }
        };

        eventSource.onclose = function() {
            if (fullAnswer) {
                speak(fullAnswer);
            }
        };
    }

    function speak(text) {
        if (isMuted) {
            console.log("TTS is muted.");
            return;
        }

        const audio = new Audio(`/synthesize?text=${encodeURIComponent(text)}`);
        audio.play();
    }

    if (chatInput) {
        const sendButton = document.getElementById('send-button');

        function sendMessage() {
            const message = chatInput.value.trim();
            if (message) {
                addUserMessage(message);
                sendToServer(message);
                chatInput.value = '';
                chatInput.style.height = 'auto';
                
                if (sendButton && recordButton) {
                    recordButton.classList.remove('hidden');
                    sendButton.classList.add('hidden');
                }
            }
        }

        if (sendButton) {
            sendButton.addEventListener('click', sendMessage);
        }

        chatInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        });

        function updateButtonVisibility() {
            if (sendButton && recordButton) {
                if (chatInput.value.trim().length > 0) {
                    recordButton.classList.add('hidden');
                    sendButton.classList.remove('hidden');
                } else {
                    recordButton.classList.remove('hidden');
                    sendButton.classList.add('hidden');
                }
            }
        }

        chatInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
            updateButtonVisibility();
        });
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        console.log("Spracherkennung wird in diesem Browser nicht unterst\u00fctzt.");
    } else if (recordButton) { // Check if recordButton exists
        const recognition = new SpeechRecognition();
        recognition.lang = 'de-DE';
        recognition.continuous = false;
        recognition.interimResults = false;

        let isRecording = false;

        // Speech Recognition Event Handlers
        recordButton.addEventListener('click', () => {
            if (isRecording) {
                recognition.stop();
            } else {
                recognition.start();
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
        
        recognition.onstart = () => {
            isRecording = true;
            updateRecordButton(true);
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;

            // Send it directly without modifying the input field
            if (transcript) {
                addUserMessage(transcript);
                sendToServer(transcript);
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error', event.error);
        };

        recognition.onend = () => {
            isRecording = false;
            updateRecordButton(false);
        };
    }

    function formatTime(date) {
        return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    }

    function addUserMessage(message, timestamp = null, image = null) {
        const messageElement = document.createElement('div');
        messageElement.className = 'flex space-x-3 justify-end chat-message';
        const time = timestamp ? new Date(timestamp) : new Date();
        
        let imageHTML = '';
        if (image) {
            let imageUrl;
            if (typeof image === 'string') {
                imageUrl = image; // It's a base64 string from history
            } else {
                imageUrl = URL.createObjectURL(image); // It's a File object from upload
            }
            imageHTML = `<img src="${imageUrl}" class="mt-2 rounded-lg max-w-xs">`;
        }

        messageElement.innerHTML = `
            <div class="flex flex-col items-end max-w-xs md:max-w-md">
                <div class="bg-gradient-to-r from-purple-600 to-pink-500 text-white p-3 rounded-2xl rounded-br-sm">
                    ${imageHTML}
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

    function addBotMessage(message, timestamp = null, worksheet_filename = null) {
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

        if (worksheet_filename) {
            const downloadButton = document.createElement('a');
            downloadButton.href = `/download-worksheet/${worksheet_filename}`;
            downloadButton.className = 'mt-2 inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500';
            downloadButton.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">download</span> Arbeitsblatt herunterladen';
            messageElement.querySelector('.flex-1').appendChild(downloadButton);
        }

        setTimeout(scrollToBottom, 100);
    }

    // Image upload functionality
    let uploadedImage = null;

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
                    cacheImageOnServer(uploadedImage);
                };
                reader.readAsDataURL(file);
            }
        });
    }

    if (removeButton) {
        removeButton.addEventListener('click', () => {
            uploadedImage = null;
            previewImage.src = '';
            imagePreview.classList.add('hidden');
            imageInput.value = '';
            clearImageCache();
        });
    }

    function sendMessage() {
        const message = chatInput.value.trim();
        if (message || uploadedImage) {
            addUserMessage(message, null, uploadedImage);
            sendToServer(message);
            chatInput.value = '';
            chatInput.style.height = 'auto';
            
            if (uploadedImage) {
                removeButton.click();
            }

            if (sendButton && recordButton) {
                recordButton.classList.remove('hidden');
                sendButton.classList.add('hidden');
            }
        }
    }

    function cacheImageOnServer(imageFile) {
        const formData = new FormData();
        formData.append('image', imageFile);

        fetch('/cache-image', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
            cachedImageIndicator.classList.remove('hidden');
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
            console.log(data.message);
            cachedImageIndicator.classList.add('hidden');
        })
        .catch(error => {
            console.error('Error clearing cache:', error);
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
                        addUserMessage(msg.content, msg.created_at, msg.image_data);
                    } else if (msg.message_type === 'assistant') {
                        addBotMessage(msg.content, msg.created_at, msg.worksheet_filename);
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
    if (chatSessionsContainer) {
        chatSessionsContainer.addEventListener('click', (e) => {
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

    let activeSessionId = null;
    let activeAssignmentId = null;

    const userType = document.getElementById('user-type').value;

    if (chatSessionsContainer) {
        chatSessionsContainer.addEventListener('contextmenu', (e) => {
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

    if (assignmentListContainer) {
        assignmentListContainer.addEventListener('click', (e) => {
            const assignmentElement = e.target.closest('.assignment-item');
            if (assignmentElement) {
                // Close sidebar on mobile after selecting an assignment
                if (window.innerWidth < 768) {
                    toggleSidebar();
                }
            }
        });
    }

    if (userType === 'teacher' && assignmentListContainer) {
        assignmentListContainer.addEventListener('contextmenu', (e) => {
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

    // Force close sidebar on page show (e.g., when using back button)
    window.addEventListener('pageshow', (event) => {
        if (event.persisted) {
            // Reset sidebar state on mobile to ensure it's closed
            if (window.innerWidth < 768) {
                sidebar.classList.remove('translate-x-0');
                sidebar.classList.add('-translate-x-full');
                sidebarMenuBtn.classList.remove('active');
                mobileOverlay.classList.add('hidden');
            }
        }
    });

    // Load current chat history on page load
    loadChatHistory();
});
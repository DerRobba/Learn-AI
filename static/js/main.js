document.addEventListener('DOMContentLoaded', function() {
    const userTypeEl = document.getElementById('user-type');
    // keep reference to the currently open EventSource so we can close
    // it before opening a new one. this prevents stray streams from
    // interfering with subsequent worksheet requests.
    let currentEventSource = null;
    const userType = userTypeEl ? userTypeEl.value : '';
    const isGuest = !userType || userType === 'None' || userType === '';

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
    
    // Chat Subject Filter Elements
    const chatSubjectFilterContainer = document.getElementById('chat-subject-filter-container');
    const chatSubjectFilter = document.getElementById('chat-subject-filter');

    function animateTitleUpdate(element, newTitle) {
        element.textContent = newTitle;
        element.classList.remove('animate-title');
        void element.offsetWidth; // Trigger reflow
        element.classList.add('animate-title');
        setTimeout(() => element.classList.remove('animate-title'), 1000);
    }

    function showWorksheetLoading(container, indicatorRef) {
        if (indicatorRef.val) return;
        indicatorRef.val = document.createElement('div');
        indicatorRef.val.className = 'mt-3 p-3 border border-purple-100 rounded-xl bg-purple-50/50 flex items-center space-x-3 text-purple-600';
        indicatorRef.val.innerHTML = `
            <span class="material-symbols-outlined animate-spin text-lg">progress_activity</span>
            <span class="text-sm font-medium">Arbeitsblatt wird erstellt...</span>
        `;
        container.appendChild(indicatorRef.val);
        scrollToBottom();
    }


    // --- Unified Navigation Logic ---
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const sidebarMenuBtn = document.getElementById('sidebar-menu-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar-btn');
    const mobileOverlay = document.getElementById('mobile-overlay');

    // Sidebar Tabs
    const chatsTabBtn = document.getElementById('chats-tab-btn');
    const assignmentsTabBtn = document.getElementById('assignments-tab-btn');
    const homeworkTabBtn = document.getElementById('homework-tab-btn');
    const chatSessionsContainer = document.getElementById('chat-sessions-container');
    const assignmentListContainer = document.getElementById('assignment-list-container');
    const homeworkListContainer = document.getElementById('homework-list-container');

    function toggleSidebar() {
        const isOpen = sidebar.classList.contains('translate-x-0');

        if (isOpen) {
            // CLOSE
            sidebar.classList.remove('translate-x-0');
            sidebar.classList.add('-translate-x-full');
            sidebarMenuBtn.classList.remove('active');
            mobileOverlay.classList.add('hidden');
            document.body.style.overflow = ''; // Enable scrolling
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
                document.body.style.overflow = 'hidden'; // Prevent scrolling background
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

            homeworkTabBtn.classList.add('text-gray-500', 'hover:bg-gray-100');
            homeworkTabBtn.classList.remove('bg-purple-100', 'text-purple-700');

            chatSessionsContainer.classList.remove('hidden');
            assignmentListContainer.classList.add('hidden');
            homeworkListContainer.classList.add('hidden');
            chatSubjectFilterContainer.classList.remove('hidden'); // Show filter
        });
    }

    if (assignmentsTabBtn) {
        assignmentsTabBtn.addEventListener('click', () => {
            if (isGuest) {
                window.location.href = '/login';
                return;
            }
            assignmentsTabBtn.classList.add('bg-purple-100', 'text-purple-700');
            assignmentsTabBtn.classList.remove('text-gray-500', 'hover:bg-gray-100');

            chatsTabBtn.classList.add('text-gray-500', 'hover:bg-gray-100');
            chatsTabBtn.classList.remove('bg-purple-100', 'text-purple-700');

            homeworkTabBtn.classList.add('text-gray-500', 'hover:bg-gray-100');
            homeworkTabBtn.classList.remove('bg-purple-100', 'text-purple-700');

            assignmentListContainer.classList.remove('hidden');
            chatSessionsContainer.classList.add('hidden');
            homeworkListContainer.classList.add('hidden');
            chatSubjectFilterContainer.classList.add('hidden'); // Hide filter
        });
    }

    if (homeworkTabBtn) {
        homeworkTabBtn.addEventListener('click', () => {
            if (isGuest) {
                window.location.href = '/login';
                return;
            }
            homeworkTabBtn.classList.add('bg-purple-100', 'text-purple-700');
            homeworkTabBtn.classList.remove('text-gray-500', 'hover:bg-gray-100');

            chatsTabBtn.classList.add('text-gray-500', 'hover:bg-gray-100');
            chatsTabBtn.classList.remove('bg-purple-100', 'text-purple-700');

            assignmentsTabBtn.classList.add('text-gray-500', 'hover:bg-gray-100');
            assignmentsTabBtn.classList.remove('bg-purple-100', 'text-purple-700');

            homeworkListContainer.classList.remove('hidden');
            chatSessionsContainer.classList.add('hidden');
            assignmentListContainer.classList.add('hidden');
            chatSubjectFilterContainer.classList.add('hidden'); // Hide filter
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
                <div class="text-gray-700 text-sm leading-relaxed prose prose-sm max-w-none"></div>
            </div>
        `;

        // if a previous stream is still open, close it to avoid
        // multiple concurrent connections to /ask for the same session.
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
        const eventSource = new EventSource(`/ask?question=${encodeURIComponent(text)}`);
        currentEventSource = eventSource;
        // when the SSE connection terminates (either natural or due to error)
        // clear the stored reference so that future calls won't try to close it.
        eventSource.onerror = function(e) {
            if (currentEventSource === eventSource) currentEventSource = null;
        };
        let fullAnswer = '';
        let botMessageAppended = false;
        let worksheetLoadingIndicator = { val: null };

        eventSource.onmessage = function(event) {
            // when the stream finishes or errors we should clear the
            // global reference so that a future sendToServer call will not
            // mistakenly close the wrong object.

            if (!botMessageAppended) {
                if (thinkingIndicator && thinkingIndicator.parentNode) {
                    thinkingIndicator.parentNode.removeChild(thinkingIndicator);
                }
                chatHistory.appendChild(botMessageElement);
                botMessageAppended = true;
            }
            
            const content = event.data;
            const trimmedContent = content.trim();
            
            if (trimmedContent.startsWith("WORKSHEET_DOWNLOAD_LINK:")) {
                let worksheet_filename = trimmedContent.substring("WORKSHEET_DOWNLOAD_LINK:".length);
                // Clean filename just in case
                worksheet_filename = worksheet_filename.replace(/^.*[\\\/]/, '');
                
                // Remove loading indicator if it exists
                if (worksheetLoadingIndicator.val && worksheetLoadingIndicator.val.parentNode) {
                    worksheetLoadingIndicator.val.parentNode.removeChild(worksheetLoadingIndicator.val);
                    worksheetLoadingIndicator.val = null;
                }

                // Ermittle Dateiendung
                const dateiendung = worksheet_filename.split('.').pop().toLowerCase();
                
                // Container für Arbeitsblatt-Aktionen
                const actionContainer = document.createElement('div');
                actionContainer.className = 'mt-3 space-y-2';
                
                const buttonsWrapper = document.createElement('div');
                buttonsWrapper.className = 'flex flex-wrap gap-2';
                
                const previewBtn = document.createElement('button');
                previewBtn.className = 'inline-flex items-center px-3 py-1.5 border border-purple-200 text-xs font-medium rounded-md shadow-sm text-purple-700 bg-purple-50 hover:bg-purple-100 transition-colors';
                previewBtn.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">visibility</span> Vorschau anzeigen';
                
                const downloadLink = document.createElement('a');
                downloadLink.href = `/download-worksheet/${worksheet_filename}`;
                downloadLink.className = 'inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 transition-colors';
                downloadLink.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">download</span> Herunterladen';
                
                buttonsWrapper.appendChild(previewBtn);
                buttonsWrapper.appendChild(downloadLink);
                actionContainer.appendChild(buttonsWrapper);
                
                const previewWrapper = document.createElement('div');
                previewWrapper.className = 'hidden mt-2 border border-purple-200 rounded-lg overflow-hidden bg-white';
                actionContainer.appendChild(previewWrapper);
                
                previewBtn.onclick = () => {
                    if (previewWrapper.classList.contains('hidden')) {
                        previewWrapper.classList.remove('hidden');
                        previewWrapper.innerHTML = `<iframe src="/preview-worksheet/${worksheet_filename}" style="width: 100%; height: 500px; border: none; background: white;"></iframe>`;
                        previewBtn.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">visibility_off</span> Vorschau ausblenden';
                    } else {
                        previewWrapper.classList.add('hidden');
                        previewWrapper.innerHTML = '';
                        previewBtn.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">visibility</span> Vorschau anzeigen';
                    }
                    scrollToBottom();
                };
                
                botMessageElement.querySelector('.flex-1').appendChild(actionContainer);
            } else if (trimmedContent.startsWith("SESSION_TITLE:")) {
                const newTitle = trimmedContent.substring("SESSION_TITLE:".length);
                const activeSession = document.querySelector('.chat-session.bg-purple-100');
                if (activeSession) {
                    const titleEl = activeSession.querySelector('.session-title');
                    if (titleEl) animateTitleUpdate(titleEl, newTitle);
                }
                // Always reload the full session list to ensure sync
                setTimeout(loadAllChatSessionsAndRender, 500);
            } else if (trimmedContent.startsWith("SESSION_SUBJECT:")) {
                const neuesFach = trimmedContent.substring("SESSION_SUBJECT:".length);
                const activChat = document.querySelector('.chat-session.bg-purple-100');
                if (activChat) {
                    // Update or create the subject element
                    let subjectEl = activChat.querySelector('.session-subject');
                    if (!subjectEl) {
                        subjectEl = document.createElement('span');
                        subjectEl.className = 'session-subject text-xs text-gray-600 truncate';
                        activChat.querySelector('.flex-col').appendChild(subjectEl);
                    }
                    subjectEl.textContent = `Fach: ${neuesFach}`;
                    activChat.dataset.chatSubject = neuesFach;
                }
                // Aktualisiere auch die Fach-Filter-Optionen und die Session-Liste
                loadChatSubjects();
                loadAllChatSessionsAndRender();
            } else if (trimmedContent === "START_WORKSHEET_GENERATION") {
                console.log("Arbeitsblatt-Generierung gestartet...");
                showWorksheetLoading(botMessageElement.querySelector('.flex-1'), worksheetLoadingIndicator);
            } else if (trimmedContent === "HOMEWORK_UPDATED") {
                // Reload or update specific UI part
                setTimeout(() => location.reload(), 1500);
            } else {
                fullAnswer += content;

                // Also check if the raw stream contains worksheet markers to show animation immediately
                if (fullAnswer.includes('worksheet_creation') && !worksheetLoadingIndicator.val) {
                    showWorksheetLoading(botMessageElement.querySelector('.flex-1'), worksheetLoadingIndicator);
                }

                // Remove finished action tags and replace with a single space
                let displayHTML = fullAnswer.replace(/<action>[\s\S]*?<\/action>/gi, ' ');
                
                // If we are currently inside an action tag or have a partial tag, hide it
                // This covers <, <a, <ac, <action...
                displayHTML = displayHTML.replace(/\s*<[a-zA-Z\/]*$/gi, ' '); 
                displayHTML = displayHTML.replace(/\s*<action[\s\S]*$/gi, ' '); 
                
                // Also remove raw JSON objects/arrays and replace with space
                displayHTML = displayHTML.replace(/(\{[\s\S]*?\}|\[[\s\S]*?\])/g, ' ');
                displayHTML = displayHTML.replace(/[\{\[]\s*$/g, ' '); 

                // Final cleanup for stray tag fragments
                displayHTML = displayHTML.replace(/<\/action\/?>/gi, ' ');
                displayHTML = displayHTML.replace(/action>/gi, ' ');
                
                // Filter out redundant "please wait" phrases from real-time display
                displayHTML = displayHTML.replace(/Bitte hab einen Moment Geduld, während ich es generiere\./gi, '');
                displayHTML = displayHTML.replace(/Bitte gib mir einen Moment, damit es vollständig generiert wird\./gi, '');

                // Collapse multiple spaces into one, but don't trim() yet to allow trailing spaces from AI
                displayHTML = displayHTML.replace(/\s+/g, ' ');
                
                botMessageElement.querySelector('.prose').innerHTML = marked.parse(displayHTML);
            }
            scrollToBottom();
        };

        eventSource.onerror = function(error) {
            console.error('EventSource failed:', error);
            eventSource.close();
            if (thinkingIndicator && thinkingIndicator.parentNode) {
                thinkingIndicator.parentNode.removeChild(thinkingIndicator);
            }
            if (worksheetLoadingIndicator.val && worksheetLoadingIndicator.val.parentNode) {
                worksheetLoadingIndicator.val.parentNode.removeChild(worksheetLoadingIndicator.val);
                worksheetLoadingIndicator.val = null;
            }
            if (fullAnswer) {
                // Do nothing
            } else {
                addBotMessage("Es gab ein Problem bei der Verarbeitung deiner Anfrage. Bitte versuche es später noch einmal.");
            }
        };
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const speechSupported = !!SpeechRecognition;

    if (chatInput) {
        const sendButton = document.getElementById('send-button');

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
        
        // Initial call
        updateButtonVisibility();
    }

    if (recordButton) { 
        let isRecording = false;
        let recognition = null;

        if (speechSupported) {
            recognition = new SpeechRecognition();
            recognition.lang = 'de-DE';
            recognition.continuous = false;
            recognition.interimResults = false;

            recognition.onstart = () => {
                isRecording = true;
                updateRecordButton(true);
            };

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                if (transcript) {
                    addUserMessage(transcript);
                    sendToServer(transcript);
                }
            };

            recognition.onerror = (event) => {
                console.error('Speech recognition error', event.error);
                if (event.error === 'not-allowed') {
                    addBotMessage("Mikrofon-Zugriff wurde verweigert. Bitte erlaube den Zugriff in den Browser-Einstellungen.");
                } else if (event.error === 'no-speech') {
                    console.log("No speech detected.");
                } else if (event.error === 'network') {
                    addBotMessage("Netzwerkfehler bei der Spracherkennung. Bitte prüfe deine Internetverbindung.");
                } else if (event.error !== 'aborted') {
                    addBotMessage("Ein Fehler ist bei der Spracherkennung aufgetreten: " + event.error);
                }
                isRecording = false;
                updateRecordButton(false);
            };

            recognition.onend = () => {
                isRecording = false;
                updateRecordButton(false);
            };
        }

        // Speech Recognition Event Handlers
        recordButton.addEventListener('click', () => {
            if (!speechSupported) {
                addBotMessage("Spracherkennung wird in diesem Browser leider nicht unterstützt. Nutze am besten Chrome oder Edge.");
                return;
            }

            if (isRecording) {
                try {
                    recognition.stop();
                } catch (e) {
                    console.error("Error stopping recognition:", e);
                }
            } else {
                try {
                    recognition.start();
                } catch (e) {
                    console.error("Error starting recognition:", e);
                    const isSecure = window.location.protocol === 'https:' || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
                    if (!isSecure) {
                        addBotMessage("Spracherkennung benötigt eine sichere HTTPS-Verbindung (oder localhost/127.0.0.1).");
                    } else {
                        addBotMessage("Fehler beim Starten der Spracherkennung. Bitte stelle sicher, dass Mikrofon-Zugriff gewährt ist.");
                    }
                    updateRecordButton(false);
                    isRecording = false;
                }
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
            imageHTML = `<img src="${imageUrl}" class="mt-2 rounded-lg max-w-full h-auto shadow-sm">`;
        }

        messageElement.innerHTML = `
            <div class="flex flex-col items-end max-w-[80%] md:max-w-md">
                <div class="bg-gradient-to-r from-purple-600 to-pink-500 text-white p-3 rounded-2xl rounded-br-sm shadow-md">
                    ${imageHTML}
                    <p class="text-sm leading-relaxed">${message}</p>
                </div>
                <span class="text-xs text-gray-500 mt-1">Du • ${formatTime(time)}</span>
            </div>
            <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-green-500 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm">
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
        
        // Parse markdown content
        const parsedMessage = marked.parse(message);

        messageElement.innerHTML = `
            <div class="w-10 h-10 bg-gradient-to-r from-purple-600 to-pink-500 rounded-full flex items-center justify-center flex-shrink-0">
                <span class="material-symbols-outlined text-white text-lg">adb</span>
            </div>
            <div class="flex-1">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-sm font-semibold text-purple-700">KI-Assistent</span>
                    <span class="text-xs text-gray-500">${formatTime(time)}</span>
                </div>
                <div class="text-gray-700 text-sm leading-relaxed prose prose-sm max-w-none">${parsedMessage}</div>
            </div>
        `;
        chatHistory.appendChild(messageElement);

        if (worksheet_filename === 'PENDING') {
            const indicatorRef = { val: null };
            showWorksheetLoading(messageElement.querySelector('.flex-1'), indicatorRef);
        } else if (worksheet_filename) {
            // Clean filename just in case
            const clean_filename = worksheet_filename.replace(/^.*[\\\/]/, '');

            const actionContainer = document.createElement('div');
            actionContainer.className = 'mt-3 space-y-2';
            
            const buttonsWrapper = document.createElement('div');
            buttonsWrapper.className = 'flex flex-wrap gap-2';
            
            const previewBtn = document.createElement('button');
            previewBtn.className = 'inline-flex items-center px-3 py-1.5 border border-purple-200 text-xs font-medium rounded-md shadow-sm text-purple-700 bg-purple-50 hover:bg-purple-100 transition-colors';
            previewBtn.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">visibility</span> Vorschau anzeigen';
            
            const downloadLink = document.createElement('a');
            downloadLink.href = `/download-worksheet/${clean_filename}`;
            downloadLink.className = 'inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 transition-colors';
            downloadLink.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">download</span> Herunterladen';
            
            buttonsWrapper.appendChild(previewBtn);
            buttonsWrapper.appendChild(downloadLink);
            actionContainer.appendChild(buttonsWrapper);
            
            const previewWrapper = document.createElement('div');
            previewWrapper.className = 'hidden mt-2 border border-purple-200 rounded-lg overflow-hidden bg-white';
            actionContainer.appendChild(previewWrapper);
            
            previewBtn.onclick = () => {
                if (previewWrapper.classList.contains('hidden')) {
                    previewWrapper.classList.remove('hidden');
                    previewWrapper.innerHTML = `<iframe src="/preview-worksheet/${clean_filename}" style="width: 100%; height: 500px; border: none; background: white;"></iframe>`;
                    previewBtn.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">visibility_off</span> Vorschau ausblenden';
                } else {
                    previewWrapper.classList.add('hidden');
                    previewWrapper.innerHTML = '';
                    previewBtn.innerHTML = '<span class="material-symbols-outlined text-sm mr-1">visibility</span> Vorschau anzeigen';
                }
                scrollToBottom();
            };
            
            messageElement.querySelector('.flex-1').appendChild(actionContainer);
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
                // Manually clear UI state without triggering server cache clear
                uploadedImage = null;
                previewImage.src = '';
                imagePreview.classList.add('hidden');
                imageInput.value = '';
                cachedImageIndicator.classList.add('hidden');
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

    // Global variable to store all chat sessions
    let allChatSessions = [];
    let currentSessionId = null;

    // Helper to get session ID from DOM
    function updateCurrentSessionIdFromDOM() {
        const activeSession = document.querySelector('.chat-session.bg-purple-100');
        if (activeSession) {
            currentSessionId = activeSession.dataset.sessionId;
        }
    }
    
    // Initial update
    updateCurrentSessionIdFromDOM();

    function renderChatSessions(sessionsToRender) {
        if (!chatSessionsContainer) return;
        chatSessionsContainer.innerHTML = ''; // Clear existing sessions

        if (sessionsToRender.length === 0) {
            chatSessionsContainer.innerHTML = `
                <p class="text-center text-gray-500 text-sm mt-4">Keine Chats gefunden.</p>
            `;
            return;
        }

        sessionsToRender.forEach(session => {
            const sessionElement = document.createElement('div');
            sessionElement.className = `chat-session p-3 rounded-lg bg-gray-50 hover:bg-gray-100 border border-transparent hover:border-purple-200 cursor-pointer transition-all duration-300 active:bg-purple-50 ${session.session_id === currentSessionId ? 'bg-purple-100 border-purple-300' : ''}`;
            sessionElement.dataset.sessionId = session.session_id;
            sessionElement.dataset.chatSubject = session.chat_subject || '';
            sessionElement.style.touchAction = 'manipulation';
            
            let subjectHtml = '';
            if (session.chat_subject) {
                subjectHtml = `<span class="session-subject text-xs text-gray-600 truncate">Fach: ${session.chat_subject}</span>`;
            }

            sessionElement.innerHTML = `
                <div class="flex flex-col space-y-1 pointer-events-none">
                    <span class="session-title text-sm font-medium text-gray-800 truncate">${session.session_name}</span>
                    ${subjectHtml}
                    <span class="session-date text-xs text-gray-500">${session.last_message ? session.last_message.substring(0, 16) : ''}</span>
                </div>
            `;
            chatSessionsContainer.appendChild(sessionElement);
        });
        
        // After rendering, ensure our currentSessionId is still correct
        updateCurrentSessionIdFromDOM();
    }

    function loadChatSubjects() {
        if (!chatSubjectFilter) return;

        fetch('/api/chat-subjects')
            .then(response => response.json())
            .then(subjects => {
                const currentVal = chatSubjectFilter.value;
                // Clear existing options except "Alle Chats"
                chatSubjectFilter.innerHTML = '<option value="all">Alle Chats</option>';
                subjects.forEach(subject => {
                    const option = document.createElement('option');
                    option.value = subject;
                    option.textContent = subject;
                    chatSubjectFilter.appendChild(option);
                });
                // Restore selection if still valid
                if (currentVal && Array.from(chatSubjectFilter.options).some(o => o.value === currentVal)) {
                    chatSubjectFilter.value = currentVal;
                }
            })
            .catch(error => {
                console.error('Error loading chat subjects:', error);
            });
    }

    function filterChatSessions() {
        if (!chatSubjectFilter) return;
        const selectedSubject = chatSubjectFilter.value;
        if (selectedSubject === 'all') {
            renderChatSessions(allChatSessions);
        } else {
            const filteredSessions = allChatSessions.filter(session => session.chat_subject === selectedSubject);
            renderChatSessions(filteredSessions);
        }
    }

    // Event-Listener für Filter-Dropdown
    if (chatSubjectFilter) {
        chatSubjectFilter.addEventListener('change', filterChatSessions);
    }

    function loadAllChatSessionsAndRender() {
        fetch('/get-user-chat-sessions') // This endpoint provides all sessions for the current user
        .then(response => response.json())
        .then(sessions => {
            allChatSessions = sessions; // Store all sessions
            filterChatSessions(); // Apply current filter
            loadChatSubjects(); // Populate filter dropdown
        })
        .catch(error => {
            console.error('Error loading all chat sessions:', error);
        });
    }

    function checkChatStatus(sessionId = null) {
        const url = sessionId ? `/api/check-chat-status?session_id=${sessionId}` : '/api/check-chat-status';
        fetch(url)
        .then(response => response.json())
        .then(data => {
            // Only show indicator if the chat being checked is the one currently visible
            const isCurrentSession = !sessionId || sessionId === currentSessionId;
            
            if (data.generating) {
                if (isCurrentSession && !document.querySelector('.thinking-indicator')) {
                    const thinkingIndicator = document.createElement('div');
                    thinkingIndicator.className = 'flex space-x-3 p-4 bg-gradient-to-r from-gray-50 to-gray-100 rounded-2xl thinking-indicator';
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
                }
                // Poll again in 2 seconds
                setTimeout(() => checkChatStatus(sessionId), 2000);
            } else {
                // Done generating
                if (isCurrentSession) {
                    const indicator = document.querySelector('.thinking-indicator');
                    if (indicator) {
                        indicator.parentNode.removeChild(indicator);
                        // Reload history and sidebar when finished
                        loadChatHistory();
                        loadAllChatSessionsAndRender();
                    }
                }
            }
        })
        .catch(error => console.error('Error checking chat status:', error));
    }

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
        })
        .finally(() => {
            // Check status on page load or manual reload
            checkChatStatus();
        });
    }

    if (newChatBtn) {
        newChatBtn.addEventListener('click', () => {
            fetch('/new-chat', {
                method: 'POST'
            })
            .then(response => {
                if (response.status === 401) {
                    window.location.href = '/login';
                    return;
                }
                return response.json();
            })
            .then(data => {
                if (data) location.reload();
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
                currentSessionId = sessionId;

                fetch(`/load-chat/${sessionId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    chatHistory.innerHTML = '';
                    
                    // Remove any existing thinking indicators from previous session view
                    const oldIndicator = document.querySelector('.thinking-indicator');
                    if (oldIndicator) oldIndicator.remove();

                    if (data.chat_history && data.chat_history.length > 0) {
                        data.chat_history.forEach(msg => {
                            if (msg.message_type === 'user') {
                                addUserMessage(msg.content, msg.created_at, msg.image_data);
                            } else if (msg.message_type === 'assistant') {
                                addBotMessage(msg.content, msg.created_at, msg.worksheet_filename);
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
                                    <p class="text-gray-700">Hi! Ich bin dein persönlicher Lernassistent. Sprich mit mir oder schreibe mir deine Fragen! Ich werde dir nie die Lösung verraten, sondern dir helfen sie selbst herauszufinden.</p>
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
                    
                    // Check if this newly loaded session is generating in background
                    checkChatStatus(sessionId);
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
    const homeworkContextMenu = document.getElementById('homework-context-menu');
    const deleteHomeworkOption = document.getElementById('delete-homework');

    const settingsBtn = document.getElementById('settings-btn');
    const settingsView = document.getElementById('settings-view');
    const settingsHome = document.getElementById('settings-home');
    const memoriesSection = document.getElementById('memories-section');
    const settingsTitle = document.getElementById('settings-title');
    
    const chatView = document.getElementById('chat-view');
    const backToChatBtn = document.getElementById('back-to-chat-btn');
    const backToSettingsHomeBtn = document.getElementById('back-to-settings-home-btn');
    const closeSettingsBtn = document.getElementById('close-settings-btn');
    
    const openMemoriesBtn = document.getElementById('open-memories-btn');
    const openPrivacyBtn = document.getElementById('open-privacy-btn');
    const openPrivacyPolicyBtn = document.getElementById('open-privacy-policy-btn');
    const privacySection = document.getElementById('privacy-section');
    const privacyPolicyTextSection = document.getElementById('privacy-policy-text-section');
    const impressumSection = document.getElementById('impressum-section');
    const agbSection = document.getElementById('agb-section');
    const openImpressumBtn = document.getElementById('open-impressum-btn');
    const openAgbBtn = document.getElementById('open-agb-btn');

    const mathSolverToggle = document.getElementById('math-solver-toggle');
    const memoriesList = document.getElementById('memories-list');
    const addMemoryBtn = document.getElementById('add-memory-btn');
    const newMemoryInput = document.getElementById('new-memory-input');

    function hideAllSettingsSections() {
        settingsHome.classList.add('hidden');
        memoriesSection.classList.add('hidden');
        if (privacySection) privacySection.classList.add('hidden');
        if (privacyPolicyTextSection) privacyPolicyTextSection.classList.add('hidden');
        if (impressumSection) impressumSection.classList.add('hidden');
        if (agbSection) agbSection.classList.add('hidden');
    }

    function showSettingsHome() {
        hideAllSettingsSections();
        settingsHome.classList.remove('hidden');
        backToSettingsHomeBtn.classList.add('hidden');
        if (window.innerWidth < 768) {
            backToChatBtn.classList.remove('hidden');
        }
        settingsTitle.textContent = 'Einstellungen';
        backToSettingsHomeBtn.onclick = null;
    }

    function showMemories() {
        hideAllSettingsSections();
        memoriesSection.classList.remove('hidden');
        backToSettingsHomeBtn.classList.remove('hidden');
        backToChatBtn.classList.add('hidden');
        settingsTitle.textContent = 'Gedächtnis';
        loadMemories();
        backToSettingsHomeBtn.onclick = showSettingsHome;
    }

    function showPrivacy() {
        hideAllSettingsSections();
        if (privacySection) privacySection.classList.remove('hidden');
        backToSettingsHomeBtn.classList.remove('hidden');
        backToChatBtn.classList.add('hidden');
        settingsTitle.textContent = 'Rechtliches';
        backToSettingsHomeBtn.onclick = showSettingsHome;
    }

    function showPrivacyPolicyText() {
        hideAllSettingsSections();
        if (privacyPolicyTextSection) privacyPolicyTextSection.classList.remove('hidden');
        backToSettingsHomeBtn.classList.remove('hidden');
        backToChatBtn.classList.add('hidden');
        settingsTitle.textContent = 'Datenschutzerklärung';
        backToSettingsHomeBtn.onclick = showPrivacy;
    }

    function showImpressum() {
        hideAllSettingsSections();
        if (impressumSection) impressumSection.classList.remove('hidden');
        backToSettingsHomeBtn.classList.remove('hidden');
        backToChatBtn.classList.add('hidden');
        settingsTitle.textContent = 'Impressum';
        backToSettingsHomeBtn.onclick = showPrivacy;
    }

    function showAgb() {
        hideAllSettingsSections();
        if (agbSection) agbSection.classList.remove('hidden');
        backToSettingsHomeBtn.classList.remove('hidden');
        backToChatBtn.classList.add('hidden');
        settingsTitle.textContent = 'Nutzungsbedingungen';
        backToSettingsHomeBtn.onclick = showPrivacy;
    }

    if (openMemoriesBtn) openMemoriesBtn.addEventListener('click', showMemories);
    if (openPrivacyBtn) openPrivacyBtn.addEventListener('click', showPrivacy);
    if (openPrivacyPolicyBtn) openPrivacyPolicyBtn.addEventListener('click', showPrivacyPolicyText);
    if (openImpressumBtn) openImpressumBtn.addEventListener('click', showImpressum);
    if (openAgbBtn) openAgbBtn.addEventListener('click', showAgb);

    if (backToSettingsHomeBtn) {
        backToSettingsHomeBtn.addEventListener('click', () => {
            if (!backToSettingsHomeBtn.onclick) showSettingsHome();
        });
    }

    function loadMemories() {
        if (!memoriesList) return;
        
        memoriesList.innerHTML = `
            <div class="p-8 text-center text-gray-500">
                <span class="material-symbols-outlined text-4xl mb-2 text-gray-300 animate-pulse">psychology</span>
                <p>Lade Erinnerungen...</p>
            </div>
        `;

        fetch('/api/memories')
            .then(response => response.json())
            .then(data => {
                if (data.memories && data.memories.length > 0) {
                    memoriesList.innerHTML = '';
                    data.memories.forEach(memory => {
                        const memoryItem = document.createElement('div');
                        memoryItem.className = 'p-4 hover:bg-gray-50 transition-colors flex justify-between items-start group';
                        memoryItem.innerHTML = `
                            <div class="flex items-start space-x-3">
                                <span class="material-symbols-outlined text-purple-400 mt-0.5 text-lg">lightbulb</span>
                                <div>
                                    <p class="text-gray-800 text-sm leading-relaxed">${memory.content}</p>
                                    <p class="text-xs text-gray-400 mt-1">${new Date(memory.created_at).toLocaleDateString('de-DE')}</p>
                                </div>
                            </div>
                            <button class="delete-memory-btn opacity-0 group-hover:opacity-100 p-2 text-gray-400 hover:text-red-500 transition-all" data-id="${memory.id}" title="Löschen">
                                <span class="material-symbols-outlined text-sm">delete</span>
                            </button>
                        `;
                        memoriesList.appendChild(memoryItem);
                    });

                    // Add event listeners for delete buttons
                    document.querySelectorAll('.delete-memory-btn').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const memoryId = e.currentTarget.dataset.id;
                            showDeleteModal(memoryId, 'memory');
                        });
                    });

                } else {
                    memoriesList.innerHTML = `
                        <div class="p-8 text-center text-gray-500">
                            <span class="material-symbols-outlined text-4xl mb-2 text-gray-300">psychology_alt</span>
                            <p>Noch keine Erinnerungen gespeichert.</p>
                            <p class="text-xs mt-2">Die KI speichert wichtige Infos automatisch, während ihr schreibt.</p>
                        </div>
                    `;
                }
            })
            .catch(err => {
                console.error('Error loading memories:', err);
                memoriesList.innerHTML = '<div class="p-4 text-center text-red-500">Fehler beim Laden.</div>';
            });
    }
    
    function addMemory() {
        const content = newMemoryInput.value.trim();
        if (!content) return;

        addMemoryBtn.disabled = true;
        
        fetch('/api/memories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                newMemoryInput.value = '';
                loadMemories();
            } else {
                alert(data.error || 'Fehler beim Speichern');
            }
        })
        .catch(err => console.error(err))
        .finally(() => {
            addMemoryBtn.disabled = false;
        });
    }

    if (addMemoryBtn) {
        addMemoryBtn.addEventListener('click', addMemory);
    }
    
    if (newMemoryInput) {
        newMemoryInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') addMemory();
        });
    }

    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => {
            if (window.innerWidth < 768) {
                toggleSidebar(); // Close sidebar on mobile
            }
            chatView.classList.add('hidden');
            settingsView.classList.remove('hidden');
            showSettingsHome(); // Reset to home
            loadSettings();
        });
    }

    if (backToChatBtn) {
        backToChatBtn.addEventListener('click', () => {
            settingsView.classList.add('hidden');
            chatView.classList.remove('hidden');
        });
    }

    if (closeSettingsBtn) {
        closeSettingsBtn.addEventListener('click', () => {
            settingsView.classList.add('hidden');
            chatView.classList.remove('hidden');
        });
    }
    
    // Also allow returning to chat via the sidebar "Chats" tab
    if (chatsTabBtn) {
        const originalChatTabClick = chatsTabBtn.onclick; // Preserve existing logic if any (added via addEventListener above)
        chatsTabBtn.addEventListener('click', () => {
             settingsView.classList.add('hidden');
             chatView.classList.remove('hidden');
        });
    }


    let activeSessionId = null;
    let activeAssignmentId = null;
    let activeHomeworkId = null;

    if (homeworkListContainer) {
        // Toggle completion status
        homeworkListContainer.addEventListener('click', (e) => {
            const toggleBtn = e.target.closest('.toggle-homework-btn');
            if (toggleBtn) {
                e.preventDefault();
                e.stopPropagation();
                
                const homeworkItem = toggleBtn.closest('.homework-item');
                const homeworkId = homeworkItem.dataset.id;
                
                fetch(`/toggle-homework/${homeworkId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Toggle local UI state without reload
                        const isCompleted = homeworkItem.classList.contains('bg-green-50');
                        const title = homeworkItem.querySelector('.homework-title');
                        const icon = toggleBtn.querySelector('.material-symbols-outlined');
                        const badge = homeworkItem.querySelector('.text-xs.px-2');

                        if (isCompleted) {
                            // Mark as not completed
                            homeworkItem.classList.remove('bg-green-50', 'border-green-200');
                            homeworkItem.classList.add('bg-gray-50', 'border-transparent');
                            title.classList.remove('text-green-800', 'line-through');
                            title.classList.add('text-gray-800');
                            icon.classList.remove('text-green-600');
                            icon.classList.add('text-gray-400');
                            icon.textContent = 'radio_button_unchecked';
                            toggleBtn.title = 'Erledigt';
                            if (badge) {
                                badge.classList.remove('bg-green-100', 'text-green-700');
                                badge.classList.add('bg-blue-100', 'text-blue-700');
                            }
                        } else {
                            // Mark as completed
                            homeworkItem.classList.add('bg-green-50', 'border-green-200');
                            homeworkItem.classList.remove('bg-gray-50', 'border-transparent');
                            title.classList.add('text-green-800', 'line-through');
                            title.classList.remove('text-gray-800');
                            icon.classList.add('text-green-600');
                            icon.classList.remove('text-gray-400');
                            icon.textContent = 'check_circle';
                            toggleBtn.title = 'Als offen markieren';
                            if (badge) {
                                badge.classList.add('bg-green-100', 'text-green-700');
                                badge.classList.remove('bg-blue-100', 'text-blue-700');
                            }
                        }
                    }
                });
            }
        });

        // Context Menu
        homeworkListContainer.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            const homeworkItem = e.target.closest('.homework-item');
            if (homeworkItem) {
                activeHomeworkId = homeworkItem.dataset.id;
                homeworkContextMenu.classList.remove('hidden');
                homeworkContextMenu.style.top = `${e.pageY}px`;
                homeworkContextMenu.style.left = `${e.pageX}px`;
            }
        });
    }

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
        if (homeworkContextMenu) homeworkContextMenu.classList.add('hidden');
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
                            const titleEl = sessionElement.querySelector('.session-title');
                            if (titleEl) animateTitleUpdate(titleEl, newName.trim());
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

    // Delete Modal Logic
    const deleteModal = document.getElementById('delete-modal');
    const cancelDeleteBtn = document.getElementById('cancel-delete-btn');
    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
    let itemToDeleteId = null;
    let deleteActionType = null; // 'chat', 'assignment', 'homework', 'memory'

    function showDeleteModal(id, type) {
        itemToDeleteId = id;
        deleteActionType = type;
        if (deleteModal) deleteModal.classList.remove('hidden');
    }

    function hideDeleteModal() {
        if (deleteModal) deleteModal.classList.add('hidden');
        itemToDeleteId = null;
        deleteActionType = null;
    }

    if (cancelDeleteBtn) {
        cancelDeleteBtn.addEventListener('click', hideDeleteModal);
    }

    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', () => {
            if (!itemToDeleteId || !deleteActionType) return;

            if (deleteActionType === 'chat') {
                fetch(`/delete-chat/${itemToDeleteId}`, { method: 'POST' })
                .then(() => location.reload());
            } else if (deleteActionType === 'assignment') {
                fetch(`/delete-assignment/${itemToDeleteId}`, { method: 'POST' })
                .then(() => location.reload());
            } else if (deleteActionType === 'homework') {
                fetch(`/delete-homework/${itemToDeleteId}`, { method: 'POST' })
                .then(() => location.reload());
            } else if (deleteActionType === 'memory') {
                 fetch(`/api/memories/${itemToDeleteId}`, { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                        if(data.success) loadMemories();
                        hideDeleteModal();
                    });
                 return; // Don't hide here, let the fetch callback do it or logic above
            }
            // For page reloads, we don't need to hide explicitly as the page refreshes
        });
    }

    // Close modal on outside click
    if (deleteModal) {
        deleteModal.addEventListener('click', (e) => {
            if (e.target === deleteModal) hideDeleteModal();
        });
    }

    if (deleteChatOption) {
        deleteChatOption.addEventListener('click', () => {
            if (activeSessionId) {
                showDeleteModal(activeSessionId, 'chat');
            }
        });
    }

    if (deleteAssignmentOption) {
        deleteAssignmentOption.addEventListener('click', () => {
            if (activeAssignmentId) {
                 if (confirm('Möchten Sie diese Aufgabe wirklich löschen?')) { // Keep simple confirm for now or upgrade too
                     fetch(`/delete-assignment/${activeAssignmentId}`, { method: 'POST' })
                     .then(() => location.reload());
                 }
            }
        });
    }

    if (deleteHomeworkOption) {
        deleteHomeworkOption.addEventListener('click', () => {
            if (activeHomeworkId) {
                if (confirm('Möchten Sie diese Hausaufgabe wirklich löschen?')) {
                     fetch(`/delete-homework/${activeHomeworkId}`, { method: 'POST' })
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

            // Check if a worksheet was being generated before reload

            function checkWorksheetStatusOnLoad() {

                fetch('/api/check-worksheet-status')

                    .then(res => res.json())

                    .then(data => {

                        if (data.generating) {

                            // Poll for completion

                            const pollInterval = setInterval(() => {

                                fetch('/get-chat-history')

                                    .then(r => r.json())

                                    .then(historyData => {

                                        const history = historyData.chat_history;

                                        const isStillPending = history.some(msg => msg.worksheet_filename === 'PENDING');

                                        if (!isStillPending) {

                                            clearInterval(pollInterval);

                                            location.reload(); // Refresh to show the download buttons

                                        }

                                    });

                            }, 3000);

                        }

                    });

            }

        

    

        // Load current chat history on page load
        loadChatHistory();
        
        // Load all chat sessions and render them with filter
        loadAllChatSessionsAndRender();

        setTimeout(checkWorksheetStatusOnLoad, 500);

    });

    
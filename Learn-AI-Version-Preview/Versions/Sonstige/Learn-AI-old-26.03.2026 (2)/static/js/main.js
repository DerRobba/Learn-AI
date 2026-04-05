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
    const sendButton = document.getElementById('send-button');
    
    // Chat Subject Filter Elements
    const filterOpenBtn = document.getElementById('filter-open-btn');
    const closeFilterViewBtn = document.getElementById('close-filter-view-btn');
    const sidebarTabsContent = document.getElementById('sidebar-tabs-content');
    const subjectFilterView = document.getElementById('subject-filter-view');
    const subjectChipsContainer = document.getElementById('subject-chips');

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
        let lastMessageTime = Date.now();
        let timeoutCheckInterval = null;
        
        // Check for connection timeout - restart if no data for 45 seconds
        timeoutCheckInterval = setInterval(() => {
            const timeSinceLastMessage = Date.now() - lastMessageTime;
            if (timeSinceLastMessage > 45000 && eventSource.readyState === 1) {
                console.warn('EventSource timeout - no data for 45 seconds, reconnecting...');
                eventSource.close();
                // The onerror handler will clean up and show error
            }
        }, 10000); // Check every 10 seconds
        
        // when the SSE connection terminates (either natural or due to error)
        // clear the stored reference so that future calls won't try to close it.
        eventSource.onerror = function(e) {
            clearInterval(timeoutCheckInterval);
            if (currentEventSource === eventSource) currentEventSource = null;
            // Don't show error for normal closure
            if (e.type !== 'close') {
                console.error('EventSource error:', e);
            }
        };
        let fullAnswer = '';
        let botMessageAppended = false;
        let worksheetLoadingIndicator = { val: null };

        eventSource.onmessage = function(event) {
            // Reset timeout on each message
            lastMessageTime = Date.now();
            
            const content = event.data;
            const trimmedContent = content.trim();

            // Ignore PING messages
            if (trimmedContent === "PING") {
                return;
            }

            if (!botMessageAppended && trimmedContent !== "") {
                if (thinkingIndicator && thinkingIndicator.parentNode) {
                    thinkingIndicator.parentNode.removeChild(thinkingIndicator);
                }
                chatHistory.appendChild(botMessageElement);
                botMessageAppended = true;
            }
            
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
                
                // Remove thinking/internal tags
                displayHTML = displayHTML.replace(/\[(?:thinking|thoughts|gedanken|chain-of-thought|analysis)\][\s\S]*?\[\/(?:thinking|thoughts|gedanken|chain-of-thought|analysis)\]/gi, ' ');
                displayHTML = displayHTML.replace(/\{(?:gedanken|thoughts|thinking|internal)[^}]*\}/gi, ' ');

                // If we are currently inside an action tag or have a partial tag, hide ONLY the tag
                // We use a temporary variable for the regex check to avoid mutating displayHTML incorrectly
                let cleaningHTML = displayHTML;
                
                // Hide partial tags at the end of the stream without replacing them with spaces
                // This prevents "eating" characters if the regex is too broad
                cleaningHTML = cleaningHTML.replace(/<[a-zA-Z\/]*$/i, ''); 
                cleaningHTML = cleaningHTML.replace(/<action[\s\S]*$/i, ''); 
                cleaningHTML = cleaningHTML.replace(/[\{\[]\s*$/g, ''); 

                // Final cleanup for stray complete tag fragments
                cleaningHTML = cleaningHTML.replace(/<\/action>/gi, '');
                cleaningHTML = cleaningHTML.replace(/<action>/gi, '');
                
                // Filter out redundant "please wait" phrases
                cleaningHTML = cleaningHTML.replace(/Bitte hab einen Moment Geduld, während ich es generiere\./gi, '');
                cleaningHTML = cleaningHTML.replace(/Bitte gib mir einen Moment, damit es vollständig generiert wird\./gi, '');
                cleaningHTML = cleaningHTML.replace(/Bitte hab einen Moment Geduld\./gi, '');
                cleaningHTML = cleaningHTML.replace(/Bitte gib mir einen Moment\./gi, '');

                // Normalize whitespace for marked, but don't strip leading space if it separates words
                cleaningHTML = cleaningHTML.replace(/\s+/g, ' ');
                
                // Trim leading whitespace only if it's the very start of the whole message
                // and it was likely left over from a stripped "please wait" or tag
                if (cleaningHTML.startsWith(' ')) {
                    cleaningHTML = cleaningHTML.trimStart();
                }
                
                botMessageElement.querySelector('.prose').innerHTML = marked.parse(cleaningHTML);
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
            const newHeight = Math.min(this.scrollHeight, 200);
            this.style.height = newHeight + 'px';
            this.style.overflowY = this.scrollHeight > 200 ? 'auto' : 'hidden';
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

            // Refresh sidebar after a short delay to ensure DB has been updated by the /ask request
            // This handles "lazy" chat creation (it appears only after first message)
            setTimeout(loadAllChatSessionsAndRender, 1000);
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

        if (!Array.isArray(sessionsToRender) || sessionsToRender.length === 0) {
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

    // Toggle Filter View in Sidebar
    if (filterOpenBtn && subjectFilterView && sidebarTabsContent) {
        filterOpenBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            // Open sidebar if closed
            if (!sidebar.classList.contains('translate-x-0')) {
                toggleSidebar();
            }
            // Switch views
            sidebarTabsContent.classList.add('hidden');
            subjectFilterView.classList.remove('hidden');
            loadChatSubjects(); // Refresh chips
        });
    }

    if (closeFilterViewBtn) {
        closeFilterViewBtn.addEventListener('click', () => {
            if (subjectFilterView) subjectFilterView.classList.add('hidden');
            if (sidebarTabsContent) sidebarTabsContent.classList.remove('hidden');
        });
    }

    function loadChatSubjects() {
        if (!subjectChipsContainer) return;

        // Check if user is logged in before fetching subjects
        const authData = document.body.dataset.authenticated;
        const isLoggedIn = authData === 'true';
        if (!isLoggedIn) return;

        fetch('/api/chat-subjects')
            .then(response => response.json())
            .then(subjects => {
                // Keep "Alle" chip and clear others
                const allChip = subjectChipsContainer.querySelector('[data-value="all"]');
                subjectChipsContainer.innerHTML = '';
                if (allChip) {
                    allChip.textContent = 'Alle Chats'; // Reset label
                    // Set active style for "all" chip if it's the current filter
                    if (currentFilterValue === 'all') {
                        allChip.className = 'subject-chip px-4 py-2 rounded-full text-sm font-semibold bg-purple-600 text-white border border-purple-600 shadow-sm transition-all duration-300';
                    } else {
                        allChip.className = 'subject-chip px-4 py-2 rounded-full text-sm font-semibold bg-gray-100 text-gray-600 border border-gray-200 hover:bg-purple-50 hover:text-purple-600 hover:border-purple-200 transition-all duration-300';
                    }
                    subjectChipsContainer.appendChild(allChip);
                }

                if (Array.isArray(subjects)) {
                    subjects.forEach(subject => {
                        if (!subject) return;
                        const chip = document.createElement('button');
                        // Set active style if this subject is the current filter
                        if (currentFilterValue === subject) {
                            chip.className = 'subject-chip px-4 py-2 rounded-full text-sm font-semibold bg-purple-600 text-white border border-purple-600 shadow-sm transition-all duration-300';
                        } else {
                            chip.className = 'subject-chip px-4 py-2 rounded-full text-sm font-semibold bg-gray-100 text-gray-600 border border-gray-200 hover:bg-purple-50 hover:text-purple-600 hover:border-purple-200 transition-all duration-300';
                        }
                        chip.dataset.value = subject;
                        chip.textContent = subject;
                        subjectChipsContainer.appendChild(chip);
                    });
                }

                // Re-add click listeners to all chips
                document.querySelectorAll('.subject-chip').forEach(chip => {
                    chip.addEventListener('click', () => {
                        const val = chip.dataset.value;
                        setActiveFilter(val, chip.textContent);
                        // Hide filter view and show tabs after selection
                        setTimeout(() => {
                            if (subjectFilterView) subjectFilterView.classList.add('hidden');
                            if (sidebarTabsContent) sidebarTabsContent.classList.remove('hidden');
                        }, 200);
                    });
                });
            })
            .catch(error => {
                console.error('Error loading chat subjects:', error);
            });
    }
    let currentFilterValue = 'all';

    function setActiveFilter(value, label) {
        currentFilterValue = value;
        
        // Update chip styles
        document.querySelectorAll('.subject-chip').forEach(chip => {
            if (chip.dataset.value === value) {
                chip.classList.remove('bg-gray-100', 'text-gray-600', 'border-gray-200');
                chip.classList.add('bg-purple-600', 'text-white', 'border-purple-600', 'shadow-sm');
            } else {
                chip.classList.add('bg-gray-100', 'text-gray-600', 'border-gray-200');
                chip.classList.remove('bg-purple-600', 'text-white', 'border-purple-600', 'shadow-sm');
            }
        });

        filterChatSessions();
    }

    function filterChatSessions() {
        const selectedSubject = currentFilterValue;
        if (selectedSubject === 'all') {
            renderChatSessions(allChatSessions);
        } else {
            const filteredSessions = Array.isArray(allChatSessions) ? allChatSessions.filter(session => session.chat_subject === selectedSubject) : [];
            renderChatSessions(filteredSessions);
        }
    }

    function loadAllChatSessionsAndRender() {
        // Check if user is logged in before fetching sessions
        const authData = document.body.dataset.authenticated;
        const isLoggedIn = authData === 'true';
        if (!isLoggedIn) {
            allChatSessions = [];
            renderChatSessions([]);
            return;
        }

        fetch('/get-user-chat-sessions') // This endpoint provides all sessions for the current user
        .then(response => response.json())
        .then(sessions => {
            allChatSessions = Array.isArray(sessions) ? sessions : []; // Store all sessions
            filterChatSessions(); // Apply current filter
            loadChatSubjects(); // Populate filter dropdown
        })
        .catch(error => {
            console.error('Error loading all chat sessions:', error);
            allChatSessions = [];
            renderChatSessions([]);
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
                if (data && data.session_id) {
                    currentSessionId = data.session_id;
                    // Clear history and show welcome message LOCALLY
                    chatHistory.innerHTML = `
                        <div class="flex space-x-3 p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl chat-message">
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
                    
                    // Remove highlight from all sessions since this is a new, unsaved one
                    document.querySelectorAll('.chat-session').forEach(s => {
                        s.classList.remove('bg-purple-100', 'border-purple-300');
                        s.classList.add('bg-gray-50');
                    });

                    // Close sidebar on mobile
                    if (window.innerWidth < 768 && sidebar.classList.contains('translate-x-0')) {
                        toggleSidebar();
                    }
                }
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
    const sidebarLegalBtn = document.getElementById('sidebar-legal-btn');
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

    // Download Data
    const downloadDataBtn = document.getElementById('download-data-btn');
    if (downloadDataBtn) {
        downloadDataBtn.addEventListener('click', () => {
            window.location.href = '/api/account/download-data';
        });
    }

    // Delete Account
    const deleteAccountBtn = document.getElementById('delete-account-btn');
    const deleteAccountModal = document.getElementById('delete-account-modal');
    const cancelDeleteAccountBtn = document.getElementById('cancel-delete-account-btn');
    const confirmDeleteAccountBtn = document.getElementById('confirm-delete-account-btn');

    if (deleteAccountBtn && deleteAccountModal) {
        deleteAccountBtn.addEventListener('click', () => {
            deleteAccountModal.classList.remove('hidden');
        });
        cancelDeleteAccountBtn.addEventListener('click', () => {
            deleteAccountModal.classList.add('hidden');
        });
        confirmDeleteAccountBtn.addEventListener('click', () => {
            confirmDeleteAccountBtn.disabled = true;
            confirmDeleteAccountBtn.textContent = 'Wird gelöscht...';
            fetch('/api/account/delete', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        window.location.href = '/login';
                    } else {
                        alert('Fehler beim Löschen: ' + (data.error || 'Unbekannter Fehler'));
                        deleteAccountModal.classList.add('hidden');
                        confirmDeleteAccountBtn.disabled = false;
                        confirmDeleteAccountBtn.textContent = 'Endgültig löschen';
                    }
                })
                .catch(() => {
                    alert('Netzwerkfehler. Bitte versuche es erneut.');
                    deleteAccountModal.classList.add('hidden');
                    confirmDeleteAccountBtn.disabled = false;
                    confirmDeleteAccountBtn.textContent = 'Endgültig löschen';
                });
        });
    }

    if (sidebarLegalBtn) {
        sidebarLegalBtn.addEventListener('click', () => {
            if (window.innerWidth < 768) {
                toggleSidebar(); // Close sidebar on mobile
            }
            chatView.classList.add('hidden');
            settingsView.classList.remove('hidden');
            showPrivacy(); // Directly show Legal section
        });
    }

    // Initialize Math Solver Toggle
    if (mathSolverToggle) {
        // Load current status
        fetch('/api/settings/math-solver')
            .then(response => response.json())
            .then(data => {
                mathSolverToggle.checked = data.enabled;
            })
            .catch(err => console.error('Error loading math solver status:', err));

        // Listen for changes
        mathSolverToggle.addEventListener('change', () => {
            const isEnabled = mathSolverToggle.checked;
            fetch('/api/settings/math-solver', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: isEnabled })
            })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    alert('Fehler beim Speichern der Einstellung.');
                    mathSolverToggle.checked = !isEnabled; // Revert
                }
            })
            .catch(err => {
                console.error('Error saving math solver status:', err);
                mathSolverToggle.checked = !isEnabled; // Revert
            });
        });
    }

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

    function showPrivacy(fromSidebar = false) {
        hideAllSettingsSections();
        if (privacySection) privacySection.classList.remove('hidden');
        backToSettingsHomeBtn.classList.remove('hidden');
        backToChatBtn.classList.add('hidden');
        settingsTitle.textContent = 'Rechtliches';
        
        if (fromSidebar) {
            backToSettingsHomeBtn.onclick = () => {
                settingsView.classList.add('hidden');
                chatView.classList.remove('hidden');
            };
        } else {
            backToSettingsHomeBtn.onclick = showSettingsHome;
        }
    }

    function showPrivacyPolicyText() {
        hideAllSettingsSections();
        if (privacyPolicyTextSection) privacyPolicyTextSection.classList.remove('hidden');
        backToSettingsHomeBtn.classList.remove('hidden');
        backToChatBtn.classList.add('hidden');
        settingsTitle.textContent = 'Datenschutzerklärung';
        
        // Use current back behavior to decide next back behavior
        const currentlyFromSidebar = backToSettingsHomeBtn.onclick && !backToSettingsHomeBtn.onclick.toString().includes('showSettingsHome');
        backToSettingsHomeBtn.onclick = () => showPrivacy(currentlyFromSidebar);
    }

    function showImpressum() {
        hideAllSettingsSections();
        if (impressumSection) impressumSection.classList.remove('hidden');
        backToSettingsHomeBtn.classList.remove('hidden');
        backToChatBtn.classList.add('hidden');
        settingsTitle.textContent = 'Impressum';
        const currentlyFromSidebar = backToSettingsHomeBtn.onclick && !backToSettingsHomeBtn.onclick.toString().includes('showSettingsHome');
        backToSettingsHomeBtn.onclick = () => showPrivacy(currentlyFromSidebar);
    }

    function showAgb() {
        hideAllSettingsSections();
        if (agbSection) agbSection.classList.remove('hidden');
        backToSettingsHomeBtn.classList.remove('hidden');
        backToChatBtn.classList.add('hidden');
        settingsTitle.textContent = 'Nutzungsbedingungen';
        const currentlyFromSidebar = backToSettingsHomeBtn.onclick && !backToSettingsHomeBtn.onclick.toString().includes('showSettingsHome');
        backToSettingsHomeBtn.onclick = () => showPrivacy(currentlyFromSidebar);
    }

    if (openMemoriesBtn) openMemoriesBtn.addEventListener('click', showMemories);
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

        // ===== TUTORIAL SYSTEM mit Intro.js =====
        
        // Warten bis Intro.js geladen ist
        function waitForIntro() {
            return new Promise((resolve) => {
                if (typeof introJs !== 'undefined') {
                    resolve();
                } else {
                    const checkInterval = setInterval(() => {
                        if (typeof introJs !== 'undefined') {
                            clearInterval(checkInterval);
                            resolve();
                        }
                    }, 100);
                    // Timeout nach 5 Sekunden
                    setTimeout(() => {
                        clearInterval(checkInterval);
                        resolve();
                    }, 5000);
                }
            });
        }
        
        // Tutorial-Funktion mit Intro.js
        window.startTutorial = async function() {
            console.log('startTutorial() aufgerufen');
            
            // Bestehende Instanzen aggressiv aufräumen, falls vorhanden
            if (window.introJsInstance) {
                try {
                    window.introJsInstance.exit(true);
                } catch (e) {}
            }
            
            // Manuelles Cleanup für den Fall, dass Fragmente übrig sind
            document.querySelectorAll('.introjs-overlay, .introjs-helperLayer, .introjs-tooltipReferenceLayer, .introjs-tooltip').forEach(el => el.remove());
            
            // Warte auf Intro.js
            await waitForIntro();
            
            // Stelle sicher, dass Intro.js geladen ist
            if (typeof introJs === 'undefined') {
                console.error('Intro.js konnte nicht geladen werden');
                alert('Tutorial-Bibliothek konnte nicht geladen werden. Bitte aktualisieren Sie die Seite.');
                return;
            }

            console.log('Intro.js ist geladen, starte Tour...');

            // Definiere die Tutorial-Schritte für Intro.js
            const isMobileWidth = window.innerWidth <= 500;
            
            const steps = [
                {
                    element: '#sidebar-menu-btn',
                    title: '📋 Menü & Navigation',
                    intro: 'Hier öffnest du das Seitenmenü. Dort findest du deine Chats, Aufgaben und Hausaufgaben.',
                    position: 'bottom'
                },
                {
                    element: '#tabs-container',
                    title: '📦 Alles an einem Ort',
                    intro: (isMobileWidth 
                        ? 'Hier findest du deine Chats (deine Fragen), Aufgaben (von Lehrern) und Hausaufgaben (zum Organisieren). Wische nach links, um alles zu sehen!'
                        : 'Hier verwaltest du deine Chats, Aufgaben und Hausaufgaben. Die KI hilft dir dabei, alles zu strukturieren und Hausaufgaben sogar direkt in den Kalender einzutragen.') + (isGuest ? '<br><br>⚠️ *Hinweis: Aufgaben und Hausaufgaben sind nur verfügbar, wenn du angemeldet bist.*' : ''),
                    position: 'bottom'
                },
                {
                    element: '#new-chat-btn',
                    title: '💬 Neuer Chat',
                    intro: 'Starte hier eine neue Unterhaltung, um Fragen zu stellen oder Hilfe beim Lernen zu bekommen.',
                    position: 'right'
                },
                {
                    element: '#chat-input',
                    title: '❓ Fragen stellen & Arbeitsblätter',
                    intro: 'Schreibe der KI deine Fragen. Tipp: Sag "Erstelle ein Arbeitsblatt zum Thema...", um ein PDF zu erhalten!',
                    position: 'top'
                },
                {
                    element: '#settings-btn',
                    title: '⚙️ Einstellungen & Extras',
                    intro: 'In den Einstellungen findest du alles Wichtige: Verwalte das Gedächtnis der KI und schalte den Mathe-Löser für direkte Lösungen frei.',
                    position: 'left'
                }
            ];

            // Überprüfe, welche Elemente existieren
            const validSteps = steps.filter(step => {
                const element = document.querySelector(step.element);
                if (!element) {
                    console.warn(`Element nicht gefunden: ${step.element}`);
                    return false;
                }
                return true;
            });

            console.log(`${validSteps.length} von ${steps.length} Schritte gefunden`);

            if (validSteps.length === 0) {
                console.error('Keine gültigen Tutorial-Elemente gefunden!');
                alert('Tutorial konnte nicht gestartet werden. Bitte aktualisieren Sie die Seite.');
                return;
            }

            try {
                console.log('Initialisiere Intro.js...');
                const intro = introJs();
                
                intro.setOptions({
                    steps: validSteps,
                    showProgress: false,
                    showButtons: true,
                    doneLabel: '✕',
                    nextLabel: 'Weiter →',
                    prevLabel: '← Zurück',
                    skipLabel: '✕',
                    hidePrev: true,
                    hideNext: false,
                    showBullets: false,
                    scrollToElement: true,
                    overlayOpacity: 0.7,
                    disableInteraction: false,
                    helperElementPadding: 10, // Abstand um das Element für bessere Zentrierung
                    keyboardNavigation: true,
                    exitOnEsc: true,
                    exitOnOverlayClick: false
                });

                // Dynamische Sidebar-Steuerung
                let lastStep = -1;
                
                intro.onchange(function(targetElement) {
                    const currentStep = intro._currentStep;
                    console.log('Schritt geändert zu:', currentStep, 'Element:', targetElement);
                    
                    // Nur ausführen, wenn Schritt sich wirklich geändert hat
                    if (currentStep !== lastStep) {
                        lastStep = currentStep;
                        
                        // Schritt 1 (Tabs-Container): Sidebar öffnen
                        if (currentStep === 1) {
                            console.log('→ Schritt 1: Sidebar öffnen');
                            if (sidebar && !sidebar.classList.contains('translate-x-0')) {
                                toggleSidebar();
                                setTimeout(() => {
                                    intro.refresh();
                                }, 300);
                            }
                        }
                        // Schritt 3 (Chat-Input): Sidebar schließen
                        else if (currentStep === 3) {
                            console.log('→ Schritt 3: Sidebar schließen');
                            if (sidebar && sidebar.classList.contains('translate-x-0')) {
                                toggleSidebar();
                                setTimeout(() => {
                                    intro.refresh();
                                }, 300);
                            }
                        }
                        // Schritt 4 (Settings): Sidebar öffnen
                        else if (currentStep === 4) {
                            console.log('→ Schritt 4: Sidebar öffnen');
                            if (sidebar && !sidebar.classList.contains('translate-x-0')) {
                                toggleSidebar();
                                setTimeout(() => {
                                    intro.refresh();
                                }, 300);
                            }
                        }
                    }
                });

                // Entferne Overlay und schließe Sidebar beim Beenden
                const cleanupTutorial = function() {
                    console.log('Räume Tutorial auf...');
                    
                    // Schließe Sidebar
                    if (sidebar && sidebar.classList.contains('translate-x-0')) {
                        toggleSidebar();
                    }
                    
                    // Entferne ALLE Intro.js-Elemente aggressiv
                    // Overlays
                    document.querySelectorAll('.introjs-overlay').forEach(el => {
                        el.style.opacity = '0';
                        el.style.display = 'none';
                        el.remove();
                    });
                    
                    // Helper Layers
                    document.querySelectorAll('.introjs-helperLayer').forEach(el => {
                        el.style.display = 'none';
                        el.remove();
                    });
                    
                    // Tooltips
                    document.querySelectorAll('.introjs-tooltip').forEach(el => {
                        el.style.display = 'none';
                        el.remove();
                    });
                    
                    // Floating Tooltips
                    document.querySelectorAll('[class*="floating"]').forEach(el => {
                        if (el.classList.contains('introjs-tooltip')) {
                            el.remove();
                        }
                    });
                    
                    // Progress bar verstecken
                    document.querySelectorAll('.introjs-progress').forEach(el => {
                        el.style.display = 'none !important';
                        el.remove();
                    });
                    
                    // Entferne body-Klassen
                    document.body.classList.remove('introjs-showElement');
                    
                    // Markiere Tutorial als abgeschlossen
                    localStorage.setItem('tutorialCompleted', 'true');
                    console.log('✓ Tutorial als abgeschlossen markiert');
                    
                    // Aktualisiere Tutorial-Button Sichtbarkeit
                    updateTutorialButtonVisibility();
                    
                    console.log('✓ Tutorial aufgeräumt');
                };

                intro.oncomplete(cleanupTutorial);
                intro.onexit(cleanupTutorial);

                console.log('Starte Intro.js Tour...');
                intro.start();
                console.log('✓ Tutorial erfolgreich gestartet');
            } catch (error) {
                console.error('Fehler beim Starten des Tutorials:', error);
                console.error('Error Stack:', error.stack);
                alert('Fehler beim Tutorial: ' + error.message);
            }
        };

        // Tutorial aus den Einstellungen starten
        window.startTutorialFromSettings = async function() {
            console.log('startTutorialFromSettings() aufgerufen');
            
            // Schließe Einstellungen
            const settingsView = document.getElementById('settings-view');
            if (settingsView) {
                settingsView.classList.add('hidden');
                console.log('Einstellungen geschlossen');
            }
            
            // Zeige Chat wieder
            const chatView = document.getElementById('chat-view');
            if (chatView) {
                chatView.classList.remove('hidden');
                console.log('Chat angezeigt');
            }
            
            // Starte Tutorial nach kurzer Verzögerung
            setTimeout(() => {
                window.startTutorial();
            }, 300);
        };

        // Registriere Tutorial-Buttons
        function setupTutorialButtons() {
            console.log('Richte Tutorial-Buttons ein...');
            
            // Function zum Aktualisieren der Button-Sichtbarkeit
            window.updateTutorialButtonVisibility = function() {
                const headerTutorialBtn = document.getElementById('start-tutorial-btn');
                if (!headerTutorialBtn) return;
                
                // Checke ob Benutzer angemeldet ist (über das neue data-Attribut oder Logout-Button)
                const authData = document.body.dataset.authenticated;
                const isLoggedIn = authData === 'true' || document.querySelector('a[href="/logout"]') !== null;
                
                // Checke ob Tutorial bereits gemacht wurde
                const tutorialCompleted = localStorage.getItem('tutorialCompleted') === 'true';
                
                // Zeige Button wenn: 
                // - Benutzer NICHT angemeldet ist ODER
                // - Tutorial noch nicht gemacht wurde (wichtig für neue Accounts)
                const shouldShow = !isLoggedIn || !tutorialCompleted;
                
                console.log('Tutorial Status Check:', { isLoggedIn, tutorialCompleted, shouldShow });

                if (shouldShow) {
                    headerTutorialBtn.classList.remove('hidden');
                    headerTutorialBtn.classList.add('flex'); // Zeige auf allen Größen
                    console.log('✓ Tutorial-Button sichtbar');
                } else {
                    headerTutorialBtn.classList.add('hidden');
                    headerTutorialBtn.classList.remove('flex');
                    console.log('✓ Tutorial-Button versteckt (Bedingungen nicht erfüllt)');
                }
            };
            
            // Aktualisiere Button-Sichtbarkeit beim Setup
            updateTutorialButtonVisibility();
            
            // Header-Button
            const headerTutorialBtn = document.getElementById('start-tutorial-btn');
            if (headerTutorialBtn) {
                // Entferne alte Listener
                const newBtn = headerTutorialBtn.cloneNode(true);
                headerTutorialBtn.parentNode.replaceChild(newBtn, headerTutorialBtn);
                
                // Registriere neuen Listener
                newBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('Header-Tutorial-Button geklickt');
                    window.startTutorial();
                });
                console.log('✓ Header-Tutorial-Button eingerichtet');
            } else {
                console.warn('✗ Header-Tutorial-Button nicht gefunden');
            }
            
            // Settings-Button mit Event-Delegation auf die Eltern-Container
            const settingsHome = document.getElementById('settings-home');
            if (settingsHome) {
                settingsHome.addEventListener('click', function(e) {
                    // Überprüfe, ob geklicktes Element der Tutorial-Button oder ein Kind davon ist
                    const tutorialBtn = e.target.closest('#start-tutorial-settings-btn');
                    if (tutorialBtn) {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('Settings-Tutorial-Button geklickt');
                        window.startTutorialFromSettings();
                        return false;
                    }
                });
                console.log('✓ Settings-Tutorial-Button eingerichtet');
            } else {
                console.warn('✗ settings-home nicht gefunden');
            }
        }
        
        // Richte Buttons sofort ein (im DOMContentLoaded-Callback)
        setupTutorialButtons();
        
        // Und nochmal nach einer Verzögerung als Sicherheitsmaßnahme
        setTimeout(setupTutorialButtons, 1000);

        // --- FIRST LOGIN TUTORIAL MODAL ---
        const tutorialModal = document.getElementById('tutorial-modal');
        const startTutorialNow = document.getElementById('start-tutorial-now');
        const skipTutorialNow = document.getElementById('skip-tutorial-now');
        const isFirstLoginEl = document.getElementById('is-first-login');

        if (isFirstLoginEl && (isFirstLoginEl.value === 'True' || isFirstLoginEl.value === '1')) {
            setTimeout(() => {
                if (tutorialModal) {
                    tutorialModal.classList.remove('hidden');
                    console.log('DEBUG: Zeige Tutorial-Modal für neuen Nutzer');
                }
            }, 1500);
        }

        if (startTutorialNow) {
            startTutorialNow.addEventListener('click', function() {
                if (tutorialModal) tutorialModal.classList.add('hidden');
                window.startTutorial();
            });
        }

        if (skipTutorialNow) {
            skipTutorialNow.addEventListener('click', function() {
                if (tutorialModal) tutorialModal.classList.add('hidden');
            });
        }

    });

    
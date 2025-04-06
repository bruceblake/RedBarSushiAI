// Real-time Audio Demo for RedBarSushiAI
// This script demonstrates how to use the WebSocket APIs for real-time audio streaming

// Configuration 
const config = {
    serverUrl: window.location.origin,  // Use same server as this page
    sttEndpoint: '/api/ws/speech-to-text',
    ttsEndpoint: '/api/ws/text-to-speech',
    conversationEndpoint: '/api/ws/conversation',
    capabilitiesEndpoint: '/api/ws/capabilities',
    defaultVoice: 'alloy'
};

// State management
let state = {
    recording: false,
    connected: false,
    sessionId: null,
    socket: null,
    mediaRecorder: null,
    audioContext: null,
    capabilities: null,
    conversation: [],
    audioQueue: [],
    processingAudio: false
};

// DOM Elements
const elements = {
    startButton: document.getElementById('start-recording'),
    stopButton: document.getElementById('stop-recording'),
    statusDiv: document.getElementById('status'),
    transcriptDiv: document.getElementById('transcript'),
    responseDiv: document.getElementById('response'),
    conversationDiv: document.getElementById('conversation'),
    textInput: document.getElementById('text-input'),
    sendButton: document.getElementById('send-text'),
    audioPlayer: document.getElementById('audio-player')
};

// Helper function to update UI status
function updateStatus(message) {
    if (elements.statusDiv) {
        elements.statusDiv.textContent = message;
    }
    console.log('Status:', message);
}

// Initialize by checking server capabilities
async function initialize() {
    try {
        updateStatus('Checking server capabilities...');
        
        // Fetch capabilities from server
        const response = await fetch(`${config.serverUrl}${config.capabilitiesEndpoint}`);
        state.capabilities = await response.json();
        
        updateStatus(`Server ready. Real-time STT: ${state.capabilities.real_time_stt}, Real-time TTS: ${state.capabilities.real_time_tts}`);
        
        // Setup UI based on capabilities
        setupEventListeners();
        
    } catch (error) {
        updateStatus(`Error checking capabilities: ${error.message}`);
        console.error('Initialization error:', error);
    }
}

// Setup event listeners for UI elements
function setupEventListeners() {
    // Start recording button
    if (elements.startButton) {
        elements.startButton.addEventListener('click', startRecording);
        elements.startButton.disabled = false;
    }
    
    // Stop recording button
    if (elements.stopButton) {
        elements.stopButton.addEventListener('click', stopRecording);
        elements.stopButton.disabled = true;
    }
    
    // Send text button
    if (elements.sendButton && elements.textInput) {
        elements.sendButton.addEventListener('click', () => {
            const text = elements.textInput.value.trim();
            if (text) {
                sendTextMessage(text);
                elements.textInput.value = '';
            }
        });
        
        // Also handle enter key
        elements.textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                elements.sendButton.click();
            }
        });
    }
}

// Connect to WebSocket server for conversation
function connectWebSocket() {
    if (state.socket && state.socket.readyState === WebSocket.OPEN) {
        return; // Already connected
    }
    
    updateStatus('Connecting to server...');
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}${config.conversationEndpoint}`;
    
    state.socket = new WebSocket(wsUrl);
    
    state.socket.onopen = () => {
        state.connected = true;
        updateStatus('Connected to server. Ready for conversation.');
    };
    
    state.socket.onclose = () => {
        state.connected = false;
        updateStatus('Disconnected from server.');
        
        // Clean up
        if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
            state.mediaRecorder.stop();
        }
        state.recording = false;
        if (elements.startButton) elements.startButton.disabled = false;
        if (elements.stopButton) elements.stopButton.disabled = true;
    };
    
    state.socket.onerror = (error) => {
        updateStatus(`WebSocket error: ${error.message}`);
        console.error('WebSocket error:', error);
    };
    
    state.socket.onmessage = handleWebSocketMessage;
}

// Handle incoming WebSocket messages
function handleWebSocketMessage(event) {
    // Handle binary messages (audio data)
    if (event.data instanceof Blob) {
        state.audioQueue.push(event.data);
        if (!state.processingAudio) {
            processAudioQueue();
        }
        return;
    }
    
    // Handle text messages (JSON)
    try {
        const message = JSON.parse(event.data);
        
        // Log all messages for debugging
        console.log('Received message:', message);
        
        // Handle different message types
        switch (message.type) {
            case 'connection_established':
                state.sessionId = message.session_id;
                updateStatus(`Connection established. Session ID: ${state.sessionId}`);
                break;
                
            case 'transcript':
                // Interim transcript
                if (elements.transcriptDiv) {
                    elements.transcriptDiv.textContent = message.text;
                }
                break;
                
            case 'transcript_complete':
                // Final transcript
                if (elements.transcriptDiv) {
                    elements.transcriptDiv.textContent = message.text;
                }
                
                // Add user message to conversation
                addMessageToConversation('user', message.text);
                break;
                
            case 'message':
                // Streaming response from AI
                if (elements.responseDiv) {
                    if (!elements.responseDiv.dataset.responseText) {
                        elements.responseDiv.dataset.responseText = '';
                    }
                    
                    elements.responseDiv.dataset.responseText += message.text;
                    elements.responseDiv.textContent = elements.responseDiv.dataset.responseText;
                }
                break;
                
            case 'message_complete':
                // Complete AI response
                if (elements.responseDiv) {
                    elements.responseDiv.textContent = message.text;
                    elements.responseDiv.dataset.responseText = message.text;
                }
                
                // Add AI message to conversation
                addMessageToConversation('ai', message.text);
                break;
                
            case 'speech_starting':
                updateStatus('AI response audio streaming...');
                break;
                
            case 'speech_complete':
                updateStatus('AI response complete.');
                break;
                
            case 'error':
                updateStatus(`Error: ${message.error}`);
                console.error('Server error:', message.error);
                break;
                
            case 'session_complete':
                updateStatus('Session complete.');
                break;
                
            default:
                console.log(`Unhandled message type: ${message.type}`, message);
        }
    } catch (error) {
        console.error('Error parsing WebSocket message:', error, event.data);
    }
}

// Add message to conversation history
function addMessageToConversation(role, text) {
    // Add to state
    state.conversation.push({ role, text });
    
    // Update UI
    if (elements.conversationDiv) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${role}-message`;
        
        const textElement = document.createElement('p');
        textElement.textContent = text;
        
        messageElement.appendChild(textElement);
        elements.conversationDiv.appendChild(messageElement);
        
        // Scroll to bottom
        elements.conversationDiv.scrollTop = elements.conversationDiv.scrollHeight;
    }
}

// Process the queue of audio chunks
async function processAudioQueue() {
    if (state.audioQueue.length === 0) {
        state.processingAudio = false;
        return;
    }
    
    state.processingAudio = true;
    
    const audioBlob = state.audioQueue.shift();
    
    // Play the audio
    if (elements.audioPlayer) {
        const audioUrl = URL.createObjectURL(audioBlob);
        elements.audioPlayer.src = audioUrl;
        await elements.audioPlayer.play();
        
        // Clean up when done
        elements.audioPlayer.onended = () => {
            URL.revokeObjectURL(audioUrl);
            processAudioQueue(); // Process next in queue
        };
    } else {
        // If no audio player, just move to next item
        processAudioQueue();
    }
}

// Request microphone access and start recording
async function startRecording() {
    try {
        // Connect to WebSocket if not already connected
        if (!state.connected) {
            connectWebSocket();
        }
        
        // Wait for connection to establish
        if (!state.connected) {
            updateStatus('Waiting for connection...');
            await new Promise(resolve => {
                const checkConnection = () => {
                    if (state.connected) {
                        resolve();
                    } else {
                        setTimeout(checkConnection, 100);
                    }
                };
                checkConnection();
            });
        }
        
        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // Create AudioContext for processing
        state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        
        // Setup MediaRecorder
        state.mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm', // Most compatible format for browsers
        });
        
        // Handle data available event
        state.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0 && state.socket && state.socket.readyState === WebSocket.OPEN) {
                state.socket.send(event.data);
            }
        };
        
        // Start recording
        state.mediaRecorder.start(100); // Capture in 100ms chunks
        state.recording = true;
        
        // Update UI
        updateStatus('Recording... Speak now.');
        if (elements.startButton) elements.startButton.disabled = true;
        if (elements.stopButton) elements.stopButton.disabled = false;
        if (elements.transcriptDiv) elements.transcriptDiv.textContent = '';
        if (elements.responseDiv) {
            elements.responseDiv.textContent = '';
            elements.responseDiv.dataset.responseText = '';
        }
        
    } catch (error) {
        updateStatus(`Error starting recording: ${error.message}`);
        console.error('Recording error:', error);
    }
}

// Stop recording and send end signal
function stopRecording() {
    if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
        state.mediaRecorder.stop();
        
        // Send end signal to server
        if (state.socket && state.socket.readyState === WebSocket.OPEN) {
            state.socket.send(JSON.stringify({ type: 'end' }));
        }
        
        // Update UI
        updateStatus('Processing audio...');
        if (elements.startButton) elements.startButton.disabled = false;
        if (elements.stopButton) elements.stopButton.disabled = true;
    }
    
    // Stop all audio tracks
    if (state.mediaRecorder && state.mediaRecorder.stream) {
        state.mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    
    state.recording = false;
}

// Send a text message instead of voice
function sendTextMessage(text) {
    // Connect to WebSocket if not already connected
    if (!state.connected) {
        connectWebSocket();
    }
    
    if (state.socket && state.socket.readyState === WebSocket.OPEN) {
        // Update UI
        updateStatus('Sending message...');
        if (elements.transcriptDiv) elements.transcriptDiv.textContent = text;
        if (elements.responseDiv) {
            elements.responseDiv.textContent = '';
            elements.responseDiv.dataset.responseText = '';
        }
        
        // Send the text message
        state.socket.send(JSON.stringify({
            type: 'text',
            text: text
        }));
        
        // Add user message to conversation immediately
        addMessageToConversation('user', text);
    } else {
        updateStatus('Not connected to server. Please try again.');
    }
}

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', initialize);

// Cleanup when the page unloads
window.addEventListener('beforeunload', () => {
    if (state.socket && state.socket.readyState === WebSocket.OPEN) {
        state.socket.close();
    }
    
    if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
        state.mediaRecorder.stop();
    }
});
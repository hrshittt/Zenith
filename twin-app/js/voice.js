document.addEventListener('DOMContentLoaded', () => {
  const btnVoiceMode = document.getElementById('btnVoiceMode');
  const btnVoiceClose = document.getElementById('btnVoiceClose');
  const voiceOverlay = document.getElementById('voiceOverlay');
  const voiceStatus = document.getElementById('voiceStatus');
  const voiceOrbContainer = document.querySelector('.voice-orb-container');
  const voiceOrb = document.getElementById('voiceOrb');
  const btnVoiceAction = document.getElementById('btnVoiceAction');
  const iconVoiceMic = document.getElementById('iconVoiceMic');
  const iconVoiceStop = document.getElementById('iconVoiceStop');

  let recognition = null;
  let isListening = false;
  let isSpeaking = false;
  let isProcessing = false;

  // Check browser support
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn("SpeechRecognition API not supported in this browser.");
  } else {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      isListening = true;
      setVoiceState('listening');
    };

    recognition.onresult = async (event) => {
      const transcript = event.results[0][0].transcript;
      isListening = false;
      
      // Stop recognition explicitly
      recognition.stop();
      
      // Send to existing Chat API
      await processVoiceInput(transcript);
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error", event.error);
      isListening = false;
      if (!isProcessing && !isSpeaking) {
        setVoiceState('idle');
      }
    };

    recognition.onend = () => {
      isListening = false;
      if (!isProcessing && !isSpeaking) {
        setVoiceState('idle');
      }
    };
  }

  function setVoiceState(state) {
    voiceOrbContainer.className = 'voice-orb-container'; // reset
    iconVoiceMic.classList.add('hidden');
    iconVoiceStop.classList.add('hidden');

    if (state === 'idle') {
      voiceStatus.textContent = 'Tap to speak';
      iconVoiceMic.classList.remove('hidden');
    } else if (state === 'listening') {
      voiceStatus.textContent = 'Listening...';
      voiceOrbContainer.classList.add('state-listening');
      iconVoiceStop.classList.remove('hidden');
    } else if (state === 'processing') {
      voiceStatus.textContent = 'Thinking...';
      voiceOrbContainer.classList.add('state-processing');
      iconVoiceStop.classList.remove('hidden');
    } else if (state === 'speaking') {
      voiceStatus.textContent = 'Speaking...';
      voiceOrbContainer.classList.add('state-speaking');
      iconVoiceStop.classList.remove('hidden');
    }
  }

  async function processVoiceInput(text) {
    if (!text.trim()) {
      setVoiceState('idle');
      return;
    }

    isProcessing = true;
    setVoiceState('processing');

    const persona = localStorage.getItem('twin_persona') || 'individual';
    const currentSessionId = localStorage.getItem('twin_chat_session') || "";

    if (typeof addBubble === 'function') {
      addBubble('user', text);
    }
    try {
      const res = await window.api.askTwin(text, currentSessionId || null);

      if (res && res.session_id) {
        localStorage.setItem('twin_chat_session', res.session_id);
      }

      if (typeof addBubble === 'function' && res) {
        if (res.visualization && typeof suChatVizHtml === 'function') {
          const vizHtml = suChatVizHtml(res.visualization);
          if (vizHtml) {
            const vizDiv = document.createElement('div');
            vizDiv.innerHTML = vizHtml;
            const chatLog = document.getElementById('chatLog');
            if (chatLog) {
              chatLog.appendChild(vizDiv.firstElementChild);
            }
          }
        }
        addBubble('twin', res.answer);
      }
      
      if (typeof loadChatSessions === 'function') {
          loadChatSessions();
      }
      const answer = res.answer || "I'm sorry, I couldn't process that.";
      isProcessing = false;
      
      speakResponse(answer);
      
    } catch (err) {
      console.error(err);
      isProcessing = false;
      setVoiceState('idle');
    }
  }

  // Clean TTS text to remove markdown
  function cleanTextForSpeech(text) {
    return text.replace(/[*#_`]/g, '').replace(/\[.*?\]\(.*?\)/g, '').trim();
  }

  // Procedural audio reactivity simulation
  let speakingInterval = null;
  function startOrbPulseSimulation() {
    if (speakingInterval) clearInterval(speakingInterval);
    speakingInterval = setInterval(() => {
      const scale = 1.0 + (Math.random() * 0.35); // 1.0 to 1.35
      voiceOrb.style.transform = `scale(${scale})`;
    }, 100);
  }

  function stopOrbPulseSimulation() {
    if (speakingInterval) clearInterval(speakingInterval);
    voiceOrb.style.transform = `scale(1)`;
  }

  async function speakResponse(text) {
    isSpeaking = true;
    setVoiceState('speaking');
    
    try {
      const cleanText = cleanTextForSpeech(text);
      const audioUrl = await window.api.getTTS(cleanText);
      const audio = new Audio(audioUrl);
      
      audio.onplay = () => {
        startOrbPulseSimulation();
      };
      
      audio.onended = () => {
        stopOrbPulseSimulation();
        isSpeaking = false;
        setVoiceState('idle');
        URL.revokeObjectURL(audioUrl); // Clean up memory
      };
      
      audio.onerror = (e) => {
        console.error("Audio playback error", e);
        stopOrbPulseSimulation();
        isSpeaking = false;
        setVoiceState('idle');
        URL.revokeObjectURL(audioUrl);
      };
      
      await audio.play();
      
      // Store reference to allow toggling/canceling
      window.currentVoiceAudio = audio;
      
    } catch (err) {
      console.error("TTS fetch error", err);
      stopOrbPulseSimulation();
      isSpeaking = false;
      setVoiceState('idle');
    }
  }
  function stopAudio() {
    if (window.currentVoiceAudio) {
      window.currentVoiceAudio.pause();
      window.currentVoiceAudio.src = "";
      window.currentVoiceAudio = null;
    }
  }

  function toggleMic() {
    if (isListening || isSpeaking || isProcessing) {
      if (isListening && recognition) recognition.stop();
      if (isSpeaking) stopAudio();
      isProcessing = false;
      isSpeaking = false;
      isListening = false;
      stopOrbPulseSimulation();
      setVoiceState('idle');
    } else {
      if (recognition) {
        stopAudio();
        try {
          recognition.start();
        } catch(e) {}
      } else {
        alert("Your browser does not support Voice Recognition.");
      }
    }
  }

  if (btnVoiceMode) {
    btnVoiceMode.addEventListener('click', () => {
      voiceOverlay.classList.remove('hidden');
      setVoiceState('idle');
    });
  }

  if (btnVoiceClose) {
    btnVoiceClose.addEventListener('click', () => {
      if (recognition) recognition.stop();
      stopAudio();
      isListening = false;
      isSpeaking = false;
      isProcessing = false;
      stopOrbPulseSimulation();
      voiceOverlay.classList.add('hidden');
    });
  }

  if (btnVoiceAction) {
    btnVoiceAction.addEventListener('click', toggleMic);
  }
});

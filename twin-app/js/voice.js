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

    try {
      const res = await window.api.askTwin(text, currentSessionId || null);

      if (res && res.session_id) {
        localStorage.setItem('twin_chat_session', res.session_id);
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

  function speakResponse(text) {
    if (!window.speechSynthesis) {
      setVoiceState('idle');
      return;
    }

    isSpeaking = true;
    setVoiceState('speaking');
    window.speechSynthesis.cancel();

    const msg = new SpeechSynthesisUtterance(cleanTextForSpeech(text));
    
    // Attempt to pick a premium/smooth voice
    const voices = window.speechSynthesis.getVoices();
    const premiumVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Samantha') || v.name.includes('Neural')));
    if (premiumVoice) msg.voice = premiumVoice;

    msg.rate = 1.05;

    msg.onstart = () => {
      startOrbPulseSimulation();
    };

    msg.onend = () => {
      stopOrbPulseSimulation();
      isSpeaking = false;
      setVoiceState('idle');
    };

    msg.onerror = (e) => {
      console.error(e);
      stopOrbPulseSimulation();
      isSpeaking = false;
      setVoiceState('idle');
    };

    window.speechSynthesis.speak(msg);
  }

  // Workaround for voices loading async in some browsers
  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.getVoices();
    };
  }

  function toggleMic() {
    if (isListening || isSpeaking || isProcessing) {
      if (isListening && recognition) recognition.stop();
      if (isSpeaking) window.speechSynthesis.cancel();
      isProcessing = false;
      isSpeaking = false;
      isListening = false;
      stopOrbPulseSimulation();
      setVoiceState('idle');
    } else {
      if (recognition) {
        window.speechSynthesis.cancel();
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
      window.speechSynthesis.cancel();
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

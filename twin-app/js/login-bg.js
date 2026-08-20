/**
 * login-bg.js
 * Handles staggered cinematic text reveal animation for the login page branding area.
 */

document.addEventListener('DOMContentLoaded', () => {
    /* ======================================================================
       1. CINEMATIC TEXT REVEAL LOGIC
       ====================================================================== */
    const phrases = document.querySelectorAll('.cinematic-phrase');
    let currentPhraseIndex = 0;

    function transitionText() {
        const currentPhrase = phrases[currentPhraseIndex];
        currentPhrase.classList.remove('active');
        currentPhrase.classList.add('exit');

        setTimeout(() => {
            currentPhrase.classList.remove('exit');
        }, 1000); // Wait for exit animation to finish before resetting

        currentPhraseIndex = (currentPhraseIndex + 1) % phrases.length;
        const nextPhrase = phrases[currentPhraseIndex];
        
        // Stagger word reveal
        const words = nextPhrase.querySelectorAll('.word');
        words.forEach((word, index) => {
            word.style.animationDelay = `${index * 0.15}s`;
        });

        nextPhrase.classList.add('active');
    }

    if (phrases.length > 0) {
        // Initialize first phrase delays
        const initialWords = phrases[0].querySelectorAll('.word');
        initialWords.forEach((word, index) => {
            word.style.animationDelay = `${index * 0.15}s`;
        });

        // Loop phrases every 4 seconds
        setInterval(transitionText, 4000);
    }
});

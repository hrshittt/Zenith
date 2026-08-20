const translations = {
  hi: {
    "nav-product": "उत्पाद",
    "nav-insights": "अंतर्दृष्टि",
    "nav-solutions": "समाधान",
    "nav-login": "लॉग इन",
    "nav-getstarted": "शुरू करें",
    
    "hero-welcome": "में आपका स्वागत है",
    "hero-subtext": "वित्तीय वास्तविकता बनने से पहले संभावनाओं को देखें।",
    "hero-getstarted": "शुरू करें &rarr;",
    
    "dash-title": "एजेंटिक डैशबोर्ड",
    "dash-liquidity": "तरलता",
    "dash-runway": "रनवे",
    "fl-insight": "एआई अंतर्दृष्टि",
    "fl-bullish": "बुलिश ट्रेंड का पता चला",
    "fl-sim": "सिमुलेशन",
    "fl-scenario": "परिदृश्य A: +12% YoY",
    
    "twin-intelligent": "द इंटेलिजेंट रेप्लिका",
    "twin-build": "अपना वित्तीय ट्विन बनाएं",
    "twin-desc": "अपने डेटा को सुरक्षित रूप से कनेक्ट करें ताकि आपकी वित्तीय स्थिति का एक जीवंत मॉडल बन सके। अपनी संपत्ति के लिए एक भविष्य के नियंत्रण प्रणाली का अनुभव करें।",
    
    "mock-income": "आय का साधन",
    "mock-risk": "जोखिम जोखिम",
    "mock-forecast": "प्रक्षेपवक्र पूर्वानुमान",
    
    "quote-text": "“योजनाएं बेकार हैं, लेकिन योजना बनाना ही सब कुछ है।”",
    
    "mag-header-title": "वैश्विक दृष्टिकोण",
    "mag-header-desc": "रणनीतिक वित्तीय बुद्धिमत्ता, विशेष रूप से आपके लिए।",
    
    "cat-investment": "निवेश",
    "cat-economics": "अर्थशास्त्र",
    "cat-behavioral": "व्यावहारिक वित्त",
    "cat-mental": "मानसिक मॉडल",
    "cat-tech": "प्रौद्योगिकी",
    "cat-ai": "एजेंटिक एआई",
    
    "sol-title": "जटिलता के हर स्तर के लिए निर्मित।",
    "sol-indiv": "व्यक्तिगत",
    "sol-indiv-desc": "व्यक्तिगत संपत्ति का प्रबंधन करें, मासिक खर्चों को अनुकूलित करें, और बड़ी खरीदारी का अनुकरण करें।",
    "sol-startup": "स्टार्टअप",
    "sol-startup-desc": "रनवे की निगरानी करें, हायरिंग योजनाओं का मॉडल बनाएं, और अपने अगले राउंड के सटीक डाइल्यूशन का अनुकरण करें।",
    "sol-ent": "उद्यम",
    "sol-ent-desc": "ट्रेजरी प्रबंधन, एफएक्स एक्सपोज़र ट्रैकिंग, अनुपालन जोखिम, और बहु-इकाई तरलता।",
    "btn-buildyours": "अपना बनाएं",
    
    "cta-creating": "आपका वित्तीय भविष्य पहले से ही संभावनाएं पैदा कर रहा है।",
    "cta-question": "सवाल यह है कि क्या ",
    "cta-btn": "शुरू करें &rarr;"
  }
};

window.currentLang = localStorage.getItem('moneykal_lang') || 'en';
window.currentTheme = localStorage.getItem('moneykal_theme') || 'dark';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const sun = document.getElementById('theme-icon-sun');
  const moon = document.getElementById('theme-icon-moon');
  if (sun && moon) {
    if (theme === 'light') {
      sun.style.display = 'none';
      moon.style.display = 'block';
    } else {
      sun.style.display = 'block';
      moon.style.display = 'none';
    }
  }
}

function toggleTheme() {
  window.currentTheme = window.currentTheme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('moneykal_theme', window.currentTheme);
  applyTheme(window.currentTheme);
}

function applyTranslations(lang) {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    
    if (lang === 'hi' && translations.hi[key]) {
      // Store original English text if not already stored
      if (!el.hasAttribute('data-en-text')) {
        el.setAttribute('data-en-text', el.innerHTML);
      }
      el.innerHTML = translations.hi[key];
    } else {
      // Revert to English
      if (el.hasAttribute('data-en-text')) {
        el.innerHTML = el.getAttribute('data-en-text');
      }
    }
  });

  // Specifically handle the language toggle button text
  const langBtn = document.getElementById('lang-toggle');
  if (langBtn) {
    if (lang === 'hi') {
      langBtn.innerHTML = 'EN | <span style="color: var(--primary);">हिं</span>';
    } else {
      langBtn.innerHTML = '<span style="color: var(--primary);">EN</span> | हिं';
    }
  }

  // Handle typing animation string change (called in landing.js)
  if (window.updateTypewriterLanguage) {
    window.updateTypewriterLanguage(lang);
  }
}

function toggleLanguage() {
  window.currentLang = window.currentLang === 'en' ? 'hi' : 'en';
  localStorage.setItem('moneykal_lang', window.currentLang);
  applyTranslations(window.currentLang);
}

document.addEventListener('DOMContentLoaded', () => {
  // Setup lang toggle listener
  const langBtn = document.getElementById('lang-toggle');
  if (langBtn) {
    langBtn.addEventListener('click', toggleLanguage);
  }
  
  // Setup theme toggle listener
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', toggleTheme);
  }
  
  // Apply saved language immediately
  if (window.currentLang === 'hi') {
    applyTranslations('hi');
  } else {
    // Just to set the active color on EN
    applyTranslations('en');
  }
  
  // Apply saved theme immediately
  applyTheme(window.currentTheme);
});

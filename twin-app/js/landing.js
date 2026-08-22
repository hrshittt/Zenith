document.addEventListener('DOMContentLoaded', () => {
  // ==========================================
  // 1. LENIS SMOOTH SCROLLING
  // ==========================================
  const lenis = new Lenis({
    duration: 1.2,
    easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    direction: 'vertical',
    gestureDirection: 'vertical',
    smooth: true,
    mouseMultiplier: 1,
    smoothTouch: false,
    touchMultiplier: 2,
    infinite: false,
  })

  lenis.on('scroll', ScrollTrigger.update)

  gsap.ticker.add((time)=>{
    lenis.raf(time * 1000)
  })
  gsap.ticker.lagSmoothing(0)

  // ==========================================
  // 2. CUSTOM CURSOR
  // ==========================================
  const cursorDot = document.querySelector('.cursor-dot');
  const cursorOutline = document.querySelector('.cursor-outline');
  const interactables = document.querySelectorAll('a, button, [data-cursor="hover"]');

  if (cursorDot && cursorOutline && window.innerWidth > 768) {
    window.addEventListener('mousemove', (e) => {
      const posX = e.clientX;
      const posY = e.clientY;
      
      // Fast dot
      cursorDot.style.left = `${posX}px`;
      cursorDot.style.top = `${posY}px`;
      
      // Slower outline trailing
      cursorOutline.animate({
        left: `${posX}px`,
        top: `${posY}px`
      }, { duration: 500, fill: "forwards" });
    });

    interactables.forEach(el => {
      el.addEventListener('mouseenter', () => document.body.classList.add('cursor-hover'));
      el.addEventListener('mouseleave', () => document.body.classList.remove('cursor-hover'));
    });
  }

  // ==========================================
  // 3. GLOBAL CANVAS ENGINE (Wow Moment + Ambient)
  // ==========================================
  const canvas = document.getElementById('global-canvas');
  const ctx = canvas.getContext('2d', { alpha: false });
  let width, height;

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
  }
  window.addEventListener('resize', resize);
  resize();

  // Particle System (Ambient Background)
  const particles = [];
  const particleCount = window.innerWidth < 768 ? 50 : 150;
  for(let i=0; i<particleCount; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 2,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      baseAlpha: Math.random() * 0.5
    });
  }

  // Network Lines Data (The "Wow" Moment)
  // We draw a single line from bottom to center, then it splits into many paths
  let wowProgress = 0; // 0 to 1, controlled by ScrollTrigger
  const linesCount = 50;
  const paths = [];
  
  // Pre-calculate paths
  for(let i=0; i<linesCount; i++) {
    paths.push({
      controlX: (Math.random() - 0.5) * width * 1.5 + width/2,
      controlY: (Math.random() - 0.5) * height + height/2,
      endX: (Math.random() - 0.5) * width * 2 + width/2,
      endY: (Math.random() - 0.5) * height * 2,
      speed: 0.5 + Math.random(),
      isHighlight: i < 3 // 3 highlighted outcomes
    });
  }

  function drawCanvas() {
    // Clear with deep black
    ctx.fillStyle = '#050505';
    ctx.fillRect(0, 0, width, height);

    // 1. Draw Ambient Particles
    particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      if(p.x < 0) p.x = width;
      if(p.x > width) p.x = 0;
      if(p.y < 0) p.y = height;
      if(p.y > height) p.y = 0;
      
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 229, 255, ${p.baseAlpha})`;
      ctx.fill();
    });

    // 2. Draw "Wow Moment" Paths based on scroll
    if (wowProgress > 0) {
      const startX = width / 2;
      const startY = height;
      
      // Central single trunk
      const trunkEnd = height * 0.7; // Fixed point where it splits
      
      ctx.beginPath();
      ctx.moveTo(startX, startY);
      ctx.lineTo(startX, startY - (startY - trunkEnd) * Math.min(wowProgress * 5, 1));
      ctx.strokeStyle = '#00FFFF';
      ctx.lineWidth = 3;
      ctx.shadowBlur = 20;
      ctx.shadowColor = '#00FFFF';
      ctx.stroke();

      // Splitting paths
      if (wowProgress > 0.2) {
        const splitProgress = (wowProgress - 0.2) * 1.25; // Scale 0 to 1
        
        paths.forEach(p => {
          ctx.beginPath();
          ctx.moveTo(startX, trunkEnd);
          
          // Current position along the bezier curve
          const t = Math.min(splitProgress * p.speed, 1);
          
          if (t > 0) {
            // Draw curve to current t
            const cx = startX + (p.controlX - startX) * t;
            const cy = trunkEnd + (p.controlY - trunkEnd) * t;
            const ex = startX + (p.endX - startX) * t;
            const ey = trunkEnd + (p.endY - trunkEnd) * t;
            
            ctx.quadraticCurveTo(cx, cy, ex, ey);
            
            if (p.isHighlight) {
              ctx.strokeStyle = '#00FFFF'; // Cyan highlights
              ctx.lineWidth = 2;
              ctx.shadowBlur = 15;
              ctx.shadowColor = '#00FFFF';
            } else {
              // Fade out non-highlights as progress approaches 1
              const fade = Math.max(0, 1 - Math.pow(wowProgress, 4));
              ctx.strokeStyle = `rgba(0, 229, 255, ${fade * 0.3})`;
              ctx.lineWidth = 1;
              ctx.shadowBlur = 0;
            }
            ctx.stroke();
          }
        });
      }
      ctx.shadowBlur = 0; // Reset
    }

    requestAnimationFrame(drawCanvas);
  }
  drawCanvas();

  // ==========================================
  // 3.5 TYPEWRITER ANIMATION
  // ==========================================
  const typewriterContainer = document.getElementById('typewriter-container');
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (typewriterContainer && !prefersReducedMotion) {
    const textElement = typewriterContainer.querySelector('.typewriter-text');
    const fullText = "See Tomorrow. Decide Today.";
    let currentIndex = 0;
    let isDeleting = false;
    
    // Clear text immediately for typing effect
    textElement.textContent = '';

    function typeLoop() {
      let typeSpeed = isDeleting ? 30 + Math.random() * 30 : 50 + Math.random() * 50;
      
      if (!isDeleting && currentIndex === fullText.length) {
        typeSpeed = 2000; // Pause at end
        isDeleting = true;
      } else if (isDeleting && currentIndex === 0) {
        isDeleting = false;
        typeSpeed = 1000; // Pause at start
      }

      textElement.textContent = fullText.substring(0, currentIndex);

      if (isDeleting) {
        currentIndex--;
        if (currentIndex < 0) currentIndex = 0;
      } else {
        currentIndex++;
        if (currentIndex > fullText.length) currentIndex = fullText.length;
      }

      setTimeout(typeLoop, typeSpeed);
    }

    // Start typing after initial hero GSAP animation
    setTimeout(typeLoop, 1500);
  }

  // Final CTA Typewriter
  const ctaTypewriter = document.getElementById('typewriter-cta-container');
  let ctaFullText = "you can see them.";
  
  // Expose function for i18n to change the target text
  window.updateTypewriterLanguage = function(lang) {
    if (lang === 'hi') {
      ctaFullText = "आप उन्हें देख सकते हैं।";
    } else {
      ctaFullText = "you can see them.";
    }
  };

  // Set initial based on current lang
  if (window.currentLang === 'hi') {
    ctaFullText = "आप उन्हें देख सकते हैं।";
  }

  if (ctaTypewriter && !prefersReducedMotion) {
    const ctaTextElement = ctaTypewriter.querySelector('.typewriter-text-cta');
    let ctaIndex = 0;
    let ctaIsDeleting = false;
    
    ctaTextElement.textContent = '';

    function ctaTypeLoop() {
      let speed = ctaIsDeleting ? 60 + Math.random() * 30 : 80 + Math.random() * 50;
      
      if (!ctaIsDeleting && ctaIndex >= ctaFullText.length) {
        speed = 2500; // Pause at end
        ctaIsDeleting = true;
      } else if (ctaIsDeleting && ctaIndex === 0) {
        ctaIsDeleting = false;
        speed = 1000; // Pause at start
      }

      // Safeguard against string shrinking while deleting
      if (ctaIndex > ctaFullText.length) ctaIndex = ctaFullText.length;

      ctaTextElement.textContent = ctaFullText.substring(0, ctaIndex);

      if (ctaIsDeleting) {
        ctaIndex--;
        if (ctaIndex < 0) ctaIndex = 0;
      } else {
        ctaIndex++;
        if (ctaIndex > ctaFullText.length) ctaIndex = ctaFullText.length;
      }

      setTimeout(ctaTypeLoop, speed);
    }

    setTimeout(ctaTypeLoop, 1000);
  }

  // ==========================================
  // 4. GSAP SCROLL CHOREOGRAPHY - EDITORIAL
  // ==========================================
  gsap.registerPlugin(ScrollTrigger);

  // Nav Bar Blur
  ScrollTrigger.create({
    start: 'top -50',
    end: 99999,
    toggleClass: {className: 'scrolled', targets: '.landing-nav'}
  });

  // --- SCENE 01: Hero Sequence ---
  const heroTL = gsap.timeline();
  
  heroTL.fromTo('.hero-welcome-label', 
    { opacity: 0, x: -20 },
    { opacity: 1, x: 0, duration: 1, ease: 'power2.out', delay: 0.2 }
  )
  .fromTo('.hero-brand-massive', 
    { opacity: 0, y: 50, filter: 'blur(10px)' },
    { opacity: 1, y: 0, filter: 'blur(0px)', duration: 1.5, ease: 'power3.out' }, "-=0.5"
  )
  .fromTo('.hero-tagline-official', 
    { opacity: 0, y: 20 },
    { opacity: 1, y: 0, duration: 1, ease: 'power2.out' }, "-=0.8"
  )
  .fromTo('.hero-cta-group', 
    { opacity: 0, y: 20 },
    { opacity: 1, y: 0, duration: 1, ease: 'power2.out' }, "-=0.6"
  )
  .fromTo('.hero-dashboard-main',
    { opacity: 0, x: 50, rotationY: -10 },
    { opacity: 1, x: 0, rotationY: -15, duration: 1.5, ease: 'power3.out' }, "-=1.0"
  )
  .fromTo('.hero-float-card',
    { opacity: 0, y: 30, scale: 0.9 },
    { opacity: 1, y: 0, scale: 1, duration: 1, stagger: 0.3, ease: 'back.out(1.7)' }, "-=0.8"
  );

  // Floating continuous animation for cards
  gsap.to('.hero-float-card', {
    y: -15,
    duration: 3,
    yoyo: true,
    repeat: -1,
    ease: 'sine.inOut',
    stagger: {
      each: 0.5,
      from: "random"
    }
  });

  // Fade out hero content on scroll down
  gsap.to('.hero-split-container', {
    scrollTrigger: {
      trigger: '.scene-hero-new',
      start: 'top top',
      end: 'bottom top',
      scrub: true
    },
    y: -100,
    opacity: 0
  });


  // --- SCENE 03: Financial Twin Mockup ---
  const twinTL = gsap.timeline({
    scrollTrigger: {
      trigger: '.scene-twin-mockup',
      start: 'top 50%',
    }
  });

  twinTL.fromTo('.twin-text > *', 
          { opacity: 0, x: 30 }, 
          { opacity: 1, x: 0, duration: 1, stagger: 0.2 })
        .fromTo('.mockup-ui', { opacity: 0, x: -50, rotationY: 10 }, { opacity: 1, x: 0, rotationY: 0, duration: 1.2, ease: "power3.out" }, "-=0.8")
        .fromTo('.mockup-card', { opacity: 0, y: 20 }, { opacity: 1, y: 0, stagger: 0.2, duration: 0.8 }, "-=0.5")
        .fromTo('.twin-abstract-market', { opacity: 0, filter: 'blur(10px)' }, { opacity: 1, filter: 'blur(0px)', duration: 1.5, ease: "power2.out" }, "-=1.0");


  // --- SCENE 06: Solutions ---
  gsap.fromTo('.solutions-title', 
    { opacity: 0, y: 30 },
    { opacity: 1, y: 0, duration: 1, scrollTrigger: { trigger: '.scene-solutions-rich', start: 'top 70%' } }
  );

  gsap.fromTo('.type-card', 
    { opacity: 0, y: 50 },
    { opacity: 1, y: 0, stagger: 0.2, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: '.type-grid', start: 'top 70%' } }
  );

  // --- SCENE 07: Vibrant Final CTA ---
  gsap.fromTo('.final-content', 
    { opacity: 0, scale: 0.9 },
    { opacity: 1, scale: 1, duration: 1.5, ease: 'power3.out', scrollTrigger: { trigger: '.scene-final-vibrant', start: 'top 60%' } }
  );

  // Cinematic Quote Animation
  gsap.fromTo('.quote-text', 
    { opacity: 0, y: 30 }, 
    { opacity: 1, y: 0, duration: 1.5, ease: 'power3.out', scrollTrigger: { trigger: '.scene-quote', start: 'top 60%' } }
  );
  gsap.fromTo('.quote-author', 
    { opacity: 0, y: 20 }, 
    { opacity: 1, y: 0, duration: 1.5, delay: 0.4, ease: 'power3.out', scrollTrigger: { trigger: '.scene-quote', start: 'top 60%' } }
  );
});

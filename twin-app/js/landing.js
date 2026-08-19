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
      ctx.strokeStyle = '#00E5FF';
      ctx.lineWidth = 3;
      ctx.shadowBlur = 20;
      ctx.shadowColor = '#00E5FF';
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
              ctx.strokeStyle = '#00A368'; // Green highlights
              ctx.lineWidth = 2;
              ctx.shadowBlur = 15;
              ctx.shadowColor = '#00A368';
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
  // 4. GSAP SCROLL CHOREOGRAPHY
  // ==========================================
  gsap.registerPlugin(ScrollTrigger);

  // Nav Bar Blur
  ScrollTrigger.create({
    start: 'top -50',
    end: 99999,
    toggleClass: {className: 'scrolled', targets: '.landing-nav'}
  });

  // --- SCENE 01: Hero Typography Sequence ---
  const heroTL = gsap.timeline();
  
  // SEE THE FUTURE
  heroTL.fromTo('.hero-word-1', 
    { opacity: 0, filter: 'blur(10px)', scale: 1.1 },
    { opacity: 1, filter: 'blur(0px)', scale: 1, duration: 1, ease: 'power2.out' }
  )
  .to('.hero-word-1', { opacity: 0, filter: 'blur(10px)', scale: 0.9, duration: 1, delay: 0.5 })
  
  // MODEL THE OUTCOME
  .fromTo('.hero-word-2', 
    { opacity: 0, filter: 'blur(10px)', scale: 1.1 },
    { opacity: 1, filter: 'blur(0px)', scale: 1, duration: 1, ease: 'power2.out' }, "-=0.5"
  )
  .to('.hero-word-2', { opacity: 0, filter: 'blur(10px)', scale: 0.9, duration: 1, delay: 0.5 })
  
  // UNDERSTAND THE RISK
  .fromTo('.hero-word-3', 
    { opacity: 0, filter: 'blur(10px)', scale: 1.1 },
    { opacity: 1, filter: 'blur(0px)', scale: 1, duration: 1, ease: 'power2.out' }, "-=0.5"
  )
  .to('.hero-word-3', { opacity: 0, filter: 'blur(10px)', scale: 0.9, duration: 1, delay: 0.5 })
  
  // DECIDE WITH INTELLIGENCE
  .fromTo('.hero-word-4', 
    { opacity: 0, filter: 'blur(10px)', scale: 1.1 },
    { opacity: 1, filter: 'blur(0px)', scale: 1, duration: 1.5, ease: 'power3.out' }, "-=0.5"
  )
  
  // Reveal scroll indicator
  .to('.hero-scroll-indicator', { opacity: 1, duration: 1 }, "-=1");

  // Fade out hero on scroll
  gsap.to('.hero-typography', {
    scrollTrigger: {
      trigger: '.scene-hero',
      start: 'top top',
      end: 'bottom top',
      scrub: true
    },
    y: 150,
    opacity: 0
  });

  // --- SCENE 02: WOW Moment Canvas Scrub ---
  const wowTL = gsap.timeline({
    scrollTrigger: {
      trigger: '.scene-wow',
      start: 'top top',
      end: '+=3000', // Pin for 3000px of scrolling
      pin: true,
      scrub: 1 // Smooth scrubbing
    }
  });

  // Link scroll progress to canvas animation variable
  wowTL.to({val: 0}, {
    val: 1,
    duration: 10,
    onUpdate: function() {
      wowProgress = this.targets()[0].val;
    }
  }, 0);

  // Text appearance sequence during the WOW pin
  wowTL.to('.wow-text-1', { opacity: 1, filter: 'blur(0px)', duration: 1 }, 1)
       .to('.wow-text-1', { opacity: 0, filter: 'blur(10px)', duration: 1 }, 3)
       .to('.wow-text-2', { opacity: 1, filter: 'blur(0px)', duration: 1 }, 4)
       .to('.wow-text-2', { opacity: 0, filter: 'blur(10px)', duration: 1 }, 6)
       .to('.wow-text-3', { opacity: 1, filter: 'blur(0px)', duration: 1 }, 7)
       .to('.wow-text-3', { opacity: 0, filter: 'blur(10px)', duration: 1 }, 9);


  // --- SCENE 03 & 04: Story Assembly ---
  const storySteps = document.querySelectorAll('.story-step');
  storySteps.forEach(step => {
    
    // Text Reveal
    gsap.to(step.querySelector('.story-content'), {
      scrollTrigger: {
        trigger: step,
        start: 'top 70%',
      },
      opacity: 1,
      y: 0,
      duration: 1,
      ease: 'power3.out'
    });

    // Layer Assembly (if layers exist)
    const layers = step.querySelectorAll('.ui-layer');
    if (layers.length > 0) {
      gsap.to(layers, {
        scrollTrigger: {
          trigger: step,
          start: 'top 60%',
        },
        opacity: 1,
        stagger: 0.2,
        duration: 1
      });
      
      // Parallax on scroll
      gsap.to(step.querySelector('.layer-front'), {
        scrollTrigger: {
          trigger: step,
          start: 'top bottom',
          end: 'bottom top',
          scrub: true
        },
        y: -50
      });
      gsap.to(step.querySelector('.layer-back'), {
        scrollTrigger: {
          trigger: step,
          start: 'top bottom',
          end: 'bottom top',
          scrub: true
        },
        y: 50
      });
    }
  });

  // --- SCENE 06: Global Stream ---
  // Horizontal scroll for the stream
  const streamContainer = document.querySelector('.insight-stream');
  if (streamContainer) {
    const cards = document.querySelectorAll('.stream-card');
    
    // Calculate total scroll distance
    const totalWidth = cards.length * 512; // 480 width + 32 gap
    
    gsap.to(streamContainer, {
      x: () => -(totalWidth - window.innerWidth + 200),
      ease: "none",
      scrollTrigger: {
        trigger: ".scene-insights",
        start: "top top",
        end: () => `+=${totalWidth}`,
        pin: true,
        scrub: 1
      }
    });

    // Intersection observer for center scaling
    const centerObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          // Calculate distance from center of screen
          const rect = entry.target.getBoundingClientRect();
          const center = window.innerWidth / 2;
          const cardCenter = rect.left + rect.width / 2;
          const distance = Math.abs(center - cardCenter);
          
          if (distance < rect.width) {
            entry.target.classList.add('is-center');
          } else {
            entry.target.classList.remove('is-center');
          }
        }
      });
    }, {
      root: null,
      rootMargin: '0px',
      threshold: Array.from({length: 20}, (_, i) => i * 0.05) // Many thresholds for smooth triggering
    });

    cards.forEach(card => centerObserver.observe(card));
  }

  // --- SCENE 07: Solutions ---
  const typeCards = document.querySelectorAll('.type-card');
  if(typeCards.length > 0) {
    gsap.to('.solutions-title', {
      scrollTrigger: {
        trigger: '.scene-solutions',
        start: 'top 80%'
      },
      opacity: 1,
      y: 0,
      duration: 1
    });

    gsap.to(typeCards, {
      scrollTrigger: {
        trigger: '.type-grid',
        start: 'top 80%'
      },
      opacity: 1,
      y: 0,
      stagger: 0.2,
      duration: 1,
      ease: 'power3.out'
    });
  }

  // --- SCENE 08: Final CTA ---
  if(document.querySelector('.scene-final')) {
    gsap.to('.final-content', {
      scrollTrigger: {
        trigger: '.scene-final',
        start: 'top 80%',
        end: 'bottom 80%',
        scrub: true
      },
      scale: 1,
      opacity: 1
    });
  }

});

document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('solutions-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  // Configuration
  const colors = {
    cyan: 0x00FFFF,
    purple: 0x9D72FF,
    lavender: 0xE6E0FA,
    dark: 0x0A192F
  };

  // Setup Scene
  const scene = new THREE.Scene();
  // Optional subtle fog to blend things into the background
  scene.fog = new THREE.FogExp2(0x060c14, 0.0015);

  // Setup Camera
  const camera = new THREE.PerspectiveCamera(60, canvas.clientWidth / canvas.clientHeight, 0.1, 1000);
  camera.position.z = 100;
  camera.position.y = 10;

  // Setup Renderer
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setSize(canvas.clientWidth, canvas.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // performance optimization

  // --------------------------------------------------------
  // 1. PARTICLES (DATA POINTS)
  // --------------------------------------------------------
  const particleCount = 400;
  const particleGeometry = new THREE.BufferGeometry();
  const particlePositions = new Float32Array(particleCount * 3);
  const particleColors = new Float32Array(particleCount * 3);

  const color1 = new THREE.Color(colors.cyan);
  const color2 = new THREE.Color(0x00CCCC); // A slightly darker cyan for variety instead of original cyan
  const color3 = new THREE.Color(colors.purple);

  for (let i = 0; i < particleCount; i++) {
    // Distribute randomly in a wide area
    particlePositions[i * 3] = (Math.random() - 0.5) * 400;     // x
    particlePositions[i * 3 + 1] = (Math.random() - 0.5) * 200; // y
    particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 400; // z

    // Mix colors
    const rand = Math.random();
    let mixedColor = color1;
    if (rand > 0.66) mixedColor = color2;
    else if (rand > 0.33) mixedColor = color3;

    particleColors[i * 3] = mixedColor.r;
    particleColors[i * 3 + 1] = mixedColor.g;
    particleColors[i * 3 + 2] = mixedColor.b;
  }

  particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
  particleGeometry.setAttribute('color', new THREE.BufferAttribute(particleColors, 3));

  const particleMaterial = new THREE.PointsMaterial({
    size: 2,
    vertexColors: true,
    transparent: true,
    opacity: 0.6,
    blending: THREE.AdditiveBlending
  });

  const particleSystem = new THREE.Points(particleGeometry, particleMaterial);
  scene.add(particleSystem);

  // --------------------------------------------------------
  // 2. CORE BRANCHING PATHWAYS
  // --------------------------------------------------------
  const lineMaterialCyan = new THREE.LineBasicMaterial({ color: colors.cyan, transparent: true, opacity: 0.7, linewidth: 2 });
  const lineMaterialPurple = new THREE.LineBasicMaterial({ color: colors.purple, transparent: true, opacity: 0.5, linewidth: 2 });

  // Function to create a curved path between points
  function createPath(start, end, midOffset, material) {
    const curve = new THREE.QuadraticBezierCurve3(
      start,
      new THREE.Vector3((start.x + end.x) / 2 + midOffset.x, (start.y + end.y) / 2 + midOffset.y, (start.z + end.z) / 2 + midOffset.z),
      end
    );
    const points = curve.getPoints(50);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const line = new THREE.Line(geometry, material);
    return line;
  }

  const branchesGroup = new THREE.Group();

  // Root node (bottom)
  const rootPos = new THREE.Vector3(0, -60, -20);
  // Split node (center)
  const splitPos = new THREE.Vector3(0, -10, -10);
  
  // Three distinct end nodes (Individual, Startup, Enterprise)
  const end1 = new THREE.Vector3(-60, 40, -40); // Individual
  const end2 = new THREE.Vector3(0, 50, -30);   // Startup
  const end3 = new THREE.Vector3(60, 40, -40);  // Enterprise

  // Draw main trunk
  branchesGroup.add(createPath(rootPos, splitPos, new THREE.Vector3(10, 0, 10), lineMaterialCyan));
  
  // Draw branches
  branchesGroup.add(createPath(splitPos, end1, new THREE.Vector3(-20, 10, -10), lineMaterialCyan));
  branchesGroup.add(createPath(splitPos, end2, new THREE.Vector3(0, 10, 20), lineMaterialCyan));
  branchesGroup.add(createPath(splitPos, end3, new THREE.Vector3(20, 10, -10), lineMaterialPurple));

  // Add glowing spheres at the nodes
  const nodeMat = new THREE.MeshBasicMaterial({ color: colors.lavender, transparent: true, opacity: 0.8 });
  const highlightMat = new THREE.MeshBasicMaterial({ color: colors.cyan, transparent: true, opacity: 0.9 });

  // Fallback geometries for basic dots
  const createDot = (pos, material, size) => {
    // using small simple planes/spheres
    const geo = new THREE.SphereGeometry(size, 16, 16);
    const mesh = new THREE.Mesh(geo, material);
    mesh.position.copy(pos);
    return mesh;
  };

  branchesGroup.add(createDot(rootPos, nodeMat, 1.5));
  branchesGroup.add(createDot(splitPos, highlightMat, 3));
  branchesGroup.add(createDot(end1, nodeMat, 3));
  branchesGroup.add(createDot(end2, nodeMat, 3));
  branchesGroup.add(createDot(end3, nodeMat, 3));

  scene.add(branchesGroup);

  // --------------------------------------------------------
  // 3. ABSTRACT NETWORK BACKGROUND
  // --------------------------------------------------------
  const networkGroup = new THREE.Group();
  const networkMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.1 });
  
  // Create random connected nodes in the background
  const netGeo = new THREE.BufferGeometry();
  const netPoints = [];
  for(let i=0; i<30; i++) {
    const p1 = new THREE.Vector3((Math.random()-0.5)*300, (Math.random()-0.5)*150, (Math.random()-0.5)*200 - 100);
    const p2 = new THREE.Vector3(p1.x + (Math.random()-0.5)*50, p1.y + (Math.random()-0.5)*50, p1.z + (Math.random()-0.5)*50);
    netPoints.push(p1, p2);
  }
  netGeo.setFromPoints(netPoints);
  const networkLines = new THREE.LineSegments(netGeo, networkMat);
  networkGroup.add(networkLines);
  scene.add(networkGroup);

  // --------------------------------------------------------
  // INTERACTIVITY & PARALLAX
  // --------------------------------------------------------
  let mouseX = 0;
  let mouseY = 0;
  let targetX = 0;
  let targetY = 0;

  const windowHalfX = window.innerWidth / 2;
  const windowHalfY = window.innerHeight / 2;

  document.addEventListener('mousemove', (event) => {
    mouseX = (event.clientX - windowHalfX);
    mouseY = (event.clientY - windowHalfY);
  });

  // --------------------------------------------------------
  // RESIZE LOGIC
  // --------------------------------------------------------
  window.addEventListener('resize', () => {
    camera.aspect = canvas.clientWidth / canvas.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
  });

  // --------------------------------------------------------
  // ANIMATION LOOP & OBSERVER
  // --------------------------------------------------------
  let isAnimating = false;
  const clock = new THREE.Clock();

  function animate() {
    if (!isAnimating) return;
    requestAnimationFrame(animate);

    const time = clock.getElapsedTime();

    // Subtle parallax (lerp towards mouse position)
    targetX = mouseX * 0.05;
    targetY = mouseY * 0.05;
    
    camera.position.x += (targetX - camera.position.x) * 0.02;
    camera.position.y += (-targetY + 10 - camera.position.y) * 0.02; // +10 base height
    camera.lookAt(scene.position);

    // Rotate particle system slowly
    particleSystem.rotation.y = time * 0.05;
    particleSystem.rotation.x = time * 0.02;

    // Gently float the branching structure
    branchesGroup.position.y = Math.sin(time * 0.5) * 5;
    networkGroup.rotation.y = time * 0.02;

    renderer.render(scene, camera);
  }

  // Only animate when the section is visible
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        if (!isAnimating) {
          isAnimating = true;
          clock.start();
          animate();
        }
      } else {
        isAnimating = false;
        clock.stop();
      }
    });
  }, { threshold: 0.1 });

  const section = document.getElementById('account-types');
  if (section) observer.observe(section);
});

import * as T from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

export function mountSculpture(host: HTMLDivElement): () => void {
  let renderer: T.WebGLRenderer;
  try {
    renderer = new T.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
  } catch {
    host.dataset.fallback = 'true';
    return () => {};
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1;
  renderer.setClearColor(0xffffff, 0);
  renderer.domElement.className = 'object-canvas';
  host.appendChild(renderer.domElement);
  const scene = new T.Scene();
  const camera = new T.PerspectiveCamera(34, 1, 0.1, 50);
  camera.position.set(0, 0.15, 10.8);
  const generator = new T.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const environment = generator.fromScene(room, 0.04);
  room.dispose();
  generator.dispose();
  scene.environment = environment.texture;
  scene.add(new T.AmbientLight(0xffffff, 0.65));
  const light = new T.DirectionalLight(0xf4f8ff, 1.8);
  light.position.set(-3, 5, 6);
  scene.add(light);
  const warm = new T.PointLight(0xffe1b8, 12, 15);
  warm.position.set(4, 1, 3);
  scene.add(warm);
  const object = new T.Group();
  scene.add(object);
  const rear = new T.Shape();
  rear.moveTo(17, 15);
  rear.quadraticCurveTo(17, 10, 23, 13);
  rear.lineTo(40, 22);
  rear.quadraticCurveTo(47, 28, 38, 34);
  rear.lineTo(20, 47);
  rear.quadraticCurveTo(17, 50, 17, 44);
  rear.closePath();
  const front = new T.Shape();
  front.moveTo(17, 44);
  front.quadraticCurveTo(17, 36, 27, 32);
  front.lineTo(44, 25);
  front.quadraticCurveTo(52, 22, 52, 32);
  front.quadraticCurveTo(53, 39, 47, 42);
  front.lineTo(26, 52);
  front.quadraticCurveTo(17, 57, 17, 44);
  front.closePath();
  function geometry(shape: T.Shape) {
    const g = new T.ExtrudeGeometry(shape, {
      depth: 3.2,
      bevelEnabled: true,
      bevelSegments: 5,
      bevelSize: 0.65,
      bevelThickness: 0.6,
      curveSegments: 40,
      steps: 1,
    });
    g.translate(-34, -34.5, 0);
    g.scale(0.115, -0.115, 0.115);
    // A reflection changes with the camera; the colour is part of the material.
    const positions = g.getAttribute('position');
    const colours: number[] = [];
    for (let i = 0; i < positions.count; i++) {
      const amount = T.MathUtils.clamp((positions.getX(i) + 1.4) / 3.5, 0, 1);
      positions.setZ(i, positions.getZ(i) + Math.sin(amount * Math.PI) * 0.24);
      const colour = new T.Color('#4568ed').lerp(new T.Color('#ffedce'), amount * 0.82);
      colours.push(colour.r, colour.g, colour.b);
    }
    g.setAttribute('color', new T.Float32BufferAttribute(colours, 3));
    g.computeVertexNormals();
    return g;
  }
  const material = new T.MeshPhysicalMaterial({
    vertexColors: true,
    roughness: 0.15,
    metalness: 0.05,
    transmission: 0.42,
    thickness: 0.4,
    ior: 1.44,
    clearcoat: 1,
    clearcoatRoughness: 0.15,
    envMapIntensity: 0.5,
    side: T.DoubleSide,
  });
  const back = new T.Mesh(geometry(rear), material);
  back.position.z = -0.13;
  back.rotation.y = -0.09;
  object.add(back);
  const face = new T.Mesh(geometry(front), material);
  face.position.z = 0.34;
  face.rotation.y = 0.075;
  object.add(face);
  const seam = new T.QuadraticBezierCurve3(
    new T.Vector3(-1.955, -1.0925, 0.77),
    new T.Vector3(-1.955, -0.1725, 0.77),
    new T.Vector3(-0.805, 0.2875, 0.9),
  );
  const seamGeometry = new T.TubeGeometry(seam, 48, 0.018, 6, false);
  const seamMaterial = new T.MeshBasicMaterial({ color: 0xf1f9ff, transparent: true, opacity: 0.88 });
  const fold = new T.Mesh(seamGeometry, seamMaterial);
  object.add(fold);
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const pointerFine = window.matchMedia('(hover: hover) and (pointer: fine)');
  let frame = 0,
    visible = true,
    inView = true,
    cancelled = false,
    progress = 0,
    px = 0,
    py = 0;
  let began: number | null = null;
  let yaw = -0.42,
    pitch = -0.04;
  function render(now = performance.now()) {
    frame = 0;
    if (!visible || cancelled) return;
    const intro = motion.matches
      ? 1
      : began === null
        ? 0
        : T.MathUtils.smoothstep((now - began) / 1200, 0, 1);
    const targetYaw = -0.42 + (motion.matches ? 0 : px * 0.13 + progress * 0.24);
    const targetPitch = -0.04 + (motion.matches ? 0 : py * 0.08);
    yaw = T.MathUtils.lerp(yaw, targetYaw, 0.14);
    pitch = T.MathUtils.lerp(pitch, targetPitch, 0.14);
    object.rotation.set(pitch, yaw - (1 - intro) * 0.16, -0.095);
    object.position.y = -0.08 + (motion.matches ? 0 : progress * 0.18 + (1 - intro) * -0.08);
    object.scale.setScalar(1.05 - (motion.matches ? 0 : progress * 0.045));
    const count = seamGeometry.index!.count;
    seamGeometry.setDrawRange(0, Math.floor((intro * count) / 3) * 3);
    try {
      renderer.render(scene, camera);
    } catch {
      lost();
      return;
    }
    // Shader preparation can take a moment. Reveal only the first completed frame.
    if (began === null) {
      began = performance.now();
      delete host.dataset.fallback;
      host.dataset.ready = 'true';
    }
    if (intro < 1 || Math.abs(yaw - targetYaw) > 0.0005 || Math.abs(pitch - targetPitch) > 0.0005) schedule();
  }
  function schedule() {
    if (!frame && visible && !cancelled) frame = requestAnimationFrame(render);
  }
  function resize() {
    const rect = host.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    renderer.setSize(rect.width, rect.height);
    camera.aspect = rect.width / rect.height;
    // Keep the full silhouette in narrow layouts instead of cropping its edge.
    camera.position.z = 10.8 * Math.max(1, 0.85 / camera.aspect);
    camera.updateProjectionMatrix();
    schedule();
  }
  function scroll() {
    const section = host.closest('section')!;
    const rect = section.getBoundingClientRect();
    progress = T.MathUtils.clamp(-rect.top / Math.max(rect.height, 1), 0, 1);
    schedule();
  }
  function pointer(event: PointerEvent) {
    if (motion.matches || !pointerFine.matches) return;
    const rect = host.getBoundingClientRect();
    px = T.MathUtils.clamp(((event.clientX - rect.left) / rect.width) * 2 - 1, -1, 1);
    py = T.MathUtils.clamp(((event.clientY - rect.top) / rect.height) * 2 - 1, -1, 1);
    schedule();
  }
  function reset() {
    px = py = 0;
    schedule();
  }
  function visibility() {
    visible = inView && !document.hidden;
    if (visible) schedule();
    else {
      cancelAnimationFrame(frame);
      frame = 0;
    }
  }
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(host);
  const observer = new IntersectionObserver(([entry]) => {
    inView = entry.isIntersecting;
    visible = inView && !document.hidden;
    if (visible) schedule();
    else {
      cancelAnimationFrame(frame);
      frame = 0;
    }
  });
  observer.observe(host);
  host.addEventListener('pointermove', pointer);
  host.addEventListener('pointerleave', reset);
  window.addEventListener('scroll', scroll, { passive: true });
  document.addEventListener('visibilitychange', visibility);
  motion.addEventListener('change', schedule);
  function lost() {
    host.removeAttribute('data-ready');
    host.dataset.fallback = 'true';
    cancelled = true;
    cancelAnimationFrame(frame);
    frame = 0;
  }
  renderer.domElement.addEventListener('webglcontextlost', lost);
  resize();
  scroll();
  return () => {
    cancelled = true;
    cancelAnimationFrame(frame);
    observer.disconnect();
    resizeObserver.disconnect();
    host.removeEventListener('pointermove', pointer);
    host.removeEventListener('pointerleave', reset);
    window.removeEventListener('scroll', scroll);
    document.removeEventListener('visibilitychange', visibility);
    motion.removeEventListener('change', schedule);
    renderer.domElement.removeEventListener('webglcontextlost', lost);
    back.geometry.dispose();
    face.geometry.dispose();
    material.dispose();
    seamGeometry.dispose();
    seamMaterial.dispose();
    environment.dispose();
    renderer.dispose();
    renderer.domElement.remove();
    host.removeAttribute('data-ready');
  };
}

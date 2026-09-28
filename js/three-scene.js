/* ============================================================
   Nova-Band — Three.js scenes for the white & clean design
     NovaThree.initWave(canvas)    the deck's dotted-wave motif, animated
     NovaThree.initViewer(canvas)  drag-to-rotate viewer for the Blender GLB
   Both pause off-screen, respect reduced motion, and re-colour on
   the "novaband:theme" event.
   ============================================================ */
(function (global) {
  "use strict";

  var hasThree = typeof THREE !== "undefined";
  var reduced = global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function isDark() {
    return document.documentElement.getAttribute("data-theme") === "dark";
  }

  function makeRenderer(canvas) {
    var r = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, powerPreference: "low-power" });
    r.setPixelRatio(Math.min(global.devicePixelRatio || 1, 2));
    if (THREE.sRGBEncoding !== undefined) r.outputEncoding = THREE.sRGBEncoding;
    return r;
  }

  function watchVisibility(el) {
    var state = { visible: true };
    if ("IntersectionObserver" in global) {
      new IntersectionObserver(function (e) { state.visible = e[0].isIntersecting; }).observe(el);
    }
    return state;
  }

  function fitToParent(renderer, camera, canvas) {
    function resize() {
      var w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    resize();
    global.addEventListener("resize", resize);
    return resize;
  }

  /* =========================================================
     Dotted wave — the rose dot field used across the ISIF deck
     ========================================================= */
  function initWave(canvas) {
    if (!hasThree || !canvas) { if (canvas) canvas.hidden = true; return null; }
    var renderer = makeRenderer(canvas);
    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(0, 3.2, 7.4);
    camera.lookAt(0, -0.4, 0);
    fitToParent(renderer, camera, canvas);

    var NX = 150, NY = 42;
    var base = new Float32Array(NX * NY * 3);
    var pos = new Float32Array(NX * NY * 3);
    for (var i = 0; i < NX; i++) {
      for (var j = 0; j < NY; j++) {
        var k = (i * NY + j) * 3;
        base[k] = (i / (NX - 1) - 0.5) * 16;
        base[k + 1] = 0;
        base[k + 2] = (j / (NY - 1) - 0.5) * 5.5;
        pos[k] = base[k]; pos[k + 2] = base[k + 2];
      }
    }
    var geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    var mat = new THREE.PointsMaterial({
      color: isDark() ? 0x7a3f45 : 0xc9a3a3, size: 0.045, sizeAttenuation: true,
      transparent: true, opacity: 0.9, depthWrite: false
    });
    var points = new THREE.Points(geo, mat);
    points.rotation.y = -0.18;
    scene.add(points);

    document.addEventListener("novaband:theme", function () {
      mat.color.setHex(isDark() ? 0x7a3f45 : 0xc9a3a3);
    });

    var vis = watchVisibility(canvas);
    var t0 = performance.now();
    function frame(now) {
      requestAnimationFrame(frame);
      if (!vis.visible) return;
      var t = reduced ? 0 : (now - t0) / 1000;
      var a = geo.attributes.position.array;
      for (var n = 0; n < a.length; n += 3) {
        var x = base[n], z = base[n + 2];
        a[n + 1] = 0.55 * Math.sin(x * 0.42 + t * 0.7) * Math.cos(z * 0.55 - t * 0.35) +
                   0.28 * Math.sin(x * 0.9 - z * 0.6 + t * 0.9);
      }
      geo.attributes.position.needsUpdate = true;
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);
    return { material: mat };
  }

  /* =========================================================
     GLB viewer — the same Blender model as the renders and reel
     ========================================================= */
  function softEnvironment(renderer) {
    /* A white-to-warm gradient dome baked into a PMREM so the glossy
       wine case and the metal buckle have something to reflect. */
    var envScene = new THREE.Scene();
    var g = new THREE.SphereGeometry(10, 32, 16);
    var colors = [];
    var p = g.attributes.position;
    for (var i = 0; i < p.count; i++) {
      var y = p.getY(i) / 10;
      var c = new THREE.Color().setRGB(1, 0.97 + 0.03 * y, 0.95 + 0.05 * y);
      c.multiplyScalar(0.72 + 0.35 * Math.max(y, 0));
      colors.push(c.r, c.g, c.b);
    }
    g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    envScene.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide })));
    var pm = new THREE.PMREMGenerator(renderer);
    var tex = pm.fromScene(envScene, 0.04).texture;
    pm.dispose();
    return tex;
  }

  function contactShadow() {
    var c = document.createElement("canvas");
    c.width = c.height = 128;
    var x = c.getContext("2d");
    var grd = x.createRadialGradient(64, 64, 4, 64, 64, 62);
    grd.addColorStop(0, "rgba(75,7,15,0.34)");
    grd.addColorStop(1, "rgba(75,7,15,0)");
    x.fillStyle = grd;
    x.fillRect(0, 0, 128, 128);
    var m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false }));
    m.rotation.x = -Math.PI / 2;
    return m;
  }

  function initViewer(canvas, fallback) {
    function fail() {
      if (canvas) canvas.hidden = true;
      if (fallback) fallback.hidden = false;
    }
    if (!hasThree || !canvas || typeof THREE.GLTFLoader !== "function") { fail(); return null; }

    var renderer = makeRenderer(canvas);
    var scene = new THREE.Scene();
    scene.environment = softEnvironment(renderer);
    var camera = new THREE.PerspectiveCamera(30, 1, 0.01, 50);
    fitToParent(renderer, camera, canvas);

    scene.add(new THREE.HemisphereLight(0xffffff, 0xf3e3d3, 0.55));
    var key = new THREE.DirectionalLight(0xffffff, 0.9);
    key.position.set(2, 4, 3);
    scene.add(key);
    var rim = new THREE.DirectionalLight(0xffd6d6, 0.5);
    rim.position.set(-3, 2, -2);
    scene.add(rim);

    var turntable = new THREE.Group();
    scene.add(turntable);
    var shadow = contactShadow();
    scene.add(shadow);

    var leds = [];
    new THREE.GLTFLoader().load("assets/novaband.glb", function (gltf) {
      var model = gltf.scene;
      /* the model is authored in metres; normalise it to a 2-unit box */
      var box = new THREE.Box3().setFromObject(model);
      var size = box.getSize(new THREE.Vector3());
      var centre = box.getCenter(new THREE.Vector3());
      var s = 2 / Math.max(size.x, size.y, size.z);
      model.position.sub(centre).multiplyScalar(s);
      model.scale.setScalar(s);
      /* present the module face to the viewer, band slightly tilted */
      var tilt = new THREE.Group();
      tilt.add(model);
      tilt.rotation.x = 0.35;
      turntable.add(tilt);
      model.traverse(function (o) {
        if (o.isMesh && o.material && /LedGreen|LedIR/.test(o.material.name)) {
          o.material = o.material.clone();
          leds.push(o.material);
        }
      });
      var b2 = new THREE.Box3().setFromObject(turntable);
      shadow.position.y = b2.min.y - 0.01;
      shadow.scale.setScalar(2.6);
      camera.position.set(0, 0.9, 5.2);
      camera.lookAt(0, -0.05, 0);
    }, undefined, fail);

    /* drag to rotate, with inertia; gentle auto-spin when idle */
    var drag = null, velY = 0, velX = 0, idle = 0;
    canvas.addEventListener("pointerdown", function (e) {
      drag = { x: e.clientX, y: e.clientY };
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener("pointermove", function (e) {
      if (!drag) return;
      velY = (e.clientX - drag.x) * 0.008;
      velX = (e.clientY - drag.y) * 0.004;
      drag = { x: e.clientX, y: e.clientY };
      idle = 0;
    });
    function end() { drag = null; }
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);

    var vis = watchVisibility(canvas);
    var last = performance.now();
    function frame(now) {
      requestAnimationFrame(frame);
      if (!vis.visible) return;
      var dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      idle += dt;
      turntable.rotation.y += velY;
      turntable.rotation.x = Math.max(-0.5, Math.min(0.5, turntable.rotation.x + velX));
      velY *= drag ? 0.5 : 0.92;
      velX *= 0.85;
      if (!drag && idle > 1.5 && !reduced) turntable.rotation.y += dt * 0.35;
      /* PPG beat: sharp systolic spike + dicrotic bump, 1.5 Hz */
      var ph = (now / 1000 * 1.5) % 1;
      var beat = Math.exp(-14 * ph) + 0.5 * Math.exp(-16 * Math.abs(ph - 0.3));
      leds.forEach(function (m) { m.emissiveIntensity = 0.6 + beat * 2.2; });
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);
    return { scene: scene };
  }

  global.NovaThree = { initWave: initWave, initViewer: initViewer, available: hasThree };
})(window);

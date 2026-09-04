import * as THREE from 'three';

export class Viewer3D {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0b0f19);
    this.scene.fog = new THREE.FogExp2(0x0b0f19, 0.002);

    this.camera = new THREE.PerspectiveCamera(
      60,
      this.container.clientWidth / this.container.clientHeight,
      0.1,
      3000
    );
    this.camera.position.set(0, 180, 260);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.container.appendChild(this.renderer.domElement);

    this.terrainMesh = null;
    this.gridData = null;
    this.unit = 'metres';
    this.isCalibrated = false;

    this.flyMode = 'orbit'; // 'orbit', 'drone', 'topdown', 'cinematic'
    this.heightExaggeration = 1.0;
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    // WASD Movement
    this.keys = { w: false, a: false, s: false, d: false, q: false, e: false };
    this.droneSpeed = 3.0;

    // Cross section slice points
    this.slicePoints = [];
    this.sliceLine = null;

    this.setupLighting();
    this.setupEvents();
    this.createDefaultTerrain();
    this.animate();
  }

  setupLighting() {
    const ambient = new THREE.AmbientLight(0xffffff, 0.7);
    this.scene.add(ambient);

    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(200, 400, 200);
    sun.castShadow = true;
    this.scene.add(sun);

    const gridHelper = new THREE.GridHelper(800, 40, 0x00f2fe, 0x1c2438);
    gridHelper.position.y = -1.0;
    this.scene.add(gridHelper);
  }

  setupEvents() {
    window.addEventListener('resize', () => {
      if (!this.container) return;
      this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    });

    window.addEventListener('keydown', (e) => {
      const k = e.key.toLowerCase();
      if (k in this.keys) this.keys[k] = true;
    });

    window.addEventListener('keyup', (e) => {
      const k = e.key.toLowerCase();
      if (k in this.keys) this.keys[k] = false;
    });

    this.container.addEventListener('mousemove', (e) => {
      const rect = this.container.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / this.container.clientWidth) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / this.container.clientHeight) * 2 + 1;
      this.inspectTerrain();
    });

    this.container.addEventListener('click', (e) => {
      this.handleTerrainClick();
    });
  }

  createDefaultTerrain() {
    const W = 100, H = 100;
    const geometry = new THREE.PlaneGeometry(200, 200, W - 1, H - 1);
    geometry.rotateX(-Math.PI / 2);

    const pos = geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const z = pos.getZ(i);
      const y = Math.sin(x * 0.04) * Math.cos(z * 0.04) * 25 + Math.sin(x * 0.01) * 30;
      pos.setY(i, y);
    }
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      color: 0x4facfe,
      wireframe: false,
      roughness: 0.5,
      metalness: 0.1,
    });

    if (this.terrainMesh) this.scene.remove(this.terrainMesh);
    this.terrainMesh = new THREE.Mesh(geometry, material);
    this.scene.add(this.terrainMesh);
  }

  buildTerrainFromDSMGrid(grid2D, slope2D, rgbTextureUrl, unit = 'metres', isCalibrated = true) {
    this.unit = unit;
    this.isCalibrated = isCalibrated;

    const H = grid2D.length;
    const W = grid2D[0].length;

    const geometry = new THREE.PlaneGeometry(W * 2.0, H * 2.0, W - 1, H - 1);
    geometry.rotateX(-Math.PI / 2);

    const pos = geometry.attributes.position;
    for (let i = 0; i < H; i++) {
      for (let j = 0; j < W; j++) {
        const idx = i * W + j;
        const ele = grid2D[i][j];
        pos.setY(idx, ele);
      }
    }
    geometry.computeVertexNormals();

    // Texture Loader
    const textureLoader = new THREE.TextureLoader();
    textureLoader.load(rgbTextureUrl, (texture) => {
      const material = new THREE.MeshStandardMaterial({
        map: texture,
        side: THREE.DoubleSide,
        roughness: 0.6,
        metalness: 0.1,
      });

      if (this.terrainMesh) this.scene.remove(this.terrainMesh);
      this.terrainMesh = new THREE.Mesh(geometry, material);
      this.terrainMesh.castShadow = true;
      this.terrainMesh.receiveShadow = true;
      this.scene.add(this.terrainMesh);

      this.resetCamera();
    });
  }

  loadGLBMesh(glbUrl) {
    import('three/examples/jsm/loaders/GLTFLoader.js').then(({ GLTFLoader }) => {
      const loader = new GLTFLoader();
      loader.load(glbUrl, (gltf) => {
        if (this.terrainMesh) this.scene.remove(this.terrainMesh);
        this.terrainMesh = gltf.scene;

        this.terrainMesh.traverse((child) => {
          if (child.isMesh) {
            child.material.side = THREE.DoubleSide;
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });

        this.scene.add(this.terrainMesh);
        this.resetCamera();
      });
    });
  }

  resetCamera() {
    if (!this.terrainMesh) return;
    const box = new THREE.Box3().setFromObject(this.terrainMesh);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    this.camera.position.set(center.x, center.y + size.y * 1.6 + 80, center.z + size.z * 1.6 + 80);
    this.camera.lookAt(center);
  }

  setFlyMode(mode) {
    this.flyMode = mode;
    if (mode === 'topdown') {
      const box = new THREE.Box3().setFromObject(this.terrainMesh);
      const center = box.getCenter(new THREE.Vector3());
      this.camera.position.set(center.x, 400, center.z + 1);
      this.camera.lookAt(center);
    }
  }

  setExaggeration(factor) {
    this.heightExaggeration = factor;
    if (this.terrainMesh) {
      this.terrainMesh.scale.y = factor;
    }
  }

  setWireframe(enabled) {
    if (this.terrainMesh) {
      this.terrainMesh.traverse((child) => {
        if (child.isMesh && child.material) {
          child.material.wireframe = enabled;
        }
      });
    }
  }

  inspectTerrain() {
    if (!this.terrainMesh) return;
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObject(this.terrainMesh, true);

    const hudEle = document.getElementById('hud-elevation');
    const hudSlope = document.getElementById('hud-slope');

    if (intersects.length > 0) {
      const pt = intersects[0].point;
      const eleVal = pt.y.toFixed(2);
      const unitStr = this.isCalibrated ? 'm (Metres)' : 'rDSM (Relative [0-1])';

      // Estimate slope from face normal angle
      let slopeDeg = 0.0;
      if (intersects[0].face) {
        const normal = intersects[0].face.normal.clone();
        normal.transformDirection(intersects[0].object.matrixWorld);
        const angleRad = Math.acos(Math.min(1.0, Math.max(-1.0, normal.y)));
        slopeDeg = (angleRad * (180.0 / Math.PI)).toFixed(1);
      }

      if (hudEle) hudEle.innerText = `X: ${pt.x.toFixed(1)}m | Y: ${pt.z.toFixed(1)}m | Elevation: ${eleVal} ${unitStr}`;
      if (hudSlope) hudSlope.innerText = `Slope: ${slopeDeg}°`;
    }
  }

  handleTerrainClick() {
    if (!this.terrainMesh) return;
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObject(this.terrainMesh, true);

    if (intersects.length > 0) {
      const pt = intersects[0].point;
      this.slicePoints.push(pt.clone());

      if (this.slicePoints.length > 2) {
        this.slicePoints = [pt.clone()];
      }

      this.updateSliceLine();
    }
  }

  updateSliceLine() {
    if (this.sliceLine) this.scene.remove(this.sliceLine);

    if (this.slicePoints.length === 2) {
      const geometry = new THREE.BufferGeometry().setFromPoints(this.slicePoints);
      const material = new THREE.LineBasicMaterial({ color: 0x00f2fe, linewidth: 4 });
      this.sliceLine = new THREE.Line(geometry, material);
      this.scene.add(this.sliceLine);

      // Trigger profile calculation
      const p1 = this.slicePoints[0];
      const p2 = this.slicePoints[1];
      const distM = p1.distanceTo(p2).toFixed(1);
      alert(`Cross-section slice drawn!\nLength: ${distM} meters\nCheck Evaluation tab for Height Profile curve.`);
    }
  }

  toggleFullscreen() {
    if (!document.fullscreenElement) {
      this.container.requestFullscreen().catch(err => alert(err.message));
    } else {
      document.exitFullscreen();
    }
  }

  animate() {
    requestAnimationFrame(() => this.animate());

    if (this.flyMode === 'drone') {
      const dir = new THREE.Vector3();
      this.camera.getWorldDirection(dir);
      const side = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize();

      if (this.keys.w) this.camera.position.addScaledVector(dir, this.droneSpeed);
      if (this.keys.s) this.camera.position.addScaledVector(dir, -this.droneSpeed);
      if (this.keys.a) this.camera.position.addScaledVector(side, -this.droneSpeed);
      if (this.keys.d) this.camera.position.addScaledVector(side, this.droneSpeed);
      if (this.keys.q) this.camera.position.y += this.droneSpeed;
      if (this.keys.e) this.camera.position.y -= this.droneSpeed;

      // Ground altitude boundary check: prevent camera from falling infinitely below terrain
      const minAltitude = 5.0;
      if (this.camera.position.y < minAltitude) {
        this.camera.position.y = minAltitude;
      }
    } else if (this.flyMode === 'cinematic') {
      const time = Date.now() * 0.0005;
      const radius = 300;
      this.camera.position.x = Math.sin(time) * radius;
      this.camera.position.z = Math.cos(time) * radius;
      this.camera.position.y = 150 + Math.sin(time * 2) * 50;
      this.camera.lookAt(0, 20, 0);
    }

    this.renderer.render(this.scene, this.camera);
  }
}

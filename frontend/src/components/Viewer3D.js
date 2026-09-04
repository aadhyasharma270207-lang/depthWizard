import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

/**
 * DepthWizard Hero 3D Terrain Viewer Engine.
 * Converts monocular depth / DSM elevation grids into interactive, photogrammetry-grade 3D meshes.
 */
export class Viewer3D {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    this.onPointSelected = options.onPointSelected || null;
    this.onStatsUpdated = options.onStatsUpdated || null;

    // 3D Scene setup
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0b0f19);
    this.scene.fog = new THREE.FogExp2(0x0b0f19, 0.0012);

    // Camera setup
    this.camera = new THREE.PerspectiveCamera(
      55,
      this.container.clientWidth / this.container.clientHeight,
      0.1,
      5000
    );
    this.camera.position.set(0, 220, 320);

    // Renderer setup
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.container.appendChild(this.renderer.domElement);

    // Orbit Controls
    try {
      this.controls = new OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.maxPolarAngle = Math.PI / 2 - 0.02; // Prevents camera going below ground
      this.controls.minDistance = 5;
      this.controls.maxDistance = 2500;
    } catch (e) {
      console.warn('OrbitControls fallback:', e);
      this.controls = null;
    }

    // Mesh & Data State
    this.terrainMesh = null;
    this.wireframeMesh = null;
    this.contourGroup = null;
    this.gridHelper = null;
    this.heightsArray = null;

    this.elevationGrid = null;
    this.slopeGrid = null;
    this.rgbTexture = null;
    this.rawWidth = 0;
    this.rawHeight = 0;
    this.unit = 'relative'; // 'relative' or 'metres'
    this.isCalibrated = false;
    this.hasUserData = false;

    this.minElev = 0;
    this.maxElev = 1.0;
    this.meanElev = 0.5;

    // Config Options
    this.heightExaggeration = 1.0;
    this.meshResolution = 'medium'; // 'low', 'medium', 'high'
    this.colorMode = 'elevation'; // 'elevation', 'depth', 'terrain', 'solid', 'rgb'
    this.shadingMode = 'smooth'; // 'smooth', 'flat'
    this.showWireframe = false;
    this.showContour = false;
    this.contourInterval = 10;
    this.showGrid = true;

    // Raycasting & Hover HUD
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
    this.hoverMarker = null;
    this.hoverLaserLine = null;

    // Multi-Point Inspection
    this.selectedPoints = [];
    this.pointMarkersGroup = new THREE.Group();
    this.scene.add(this.pointMarkersGroup);
    this.inspectionLine = null;

    // Cinematic Flythrough Path Animation
    this.isFlying = false;
    this.flyProgress = 0;
    this.flySpeed = 0.0008;
    this.flyPathSpline = null;

    this.setupLighting();
    this.setupHoverMarker();
    this.setupEvents();
    this.animate();
  }

  setupLighting() {
    const ambient = new THREE.AmbientLight(0xffffff, 0.65);
    this.scene.add(ambient);

    // Directional Sun Light
    this.sunLight = new THREE.DirectionalLight(0xffffff, 1.25);
    this.sunLight.position.set(250, 450, 250);
    this.sunLight.castShadow = true;
    this.sunLight.shadow.mapSize.width = 2048;
    this.sunLight.shadow.mapSize.height = 2048;
    this.scene.add(this.sunLight);

    // Cyan Rim / Accent Light
    const rimLight = new THREE.DirectionalLight(0x00f2fe, 0.45);
    rimLight.position.set(-300, 200, -300);
    this.scene.add(rimLight);

    // Ground Grid Helper & Subtle 3D Axes Reference Helper
    this.gridHelper = new THREE.GridHelper(800, 40, 0x00f2fe, 0x1c2438);
    this.gridHelper.position.y = -1.0;
    this.scene.add(this.gridHelper);

    this.axesHelper = new THREE.AxesHelper(60);
    this.axesHelper.visible = false;
    this.scene.add(this.axesHelper);
  }

  handleResize() {
    if (!this.container) return;
    const width = this.container.clientWidth || window.innerWidth;
    const height = this.container.clientHeight || window.innerHeight;
    if (width > 0 && height > 0) {
      this.camera.aspect = width / height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(width, height);
    }
  }

  setupHoverMarker() {
    const dotGeo = new THREE.SphereGeometry(2.5, 16, 16);
    const dotMat = new THREE.MeshBasicMaterial({ color: 0x00f2fe, wireframe: true });
    this.hoverMarker = new THREE.Mesh(dotGeo, dotMat);
    this.hoverMarker.visible = false;
    this.scene.add(this.hoverMarker);

    const laserGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0, -100, 0),
    ]);
    const laserMat = new THREE.LineBasicMaterial({ color: 0x00f2fe, transparent: true, opacity: 0.7 });
    this.hoverLaserLine = new THREE.Line(laserGeo, laserMat);
    this.hoverLaserLine.visible = false;
    this.scene.add(this.hoverLaserLine);
  }

  setupEvents() {
    window.addEventListener('resize', () => {
      this.handleResize();
    });

    this.container.addEventListener('mousemove', (e) => {
      const rect = this.container.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / this.container.clientWidth) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / this.container.clientHeight) * 2 + 1;
      this.inspectHoverPoint(e);
    });

    this.container.addEventListener('mouseleave', () => {
      const tooltip = document.getElementById('hover-tooltip');
      if (tooltip) tooltip.style.display = 'none';
      if (this.hoverMarker) this.hoverMarker.visible = false;
      if (this.hoverLaserLine) this.hoverLaserLine.visible = false;
    });

    this.container.addEventListener('click', () => {
      this.handleTerrainClick();
    });
  }

  /**
   * Dynamic camera framing function based on terrain bounding box.
   */
  fitCameraToTerrain() {
    if (!this.terrainMesh) return;
    this.terrainMesh.geometry.computeBoundingBox();
    const box = this.terrainMesh.geometry.boundingBox;
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.z, size.y, 40);

    const dist = maxDim * 1.35;
    this.camera.position.set(
      center.x + dist * 0.6,
      center.y + dist * 0.65,
      center.z + dist * 0.85
    );
    this.camera.lookAt(center);
    if (this.controls) {
      this.controls.target.copy(center);
      this.controls.update();
    }
  }

  /**
   * Constructs a real triangulated 3D terrain BufferGeometry from 2D elevation grid.
   */
  buildTerrainFromElevationGrid(
    grid2D,
    rgbTextureUrl = null,
    slope2D = null,
    unit = 'relative',
    isCalibrated = false,
    datasetLabel = 'Custom DSM'
  ) {
    this.elevationGrid = grid2D;
    this.slopeGrid = slope2D;
    this.unit = unit;
    this.isCalibrated = isCalibrated;

    const rawH = grid2D.length;
    const rawW = grid2D[0].length;
    this.rawWidth = rawW;
    this.rawHeight = rawH;

    let stride = 1;
    if (this.meshResolution === 'low') stride = Math.max(1, Math.floor(Math.max(rawW, rawH) / 128));
    else if (this.meshResolution === 'medium') stride = Math.max(1, Math.floor(Math.max(rawW, rawH) / 256));
    else if (this.meshResolution === 'high') stride = Math.max(1, Math.floor(Math.max(rawW, rawH) / 512));

    const H = Math.floor((rawH - 1) / stride) + 1;
    const W = Math.floor((rawW - 1) / stride) + 1;

    let minE = Infinity, maxE = -Infinity, sumE = 0, count = 0;
    let validCount = 0, invalidCount = 0;
    this.heightsArray = new Float32Array(H * W);

    for (let i = 0; i < H; i++) {
      for (let j = 0; j < W; j++) {
        const rIdx = Math.min(rawH - 1, i * stride);
        const cIdx = Math.min(rawW - 1, j * stride);
        let val = grid2D[rIdx][cIdx];
        if (typeof val !== 'number' || isNaN(val) || !isFinite(val)) {
          val = 0.0;
          invalidCount++;
        } else {
          validCount++;
        }
        this.heightsArray[i * W + j] = val;
        if (val < minE) minE = val;
        if (val > maxE) maxE = val;
        sumE += val;
        count++;
      }
    }
    this.minElev = isFinite(minE) ? minE : 0;
    this.maxElev = isFinite(maxE) ? maxE : (isCalibrated ? 100 : 1.0);
    this.meanElev = count > 0 ? sumE / count : (isCalibrated ? 50 : 0.5);

    console.log(`[Viewer3D] Grid Built: ${W}x${H} | Valid Vertices: ${validCount} | Invalid Vertices: ${invalidCount}`);

    const aspectW = 300.0;
    const aspectH = (rawH / rawW) * 300.0;

    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(H * W * 3);
    const uvs = new Float32Array(H * W * 2);
    const colors = new Float32Array(H * W * 3);

    for (let i = 0; i < H; i++) {
      for (let j = 0; j < W; j++) {
        const idx = i * W + j;
        const x = (j / (W - 1) - 0.5) * aspectW;
        const z = (i / (H - 1) - 0.5) * aspectH;
        const ele = this.heightsArray[idx];

        positions[idx * 3] = x;
        positions[idx * 3 + 1] = ele * this.heightExaggeration;
        positions[idx * 3 + 2] = z;

        uvs[idx * 2] = j / (W - 1);
        uvs[idx * 2 + 1] = 1.0 - i / (H - 1);

        const normH = Math.min(1.0, Math.max(0.0, (ele - this.minElev) / (this.maxElev - this.minElev || 1.0)));
        const col = this.getElevationColor(normH);
        colors[idx * 3] = col.r;
        colors[idx * 3 + 1] = col.g;
        colors[idx * 3 + 2] = col.b;
      }
    }

    const indices = [];
    for (let i = 0; i < H - 1; i++) {
      for (let j = 0; j < W - 1; j++) {
        const a = i * W + j;
        const b = i * W + (j + 1);
        const c = (i + 1) * W + j;
        const d = (i + 1) * W + (j + 1);
        indices.push(a, c, b);
        indices.push(b, c, d);
      }
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      side: THREE.DoubleSide,
      roughness: 0.55,
      metalness: 0.15,
      flatShading: this.shadingMode === 'flat',
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    });

    if (this.terrainMesh) {
      if (this.terrainMesh.geometry) this.terrainMesh.geometry.dispose();
      if (this.terrainMesh.material) this.terrainMesh.material.dispose();
      this.scene.remove(this.terrainMesh);
    }
    if (this.wireframeMesh) {
      if (this.wireframeMesh.geometry) this.wireframeMesh.geometry.dispose();
      if (this.wireframeMesh.material) this.wireframeMesh.material.dispose();
      this.scene.remove(this.wireframeMesh);
    }
    if (this.contourGroup) this.scene.remove(this.contourGroup);

    this.terrainMesh = new THREE.Mesh(geometry, material);
    this.terrainMesh.castShadow = true;
    this.terrainMesh.receiveShadow = true;
    this.scene.add(this.terrainMesh);

    const wireGeo = new THREE.WireframeGeometry(geometry);
    const wireMat = new THREE.LineBasicMaterial({ color: 0x00f2fe, transparent: true, opacity: 0.35 });
    this.wireframeMesh = new THREE.LineSegments(wireGeo, wireMat);
    this.wireframeMesh.visible = this.showWireframe;
    this.scene.add(this.wireframeMesh);

    if (rgbTextureUrl) {
      const loader = new THREE.TextureLoader();
      loader.load(rgbTextureUrl, (tex) => {
        this.rgbTexture = tex;
        if (this.colorMode === 'rgb') {
          this.terrainMesh.material.map = tex;
          this.terrainMesh.material.vertexColors = false;
          this.terrainMesh.material.needsUpdate = true;
        }
      });
    }

    this.rebuildContourLines();
    this.fitCameraToTerrain();
    this.updateDebugPanel(H * W, indices.length / 3, rawW, rawH);

    if (this.onStatsUpdated) {
      this.onStatsUpdated({
        vertices: H * W,
        faces: indices.length / 3,
        sourceCells: rawW * rawH,
        minElev: this.minElev,
        maxElev: this.maxElev,
        meanElev: this.meanElev,
        unit: this.unit,
        isCalibrated: this.isCalibrated,
        label: datasetLabel,
      });
    }
  }

  updateDebugPanel(verts, tris, rawW, rawH) {
    const dbgRenderer = document.getElementById('dbg-renderer');
    const dbgDsm = document.getElementById('dbg-dsm');
    const dbgMesh = document.getElementById('dbg-mesh');
    const dbgVerts = document.getElementById('dbg-verts');
    const dbgTris = document.getElementById('dbg-tris');
    const dbgRange = document.getElementById('dbg-range');
    const dbgWebgl = document.getElementById('dbg-webgl');

    if (dbgRenderer) dbgRenderer.style.color = 'var(--accent-green)';
    if (dbgDsm) {
      dbgDsm.innerText = 'READY';
      dbgDsm.style.color = 'var(--accent-green)';
    }
    if (dbgMesh) {
      dbgMesh.innerText = `${rawW}x${rawH}`;
      dbgMesh.style.color = 'var(--accent-cyan)';
    }
    if (dbgVerts) dbgVerts.innerText = verts.toLocaleString();
    if (dbgTris) dbgTris.innerText = tris.toLocaleString();
    if (dbgRange) dbgRange.innerText = `${this.minElev.toFixed(1)} – ${this.maxElev.toFixed(1)} ${this.unit === 'metres' ? 'm' : 'rDSM'}`;
    if (dbgWebgl) dbgWebgl.style.color = 'var(--accent-green)';
  }

  getElevationColor(normH) {
    const clamped = Math.min(1.0, Math.max(0.0, normH));
    const color = new THREE.Color();
    
    // Smooth 5-stop turbo terrain gradient:
    // 0.00: Deep Purple (#3b0764)
    // 0.25: Vibrant Cyan (#06b6d4)
    // 0.50: Emerald Green (#10b981)
    // 0.75: Golden Yellow (#f59e0b)
    // 1.00: Crimson Red (#ef4444)
    const c0 = new THREE.Color(0x3b0764);
    const c1 = new THREE.Color(0x06b6d4);
    const c2 = new THREE.Color(0x10b981);
    const c3 = new THREE.Color(0xf59e0b);
    const c4 = new THREE.Color(0xef4444);

    if (clamped < 0.25) {
      color.copy(c0).lerp(c1, clamped / 0.25);
    } else if (clamped < 0.50) {
      color.copy(c1).lerp(c2, (clamped - 0.25) / 0.25);
    } else if (clamped < 0.75) {
      color.copy(c2).lerp(c3, (clamped - 0.50) / 0.25);
    } else {
      color.copy(c3).lerp(c4, (clamped - 0.75) / 0.25);
    }
    return color;
  }

  setColorMode(mode) {
    this.colorMode = mode;
    if (!this.terrainMesh || !this.terrainMesh.geometry) return;

    const geo = this.terrainMesh.geometry;
    const pos = geo.attributes.position;
    const colors = geo.attributes.color;
    if (!pos || !colors) return;
    const count = pos.count;

    if (mode === 'rgb' && this.rgbTexture) {
      this.terrainMesh.material.map = this.rgbTexture;
      this.terrainMesh.material.vertexColors = false;
    } else {
      this.terrainMesh.material.map = null;
      this.terrainMesh.material.vertexColors = true;

      for (let i = 0; i < count; i++) {
        const ele = pos.getY(i) / (this.heightExaggeration || 1.0);
        const normH = Math.min(1.0, Math.max(0.0, (ele - this.minElev) / (this.maxElev - this.minElev || 1.0)));

        let c = new THREE.Color();
        if (mode === 'elevation') {
          c = this.getElevationColor(normH);
        } else if (mode === 'depth') {
          c.setRGB(normH, normH, normH);
        } else if (mode === 'terrain') {
          if (normH < 0.15) c.setHex(0x1a365d);
          else if (normH < 0.45) c.setHex(0x2f855a);
          else if (normH < 0.75) c.setHex(0x975a16);
          else c.setHex(0xedf2f7);
        } else if (mode === 'solid') {
          c.setHex(0x4a5568);
        }

        colors.setXYZ(i, c.r, c.g, c.b);
      }
      colors.needsUpdate = true;
    }

    this.terrainMesh.material.needsUpdate = true;
  }

  rebuildContourLines() {
    if (this.contourGroup) this.scene.remove(this.contourGroup);
    if (!this.showContour || !this.terrainMesh || !this.terrainMesh.geometry) return;

    this.contourGroup = new THREE.Group();
    const interval = this.contourInterval || 10;
    const stepMin = Math.ceil(this.minElev / interval) * interval;
    const stepMax = Math.floor(this.maxElev / interval) * interval;

    const geo = this.terrainMesh.geometry;
    const pos = geo.attributes.position;
    const index = geo.index;
    if (!pos || !index) return;

    const contourPoints = [];
    for (let targetZ = stepMin; targetZ <= stepMax; targetZ += interval) {
      const scaledTarget = targetZ * this.heightExaggeration;
      for (let i = 0; i < index.count; i += 3) {
        const i1 = index.getX(i);
        const i2 = index.getX(i + 1);
        const i3 = index.getX(i + 2);

        const y1 = pos.getY(i1), y2 = pos.getY(i2), y3 = pos.getY(i3);

        const p1 = new THREE.Vector3(pos.getX(i1), y1, pos.getZ(i1));
        const p2 = new THREE.Vector3(pos.getX(i2), y2, pos.getZ(i2));
        const p3 = new THREE.Vector3(pos.getX(i3), y3, pos.getZ(i3));

        const isects = [];
        this.checkEdgeIntersect(p1, p2, scaledTarget, isects);
        this.checkEdgeIntersect(p2, p3, scaledTarget, isects);
        this.checkEdgeIntersect(p3, p1, scaledTarget, isects);

        if (isects.length === 2) {
          contourPoints.push(isects[0], isects[1]);
        }
      }
    }

    if (contourPoints.length > 0) {
      const contourGeo = new THREE.BufferGeometry().setFromPoints(contourPoints);
      const contourMat = new THREE.LineBasicMaterial({ color: 0x00f2fe, linewidth: 2, transparent: true, opacity: 0.8 });
      const contourLines = new THREE.LineSegments(contourGeo, contourMat);
      this.contourGroup.add(contourLines);
      this.scene.add(this.contourGroup);
    }
  }

  checkEdgeIntersect(pA, pB, targetY, outIsects) {
    if ((pA.y <= targetY && pB.y >= targetY) || (pA.y >= targetY && pB.y <= targetY)) {
      if (Math.abs(pA.y - pB.y) > 0.0001) {
        const t = (targetY - pA.y) / (pB.y - pA.y);
        const pt = new THREE.Vector3().lerpVectors(pA, pB, t);
        outIsects.push(pt);
      }
    }
  }

  setExaggeration(factor) {
    this.heightExaggeration = factor;
    if (this.terrainMesh && this.heightsArray) {
      const geo = this.terrainMesh.geometry;
      const pos = geo.attributes.position;
      const count = pos.count;

      for (let i = 0; i < count; i++) {
        pos.setY(i, this.heightsArray[i] * factor);
      }
      pos.needsUpdate = true;
      geo.computeVertexNormals();

      if (this.wireframeMesh) {
        this.wireframeMesh.geometry.dispose();
        this.wireframeMesh.geometry = new THREE.WireframeGeometry(geo);
      }
      this.rebuildContourLines();
    } else if (this.elevationGrid) {
      this.buildTerrainFromElevationGrid(
        this.elevationGrid,
        null,
        this.slopeGrid,
        this.unit,
        this.isCalibrated,
        'Custom DSM'
      );
    }
  }

  setMeshResolution(res) {
    this.meshResolution = res;
    if (this.elevationGrid) {
      this.buildTerrainFromElevationGrid(
        this.elevationGrid,
        null,
        this.slopeGrid,
        this.unit,
        this.isCalibrated,
        'Custom DSM'
      );
    }
  }

  setWireframe(enabled) {
    this.showWireframe = enabled;
    if (this.wireframeMesh) this.wireframeMesh.visible = enabled;
  }

  setContour(enabled, interval = 10) {
    this.showContour = enabled;
    this.contourInterval = interval;
    this.rebuildContourLines();
  }

  setShadingMode(mode) {
    this.shadingMode = mode;
    if (this.terrainMesh && this.terrainMesh.material) {
      this.terrainMesh.material.flatShading = mode === 'flat';
      this.terrainMesh.material.needsUpdate = true;
    }
  }

  setGridVisible(enabled) {
    this.showGrid = enabled;
    if (this.gridHelper) this.gridHelper.visible = enabled;
  }

  /**
   * Raycasting & Hover Inspection HUD (Real Elevation Unexaggerated)
   */
  inspectHoverPoint(e = null) {
    if (!this.terrainMesh) return;
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObject(this.terrainMesh, true);

    const hudElev = document.getElementById('hud-elevation');
    const hudSlope = document.getElementById('hud-slope');
    const hudPos = document.getElementById('hud-pos');
    const tooltip = document.getElementById('hover-tooltip');
    const ttElev = document.getElementById('tt-elev');
    const ttSlope = document.getElementById('tt-slope');
    const ttPos = document.getElementById('tt-pos');

    if (intersects.length > 0) {
      const pt = intersects[0].point;
      const realEle = pt.y / (this.heightExaggeration || 1.0);
      const isMetric = this.isCalibrated || this.unit === 'metres';
      const elevText = isMetric
        ? `Elevation: <strong>${realEle.toFixed(2)} m</strong> (Metric DSM)`
        : `Relative Elevation: <strong>${realEle.toFixed(2)}</strong> (rDSM [0-1])`;

      let slopeDeg = '0.0';
      if (intersects[0].face) {
        const norm = intersects[0].face.normal.clone();
        norm.transformDirection(intersects[0].object.matrixWorld);
        const rad = Math.acos(Math.min(1.0, Math.max(-1.0, norm.y)));
        slopeDeg = (rad * (180.0 / Math.PI)).toFixed(1);
      }

      this.hoverMarker.position.copy(pt);
      this.hoverMarker.visible = true;

      const laserPositions = this.hoverLaserLine.geometry.attributes.position;
      laserPositions.setXYZ(0, pt.x, pt.y, pt.z);
      laserPositions.setXYZ(1, pt.x, -2.0, pt.z);
      laserPositions.needsUpdate = true;
      this.hoverLaserLine.visible = true;

      if (hudElev) hudElev.innerHTML = elevText;
      if (hudSlope) hudSlope.innerText = `Slope: ${slopeDeg}°`;
      if (hudPos) hudPos.innerText = `X: ${pt.x.toFixed(1)} | Z: ${pt.z.toFixed(1)}`;

      if (tooltip && e) {
        tooltip.style.display = 'block';
        tooltip.style.left = `${e.clientX + 16}px`;
        tooltip.style.top = `${e.clientY + 16}px`;
        if (ttElev) ttElev.innerHTML = `Elev: ${realEle.toFixed(2)}${isMetric ? 'm' : ''}`;
        if (ttSlope) ttSlope.innerText = `Slope: ${slopeDeg}°`;
        if (ttPos) ttPos.innerText = `X: ${pt.x.toFixed(1)} | Z: ${pt.z.toFixed(1)}`;
      }
    } else {
      this.hoverMarker.visible = false;
      this.hoverLaserLine.visible = false;
      if (tooltip) tooltip.style.display = 'none';
    }
  }

  handleTerrainClick() {
    if (!this.terrainMesh) return;
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObject(this.terrainMesh, true);

    if (intersects.length > 0) {
      const pt = intersects[0].point.clone();
      const realEle = pt.y / (this.heightExaggeration || 1.0);

      this.selectedPoints.push({ point: pt, elevation: realEle });
      if (this.selectedPoints.length > 4) {
        this.selectedPoints.shift();
      }

      this.renderPointMarkers();
      if (this.onPointSelected) this.onPointSelected(this.selectedPoints);
    }
  }

  renderPointMarkers() {
    while (this.pointMarkersGroup.children.length > 0) {
      this.pointMarkersGroup.remove(this.pointMarkersGroup.children[0]);
    }
    if (this.inspectionLine) this.scene.remove(this.inspectionLine);

    const linePoints = [];
    this.selectedPoints.forEach((item) => {
      const p = item.point;
      linePoints.push(p);

      const pinGeo = new THREE.CylinderGeometry(0.5, 2.5, 12, 16);
      const pinMat = new THREE.MeshStandardMaterial({ color: 0x00f2fe, emissive: 0x00f2fe, emissiveIntensity: 0.5 });
      const pinMesh = new THREE.Mesh(pinGeo, pinMat);
      pinMesh.position.set(p.x, p.y + 6, p.z);
      this.pointMarkersGroup.add(pinMesh);
    });

    if (linePoints.length >= 2) {
      const lineGeo = new THREE.BufferGeometry().setFromPoints(linePoints);
      const lineMat = new THREE.LineBasicMaterial({ color: 0x00f2fe, linewidth: 3 });
      this.inspectionLine = new THREE.Line(lineGeo, lineMat);
      this.scene.add(this.inspectionLine);
    }
  }

  clearSelectedPoints() {
    this.selectedPoints = [];
    this.renderPointMarkers();
    if (this.onPointSelected) this.onPointSelected([]);
  }

  resetCamera() {
    this.fitCameraToTerrain();
  }

  setCameraPreset(mode) {
    if (!this.terrainMesh) return;
    const box = new THREE.Box3().setFromObject(this.terrainMesh);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.z, size.y);

    if (mode === 'topdown') {
      this.camera.position.set(center.x, center.y + maxDim * 1.6, center.z + 0.1);
      this.camera.lookAt(center);
    } else if (mode === 'perspective') {
      this.camera.position.set(center.x + maxDim * 0.8, center.y + maxDim * 0.6, center.z + maxDim * 0.8);
      this.camera.lookAt(center);
    } else if (mode === 'lowfly') {
      this.camera.position.set(center.x - maxDim * 0.4, center.y + size.y * 0.4 + 20, center.z + maxDim * 0.4);
      this.camera.lookAt(center.x, center.y + 20, center.z);
    } else if (mode === 'highfly') {
      this.camera.position.set(center.x, center.y + maxDim * 2.0, center.z + maxDim * 1.2);
      this.camera.lookAt(center);
    } else if (mode === 'inspection') {
      this.camera.position.set(center.x + 60, center.y + 45, center.z + 60);
      this.camera.lookAt(center);
    }

    if (this.controls) {
      this.controls.target.copy(center);
      this.controls.update();
    }
  }

  startFlythrough(speedMode = 'normal') {
    if (!this.terrainMesh) return;
    this.isFlying = true;
    this.flySpeed = speedMode === 'slow' ? 0.0004 : speedMode === 'fast' ? 0.0016 : 0.0008;

    const box = new THREE.Box3().setFromObject(this.terrainMesh);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.z) * 0.75 + 60;

    const points = [];
    for (let i = 0; i <= 8; i++) {
      const angle = (i / 8) * Math.PI * 2;
      const x = center.x + Math.cos(angle) * radius;
      const z = center.z + Math.sin(angle) * radius;
      const y = center.y + size.y * 0.5 + 70 + Math.sin(angle * 3) * 25;
      points.push(new THREE.Vector3(x, y, z));
    }
    this.flyPathSpline = new THREE.CatmullRomCurve3(points, true);
  }

  pauseFlythrough() {
    this.isFlying = false;
  }

  stopFlythrough() {
    this.isFlying = false;
    this.flyProgress = 0;
    this.fitCameraToTerrain();
  }

  loadGLBMesh(glbUrl) {
    import('three/examples/jsm/loaders/GLTFLoader.js').then(({ GLTFLoader }) => {
      const loader = new GLTFLoader();
      loader.load(glbUrl, (gltf) => {
        if (this.terrainMesh) this.scene.remove(this.terrainMesh);
        if (this.wireframeMesh) this.scene.remove(this.wireframeMesh);

        let targetMesh = null;
        gltf.scene.traverse((child) => {
          if (child.isMesh && !targetMesh) {
            targetMesh = child;
          }
        });

        if (targetMesh) {
          this.terrainMesh = targetMesh;
          this.terrainMesh.material.side = THREE.DoubleSide;
          this.terrainMesh.castShadow = true;
          this.terrainMesh.receiveShadow = true;

          const wireGeo = new THREE.WireframeGeometry(targetMesh.geometry);
          const wireMat = new THREE.LineBasicMaterial({ color: 0x00f2fe, transparent: true, opacity: 0.35 });
          this.wireframeMesh = new THREE.LineSegments(wireGeo, wireMat);
          this.wireframeMesh.visible = this.showWireframe;
          this.scene.add(this.wireframeMesh);
        } else {
          this.terrainMesh = gltf.scene;
        }

        this.scene.add(this.terrainMesh);
        this.fitCameraToTerrain();
      });
    });
  }

  async fetchGridAndBuildTerrain(jobId) {
    const emptyState = document.getElementById('viewer-empty-state');
    const loadingState = document.getElementById('viewer-loading-state');
    const stepData = document.getElementById('step-data');
    const stepMesh = document.getElementById('step-mesh');
    const stepNormals = document.getElementById('step-normals');
    const stepColors = document.getElementById('step-colors');
    const stepCamera = document.getElementById('step-camera');

    if (emptyState) emptyState.style.display = 'none';
    if (loadingState) loadingState.style.display = 'flex';

    if (stepData) stepData.innerHTML = '🟡 Loading elevation grid data...';
    if (stepMesh) stepMesh.innerHTML = '⚪ Building 3D mesh geometry...';
    if (stepNormals) stepNormals.innerHTML = '⚪ Computing vertex normals...';
    if (stepColors) stepColors.innerHTML = '⚪ Applying elevation colors...';
    if (stepCamera) stepCamera.innerHTML = '⚪ Framing camera frustum...';

    try {
      const res = await fetch(`/api/jobs/${jobId}/grid?max_size=512`);
      if (!res.ok) throw new Error('Grid fetch failed');
      const data = await res.json();

      if (stepData) stepData.innerHTML = '🟢 Elevation data loaded';
      if (stepMesh) stepMesh.innerHTML = '🟡 Building 3D mesh geometry...';
      await new Promise(r => setTimeout(r, 60));

      const previewUrl = `/api/jobs/${jobId}/preview`;
      
      if (stepNormals) stepNormals.innerHTML = '🟡 Computing vertex normals...';
      if (stepColors) stepColors.innerHTML = '🟡 Applying elevation colors...';

      this.buildTerrainFromElevationGrid(
        data.elevations,
        previewUrl,
        null,
        data.unit,
        data.is_georeferenced,
        `Job ${jobId}`
      );

      if (stepMesh) stepMesh.innerHTML = '🟢 Mesh geometry created';
      if (stepNormals) stepNormals.innerHTML = '🟢 Vertex normals computed';
      if (stepColors) stepColors.innerHTML = '🟢 Elevation colors applied';
      if (stepCamera) stepCamera.innerHTML = '🟢 Camera frustum framed';

      await new Promise(r => setTimeout(r, 180));
      if (loadingState) loadingState.style.display = 'none';
      this.hasUserData = true;
    } catch (err) {
      console.warn('Fallback GLB loader for job:', jobId, err);
      this.loadGLBMesh(`/api/jobs/${jobId}/mesh`);
      if (loadingState) loadingState.style.display = 'none';
      this.hasUserData = true;
    }
  }

  toggleFullscreen() {
    if (!document.fullscreenElement) {
      this.container.requestFullscreen().catch((err) => alert(err.message));
    } else {
      document.exitFullscreen();
    }
  }

  animate() {
    requestAnimationFrame(() => this.animate());

    if (this.controls && !this.isFlying) {
      this.controls.update();
    }

    if (this.isFlying && this.flyPathSpline) {
      this.flyProgress += this.flySpeed;
      if (this.flyProgress > 1.0) this.flyProgress = 0;

      const pos = this.flyPathSpline.getPointAt(this.flyProgress);
      const lookAtPt = this.flyPathSpline.getPointAt((this.flyProgress + 0.03) % 1.0);

      this.camera.position.copy(pos);
      this.camera.lookAt(lookAtPt);
      if (this.controls) this.controls.target.copy(lookAtPt);
    }

    const compassDir = document.getElementById('compass-arrow');
    if (compassDir) {
      const dir = new THREE.Vector3();
      this.camera.getWorldDirection(dir);
      const angleDeg = (Math.atan2(dir.x, dir.z) * (180 / Math.PI)).toFixed(0);
      compassDir.style.transform = `rotate(${angleDeg}deg)`;
    }

    const camAltEl = document.getElementById('hud-cam-alt');
    if (camAltEl) {
      camAltEl.innerText = `Cam Alt: ${this.camera.position.y.toFixed(0)}m`;
    }

    this.renderer.render(this.scene, this.camera);
  }
}


import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

import type { VolatilitySurface } from '../api/types';
import { cssColor } from '../utilities/cssColor';
import type { MotionLevel } from '../utilities/motionController';
import { SceneController } from './sceneController';

const WIDTH = 60;
const DEPTH = 36;
const HEIGHT = 22;

/** The implied volatility surface as a coloured 3D mesh: strike across, expiry going back, volatility as height. */
export class SurfaceScene extends SceneController {
  private readonly controls: OrbitControls;
  private readonly group = new THREE.Group();
  private readonly surfaceMaterial: THREE.MeshStandardMaterial;
  private readonly wireMaterial: THREE.LineBasicMaterial;
  private readonly lowColor = new THREE.Color();
  private readonly highColor = new THREE.Color();
  private readonly labelTextures: THREE.Texture[] = [];
  private surface: VolatilitySurface | null = null;

  /**
   * Builds the empty scene with its lights and orbit controls.
   * @param canvas The canvas to draw on, which also receives the pointer for orbiting.
   * @param level The animation intensity: maximal turns the scene slowly by itself.
   * @throws Error when the browser cannot create a WebGL context.
   */
  constructor(canvas: HTMLCanvasElement, level: MotionLevel) {
    super(canvas, 45);
    this.surfaceMaterial = new THREE.MeshStandardMaterial({
      vertexColors: true,
      side: THREE.DoubleSide,
      roughness: 0.55,
      metalness: 0.1,
      transparent: true,
      opacity: 0.92,
    });
    this.wireMaterial = new THREE.LineBasicMaterial({
      transparent: true,
      opacity: 0.35,
    });
    this.scene.add(this.group);
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const light = new THREE.DirectionalLight(0xffffff, 1.2);
    light.position.set(-20, 50, 40);
    this.scene.add(light);
    this.camera.position.set(-46, 40, 62);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.target.set(0, HEIGHT * 0.35, 0);
    this.controls.autoRotate = level === 'maximal';
    this.controls.autoRotateSpeed = 0.4;
    this.applyTheme();
  }

  /**
   * Replaces the surface shown.
   * @param surface The surface from the server.
   */
  setSurface(surface: VolatilitySurface): void {
    this.surface = surface;
    this.rebuild();
  }

  /** Re-reads the theme's colours and rebuilds the mesh with them. */
  applyTheme(): void {
    this.lowColor.set(cssColor.read('--second', '#64b5f6'));
    this.highColor.set(cssColor.read('--accent', '#ff8a65'));
    this.wireMaterial.color.set(cssColor.read('--ink', '#e8eaed'));
    if (this.surface !== null) {
      this.rebuild();
    }
  }

  /**
   * Lets the orbit controls glide and turn the scene.
   * @param elapsedSeconds Seconds since the scene started.
   * @param deltaSeconds Seconds since the previous frame.
   */
  protected update(elapsedSeconds: number, deltaSeconds: number): void {
    void elapsedSeconds;
    void deltaSeconds;
    this.controls.update();
  }

  /** Stops the orbit controls and frees the materials and label textures. */
  protected disposeResources(): void {
    this.controls.dispose();
    this.clearGroup();
    this.surfaceMaterial.dispose();
    this.wireMaterial.dispose();
  }

  /** Removes the previous mesh, wireframe and labels, freeing their geometries and textures. */
  private clearGroup(): void {
    for (const child of [...this.group.children]) {
      this.group.remove(child);
      if (child instanceof THREE.Mesh || child instanceof THREE.LineSegments) {
        child.geometry.dispose();
      }
      if (child instanceof THREE.Sprite) {
        child.material.dispose();
      }
    }
    for (const texture of this.labelTextures) {
      texture.dispose();
    }
    this.labelTextures.length = 0;
  }

  /** Builds the mesh from the surface: one vertex per strike and expiry, and a triangle pair wherever all four corners have a value. */
  private rebuild(): void {
    this.clearGroup();
    const surface = this.surface;
    if (surface === null || surface.strikes.length < 2 || surface.expiries.length < 1) {
      return;
    }
    let lowest = Infinity;
    let highest = -Infinity;
    for (const row of surface.volatility) {
      for (const value of row) {
        if (value !== null) {
          lowest = Math.min(lowest, value);
          highest = Math.max(highest, value);
        }
      }
    }
    if (!Number.isFinite(lowest)) {
      return;
    }
    const range = highest - lowest || 1;
    const columns = surface.strikes.length;
    const rowsCount = Math.max(surface.expiries.length, 2);
    const positions: number[] = [];
    const colors: number[] = [];
    const color = new THREE.Color();
    for (let row = 0; row < rowsCount; row += 1) {
      const values = surface.volatility[Math.min(row, surface.volatility.length - 1)];
      for (let column = 0; column < columns; column += 1) {
        const value = values[column];
        const x = (column / (columns - 1) - 0.5) * WIDTH;
        const z = (row / (rowsCount - 1) - 0.5) * DEPTH;
        const share = value === null ? 0 : (value - lowest) / range;
        positions.push(x, value === null ? 0 : share * HEIGHT, z);
        color.copy(this.lowColor).lerp(this.highColor, share);
        colors.push(color.r, color.g, color.b);
      }
    }
    const indices: number[] = [];
    for (let row = 0; row < rowsCount - 1; row += 1) {
      const upper = surface.volatility[Math.min(row, surface.volatility.length - 1)];
      const lower = surface.volatility[Math.min(row + 1, surface.volatility.length - 1)];
      for (let column = 0; column < columns - 1; column += 1) {
        if (upper[column] === null || upper[column + 1] === null || lower[column] === null || lower[column + 1] === null) {
          continue;
        }
        const topLeft = row * columns + column;
        const topRight = topLeft + 1;
        const bottomLeft = topLeft + columns;
        const bottomRight = bottomLeft + 1;
        indices.push(topLeft, bottomLeft, topRight, topRight, bottomLeft, bottomRight);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    this.group.add(new THREE.Mesh(geometry, this.surfaceMaterial));
    this.group.add(new THREE.LineSegments(new THREE.WireframeGeometry(geometry), this.wireMaterial));
    this.addLabels(surface, lowest, highest, rowsCount);
  }

  /**
   * Adds text labels for a few strikes along the front edge, each expiry along the side, and the volatility range.
   * @param surface The surface.
   * @param lowest The lowest volatility shown.
   * @param highest The highest volatility shown.
   * @param rowsCount How many rows the mesh has.
   */
  private addLabels(surface: VolatilitySurface, lowest: number, highest: number, rowsCount: number): void {
    const ink = cssColor.read('--ink-muted', '#9aa0a6');
    const accent = cssColor.read('--accent', '#ff8a65');
    const columns = surface.strikes.length;
    const step = Math.max(1, Math.round(columns / 6));
    for (let column = 0; column < columns; column += step) {
      const x = (column / (columns - 1) - 0.5) * WIDTH;
      this.addLabel(String(surface.strikes[column]), new THREE.Vector3(x, -1.5, DEPTH / 2 + 3), ink);
    }
    surface.expiries.forEach((expiry, row) => {
      const z = (row / (rowsCount - 1) - 0.5) * DEPTH;
      this.addLabel(expiry.expiry_date.slice(5), new THREE.Vector3(WIDTH / 2 + 5, 0, z), ink);
    });
    this.addLabel(`${highest.toFixed(1)}%`, new THREE.Vector3(-WIDTH / 2 - 5, HEIGHT, -DEPTH / 2), accent);
    this.addLabel(`${lowest.toFixed(1)}%`, new THREE.Vector3(-WIDTH / 2 - 5, 0, -DEPTH / 2), ink);
  }

  /**
   * Adds one text label that always faces the camera.
   * @param text The text.
   * @param position Where to place it.
   * @param color The text colour.
   */
  private addLabel(text: string, position: THREE.Vector3, color: string): void {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    const context = canvas.getContext('2d');
    if (context === null) {
      return;
    }
    context.font = '500 30px Roboto, sans-serif';
    context.fillStyle = color;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(text, 128, 32);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    this.labelTextures.push(texture);
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthWrite: false,
      }),
    );
    sprite.position.copy(position);
    sprite.scale.set(8, 2, 1);
    this.group.add(sprite);
  }
}

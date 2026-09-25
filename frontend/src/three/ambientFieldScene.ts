import * as THREE from 'three';

import { cssColor } from '../utilities/cssColor';
import type { MotionLevel } from '../utilities/motionController';
import { SceneController } from './sceneController';
import { spriteTexture } from './spriteTexture';

const STAR_COUNT = 2600;
const WAVE_COLUMNS = 120;
const WAVE_ROWS = 46;
const WAVE_SPACING = 4.2;
const CAMERA_HEIGHT = 20;
const CAMERA_DISTANCE = 120;
const DOLLY_SECONDS = 1.4;

/** The animated backdrop behind every page: a slowly turning star field above a flowing landscape of points, like a price surface. */
export class AmbientFieldScene extends SceneController {
  private readonly speed: number;
  private readonly followsPointer: boolean;
  private readonly pointer = new THREE.Vector2();
  private readonly texture: THREE.Texture;
  private readonly stars: THREE.Points;
  private readonly starMaterial: THREE.PointsMaterial;
  private readonly wave: THREE.Points;
  private readonly waveMaterial: THREE.PointsMaterial;
  private readonly waveColors: Float32Array;
  private readonly lowColor = new THREE.Color();
  private readonly highColor = new THREE.Color();
  private readonly mixedColor = new THREE.Color();
  private dollyStartedAt = -100;

  /**
   * Builds the scene.
   * @param canvas The canvas to draw on.
   * @param level The animation intensity: reduced draws fewer points, moves slower and ignores the pointer.
   * @throws Error when the browser cannot create a WebGL context.
   */
  constructor(canvas: HTMLCanvasElement, level: MotionLevel) {
    super(canvas, 60);
    const reduced = level === 'reduced';
    this.speed = reduced ? 0.35 : 1;
    this.followsPointer = !reduced;
    this.texture = spriteTexture.create(64);
    const starCount = reduced ? Math.round(STAR_COUNT * 0.4) : STAR_COUNT;
    this.starMaterial = new THREE.PointsMaterial({
      size: 2.2,
      map: this.texture,
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      sizeAttenuation: true,
    });
    this.stars = new THREE.Points(this.createStarGeometry(starCount), this.starMaterial);
    this.scene.add(this.stars);
    this.waveColors = new Float32Array(WAVE_COLUMNS * WAVE_ROWS * 3);
    this.waveMaterial = new THREE.PointsMaterial({
      size: 1.6,
      map: this.texture,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      depthWrite: false,
      sizeAttenuation: true,
    });
    this.wave = new THREE.Points(this.createWaveGeometry(), this.waveMaterial);
    this.wave.position.set(0, -26, -40);
    this.scene.add(this.wave);
    this.camera.position.set(0, CAMERA_HEIGHT, CAMERA_DISTANCE);
    this.camera.lookAt(0, 0, 0);
    this.applyTheme();
    window.addEventListener('pointermove', this.handlePointerMove);
  }

  /** Re-reads the theme's colours and blending, after the page switches between light and dark. */
  applyTheme(): void {
    const dark = document.documentElement.dataset.theme !== 'light';
    this.lowColor.set(cssColor.read('--second', '#64b5f6'));
    this.highColor.set(cssColor.read('--accent', '#ff8a65'));
    const blending = dark ? THREE.AdditiveBlending : THREE.NormalBlending;
    this.starMaterial.blending = blending;
    this.waveMaterial.blending = blending;
    this.starMaterial.opacity = dark ? 0.9 : 0.55;
    this.waveMaterial.opacity = dark ? 0.85 : 0.4;
    this.starMaterial.needsUpdate = true;
    this.waveMaterial.needsUpdate = true;
    this.colorStars();
  }

  /** Starts a short camera dolly, used when the user moves to another page. */
  nudge(): void {
    this.dollyStartedAt = this.elapsedSeconds;
  }

  /**
   * Turns the stars, moves the landscape and eases the camera toward the pointer.
   * @param elapsedSeconds Seconds since the scene started.
   * @param deltaSeconds Seconds since the previous frame.
   */
  protected update(elapsedSeconds: number, deltaSeconds: number): void {
    const time = elapsedSeconds * this.speed;
    this.stars.rotation.y += deltaSeconds * 0.012 * this.speed;
    this.stars.rotation.x = Math.sin(time * 0.05) * 0.06;
    this.moveWave(time);
    const sinceDolly = elapsedSeconds - this.dollyStartedAt;
    let dolly = 0;
    if (sinceDolly < DOLLY_SECONDS) {
      const progress = sinceDolly / DOLLY_SECONDS;
      dolly = Math.sin(progress * Math.PI) * (1 - progress * 0.4);
    }
    const targetX = this.followsPointer ? this.pointer.x * 14 : 0;
    const targetY = CAMERA_HEIGHT + (this.followsPointer ? this.pointer.y * 7 : 0);
    const targetZ = CAMERA_DISTANCE - dolly * 34;
    const easing = Math.min(deltaSeconds * 2.5, 1);
    this.camera.position.x += (targetX - this.camera.position.x) * easing;
    this.camera.position.y += (targetY - this.camera.position.y) * easing;
    this.camera.position.z += (targetZ - this.camera.position.z) * Math.min(deltaSeconds * 6, 1);
    this.camera.lookAt(0, 0, 0);
  }

  /** Removes the pointer listener and frees the dot texture. */
  protected disposeResources(): void {
    window.removeEventListener('pointermove', this.handlePointerMove);
    this.texture.dispose();
  }

  /**
   * Scatters stars through a thick spherical shell around the camera's view.
   * @param count How many stars to create.
   * @returns The geometry with positions and an empty colour attribute.
   */
  private createStarGeometry(count: number): THREE.BufferGeometry {
    const positions = new Float32Array(count * 3);
    for (let index = 0; index < count; index += 1) {
      const radius = 180 + Math.random() * 520;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[index * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[index * 3 + 1] = radius * Math.cos(phi) * 0.6;
      positions[index * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    return geometry;
  }

  /**
   * Lays the landscape's points out on a flat grid; their heights are set every frame.
   * @returns The geometry with positions and colours.
   */
  private createWaveGeometry(): THREE.BufferGeometry {
    const positions = new Float32Array(WAVE_COLUMNS * WAVE_ROWS * 3);
    let index = 0;
    for (let row = 0; row < WAVE_ROWS; row += 1) {
      for (let column = 0; column < WAVE_COLUMNS; column += 1) {
        positions[index * 3] = (column - WAVE_COLUMNS / 2) * WAVE_SPACING;
        positions[index * 3 + 1] = 0;
        positions[index * 3 + 2] = (row - WAVE_ROWS / 2) * WAVE_SPACING;
        index += 1;
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(this.waveColors, 3));
    return geometry;
  }

  /** Gives each star a colour: mostly faint, with some in the accent and second colours. */
  private colorStars(): void {
    const attribute = this.stars.geometry.getAttribute('color') as THREE.BufferAttribute;
    const faint = new THREE.Color(cssColor.read('--ink-muted', '#9aa0a6'));
    for (let index = 0; index < attribute.count; index += 1) {
      const pick = (index * 7919) % 10;
      let color = faint;
      if (pick === 0) {
        color = this.highColor;
      } else if (pick === 1 || pick === 2) {
        color = this.lowColor;
      }
      attribute.setXYZ(index, color.r, color.g, color.b);
    }
    attribute.needsUpdate = true;
  }

  /**
   * Sets every landscape point's height from overlapping travelling waves, and colours it by height.
   * @param time The scaled scene time, in seconds.
   */
  private moveWave(time: number): void {
    const positions = this.wave.geometry.getAttribute('position') as THREE.BufferAttribute;
    const colors = this.wave.geometry.getAttribute('color') as THREE.BufferAttribute;
    for (let index = 0; index < positions.count; index += 1) {
      const x = positions.getX(index);
      const z = positions.getZ(index);
      const height =
        Math.sin(x * 0.045 + time * 0.55) * 5.5 +
        Math.sin(z * 0.08 + time * 0.38) * 3.5 +
        Math.sin((x + z) * 0.028 + time * 0.8) * 2.5;
      positions.setY(index, height);
      const mix = Math.min(Math.max((height + 11.5) / 23, 0), 1);
      this.mixedColor.copy(this.lowColor).lerp(this.highColor, mix);
      const fade = 0.35 + 0.65 * (1 - Math.abs(z) / ((WAVE_ROWS / 2) * WAVE_SPACING));
      colors.setXYZ(index, this.mixedColor.r * fade, this.mixedColor.g * fade, this.mixedColor.b * fade);
    }
    positions.needsUpdate = true;
    colors.needsUpdate = true;
  }

  /**
   * Remembers where the pointer is, as -1 to 1 across the window.
   * @param event The pointer event.
   */
  private readonly handlePointerMove = (event: PointerEvent): void => {
    this.pointer.set((event.clientX / window.innerWidth) * 2 - 1, -((event.clientY / window.innerHeight) * 2 - 1));
  };
}

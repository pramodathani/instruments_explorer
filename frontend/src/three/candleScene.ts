import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

import type { CandleRow } from '../api/types';
import { cssColor } from '../utilities/cssColor';
import type { MotionLevel } from '../utilities/motionController';
import { SceneController } from './sceneController';

const MAXIMUM_CANDLES = 240;
const SPACING = 0.6;
const BODY_WIDTH = 0.42;
const PRICE_HEIGHT = 36;
const VOLUME_HEIGHT = 10;
const AVERAGE_PERIOD = 20;

/** The latest candles as glowing 3D boxes with wicks, volume bars behind them and a moving average line, orbitable with the pointer. */
export class CandleScene extends SceneController {
  private readonly controls: OrbitControls;
  private readonly group = new THREE.Group();
  private readonly upMaterial: THREE.MeshStandardMaterial;
  private readonly downMaterial: THREE.MeshStandardMaterial;
  private readonly volumeMaterial: THREE.MeshBasicMaterial;
  private readonly wickMaterial: THREE.LineBasicMaterial;
  private readonly averageMaterial: THREE.LineBasicMaterial;
  private readonly grid: THREE.GridHelper;
  private candles: CandleRow[] = [];
  private framed = false;

  /**
   * Builds the empty scene with its lights, floor grid and orbit controls.
   * @param canvas The canvas to draw on, which also receives the pointer for orbiting.
   * @param level The animation intensity: maximal turns the scene slowly by itself.
   * @throws Error when the browser cannot create a WebGL context.
   */
  constructor(canvas: HTMLCanvasElement, level: MotionLevel) {
    super(canvas, 45);
    this.upMaterial = new THREE.MeshStandardMaterial({
      roughness: 0.35,
      metalness: 0.2,
    });
    this.downMaterial = new THREE.MeshStandardMaterial({
      roughness: 0.35,
      metalness: 0.2,
    });
    this.volumeMaterial = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity: 0.22,
    });
    this.wickMaterial = new THREE.LineBasicMaterial({
      transparent: true,
      opacity: 0.8,
    });
    this.averageMaterial = new THREE.LineBasicMaterial();
    this.grid = new THREE.GridHelper(MAXIMUM_CANDLES * SPACING * 1.2, 40);
    this.grid.position.y = -0.5;
    this.scene.add(this.grid);
    this.scene.add(this.group);
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
    keyLight.position.set(-30, 60, 50);
    this.scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.6);
    rimLight.position.set(40, 20, -60);
    this.scene.add(rimLight);
    this.camera.position.set(-38, 34, 78);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.target.set(0, PRICE_HEIGHT / 2, 0);
    this.controls.minDistance = 20;
    this.controls.maxDistance = 260;
    this.controls.autoRotate = level === 'maximal';
    this.controls.autoRotateSpeed = 0.35;
    this.applyTheme();
  }

  /**
   * Replaces the candles shown, keeping the most recent ones.
   * @param candles The candle rows, oldest first.
   */
  setCandles(candles: CandleRow[]): void {
    this.candles = candles.slice(-MAXIMUM_CANDLES);
    this.rebuild();
    if (!this.framed && this.candles.length > 0) {
      this.frameCamera();
      this.framed = true;
    }
  }

  /** Re-reads the theme's colours for candles, volume, wicks, the average line and the grid. */
  applyTheme(): void {
    const up = new THREE.Color(cssColor.read('--up', '#5bb974'));
    const down = new THREE.Color(cssColor.read('--down', '#e25f5b'));
    this.upMaterial.color.copy(up);
    this.upMaterial.emissive.copy(up).multiplyScalar(0.35);
    this.downMaterial.color.copy(down);
    this.downMaterial.emissive.copy(down).multiplyScalar(0.35);
    this.volumeMaterial.color.set(cssColor.read('--second', '#64b5f6'));
    this.wickMaterial.color.set(cssColor.read('--ink-muted', '#9aa0a6'));
    this.averageMaterial.color.set(cssColor.read('--accent', '#ff8a65'));
    const gridColor = new THREE.Color(cssColor.read('--ink-faint', '#6b7178'));
    const gridMaterials = Array.isArray(this.grid.material) ? this.grid.material : [this.grid.material];
    for (const material of gridMaterials) {
      if (material instanceof THREE.LineBasicMaterial) {
        material.color.copy(gridColor);
        material.vertexColors = false;
        material.transparent = true;
        material.opacity = 0.35;
        material.needsUpdate = true;
      }
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

  /** Stops the orbit controls and frees the shared materials. */
  protected disposeResources(): void {
    this.controls.dispose();
    this.clearGroup();
    this.upMaterial.dispose();
    this.downMaterial.dispose();
    this.volumeMaterial.dispose();
    this.wickMaterial.dispose();
    this.averageMaterial.dispose();
  }

  /** Moves the camera so the first candles loaded fill the view; later updates, such as a new live candle, leave the camera where the user put it. */
  private frameCamera(): void {
    const width = Math.max(this.candles.length * SPACING, 24);
    const distance = Math.max(width * 0.85, 48);
    const target = new THREE.Vector3(0, PRICE_HEIGHT * 0.45, 0);
    const direction = new THREE.Vector3(-0.28, 0.34, 0.9).normalize();
    this.camera.position.copy(target).addScaledVector(direction, distance);
    this.controls.target.copy(target);
    this.controls.update();
  }

  /** Removes the previous candles' meshes and lines and frees their geometries. */
  private clearGroup(): void {
    for (const child of [...this.group.children]) {
      this.group.remove(child);
      if (child instanceof THREE.Mesh || child instanceof THREE.LineSegments || child instanceof THREE.Line) {
        child.geometry.dispose();
      }
    }
  }

  /** Builds the bodies, wicks, volume bars and average line for the current candles. */
  private rebuild(): void {
    this.clearGroup();
    const candles = this.candles.filter((candle) => candle[1] !== null && candle[2] !== null && candle[3] !== null && candle[4] !== null);
    if (candles.length === 0) {
      return;
    }
    let lowest = Infinity;
    let highest = -Infinity;
    let largestVolume = 0;
    for (const candle of candles) {
      lowest = Math.min(lowest, candle[3] ?? lowest);
      highest = Math.max(highest, candle[2] ?? highest);
      largestVolume = Math.max(largestVolume, candle[5] ?? 0);
    }
    const range = highest - lowest || 1;
    const toHeight = (price: number) => ((price - lowest) / range) * PRICE_HEIGHT;
    const box = new THREE.BoxGeometry(BODY_WIDTH, 1, BODY_WIDTH);
    const upBodies = new THREE.InstancedMesh(box, this.upMaterial, candles.length);
    const downBodies = new THREE.InstancedMesh(box.clone(), this.downMaterial, candles.length);
    const volumeBars = new THREE.InstancedMesh(new THREE.BoxGeometry(BODY_WIDTH, 1, 0.1), this.volumeMaterial, candles.length);
    const matrix = new THREE.Matrix4();
    const wickPositions: number[] = [];
    const averagePoints: THREE.Vector3[] = [];
    let upCount = 0;
    let downCount = 0;
    let volumeCount = 0;
    let runningSum = 0;
    const offset = ((candles.length - 1) * SPACING) / 2;
    candles.forEach((candle, index) => {
      const open = candle[1] as number;
      const high = candle[2] as number;
      const low = candle[3] as number;
      const close = candle[4] as number;
      const x = index * SPACING - offset;
      const bottom = toHeight(Math.min(open, close));
      const bodyHeight = Math.max(toHeight(Math.max(open, close)) - bottom, 0.06);
      matrix.makeScale(1, bodyHeight, 1);
      matrix.setPosition(x, bottom + bodyHeight / 2, 0);
      if (close >= open) {
        upBodies.setMatrixAt(upCount, matrix);
        upCount += 1;
      } else {
        downBodies.setMatrixAt(downCount, matrix);
        downCount += 1;
      }
      wickPositions.push(x, toHeight(low), 0, x, toHeight(high), 0);
      const volume = candle[5] ?? 0;
      if (largestVolume > 0 && volume > 0) {
        const barHeight = (volume / largestVolume) * VOLUME_HEIGHT;
        matrix.makeScale(1, barHeight, 1);
        matrix.setPosition(x, barHeight / 2, -3);
        volumeBars.setMatrixAt(volumeCount, matrix);
        volumeCount += 1;
      }
      runningSum += close;
      if (index >= AVERAGE_PERIOD) {
        runningSum -= candles[index - AVERAGE_PERIOD][4] as number;
      }
      if (index >= AVERAGE_PERIOD - 1) {
        averagePoints.push(new THREE.Vector3(x, toHeight(runningSum / AVERAGE_PERIOD), 0.6));
      }
    });
    upBodies.count = upCount;
    downBodies.count = downCount;
    volumeBars.count = volumeCount;
    this.group.add(upBodies, downBodies, volumeBars);
    const wickGeometry = new THREE.BufferGeometry();
    wickGeometry.setAttribute('position', new THREE.Float32BufferAttribute(wickPositions, 3));
    this.group.add(new THREE.LineSegments(wickGeometry, this.wickMaterial));
    if (averagePoints.length > 1) {
      const averageGeometry = new THREE.BufferGeometry().setFromPoints(averagePoints);
      this.group.add(new THREE.Line(averageGeometry, this.averageMaterial));
    }
  }
}

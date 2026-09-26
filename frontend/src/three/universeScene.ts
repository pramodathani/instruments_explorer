import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

import type { UniverseLabel, UniverseMap } from '../api/types';
import { cssColor } from '../utilities/cssColor';
import type { MotionLevel } from '../utilities/motionController';
import { SceneController } from './sceneController';
import { spriteTexture } from './spriteTexture';

/** What the points' colours show. */
export type UniverseColouring = 'change' | 'asset_class' | 'shape';

/** What the page is told when the pointer moves over, or clicks, a point. */
export interface UniverseListener {
  onHover: (index: number | null, clientX: number, clientY: number) => void;
  onSelect: (index: number) => void;
}

const FLIGHT_SECONDS = 1.6;
const OPENING_SECONDS = 2.4;
const CHANGE_LIMIT = 3;
const CLICK_TOLERANCE = 5;
const POINT_PIXELS = 3;
const SPRING_OPACITY = 0.16;
const SPRING_FADE_DISTANCE = 160;
const SPRING_MINIMUM_SHARE = 0.12;
const SPRING_SEGMENTS_PER_COIL = 6;
const CLUSTER_LABEL_SIZE = 0.16;
const CLUSTER_LABEL_DISTANCE = 900;
const MAXIMUM_POINT_PIXELS = 11;
const POINT_GROWTH_DISTANCE = 120;

/** Every instrument as a glowing point: asset classes are galaxies on a ring, underlyings are clusters inside them, and contracts orbit their underlying. */
export class UniverseScene extends SceneController {
  private readonly controls: OrbitControls;
  private readonly listener: UniverseListener;
  private readonly level: MotionLevel;
  private readonly pointTexture: THREE.Texture;
  private readonly ringTexture: THREE.Texture;
  private readonly pointMaterial: THREE.PointsMaterial;
  private readonly marker: THREE.Sprite;
  private readonly springMaterial: THREE.LineBasicMaterial;
  private springs: THREE.LineSegments | null = null;
  private springsShown = true;
  private readonly labels = new THREE.Group();
  private readonly labelTextures: THREE.Texture[] = [];
  private readonly clusterLabels: THREE.Sprite[] = [];
  private readonly raycaster = new THREE.Raycaster();
  private readonly pointer = new THREE.Vector2();
  private readonly canvas: HTMLCanvasElement;
  private points: THREE.Points | null = null;
  private map: UniverseMap | null = null;
  private colouring: UniverseColouring = 'change';
  private pointerMoved = false;
  private pointerInside = false;
  private pointerClientX = 0;
  private pointerClientY = 0;
  private pressX = 0;
  private pressY = 0;
  private hovered: number | null = null;
  private readonly homePosition = new THREE.Vector3(0, 700, 1100);
  private openingStartedAt = -1;
  private flight: {
    startedAt: number;
    fromPosition: THREE.Vector3;
    toPosition: THREE.Vector3;
    fromTarget: THREE.Vector3;
    toTarget: THREE.Vector3;
  } | null = null;

  /**
   * Builds the empty scene with orbit controls and the pointer handlers.
   * @param canvas The canvas to draw on, which also receives the pointer.
   * @param level The animation intensity: maximal opens with the galaxies unfolding and turns the scene slowly.
   * @param listener Told about hovers and clicks on points.
   * @throws Error when the browser cannot create a WebGL context.
   */
  constructor(canvas: HTMLCanvasElement, level: MotionLevel, listener: UniverseListener) {
    super(canvas, 50);
    this.canvas = canvas;
    this.level = level;
    this.listener = listener;
    this.camera.far = 20000;
    this.camera.position.copy(this.homePosition);
    this.camera.updateProjectionMatrix();
    this.pointTexture = spriteTexture.create(64);
    this.ringTexture = this.createRingTexture();
    this.pointMaterial = new THREE.PointsMaterial({
      size: POINT_PIXELS,
      map: this.pointTexture,
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
      depthWrite: false,
      sizeAttenuation: false,
    });
    this.springMaterial = new THREE.LineBasicMaterial({
      color: cssColor.read('--ink-muted', '#9aa0a6'),
      transparent: true,
      opacity: SPRING_OPACITY,
      depthWrite: false,
    });
    this.marker = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: this.ringTexture,
        transparent: true,
        depthTest: false,
        depthWrite: false,
      }),
    );
    this.marker.visible = false;
    this.marker.renderOrder = 10;
    this.scene.add(this.marker);
    this.scene.add(this.labels);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.maxDistance = 5000;
    this.controls.minDistance = 2;
    this.controls.zoomSpeed = 1.4;
    this.controls.autoRotate = level === 'maximal';
    this.controls.autoRotateSpeed = 0.25;
    canvas.addEventListener('pointermove', this.handlePointerMove);
    canvas.addEventListener('pointerleave', this.handlePointerLeave);
    canvas.addEventListener('pointerdown', this.handlePointerDown);
    canvas.addEventListener('pointerup', this.handlePointerUp);
  }

  /**
   * Replaces the instruments shown.
   * @param map The laid-out instruments from the server.
   */
  setMap(map: UniverseMap): void {
    const firstMap = this.map === null;
    this.map = map;
    this.hovered = null;
    this.marker.visible = false;
    if (this.points !== null) {
      this.scene.remove(this.points);
      this.points.geometry.dispose();
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(map.positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(map.ids.length * 3), 3));
    geometry.computeBoundingSphere();
    this.points = new THREE.Points(geometry, this.pointMaterial);
    this.scene.add(this.points);
    this.buildSprings(map);
    this.paint();
    this.buildLabels();
    if (firstMap) {
      let widestGalaxy = 0;
      for (const galaxy of map.galaxies) {
        widestGalaxy = Math.max(widestGalaxy, galaxy.radius);
      }
      const extent = map.radius + widestGalaxy;
      const halfView = Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)) * Math.min(this.camera.aspect, 1);
      const distance = (extent / halfView) * 1.05;
      this.homePosition.set(0, distance * 0.5, distance * 0.87);
      this.camera.position.copy(this.homePosition);
      this.controls.target.set(0, 0, 0);
      this.controls.maxDistance = Math.max(map.radius * 6, 500);
    }
    if (firstMap && this.level === 'maximal') {
      this.openingStartedAt = this.elapsedSeconds;
      this.points.scale.setScalar(0.001);
      this.labels.visible = false;
    }
  }

  /**
   * Shows or hides the springs that connect derivatives to their underlying.
   * @param shown Whether the springs are drawn.
   */
  setSpringsShown(shown: boolean): void {
    this.springsShown = shown;
    if (this.springs !== null) {
      this.springs.visible = shown;
    }
  }

  /**
   * Changes what the points' colours show.
   * @param colouring The day's change, the asset class or the shape.
   */
  setColouring(colouring: UniverseColouring): void {
    this.colouring = colouring;
    this.paint();
  }

  /** Re-reads the theme's colours and repaints the points and labels. */
  applyTheme(): void {
    this.springMaterial.color.set(cssColor.read('--ink-muted', '#9aa0a6'));
    this.paint();
    this.buildLabels();
  }

  /**
   * Flies the camera to one instrument and marks it.
   * @param index The instrument's position in the map's arrays.
   */
  flyTo(index: number): void {
    if (this.map === null) {
      return;
    }
    const target = this.positionOf(index);
    this.marker.position.copy(target);
    this.marker.visible = true;
    const direction = this.camera.position.clone().sub(this.controls.target).normalize();
    this.startFlight(target.clone().add(direction.multiplyScalar(30)), target);
  }

  /**
   * Flies the camera to a galaxy or cluster, stopping where the whole of it fits in view.
   * @param label The galaxy's or cluster's label.
   */
  flyToLabel(label: UniverseLabel): void {
    const target = new THREE.Vector3(label.x, label.y, label.z);
    const distance = Math.max(label.radius * 2.2, 25);
    this.startFlight(target.clone().add(new THREE.Vector3(0, distance * 0.55, distance)), target);
  }

  /** Flies the camera back to where it can see every galaxy. */
  flyHome(): void {
    this.marker.visible = false;
    this.startFlight(this.homePosition.clone(), new THREE.Vector3(0, 0, 0));
  }

  /**
   * Moves the camera along any flight, runs the opening, finds the point under the pointer, and pulses the marker.
   * @param elapsedSeconds Seconds since the scene started.
   * @param deltaSeconds Seconds since the previous frame.
   */
  protected update(elapsedSeconds: number, deltaSeconds: number): void {
    void deltaSeconds;
    this.runOpening(elapsedSeconds);
    if (this.flight !== null) {
      const progress = Math.min((elapsedSeconds - this.flight.startedAt) / FLIGHT_SECONDS, 1);
      const eased = progress < 0.5 ? 4 * progress ** 3 : 1 - (-2 * progress + 2) ** 3 / 2;
      this.camera.position.lerpVectors(this.flight.fromPosition, this.flight.toPosition, eased);
      this.controls.target.lerpVectors(this.flight.fromTarget, this.flight.toTarget, eased);
      if (progress >= 1) {
        this.flight = null;
      }
    }
    this.controls.update();
    const viewDistance = this.camera.position.distanceTo(this.controls.target);
    const nearness = Math.min(Math.max(SPRING_FADE_DISTANCE / viewDistance, SPRING_MINIMUM_SHARE), 1);
    this.springMaterial.opacity = SPRING_OPACITY * nearness;
    this.pointMaterial.size = Math.min(Math.max(POINT_PIXELS * (POINT_GROWTH_DISTANCE / viewDistance), POINT_PIXELS), MAXIMUM_POINT_PIXELS);
    for (const label of this.clusterLabels) {
      label.visible = this.camera.position.distanceTo(label.position) < CLUSTER_LABEL_DISTANCE;
    }
    if (this.marker.visible) {
      const distance = this.camera.position.distanceTo(this.marker.position);
      const pulse = this.level === 'off' ? 1 : 1 + 0.25 * Math.sin(elapsedSeconds * 4);
      this.marker.scale.setScalar(distance * 0.04 * pulse);
    }
    if (this.pointerMoved) {
      this.pointerMoved = false;
      this.findHovered();
    }
  }

  /** Removes the pointer handlers and frees the textures, labels and controls. */
  protected disposeResources(): void {
    this.canvas.removeEventListener('pointermove', this.handlePointerMove);
    this.canvas.removeEventListener('pointerleave', this.handlePointerLeave);
    this.canvas.removeEventListener('pointerdown', this.handlePointerDown);
    this.canvas.removeEventListener('pointerup', this.handlePointerUp);
    this.controls.dispose();
    this.clearLabels();
    this.pointTexture.dispose();
    this.springMaterial.dispose();
    this.ringTexture.dispose();
    this.marker.material.dispose();
  }

  /**
   * Grows the galaxies out of the centre over the first seconds, when the opening is running.
   * @param elapsedSeconds Seconds since the scene started.
   */
  private runOpening(elapsedSeconds: number): void {
    if (this.openingStartedAt < 0 || this.points === null) {
      return;
    }
    const progress = Math.min((elapsedSeconds - this.openingStartedAt) / OPENING_SECONDS, 1);
    const eased = 1 - (1 - progress) ** 4;
    this.points.scale.setScalar(Math.max(eased, 0.001));
    this.points.rotation.y = (1 - eased) * Math.PI * 1.5;
    if (progress >= 1) {
      this.openingStartedAt = -1;
      this.points.rotation.y = 0;
      this.labels.visible = true;
    }
  }

  /**
   * Starts a camera flight from where the camera is now.
   * @param toPosition Where the camera ends.
   * @param toTarget What it looks at when it arrives.
   */
  private startFlight(toPosition: THREE.Vector3, toTarget: THREE.Vector3): void {
    if (this.level === 'off') {
      this.camera.position.copy(toPosition);
      this.controls.target.copy(toTarget);
      this.flight = null;
      return;
    }
    this.flight = {
      startedAt: this.elapsedSeconds,
      fromPosition: this.camera.position.clone(),
      toPosition,
      fromTarget: this.controls.target.clone(),
      toTarget,
    };
  }

  /**
   * Reads one point's position.
   * @param index The point's position in the map's arrays.
   * @returns Its position in the scene.
   */
  private positionOf(index: number): THREE.Vector3 {
    const positions = this.map?.positions ?? [];
    return new THREE.Vector3(positions[index * 3], positions[index * 3 + 1], positions[index * 3 + 2]);
  }

  /** Finds the point nearest the pointer and tells the listener when it changes. */
  private findHovered(): void {
    if (this.points === null || !this.pointerInside || this.openingStartedAt >= 0) {
      return;
    }
    const distance = this.camera.position.distanceTo(this.controls.target);
    this.raycaster.params.Points = {
      threshold: Math.max(distance * 0.004, 0.2),
    };
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hits = this.raycaster.intersectObject(this.points, false);
    let found: number | null = null;
    let nearest = Infinity;
    for (const hit of hits) {
      if (hit.index !== undefined && hit.distanceToRay !== undefined && hit.distanceToRay < nearest) {
        nearest = hit.distanceToRay;
        found = hit.index;
      }
    }
    this.hovered = found;
    this.canvas.style.cursor = found === null ? 'grab' : 'pointer';
    this.listener.onHover(found, this.pointerClientX, this.pointerClientY);
  }

  /**
   * Draws a thin coiled spring from every future and option to the instrument it is based on, as one line object attached to the points so it follows them.
   * @param map The laid-out instruments.
   */
  private buildSprings(map: UniverseMap): void {
    if (this.springs !== null) {
      this.springs.removeFromParent();
      this.springs.geometry.dispose();
      this.springs = null;
    }
    const segmentCounts: number[] = [];
    let vertexTotal = 0;
    let segmentTotal = 0;
    for (let index = 0; index < map.anchors.length; index += 1) {
      const anchor = map.anchors[index];
      let segments = 0;
      if (anchor >= 0) {
        const length = Math.hypot(map.positions[index * 3] - map.positions[anchor * 3], map.positions[index * 3 + 1] - map.positions[anchor * 3 + 1], map.positions[index * 3 + 2] - map.positions[anchor * 3 + 2]);
        if (length > 0.05) {
          const coils = Math.min(Math.max(Math.round(length / 3), 1), 3);
          segments = coils * SPRING_SEGMENTS_PER_COIL;
        }
      }
      segmentCounts.push(segments);
      if (segments > 0) {
        vertexTotal += segments + 1;
        segmentTotal += segments;
      }
    }
    if (segmentTotal === 0 || this.points === null) {
      return;
    }
    const vertices = new Float32Array(vertexTotal * 3);
    const indices = new Uint32Array(segmentTotal * 2);
    const start = new THREE.Vector3();
    const end = new THREE.Vector3();
    const along = new THREE.Vector3();
    const across = new THREE.Vector3();
    const around = new THREE.Vector3();
    const up = new THREE.Vector3(0, 1, 0);
    const side = new THREE.Vector3(1, 0, 0);
    let vertex = 0;
    let indexPosition = 0;
    for (let index = 0; index < map.anchors.length; index += 1) {
      const segments = segmentCounts[index];
      if (segments === 0) {
        continue;
      }
      const anchor = map.anchors[index];
      start.set(map.positions[anchor * 3], map.positions[anchor * 3 + 1], map.positions[anchor * 3 + 2]);
      end.set(map.positions[index * 3], map.positions[index * 3 + 1], map.positions[index * 3 + 2]);
      along.subVectors(end, start);
      const length = along.length();
      along.divideScalar(length);
      across.crossVectors(along, Math.abs(along.y) > 0.9 ? side : up).normalize();
      around.crossVectors(along, across).normalize();
      const radius = Math.min(Math.max(length * 0.05, 0.08), 0.5);
      const firstVertex = vertex;
      for (let step = 0; step <= segments; step += 1) {
        const share = step / segments;
        const angle = (step / SPRING_SEGMENTS_PER_COIL) * Math.PI * 2;
        const taper = Math.sin(share * Math.PI) * radius;
        const offset = vertex * 3;
        vertices[offset] = start.x + along.x * length * share + (across.x * Math.cos(angle) + around.x * Math.sin(angle)) * taper;
        vertices[offset + 1] = start.y + along.y * length * share + (across.y * Math.cos(angle) + around.y * Math.sin(angle)) * taper;
        vertices[offset + 2] = start.z + along.z * length * share + (across.z * Math.cos(angle) + around.z * Math.sin(angle)) * taper;
        vertex += 1;
      }
      for (let step = 0; step < segments; step += 1) {
        indices[indexPosition] = firstVertex + step;
        indices[indexPosition + 1] = firstVertex + step + 1;
        indexPosition += 2;
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    geometry.setIndex(new THREE.BufferAttribute(indices, 1));
    this.springs = new THREE.LineSegments(geometry, this.springMaterial);
    this.springs.visible = this.springsShown;
    this.springs.renderOrder = -1;
    this.points.add(this.springs);
  }

  /** Colours every point by the chosen colouring. */
  private paint(): void {
    const map = this.map;
    if (map === null || this.points === null) {
      return;
    }
    const attribute = this.points.geometry.getAttribute('color') as THREE.BufferAttribute;
    const colours = attribute.array as Float32Array;
    const palette = this.palette();
    const neutral = new THREE.Color(cssColor.read('--ink-faint', '#6b7178'));
    const up = new THREE.Color(cssColor.read('--up', '#5bb974'));
    const down = new THREE.Color(cssColor.read('--down', '#e25f5b'));
    const unknown = neutral.clone().multiplyScalar(0.8);
    const colour = new THREE.Color();
    for (let index = 0; index < map.ids.length; index += 1) {
      if (this.colouring === 'asset_class') {
        colour.copy(palette[map.asset_classes[index] % palette.length]);
      } else if (this.colouring === 'shape') {
        colour.copy(palette[map.shapes[index] % palette.length]);
      } else {
        const change = map.changes[index];
        if (change === null) {
          colour.copy(unknown);
        } else {
          const share = Math.min(Math.abs(change) / CHANGE_LIMIT, 1);
          colour.copy(neutral).lerp(change >= 0 ? up : down, 0.35 + share * 0.65);
        }
      }
      colours[index * 3] = colour.r;
      colours[index * 3 + 1] = colour.g;
      colours[index * 3 + 2] = colour.b;
    }
    attribute.needsUpdate = true;
  }

  /**
   * Gives the colours used for asset classes and shapes.
   * @returns Six theme colours.
   */
  private palette(): THREE.Color[] {
    return [
      new THREE.Color(cssColor.read('--accent', '#ff8a65')),
      new THREE.Color(cssColor.read('--second', '#64b5f6')),
      new THREE.Color(cssColor.read('--up', '#5bb974')),
      new THREE.Color(cssColor.read('--warning', '#fab219')),
      new THREE.Color('#b388ff'),
      new THREE.Color(cssColor.read('--ink-muted', '#9aa0a6')),
    ];
  }

  /** Removes every label, freeing its texture and material. */
  private clearLabels(): void {
    for (const child of [...this.labels.children]) {
      this.labels.remove(child);
      if (child instanceof THREE.Sprite) {
        child.material.dispose();
      }
    }
    for (const texture of this.labelTextures) {
      texture.dispose();
    }
    this.labelTextures.length = 0;
    this.clusterLabels.length = 0;
  }

  /** Labels every galaxy above its centre and the biggest clusters beside themselves. */
  private buildLabels(): void {
    this.clearLabels();
    const map = this.map;
    if (map === null) {
      return;
    }
    const accent = cssColor.read('--accent', '#ff8a65');
    const ink = cssColor.read('--ink', '#e8eaed');
    for (const galaxy of map.galaxies) {
      const title = galaxy.label.replace('_', ' ').toUpperCase();
      const width = Math.max(galaxy.radius * 0.9, 150);
      const sprite = this.addLabel(title, accent);
      if (sprite !== null) {
        sprite.position.set(galaxy.x, galaxy.y + galaxy.radius * 0.35 + width * 0.2, galaxy.z);
        sprite.scale.set(width, width * 0.1875, 1);
      }
    }
    for (const cluster of map.clusters) {
      const sprite = this.addLabel(cluster.label, ink);
      if (sprite !== null) {
        sprite.material.sizeAttenuation = false;
        sprite.position.set(cluster.x, cluster.y + cluster.radius * 0.3 + 2, cluster.z);
        sprite.scale.set(CLUSTER_LABEL_SIZE, CLUSTER_LABEL_SIZE * 0.1875, 1);
        sprite.visible = false;
        this.clusterLabels.push(sprite);
      }
    }
  }

  /**
   * Adds one text label that always faces the camera, for the caller to place and size.
   * @param text The text.
   * @param color The text colour.
   * @returns The label, or null when the browser cannot draw text on a canvas.
   */
  private addLabel(text: string, color: string): THREE.Sprite | null {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 96;
    const context = canvas.getContext('2d');
    if (context === null) {
      return null;
    }
    context.font = '600 52px Roboto, sans-serif';
    context.fillStyle = color;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(text, 256, 48, 500);
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
    this.labels.add(sprite);
    return sprite;
  }

  /**
   * Draws the ring that marks a chosen instrument.
   * @returns A texture holding an accent-coloured ring.
   */
  private createRingTexture(): THREE.Texture {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const context = canvas.getContext('2d');
    if (context !== null) {
      context.strokeStyle = cssColor.read('--accent', '#ff8a65');
      context.lineWidth = 10;
      context.beginPath();
      context.arc(64, 64, 50, 0, Math.PI * 2);
      context.stroke();
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  /**
   * Records where the pointer is, so the next frame can look for the point under it.
   * @param event The pointer event.
   */
  private readonly handlePointerMove = (event: PointerEvent): void => {
    const bounds = this.canvas.getBoundingClientRect();
    this.pointer.set(((event.clientX - bounds.left) / bounds.width) * 2 - 1, -((event.clientY - bounds.top) / bounds.height) * 2 + 1);
    this.pointerClientX = event.clientX;
    this.pointerClientY = event.clientY;
    this.pointerInside = true;
    this.pointerMoved = true;
  };

  /** Forgets the hovered point when the pointer leaves the canvas. */
  private readonly handlePointerLeave = (): void => {
    this.pointerInside = false;
    this.hovered = null;
    this.listener.onHover(null, 0, 0);
  };

  /**
   * Remembers where a press started, and stops the slow turn once the user takes control.
   * @param event The pointer event.
   */
  private readonly handlePointerDown = (event: PointerEvent): void => {
    this.pressX = event.clientX;
    this.pressY = event.clientY;
    this.controls.autoRotate = false;
    this.flight = null;
  };

  /**
   * Treats a press that barely moved as a click on the hovered point.
   * @param event The pointer event.
   */
  private readonly handlePointerUp = (event: PointerEvent): void => {
    const moved = Math.hypot(event.clientX - this.pressX, event.clientY - this.pressY);
    if (moved <= CLICK_TOLERANCE && this.hovered !== null) {
      this.listener.onSelect(this.hovered);
    }
  };
}

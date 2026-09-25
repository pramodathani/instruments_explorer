import * as THREE from 'three';

/** The shared mechanism of every three.js scene: the renderer, the camera, the animation loop, resizing and cleanup. */
export abstract class SceneController {
  protected readonly renderer: THREE.WebGLRenderer;
  protected readonly scene: THREE.Scene;
  protected readonly camera: THREE.PerspectiveCamera;
  protected elapsedSeconds = 0;
  private frameRequest = 0;
  private running = false;
  private previousTime = 0;

  /**
   * Creates the renderer on a canvas, with a perspective camera.
   * @param canvas The canvas to draw on.
   * @param fieldOfView The camera's vertical field of view, in degrees.
   * @throws Error when the browser cannot create a WebGL context.
   */
  constructor(canvas: HTMLCanvasElement, fieldOfView: number) {
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'low-power',
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 0);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(fieldOfView, 1, 0.1, 4000);
    document.addEventListener('visibilitychange', this.handleVisibilityChange);
  }

  /** Starts the animation loop. */
  start(): void {
    if (this.running) {
      return;
    }
    this.running = true;
    this.requestFrame();
  }

  /** Stops the animation loop, leaving the last frame on the canvas. */
  stop(): void {
    this.running = false;
    cancelAnimationFrame(this.frameRequest);
  }

  /**
   * Matches the drawing size and camera to the canvas's size on the page.
   * @param width The width in CSS pixels.
   * @param height The height in CSS pixels.
   */
  resize(width: number, height: number): void {
    if (width === 0 || height === 0) {
      return;
    }
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.render(this.scene, this.camera);
  }

  /** Stops the loop and frees every GPU resource the scene holds. */
  dispose(): void {
    this.stop();
    document.removeEventListener('visibilitychange', this.handleVisibilityChange);
    this.disposeResources();
    this.scene.traverse((object) => {
      if (object instanceof THREE.Mesh || object instanceof THREE.Points || object instanceof THREE.LineSegments) {
        object.geometry.dispose();
        const materials = Array.isArray(object.material) ? object.material : [object.material];
        for (const material of materials) {
          material.dispose();
        }
      }
    });
    this.renderer.dispose();
  }

  /**
   * Moves the scene forward by one frame.
   * @param elapsedSeconds Seconds since the scene started, not counting paused time.
   * @param deltaSeconds Seconds since the previous frame.
   */
  protected abstract update(elapsedSeconds: number, deltaSeconds: number): void;

  /** Frees resources that are not part of the scene graph, such as textures and event listeners. */
  protected disposeResources(): void {
    return;
  }

  /** Asks the browser for the next frame, restarting the frame clock. */
  private requestFrame(): void {
    this.previousTime = performance.now();
    this.frameRequest = requestAnimationFrame(this.frame);
  }

  /**
   * Draws one frame and asks for the next.
   * @param time The browser's frame timestamp, in milliseconds.
   */
  private readonly frame = (time: number): void => {
    if (!this.running) {
      return;
    }
    const deltaSeconds = Math.min((time - this.previousTime) / 1000, 0.1);
    this.previousTime = time;
    this.elapsedSeconds += deltaSeconds;
    this.update(this.elapsedSeconds, deltaSeconds);
    this.renderer.render(this.scene, this.camera);
    this.frameRequest = requestAnimationFrame(this.frame);
  };

  /** Pauses drawing while the tab is hidden and resumes when it is shown again. */
  private readonly handleVisibilityChange = (): void => {
    if (!this.running) {
      return;
    }
    cancelAnimationFrame(this.frameRequest);
    if (document.visibilityState === 'visible') {
      this.requestFrame();
    }
  };
}

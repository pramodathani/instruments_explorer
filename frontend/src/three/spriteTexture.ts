import * as THREE from 'three';

/** Draws the soft round dot that point clouds use instead of square pixels. */
export class SpriteTexture {
  /**
   * Creates the texture.
   * @param size The texture's width and height in pixels.
   * @returns A texture holding a white dot that fades to transparent at its edge.
   */
  create(size: number): THREE.Texture {
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext('2d');
    if (context !== null) {
      const middle = size / 2;
      const gradient = context.createRadialGradient(middle, middle, 0, middle, middle, middle);
      gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
      gradient.addColorStop(0.35, 'rgba(255, 255, 255, 0.75)');
      gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
      context.fillStyle = gradient;
      context.fillRect(0, 0, size, size);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }
}

export const spriteTexture = new SpriteTexture();

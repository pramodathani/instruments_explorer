import * as THREE from 'three';

/** Draws the round dot that point clouds use instead of square pixels. */
export class SpriteTexture {
  /**
   * Creates the texture.
   * @param size The texture's width and height in pixels.
   * @returns A texture holding a solid white disc with a thin soft rim, so dots look crisp but not jagged.
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
      gradient.addColorStop(0.82, 'rgba(255, 255, 255, 1)');
      gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
      context.fillStyle = gradient;
      context.fillRect(0, 0, size, size);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.generateMipmaps = false;
    texture.minFilter = THREE.LinearFilter;
    return texture;
  }
}

export const spriteTexture = new SpriteTexture();

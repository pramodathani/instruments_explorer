/** Reads colours from the page's CSS custom properties, so WebGL scenes follow the theme. */
export class CssColor {
  /**
   * Reads one custom property from the root element.
   * @param name The property name, such as "--accent".
   * @param fallback The colour to use when the property is empty.
   * @returns The property's value, trimmed.
   */
  read(name: string, fallback: string): string {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value === '' ? fallback : value;
  }
}

export const cssColor = new CssColor();

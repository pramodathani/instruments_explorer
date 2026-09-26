# universeScene.ts

## Point size

Points use a fixed pixel size (`sizeAttenuation: false`) rather than a size in scene units. With scene-unit sizes the points were sub-pixel from the overview distance and huge up close. Instead, the size grows from 3 to 11 pixels as the camera comes within about 120 units of its target, so a single cluster reads clearly after a fly-to.

## Blending

Additive blending was tried first for a glow, but tens of thousands of overlapping points in a galaxy's middle added up to solid white discs. Normal blending at 90% opacity keeps each point's colour.

## Labels

Galaxy labels are sized in scene units so they shrink with distance like the galaxies. Cluster labels have a fixed screen size and are shown only within 900 units of the camera, because scene-unit cluster labels became enormous when the camera flew past them.

## Hover

The pointer handler only records the position; the raycast runs once in the next frame. A raycast against 236,000 points takes a few milliseconds, and running it on every pointer event would stall the page. The raycaster's threshold scales with the camera's distance so hovering works both from far away and up close.

## Opening animation

At the maximal level the galaxies grow out of the centre over 2.4 seconds while turning, and labels appear when it ends. Browsers do not deliver animation frames to a hidden tab, so a tab opened in the background shows the animation frozen until it is brought to the front. During browser checks with the automation extension the tab reports `document.visibilityState === 'hidden'`, so checks there are easiest with the animation level set to off.

## Dot texture

The dots were first drawn with a radial gradient that began fading 35% of the way from the centre, so most of each dot was a soft halo and the map looked blurry at 3 pixels. `SpriteTexture.create` now draws a solid disc that fades only in its outer 18%, just enough to avoid jagged edges, and turns off mipmaps, which blurred small points further. The ambient background's particles use the same texture.

## Springs

Every future and option is joined to the instrument it is based on by a faint coiled line, a "spring". The server decides the pairs (`anchors` in the map): the cash instrument, preferring the NSE listing, or for underlyings without one, such as commodities, the nearest future for options. On the 2026-09-25 index that is 2,012 springs without options and 194,174 with them.

All springs are one indexed `LineSegments` object, attached as a child of the points so it follows the opening animation's scale and rotation. Each spring has one to three coils of six segments, tapered to nothing at both ends so it meets the dots cleanly. With options that is roughly 1.7 million vertices, built once per map in plain loops over typed arrays.

The springs are kept faint so they do not clutter the map: their opacity is 0.16 when the camera is within 160 units of its target and falls with distance to an eighth of that, so the overview stays clean while a cluster seen up close shows its hub. Where hundreds of springs meet at one share they add up to a soft glow, which reads as the hub rather than clutter. The hover raycast is not recursive, so springs are never picked as points. The toolbar's Springs switch hides them.

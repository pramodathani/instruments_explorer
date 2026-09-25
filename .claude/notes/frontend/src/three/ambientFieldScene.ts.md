# ambientFieldScene.ts

## What it shows

There are two point clouds. One is a star field in a thick spherical shell that turns slowly. The other is a grid of about 5,500 points whose heights come from three overlapping travelling sine waves, which reads as a flowing price landscape. Wave points are coloured from the second colour (low) to the accent (high) and fade toward the front and back edges.

## Performance

The landscape's positions and colours are rewritten on the CPU every frame. About 5,500 points is well within budget, and it keeps the code plain, with no custom shaders. If a later scene needs many more points, a vertex shader would be the next step.

## Theme

Additive blending makes points glow on the dark background but would wash them out to nothing on white, so the light theme switches to normal blending and lowers the opacity. `applyTheme()` re-reads the CSS colour tokens whenever the theme changes.

## Reduced level

The reduced level draws 40% of the stars, moves at 35% speed, and ignores the pointer.

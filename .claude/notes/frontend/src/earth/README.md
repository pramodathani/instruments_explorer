# frontend/src/earth/

## MapLibre and the globe

The Earth page and the company panel's headquarters map use MapLibre GL JS 6 with `projection: {type: 'globe'}`, which draws a 3D globe when zoomed out and a flat map when zoomed in, like Google Earth. The imagery is Esri World Imagery raster tiles, with Esri's World Boundaries and Places layer on top for names; both need the attribution shown in the corner. The user chose Esri satellite imagery on 2026-09-26, knowing that Esri's terms were not checked in detail.

There are no text labels drawn by MapLibre itself, because symbol layers need a glyph server. Cluster sizes show how many companies a cluster holds instead.

## The worker

MapLibre 6 loads a separate worker file, and by default looks for it next to its own module file. Vite does not copy that file into the build, so the first version failed with "Worker failed to load" and drew no tiles. `earthMap.ts` imports `maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url`, which makes Vite bundle the worker with its imports and gives its address, and passes it to `maplibregl.setWorkerUrl`.

## Size

MapLibre adds about 1 MB of script (280 kB compressed) and a 510 kB worker, loaded only when a globe or headquarters map is shown, because `earthMap.ts` is imported with dynamic `import()`.

## Browser checks

A background tab draws no frames, so screenshots of a map in the automation tab can show black until something prompts a repaint, such as scrolling. Checking that tiles were requested with `performance.getEntriesByType('resource')` tells a drawing problem from a loading problem.

# sceneController.ts

Every scene shares this one mechanism: creating the renderer, keeping the camera's aspect ratio right, running the `requestAnimationFrame` loop, pausing while the tab is hidden, and freeing geometries, materials and the renderer on disposal. Subclasses write only `update()` and, where needed, `disposeResources()`.

The frame delta is capped at 0.1 seconds, so a scene that was paused, or a slow frame, does not jump forward. `elapsedSeconds` counts only running time for the same reason.

The renderer asks for `powerPreference: 'low-power'`, because a background animation should prefer the integrated GPU on machines that have two. The pixel ratio is capped at 2, which keeps high-density screens from rendering at 3x or more.

`requestAnimationFrame` is used only for drawing. sridhara's rule that data updates are batched on timers, never animation frames, still applies to data.

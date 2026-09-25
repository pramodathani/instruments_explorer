# frontend/

## Stack

The stack follows sridhara and system_monitor: React 19, TypeScript 7 in strict mode, Vite 8 and react-router 8, with no CSS framework. The additions are three.js for the 3D work and Highcharts with Highcharts Stock for charts. Highcharts is free for personal, non-commercial use, which is how this project uses it.

## Look

The user chose a dark theme by default with the deep-orange accent of their ubi MkDocs site. The colour tokens in `src/styles/tokens.css` are that site's diagram palette. Cards, stat tiles, chips and status badges follow system_monitor. Status badges use a different shape per status so colour is never the only signal. Fonts are Roboto and Roboto Mono, bundled through `@fontsource`.

Unlike sridhara, the app does not follow the operating system's light or dark setting. It starts dark and switches to light only when the user toggles it, because the user asked for dark as the default.

## Animation everywhere, with valves

The user asked for three.js animation everywhere, at the maximal level. What exists after phase 1:

- `AmbientFieldScene` behind every page, including login.
- A camera dolly on each page change.
- A 3D entrance animation for each page.
- Cards that tilt toward the pointer with a glare.
- Numbers that count to their value.
- An orbiting dot in the logo.

Because that much motion costs GPU time and can make numbers harder to read, there are three safety valves:

1. **The animation-intensity setting.** The header's wave button cycles through maximal, reduced and off, and the choice is stored in `localStorage`. When nothing is stored, the operating system's reduced-motion preference starts the app at reduced.
2. **Pausing when hidden.** `SceneController` stops drawing while the tab is hidden.
3. **Deferred loading.** Scenes are loaded with dynamic `import()`, so three.js (about 530 kB) arrives after the first paint instead of delaying it. `chunkSizeWarningLimit` is 600 kB for that reason: the only large chunk is three.js itself.

The 3D tilt on cards uses CSS transforms, not WebGL, because one WebGL context per card would exhaust the browser's context limit.

## Talking to the server

`ApiClient` is sridhara's, with its `X-Requested-With` value changed. The layout fetches `/api/status` once and shares it through the router's outlet context, so the Overview page and the chat panel read the same document.

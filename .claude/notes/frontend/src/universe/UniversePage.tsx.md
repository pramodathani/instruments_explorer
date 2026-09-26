# UniversePage.tsx

The `focus` query parameter takes an instrument id and flies to it after the map loads. It waits 2.6 seconds at the maximal level so the opening animation finishes first. It exists so the chat assistant's `show_in_ui` tool can point at an instrument in the universe.

The search box searches the map's names in the browser rather than calling the index's search, because the point to fly to must be one that is in the map, and the map already holds every name.

# candleScene.ts

## Instancing

Up to 240 candles are drawn with three instanced meshes: up bodies, down bodies and volume bars. That makes three draw calls in all rather than one per candle. Wicks are one `LineSegments`. The whole group is rebuilt when the candles change; with at most 240 candles that is cheap and much simpler than updating instances in place.

## Framing

The camera is placed once, when the first candles arrive, at a distance of 0.85 times the width of the candle row (at least 48), looking slightly from the left and above. Later updates, such as today's live candle, leave the camera wherever the user has orbited it.

Two earlier tries, recorded because they looked plausible, both failed:

| Try | What went wrong |
|---|---|
| A fixed distance from the old default | The candles filled only the middle third of the view |
| 0.62 times the width | Too close; perspective made the nearest candles huge and cut them off |

## Motion

At the maximal animation level OrbitControls turns the scene slowly by itself. At reduced and off it stays still until dragged. Damping is on, so a drag coasts to a stop.

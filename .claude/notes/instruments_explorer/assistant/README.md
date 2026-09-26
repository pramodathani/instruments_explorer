# assistant/

## Why a hand-written loop

The SDK's beta tool runner would run the loop, but it hands back whole messages. The chat panel shows every piece as it arrives: thinking summaries, text, each tool call starting and finishing, and page instructions. `ChatSession` therefore streams each request with `client.beta.messages.stream`, forwards events, and runs the tools itself. The beta client is needed anyway for `fallbacks`.

## Request settings, and why

| Setting | Value | Reason |
|---|---|---|
| `model` | `claude-opus-5-5` | The user chose Opus 5.5. It comes from `INSTRUMENTS_EXPLORER_CLAUDE_MODEL`. |
| `thinking` | `{'type': 'adaptive', 'display': 'summarized'}` | Thinking cannot be switched off on Opus 5.5. The default display is empty text, so the panel would go quiet during long turns; `summarized` returns readable summaries and the short progress notes Opus 5.5 writes between tool calls. |
| `output_config.effort` | `high` from settings | Opus 5.5 defaults to `medium` when effort is left out, so it is always set explicitly. |
| `tool_choice` | not sent | Opus 5.5 answers forced `any` or `tool` choices with a 400. |
| `fallbacks` | `'default'` with beta `server-side-fallback-2026-07-01` | If Opus 5.5's classifiers decline a turn, the API reruns it on Anthropic's recommended model inside the same call. That turn runs without Opus 5.5's thinking blocks, which needs no handling. The array form uses a different beta header; the two must not be mixed. |
| `max_tokens` | 64,000 | Thinking counts toward it, and 64K is the documented starting point for agentic turns. |
| `eager_input_streaming` on every client tool | true | Tool inputs stream as they are written. The server no longer validates them, so `BaseTool.problems` checks each input against its schema before running, and a tool input the SDK cannot parse at all raises `ValueError` from the stream, which retries the round up to twice. |

## Append-only history

Opus 5.5 checks that the thinking blocks it is sent back belong to an unchanged conversation (preserved thinking, enforced for accounts created on or after 2026-08-31). Messages are therefore never edited after they are stored. Content blocks are stored with `block.to_dict(mode='json')`, which keeps exactly the fields the API sent, and are replayed unchanged. `test_history_is_sent_back_unchanged` checks this.

- A refused answer is not stored, because its partial content should be discarded; the user's message stays, and the next message simply follows it (consecutive user messages are allowed).
- An answer cut off by `max_tokens` while writing a tool call is not stored either. Storing a `tool_use` without its `tool_result` would make every later request fail.
- Renaming and deleting act on whole conversations, which does not edit any history that is replayed.
- Facts only the chat panel needs, such as tool result summaries and page instructions, go in the message's `display` field, which is never sent to Claude.

## Prompt caching

The system prompt (`system_prompt.md`) and the tool list never change between requests, and the system block carries an explicit cache marker. Top-level automatic caching then moves a second marker along the growing conversation. This is the combination the caching guide recommends for agent loops.

Anything that changes per message goes into the user message as a `<page_context>` block (the time and the page address), never into the system prompt, so the cached prefix stays byte-identical.

Measured on 2026-09-26 with the first real conversation ("chart RELIANCE with RSI 14 and the 50-day average", then one follow-up):

| Round | Stop | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| 1 | tool_use | 4 | 122 | 0 | 10,811 |
| 2 | tool_use | 2 | 136 | 10,811 | 711 |
| 3 | tool_use | 2 | 853 | 11,522 | 2,088 |
| 4 | end_turn | 2 | 189 | 13,610 | 930 |
| Follow-up | end_turn | 4 | 289 | 14,540 | 328 |

The system prompt and tools are about 10,800 tokens. From the second round on, almost everything is read from the cache.

## Daily limit

`INSTRUMENTS_EXPLORER_CLAUDE_DAILY_TOKEN_LIMIT` counts input, output and cache-write tokens per India day, but not cache reads. Cache reads cost 0.05 times the input price on Opus 5.5, and a single agentic question re-reads the whole prefix every round, so counting them would use up the limit several times faster than the money actually spent.

## Tools call the route handlers

Each tool calls the same route handler the page uses (for example `InstrumentRoutes.search` or `ChartRoutes.chart`) through `AssistantServices`, so Claude sees exactly what the pages show and can do nothing a page cannot. `BaseTool.call_route` turns the handler's `HTTPException` into a `ToolError` whose message Claude reads. Large answers are trimmed by the tools (twenty recent candles, twelve strikes each side of the money, at most fifty screen rows) and cut at 24,000 characters as a last resort.

`request_knowledge_fetch` never fetches: fetching sends requests to outside websites, so it only asks the page to show a button, and the user starts the fetch.

`show_in_ui` builds page addresses from structured fields rather than letting Claude write URLs, so every address it opens is one the pages understand.

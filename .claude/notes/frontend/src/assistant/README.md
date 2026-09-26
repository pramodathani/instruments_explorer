# frontend/src/assistant/

`chatController` holds all chat state outside React, following the same subscribe-and-snapshot pattern as `ThemeController`, so the slide-in panel and the `/chat` page show the same conversation, and a streaming answer keeps going when the user changes page.

The answer is read from a POST response with `fetch` and a stream reader, because `EventSource` can only send GET requests and the message has to go in the body.

When Claude opens a view with `show_in_ui`, the controller calls the navigator that `AppLayout` sets. On the `/chat` page the navigator also opens the side panel first, so the conversation stays visible after the page changes.

Deleting a conversation asks for a second click instead of `window.confirm`, because browser dialogs block the automation used for browser checks and look out of place in the app.

Markdown is rendered with `react-markdown` and `remark-gfm` for tables. It renders to React elements without `dangerouslySetInnerHTML`, so text from Claude cannot inject HTML into the page.

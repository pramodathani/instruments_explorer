# settings.py

## Environment prefix

Every setting is an `INSTRUMENTS_EXPLORER_*` variable, read from the environment first and `.env` second, as in the sibling projects. `.env.example` lists every key.

## The Claude API key has the project prefix

The key is `INSTRUMENTS_EXPLORER_ANTHROPIC_API_KEY` rather than the SDK's default `ANTHROPIC_API_KEY`. That way the key is clearly this project's, it cannot be picked up by accident from a shell that exports another key, and the settings object is the single place that says whether the assistant is configured. The assistant passes the key to the SDK client explicitly.

## Model and effort

The user chose Claude Opus 5.5 (`claude-opus-5-5`). That model defaults to `medium` effort, so the effort setting defaults to `high` and is always sent explicitly. The daily token ceiling is a cost guard for the chat assistant.

## MongoDB URI

The user name and password are URL-escaped, because a generated password may contain characters such as `@` or `/` that would otherwise break the URI. Authentication uses the `admin` database, because the container creates the root user there.

## ubi settings

`ubi_request_timeout_seconds` is 30 seconds, not a few. The same HTTP client streams the 127 MB master, and while ubi's catalogue cache is cold, a single chunk can take several seconds to arrive from TimescaleDB. For the streamed master, the timeout applies to each read, not to the whole download.

`ubi_may_connect` defaults to true, because ubi hands back the same token when one issued after 07:00 exists, so a connect rarely logs anyone out. It can be switched off if another client keeps losing its session.

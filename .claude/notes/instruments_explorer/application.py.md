# application.py

## Shape copied from sridhara

`build()` creates real components and `create_web_application()` assembles FastAPI from ready components. Tests call the second one with stand-ins and `with_lifespan=False`, so no test ever opens a real connection.

## One worker

uvicorn runs one worker, as in both sibling projects. Later phases keep process-wide state, such as the instrument index, the live quote relay, fetch jobs and chat sessions, which several workers would each hold separately.

## Session cookie

The cookie is named `instruments_explorer_session` so it cannot collide with sridhara's or system_monitor's cookies on the same host. `same_site='strict'` together with the `X-Requested-With` header check protects the POST routes against cross-site requests.

## Logging format

The format has no timestamp because journald adds one when the app runs as a service.

## FrontendRoutes last

`FrontendRoutes` answers every path, so any router included after it would never be reached.

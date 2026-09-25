# security/

The three modules are copied from sridhara with only the names changed:

- `authenticator.py`: the argon2 password check with a five-failure, five-minute lockout per address.
- `session_guard.py`: the session helpers and the `X-Requested-With` check.
- `password_setup.py`: the interactive `bin/set-password` tool.

The header value is `instruments-explorer`, and the frontend's `ApiClient` sends the same value. Keeping the code identical to sridhara's makes a fix in one project easy to carry to the other.

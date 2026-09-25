# instruments-explorer.service

This is a systemd user unit, like the sibling projects' units, so it runs as the user without root and starts at login through `default.target`. It restarts ten seconds after any exit, which covers a crash and a MongoDB that is not up yet.

It is not linked or enabled automatically. The user links it with `systemctl --user link` when they want the app to run permanently.

# Trial delivery demonstration project

This tiny project is copied into a temporary directory and receives a normal NightShift installation in `TrialDemoIntegrationTests`.

- `bin/standalone` is a single executable with no project-tree dependency. It can be copied alone into `.trials/<TASK-ID>/bin/`.
- `bundled/bin/show-message` reads `bundled/resources/message.txt` relative to its own location. Copy both directories into a trial delivery to keep the script and its required asset together.
- `scripts/read-shared.sh` reads `shared/demo-state.txt` from the project directory. This is a shared project resource; a trial handoff must disclose that dependency and recommend pausing the Worker if development may change it during the trial.
- Set `PAUSE_FILE=ops/worker.hold` in `nightshift/worker.sh` to select the custom pause path. The user can create the file and use `nightshift/status.sh` to confirm the Worker is paused before starting a trial that conflicts with shared resources.

The demo fixtures contain no credentials, network calls, or live model adapters.

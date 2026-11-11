# Arena collector health assets

These files are maintained source for the shared reporting and collector-health view deployed on `gh-pages:arena/`. Publish only the changed assets and update the script cache version in the deployed HTML. Preserve the live registry and other publishers’ work; do not overwrite the site with an older saved snapshot.

Run `node --test web/arena-reporting/tests/*.test.cjs`. The full dashboard regression suites live beside the deployment at `arena/tests/`. See [collector health](../../docs/collector-health.md).

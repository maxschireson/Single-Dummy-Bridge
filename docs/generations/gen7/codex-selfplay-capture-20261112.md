# Codex Gen7 self-play with retained capture

The05d2cd self-play runtime accepts single-table self-play, but its main-based engine does not execute the carried gap-fork settings or record guess-size/best-share fields. This source combines that authorized self-play port with the existing capture implementation from522eda6. It changes no bot/model/settings and preserves old cohorts separately.

The new collector must pass all Gen7 and gap-fork tests and real-model self-play/comparison preflight with nonzero gap forks and recorded guess metrics before launch. Existing cohorts are drained and archived; no frozen runtime, model, manifest, episode or receipt is edited.

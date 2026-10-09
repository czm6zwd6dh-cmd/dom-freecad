# Instructions for CAD development agents

This repository is PUBLIC. Only generic reviewed code and synthetic fixtures are allowed.
Never upload or log actual house plans, measured project dimensions, scans, photographs,
addresses, building services layouts, private models or backups. Ignoring a filename does
not prevent a later forced upload. The CI privacy guard runs after publication; review first.

Read `docs/OPERATIONS_RU.md`, the current workflow and all invoked `ci/` files at one full
commit SHA. Read the complete current host skill separately. `vendor/architect-engineer-spds`
is ONLY the audited native/backup subset of v0.13.0, pinned by `ORIGIN.json`.
Do not claim that the full skill or normative register has been installed on the runner.

Use one writer and compare the remote HEAD before publishing. Never reset another writer's
changes. Keep FreeCAD and Actions references pinned. Normal workflows have `contents: read`,
no retained checkout credential and no private project secrets. No recurring schedules,
interactive desktop tunnels or unbounded retries belong here.

Run `python ci/verify_vendor.py`, `python ci/run_unit_tests.py`, and the public privacy guard.
A native qualification needs all required workflow steps on the reviewed SHA and attempt,
verified artifact bytes, the complete report set, and a separate visual check of all PDF
previews. Report exact scope: five separate native processes, synthetic fixtures, limited
vector control spans, and file preservation. Unit test success alone proves none of these.

R1 geometry must not be changed by infrastructure work. A separate private route is required
before processing real project data. Do not call a green synthetic test construction approval,
complete SPDS, qualified associated dimensions/sections, or professional engineering review.

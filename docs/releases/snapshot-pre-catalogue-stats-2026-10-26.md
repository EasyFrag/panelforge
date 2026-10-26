# Snapshot before catalogue and factory statistics fixes — 2026-10-26

Restore point before the two startup fixes requested by the user.
Includes the current application, tests, workflows, HTTP refactoring, queue/history
and asset-loading improvements, Creation batch and its Flux Klein/Moody defaults,
and the CSV examples. The catalogue/statistics fixes are deliberately subsequent.

Based on fc38fb6a6720be4f583743436ad66df9531f60e7. The newer published Story V2
guide is retained. Private launch configuration, runtime data, generated media,
local diagnostics and untracked design prototypes are excluded.

Created with an isolated index; working branches and normal indexes are preserved.
No test suite, model call, generation or service restart performed for this snapshot.
This is a restore point, not a claim of functional validation.

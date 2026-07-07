# Release Notes

## 1.0.0

### Changed

- Refreshed the PySide6 dark theme with a consistent color system, typography, spacing, and control states.
- Added visual button hierarchy for primary, secondary, and tertiary actions.
- Improved form responsiveness for compact and expanded window sizes.
- Restyled directory dropdown controls as compact circular `...` buttons.
- Improved preview table styling with zebra rows, visible separators, row hover, and an empty-state hint.

### Fixed

- Prevented compact combo boxes and date filters from clipping their text.
- Disabled document actions, including `DOCX + PDF`, until a statement has been generated.
- Reset generated-document actions when a new Excel file is selected.

### Verification

- `python -m compileall app tests`
- Full `pytest` run requires installing `requirements-dev.txt`.

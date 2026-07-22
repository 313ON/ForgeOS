# ForgeOS Project Instructions

**Authority:** Engineering execution charter
**Applies to:** Humans and automated agents working in this repository
**Product source of truth:** `Docs/Canonical/FORGE_CANON.md`

This file defines how ForgeOS engineering work must be performed. Product vision,
architecture decisions, terminology, and roadmap authority remain under
`Docs/Canonical/`.

## Authority and Conflict Resolution

- `Docs/Canonical/*` defines product intent, architecture intent, terminology, and
  roadmap truth.
- `PROJECT_INSTRUCTION.md` defines execution policy, engineering workflow, validation
  discipline, reporting requirements, and agent behavior.
- Neither authority may be silently reinterpreted to bypass the other.

If these sources appear to conflict:

1. Stop work at the conflicting decision.
2. Report the exact conflict and the affected files or behavior.
3. Do not silently choose one source or implement a compromise.
4. Request clarification or update the appropriate canonical source before continuing.

Temporary exceptions must be explicit, documented with their reason and owner, limited
to the narrowest possible scope, and time-bounded where practical. An exception does not
create precedent or permanently change either authority.

## Engineering Syndicate

Operate as one coordinated multi-role engineering agent:

- **CTO:** Protect system stability, architectural coherence, maintainability, and
  long-term operational cost.
- **Systems Architect:** Design portable, observable, resource-aware components with
  conservative failure modes.
- **Senior Python Engineer:** Produce small, typed, testable Python 3.12 code that follows
  existing project conventions.

When these roles create competing priorities, choose system stability and the simplest
architecture that satisfies the requirement.

## Audit-First Workflow

Every implementation must follow this sequence:

1. **Audit:** Inspect the repository tree, applicable instructions, relevant code,
   configuration, tests, and Git working state before writing.
2. **Reuse:** Identify the canonical integration point and reuse existing modules,
   utilities, naming, and configuration mechanisms.
3. **Design:** State the intended files and behavior before making substantial changes.
4. **Implement:** Make focused changes that solve the root problem without modifying
   unrelated work.
5. **Validate:** Run the most specific tests first, then broader checks where practical.
6. **Report:** End with the Reporting Protocol defined below.

Never assume a file or utility is missing until the repository has been searched.
Preserve user changes already present in the working tree.

## Major Task Definition

A task is major when it does one or more of the following:

- Changes runtime behavior.
- Changes configuration structure or precedence.
- Changes hardware detection, identity matching, or profile behavior.
- Changes public interfaces, commands, scripts, or entry points.
- Changes validation rules or architecture boundaries.
- Changes multiple files with behavioral impact.
- Introduces or changes a dependency.
- Changes platform-specific behavior.
- Modifies canonical documentation or engineering policy.

Typo-only, formatting-only, and wording-only edits are not major unless specifically
requested as such or they alter meaning. Major tasks require the full Reporting Protocol.

## Architecture Rules

- Preserve Backend-first modularity and the canonical layers documented under
  `Docs/Canonical/`.
- Application and API code belongs under `Backend/`.
- Operational entry points and developer tooling belong under `Scripts/`.
- Reusable core runtime behavior belongs under `forge/runtime/`.
- Keep scripts thin. Shared logic must live in an importable module rather than being
  duplicated in command wrappers.
- Prefer standard-library solutions unless an existing project dependency provides a
  clearly better canonical abstraction.
- Use repository-relative paths derived from `pathlib.Path`; never depend on a specific
  user profile, drive letter, or current working directory.

## Hardware Profile Contract

- All system-level tuning and resource optimization must use
  `forge/runtime/hardware.py`.
- Consumers must use the generated profile rather than independently detecting CPU,
  memory, hostname, or machine type.
- The canonical profile names are exactly `office_desktop`, `laptop`, and `minimal`.
  Do not introduce aliases or alternate spellings without changing the central contract
  and its tests.
- Unknown or incomplete hardware data must select conservative limits and must not cause
  an uncaught exception.
- Partial or ambiguous detection must degrade to the safest applicable profile.
- A local override may refine resource behavior but must not disable mandatory safety
  limits or bypass conservative fallback behavior.
- Resource tuning, profile selection, hostname normalization, and machine identity
  matching belong in the central hardware/runtime layer.
- Normalize hostnames for matching and compare them case-insensitively. Preserve the
  detected hostname only for display and diagnostics.
- Laptop behavior must minimize heat, background concurrency, indexing pressure, and
  memory footprint.
- Office Desktop behavior may use higher concurrency only within explicit worker and
  memory limits.

The canonical reference hostname is `IT-STATION`, normally classified as
`office_desktop` with 12 logical processors and 16 GB installed RAM.

## Configuration Rules

The effective machine configuration hierarchy is:

1. `config/system.generated.json` provides detected defaults.
2. `config/system.local.json` provides machine-local overrides and takes precedence.

Rules:

- Treat the hierarchy as:
  `system.generated.json < system.local.json`.
- Never overwrite, delete, normalize, or regenerate `system.local.json`.
- Do not overwrite `system.generated.json` by default. Regenerate it only through an
  explicit force/update action.
- Merge local overrides deeply so an override can change one setting without discarding
  unrelated generated settings.
- Keep generated and local machine configuration out of Git.
- Do not place machine tuning in `Backend/.env` when the runtime JSON hierarchy is the
  established mechanism.
- Never log secrets or environment values.

### Generated Configuration Lifecycle

An explicit force/update action means a deliberate invocation of the supported
configuration manager regeneration option, such as `--force`, by the machine owner or an
authorized contributor who has reviewed the resulting diff or output. File deletion,
incidental startup, bootstrap, tests, and background execution do not count as explicit
authorization.

Regeneration is appropriate when:

- Hardware, hostname, assigned resources, or the selected profile changes.
- The generated configuration schema or profile defaults change.
- The generated file is missing, invalid, or known to predate a relevant runtime change.
- A contributor intentionally verifies a new detection or tuning implementation.

Suspect stale configuration when detected hardware differs from recorded hardware,
required schema fields are absent, `schema_version` is unsupported, or runtime defaults
have changed since generation. Schema evolution must be explicit, validated, and either
backward compatible or accompanied by a documented migration/regeneration requirement.

Every regeneration must:

- Display or inspect the detected hardware, selected profile, and resulting limits.
- Preserve `config/system.local.json` byte-for-byte.
- Apply local overrides only after generated defaults.
- Report whether the generated file was created, replaced, or left unchanged.
- Never silently erase user intent. If an override conflicts with a new safety
  requirement, stop and report the conflict rather than rewriting the override.

## Platform Support and Systems Rules

- Primary target: modern Windows environments used by ForgeOS.
- Secondary execution environments: Linux and WSL for development and validation where
  appropriate.
- Do not claim support for an untested platform or broaden the support contract
  implicitly.
- Use standard Python APIs first: `socket`, `os`, and `platform`.
- On native Windows, provide bounded PowerShell/CIM fallbacks for hardware information.
- Subprocess calls must use argument lists, timeouts, captured output, and graceful error
  handling.
- Never make successful execution depend solely on WMI, CIM, PowerShell, `/proc`, or
  another platform-specific interface.
- Linux/WSL reports memory assigned to the WSL virtual machine, which may be lower than
  native Windows installed RAM. Native Windows CIM results are authoritative for Windows
  capacity planning.

## Dependency and Reproducibility Policy

- Prefer the Python standard library when it is sufficient and maintainable.
- Every new dependency requires a concrete justification tied to the change.
- Dependency changes must be minimal, targeted, and consistent with the repository's
  existing package and version-management conventions.
- Do not add a package merely to avoid straightforward, testable Python.
- Changes to `requirements.txt`, `pyproject.toml`, or other dependency manifests require
  installation/import validation where practical and explicit reporting.
- Do not introduce new package-management or lockfile tooling unless the repository
  adopts it through an explicit architectural decision.

## Python Standards

- Target Python 3.12 and use modern type hints.
- Add `from __future__ import annotations` where consistent with the surrounding module.
- Prefer immutable data models for detected system facts.
- Keep functions focused, deterministic, and directly testable.
- Catch only expected operational errors; never hide programming errors with broad
  exception handling.
- Use UTF-8 and stable, human-readable JSON output.
- Maintain the configured 100-character line length.

## Security and Operational Safety

- Do not log secrets, tokens, credentials, sensitive environment values, or unnecessary
  machine-specific details in logs or committed files.
- Treat machine-local configuration and detected hardware data as non-portable unless
  explicitly designed and reviewed for sharing.
- Never hardcode user-specific paths, profile directories, drive letters, or local
  credentials.
- Avoid shell-string subprocess execution. Use argument lists, timeouts, captured output,
  and bounded failure handling.
- Do not commit generated machine configuration or local overrides.
- Prefer conservative failure behavior for resource inspection and configuration writes.

## Validation Matrix

Validation must match the change surface. No implementation or pull request is complete
until the applicable rows below are satisfied:

- **Documentation-only:** Run Markdown whitespace/sanity checks, verify links and file
  references where practical, and confirm that meaning and authority boundaries remain
  consistent. Runtime tests are not required unless behavior or executable examples
  changed.
- **Python modules:** Run syntax/import validation and the relevant unit tests under
  `Backend/tests/unit/` using the repository-local `.venv`.
- **Runtime, hardware, or configuration:** Run relevant unit tests plus generated-config
  inspection, overwrite-protection verification, local-override precedence verification,
  syntax/import validation, and platform-specific execution notes or reasoning where
  applicable.
- **Scripts or CLI:** Exercise help/argument parsing, a successful path, expected failure
  behavior, exit status, and filesystem side effects where applicable.
- **Cross-platform-sensitive:** Validate on each available relevant environment and
  document platform-specific reasoning, fallbacks, and unexecuted paths.
- **Dependencies:** Validate the changed manifest, environment installation or resolution
  where practical, and imports or tests that prove the dependency is usable.

All change types require review of `git status` and the focused diff for unintended or
unrelated modifications.

Preferred Windows command:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s Backend\tests\unit -v
```

If the current environment cannot execute the Windows virtual environment, run the
closest available Python 3.12 validation, report the limitation explicitly, and require
native Windows validation before merge whenever correctness depends on Windows behavior.
Clearly separate what was executed from what was reasoned about.

## Documentation Rules

- Maintain authoritative product and architecture documentation under `Docs/Canonical/`.
- Update canonical documentation when behavior, architecture, terminology, or operating
  constraints change.
- Record durable architectural decisions in `Docs/Canonical/DECISIONS.md`.
- Keep `Docs/Canonical/CHANGELOG.md` aligned with meaningful released changes.
- Do not create competing architecture or policy documents outside their established
  locations.
- This file governs engineering workflow; it does not replace the ForgeOS Canon.

## Anti-Patterns

The following are prohibited:

- Hardcoded absolute paths, Windows user directories, drive letters, or host-specific
  filesystem assumptions.
- Untyped new Python interfaces or ignoring type-checking-friendly design.
- Duplicate hardware detection, configuration merging, path resolution, logging, or
  utility functions.
- Resource settings chosen without consulting the hardware profile.
- Blindly overwriting `.env`, generated configuration, or local override files.
- Unbounded subprocesses, shell-string command execution, or uncaught inspection errors.
- Adding dependencies for behavior already covered safely by the standard library.
- Mixing unrelated formatting, documentation, or refactoring changes into a focused task.
- Pushing, force-resetting, or discarding working-tree changes without explicit approval.

## Reporting Protocol

Every major task must end with these exact sections. Reports must separate verified facts
from assumptions and environment limitations; do not describe an unexecuted check as
verified.

### Implemented

- State what changed, where it changed, and why.
- List created and modified files.
- State the architectural integration point and distinguish reused components from new
  components.

### Verified

- List what was actually checked, the commands or methods used, and what passed.
- Report detected hardware/profile output when relevant.
- Label assumptions explicitly.
- State what could not be verified, environment limitations, skipped checks, and required
  follow-up validation.

### Git Status

- State the current branch and every task-related touched file.
- List task-related changes separately from pre-existing or unrelated working-tree
  changes, and confirm unrelated changes were left untouched.
- Confirm whether anything is staged, committed, or pushed.
- Provide a concise proposed commit message when changes were made.

## Current Operational Baseline

- Canonical reference machine identity: `IT-STATION`.
- Expected profile: `office_desktop`.
- Runtime target: Python 3.12.
- Known environment distinction: WSL-visible RAM can differ from native Windows
  installed RAM.
- Hardware authority: `forge/runtime/hardware.py`.
- Configuration entry point: `Scripts/system_config_manager.py`.

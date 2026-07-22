# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_Hardware & Governance Baseline_

### Added

- **Hardware Configuration Engine (`forge/runtime/hardware.py`)**
  - Added platform-aware hostname, logical CPU, RAM, and platform detection.
  - Added Windows CIM/PowerShell queries with standard-library and POSIX/WSL fallbacks.
  - Added bounded worker, memory, parallel-build, and indexing recommendations.
- **Environment Classifier CLI (`Scripts/system_config_manager.py`)**
  - Added automatic `office_desktop`, `laptop`, and `minimal` profile classification.
  - Added clear hardware/profile logging, print-only inspection, and explicit forced
    regeneration support.
- **Configuration Hierarchy System**
  - Added generated defaults in `config/system.generated.json`.
  - Added optional deep-merged user overrides through `config/system.local.json`.
  - Added overwrite protection for existing generated configuration and Git exclusions
    for machine-local configuration.
- **Engineering Charter & Governance (`PROJECT_INSTRUCTION.md`)**
  - Added the Engineering Syndicate persona and audit-first development workflow.
  - Added authority boundaries, hardware and configuration contracts, validation matrix,
    security controls, and structured Git status reporting.
- **Unit Testing Suite (`Backend/tests/unit/test_hardware.py`)**
  - Added six Python 3.12 unit tests covering profile resolution, conservative laptop
    settings, local override precedence, and generated-config overwrite protection.

### Changed

- **Branch Synchronization & Git Governance**
  - Synchronized `feature/configuration-engine` with `main` through merge commit
    `3d7e45b`.
  - Aligned the feature branch with the hardware runtime and governance baseline tracked
    on `main` and the corresponding remote branches.

### Known Technical Debt / Upcoming

- Normalize repository line-ending behavior with an explicit `.gitattributes` policy
  for LF and CRLF handling.
- Integrate live resource telemetry into the runtime orchestrator in
  `forge/runtime/runtime.py`.
- Extend hardware inspection with GPU detection, storage performance classification,
  and virtualization-environment checks.

## [0.1.0]

- Bootstrap Engine
- Initial Repository Structure

"""StitchLab G-Code Intake.

Streaming parser, compatibility checks, metadata extraction. Phase 1 ships
the CLI; Moonraker integration and thumbnail rendering follow in later
phases. See docs in Reports&Plans/G-Code Intake Stable Job Preview Plan.md.
"""

from .version import CHECKER_VERSION, SCHEMA_VERSION

__all__ = ["CHECKER_VERSION", "SCHEMA_VERSION"]

"""Version constants used as cache-invalidation tokens.

CHECKER_VERSION bumps whenever the parser or check logic changes in a way
that could yield a different verdict for the same input file. The Moonraker
component derives analysis_key from sha256(content) + CHECKER_VERSION, so a
bump invalidates all cached reports without touching files on disk.

SCHEMA_VERSION names the JSON shape consumed by Mainsail / dashboard.
"""

CHECKER_VERSION = "v2"  # v2: hoop check also enforces position
SCHEMA_VERSION = "stitchlab_intake.v1"

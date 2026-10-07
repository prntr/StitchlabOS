"""Version constants used as cache-invalidation tokens.

CHECKER_VERSION bumps whenever the parser or check logic changes in a way
that could yield a different verdict for the same input file. The Moonraker
component derives analysis_key from sha256(content) + CHECKER_VERSION, so a
bump invalidates all cached reports without touching files on disk.

SCHEMA_VERSION names the JSON shape consumed by Mainsail / dashboard.
"""

CHECKER_VERSION = "v4"  # v4: Z-step stitch model, contract commands, G20 and
                        # (...) comments block, machine travel check
SCHEMA_VERSION = "stitchlab_intake.v1"

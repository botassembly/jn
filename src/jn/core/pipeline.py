"""Pipeline orchestration for JN data flows.

DEPRECATED: This module's functions have been replaced by the addressability system.
CLI commands now use AddressResolver directly for cleaner, more flexible pipeline construction.

This module is retained only for PipelineError, which may be used in tests or external code.
"""


class PipelineError(Exception):
    """Error during pipeline execution."""

    pass

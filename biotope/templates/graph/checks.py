"""Executable acceptance: does this graph answer what it claims to answer?

Derive each expectation from the source, a published figure or a curated
answer. A check that recomputes the pipeline's logic agrees with it by
construction and is blind to the records it exists to find.
"""

from biotope.graph import ValidationCheck


VALIDATION_CHECKS: tuple[ValidationCheck, ...] = ()

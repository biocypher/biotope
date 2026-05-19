"""Layer 1: schema codegen.

Generates a typed Python module of ``Dataset*`` and ``Field*`` classes from a
Croissant model so downstream layers can refer to fields symbolically rather
than by string.
"""

from biotope.croissant.codegen.schema import render_schema_module

__all__ = ["render_schema_module"]

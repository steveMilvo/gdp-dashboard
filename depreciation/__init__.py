"""Australian investment-property tax depreciation engine and validation layer.

Public API:
    calc        -- pure depreciation calculation engine (Div 43 + Div 40)
    assets      -- ATO effective-life reference data
    validation  -- cross-reference proposed/LLM data against the tax rules
    llm         -- optional LLM-assisted extraction (always validated)
"""

from . import assets, calc, llm, validation

__all__ = ["assets", "calc", "llm", "validation"]

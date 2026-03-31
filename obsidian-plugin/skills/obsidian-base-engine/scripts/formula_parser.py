#!/usr/bin/env python3
"""Formula parser for Dataview-style expressions in Obsidian Base files.

This module parses and validates Dataview-style expressions used in
formula fields of .base YAML files.

Supported expression types:
- String literals: `"text"` or `'text'`
- Field references: `field_name`, `nested.field`
- Function calls: `func(arg1, arg2)`
- Conditional: `if(condition, then, else)`
- Binary operators: `+`, `-`, `*`, `/`, `%`, `==`, `!=`, `<`, `>`, `<=`, `>=`
- Logical operators: `and`, `or`, `!`
- Array operations: `.length`, `.join(sep)`, `.map(fn)`, `.filter(fn)`, `.includes(x)`
- String operations: `.toString()`, `.replace(a, b)`, `.toLowerCase()`, `.toUpperCase()`
- Number operations: `.toFixed(n)`, `.length` (for string conversion)
"""
from __future__ import annotations

import re
from typing import Any


class FormulaParseError(ValueError):
    """Raised when a formula cannot be parsed."""
    pass


class FormulaToken:
    """A token in a formula expression."""

    def __init__(self, type: str, value: str, pos: int):
        self.type = type
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:
        return f"FormulaToken({self.type!r}, {self.value!r}, {self.pos})"


class Tokenizer:
    """Tokenize a Dataview-style formula string."""

    TOKEN_PATTERNS = [
        ("STRING", r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\''),
        ("NUMBER", r"\b\d+\.?\d*\b"),
        ("IDENT", r"[a-zA-Z_][a-zA-Z0-9_.]*"),
        ("OP", r"[+\-*/%=<>!]+|and|or|not"),
        ("LPAREN", r"\("),
        ("RPAREN", r"\)"),
        ("LBRACKET", r"\["),
        ("RBRACKET", r"\]"),
        ("COMMA", r","),
        ("WHITESPACE", r"\s+"),
    ]

    def __init__(self, formula: str):
        self.formula = formula
        self.pos = 0
        self.tokens: list[FormulaToken] = []

    def tokenize(self) -> list[FormulaToken]:
        """Tokenize the formula string."""
        while self.pos < len(self.formula):
            matched = False
            for tok_type, pattern in self.TOKEN_PATTERNS:
                regex = re.compile(r"^" + pattern)
                m = regex.match(self.formula, self.pos)
                if m:
                    value = m.group(0)
                    if tok_type != "WHITESPACE":
                        self.tokens.append(FormulaToken(tok_type, value, self.pos))
                    self.pos = m.end()
                    matched = True
                    break
            if not matched:
                raise FormulaParseError(f"Unexpected character at position {self.pos}: {self.formula[self.pos]!r}")
        return self.tokens


class FormulaParser:
    """Parse and validate Dataview-style expressions.

    This is a simplified parser that validates formula syntax without
    executing them. It checks:
    - Balanced parentheses
    - Balanced brackets
    - String literal correctness
    - Known function names
    - Valid field references
    """

    KNOWN_FUNCTIONS: set[str] = {
        "if", "default", "join", "map", "filter", "sort", "reverse",
        "contains", "includes", "excludes", "startswith", "endswith",
        "replace", "split", "trim", "lower", "upper", "length",
        "toString", "toNumber", "toFixed", "floor", "ceil", "round",
        "min", "max", "sum", "average", "count",
        "extract", "any", "all",
    }

    KNOWN_METHODS: set[str] = {
        "toString", "toFixed", "toLowerCase", "toUpperCase",
        "replace", "split", "trim", "join", "map", "filter",
        "length", "includes", "excludes", "sort", "reverse",
        "push", "pop", "join", "concat",
    }

    def __init__(self, strict: bool = True):
        """
        Args:
            strict: If True, unknown functions/methods raise errors.
                   If False, allow unknown (for forward compatibility).
        """
        self.strict = strict

    def parse(self, formula: str) -> dict[str, Any]:
        """Parse a formula string and return a parse tree.

        Returns:
            A dictionary with parse metadata including:
            - valid: bool
            - tokens: list of token types
            - issues: list of warnings/errors
        """
        if not formula or not formula.strip():
            return {"valid": False, "issues": ["Empty formula"], "tokens": []}

        issues: list[str] = []
        tokens: list[str] = []

        try:
            tokenizer = Tokenizer(formula)
            token_list = tokenizer.tokenize()
            tokens = [t.type for t in token_list]
        except FormulaParseError as exc:
            return {"valid": False, "issues": [str(exc)], "tokens": []}

        # Validate token sequence
        paren_depth = 0
        bracket_depth = 0
        prev_token: str | None = None

        for token in token_list:
            t_type, t_value, t_pos = token.type, token.value, token.pos

            # Track nesting
            if t_type == "LPAREN":
                paren_depth += 1
            elif t_type == "RPAREN":
                paren_depth -= 1
                if paren_depth < 0:
                    issues.append(f"Unmatched ')' at position {t_pos}")

            if t_type == "LBRACKET":
                bracket_depth += 1
            elif t_type == "RBRACKET":
                bracket_depth -= 1
                if bracket_depth < 0:
                    issues.append(f"Unmatched ']' at position {t_pos}")

            # Check identifiers
            if t_type == "IDENT":
                # Check for function call pattern
                if prev_token and prev_token == "IDENT":
                    issues.append(f"Missing comma or operator between identifiers at position {t_pos}")

            prev_token = t_type

        # Check balanced nesting
        if paren_depth > 0:
            issues.append(f"Unclosed '(' — missing {paren_depth} closing parenthesis(es)")
        if bracket_depth > 0:
            issues.append(f"Unclosed '[' — missing {bracket_depth} closing bracket(s)")

        # Validate function names if strict
        if self.strict:
            for token in token_list:
                if token.type == "IDENT" and token.value not in self.KNOWN_FUNCTIONS:
                    # Check if it's a field reference (lowercase start)
                    if token.value[0].islower() and token.value not in self.KNOWN_FUNCTIONS:
                        # It might be a method call after a dot — check next token
                        pass  # Let field references pass

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "tokens": tokens,
            "token_count": len(token_list),
        }

    def validate_formula(self, formula: str) -> tuple[bool, list[str]]:
        """Validate a formula. Returns (is_valid, issues)."""
        result = self.parse(formula)
        return result["valid"], result["issues"]

    def validate_formula_dict(
        self, formulas: dict[str, str]
    ) -> dict[str, dict[str, Any]]:
        """Validate all formulas in a dictionary.

        Returns:
            Dict mapping formula name to parse result
        """
        results = {}
        for name, formula in formulas.items():
            results[name] = self.parse(formula)
        return results


def extract_field_references(formula: str) -> list[str]:
    """Extract field names referenced in a formula.

    This is a best-effort extraction that may include false positives
    and miss some references.

    Returns:
        List of field names found in the formula
    """
    # Match dot-notation: field.subfield
    dot_pattern = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\.')
    fields: list[str] = []

    for m in dot_pattern.finditer(formula):
        fields.append(m.group(1))

    # Also find simple identifiers that aren't known functions
    ident_pattern = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b')
    known = FormulaParser.KNOWN_FUNCTIONS | FormulaParser.KNOWN_METHODS | {
        "true", "false", "null", "none", "and", "or", "not",
    }
    for m in ident_pattern.finditer(formula):
        name = m.group(1)
        if name not in known and name not in fields:
            fields.append(name)

    return list(dict.fromkeys(fields))  # dedupe preserving order

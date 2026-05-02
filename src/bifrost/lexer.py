"""Lexer for Bifrost source code.

Implements RFC-0002 lexical tokens including indentation-sensitive INDENT/DEDENT.
"""

from __future__ import annotations

from dataclasses import dataclass


KEYWORDS = {
    "pipeline",
    "function",
    "iterate",
    "module",
    "requires",
    "guarantees",
    "uncertain",
    "strategy",
    "confidence",
    "yield",
    "with",
    "when",
    "try",
    "on_error",
    "on_low_confidence",
    "primary",
    "fallback",
    "alternative",
    "collect",
    "drop",
    "skip",
    "halt",
    "and",
    "or",
    "not",
    "true",
    "false",
    "null",
    "old",
}


SYMBOL_TOKENS = {
    "(": "LPAREN",
    ")": "RPAREN",
    "[": "LBRACKET",
    "]": "RBRACKET",
    "{": "LBRACE",
    "}": "RBRACE",
    ",": "COMMA",
    ":": "COLON",
    ".": "DOT",
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    "%": "PERCENT",
    "<": "LT",
    ">": "GT",
    "=": "ASSIGN",
    "|": "PIPE",
    "?": "QUESTION",
}


@dataclass(frozen=True)
class Token:
    type: str
    value: str
    line: int
    column: int


class LexerError(ValueError):
    pass


class Lexer:
    def tokenize(self, source: str) -> list[Token]:
        tokens: list[Token] = []
        indent_stack = [0]

        # Keep trailing empty line behavior predictable.
        lines = source.splitlines()
        if source.endswith("\n"):
            lines.append("")

        for line_no, raw_line in enumerate(lines, start=1):
            if "\t" in raw_line:
                raise LexerError(f"Tabs are forbidden (line {line_no}).")

            stripped = raw_line.lstrip(" ")
            indent = len(raw_line) - len(stripped)

            # Blank/comment-only lines do not affect indentation.
            if stripped == "" or stripped.startswith("#"):
                continue

            if indent % 2 != 0:
                raise LexerError(
                    f"Indentation must use multiples of 2 spaces (line {line_no})."
                )

            current_indent = indent_stack[-1]
            if indent > current_indent:
                indent_stack.append(indent)
                tokens.append(Token("INDENT", "", line_no, 1))
            elif indent < current_indent:
                while len(indent_stack) > 1 and indent < indent_stack[-1]:
                    indent_stack.pop()
                    tokens.append(Token("DEDENT", "", line_no, 1))
                if indent != indent_stack[-1]:
                    raise LexerError(
                        f"Inconsistent dedent level at line {line_no}: {indent}."
                    )

            tokens.extend(self._tokenize_line(stripped, line_no, indent + 1))
            tokens.append(Token("NEWLINE", "\\n", line_no, len(raw_line) + 1))

        while len(indent_stack) > 1:
            indent_stack.pop()
            tokens.append(Token("DEDENT", "", len(lines) + 1, 1))

        tokens.append(Token("EOF", "", len(lines) + 1, 1))
        return tokens

    def _tokenize_line(self, text: str, line_no: int, start_col: int) -> list[Token]:
        tokens: list[Token] = []
        i = 0
        while i < len(text):
            ch = text[i]
            col = start_col + i

            if ch == "#":
                break
            if ch.isspace():
                i += 1
                continue

            if ch in {"'", '"'}:
                token, consumed = self._read_string(text[i:], line_no, col)
                tokens.append(token)
                i += consumed
                continue

            if ch.isdigit():
                token, consumed = self._read_number(text[i:], line_no, col)
                tokens.append(token)
                i += consumed
                continue

            if ch.isalpha() or ch == "_":
                j = i + 1
                while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                value = text[i:j]
                typ = "KEYWORD" if value in KEYWORDS else "IDENTIFIER"
                tokens.append(Token(typ, value, line_no, col))
                i = j
                continue

            # Multi-char operators first.
            if text.startswith("->", i):
                tokens.append(Token("ARROW_ASCII", "->", line_no, col))
                i += 2
                continue
            if text.startswith("==", i):
                tokens.append(Token("EQ", "==", line_no, col))
                i += 2
                continue
            if text.startswith("!=", i):
                tokens.append(Token("NE", "!=", line_no, col))
                i += 2
                continue
            if text.startswith(">=", i):
                tokens.append(Token("GE", ">=", line_no, col))
                i += 2
                continue
            if text.startswith("<=", i):
                tokens.append(Token("LE", "<=", line_no, col))
                i += 2
                continue

            if ch == "→":
                tokens.append(Token("ARROW", ch, line_no, col))
                i += 1
                continue

            tok_type = SYMBOL_TOKENS.get(ch)
            if tok_type is not None:
                tokens.append(Token(tok_type, ch, line_no, col))
                i += 1
                continue

            raise LexerError(f"Unexpected character {ch!r} at {line_no}:{col}")

        return tokens

    def _read_string(self, text: str, line_no: int, col: int) -> tuple[Token, int]:
        quote = text[0]
        i = 1
        value_parts: list[str] = []
        while i < len(text):
            ch = text[i]
            if ch == "\\":
                if i + 1 >= len(text):
                    raise LexerError(f"Invalid escape at {line_no}:{col + i}")
                value_parts.append(text[i : i + 2])
                i += 2
                continue
            if ch == quote:
                raw = quote + "".join(value_parts) + quote
                return Token("STRING", raw, line_no, col), i + 1
            value_parts.append(ch)
            i += 1
        raise LexerError(f"Unterminated string at {line_no}:{col}")

    def _read_number(self, text: str, line_no: int, col: int) -> tuple[Token, int]:
        i = 0
        while i < len(text) and text[i].isdigit():
            i += 1
        if i < len(text) and text[i] == ".":
            j = i + 1
            while j < len(text) and text[j].isdigit():
                j += 1
            if j == i + 1:
                raise LexerError(f"Malformed float at {line_no}:{col}")
            return Token("NUMBER", text[:j], line_no, col), j
        return Token("NUMBER", text[:i], line_no, col), i


__all__ = ["Lexer", "LexerError", "Token", "KEYWORDS"]

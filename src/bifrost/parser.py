"""Parser for Bifrost token streams.

Builds a lightweight AST for the current RFC grammar subset.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .lexer import Lexer, Token


class ParserError(ValueError):
    """Raised when parsing fails."""


@dataclass(frozen=True)
class Expr:
    text: str


@dataclass(frozen=True)
class CallExpr:
    name: str
    args: list[Expr] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineStep:
    call: CallExpr
    action: str | None = None


@dataclass(frozen=True)
class PipelineDecl:
    name: str
    first_step: PipelineStep
    next_steps: list[PipelineStep] = field(default_factory=list)
    with_items: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FunctionClause:
    kind: str
    value: str


@dataclass(frozen=True)
class FunctionDecl:
    name: str
    params: list[str]
    return_type: str
    clauses: list[FunctionClause] = field(default_factory=list)


@dataclass(frozen=True)
class Program:
    declarations: list[PipelineDecl | FunctionDecl] = field(default_factory=list)


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    @classmethod
    def parse_source(cls, source: str) -> Program:
        lexer = Lexer()
        return cls(lexer.tokenize(source)).parse_program()

    def parse_program(self) -> Program:
        decls: list[PipelineDecl | FunctionDecl] = []
        while not self._at("EOF"):
            self._skip_newlines()
            if self._at("EOF"):
                break
            if self._keyword("pipeline"):
                decls.append(self._parse_pipeline_decl())
            elif self._keyword("function"):
                decls.append(self._parse_function_decl())
            else:
                token = self._peek()
                raise ParserError(
                    f"Expected top-level declaration at {token.line}:{token.column}, got {token.type} {token.value!r}"
                )
        return Program(declarations=decls)

    def _parse_pipeline_decl(self) -> PipelineDecl:
        self._expect_keyword("pipeline")
        name = self._expect("IDENTIFIER").value
        self._expect("COLON")
        self._expect("NEWLINE")
        self._expect("INDENT")

        first = self._parse_pipeline_step(first=True)
        next_steps: list[PipelineStep] = []
        with_items: list[str] = []
        while not self._at("DEDENT"):
            if self._at("ARROW") or self._at("ARROW_ASCII"):
                next_steps.append(self._parse_pipeline_step(first=False))
            elif self._keyword("with"):
                with_items = self._parse_with_clause()
            else:
                token = self._peek()
                raise ParserError(
                    f"Unexpected token in pipeline body at {token.line}:{token.column}: {token.type} {token.value!r}"
                )

        self._expect("DEDENT")
        return PipelineDecl(name=name, first_step=first, next_steps=next_steps, with_items=with_items)

    def _parse_pipeline_step(self, *, first: bool) -> PipelineStep:
        if not first:
            self._advance()  # ARROW or ARROW_ASCII
        call = self._parse_call()
        action: str | None = None
        if self._at("COLON"):
            self._advance()
            action = self._consume_line_text()
        self._expect("NEWLINE")
        return PipelineStep(call=call, action=action)

    def _parse_with_clause(self) -> list[str]:
        self._expect_keyword("with")
        self._expect("COLON")
        parts: list[str] = []
        current: list[str] = []
        while not self._at("NEWLINE"):
            if self._at("COMMA"):
                if current:
                    parts.append("".join(current).strip())
                    current = []
                self._advance()
                continue
            current.append(self._advance().value)
        if current:
            parts.append("".join(current).strip())
        self._expect("NEWLINE")
        return [p for p in parts if p]

    def _parse_function_decl(self) -> FunctionDecl:
        self._expect_keyword("function")
        name = self._expect("IDENTIFIER").value
        self._expect("LPAREN")
        params = self._parse_param_list()
        self._expect("RPAREN")

        if self._at("ARROW") or self._at("ARROW_ASCII"):
            self._advance()
        else:
            raise ParserError("Function return arrow (→ or ->) is required.")

        return_type = self._consume_until("COLON")
        self._expect("COLON")
        self._expect("NEWLINE")
        self._expect("INDENT")

        clauses: list[FunctionClause] = []
        while not self._at("DEDENT"):
            key_tok = self._advance()
            if key_tok.type not in {"KEYWORD", "IDENTIFIER"}:
                raise ParserError(
                    f"Expected function clause key at {key_tok.line}:{key_tok.column}, got {key_tok.type}."
                )
            self._expect("COLON")
            value = self._consume_line_text()
            self._expect("NEWLINE")
            clauses.append(FunctionClause(kind=key_tok.value, value=value))

        self._expect("DEDENT")
        return FunctionDecl(name=name, params=params, return_type=return_type.strip(), clauses=clauses)

    def _parse_param_list(self) -> list[str]:
        params: list[str] = []
        while not self._at("RPAREN"):
            item = self._consume_until_any({"COMMA", "RPAREN"}).strip()
            if item:
                params.append(item)
            if self._at("COMMA"):
                self._advance()
        return params

    def _parse_call(self) -> CallExpr:
        name = self._expect("IDENTIFIER").value
        self._expect("LPAREN")
        args: list[Expr] = []
        current: list[str] = []
        depth = 1
        while depth > 0:
            tok = self._advance()
            if tok.type == "LPAREN":
                depth += 1
                current.append(tok.value)
            elif tok.type == "RPAREN":
                depth -= 1
                if depth == 0:
                    if current:
                        args.append(Expr("".join(current).strip()))
                    break
                current.append(tok.value)
            elif tok.type == "COMMA" and depth == 1:
                args.append(Expr("".join(current).strip()))
                current = []
            else:
                current.append(tok.value)
        return CallExpr(name=name, args=[a for a in args if a.text])

    def _consume_line_text(self) -> str:
        out: list[str] = []
        while not self._at("NEWLINE"):
            out.append(self._advance().value)
        return "".join(out).strip()

    def _consume_until(self, token_type: str) -> str:
        out: list[str] = []
        while not self._at(token_type):
            out.append(self._advance().value)
        return "".join(out)

    def _consume_until_any(self, token_types: set[str]) -> str:
        out: list[str] = []
        while self._peek().type not in token_types:
            out.append(self._advance().value)
        return "".join(out)

    def _skip_newlines(self) -> None:
        while self._at("NEWLINE"):
            self._advance()

    def _keyword(self, value: str) -> bool:
        tok = self._peek()
        return tok.type == "KEYWORD" and tok.value == value

    def _expect_keyword(self, value: str) -> Token:
        tok = self._peek()
        if tok.type == "KEYWORD" and tok.value == value:
            return self._advance()
        raise ParserError(f"Expected keyword {value!r} at {tok.line}:{tok.column}")

    def _expect(self, token_type: str) -> Token:
        tok = self._peek()
        if tok.type != token_type:
            raise ParserError(
                f"Expected {token_type}, got {tok.type} {tok.value!r} at {tok.line}:{tok.column}"
            )
        return self._advance()

    def _at(self, token_type: str) -> bool:
        return self._peek().type == token_type

    def _peek(self) -> Token:
        return self.tokens[self.i]

    def _advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok


__all__ = [
    "Parser",
    "ParserError",
    "Program",
    "PipelineDecl",
    "PipelineStep",
    "FunctionDecl",
    "FunctionClause",
    "CallExpr",
    "Expr",
]

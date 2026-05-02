"""Bifrost AST -> Python transpiler."""

from __future__ import annotations

from .parser import FunctionDecl, PipelineDecl, PipelineStep, Program


class Transpiler:
    def transpile(self, program: Program) -> str:
        chunks: list[str] = ["# Generated from Bifrost AST\n"]
        for decl in program.declarations:
            if isinstance(decl, PipelineDecl):
                chunks.append(self._emit_pipeline(decl))
            elif isinstance(decl, FunctionDecl):
                chunks.append(self._emit_function(decl))
        return "\n\n".join(chunks).strip() + "\n"

    def _emit_pipeline(self, decl: PipelineDecl) -> str:
        lines = [f"def pipeline_{decl.name}(input_value=None):"]
        steps = [decl.first_step, *decl.next_steps]
        lines.append("    _current = input_value")
        for step in steps:
            lines.extend(self._emit_pipeline_step(step))
        if decl.with_items:
            joined = ", ".join(decl.with_items)
            lines.append(f"    # with: {joined}")
        lines.append("    return _current")
        return "\n".join(lines)

    def _emit_pipeline_step(self, step: PipelineStep) -> list[str]:
        arg_list = ", ".join(arg.text for arg in step.call.args)
        if arg_list:
            invoke = f"{step.call.name}(_current, {arg_list})"
        else:
            invoke = f"{step.call.name}(_current)"

        lines = [f"    _current = {invoke}"]
        if step.action:
            lines.append(f"    # action: {step.action}")
        return lines

    def _emit_function(self, decl: FunctionDecl) -> str:
        params = ", ".join(p.split(":")[0].strip() for p in decl.params if p.strip())
        lines = [f"def {decl.name}({params}):", f"    # returns: {decl.return_type}"]
        for clause in decl.clauses:
            lines.append(f"    # {clause.kind}: {clause.value}")
        lines.append('    raise NotImplementedError("Generated from Bifrost; implement body.")')
        return "\n".join(lines)


__all__ = ["Transpiler"]

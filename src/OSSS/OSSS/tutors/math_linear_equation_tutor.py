from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Optional: local reasoning/explanation without external APIs
import sympy as sp


# ---------- Base interface (adapter) ----------

class Tutor:
    """
    Base interface for a subject/skill-specific tutor.
    Implement `run()` in subclasses.
    """
    id: str = "base_tutor"
    domains: list[str] = []  # e.g., ["math.algebra.linear_equations"]

    async def run(self, prompt: str, context: dict) -> Dict[str, Any]:
        """
        Args:
            prompt: student/user input (e.g., "Solve 2x + 3 = 9")
            context: session/student info, objective_code, tools, etc.

        Returns:
            {
              "response": str,                # student-facing answer
              "evidence": { ... },            # steps, checks, citations
              "confidence": float,            # 0..1
            }
        """
        raise NotImplementedError


# ---------- Example concrete tutor ----------

@dataclass
class ParseResult:
    expr_lhs: sp.Expr
    expr_rhs: sp.Expr
    symbol: sp.Symbol


class MathLinearEqTutor(Tutor):
    """
    Solves simple linear equations in one variable (e.g., 2x + 3 = 9),
    verifies with sympy, and returns a step-by-step explanation.
    """
    id = "math_linear_eq_v1"
    domains = ["math.algebra.linear_equations"]

    async def run(self, prompt: str, context: dict) -> Dict[str, Any]:
        # 1) Parse the problem (best-effort)
        parsed = self._parse_equation(prompt)

        if not parsed:
            return {
                "response": (
                    "I can help with one-variable linear equations like "
                    "`2x + 3 = 9`. Could you rephrase the problem in that form?"
                ),
                "evidence": {
                    "parser": "sympy",
                    "parsed": None,
                    "error": "Unable to parse a simple linear equation",
                },
                "confidence": 0.25,
            }

        # 2) Solve
        solution, steps = self._solve_linear(parsed)

        # 3) Verify
        verified, check = self._verify_solution(parsed, solution)

        # 4) Build a student-facing explanation
        explanation = self._render_explanation(prompt, steps, solution, verified)

        # 5) Confidence: higher if verified
        confidence = 0.9 if verified else 0.6

        evidence = {
            "parser": "sympy",
            "symbol": str(parsed.symbol),
            "steps": steps,
            "verification": check,
        }

        return {
            "response": explanation,
            "evidence": evidence,
            "confidence": confidence,
        }

    # ---------- helpers ----------

    def _parse_equation(self, text: str) -> Optional[ParseResult]:
        """
        Tries to parse 'ax + b = c' style problems. We look for the first symbol.
        """
        # Heuristic: find first letter to treat as variable; default to x
        var_name = None
        for ch in text:
            if ch.isalpha():
                var_name = ch
                break
        if var_name is None:
            var_name = "x"

        x = sp.Symbol(var_name)

        # Split on '=' and parse both sides with sympy
        if "=" not in text:
            return None

        left, right = text.split("=", 1)
        try:
            lhs = sp.sympify(left, convert_xor=True)
            rhs = sp.sympify(right, convert_xor=True)
        except Exception:
            return None

        # Quick sanity check: appears linear in x?
        expr = lhs - rhs
        try:
            degree = sp.Poly(expr, x).degree()
        except Exception:
            # If not polynomial in x, we still might be able to solve; allow it
            degree = None

        if degree is not None and degree > 1:
            # Out of scope for this tutor
            return None

        return ParseResult(expr_lhs=lhs, expr_rhs=rhs, symbol=x)

    def _solve_linear(self, parsed: ParseResult) -> tuple[Optional[float | sp.Rational | sp.Expr], list[str]]:
        """
        Solve the linear equation and return (solution, steps).
        """
        x = parsed.symbol
        lhs, rhs = parsed.expr_lhs, parsed.expr_rhs
        steps: list[str] = []

        # Use sympy's solve for robustness
        try:
            sols = sp.solve(sp.Eq(lhs, rhs), x, dict=True)
        except Exception as e:
            steps.append(f"Error while solving: {e}")
            return None, steps

        if not sols:
            steps.append("No solution found (equation may be inconsistent).")
            return None, steps

        sol_expr = sols[0].get(x)
        steps.append(f"Set up equation: {sp.Eq(lhs, rhs)}")
        steps.append("Isolate the variable using inverse operations.")
        steps.append(f"Solution: {x} = {sp.simplify(sol_expr)}")

        return sol_expr, steps

    def _verify_solution(self, parsed: ParseResult, solution: Any) -> tuple[bool, dict]:
        """
        Substitute solution back into both sides and compare.
        """
        x = parsed.symbol
        lhs_val = parsed.expr_lhs.subs(x, solution)
        rhs_val = parsed.expr_rhs.subs(x, solution)
        equal = sp.simplify(lhs_val - rhs_val) == 0

        return equal, {
            "substitution": {str(x): str(solution)},
            "lhs_evaluated": str(sp.simplify(lhs_val)),
            "rhs_evaluated": str(sp.simplify(rhs_val)),
            "equal": bool(equal),
        }

    def _render_explanation(
        self,
        original_prompt: str,
        steps: list[str],
        solution: Any,
        verified: bool,
    ) -> str:
        bullet_steps = "\n".join(f"• {s}" for s in steps)
        tail = "I verified the solution by substitution." if verified else \
               "I could not fully verify; please double-check or provide a clearer equation."
        return (
            f"**Problem**: {original_prompt.strip()}\n\n"
            f"**Steps**:\n{bullet_steps}\n\n"
            f"**Answer**: {solution}\n\n"
            f"{tail}"
        )


# ---------- Minimal usage demo ----------

async def _demo():
    tutor = MathLinearEqTutor()
    prompt = "Solve 2x + 3 = 9"
    out = await tutor.run(prompt, context={"objective_code": "math.algebra.linear_equations"})
    print("Response:\n", out["response"])
    print("\nEvidence:", out["evidence"])
    print("\nConfidence:", out["confidence"])


if __name__ == "__main__":
    asyncio.run(_demo())

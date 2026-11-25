"""Isolated UI smoke checks for pre-lock warnings without requiring Streamlit server."""
import ast
from pathlib import Path
import unittest


def review_branch():
    tree = ast.parse(Path(__file__).with_name("site_ui.py").read_text(encoding="utf-8"))
    render = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "render_slate")
    branch = next(n for n in ast.walk(render)
                  if isinstance(n, ast.If)
                  and isinstance(n.test, ast.Compare)
                  and isinstance(n.test.left, ast.Name)
                  and n.test.left.id == "objective"
                  and any(isinstance(op, ast.NotEq) for op in n.test.ops)
                  and any(isinstance(c, ast.Constant) and c.value == "adjusted_fd_points"
                          for c in n.test.comparators))
    return branch


class UIIntegrationTests(unittest.TestCase):
    def test_gpp_branch_discloses_unverified_sensitivity(self):
        branch = review_branch()
        messages = [node for stmt in branch.body for node in ast.walk(stmt)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        self.assertTrue(any("not yet validated" in m.value for m in messages))

    def test_mean_fd_branch_runs_sensitivity(self):
        branch = review_branch()
        calls = [node for stmt in branch.orelse for node in ast.walk(stmt)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertEqual(sum(node.func.id == "rank_fragility" for node in calls), 1)

    def test_gpp_branch_never_calls_mean_fd_fragility(self):
        branch = review_branch()
        calls = [node for stmt in branch.body for node in ast.walk(stmt)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertFalse(any(node.func.id == "rank_fragility" for node in calls))

    def test_mean_fd_branch_catches_invalid_audit(self):
        branch = review_branch()
        handlers = [node for stmt in branch.orelse for node in ast.walk(stmt)
                    if isinstance(node, ast.ExceptHandler)]
        self.assertTrue(any("ValueError" in ast.unparse(h.type) for h in handlers))


if __name__ == "__main__":
    unittest.main()

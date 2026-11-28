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


def test_manual_reviewed_pool_export_preserves_same_research_features_as_archive():
    tree = ast.parse(Path(__file__).with_name('site_ui.py').read_text(encoding='utf-8'))
    render = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_slate')
    calls = [n for n in ast.walk(render) if isinstance(n,ast.Call)]
    freeze = [n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='freeze_research_features']
    assert len(freeze)==1
    downloads = [n for n in calls if n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='Download reviewed pool']
    assert len(downloads)==1
    assert ast.unparse(downloads[0].args[1])=='reviewed_export.to_csv(index=False)'
    assigns = [n for n in ast.walk(render) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='archive_pool' for t in n.targets)]
    assert any('reviewed_export' in ast.unparse(n.value) for n in assigns)


def test_long_history_defaults_on_only_with_verified_early_schedule_and_reuses_scope():
    tree = ast.parse(Path(__file__).with_name('site_ui.py').read_text(encoding='utf-8'))
    render = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_slate')
    calls = [n for n in ast.walk(render) if isinstance(n,ast.Call)]
    longer = next(n for n in calls if n.args and isinstance(n.args[0],ast.Constant)
                  and n.args[0].value=='Load a longer rotation window')
    assert any(k.arg=='value' and ast.unparse(k.value)=='history_early' for k in longer.keywords)
    guarded = [n for n in ast.walk(render) if isinstance(n,ast.If)
               and ast.unparse(n.test)=='history_early and (refresh or not retained_long)']
    assert len(guarded)==1
    assert sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
               and n.func.id=='extended_rotations' for n in ast.walk(guarded[0]))==1
    role_guard = [n for n in ast.walk(render) if isinstance(n,ast.If)
                  and ast.unparse(n.test)=='recover_roles and rotation_rows and role_early']
    assert len(role_guard)==1
    assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
               and n.func.id=='public_historical_roles' for n in ast.walk(role_guard[0]))
    assert any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='retained_long'
                   for t in n.targets) and 'research_scope' in ast.unparse(n.value)
               for n in ast.walk(render))

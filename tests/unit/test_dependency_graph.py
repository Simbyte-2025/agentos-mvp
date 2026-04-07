"""Tests for Subtask dependency graph and topological sort."""

from agentos.orchestrators.planner_executor import PlannerExecutorOrchestrator, Subtask


def _st(id: str, deps: list = None) -> Subtask:
    return Subtask(id=id, objetivo=f"task {id}", criterios_exito=[], dependencies=deps or [])


class TestBuildExecutionOrder:
    def test_no_dependencies(self):
        subtasks = [_st("a"), _st("b"), _st("c")]
        layers = PlannerExecutorOrchestrator._build_execution_order(subtasks)
        assert len(layers) == 1
        assert len(layers[0]) == 3

    def test_linear_chain(self):
        subtasks = [_st("a"), _st("b", ["a"]), _st("c", ["b"])]
        layers = PlannerExecutorOrchestrator._build_execution_order(subtasks)
        assert len(layers) == 3
        assert [layers[0][0].id, layers[1][0].id, layers[2][0].id] == ["a", "b", "c"]

    def test_diamond_dependencies(self):
        #   a
        #  / \
        # b   c
        #  \ /
        #   d
        subtasks = [_st("a"), _st("b", ["a"]), _st("c", ["a"]), _st("d", ["b", "c"])]
        layers = PlannerExecutorOrchestrator._build_execution_order(subtasks)
        assert len(layers) == 3
        assert layers[0][0].id == "a"
        layer1_ids = sorted(st.id for st in layers[1])
        assert layer1_ids == ["b", "c"]
        assert layers[2][0].id == "d"

    def test_circular_dependency_best_effort(self):
        subtasks = [_st("a", ["b"]), _st("b", ["a"])]
        layers = PlannerExecutorOrchestrator._build_execution_order(subtasks)
        # Should not crash — dumps circular deps into final layer
        assert len(layers) == 1
        assert len(layers[0]) == 2

    def test_dependency_on_unknown_id_treated_as_met(self):
        subtasks = [_st("a", ["nonexistent"]), _st("b")]
        layers = PlannerExecutorOrchestrator._build_execution_order(subtasks)
        # "nonexistent" not in subtask ids → treated as already met
        assert len(layers) == 1
        assert len(layers[0]) == 2

    def test_empty_list(self):
        assert PlannerExecutorOrchestrator._build_execution_order([]) == []

    def test_single_subtask(self):
        layers = PlannerExecutorOrchestrator._build_execution_order([_st("only")])
        assert len(layers) == 1
        assert layers[0][0].id == "only"

    def test_subtask_has_dependencies_field(self):
        st = Subtask(id="x", objetivo="test", criterios_exito=[], dependencies=["a", "b"])
        assert st.dependencies == ["a", "b"]

    def test_subtask_default_empty_dependencies(self):
        st = Subtask(id="x", objetivo="test", criterios_exito=[])
        assert st.dependencies == []

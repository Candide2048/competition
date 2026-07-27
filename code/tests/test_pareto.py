# -*- coding: utf-8 -*-
"""Pareto 非支配排序单元测试

覆盖：支配判定、快速非支配排序分层、rank 标注与支配关系列表、
None/缺失字段按最差值处理（payback None → inf 口径）。
"""
import os
import sys

import pytest

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from analytics.pareto import (  # noqa: E402
    assign_pareto_rank, dominates, non_dominated_sort,
)

OBJS = [("npv", "max"), ("payback", "min")]


class TestDominates:
    def test_strictly_better_on_all(self):
        a = {"npv": 100.0, "payback": 5.0}
        b = {"npv": 50.0, "payback": 8.0}
        assert dominates(a, b, OBJS)
        assert not dominates(b, a, OBJS)

    def test_better_on_one_equal_on_other(self):
        a = {"npv": 100.0, "payback": 5.0}
        b = {"npv": 100.0, "payback": 8.0}
        assert dominates(a, b, OBJS)
        assert not dominates(b, a, OBJS)

    def test_tradeoff_neither_dominates(self):
        a = {"npv": 100.0, "payback": 8.0}
        b = {"npv": 50.0, "payback": 5.0}
        assert not dominates(a, b, OBJS)
        assert not dominates(b, a, OBJS)

    def test_identical_no_domination(self):
        a = {"npv": 100.0, "payback": 5.0}
        assert not dominates(a, dict(a), OBJS)

    def test_none_treated_as_worst(self):
        # payback=None（不回本）应被有限回收期支配
        a = {"npv": 100.0, "payback": 5.0}
        b = {"npv": 100.0, "payback": None}
        assert dominates(a, b, OBJS)
        assert not dominates(b, a, OBJS)

    def test_missing_field_treated_as_worst(self):
        a = {"npv": 100.0, "payback": 5.0}
        b = {"npv": 100.0}
        assert dominates(a, b, OBJS)

    def test_empty_objectives_raises(self):
        with pytest.raises(ValueError):
            dominates({}, {}, [])


class TestNonDominatedSort:
    def test_layering(self):
        cands = [
            {"npv": 100.0, "payback": 5.0},   # 0: front
            {"npv": 50.0, "payback": 8.0},    # 1: dominated by 0 & 2
            {"npv": 80.0, "payback": 4.0},    # 2: front（回收期更短）
            {"npv": 40.0, "payback": 9.0},    # 3: dominated by all
        ]
        fronts = non_dominated_sort(cands, OBJS)
        assert fronts[0] == [0, 2]
        assert fronts[1] == [1]
        assert fronts[2] == [3]
        # 全体下标恰好出现一次
        flat = sorted(i for f in fronts for i in f)
        assert flat == list(range(len(cands)))

    def test_all_on_front_when_pure_tradeoff(self):
        # NPV 越高回收期越长 → 两两互不支配
        cands = [{"npv": float(100 - 10 * i), "payback": float(8 - i)}
                 for i in range(5)]
        fronts = non_dominated_sort(cands, OBJS)
        assert len(fronts) == 1
        assert sorted(fronts[0]) == list(range(5))

    def test_empty_input(self):
        assert non_dominated_sort([], OBJS) == []

    def test_single_candidate(self):
        assert non_dominated_sort([{"npv": 1.0, "payback": 1.0}], OBJS) == [[0]]


class TestAssignParetoRank:
    def test_rank_and_relations(self):
        cands = [
            {"id": "a", "npv": 100.0, "payback": 5.0},
            {"id": "b", "npv": 50.0, "payback": 8.0},
            {"id": "c", "npv": 80.0, "payback": 4.0},
        ]
        ranked = assign_pareto_rank(cands, OBJS)
        by_id = {c["id"]: c for c in ranked}
        assert by_id["a"]["pareto_rank"] == 0 and by_id["a"]["is_front"]
        assert by_id["c"]["pareto_rank"] == 0 and by_id["c"]["is_front"]
        assert by_id["b"]["pareto_rank"] == 1 and not by_id["b"]["is_front"]
        assert set(by_id["b"]["dominated_by"]) == {"a", "c"}
        assert by_id["b"]["dominates"] == []
        assert "b" in by_id["a"]["dominates"]

    def test_rank0_never_dominated(self):
        cands = [{"id": f"c{i}", "npv": float(i * 7 % 5), "payback": float(i % 3)}
                 for i in range(10)]
        ranked = assign_pareto_rank(cands, OBJS)
        for c in ranked:
            if c["pareto_rank"] == 0:
                assert c["dominated_by"] == []
            else:
                assert len(c["dominated_by"]) > 0

    def test_input_not_mutated(self):
        cands = [{"id": "a", "npv": 1.0, "payback": 1.0},
                 {"id": "b", "npv": 2.0, "payback": 0.5}]
        assign_pareto_rank(cands, OBJS)
        assert "pareto_rank" not in cands[0]
        assert "dominates" not in cands[1]

    def test_at_least_one_rank0(self):
        cands = [{"id": str(i), "npv": float(i), "payback": float(i)}
                 for i in range(4)]
        ranked = assign_pareto_rank(cands, OBJS)
        assert any(c["pareto_rank"] == 0 for c in ranked)

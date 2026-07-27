# -*- coding: utf-8 -*-
"""Pareto 决策前沿：NSGA-II 风格非支配排序

多目标同时最优通常不存在，Pareto 前沿给出"没有免费改进"的候选集合：
前沿上的每个候选，任何一个目标的改进都必然以牺牲另一目标为代价。

候选规模 N = 帆型 × 网格航速（≤ 3×5 = 15），快速非支配排序
O(M·N²) 完全够用，无需 NSGA-II 的拥挤距离/进化部分。

约定：
- objective = (字段名, "max" | "min")
- 字段缺失或为 None 按"最差"处理（max → -inf，min → +inf），
  与 /api/pareto 中 payback None → inf 的口径一致。
"""

from __future__ import annotations

from typing import Literal

Objective = tuple[str, Literal["max", "min"]]


def _value(cand: dict, field: str, direction: str) -> float:
    """取目标值；缺失/None 视为该方向的最差值"""
    v = cand.get(field)
    if v is None:
        return float("-inf") if direction == "max" else float("inf")
    return float(v)


def dominates(a: dict, b: dict, objectives: list[Objective]) -> bool:
    """a 支配 b：所有目标不劣于 b，且至少一个目标严格更优"""
    if not objectives:
        raise ValueError("objectives 不能为空")
    strictly_better = False
    for field, direction in objectives:
        va = _value(a, field, direction)
        vb = _value(b, field, direction)
        if direction == "max":
            if va < vb:
                return False
            if va > vb:
                strictly_better = True
        else:
            if va > vb:
                return False
            if va < vb:
                strictly_better = True
    return strictly_better


def non_dominated_sort(candidates: list[dict],
                       objectives: list[Objective]) -> list[list[int]]:
    """快速非支配排序（Deb 2002），返回各前沿的候选下标列表

    fronts[0] 为 Pareto 前沿（不被任何候选支配），fronts[k] 中的候选
    仅被前 k 层候选支配。所有下标恰好出现一次。
    """
    n = len(candidates)
    if n == 0:
        return []
    dominated_sets: list[list[int]] = [[] for _ in range(n)]
    domination_counts = [0] * n
    fronts: list[list[int]] = [[]]

    for p in range(n):
        for q in range(p + 1, n):
            if dominates(candidates[p], candidates[q], objectives):
                dominated_sets[p].append(q)
                domination_counts[q] += 1
            elif dominates(candidates[q], candidates[p], objectives):
                dominated_sets[q].append(p)
                domination_counts[p] += 1
    for p in range(n):
        if domination_counts[p] == 0:
            fronts[0].append(p)

    i = 0
    while fronts[i]:
        nxt: list[int] = []
        for p in fronts[i]:
            for q in dominated_sets[p]:
                domination_counts[q] -= 1
                if domination_counts[q] == 0:
                    nxt.append(q)
        i += 1
        fronts.append(nxt)
    fronts.pop()  # 最后一层为空
    return fronts


def assign_pareto_rank(candidates: list[dict],
                       objectives: list[Objective]) -> list[dict]:
    """标注 pareto_rank / is_front / dominates / dominated_by

    返回候选的浅拷贝列表（顺序不变）。dominates/dominated_by 使用候选的
    "id" 字段（缺失时退化为下标字符串），便于前端直接展示支配关系。
    """
    fronts = non_dominated_sort(candidates, objectives)
    ids = [str(c.get("id", i)) for i, c in enumerate(candidates)]
    out = [dict(c) for c in candidates]

    for rank, front in enumerate(fronts):
        for idx in front:
            out[idx]["pareto_rank"] = rank
            out[idx]["is_front"] = rank == 0

    for idx, cand in enumerate(out):
        dom = [ids[j] for j in range(len(out)) if j != idx
               and dominates(candidates[idx], candidates[j], objectives)]
        dom_by = [ids[j] for j in range(len(out)) if j != idx
                  and dominates(candidates[j], candidates[idx], objectives)]
        cand["dominates"] = dom
        cand["dominated_by"] = dom_by

    return out

# -*- coding: utf-8 -*-
"""风帆气动模型抽象基类

定义三种帆型（旋筒帆/刚性翼帆/吸力帆）的统一接口。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol


@dataclass
class SailConfig:
    """风帆通用配置"""
    sail_type: str  # 'flettner' | 'rigid_wingsail' | 'suction_sail'
    geometry: dict  # 几何参数（H, D, AR, S 等）


class SailBase(ABC):
    """风帆气动模型抽象基类

    所有帆型必须实现以下接口：
        - forces: 计算升力/阻力/推力/侧向力/功率
        - optimal_control: 在给定风况下求最优控制变量
    """

    @abstractmethod
    def forces(self, V_apparent: float, rho_air: float,
               beta: float, **kwargs) -> dict[str, float]:
        """计算风帆气动力

        Args:
            V_apparent: 相对风速 (m/s)
            rho_air: 空气密度 (kg/m³)
            beta: 相对风向角 (rad)，0 为顶风，π/2 为横风
            **kwargs: 帆型特定控制变量（如 Flettner 的 SR）

        Returns:
            dict 包含:
                - 'lift': 升力 (N)
                - 'drag': 阻力 (N)
                - 'thrust': 推力分量（沿船首方向）(N)
                - 'side_force': 侧向力 (N)
                - 'power_rotor': 转子驱动功耗（仅 Flettner）(W)
        """
        ...

    @abstractmethod
    def optimal_control(self, V_apparent: float, rho_air: float,
                        beta: float) -> dict:
        """在给定风况下求最优控制变量

        Returns:
            dict 包含最优控制变量及对应的力
        """
        ...

    @property
    @abstractmethod
    def projected_area(self) -> float:
        """投影面积 S (m²)"""
        ...

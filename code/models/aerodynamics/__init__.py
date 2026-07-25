# -*- coding: utf-8 -*-
"""aerodynamics 子模块：风帆气动模型

包含三种帆型的统一接口与实现：
    - flettner.py: 旋筒帆（⑤ Guzelbulut 2024 Kwon 回归）
    - rigid_wing.py: 刚性翼帆（Song 2025 风洞极曲线）
    - suction_sail.py: 吸力帆（参数化极曲线，锚定 bound4blue eSAIL）
"""
from .base import SailBase, SailConfig
from .flettner import FlettnerSail, FlettnerConfig
from .rigid_wing import RigidWingSail
from .suction_sail import SuctionSail

__all__ = [
    "SailBase", "SailConfig",
    "FlettnerSail", "FlettnerConfig",
    "RigidWingSail", "SuctionSail",
]

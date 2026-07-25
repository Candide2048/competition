# -*- coding: utf-8 -*-
"""船东输入参数 schema

将「成本 / 年运营小时 / 航速 / 油价 / 碳价 / 帆型规格」等不确定量抽象为
一组船东可填写的输入参数，对齐 Norsepower Simplified Performance Simulator
的评估思路（型号 / 航线 / 航速 / 海上作业时间比例）。系统据此做整体评估与
敏感性分析，而非写死单一假设。

默认值与取值范围来自 config/economics.yaml 的 owner_inputs 段。
单台成本（unit_cost_usd）若为 None，则回退到 config/sail_types.yaml 中
对应帆型（Flettner 还区分规格）的默认单价。

用法:
    inp = OwnerInputs.from_defaults()          # 全部取默认
    inp = OwnerInputs(sail_type="flettner", flettner_spec="30x5",
                      ship_speed_kn=13.0, sea_operating_ratio=0.74)
    inp.validate()
    hours = inp.annual_operating_hours()       # = ratio × 8765
    cost = inp.resolved_unit_cost_usd()        # 覆盖值或帆型/规格默认
"""
import os
from dataclasses import dataclass, field

import yaml


HOURS_PER_YEAR = 8765.0  # Norsepower simulator 口径（年小时数）

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config"
)
DEFAULT_ECON_CONFIG = os.path.join(CONFIG_DIR, "economics.yaml")
DEFAULT_SAIL_CONFIG = os.path.join(CONFIG_DIR, "sail_types.yaml")

VALID_SAIL_TYPES = ("flettner", "rigid_wing", "suction_wing")
VALID_FLETTNER_SPECS = ("20x4", "24x4", "28x4", "30x5", "35x5")
# 燃料类型 → CO₂ 排放因子 C_F 的键（权威值见 analytics/cii.py EMISSION_FACTORS）
VALID_FUEL_TYPES = ("VLSFO", "HFO", "MGO", "MDO", "LNG", "METHANOL")
# 船型键 → config/ship_*.yaml（几何/水动力参数见 core/ship_params.py）
VALID_SHIP_TYPES = ("kvlcc2", "kamsarmax", "mr_tanker", "container", "pctc")


def _load_owner_schema(econ_config: str = DEFAULT_ECON_CONFIG) -> dict:
    """从 economics.yaml 读取 owner_inputs schema（含 default/range）"""
    with open(econ_config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("owner_inputs", {})


@dataclass
class OwnerInputs:
    """船东输入参数

    Attributes:
        sail_type:            帆型 (flettner/rigid_wing/suction_wing)
        flettner_spec:        Norsepower 规格 (20x4..35x5)，仅 flettner 生效
        ship_type:            船型 (kvlcc2/kamsarmax/mr_tanker/container)，决定几何/水动力/CII 参考线
        ship_overrides:       实船参数覆盖 {DWT/L/B/draft/C_B: 值}（None=用代表船），
                              在选定 ship_type 基础上把代表船缩放到实船（上游筛选→近似实船）
        route:                航线走廊 key（对应 routes.yaml）
        route_weights:        多航线加权 {走廊 key: 权重}（None=单航线 route@100%）
        ship_speed_kn:        船舶航速 (kn)
        sea_operating_ratio:  海上作业时间比例 = 年航行小时数 / 8765
        fuel_type:            主要燃料类型（决定 CO₂ 排放因子 C_F）
        sfoc_g_per_kwh:       主机比油耗 (g/kWh，Norsepower 数据表标称 180)
        fuel_price_usd_per_kg:燃油价格 (USD/kg)
        co2_price_eur_per_t:  碳价 (EUR/tCO2)
        unit_cost_usd:        单台成本覆盖值 (None=用帆型/规格默认)
    """
    sail_type: str = "flettner"
    flettner_spec: str = "24x4"
    ship_type: str = "kvlcc2"
    ship_overrides: dict | None = None
    route: str = "middle_east_china"
    route_weights: dict | None = None
    ship_speed_kn: float = 14.0
    sea_operating_ratio: float = 0.742
    fuel_type: str = "VLSFO"
    sfoc_g_per_kwh: float = 180.0
    fuel_price_usd_per_kg: float = 0.6
    co2_price_eur_per_t: float = 74.0
    unit_cost_usd: float | None = None

    # ---------- 构造 ----------

    @classmethod
    def from_defaults(cls, econ_config: str = DEFAULT_ECON_CONFIG) -> "OwnerInputs":
        """用 economics.yaml owner_inputs 段的 default 值构造"""
        schema = _load_owner_schema(econ_config)

        def _d(key, fallback):
            return schema.get(key, {}).get("default", fallback)

        return cls(
            sail_type=_d("sail_type", "flettner"),
            flettner_spec=_d("flettner_spec", "24x4"),
            ship_type=_d("ship_type", "kvlcc2"),
            route=_d("route", "middle_east_china"),
            ship_speed_kn=_d("ship_speed_kn", 14.0),
            sea_operating_ratio=_d("sea_operating_ratio", 0.742),
            fuel_type=_d("fuel_type", "VLSFO"),
            sfoc_g_per_kwh=_d("sfoc_g_per_kwh", 180.0),
            fuel_price_usd_per_kg=_d("fuel_price_usd_per_kg", 0.6),
            co2_price_eur_per_t=_d("co2_price_eur_per_t", 74.0),
            unit_cost_usd=_d("unit_cost_usd", None),
        )

    # ---------- 校验 ----------

    def validate(self, econ_config: str = DEFAULT_ECON_CONFIG) -> None:
        """校验取值合法性，越界或非法枚举抛 ValueError"""
        if self.sail_type not in VALID_SAIL_TYPES:
            raise ValueError(
                f"sail_type={self.sail_type} 非法，应为 {VALID_SAIL_TYPES}")
        if self.sail_type == "flettner" and self.flettner_spec not in VALID_FLETTNER_SPECS:
            raise ValueError(
                f"flettner_spec={self.flettner_spec} 非法，应为 {VALID_FLETTNER_SPECS}")
        if self.ship_type not in VALID_SHIP_TYPES:
            raise ValueError(
                f"ship_type={self.ship_type} 非法，应为 {VALID_SHIP_TYPES}")
        self._validate_ship_overrides()
        if self.fuel_type not in VALID_FUEL_TYPES:
            raise ValueError(
                f"fuel_type={self.fuel_type} 非法，应为 {VALID_FUEL_TYPES}")
        if self.sfoc_g_per_kwh <= 0:
            raise ValueError("sfoc_g_per_kwh 应为正")
        if not (0.0 < self.sea_operating_ratio <= 1.0):
            raise ValueError(
                f"sea_operating_ratio={self.sea_operating_ratio} 应在 (0, 1]")
        if self.ship_speed_kn <= 0:
            raise ValueError(f"ship_speed_kn={self.ship_speed_kn} 应为正")
        if self.fuel_price_usd_per_kg <= 0:
            raise ValueError("fuel_price_usd_per_kg 应为正")
        if self.co2_price_eur_per_t < 0:
            raise ValueError("co2_price_eur_per_t 不应为负")
        if self.unit_cost_usd is not None and self.unit_cost_usd <= 0:
            raise ValueError("unit_cost_usd 若给定应为正")
        if self.route_weights is not None:
            if not self.route_weights:
                raise ValueError("route_weights 若给定不应为空")
            if any(w <= 0 for w in self.route_weights.values()):
                raise ValueError("route_weights 各航线权重应为正")
            total = sum(self.route_weights.values())
            if not (abs(total - 1.0) < 0.02 or abs(total - 100.0) < 2.0):
                self._warnings.append(
                    f"route_weights 之和={total:.3f} 非 1 也非 100，resolved_routes 将按比例归一化")

        # 软校验：范围外仅提示（不同船东/市场可能超出示例区间）
        schema = _load_owner_schema(econ_config)
        for key, value in [
            ("ship_speed_kn", self.ship_speed_kn),
            ("sea_operating_ratio", self.sea_operating_ratio),
            ("sfoc_g_per_kwh", self.sfoc_g_per_kwh),
            ("fuel_price_usd_per_kg", self.fuel_price_usd_per_kg),
            ("co2_price_eur_per_t", self.co2_price_eur_per_t),
        ]:
            rng = schema.get(key, {}).get("range")
            if rng and not (rng[0] <= value <= rng[1]):
                self._warnings.append(
                    f"{key}={value} 超出建议区间 {rng}（仍允许，结果外推需谨慎）")

    # ---------- 派生量 ----------

    def _validate_ship_overrides(self) -> None:
        """校验实船参数覆盖：键合法、值为正、C_B 在 (0,1)"""
        if self.ship_overrides is None:
            return
        from core.ship_params import OWNER_OVERRIDE_KEYS
        if not isinstance(self.ship_overrides, dict):
            raise ValueError("ship_overrides 若给定应为 dict")
        for key, value in self.ship_overrides.items():
            if key not in OWNER_OVERRIDE_KEYS:
                raise ValueError(
                    f"ship_overrides 含非法键 {key}，应为 {OWNER_OVERRIDE_KEYS} 子集")
            if value is None:
                continue
            if value <= 0:
                raise ValueError(f"ship_overrides[{key}]={value} 应为正")
            if key == "C_B" and not (0.0 < value < 1.0):
                raise ValueError(f"ship_overrides[C_B]={value} 应在 (0, 1)")

    def resolved_ship_overrides(self) -> dict | None:
        """返回非空覆盖项（值为 None 的键剔除）；无有效覆盖时返回 None"""
        if not self.ship_overrides:
            return None
        cleaned = {k: v for k, v in self.ship_overrides.items() if v is not None}
        return cleaned or None

    def annual_operating_hours(self) -> float:
        """年海上运营小时数 = 比例 × 8765"""
        return self.sea_operating_ratio * HOURS_PER_YEAR

    def resolved_emission_factor(self) -> float:
        """按燃料类型解析 CO₂ 排放因子 C_F (tCO2/tFuel)

        权威值来自 analytics/cii.py EMISSION_FACTORS（IMO G1 导则）。
        """
        from analytics.cii import EMISSION_FACTORS
        return float(EMISSION_FACTORS[self.fuel_type])

    def resolved_routes(self) -> list:
        """解析为 [(route_key, weight)] 列表，权重归一化到和为 1。

        route_weights=None 时回退为单航线 route @100%。
        """
        if not self.route_weights:
            return [(self.route, 1.0)]
        total = sum(self.route_weights.values())
        if total <= 0:
            raise ValueError("route_weights 之和必须为正")
        return [(k, v / total) for k, v in self.route_weights.items()]

    def resolved_unit_cost_usd(self, sail_config: str = DEFAULT_SAIL_CONFIG) -> float:
        """解析单台成本：覆盖值优先，否则取帆型/规格默认

        Flettner 若指定规格且规格含 unit_cost_usd，则用规格价；否则用帆型默认价。
        """
        if self.unit_cost_usd is not None:
            return float(self.unit_cost_usd)

        with open(sail_config, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        default_cost = float(cfg[self.sail_type]["cost"]["unit_cost_usd"])

        if self.sail_type == "flettner":
            specs = cfg["flettner"].get("specifications", {})
            spec = specs.get(self.flettner_spec, {})
            return float(spec.get("unit_cost_usd", default_cost))
        return default_cost

    def to_dict(self) -> dict:
        """导出为可序列化字典（含派生量）"""
        return {
            "sail_type": self.sail_type,
            "flettner_spec": self.flettner_spec if self.sail_type == "flettner" else None,
            "ship_type": self.ship_type,
            "ship_overrides": self.resolved_ship_overrides(),
            "route": self.route,
            "routes": self.resolved_routes(),
            "ship_speed_kn": self.ship_speed_kn,
            "sea_operating_ratio": self.sea_operating_ratio,
            "annual_operating_hours": self.annual_operating_hours(),
            "fuel_type": self.fuel_type,
            "emission_factor": self.resolved_emission_factor(),
            "sfoc_g_per_kwh": self.sfoc_g_per_kwh,
            "fuel_price_usd_per_kg": self.fuel_price_usd_per_kg,
            "co2_price_eur_per_t": self.co2_price_eur_per_t,
            "unit_cost_usd": self.resolved_unit_cost_usd(),
            "warnings": list(self._warnings),
        }

    # 内部：软校验告警收集
    _warnings: list = field(default_factory=list, repr=False)

# -*- coding: utf-8 -*-
"""船型参数加载器

从 config/ship_kvlcc2.yaml 加载 KVLCC2 船型参数，
提供统一的 dataclass 接口供其他模块使用。

也提供阻力模型所需的 HoltropMennenInput 加载入口（与 models/resistance 互操作）。
"""
import os
from dataclasses import dataclass
from typing import Any

import yaml


DEFAULT_SHIP_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "ship_kvlcc2.yaml"
)

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config"
)

# 船型键 → 配置文件名（与 core/owner_inputs.py VALID_SHIP_TYPES 对齐）
SHIP_TYPE_CONFIGS = {
    "kvlcc2": "ship_kvlcc2.yaml",       # VLCC 原油轮 300000 DWT
    "kamsarmax": "ship_kamsarmax.yaml",  # 散货船 82000 DWT
    "mr_tanker": "ship_mr_tanker.yaml",  # 成品油轮 50000 DWT
    "container": "ship_container.yaml",  # 集装箱船 KCS/Panamax 40000 DWT
    "pctc": "ship_pctc.yaml",            # PCTC 汽车滚装船 ~62000 GT / 18000 DWT
}


@dataclass
class ShipParams:
    """船型综合参数（含主尺度、水动力、运营、风阻、海水属性）

    此 dataclass 是 ship_kvlcc2.yaml 的内存映射，
    供 analytics/ 与 pipelines/ 使用。
    """
    # 主尺度
    L: float
    B: float
    T: float
    V_disp: float
    C_B: float
    D_prop: float  # 螺旋桨直径
    S_rudder: float
    x_G: float

    # 水动力系数
    C_M: float
    C_P: float
    C_WP: float
    lcb: float

    # 球鼻艏与尾型
    A_BT: float
    h_B: float
    C_stern: float

    # 附体
    S_app: float
    k2_eq: float

    # 运营
    DWT: float
    V_design_kn: float
    V_design_ms: float
    ship_type_imo: str

    # 风阻
    A_T: float  # 横剖面受风面积
    A_L: float  # 侧向受风面积
    C_X_head: float
    C_X_cross: float
    C_X_tail: float

    # 海水
    rho_sw: float
    nu_sw: float

    # 可选：总吨（仅部分船型提供；CII 用 GT 基数的船型需要，如 PCTC/roro）
    GT: float | None = None

    @property
    def operational_speed_ms(self) -> float:
        """运营船速 (m/s)"""
        return self.V_design_ms


def load_ship_params(config_path: str | None = None) -> ShipParams:
    """从 YAML 加载船型参数

    Args:
        config_path: 配置文件路径，默认 config/ship_kvlcc2.yaml

    Returns:
        ShipParams 实例
    """
    if config_path is None:
        config_path = DEFAULT_SHIP_CONFIG

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    pd_ = cfg["principal_dimensions"]
    hc = cfg["hydrostatic_coefficients"]
    bs = cfg["bow_and_stern"]
    ap = cfg["appendages"]
    op = cfg["operational"]
    wr = cfg["wind_resistance"]
    sw = cfg["seawater"]

    return ShipParams(
        L=pd_["L"],
        B=pd_["B"],
        T=pd_["d"],
        V_disp=pd_["V_disp"],
        C_B=pd_["C_B"],
        D_prop=pd_["D"],
        S_rudder=pd_["S_rudder"],
        x_G=pd_["x_G"],
        C_M=hc["C_M"],
        C_P=hc["C_P"],
        C_WP=hc["C_WP"],
        lcb=hc["lcb"],
        A_BT=bs["A_BT"],
        h_B=bs["h_B"],
        C_stern=bs["C_stern"],
        S_app=ap["S_app"],
        k2_eq=ap.get("k2_eq", 1.3),
        DWT=op["DWT"],
        V_design_kn=op["V_design_kn"],
        V_design_ms=op["V_design_ms"],
        ship_type_imo=op["ship_type_imo"],
        GT=op.get("GT"),
        A_T=wr["A_T"],
        A_L=wr["A_L"],
        C_X_head=wr["C_X_head"],
        C_X_cross=wr["C_X_cross"],
        C_X_tail=wr["C_X_tail"],
        rho_sw=sw["rho_sw"],
        nu_sw=sw["nu_sw"],
    )


def load_ship_params_by_type(ship_type: str = "kvlcc2") -> ShipParams:
    """按船型键加载船型参数

    Args:
        ship_type: 船型键，SHIP_TYPE_CONFIGS 的 key
            ("kvlcc2"/"kamsarmax"/"mr_tanker"/"container")

    Returns:
        ShipParams 实例

    Raises:
        ValueError: ship_type 非法
    """
    if ship_type not in SHIP_TYPE_CONFIGS:
        raise ValueError(
            f"ship_type={ship_type} 非法，应为 {tuple(SHIP_TYPE_CONFIGS)}")
    config_path = os.path.join(_CONFIG_DIR, SHIP_TYPE_CONFIGS[ship_type])
    return load_ship_params(config_path)


# 船东可覆盖的实船参数键（交船资料/船级证书即可获得）
OWNER_OVERRIDE_KEYS = ("DWT", "L", "B", "draft", "C_B")


def apply_geometry_overrides(ship: ShipParams, overrides: dict) -> ShipParams:
    """在代表船基础上应用船东实船参数覆盖，返回自洽的新 ShipParams。

    可覆盖键见 OWNER_OVERRIDE_KEYS：DWT / L / B / draft(吃水) / C_B。
    仅当主尺度真正被覆盖时才重算派生量，以免污染代表船的权威系数：
        V_disp = L·B·T·C_B          （方形系数定义；任一主尺度变动即重算）
        C_P    = C_B / C_M           （仅 C_B 被覆盖时重算，C_M 沿用代表船）
        C_WP   = (1 + 2·C_B) / 3      （经验式，与船型 YAML 注释口径一致）
    其余水动力系数(C_M/lcb/A_BT/…)、附体、螺旋桨、风阻、海水、CII 船型(imo)
    均沿用代表船。航速不在此覆盖，由 OwnerInputs.ship_speed_kn 独立驱动。

    Args:
        ship: 代表船 ShipParams
        overrides: 覆盖字典，键为 OWNER_OVERRIDE_KEYS 子集，值为正数或 None

    Returns:
        应用覆盖后的新 ShipParams（原实例不变）
    """
    import dataclasses

    def _ov(key, default):
        v = overrides.get(key)
        return float(v) if v is not None else default

    L = _ov("L", ship.L)
    B = _ov("B", ship.B)
    T = _ov("draft", ship.T)
    C_B = _ov("C_B", ship.C_B)
    DWT = _ov("DWT", ship.DWT)

    new_fields: dict[str, Any] = {"L": L, "B": B, "T": T, "C_B": C_B, "DWT": DWT}
    # 任一主尺度被覆盖 → 按定义重算排水体积
    if any(overrides.get(k) is not None for k in ("L", "B", "draft", "C_B")):
        new_fields["V_disp"] = L * B * T * C_B
    # 仅 C_B 被覆盖 → 重算依赖 C_B 的形状系数（否则保留代表船权威值）
    if overrides.get("C_B") is not None:
        new_fields["C_P"] = C_B / ship.C_M
        new_fields["C_WP"] = (1.0 + 2.0 * C_B) / 3.0
    return dataclasses.replace(ship, **new_fields)


def to_holtrop_input(ship: ShipParams):
    """从 ShipParams 转换为 HoltropMennenInput

    Returns:
        HoltropMennenInput 实例（延迟导入避免循环依赖）
    """
    from models.resistance import HoltropMennenInput
    return HoltropMennenInput(
        L=ship.L,
        B=ship.B,
        T=ship.T,
        V_disp=ship.V_disp,
        C_B=ship.C_B,
        C_M=ship.C_M,
        C_P=ship.C_P,
        C_WP=ship.C_WP,
        lcb=ship.lcb,
        A_BT=ship.A_BT,
        h_B=ship.h_B,
        C_stern=ship.C_stern,
        S_app=ship.S_app,
        k2_eq=ship.k2_eq,
        rho_sw=ship.rho_sw,
        nu_sw=ship.nu_sw,
    )

"""BaZi Engine — 八字計算封裝層（純 Python + lunardate）

提供八字排盤、五行分析、十神、地支關係。
不依賴 tianji，使用傳統天干地支公式計算。
"""

from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional
import json

from lunardate import LunarDate

TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
SHENG_XIAO = ["鼠", "牛", "虎", "兔", "龍", "蛇", "馬", "羊", "猴", "雞", "狗", "豬"]

GAN_ELEMENT = ["木", "木", "火", "火", "土", "土", "金", "金", "水", "水"]
GAN_POLARITY = ["陽", "陰", "陽", "陰", "陽", "陰", "陽", "陰", "陽", "陰"]
ZHI_ELEMENT = ["水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水"]

ELEMENT_WEIGHTS = {"木": 1.0, "火": 1.0, "土": 1.0, "金": 1.0, "水": 1.0}

ELEMENT_CN = {"木": "木", "火": "火", "土": "土", "金": "金", "水": "水"}

DAY_MASTER_TRAITS = {
    "甲": {"name": "甲木", "element": "木", "polarity": "陽", "traits": ["正直", "有擔當", "領導力強", "固執", "不善變通"]},
    "乙": {"name": "乙木", "element": "木", "polarity": "陰", "traits": ["溫和", "有彈性", "善於溝通", "優柔寡斷", "依賴性強"]},
    "丙": {"name": "丙火", "element": "火", "polarity": "陽", "traits": ["熱情", "開朗", "樂觀", "衝動", "缺乏耐心"]},
    "丁": {"name": "丁火", "element": "火", "polarity": "陰", "traits": ["細膩", "敏感", "有洞察力", "多愁善感", "容易焦慮"]},
    "戊": {"name": "戊土", "element": "土", "polarity": "陽", "traits": ["穩重", "誠信", "包容力強", "保守", "反應慢"]},
    "己": {"name": "己土", "element": "土", "polarity": "陰", "traits": ["隨和", "體貼", "善解人意", "優柔寡斷", "容易受影響"]},
    "庚": {"name": "庚金", "element": "金", "polarity": "陽", "traits": ["果斷", "有義氣", "執行力強", "好勝心強", "容易得罪人"]},
    "辛": {"name": "辛金", "element": "金", "polarity": "陰", "traits": ["聰明", "有品味", "追求完美", "挑剔", "容易鑽牛角尖"]},
    "壬": {"name": "壬水", "element": "水", "polarity": "陽", "traits": ["聰明", "有智慧", "適應力強", "不穩定", "容易分心"]},
    "癸": {"name": "癸水", "element": "水", "polarity": "陰", "traits": ["敏感", "有想像力", "直覺力強", "被動", "容易受傷"]},
}

ELEMENT_GENERATE = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
ELEMENT_OVERCOME = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


@dataclass
class BaziResult:
    birth_datetime: str
    gender: str
    pillars: dict
    day_master: dict
    five_elements: dict
    ten_gods: list
    relationships: list
    strength_analysis: dict

    def to_dict(self) -> dict:
        return {
            "birth_datetime": self.birth_datetime,
            "gender": self.gender,
            "pillars": self.pillars,
            "day_master": self.day_master,
            "five_elements": self.five_elements,
            "ten_gods": self.ten_gods,
            "relationships": self.relationships,
            "strength_analysis": self.strength_analysis,
        }


def _heavenly_stem(year: int) -> int:
    return (year - 4) % 10


def _earthly_branch(year: int) -> int:
    return (year - 4) % 12


def _month_pillar(year: int, month: int, day: int) -> tuple[int, int]:
    """月柱：年上起月法"""
    stem_offset = (_heavenly_stem(year) % 5) * 2
    month_stem_base = (stem_offset + 2) % 10
    month_stem = (month_stem_base + month - 1) % 10

    month_branch_base = 2  # 寅月起
    month_branch = (month_branch_base + month - 1) % 12
    return month_stem, month_branch


def _day_stem_branch(year: int, month: int, day: int) -> tuple[int, int]:
    """日柱：基於儒略日的天干地支計算"""
    d = date(year, month, day)
    jd = d.toordinal() + 1721139
    day_stem = jd % 10
    day_branch = jd % 12
    return day_stem, day_branch


def _hour_pillar(day_stem: int, hour: int) -> tuple[int, int]:
    """時柱：日上起時法"""
    hour_branch = ((hour + 1) // 2) % 12
    hour_stem_base = (day_stem % 5) * 2
    hour_stem = (hour_stem_base + hour_branch) % 10
    return hour_stem, hour_branch


def _ten_god(day_stem_idx: int, other_stem_idx: int) -> str:
    """計算十神關係"""
    day_element_idx = day_stem_idx // 2
    day_polarity = day_stem_idx % 2
    other_element_idx = other_stem_idx // 2
    other_polarity = other_stem_idx % 2

    if day_element_idx == other_element_idx:
        return "比肩" if day_polarity == other_polarity else "劫財"

    generate_order = [4, 0, 1, 2, 3]  # 木火土金水
    day_elem = day_element_idx
    other_elem = other_element_idx

    if generate_order[(other_elem + 1) % 5] == day_elem:
        if day_polarity == other_polarity:
            return "食神"
        else:
            return "傷官"
    if generate_order[(day_elem + 1) % 5] == other_elem:
        if day_polarity == other_polarity:
            return "偏印"
        else:
            return "正印"
    if generate_order[(other_elem + 2) % 5] == day_elem:
        if day_polarity == other_polarity:
            return "七殺"
        else:
            return "正官"
    if generate_order[(day_elem + 2) % 5] == other_elem:
        if day_polarity == other_polarity:
            return "偏財"
        else:
            return "正財"

    return "比肩"


def _calculate_five_elements(stems: list[int], branches: list[int]) -> dict:
    """計算五行分佈"""
    counts = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for s in stems:
        elem = GAN_ELEMENT[s]
        counts[elem] += 1.0
    for b in branches:
        elem = ZHI_ELEMENT[b]
        counts[elem] += 0.6

    total = sum(counts.values())
    scores = {k: round(v / total * 100, 1) if total > 0 else 0 for k, v in counts.items()}
    return {
        "scores": scores,
        "counts": counts,
        "total": round(total, 1),
    }


def _earthly_branches_relation(b1: int, b2: int) -> list[str]:
    """地支關係"""
    liuhe = {(0, 4): "子丑合土", (1, 11): "寅亥合木", (2, 9): "卯戌合火", (3, 8): "辰酉合金", (4, 7): "巳申合水", (5, 6): "午未合火"}
    liuchong = {(0, 6): "子午沖", (1, 7): "丑未沖", (2, 8): "寅申沖", (3, 9): "卯酉沖", (4, 10): "辰戌沖", (5, 11): "巳亥沖"}

    results = []
    pair = (min(b1, b2), max(b1, b2))
    if pair in liuhe:
        results.append(liuhe[pair])
    if b1 != b2 and abs(b1 - b2) == 6:
        key = (min(b1, b2), max(b1, b2))
        if key in liuchong:
            results.append(liuchong[key])
    return results


def calculate_bazi(
    birth_datetime: str,
    gender: str,
    birthplace: Optional[str] = None,
) -> BaziResult:
    dt = datetime.fromisoformat(birth_datetime)

    year_stem_idx = _heavenly_stem(dt.year)
    year_branch_idx = _earthly_branch(dt.year)
    month_stem_idx, month_branch_idx = _month_pillar(dt.year, dt.month, dt.day)
    day_stem_idx, day_branch_idx = _day_stem_branch(dt.year, dt.month, dt.day)
    hour_stem_idx, hour_branch_idx = _hour_pillar(day_stem_idx, dt.hour)

    pillars = {
        "year": f"{TIAN_GAN[year_stem_idx]}{DI_ZHI[year_branch_idx]}",
        "month": f"{TIAN_GAN[month_stem_idx]}{DI_ZHI[month_branch_idx]}",
        "day": f"{TIAN_GAN[day_stem_idx]}{DI_ZHI[day_branch_idx]}",
        "hour": f"{TIAN_GAN[hour_stem_idx]}{DI_ZHI[hour_branch_idx]}",
        "year_element": GAN_ELEMENT[year_stem_idx],
        "month_element": GAN_ELEMENT[month_stem_idx],
        "day_element": GAN_ELEMENT[day_stem_idx],
        "hour_element": GAN_ELEMENT[hour_stem_idx],
        "sheng_xiao": SHENG_XIAO[year_branch_idx],
    }

    dm_stem = TIAN_GAN[day_stem_idx]
    dm_info = DAY_MASTER_TRAITS.get(dm_stem, {"name": dm_stem, "element": GAN_ELEMENT[day_stem_idx], "polarity": GAN_POLARITY[day_stem_idx], "traits": []})
    day_master = {
        "stem": dm_stem,
        "element": GAN_ELEMENT[day_stem_idx],
        "polarity": GAN_POLARITY[day_stem_idx],
        "name": dm_info["name"],
        "traits": dm_info["traits"],
    }

    all_stems = [year_stem_idx, month_stem_idx, day_stem_idx, hour_stem_idx]
    all_branches = [year_branch_idx, month_branch_idx, day_branch_idx, hour_branch_idx]

    five_elements = _calculate_five_elements(all_stems, all_branches)

    position_names = ["年干", "月干", "日干", "時干"]
    ten_gods = []
    for i, pos in enumerate(position_names):
        if i == 2:
            continue
        god = _ten_god(day_stem_idx, all_stems[i])
        ten_gods.append({
            "position": pos,
            "stem": TIAN_GAN[all_stems[i]],
            "ten_god": god,
        })

    position_branch_names = ["年支", "月支", "日支", "時支"]
    for i, pos in enumerate(position_branch_names):
        hidden_stems = _hidden_stems(all_branches[i])
        for hs_idx in hidden_stems:
            god = _ten_god(day_stem_idx, hs_idx)
            ten_gods.append({
                "position": pos,
                "stem": TIAN_GAN[hs_idx],
                "ten_god": f"{god}（藏干）",
            })

    relationships = []
    branch_names = ["年支", "月支", "日支", "時支"]
    for i in range(4):
        for j in range(i + 1, 4):
            rels = _earthly_branches_relation(all_branches[i], all_branches[j])
            if rels:
                for r in rels:
                    relationships.append({
                        "kind": r,
                        "branches": f"{branch_names[i]}{DI_ZHI[all_branches[i]]} - {branch_names[j]}{DI_ZHI[all_branches[j]]}",
                        "description": r,
                    })

    dm_element = GAN_ELEMENT[day_stem_idx]
    scores = five_elements["scores"]
    help_element = ELEMENT_GENERATE.get("水", "木")
    for k, v in ELEMENT_GENERATE.items():
        if v == dm_element:
            help_element = k
            break
    drain_element = ELEMENT_GENERATE.get(dm_element, "火")

    help_score = scores.get(dm_element, 0) + scores.get(help_element, 0)
    drain_score = scores.get(drain_element, 0)
    for k, v in ELEMENT_OVERCOME.items():
        if v == dm_element:
            drain_score += scores.get(k, 0)

    strength_analysis = {
        "day_master_element": dm_element,
        "help_elements": [dm_element, help_element],
        "drain_elements": [drain_element],
        "is_strong": help_score > drain_score,
        "help_score": round(help_score, 1),
        "drain_score": round(drain_score, 1),
    }

    return BaziResult(
        birth_datetime=birth_datetime,
        gender=gender,
        pillars=pillars,
        day_master=day_master,
        five_elements=five_elements,
        ten_gods=ten_gods,
        relationships=relationships,
        strength_analysis=strength_analysis,
    )


def _hidden_stems(branch_idx: int) -> list[int]:
    """地支藏干"""
    hidden = {
        0: [8],      # 子 → 壬
        1: [5, 8, 7],  # 丑 → 己癸辛
        2: [0, 2, 4],  # 寅 → 甲丙戊
        3: [1],      # 卯 → 乙
        4: [4, 1, 8],  # 辰 → 戊乙癸
        5: [2, 4, 6],  # 巳 → 丙戊庚
        6: [3, 5],   # 午 → 丁己
        7: [5, 3, 1],  # 未 → 己丁乙
        8: [6, 4, 8],  # 申 → 庚戊壬
        9: [7],      # 酉 → 辛
        10: [4, 7, 3], # 戌 → 戊辛丁
        11: [8, 2],  # 亥 → 壬甲
    }
    return hidden.get(branch_idx, [])

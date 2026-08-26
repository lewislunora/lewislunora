"""BaZi Engine — 八字計算封裝層

整合 tianji 庫，提供八字排盤、五行分析、十神、地支關係。
用於 AI 理想型配對系統。
"""

from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import json

from tianji.bazi import BaZiChart, ten_gods_from_chart
from tianji.bazi.five_elements import elements_from_chart, Element
from tianji.bazi.relationships import relationships_from_chart


# 五行中文對照
ELEMENT_CN = {
    "WOOD": "木", "FIRE": "火", "EARTH": "土", "METAL": "金", "WATER": "水"
}

# 十神中文
TEN_GOD_CN = {
    "Companion (Parallel Shoulder)": "比肩",
    "Rob Wealth (Sibling)": "劫財",
    "Eating God": "食神",
    "Hurting Officer": "傷官",
    "Indirect Wealth": "偏財",
    "Direct Wealth": "正財",
    "Seven Killings": "七殺",
    "Direct Officer": "正官",
    "Indirect Resource": "偏印",
    "Direct Resource": "正印",
}

# 天干五行對照
STEM_ELEMENT = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

# 地支五行對照
BRANCH_ELEMENT = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

# 日主性格特質
DAY_MASTER_TRAITS = {
    "甲": {"name": "甲木", "element": "木", "traits": ["正直", "有擔當", "領導力強", "固執", "不善變通"]},
    "乙": {"name": "乙木", "element": "木", "traits": ["溫和", "有彈性", "善於溝通", "優柔寡斷", "依賴性強"]},
    "丙": {"name": "丙火", "element": "火", "traits": ["熱情", "開朗", "樂觀", "衝動", "缺乏耐心"]},
    "丁": {"name": "丁火", "element": "火", "traits": ["細膩", "敏感", "有洞察力", "多愁善感", "容易焦慮"]},
    "戊": {"name": "戊土", "element": "土", "traits": ["穩重", "誠信", "包容力強", "保守", "反應慢"]},
    "己": {"name": "己土", "element": "土", "traits": ["隨和", "體貼", "善解人意", "優柔寡斷", "容易受影響"]},
    "庚": {"name": "庚金", "element": "金", "traits": ["果斷", "有義氣", "執行力強", "好勝心強", "容易得罪人"]},
    "辛": {"name": "辛金", "element": "金", "traits": ["聰明", "有品味", "追求完美", "挑剔", "容易鑽牛角尖"]},
    "壬": {"name": "壬水", "element": "水", "traits": ["聰明", "有智慧", "適應力強", "不穩定", "容易分心"]},
    "癸": {"name": "癸水", "element": "水", "traits": ["敏感", "有想像力", "直覺力強", "被動", "容易受傷"]},
}

# 五行相生相剋
ELEMENT_GENERATE = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
ELEMENT_OVERCOME = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


@dataclass
class BaziResult:
    """八字計算結果"""
    birth_datetime: str
    gender: str
    pillars: dict
    day_master: dict
    five_elements: dict
    ten_gods: list
    relationships: list
    strength_analysis: dict
    chart_dict: dict

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


def calculate_bazi(
    birth_datetime: str,
    gender: str,
    birthplace: Optional[str] = None,
) -> BaziResult:
    """計算八字
    
    Args:
        birth_datetime: 出生時間 ISO 格式 "1990-05-15T14:30:00"
        gender: "male" 或 "female"
        birthplace: 出生地（未來用於真太陽時校正）
    
    Returns:
        BaziResult 包含完整八字分析
    """
    dt = datetime.fromisoformat(birth_datetime)
    chart = BaZiChart(birth_dt=dt, gender=gender)
    
    # 四柱
    pillars = {
        "year": str(chart.year_pillar),
        "month": str(chart.month_pillar),
        "day": str(chart.day_pillar),
        "hour": str(chart.hour_pillar),
        "year_element": chart.year_pillar.stem.element.value,
        "month_element": chart.month_pillar.stem.element.value,
        "day_element": chart.day_pillar.stem.element.value,
        "hour_element": chart.hour_pillar.stem.element.value,
    }
    
    # 日主
    day_master_stem = chart.day_master.char
    day_master_info = DAY_MASTER_TRAITS.get(day_master_stem, {})
    day_master = {
        "stem": day_master_stem,
        "element": chart.day_master.element.value,
        "polarity": chart.day_master.polarity,
        "name": day_master_info.get("name", day_master_stem),
        "traits": day_master_info.get("traits", []),
    }
    
    # 五行分析
    five_analysis = elements_from_chart(chart)
    five_elements = {
        "scores": {ELEMENT_CN[k.name]: v for k, v in five_analysis.weighted_scores.items()},
        "stem_counts": {ELEMENT_CN[k.name]: v for k, v in five_analysis.stem_counts.items()},
        "branch_counts": {ELEMENT_CN[k.name]: v for k, v in five_analysis.branch_counts.items()},
    }
    
    # 十神
    gods = ten_gods_from_chart(chart)
    ten_gods = []
    for pos, result in gods.items():
        god_cn = TEN_GOD_CN.get(result.ten_god, result.ten_god)
        ten_gods.append({
            "position": pos,
            "stem": result.stem.char,
            "ten_god": god_cn,
            "english": result.english,
        })
    
    # 地支關係
    rel_analysis = relationships_from_chart(chart)
    relationships = []
    for rel in rel_analysis.relationships:
        relationships.append({
            "kind": rel.kind,
            "branches": rel.branches,
            "description": rel.description,
        })
    
    # 日主強弱分析（簡化版）
    dm_element = chart.day_master.element.value
    scores = five_analysis.weighted_scores
    
    # 找出生助日主的元素（同 element + 生我的 element）
    help_elements = [dm_element]
    for k, v in ELEMENT_GENERATE.items():
        if v == dm_element:
            help_elements.append(k)
            break
    
    # 找出剋洩日主的元素
    drain_elements = []
    for k, v in ELEMENT_OVERCOME.items():
        if v == dm_element:
            drain_elements.append(k)
            break
    for k, v in ELEMENT_GENERATE.items():
        if k == dm_element:
            drain_elements.append(v)
            break
    
    # 計算分數
    help_score = sum(
        scores.get(e, 0) for e in Element
        if ELEMENT_CN.get(e.name) in help_elements
    )
    drain_score = sum(
        scores.get(e, 0) for e in Element
        if ELEMENT_CN.get(e.name) in drain_elements
    )
    
    strength_analysis = {
        "day_master_element": dm_element,
        "help_elements": help_elements,
        "drain_elements": drain_elements,
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
        chart_dict=chart.to_dict(),
    )

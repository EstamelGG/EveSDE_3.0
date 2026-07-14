#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建流水线：分阶段、顺序与现有 BUILD_PIPELINE 完全一致（仅编排，不改业务）。"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import evesde.processors.icon_builder_processor as icon_builder_processor
import evesde.processors.icon_fetcher as icon_fetcher
import evesde.processors.dynamic_items_updater as dynamic_items_updater
import evesde.processors.universe_processor as universe_processor
import evesde.processors.universe_names_processor as universe_names_processor
import evesde.processors.dogma_effects_processor as dogma_effects_processor
import evesde.processors.planet_schematics_processor as planet_schematics_processor
import evesde.processors.categories_processor as categories_processor
import evesde.processors.groups_processor as groups_processor
import evesde.processors.metagroups_processor as metagroups_processor
import evesde.processors.stations_processor as stations_processor
import evesde.processors.factions_processor as factions_processor
import evesde.processors.npcCorporations_processor as npcCorporations_processor
import evesde.processors.loyalty_stores_processor as loyalty_stores_processor
import evesde.processors.agents_processor as agents_processor
import evesde.processors.divisions_processor as divisions_processor
import evesde.processors.dogmaAttributeCategories_processor as dogmaAttributeCategories_processor
import evesde.processors.dogmaAttributes_processor as dogmaAttributes_processor
import evesde.processors.typeDogma_processor as typeDogma_processor
import evesde.processors.types_processor as types_processor
import evesde.processors.npc_ship_classifier as npc_ship_classifier
import evesde.processors.dbuffCollections_processor as dbuffCollections_processor
import evesde.processors.marketGroups_processor as marketGroups_processor
import evesde.processors.typeMaterials_processor as typeMaterials_processor
import evesde.processors.blueprints_processor as blueprints_processor
import evesde.processors.celestial_names_processor as celestial_names_processor
import evesde.processors.skill_requirements_processor as skill_requirements_processor
import evesde.processors.facility_rig_effects_processor as facility_rig_effects_processor
import evesde.processors.compressable_types_processor as compressable_types_processor
import evesde.processors.typeTraits_processor as typeTraits_processor
import evesde.processors.ore_color_processor as ore_color_processor
import evesde.processors.map_generator as map_generator
import evesde.processors.database_normalizer as database_normalizer

StepFn = Callable[[Dict[str, Any]], Any]
# (stage, name, fn)
PipelineStep = Tuple[str, str, StepFn]

# 阶段仅作文档/日志分组；顺序严禁改动
PIPELINE_STEPS: List[PipelineStep] = [
    # icons
    ("icons", "图标构造", icon_builder_processor.main),
    ("icons", "图标获取", icon_fetcher.main),
    ("icons", "动态物品数据", dynamic_items_updater.main),
    # dimensions
    ("dimensions", "宇宙数据", universe_processor.main),
    ("dimensions", "宇宙名称", universe_names_processor.main),
    ("dimensions", "Dogma效果数据", dogma_effects_processor.main),
    ("dimensions", "行星制造数据", planet_schematics_processor.main),
    ("dimensions", "物品分类数据", categories_processor.main),
    ("dimensions", "物品组数据", groups_processor.main),
    ("dimensions", "物品衍生组数据", metagroups_processor.main),
    ("dimensions", "空间站数据", stations_processor.main),
    ("dimensions", "派系数据", factions_processor.main),
    ("dimensions", "NPC公司数据", npcCorporations_processor.main),
    ("dimensions", "LP商店数据", loyalty_stores_processor.main),
    ("dimensions", "代理人数据", agents_processor.main),
    ("dimensions", "NPC公司部门数据", divisions_processor.main),
    ("dimensions", "物品属性目录数据", dogmaAttributeCategories_processor.main),
    ("dimensions", "物品属性数据", dogmaAttributes_processor.main),
    ("dimensions", "物品属性详情数据", typeDogma_processor.main),
    # core
    ("core", "物品详情数据", types_processor.main),
    ("core", "分组图标回填", groups_processor.backfill_group_icons),
    # enrich
    ("enrich", "NPC船只分类数据", npc_ship_classifier.main),
    ("enrich", "矿石主题色数据", ore_color_processor.main),
    ("enrich", "dbuff集合数据", dbuffCollections_processor.main),
    ("enrich", "市场分组数据", marketGroups_processor.main),
    ("enrich", "物品材料产出数据", typeMaterials_processor.main),
    ("enrich", "蓝图数据", blueprints_processor.main),
    ("enrich", "天体数据", celestial_names_processor.main),
    ("enrich", "技能需求数据", skill_requirements_processor.main),
    ("enrich", "设施装配效果数据", facility_rig_effects_processor.main),
    ("enrich", "可压缩物品数据", compressable_types_processor.main),
    ("enrich", "类型特性数据", typeTraits_processor.main),
    # maps_pack
    ("maps_pack", "地图生成", map_generator.main),
    ("maps_pack", "数据库标准化", database_normalizer.main),
]


def iter_pipeline() -> Iterator[PipelineStep]:
    yield from PIPELINE_STEPS


def run_pipeline(
    config: Dict[str, Any],
    on_step: Optional[Callable[[str, str, StepFn], None]] = None,
) -> None:
    """按固定顺序执行流水线。on_step(stage, name, fn) 默认打印并调用 fn(config)。"""
    current_stage = None
    for stage, name, fn in PIPELINE_STEPS:
        if stage != current_stage:
            current_stage = stage
            print(f"\n[+] === 阶段: {stage} ===")
        if on_step is not None:
            on_step(stage, name, fn)
        else:
            print(f"\n[+] 开始处理{name}")
            result = fn(config)
            if result is not None and not result:
                raise RuntimeError(f"{name}处理失败")
            print(f"[+] {name}处理完成")

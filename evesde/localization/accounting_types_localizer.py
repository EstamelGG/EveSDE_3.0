#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""从官方 SDE accountingEntryTypes.jsonl 生成会计条目本地化 JSON。"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from evesde.paths import PROJECT_ROOT, load_config, path as cfg_path
import evesde.processors.jsonl_loader as jsonl_loader


class AccountingTypesLocalizer:
    def __init__(self, project_root: Path, config: Optional[Dict[str, Any]] = None):
        self.project_root = project_root
        cfg = config if config is not None else load_config()
        self.sde_jsonl_path = cfg_path("sde_input", cfg)
        self.language_order = ["en", "de", "es", "fr", "ja", "ko", "ru", "zh"]

    def _lang_lists(self, text_map: Any) -> Optional[Dict[str, List[str]]]:
        if not isinstance(text_map, dict):
            return None
        en = text_map.get("en")
        out = {}
        for lang in self.language_order:
            val = text_map.get(lang) or en
            if val:
                out[lang] = [val]
        return out or None

    def get_manual_entry_journal_messages(self) -> Dict[str, Dict[str, List[str]]]:
        """SDE 缺 journalMessage 的条目，沿用旧版手工补丁。"""
        return {
            "market_escrow": {
                "en": ["Market escrow release"],
                "zh": ["市场契约金退还"],
            },
            "corporation_account_withdrawal": {
                "en": ["{name1} transferred cash from {name2}'s corporate account to {name3}'s account"],
                "zh": ["{name1}从{name2}的军团账户转移现金到{name3}的账户"],
            },
            "brokers_fee": {
                "en": ["Market order commission to broker authorized by: {name1}"],
                "zh": ["{name1}授权的支付给中介的市场订单佣金"],
            },
            "kill_right_fee": {
                "en": ["{buyer} bought kill right on {name} from {seller}"],
                "zh": ["{buyer}从{seller}手中买到了对{name}的击毁权"],
            },
            "bounty_prizes": {
                "en": [
                    "{name1} got bounty prizes for killing pirates in {location}",
                    "{name1} got bounty prize for killing {name2}",
                    "Player got bounty prize for killing someone",
                ],
                "zh": [
                    "{name1}因在{location}击毁海盗而获得追击赏金",
                    "{name1}因击毁{name2}而获得追击赏金",
                    "玩家因为成功追击某人而得到的奖金",
                ],
            },
            "insurance": {
                "en": [
                    "Insurance paid by {name1} to {name2} for ship {location} (Insurance RefID:{refID}",
                    "Insurance paid by {name1} to {name2} covering loss of a {itemname}",
                    "Insurance paid by {name1} to {name2}",
                ],
                "zh": [
                    "{name1}为飞船{location}投保而向{name2}支付保险金 (保单参考ID：{refID})",
                    "{name1}为{itemname}的损失而对{name2}保险赔付",
                    "{name1}支付给{name2}的保险金",
                ],
            },
            "planetary_import_tax": {
                "en": ["Planetary Import Tax: {name1} imported to {location}"],
                "zh": ["行星进口税: 由 {name1} 进口到 {location}"],
            },
            "planetary_export_tax": {
                "en": ["Planetary Export Tax: {name1} exported from {location}"],
                "zh": ["行星出口税: 由 {name1} 从 {location} 出口"],
            },
        }

    def apply_manual_patches(self, accounting_types_data: Dict[str, Any]) -> Dict[str, Any]:
        manual_messages = self.get_manual_entry_journal_messages()
        print("[+] 应用手动编码的entryJournalMessage补丁...")
        patched_count = 0
        for ref_type, manual_message in manual_messages.items():
            if ref_type not in accounting_types_data:
                print(f"[!] 未找到 {ref_type} 条目，无法应用补丁")
                continue
            if "entryJournalMessage" in accounting_types_data[ref_type]:
                print(f"[!] {ref_type} 已有entryJournalMessage，跳过补丁")
                continue
            en_value = manual_message.get("en", [])
            filled = {lang: manual_message.get(lang, en_value) for lang in self.language_order}
            accounting_types_data[ref_type]["entryJournalMessage"] = filled
            print(f"[+] 为 {ref_type} 添加了手动编码的entryJournalMessage")
            patched_count += 1
        print(f"[+] 手动补丁应用完成，共处理了 {patched_count} 个条目")
        return accounting_types_data

    def process_accounting_types(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        result = {}
        for row in sorted(rows, key=lambda r: r.get("_key", 0)):
            ref_type = row.get("internalName")
            if not ref_type:
                continue
            entry = {}
            names = self._lang_lists(row.get("name"))
            if names:
                entry["entryTypeName"] = names
            messages = self._lang_lists(row.get("journalMessage"))
            if messages:
                entry["entryJournalMessage"] = messages
            if entry:
                result[ref_type] = entry
        return result

    def save_json_file(self, data: Any, file_path: Path) -> bool:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[+] 成功保存到 {file_path}")
            return True
        except Exception as e:
            print(f"[x] 保存到 {file_path} 时出错: {e}")
            return False

    def localize_accounting_types(self) -> bool:
        print("[+] 开始处理会计条目类型本地化...")
        jsonl_file = self.sde_jsonl_path / "accountingEntryTypes.jsonl"
        rows = jsonl_loader.load_jsonl(str(jsonl_file))
        if not rows:
            print("[x] 无法读取官方 SDE accountingEntryTypes.jsonl")
            return False

        localized = self.process_accounting_types(rows)
        localized = self.apply_manual_patches(localized)

        output_dir = self.project_root / "output/sde" / "localization"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "accountingentrytypes_localized.json"
        if not self.save_json_file(localized, output_file):
            return False
        print(f"[+] 会计条目类型本地化完成！共处理了 {len(localized)} 个条目。")
        return True


def main():
    localizer = AccountingTypesLocalizer(PROJECT_ROOT)
    if localizer.localize_accounting_types():
        print("\n[+] 会计条目类型本地化成功完成！")
    else:
        print("\n[x] 会计条目类型本地化失败！")


if __name__ == "__main__":
    main()

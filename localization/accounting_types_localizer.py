#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
会计条目类型本地化处理器
处理accountingentrytypes.json的本地化
"""

import json
import os
from pathlib import Path
from utils.http_client import get
from typing import Dict, Any, List, Optional

class AccountingTypesLocalizer:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.localization_dir = project_root / "localization"
        self.extra_dir = self.localization_dir / "extra"
        self.output_dir = self.localization_dir / "output"
        
        # 语言顺序（输出文件中包含的语言）
        self.language_order = ["en", "de", "es", "fr", "ja", "ko", "ru", "zh"]
        
        # 在线数据源URL
        self.accounting_types_url = "https://sde.hoboleaks.space/tq/accountingentrytypes.json"
        
        # 从wallet_journal_ref.py中提取的ref_type与id的映射关系
        self.ref_type_to_id = {
            "player_trading": 1,
            "market_transaction": 2,
            "gm_cash_transfer": 3,
            "mission_reward": 7,
            "clone_activation": 8,
            "inheritance": 9,
            "player_donation": 10,
            "corporation_payment": 11,
            "docking_fee": 12,
            "office_rental_fee": 13,
            "factory_slot_rental_fee": 14,
            "repair_bill": 15,
            "bounty": 16,
            "bounty_prize": 17,
            "insurance": 19,
            "mission_expiration": 20,
            "mission_completion": 21,
            "shares": 22,
            "courier_mission_escrow": 23,
            "mission_cost": 24,
            "agent_miscellaneous": 25,
            "lp_store": 26,
            "agent_location_services": 27,
            "agent_donation": 28,
            "agent_security_services": 29,
            "agent_mission_collateral_paid": 30,
            "agent_mission_collateral_refunded": 31,
            "agents_preward": 32,
            "agent_mission_reward": 33,
            "agent_mission_time_bonus_reward": 34,
            "cspa": 35,
            "cspaofflinerefund": 36,
            "corporation_account_withdrawal": 37,
            "corporation_dividend_payment": 38,
            "corporation_registration_fee": 39,
            "corporation_logo_change_cost": 40,
            "release_of_impounded_property": 41,
            "market_escrow": 42,
            "agent_services_rendered": 43,
            "market_fine_paid": 44,
            "corporation_liquidation": 45,
            "brokers_fee": 46,
            "corporation_bulk_payment": 47,
            "alliance_registration_fee": 48,
            "war_fee": 49,
            "alliance_maintainance_fee": 50,
            "contraband_fine": 51,
            "clone_transfer": 52,
            "acceleration_gate_fee": 53,
            "transaction_tax": 54,
            "jump_clone_installation_fee": 55,
            "manufacturing": 56,
            "researching_technology": 57,
            "researching_time_productivity": 58,
            "researching_material_productivity": 59,
            "copying": 60,
            "reverse_engineering": 62,
            "contract_auction_bid": 63,
            "contract_auction_bid_refund": 64,
            "contract_collateral": 65,
            "contract_reward_refund": 66,
            "contract_auction_sold": 67,
            "contract_reward": 68,
            "contract_collateral_refund": 69,
            "contract_collateral_payout": 70,
            "contract_price": 71,
            "contract_brokers_fee": 72,
            "contract_sales_tax": 73,
            "contract_deposit": 74,
            "contract_deposit_sales_tax": 75,
            "contract_auction_bid_corp": 77,
            "contract_collateral_deposited_corp": 78,
            "contract_price_payment_corp": 79,
            "contract_brokers_fee_corp": 80,
            "contract_deposit_corp": 81,
            "contract_deposit_refund": 82,
            "contract_reward_deposited": 83,
            "contract_reward_deposited_corp": 84,
            "bounty_prizes": 85,
            "advertisement_listing_fee": 86,
            "medal_creation": 87,
            "medal_issued": 88,
            "dna_modification_fee": 90,
            "sovereignity_bill": 91,
            "bounty_prize_corporation_tax": 92,
            "agent_mission_reward_corporation_tax": 93,
            "agent_mission_time_bonus_reward_corporation_tax": 94,
            "upkeep_adjustment_fee": 95,
            "planetary_import_tax": 96,
            "planetary_export_tax": 97,
            "planetary_construction": 98,
            "corporate_reward_payout": 99,
            "bounty_surcharge": 101,
            "contract_reversal": 102,
            "corporate_reward_tax": 103,
            "store_purchase": 106,
            "store_purchase_refund": 107,
            "datacore_fee": 112,
            "war_fee_surrender": 113,
            "war_ally_contract": 114,
            "bounty_reimbursement": 115,
            "kill_right_fee": 116,
            "security_processing_fee": 117,
            "industry_job_tax": 120,
            "infrastructure_hub_maintenance": 122,
            "asset_safety_recovery_tax": 123,
            "opportunity_reward": 124,
            "project_discovery_reward": 125,
            "project_discovery_tax": 126,
            "reprocessing_tax": 127,
            "jump_clone_activation_fee": 128,
            "operation_bonus": 129,
            "resource_wars_reward": 131,
            "duel_wager_escrow": 132,
            "duel_wager_payment": 133,
            "duel_wager_refund": 134,
            "reaction": 135,
            "external_trade_freeze": 136,
            "external_trade_thaw": 137,
            "external_trade_delivery": 138,
            "season_challenge_reward": 139,
            "structure_gate_jump": 140,
            "skill_purchase": 141,
            "item_trader_payment": 142,
            "flux_ticket_sale": 143,
            "flux_payout": 144,
            "flux_tax": 145,
            "flux_ticket_repayment": 146,
            "redeemed_isk_token": 147,
            "daily_challenge_reward": 148,
            "market_provider_tax": 149,
            "ess_escrow_transfer": 155,
            "milestone_reward_payment": 156,
            "under_construction": 166,
            "allignment_based_gate_toll": 168,
            "project_payouts": 170,
            "insurgency_corruption_contribution_reward": 172,
            "insurgency_suppression_contribution_reward": 173,
            "daily_goal_payouts": 174,
            "daily_goal_payouts_tax": 175,
            "cosmetic_market_component_item_purchase": 178,
            "cosmetic_market_skin_sale_broker_fee": 179,
            "cosmetic_market_skin_purchase": 180,
            "cosmetic_market_skin_sale": 181,
            "cosmetic_market_skin_sale_tax": 182,
            "cosmetic_market_skin_transaction": 183,
            "skyhook_claim_fee": 184,
            "air_career_program_reward": 185,
            "freelance_jobs_duration_fee": 186,
            "freelance_jobs_broadcasting_fee": 187,
            "freelance_jobs_reward_escrow": 188,
            "freelance_jobs_reward": 189,
            "freelance_jobs_escrow_refund": 190,
            "freelance_jobs_reward_corporation_tax": 191,
            "gm_plex_fee_refund": 192,
        }
        
        # 创建id到ref_type的反向映射
        self.id_to_ref_type = {v: k for k, v in self.ref_type_to_id.items()}
    
    def load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """加载JSON文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[x] 加载 {file_path} 时出错: {e}")
            return {}
    
    def download_accounting_types(self) -> Dict[str, Any]:
        """从在线数据源下载accountingentrytypes.json"""
        print(f"[+] 开始下载会计条目类型数据...")
        print(f"[+] 下载URL: {self.accounting_types_url}")
        
        try:
            response = get(self.accounting_types_url, timeout=30, verify=False)
            
            accounting_types = response.json()
            print(f"[+] 成功下载会计条目类型数据，共 {len(accounting_types)} 个条目")
            
            return accounting_types
            
        except Exception as e:
            print(f"[x] 下载会计条目类型数据失败: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"[x] 解析会计条目类型JSON数据失败: {e}")
            return {}
    
    def save_json_file(self, data: Any, file_path: Path) -> bool:
        """保存JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[+] 成功保存到 {file_path}")
            return True
        except Exception as e:
            print(f"[x] 保存到 {file_path} 时出错: {e}")
            return False
    
    def create_ordered_dict_by_language(self, data: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """创建按指定语言顺序排序的字典"""
        ordered_dict = {}
        for lang in self.language_order:
            if lang in data:
                ordered_dict[lang] = data[lang]
        return ordered_dict
    
    def load_localization_data(self) -> Dict[str, Dict[str, Any]]:
        """加载所有语言的本地化数据"""
        localization_data = {}
        
        if not self.extra_dir.exists():
            print(f"[x] extra目录不存在: {self.extra_dir}")
            return {}
        
        for lang_dir in self.extra_dir.iterdir():
            if lang_dir.is_dir():
                lang_code = lang_dir.name
                json_file = lang_dir / f"{lang_code}_localization.json"
                if json_file.exists():
                    localization_data[lang_code] = self.load_json_file(json_file)
                    print(f"[+] 已加载 {lang_code} 的本地化数据")
        
        return localization_data
    
    def process_accounting_types(self, accounting_types: Dict[str, Any], 
                               localization_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """处理会计条目类型的本地化"""
        new_accounting_types = {}
        used_ref_types = {}
        
        # 过滤掉key大于10000的项目
        filtered_accounting_types = {k: v for k, v in accounting_types.items() if int(k) <= 10000}
        print(f"[+] 过滤前项目数: {len(accounting_types)}, 过滤后项目数: {len(filtered_accounting_types)}")
        
        # 处理每个会计条目类型
        for entry_id, entry_data in filtered_accounting_types.items():
            try:
                entry_id_int = int(entry_id)
                # 检查ID是否在id_to_ref_type映射中
                if entry_id_int in self.id_to_ref_type:
                    new_entry = {}
                    
                    # 处理entryTypeName
                    if "entryTypeNameID" in entry_data:
                        if isinstance(entry_data["entryTypeNameID"], list):
                            all_translations = {"en": []}
                            for name_id in entry_data["entryTypeNameID"]:
                                if "entryTypeNameTranslated" in entry_data:
                                    all_translations["en"].append(entry_data.get("entryTypeNameTranslated", ""))
                            
                            for lang_code, lang_data in localization_data.items():
                                all_translations[lang_code] = []
                                for name_id in entry_data["entryTypeNameID"]:
                                    if str(name_id) in lang_data:
                                        all_translations[lang_code].append(lang_data[str(name_id)]["text"])
                            
                            entry_type_name = self.create_ordered_dict_by_language(all_translations)
                        else:
                            # 处理单个ID的情况
                            all_translations = {"en": [entry_data.get("entryTypeNameTranslated", "")]}
                            for lang_code, lang_data in localization_data.items():
                                if str(entry_data["entryTypeNameID"]) in lang_data:
                                    all_translations[lang_code] = [lang_data[str(entry_data["entryTypeNameID"])]["text"]]
                            
                            entry_type_name = self.create_ordered_dict_by_language(all_translations)
                        
                        new_entry["entryTypeName"] = entry_type_name
                    
                    # 处理entryJournalMessage
                    if "entryJournalMessageID" in entry_data:
                        if isinstance(entry_data["entryJournalMessageID"], list):
                            all_translations = {"en": []}
                            for message_id in entry_data["entryJournalMessageID"]:
                                if "entryJournalMessageTranslated" in entry_data:
                                    all_translations["en"].append(entry_data.get("entryJournalMessageTranslated", ""))
                            
                            for lang_code, lang_data in localization_data.items():
                                all_translations[lang_code] = []
                                for message_id in entry_data["entryJournalMessageID"]:
                                    if str(message_id) in lang_data:
                                        all_translations[lang_code].append(lang_data[str(message_id)]["text"])
                            
                            entry_journal_message = self.create_ordered_dict_by_language(all_translations)
                        else:
                            all_translations = {"en": [entry_data.get("entryJournalMessageTranslated", "")]}
                            for lang_code, lang_data in localization_data.items():
                                if str(entry_data["entryJournalMessageID"]) in lang_data:
                                    all_translations[lang_code] = [lang_data[str(entry_data["entryJournalMessageID"])]["text"]]
                            
                            entry_journal_message = self.create_ordered_dict_by_language(all_translations)
                        
                        new_entry["entryJournalMessage"] = entry_journal_message
                    
                    # 只有当至少有一个字段时才添加到新数据中
                    if new_entry:
                        ref_type = self.id_to_ref_type[entry_id_int]
                        
                        # 检查是否已经使用过这个ref_type
                        if ref_type in used_ref_types:
                            # 如果已经使用过，添加一个数字后缀
                            used_ref_types[ref_type] += 1
                            new_key = f"{ref_type}_{used_ref_types[ref_type]}"
                            print(f"[!] 重复的ref_type: {ref_type}，重命名为 {new_key}")
                        else:
                            # 第一次使用这个ref_type
                            used_ref_types[ref_type] = 0
                            new_key = ref_type
                        
                        # 使用ref_type作为键
                        new_accounting_types[new_key] = new_entry
            except ValueError:
                # 如果entry_id不是整数，跳过
                continue
        
        return new_accounting_types
    
    def get_manual_entry_journal_messages(self) -> Dict[str, Dict[str, List[str]]]:
        """
        返回手动编码的entryJournalMessage内容
        这些内容来自old版本，用于补充在线数据源中缺失的条目
        """
        return {
            "market_escrow": {
                "en": [
                    "Market escrow release"
                ],
                "zh": [
                    "市场契约金退还"
                ]
            },
            "corporation_account_withdrawal": {
                "en": [
                    "{name1} transferred cash from {name2}'s corporate account to {name3}'s account"
                ],
                "zh": [
                    "{name1}从{name2}的军团账户转移现金到{name3}的账户"
                ]
            },
            "brokers_fee": {
                "en": [
                    "Market order commission to broker authorized by: {name1}"
                ],
                "zh": [
                    "{name1}授权的支付给中介的市场订单佣金"
                ]
            },
            "kill_right_fee": {
                "en": [
                    "{buyer} bought kill right on {name} from {seller}"
                ],
                "zh": [
                    "{buyer}从{seller}手中买到了对{name}的击毁权"
                ]
            },
            "bounty_prizes": {
                "en": [
                    "{name1} got bounty prizes for killing pirates in {location}",
                    "{name1} got bounty prize for killing {name2}",
                    "Player got bounty prize for killing someone"
                ],
                "zh": [
                    "{name1}因在{location}击毁海盗而获得追击赏金",
                    "{name1}因击毁{name2}而获得追击赏金",
                    "玩家因为成功追击某人而得到的奖金"
                ]
            },
            "insurance": {
                "en": [
                    "Insurance paid by {name1} to {name2} for ship {location} (Insurance RefID:{refID}",
                    "Insurance paid by {name1} to {name2} covering loss of a {itemname}",
                    "Insurance paid by {name1} to {name2}"
                ],
                "zh": [
                    "{name1}为飞船{location}投保而向{name2}支付保险金 (保单参考ID：{refID})",
                    "{name1}为{itemname}的损失而对{name2}保险赔付",
                    "{name1}支付给{name2}的保险金"
                ]
            },
            "planetary_import_tax": {
                "en": [
                    "Planetary Import Tax: {name1} imported to {location}"
                ],
                "zh": [
                    "行星进口税: 由 {name1} 进口到 {location}"
                ]
            },
            "planetary_export_tax": {
                "en": [
                    "Planetary Export Tax: {name1} exported from {location}"
                ],
                "zh": [
                    "行星出口税: 由 {name1} 从 {location} 出口"
                ]
            }
        }
    
    def apply_manual_patches(self, accounting_types_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将手动编码的entryJournalMessage应用到会计条目类型数据中
        
        Args:
            accounting_types_data: 从在线数据源处理后的会计条目类型数据
            
        Returns:
            应用补丁后的会计条目类型数据
        """
        manual_messages = self.get_manual_entry_journal_messages()
        
        print("[+] 应用手动编码的entryJournalMessage补丁...")
        
        patched_count = 0
        for ref_type, manual_message in manual_messages.items():
            if ref_type in accounting_types_data:
                # 检查是否已经有entryJournalMessage
                if "entryJournalMessage" not in accounting_types_data[ref_type]:
                    # 为缺失的语言补上英文值
                    en_value = manual_message.get("en", [])
                    filled_message = {}
                    for lang in self.language_order:
                        filled_message[lang] = manual_message.get(lang, en_value)
                    accounting_types_data[ref_type]["entryJournalMessage"] = filled_message
                    print(f"[+] 为 {ref_type} 添加了手动编码的entryJournalMessage")
                    patched_count += 1
                else:
                    print(f"[!] {ref_type} 已有entryJournalMessage，跳过补丁")
            else:
                print(f"[!] 未找到 {ref_type} 条目，无法应用补丁")
        
        print(f"[+] 手动补丁应用完成，共处理了 {patched_count} 个条目")
        return accounting_types_data
    
    def localize_accounting_types(self) -> bool:
        """执行会计条目类型的本地化处理"""
        print("[+] 开始处理会计条目类型本地化...")
        
        # 从在线数据源下载accountingentrytypes.json
        accounting_types = self.download_accounting_types()
        if not accounting_types:
            print("[x] 无法获取会计条目类型数据")
            return False
        
        # 加载本地化数据
        localization_data = self.load_localization_data()
        if not localization_data:
            print("[x] 无法加载本地化数据")
            return False
        
        # 处理会计条目类型
        localized_accounting_types = self.process_accounting_types(accounting_types, localization_data)
        
        # 应用手动补丁
        localized_accounting_types = self.apply_manual_patches(localized_accounting_types)
        
        # 保存本地化后的会计条目类型到项目根目录的output_sde/localization目录
        project_output_dir = self.project_root / "output_sde" / "localization"
        project_output_dir.mkdir(parents=True, exist_ok=True)
        output_file = project_output_dir / "accountingentrytypes_localized.json"
        success = self.save_json_file(localized_accounting_types, output_file)
        
        if success:
            print(f"[+] 会计条目类型本地化完成！共处理了 {len(localized_accounting_types)} 个条目。")
            return True
        else:
            return False

def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    localizer = AccountingTypesLocalizer(project_root)
    
    success = localizer.localize_accounting_types()
    
    if success:
        print("\n[+] 会计条目类型本地化成功完成！")
    else:
        print("\n[x] 会计条目类型本地化失败！")

if __name__ == "__main__":
    main()

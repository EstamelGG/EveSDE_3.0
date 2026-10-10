"""应用编排：构建、报告和发布打包共用显式构建计划。"""
from pathlib import Path
from tempfile import TemporaryDirectory

from evesde import build_prep
from evesde.github import output
from evesde.release.changes import detect_changes
from evesde.brackets.parse_brackets_standalone import main as parse_brackets
from evesde.localization.accounting_types_localizer import AccountingTypesLocalizer
from evesde.paths import PROJECT_ROOT, path
from evesde.pipeline import execute_processor, run_pipeline
from evesde.processors import compression_processor, item_detail_extractor, sde_downloader, version_info_processor
from evesde.release import assets, comparison, reports
from evesde.release.baseline import ReleaseBaseline
from evesde.utils.eve_client import EveClient, set_eve_client
from evesde.utils.single_db import get_db_path


def generate_reports(config, plan, baseline):
    if not comparison.main(config, plan.final_build_number, baseline):
        print("[!] 版本比较未完整完成，详情见比较报告")
    return reports.generate_report(config, plan, baseline)


def run_build(config, plan, *, package=False):
    output("should-publish", False)
    if not plan.should_build:
        reason = "版本尚未同步" if plan.skipped else "Release 已存在"
        print(f"[+] {plan.final_build_number} {reason}，跳过构建")
        return None
    config = dict(config)
    config["sde_build_number"] = plan.build_number
    print(f"[+] 开始构建 {plan.final_build_number}")
    build_prep.rebuild_output_directory(config)
    build_prep.ensure_directories(config)
    client = EveClient.from_tq(path("client_cache", config), client_data=plan.client_data)
    set_eve_client(client)
    config["eve_client"] = client
    try:
        execute_processor(lambda cfg: sde_downloader.main(cfg, build_number=plan.build_number), "SDE下载", config)
        execute_processor(lambda cfg: AccountingTypesLocalizer(PROJECT_ROOT, cfg).localize_accounting_types(),
                          "会计条目类型", config)
        parse_brackets(eve_client=client)
        run_pipeline(config)
        execute_processor(lambda cfg: version_info_processor.main(
            cfg, build_number=plan.final_build_number, release_date=plan.release_date, build_key=plan.build_key
        ), "版本信息", config)
        execute_processor(compression_processor.main, "图标打包", config)
        with TemporaryDirectory(prefix="evesde-release-") as directory:
            baseline = ReleaseBaseline(plan.repository, plan.previous_release, Path(directory))
            decision = detect_changes(config, plan, baseline)
            decision_path = decision.save(config)
            output("has-changes", decision.has_changes)
            output("decision", str(decision_path))
            print(f"[+] 发布内容检查: {'; '.join(decision.reasons)}")
            if not decision.has_changes:
                print("[+] 无实际内容变化，跳过详情导出、报告打包、历史提交和发布")
                return None
            for lang in ("en", "zh"):
                execute_processor(lambda cfg, lang=lang: item_detail_extractor.item_detail_extract(
                    str(get_db_path(cfg)), str(path(f"item_detail_{lang}", cfg)), lang=lang
                ), f"物品详情 {lang}", config)
            build_prep.write_latest_log(plan.final_build_number, plan.release_date, config)
            whats_new = generate_reports(config, plan, baseline)
            if package:
                manifest = assets.prepare_release(config, plan, baseline, whats_new)
                output("should-publish", not plan.debug)
                return manifest
    finally:
        set_eve_client(None)
        client.close()
    print("[+] 构建完成")
    return None

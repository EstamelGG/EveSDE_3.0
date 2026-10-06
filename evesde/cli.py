"""统一命令入口，Actions 环境变量仅在此和 github 适配层读取。"""
import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from evesde.paths import load_config


def env_flag(name):
    return os.environ.get(name, "false").lower() == "true"


def parser():
    root = argparse.ArgumentParser(description="EVE SDE 构建与发布工具")
    commands = root.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="查询一次版本，保存构建计划")
    plan.add_argument("--output", type=Path, default=Path("tmp/build-plan.json"))
    plan.add_argument("--patch", action="store_true", default=env_flag("BUILD_PATCH"))
    plan.add_argument("--debug", action="store_true", default=env_flag("DEBUG_MODE"))
    plan.add_argument("--skip-version-check", action="store_true", default=env_flag("SKIP_VERSION_CHECK"))
    build = commands.add_parser("build", help="构建全部数据、图标和报告")
    build.add_argument("--plan", type=Path)
    build.add_argument("--package", action="store_true", help="同时校验并生成全部 Release 附件")
    build.add_argument("--skip-version-check", action="store_true", default=env_flag("SKIP_VERSION_CHECK"))
    build.add_argument("--force-rebuild", action="store_true", help="兼容旧参数；build 总是重新构建")
    for command, help_text in (("reports", "重新生成比较报告"), ("package", "校验并打包现有构建")):
        child = commands.add_parser(command, help=help_text)
        child.add_argument("--plan", type=Path, required=True)
    history = commands.add_parser("sync-history", help="向独立 checkout 同步历史和物品详情")
    history.add_argument("--manifest", type=Path, required=True)
    history.add_argument("--checkout", type=Path, required=True)
    history.add_argument("--branch", default="main")
    history.add_argument("--push", action="store_true")
    cleanup = commands.add_parser("clean-artifacts", help="清理过期 Actions 产物")
    cleanup.add_argument("--days", type=int, default=5)
    cleanup.add_argument("--keep", type=int, default=5)
    summary = commands.add_parser("summary", help="写入 Actions 运行摘要")
    summary.add_argument("--plan", type=Path, default=Path("tmp/build-plan.json"))
    summary.add_argument("--status", required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return dispatch(args)
    except Exception as exc:
        print(f"[x] {exc}", file=sys.stderr)
        return 1


def dispatch(args):
    from evesde.github import output, repository_name
    from evesde.release.plan import BuildPlan, create_plan

    if args.command == "summary":
        plan = BuildPlan.load(args.plan) if args.plan.is_file() else None
        version = plan.final_build_number if plan else "未确定"
        mode = "调试（未发布）" if plan and plan.debug else "构建与发布"
        if plan and not plan.should_build:
            mode = "相同版本已发布，跳过"
        decision_path = Path("output/release/publish-decision.json")
        if plan and decision_path.is_file():
            decision = json.loads(decision_path.read_text(encoding="utf-8"))
            if decision.get("build_number") == plan.final_build_number and not decision["has_changes"]:
                mode = "仅版本信息变化，跳过发布"
        message = f"### EVE SDE {version}\n\n- 模式：{mode}\n- 运行状态：{args.status}\n"
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as stream:
                stream.write(message)
        print(message)
        return 0
    if args.command == "sync-history":
        from evesde.release.history import sync_history
        sync_history(args.manifest, args.checkout, branch=args.branch, push=args.push)
        return 0
    config = load_config()
    if args.command == "clean-artifacts":
        from evesde.maintenance import clean_artifacts
        clean_artifacts(repository_name(config), days=args.days, keep=args.keep)
        return 0
    if args.command == "plan":
        plan = create_plan(config, patch=args.patch, debug=args.debug, skip_version_check=args.skip_version_check)
        plan.save(args.output)
        output("should-build", plan.should_build)
        output("final-build-number", plan.final_build_number)
        output("debug", plan.debug)
        print(f"[+] 版本 {plan.final_build_number}，构建={plan.should_build}，计划={args.output}")
        return 0
    plan = BuildPlan.load(args.plan) if args.plan else create_plan(
        config, check_release=False, skip_version_check=args.skip_version_check
    )
    if not plan.should_build:
        print("[+] 此计划无需构建")
        return 0
    if args.command == "build":
        from evesde.application import run_build
        run_build(config, plan, package=args.package)
    else:
        from evesde.application import generate_reports
        from evesde.release import assets
        from evesde.release.baseline import ReleaseBaseline
        with TemporaryDirectory(prefix="evesde-release-") as directory:
            baseline = ReleaseBaseline(plan.repository, plan.previous_release, Path(directory))
            if args.command == "reports":
                generate_reports(config, plan, baseline)
            else:
                from evesde.release.changes import detect_changes
                output("should-publish", False)
                decision = detect_changes(config, plan, baseline)
                output("decision", str(decision.save(config)))
                output("has-changes", decision.has_changes)
                if not decision.has_changes:
                    print("[+] 实际内容未变，跳过发布打包")
                    return 0
                whats_new = assets.find_whats_new(plan.final_build_number, config)
                assets.prepare_release(config, plan, baseline, whats_new)
                output("should-publish", not plan.debug)
    return 0

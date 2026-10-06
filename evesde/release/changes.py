"""比较实际发布内容，版本字段或容器元数据变化不会触发发布。"""
from contextlib import closing
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import zip_longest
import json
from pathlib import Path
import sqlite3
import zipfile

from evesde.paths import path

# 仅忽略已知的版本记录字段，版本表结构和其他业务列仍然参与比较。
VERSION_COLUMNS = {"id", "build_number", "patch_number", "release_date", "build_key"}


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def database_changes(previous: Path, current: Path) -> list[str]:
    """只读比较结构和行内容；忽略页布局、插入顺序、内部统计和版本字段。"""
    with closing(sqlite3.connect(f"{previous.resolve().as_uri()}?mode=ro", uri=True)) as old, \
         closing(sqlite3.connect(f"{current.resolve().as_uri()}?mode=ro", uri=True)) as new:
        for conn in (old, new):
            if conn.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise RuntimeError("比较数据库时完整性检查失败")
        for pragma in ("user_version", "application_id"):
            if old.execute(f"PRAGMA {pragma}").fetchone() != new.execute(f"PRAGMA {pragma}").fetchone():
                return [f"数据库设置变化: {pragma}"]
        schema_sql = "SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE substr(name, 1, 7) != 'sqlite_' ORDER BY type, name"
        old_schema, new_schema = old.execute(schema_sql).fetchall(), new.execute(schema_sql).fetchall()
        if old_schema != new_schema:
            return ["数据库结构变化"]
        changes = []
        sentinel = object()
        for kind, table, _, _ in new_schema:
            if kind != "table":
                continue
            info = new.execute(f"PRAGMA table_xinfo({quote_identifier(table)})").fetchall()
            columns = [row[1] for row in info if row[6] != 1]
            if table.lower() == "version_info":
                columns = [name for name in columns if name.lower() not in VERSION_COLUMNS]
            if not columns:
                continue
            # 保留重复行数量与 SQLite 值类型；EXCEPT 会去重，不能单独用来判等。
            keys = [row[1] for row in sorted(info, key=lambda row: row[5]) if row[5] and row[1] in columns]
            order = keys + [name for name in columns if name not in keys]
            selected = ", ".join(quote_identifier(name) for name in columns)
            ordering = ", ".join(f"{quote_identifier(name)} COLLATE BINARY, typeof({quote_identifier(name)})" for name in order)
            query = f"SELECT {selected} FROM {quote_identifier(table)} ORDER BY {ordering}"
            for left, right in zip_longest(old.execute(query), new.execute(query), fillvalue=sentinel):
                if left is sentinel or right is sentinel or any(type(a) is not type(b) or a != b for a, b in zip(left, right)):
                    changes.append(f"数据库表内容变化: {table}")
                    break
        return changes


def content_hash(stream, *, json_content=False):
    digest = sha256()
    if json_content:
        # 对象键顺序、缩进不影响实际 JSON 数据，数组顺序仍然保留。
        value = json.load(stream)
        for chunk in json.JSONEncoder(sort_keys=True, ensure_ascii=False).iterencode(value):
            digest.update(chunk.encode("utf-8"))
    else:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def zip_contents(filename: Path):
    with zipfile.ZipFile(filename) as archive:
        result = {}
        for member in archive.infolist():
            if member.is_dir():
                continue
            if member.filename in result:
                raise RuntimeError(f"压缩包包含重复路径: {member.filename}")
            with archive.open(member) as stream:
                result[member.filename] = content_hash(stream, json_content=member.filename.endswith(".json"))
        return result


def files_equal(previous: Path, current: Path):
    if current.suffix.lower() == ".zip":
        return zip_contents(previous) == zip_contents(current)
    with previous.open("rb") as old, current.open("rb") as new:
        is_json = current.suffix.lower() == ".json"
        return content_hash(old, json_content=is_json) == content_hash(new, json_content=is_json)


@dataclass(frozen=True)
class ReleaseDecision:
    build_number: str
    previous_tag: str | None
    has_changes: bool
    reasons: list[str]

    def save(self, config):
        destination = path("release_output", config) / "publish-decision.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destination


def detect_changes(config, plan, baseline) -> ReleaseDecision:
    """只有确定所有有效内容相同才跳过；比较错误向上传播，不能误判为无变化。"""
    if baseline.release is None:
        return ReleaseDecision(plan.final_build_number, None, True, ["首次发布"])
    old_root = baseline.sde_directory()
    new_root = path("sde_output", config)
    for required in ("db/item_db.sqlite", "texts.zip"):
        if not (new_root / required).is_file():
            raise RuntimeError(f"当前构建缺少必需产物: {required}")
    old_icons = baseline.asset("icons.zip", required=True)
    new_icons = path("icons_output", config) / "icons.zip"
    changes = []
    if not files_equal(old_icons, new_icons):
        changes.append("图标文件变化")
    # latest.log 为运行记录；其余所有输出都纳入比较，包含新增/删除文件。
    def inventory(root):
        return {file.relative_to(root).as_posix(): file for file in root.rglob("*")
                if file.is_file() and file.relative_to(root).as_posix() != "latest.log"}
    previous, current = inventory(old_root), inventory(new_root)
    for name in sorted(previous.keys() | current.keys()):
        if name not in previous or name not in current:
            changes.append(f"SDE 文件新增/删除: {name}")
        elif name.endswith(".sqlite"):
            changes.extend(database_changes(previous[name], current[name]))
        elif not files_equal(previous[name], current[name]):
            changes.append(f"SDE 文件内容变化: {name}")
    return ReleaseDecision(plan.final_build_number, baseline.release.get("tag_name"), bool(changes),
                           changes or ["仅版本信息或打包元数据变化，实际发布内容相同"])

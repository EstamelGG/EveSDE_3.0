"""Actions 产物维护；先完成分页查询，再删除，避免分页偏移漏项。"""
from datetime import datetime, timedelta, timezone

from evesde.github import GitHub


def clean_artifacts(repository: str, *, days=5, keep=5, now=None):
    if days < 0 or keep < 0:
        raise ValueError("days 和 keep 不能为负数")
    github = GitHub(repository)
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    artifacts = sorted(github.pages("actions/artifacts", "artifacts"),
                       key=lambda item: item["created_at"], reverse=True)
    deleted = []
    for artifact in artifacts[keep:]:
        created = datetime.fromisoformat(artifact["created_at"].replace("Z", "+00:00"))
        if created < cutoff:
            github.delete_artifact(artifact["id"])
            deleted.append(artifact["id"])
    print(f"[+] 已删除 {len(deleted)} 个过期产物，保留最近 {keep} 个")
    return deleted

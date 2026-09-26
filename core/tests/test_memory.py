"""四层记忆测试：分层写入 / 三因子召回 / 遗忘衰减 / 隔离污染探针 / 编辑删除。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from amber_core.memory import MemoryStore

P_A, P_B, OWNER = "profile_A", "profile_B", "user1"


@pytest.fixture()
def store(tmp_path):
    s = MemoryStore(tmp_path / "mem.db")
    yield s
    s.close()


def _now(h: int = 0) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) + timedelta(hours=h)).isoformat()


def test_layer_validation_and_scope_required(store):
    with pytest.raises(ValueError):
        store.add(P_A, OWNER, "wrong_layer", "x")
    with pytest.raises(ValueError):
        store.add(P_A, OWNER, "semantic", "   ")
    with pytest.raises(ValueError):
        store.add("  ", OWNER, "semantic", "x")
    m = store.add(P_A, OWNER, "core", "用户对花生过敏", importance=9.0)
    assert m > 0


def test_isolation_pollution_probe(store):
    """污染探针：A 角色的记忆绝不能被 B 角色召回；owner 维度同理。"""
    store.add(P_A, OWNER, "semantic", "用户正在筹备求婚", importance=9.0)
    store.add(P_B, OWNER, "semantic", "用户上周去爬了泰山", importance=9.0)
    store.add(P_A, "user2", "semantic", "user2 的私密话题", importance=9.0)

    hit_a = [r.content for r in store.recall(P_A, OWNER, "求婚", top_k=10)]
    hit_b = [r.content for r in store.recall(P_B, OWNER, "求婚 泰山", top_k=10)]
    assert hit_a == ["用户正在筹备求婚"]
    assert hit_b == ["用户上周去爬了泰山"]

    other = [r.content for r in store.recall(P_A, "user2", "私密话题", top_k=10)]
    assert other == ["user2 的私密话题"]
    assert store.count(profile_id=P_A, owner=OWNER) == 1
    with pytest.raises(ValueError):
        store.count()  # 拒绝无范围全库计数


def test_three_factor_ranking(store):
    store.add(P_A, OWNER, "semantic", "用户爱吃火锅", importance=9.0, now=_now(-1))
    store.add(P_A, OWNER, "semantic", "用户养了橘猫", importance=5.0, now=_now(-1))
    store.add(P_A, OWNER, "episodic", "上周聊了火锅底料", importance=3.0, now=_now(-1))
    top = store.recall(P_A, OWNER, "火锅 好吃", top_k=3)
    assert top[0].content == "用户爱吃火锅"  # 相关×重要×新鲜 综合最高
    assert len(top) == 2  # 「养橘猫」零相关被过滤（宁缺勿滥）


def test_decay_and_archive(store):
    sid = store.add(P_A, OWNER, "episodic", "很久以前的琐碎日常", importance=2.0, now=_now(-60 * 24 * 3))
    cid = store.add(P_A, OWNER, "core", "用户对花生过敏", importance=10.0, now=_now(-60 * 24 * 3))
    archived = store.apply_decay()
    rows = {r["id"]: r for r in store.conn.execute("SELECT * FROM memories")}
    assert archived == 1 and rows[sid]["archived"] == 1
    assert rows[cid]["archived"] == 0  # core 永不归档
    assert store.recall(P_A, OWNER, "琐碎", top_k=5) == []  # 归档默认不召回
    assert store.recall(P_A, OWNER, "过敏", top_k=5)[0].content == "用户对花生过敏"


def test_edit_delete_scoped(store):
    mid = store.add(P_A, OWNER, "core", "旧称呼", importance=8.0)
    store.edit(P_A, OWNER, mid, "新称呼")
    assert store.recall(P_A, OWNER, "称呼", top_k=1)[0].content == "新称呼"
    with pytest.raises(LookupError):
        store.edit(P_B, OWNER, mid, "越权")  # 跨角色改不到
    with pytest.raises(LookupError):
        store.delete(P_A, OWNER, 99999)
    store.delete(P_A, OWNER, mid)
    assert store.count(profile_id=P_A, owner=OWNER) == 0


def test_relevance_fn_injection(store):
    store.add(P_A, OWNER, "semantic", "用户在上海工作", importance=7.0)
    hit = store.recall(P_A, OWNER, "上海", top_k=1, relevance_fn=lambda q, c: 1.0 if "上海" in c else 0.0)
    assert hit[0].content == "用户在上海工作"
    miss = store.recall(P_A, OWNER, "北京", top_k=1, relevance_fn=lambda q, c: 1.0 if "北京" in c else 0.0)
    assert miss == []

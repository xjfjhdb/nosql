# -*- coding: utf-8 -*-
"""
task3_redis.py —— 第三题：Redis 学习信息维护、章节记录、排行榜、会话过期与类型核验
运行环境：Redis Cluster（三主三从）启动节点 127.0.0.1:7000~7002
运行：python task3_redis.py
说明：所有键统一使用前缀 exam:<SID>:
"""
import time
from redis.cluster import RedisCluster, ClusterNode

SID = "12403030110"
S = int(SID[-2:])
A = S % 3                  # 1
B = S % 4                  # 2
C = S % 5                  # 0

PREFIX = "exam:" + SID + ":"
STUDENT_HASH = PREFIX + "student"
CHAPTER_SET = PREFIX + "chapters:done"
RANK_ZSET = PREFIX + "rank"
SESSION_KEY = PREFIX + "session"

r = RedisCluster(
    startup_nodes=[ClusterNode("127.0.0.1", 7000), ClusterNode("127.0.0.1", 7001)],
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=5,
)

LINE = "=" * 72

print(LINE)
print("个人参数：S=%d  A=%d  B=%d  C=%d" % (S, A, B, C))
print("键前缀：%s" % PREFIX)
print("集群节点：")
for node in r.get_nodes():
    print("      %s:%s  %s" % (node.host, node.port, node.server_type))
print(LINE)

# 清理本人前缀下的历史键，保证本次运行结果可复现（只删自己的键）
for k in r.scan_iter(match=PREFIX + "*", count=200):
    r.delete(k)

# ------------------------------------------------------------------
# 1. 学生信息维护（Hash）
# ------------------------------------------------------------------
print("\n【1】学生信息维护（Hash：%s）" % STUDENT_HASH)
r.hset(STUDENT_HASH, mapping={
    "studentId": SID,
    "name": "张三",
    "className": "124030301",
    "courseId": "COURSE-" + SID + "-01",
    "status": "learning",
})
print("（1）创建后字段：", r.hgetall(STUDENT_HASH))

r.hset(STUDENT_HASH, "status", "completed")
print("（2）将 status 修改为 completed 后：", r.hgetall(STUDENT_HASH))

print("（3）单独读取 name   =", r.hget(STUDENT_HASH, "name"))
print("（3）单独读取 status =", r.hget(STUDENT_HASH, "status"))

print("（4）完整 Hash：")
for field, value in r.hgetall(STUDENT_HASH).items():
    print("      %-10s = %s" % (field, value))
print("      studentId / className / courseId 均在，其他字段保留")

# ------------------------------------------------------------------
# 2. 已完成章节记录（Set）
# ------------------------------------------------------------------
print("\n【2】已完成章节记录（Set：%s）" % CHAPTER_SET)
for ch in ["CH01", "CH02", "CH02", "CH03"]:
    added = r.sadd(CHAPTER_SET, ch)
    print("提交 %s -> 本次新增成员数=%d，当前已完成章节数量=%d"
          % (ch, added, r.scard(CHAPTER_SET)))

print("（2）最终全部章节：", sorted(r.smembers(CHAPTER_SET)))
print("（3）CH02 是否已完成：%s    CH04 是否已完成：%s"
      % (bool(r.sismember(CHAPTER_SET, "CH02")), bool(r.sismember(CHAPTER_SET, "CH04"))))
print("（4）再次提交 CH02 -> 新增成员数=%d，章节数量=%d（数量未增加，重复提交被 Set 去重）"
      % (r.sadd(CHAPTER_SET, "CH02"), r.scard(CHAPTER_SET)))

# ------------------------------------------------------------------
# 3. 成绩排行榜（Sorted Set）
# ------------------------------------------------------------------
print("\n【3】成绩排行榜（Sorted Set：%s）" % RANK_ZSET)
me = "Student:" + SID
r.zadd(RANK_ZSET, {me: 70 + C, "demo:01": 85, "demo:02": 90, "demo:03": 60, "demo:04": 80})
print("初始成员与分数：", r.zrevrange(RANK_ZSET, 0, -1, withscores=True))

print("（1）按分数从高到低前 3 名：")
top3 = r.zrevrange(RANK_ZSET, 0, 2, withscores=True)
for idx, (member, score) in enumerate(top3, start=1):
    print("      第%d名  %-18s %s分" % (idx, member, int(score)))

new_score = r.zincrby(RANK_ZSET, 20, me)
print("（2）本人 %s 加 20 分后分数：%s" % (me, int(new_score)))

print("（3）再次输出前 3 名：")
top3 = r.zrevrange(RANK_ZSET, 0, 2, withscores=True)
for idx, (member, score) in enumerate(top3, start=1):
    print("      第%d名  %-18s %s分" % (idx, member, int(score)))

score = r.zscore(RANK_ZSET, me)
rank0 = r.zrevrank(RANK_ZSET, me)     # 降序位置，从 0 开始
print("（4）本人更新后分数 = %s，降序位置（0 起）= %d -> 名次：第%d名"
      % (int(score), rank0, rank0 + 1))
print("    （名次按降序位置计算，不采用并列名次制）")

# ------------------------------------------------------------------
# 4. 会话生命周期（String + TTL）
# ------------------------------------------------------------------
print("\n【4】会话生命周期（String：%s）" % SESSION_KEY)
r.set(SESSION_KEY, "session-12403030110-abc", ex=5)
print("（1）创建后立即输出：键值 = %s，TTL = %d 秒" % (r.get(SESSION_KEY), r.ttl(SESSION_KEY)))

# 第 5 小问要求“会话键的数据类型应在过期前检查”，故此处先记录类型
session_type = r.type(SESSION_KEY)

print("（2）等待至少 6 秒 ...")
time.sleep(6)
print("（3）等待 6 秒后：键是否存在 = %s，TTL = %d（-2 表示键已不存在）"
      % (bool(r.exists(SESSION_KEY)), r.ttl(SESSION_KEY)))
passed = (r.exists(SESSION_KEY) == 0 and r.ttl(SESSION_KEY) == -2)
print("（4）过期验证：%s（设置 5 秒有效，6 秒后键已自动删除）" % ("通过" if passed else "不通过"))

# ------------------------------------------------------------------
# 5. 数据类型核验与说明
# ------------------------------------------------------------------
print("\n【5】四类键的实际数据类型（TYPE 命令）")
print("      %-45s %s" % (STUDENT_HASH, r.type(STUDENT_HASH)))
print("      %-45s %s" % (CHAPTER_SET, r.type(CHAPTER_SET)))
print("      %-45s %s" % (RANK_ZSET, r.type(RANK_ZSET)))
print("      %-45s %s（创建后、过期前记录的返回值）" % (SESSION_KEY, session_type))

print("\n      选择理由：")
print("      Hash  ：学生信息是多个“字段—值”对（学号/姓名/班级/课程/状态），"
          "Hash 可按字段读写与修改，无需整体序列化，字段扩展也不影响其他字段。")
print("      Set   ：已完成章节要求去重且需要判断“某章节是否已完成”，"
          "Set 天然去重并提供 O(1) 的 SISMEMBER 成员判断。")
print("      ZSet  ：排行榜既要按分数排序又要取前 N 名，"
          "ZSet 以分数为排序权重、成员唯一，可直接 ZREVRANGE/ZINCRBY 实现排名与加分。")
print("      String：会话键只是单个标识值，配合 EX 过期时间即可实现自动失效，"
          "是最轻量的单值结构。")

print("\n" + LINE)
print("第三题执行完毕")

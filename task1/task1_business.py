# -*- coding: utf-8 -*-
"""
task1_business.py —— 第一题业务操作（课程查询、局部更新、幂等新增、核验）
前提：已执行 task1_init.py 初始化个人数据库 exam_<SID>
运行：python task1_business.py
说明：脚本本身不初始化数据，可连续重复执行，用于验证重复执行效果
"""
import os
import unicodedata
from pymongo import MongoClient

SID = "12403030110"
S = int(SID[-2:])          # 10
A = S % 3                  # 1
B = S % 4                  # 2
C = S % 5                  # 0

URI = os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27018/?replicaSet=rs0")
client = MongoClient(URI, serverSelectionTimeoutMS=5000)
exam_db = client["exam_" + SID]
courses = exam_db["courses"]

COURSE01 = "COURSE-" + SID + "-01"
NEW_CH02_TITLE = "Redis基础与应用-%d" % S          # Redis基础与应用-10
CH03 = {"chapterId": "CH03", "title": "Redis高级操作", "hours": 2 + A}  # hours = 2+1 = 3

LINE = "=" * 72


def chapters_count(doc):
    """在服务端统计章节数组长度（不写死数量）"""
    return len(doc.get("chapters", []))


def dwidth(text):
    """按控制台显示宽度计算：中文/全角算 2 列，其他算 1 列"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def pad(text, width):
    return text + " " * (width - dwidth(text))


print(LINE)
print("个人参数：S=%d  A=%d  B=%d  C=%d" % (S, A, B, C))
print("个人数据库：exam_%s   课程集合：courses" % SID)
print(LINE)

# ------------------------------------------------------------------
# 1. 查询课程：张老师授课且状态 OPEN，输出课程编号/名称/章节数量
# ------------------------------------------------------------------
print("\n【1】查询“张老师”授课且状态为 OPEN 的课程")
pipeline = [
    {"$match": {"teacher": "张老师", "status": "OPEN"}},
    {"$project": {"_id": 1, "title": 1, "chapterCount": {"$size": "$chapters"}}},
    {"$sort": {"_id": 1}},
]
rows = list(courses.aggregate(pipeline))
print(pad("课程编号", 24) + pad("课程名称", 14) + "章节数量")
for r in rows:
    print(pad(r["_id"], 24) + pad(r["title"], 14) + str(r["chapterCount"]))
print("命中课程数 = %d（$size 在服务端按 chapters 数组实际长度计算）" % len(rows))

# ------------------------------------------------------------------
# 2. 修改第 01 门课程 CH02 章节标题（局部更新 + arrayFilters）
# ------------------------------------------------------------------
print("\n【2】将第 01 门课程 CH02 章节标题改为：%s" % NEW_CH02_TITLE)
res = courses.update_one(
    {"_id": COURSE01},
    {"$set": {"chapters.$[c].title": NEW_CH02_TITLE}},
    array_filters=[{"c.chapterId": "CH02"}],
)
print("匹配文档数 = %d，实际修改文档数 = %d" % (res.matched_count, res.modified_count))
doc01 = courses.find_one({"_id": COURSE01})
print("更新后课程文档：")
for ch in doc01["chapters"]:
    print("  chapterId=%s  title=%s  hours=%s" % (ch["chapterId"], ch["title"], ch["hours"]))
print("其余字段：title=%s  teacher=%s  status=%s" % (doc01["title"], doc01["teacher"], doc01["status"]))

# ------------------------------------------------------------------
# 3. 增加 CH03 章节并防止重复（$ne 条件 + $push，连续执行两次）
# ------------------------------------------------------------------
print("\n【3】向第 01 门课程增加章节 CH03，连续执行两次")
print("待新增章节：%s  title=%s  hours=%d" % (CH03["chapterId"], CH03["title"], CH03["hours"]))
for i in (1, 2):
    res = courses.update_one(
        {"_id": COURSE01, "chapters.chapterId": {"$ne": "CH03"}},
        {"$push": {"chapters": CH03}},
    )
    print("第 %d 次执行：匹配 = %d，修改 = %d（匹配 0 表示已存在 CH03，条件阻止了重复插入）"
          % (i, res.matched_count, res.modified_count))

# ------------------------------------------------------------------
# 4. 验证与解释
# ------------------------------------------------------------------
print("\n【4】核验结果")
doc01 = courses.find_one({"_id": COURSE01})

ch02_title = None
ch03_count = 0
for ch in doc01["chapters"]:
    if ch["chapterId"] == "CH02":
        ch02_title = ch["title"]
    if ch["chapterId"] == "CH03":
        ch03_count += 1

# CH03 数量同时用聚合在服务端再核验一次
ch03_filter = {"$filter": {"input": "$chapters", "as": "c",
                           "cond": {"$eq": ["$$c.chapterId", "CH03"]}}}
ch03_proj = {"$project": {"ch03": {"$size": ch03_filter}}}
agg = list(courses.aggregate([{"$match": {"_id": COURSE01}}, ch03_proj]))
server_ch03 = agg[0]["ch03"]

print("（1）修改后 CH02 的标题：%s" % ch02_title)
print("（2）两次新增后 CH03 的数量：%d（服务端聚合复核 = %d）" % (ch03_count, server_ch03))
print("（3）最终章节总数：%d" % len(doc01["chapters"]))
print("（4）teacher = %s，status = %s（与初始值一致：%s）"
      % (doc01["teacher"], doc01["status"],
         "是" if (doc01["teacher"] == "张老师" and doc01["status"] == "OPEN") else "否"))

print("\n最终课程文档：")
print(doc01)

print("\n【解释】为什么本题适合局部更新，而不宜直接替换整个课程文档？")
print("1) 本题只改一个数组元素的一个字段，$set 配 arrayFilters 只写入发生变化的路径，"
      "其余字段（title/teacher/status 及其他章节）由服务端原样保留，天然满足“保留其他字段与其他章节”的要求；")
print("2) 若在客户端读出整个文档、改完再 replaceOne 写回，会把客户端拿到的旧快照整体覆盖库中当前值，"
      "并发写入时其他人刚提交的修改会丢失（读—改—写竞态），也无法防止中途被改动的字段回退；")
print("3) 整文档替换需要传输全部数据并重写整个文档，网络与写入开销都更大；局部更新的更新路径短、并发冲突面小；")
print("4) 新增章节用“$ne 判断 + $push”合并成一次单文档原子更新，天然实现顺序重复执行不重复插入，"
      "不需要先查询再判断，也不存在读改写的中间态。")

# -*- coding: utf-8 -*-
"""
task1_init.py  —— 第一题初始化代码（与业务操作代码分开）
功能：在个人数据库 exam_<SID> 中重建 courses 集合
说明：SID 为本人完整学号，S = 学号最后两位对应的整数
运行：python task1_init.py
"""
import os
from pymongo import MongoClient

SID = "12403030110"           # 本人完整学号
S = int(SID[-2:])             # 10
A = S % 3                     # 1
B = S % 4                     # 2
C = S % 5                     # 0

URI = os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27018/?replicaSet=rs0")

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
exam_db = client["exam_" + SID]
courses = exam_db["courses"]

# 初始化：清空后重新插入三门课程（只在初始化阶段执行，业务脚本不重复初始化）
courses.delete_many({})
result = courses.insert_many([
    {
        "_id": "COURSE-" + SID + "-01",
        "title": "NoSQL数据库",
        "teacher": "张老师",
        "status": "OPEN",
        "chapters": [
            {"chapterId": "CH01", "title": "MongoDB基础", "hours": 2},
            {"chapterId": "CH02", "title": "Redis基础", "hours": 2},
        ],
    },
    {
        "_id": "COURSE-" + SID + "-02",
        "title": "数据库原理",
        "teacher": "张老师",
        "status": "CLOSED",
        "chapters": [
            {"chapterId": "CH01", "title": "关系模型", "hours": 2},
        ],
    },
    {
        "_id": "COURSE-" + SID + "-03",
        "title": "机器学习",
        "teacher": "李老师",
        "status": "OPEN",
        "chapters": [
            {"chapterId": "CH01", "title": "分类", "hours": 2},
            {"chapterId": "CH02", "title": "聚类", "hours": 2},
        ],
    },
])

print("个人参数：S=%d, A=%d, B=%d, C=%d" % (S, A, B, C))
print("数据库：exam_%s" % SID)
print("初始化完成，course 文档数量 = %d，插入 id 数 = %d" % (courses.count_documents({}), len(result.inserted_ids)))
for doc in courses.find({}, {"_id": 1, "title": 1, "chapters": 1}):
    print("  -", doc["_id"], doc["title"], "章节数=", len(doc["chapters"]))

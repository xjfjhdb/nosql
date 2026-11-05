========================================================
《NoSQL数据库》上机测验  代码目录说明
========================================================

一、个人信息
  学号（SID）：12403030110
  姓名：张三
  班级：124030301
  S  = 学号最后两位 = 10
  A  = S mod 3 = 1
  B  = S mod 4 = 2
  C  = S mod 5 = 0
  Stock = 5 + C = 5      Buy = 1 + A = 2
  N     = 1000 + 100C + S = 1010     Q = 100

二、运行环境
  操作系统：Windows 10/11 x64
  Python：3.13
  MongoDB：8.3（单节点副本集 rs0，监听 127.0.0.1:27018；事务必须在副本集上运行）
          连接串 mongodb://127.0.0.1:27018/?replicaSet=rs0，
          可通过环境变量 MONGODB_URI 覆盖，代码中不含任何账号密码。
  Redis：8.10.2，三主三从 Cluster（主 127.0.0.1:7000/7001/7002，从 7003/7004/7005）
  依赖：pymongo 4.19.0、redis-py 8.1.0
      安装：pip install pymongo redis

三、目录与执行方法
  task1\  第一题 MongoDB 课程信息查询与维护
    task1_init.py       初始化代码（重建 exam_12403030110.courses，与业务代码分开）
    task1_business.py   业务操作（查询 / 局部更新 / 幂等新增 / 核验），不重复初始化
    result_init.txt     初始化运行结果
    result_task1.txt    业务操作运行结果
    说明.md             简短说明

  task2\  第二题 MongoDB 原子扣减与事务验证
    task2_order.py      原子扣减、结果分类、事务订购函数、T1～T4 场景测试（场景内自行重置数据）
    result_task2.txt    运行结果
    说明.md             简短说明

  task3\  第三题 Redis 学习信息与排行榜
    task3_redis.py      Hash / Set / Sorted Set / String+TTL 与数据类型核验
    result_task3.txt    运行结果
    说明.md             简短说明（含数据类型选择理由）

  task4\  第四题（选做）Redis Pipeline 与性能比较
    task4_pipeline.py   逐条写入与普通 Pipeline 分批写入、计时、完整性核验、尾批校验
    result_task4.txt    运行结果
    说明.md             简短说明

四、执行顺序
  1) 启动 MongoDB 副本集（27018）与 Redis Cluster（7000~7005）
  2) cd task1 && python task1_init.py && python task1_business.py
  3) cd task2 && python task2_order.py
  4) cd task3 && python task3_redis.py
  5) cd task4 && python task4_pipeline.py

五、说明
  · 所有键均使用前缀 exam:12403030110:，数据库名为 exam_12403030110，均已替换为本人学号。
  · task1 初始化与业务操作分文件、分步骤执行，业务脚本重复执行不会重建数据。
  · task2 每个场景开始前单独重置 inventory 与 orders，预期值由个人参数计算后与实测比较。
  · task4 每次运行先清理本人方案甲、方案乙的键，不删除其他人的键。
  · 源代码中不含数据库账号、密码等连接凭据。

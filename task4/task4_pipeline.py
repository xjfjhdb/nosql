# -*- coding: utf-8 -*-
"""
task4_pipeline.py —— 第四题（选做）：Redis 逐条写入与普通 Pipeline 分批写入性能对比
个人参数：N = 1000+100C+S = 1010，每批最多 Q = 100
方案甲：键 exam:<SID>:seq:<i>，逐条写入，每条收到返回后才发下一条，不使用 Pipeline/多线程/异步
方案乙：键 exam:<SID>:pipe:<i>，普通 Pipeline（transaction=False），每批最多 100 条，
        一批执行并取得全部结果后再提交下一批，最后不足 100 条的批次单独处理
运行：python task4_pipeline.py（Redis Cluster 节点 127.0.0.1:7000~7002）
"""
import math
import time
from redis.cluster import RedisCluster, ClusterNode

SID = "12403030110"
S = int(SID[-2:])
A = S % 3                  # 1
B = S % 4                  # 2
C = S % 5                  # 0

N = 1000 + 100 * C + S     # 1010
Q = 100                    # 每批最多 100 条
BATCHES = math.ceil(N / Q)  # 11
LAST_BATCH = N - (BATCHES - 1) * Q   # 10

PREFIX = "exam:" + SID + ":"
SEQ_PREFIX = PREFIX + "seq:"
PIPE_PREFIX = PREFIX + "pipe:"

r = RedisCluster(
    startup_nodes=[ClusterNode("127.0.0.1", 7000), ClusterNode("127.0.0.1", 7001)],
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=5,
)

LINE = "=" * 72


def cleanup(match):
    n = 0
    for k in r.scan_iter(match=match, count=500):
        r.delete(k)
        n += 1
    return n


def scheme_a():
    """方案甲：逐条写入，每条命令收到返回后再发送下一条"""
    start = time.perf_counter()
    for i in range(1, N + 1):
        r.set("%s%d" % (SEQ_PREFIX, i), "value-%s-%d" % (SID, i))   # 同步等待本条回复
    return (time.perf_counter() - start) * 1000


def scheme_b():
    """方案乙：普通 Pipeline 分批写入（transaction=False），尾批不足 Q 条单独处理"""
    start = time.perf_counter()
    for start_idx in range(1, N + 1, Q):
        end_idx = min(start_idx + Q - 1, N)
        pipe = r.pipeline(transaction=False)
        for i in range(start_idx, end_idx + 1):
            pipe.set("%s%d" % (PIPE_PREFIX, i), "value-%s-%d" % (SID, i))
        pipe.execute()      # 取得本批全部回复后才进入下一批
    return (time.perf_counter() - start) * 1000


def verify(match, prefix_name):
    count = 0
    for _ in r.scan_iter(match=match, count=500):
        count += 1
    samples = [1, Q, Q + 1, N]
    bad = []
    for i in samples:
        if r.get("%s%d" % (prefix_name, i)) != "value-%s-%d" % (SID, i):
            bad.append(i)
    return count, samples, bad


print(LINE)
print("个人参数：S=%d  A=%d  B=%d  C=%d" % (S, A, B, C))
print("N = 1000+100C+S = %d，每批最多 Q = %d" % (N, Q))
print("Pipeline 批次数 = ceil(%d/%d) = %d，最后一批数量 = %d" % (N, Q, BATCHES, LAST_BATCH))
print("键前缀：%s" % PREFIX)
print(LINE)

# 写入前先清理本人方案甲、方案乙的键（不影响其他键）
cleanup(SEQ_PREFIX + "*")
cleanup(PIPE_PREFIX + "*")

print("\n【1】方案甲（逐条写入）、方案乙（普通 Pipeline 分批写入）实现完成，开始计时运行")

rounds = 3
a_times = []
b_times = []
for rd in range(1, rounds + 1):
    cleanup(SEQ_PREFIX + "*")
    a_ms = scheme_a()

    cleanup(PIPE_PREFIX + "*")
    b_ms = scheme_b()

    a_times.append(a_ms)
    b_times.append(b_ms)
    print("  第 %d 次测量：方案甲 %.2f ms，方案乙 %.2f ms，加速比 %.1f 倍"
          % (rd, a_ms, b_ms, a_ms / b_ms))

a_avg = sum(a_times) / len(a_times)
b_avg = sum(b_times) / len(b_times)

print("\n【2】计时与结果输出")
print("  ---- 表格数据 ----")
print("  命令总数            : %d（两种方案各自写入 %d 条）" % (N, N))
print("  Pipeline 批次数      : %d" % BATCHES)
print("  最后一批数量        : %d" % LAST_BATCH)
print("  方案甲耗时(ms)      : %.2f（3 次平均，单次：%s）"
      % (a_avg, " / ".join("%.2f" % t for t in a_times)))
print("  方案乙耗时(ms)      : %.2f（3 次平均，单次：%s）"
      % (b_avg, " / ".join("%.2f" % t for t in b_times)))
print("  加速比              : %.1f 倍" % (a_avg / b_avg))

print("\n  ---- 数据完整性核验 ----")
a_count, a_samples, a_bad = verify(SEQ_PREFIX + "*", SEQ_PREFIX)
b_count, b_samples, b_bad = verify(PIPE_PREFIX + "*", PIPE_PREFIX)
print("  方案甲：键数量 = %d（预期 %d）%s；抽样键 %s 值校验%s"
      % (a_count, N, "一致" if a_count == N else "不一致", a_samples,
         "全部正确" if not a_bad else "错误键 %s" % a_bad))
print("  方案乙：键数量 = %d（预期 %d）%s；抽样键 %s 值校验%s（含尾批第 %d 条）"
      % (b_count, N, "一致" if b_count == N else "不一致", b_samples,
         "全部正确" if not b_bad else "错误键 %s" % b_bad, N))
print("  尾批校验：第 %d 条键值 = %s（最后一批共 %d 条命令已全部执行）"
      % (N, r.get("%s%d" % (PIPE_PREFIX, N)), LAST_BATCH))

print("\n  ---- 结论 ----")
if b_avg < a_avg:
    print("  Pipeline 更快。方案甲每条命令都要经历一次完整的往返（RTT：等待服务端处理并读回回复），"
          "%d 条命令即 %d 次往返；方案乙把最多 %d 条命令合并成一个批次一次性发送，"
          "只在批末等待一次回复，往返次数从 %d 次降到 %d 次，因此耗时显著降低。"
          % (N, N, Q, N, BATCHES))
else:
    print("  本次测量 Pipeline 未表现出优势。")
print("  若差异不明显甚至 Pipeline 更慢，可能的原因：")
print("    1) 本机 127.0.0.1 客户端与服务端同机，单次 RTT 本身只有几十微秒，"
          "省下的往返时间被命令行构造、结果解析等开销摊薄；")
print("    2) 数据量为 %d 条、单键体积很小，绝对时间只有毫秒级，测量噪声占比大；" % N)
print("    3) 集群模式下 Pipeline 需要按槽位拆分到不同节点，客户端在批次构建与结果聚合上额外付出开销；")
print("    4) 服务端为单线程处理，一次收到大批命令时排队执行，端到端时延不一定线性缩短；")
print("    5) 首次连接、连接池扩容、GC 等一次性开销也会影响单次测量结果。")

print("\n" + LINE)
print("第四题执行完毕")

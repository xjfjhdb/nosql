# -*- coding: utf-8 -*-
"""
task2_order.py —— 第二题：MongoDB 原子扣减与事务验证
内容：① 单文档原子扣减函数  ② 扣减结果分类  ③ 事务订购函数（含 forceError）
      ④ T1~T4 场景测试（每个场景独立重置数据、按个人参数计算预期值并核验）  ⑤ 结果解释

个人参数：SID=12403030110，S=10，A=1，C=0
          Stock = 5+C = 5      Buy = 1+A = 2
运行：python task2_order.py
"""
import os
import sys
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError

SID = "12403030110"
S = int(SID[-2:])
A = S % 3                  # 1
B = S % 4                  # 2
C = S % 5                  # 0

STOCK_INIT = 5 + C          # 5
BUY = 1 + A                 # 2
BOOK_ID = "BOOK-" + SID
URI = os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27018/?replicaSet=rs0")

client = MongoClient(URI, serverSelectionTimeoutMS=5000)
exam_db = client["exam_" + SID]
inventory = exam_db["inventory"]
orders = exam_db["orders"]

LINE = "=" * 72


class OrderAborted(Exception):
    """forceError=true 时主动抛出的业务异常"""
    pass


# ---------------------------------------------------------------
# 数据重置：库存与订单各自重置，场景之间互不影响
# ---------------------------------------------------------------
def reset_data(initial_stock):
    inventory.delete_many({})
    orders.delete_many({})
    inventory.insert_one({"_id": BOOK_ID, "title": "NoSQL数据库教材", "stock": initial_stock})


def current_stock():
    doc = inventory.find_one({"_id": BOOK_ID})
    return None if doc is None else doc["stock"]


# ---------------------------------------------------------------
# ① 原子扣减：条件检查与扣减合并为一次单文档更新
# ---------------------------------------------------------------
def deduct_stock(session, quantity):
    """
    一次 find_one_and_update 同时筛选教材编号和库存条件：
      filter = {_id: 教材编号, stock: {$gte: 购买量}}
      update = {$inc: {stock: -购买量}}
    返回扣减后的库存文档；返回 None 表示条件不满足（未扣减）。
    """
    return inventory.find_one_and_update(
        {"_id": BOOK_ID, "stock": {"$gte": quantity}},
        {"$inc": {"stock": -quantity}},
        return_document=ReturnDocument.AFTER,
        session=session,
    )


# ---------------------------------------------------------------
# ② 按数据库返回结果分类（不靠“程序走到哪一行”判断）
# ---------------------------------------------------------------
def deduct_once(quantity):
    """单次扣减并返回分类结果，用于题目第 2 小问"""
    with client.start_session() as session:
        session.start_transaction()
        doc = deduct_stock(session, quantity)
        if doc is None:
            existed = inventory.find_one({"_id": BOOK_ID}, session=session) is not None
            session.abort_transaction()
            if not existed:
                return {"status": "NOT_FOUND", "detail": "教材不存在，未扣减", "doc": None}
            return {"status": "INSUFFICIENT", "detail": "库存不足，条件不满足，未扣减", "doc": None}
        session.commit_transaction()
        return {"status": "SUCCESS", "detail": "扣减成功，库存变为 %d" % doc["stock"], "doc": doc}


# ---------------------------------------------------------------
# ③ 事务订购：库存扣减与订单插入同一事务、同一会话
# ---------------------------------------------------------------
def place_order(request_id, force_error=False, quantity=BUY):
    with client.start_session() as session:
        try:
            session.start_transaction()

            # 事务内做原子扣减
            doc = deduct_stock(session, quantity)
            if doc is None:
                existed = inventory.find_one({"_id": BOOK_ID}, session=session) is not None
                session.abort_transaction()
                if not existed:
                    return {"status": "NOT_FOUND", "requestId": request_id,
                            "detail": "教材不存在，事务已中止，未生成订单"}
                return {"status": "INSUFFICIENT", "requestId": request_id,
                        "detail": "库存不足，事务已中止，未生成订单"}

            # 扣减成功之后、订单插入之前，按 forceError 主动抛异常
            if force_error:
                raise OrderAborted("forceError=true：库存已扣减(%d)，订单插入前主动抛出异常" % doc["stock"])

            orders.insert_one({
                "_id": request_id,
                "bookId": BOOK_ID,
                "studentId": SID,
                "quantity": quantity,
            }, session=session)

            session.commit_transaction()   # 提交成功后才返回成功
            return {"status": "SUCCESS", "requestId": request_id,
                    "detail": "事务提交成功，库存 %d，订单 %s" % (doc["stock"], request_id)}
        except OrderAborted as e:
            if session.in_transaction:
                session.abort_transaction()
            return {"status": "ABORTED", "requestId": request_id, "detail": "已回滚：%s" % e}
        except PyMongoError as e:
            if session.in_transaction:
                try:
                    session.abort_transaction()
                except PyMongoError:
                    pass
            return {"status": "DB_ERROR", "requestId": request_id, "detail": "数据库执行异常：%s" % e}


# ---------------------------------------------------------------
# ④ 场景测试
# ---------------------------------------------------------------
def run_scenario(name, initial_stock, attempts, force_error=False):
    reset_data(initial_stock)

    success = 0
    fail = 0
    for i in range(1, attempts + 1):
        request_id = "%s-%s-%02d" % (name, SID, i)
        r = place_order(request_id, force_error=force_error)
        print("    第 %d 次订购 %s -> %s：%s" % (i, request_id, r["status"], r["detail"]))
        if r["status"] == "SUCCESS":
            success += 1
        else:
            fail += 1

    final_stock = current_stock()
    final_orders = orders.count_documents({})

    # 用个人参数模拟预期值（不写死结果）
    exp_stock = initial_stock
    exp_success = 0
    exp_fail = 0
    for _ in range(attempts):
        enough = exp_stock >= BUY
        if force_error:
            exp_fail += 1                      # 异常回滚，库存不变，订单不生成
        elif enough:
            exp_success += 1
            exp_stock -= BUY
        else:
            exp_fail += 1
    exp_orders = exp_success

    passed = (success == exp_success and fail == exp_fail
              and final_stock == exp_stock and final_orders == exp_orders)

    print("    ---- 场景 %s 输出 ----" % name)
    print("    （1）场景编号      : %s" % name)
    print("    （2）初始库存      : %d" % initial_stock)
    print("    （3）购买数量      : %d" % BUY)
    print("    （4）成功次数      : %d" % success)
    print("    （5）失败次数      : %d" % fail)
    print("    （6）最终库存      : %s" % final_stock)
    print("    （7）最终订单数量  : %d" % final_orders)
    print("    （8）核验结果      : %s（预期 成功%d/失败%d/库存%d/订单%d）"
          % ("通过" if passed else "不通过", exp_success, exp_fail, exp_stock, exp_orders))
    return passed


def main():
    print(LINE)
    print("个人参数：S=%d  A=%d  B=%d  C=%d" % (S, A, B, C))
    print("Stock = 5+C = %d      Buy = 1+A = %d" % (STOCK_INIT, BUY))
    print("个人数据库：exam_%s   库存文档 _id=%s" % (SID, BOOK_ID))
    print("MongoDB：%s" % URI)
    print(LINE)

    print("\n【1】实现原子扣减（条件筛选 + $inc 合并为一次单文档更新）")
    reset_data(STOCK_INIT)
    r = place_order("DEMO-%s-01" % SID)
    print("单次正常订购 -> %s：%s" % (r["status"], r["detail"]))
    print("对应扣减语句：find_one_and_update({_id:%s, stock:{$gte:%d}}, {$inc:{stock:-%d}}) -> 返回文档 stock=%s（扣减后）"
          % (BOOK_ID, BUY, BUY, current_stock()))

    print("\n【2】按数据库返回结果判断操作结果（三种情形的实际返回）")
    reset_data(STOCK_INIT)
    res = deduct_once(BUY)
    print("  a) 库存充足：返回文档 stock=%s -> %s（%s）"
          % (res["doc"] and res["doc"]["stock"], res["status"], res["detail"]))
    reset_data(BUY - 1)
    res = deduct_once(BUY)
    print("  b) 库存不足：返回 None -> %s（%s）" % (res["status"], res["detail"]))
    reset_data(STOCK_INIT)
    inventory.delete_many({})
    res = deduct_once(BUY)
    print("  c) 教材不存在：返回 None -> %s（%s）" % (res["status"], res["detail"]))
    try:
        bad = MongoClient("mongodb://127.0.0.1:27099/?serverSelectionTimeoutMS=800",
                          serverSelectionTimeoutMS=800)
        bad["exam_" + SID]["inventory"].find_one_and_update(
            {"_id": BOOK_ID, "stock": {"$gte": BUY}}, {"$inc": {"stock": -BUY}})
        print("  d) 数据库异常：未捕获异常（不预期）")
    except PyMongoError as e:
        print("  d) 数据库执行异常：捕获 %s -> DB_ERROR（%s）" % (type(e).__name__, str(e)[:90]))

    print("\n【3】事务订购函数 place_order(requestId, forceError) 已实现："
          "同一会话同一事务，扣减失败不生成订单，正常提交，异常回滚，提交成功后才返回成功")

    print("\n【4】系统测试（每个场景单独重置 inventory 与 orders）")
    results = []
    attempts_t1 = 1
    attempts_t2 = 1
    attempts_t3 = 1
    attempts_t4 = STOCK_INIT // BUY + 1          # ⌊Stock/Buy⌋+1 = 3

    print("\n  T1 正常订购：初始库存 %d，执行 1 次正常订购" % STOCK_INIT)
    results.append(("T1", run_scenario("T1", STOCK_INIT, attempts_t1)))
    print("\n  T2 库存不足：初始库存 Buy-1 = %d，执行 1 次正常订购" % (BUY - 1))
    results.append(("T2", run_scenario("T2", BUY - 1, attempts_t2)))
    print("\n  T3 中途异常：初始库存 %d，forceError=true" % STOCK_INIT)
    results.append(("T3", run_scenario("T3", STOCK_INIT, attempts_t3, force_error=True)))
    print("\n  T4 连续购买：初始库存 %d，连续发起 ⌊%d/%d⌋+1 = %d 次正常订购"
          % (STOCK_INIT, STOCK_INIT, BUY, attempts_t4))
    results.append(("T4", run_scenario("T4", STOCK_INIT, attempts_t4)))

    print("\n【4-汇总】")
    all_pass = True
    for name, ok in results:
        print("  %s 核验：%s" % (name, "通过" if ok else "不通过"))
        all_pass = all_pass and ok
    print("  四个场景总体核验：%s" % ("全部通过" if all_pass else "存在不通过项"))

    print("\n【5】结果解释")
    print("（1）为什么单次扣减具有原子性，仍然需要事务？")
    print("    单文档 find_one_and_update 只能保证“库存检查+扣减”这一文档不被并发撕开，"
          "但业务要求“库存扣减”与“订单插入”是两个文档、两个集合的两次写操作。"
          "若没有事务，扣减成功后进程崩溃、网络超时或订单插入失败，就会出现“扣了库存却没有订单”的不一致状态；"
          "事务把两次写放进同一会话的同一事务，要么一起提交，要么一起回滚，"
          "从而保证跨文档操作的原子性与一致性（同时事务还提供快照隔离，避免读到中间态）。")
    print("（2）forceError 测试验证了什么？")
    print("    T3 在库存扣减成功之后、订单插入之前主动抛异常，最终库存仍为初始值、订单数为 0，"
          "证明事务确实回滚了已经执行的扣减，而不是只回滚了报错之后的语句；"
          "它验证了“全部成功或全部不生效”的跨文档一致性，也验证了程序只在 commit 成功后才报告订购成功——"
          "若把扣减写成事务外操作，同样的异常会留下库存被扣而订单缺失的脏数据。")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

# 批发订单管理系统 (Wholesale ERP)

## 项目概述

为女鞋工厂开发的批发订单管理系统，用于管理多家批发客户的订单、发货和物流跟踪。替代腾讯文档"批发总表"，实现在线多设备操作。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.x + Flask 3.0 + SQLAlchemy ORM |
| 数据库 | SQLite (`erp.db`) |
| 前端 | Bootstrap 5 + Jinja2 模板 |
| 部署 | PythonAnywhere (免费版, 用户名 Xtttt) |

## 项目结构

```
wholesale-erp/
├── app.py              # Flask 主应用 (~700行)
├── erp.db              # SQLite 数据库 (生产数据)
├── requirements.txt    # Python 依赖
├── wsgi.py             # PythonAnywhere WSGI 入口
├── sync_v2.py          # 数据同步脚本 (腾讯文档 → 数据库)
├── PROJECT.md          # 本文件
└── templates/
    ├── dashboard.html  # 首页概览 (仪表盘)
    ├── orders.html     # 订单列表 + 矩阵总览
    ├── customers.html  # 客户列表
    ├── shipments.html  # 发货记录
    ├── products.html   # 产品管理
    └── ...
```

## 数据库设计

### 核心表

| 表 | 说明 | 关键字段 |
|----|------|----------|
| `customers` | 客户 | id, name |
| `products` | 产品 | id, name, is_active |
| `product_colors` | 产品颜色 | product_id, color_name, sort_order |
| `product_sizes` | 产品尺码 | product_id, size_name, sort_order |
| `orders` | 订单 | customer_id, total_qty, total_shipped |
| `order_lines` | 订单明细 | order_id, batch, color, size, qty, shipped_qty |
| `shipments` | 发货记录 | order_id, ship_date, notes, logistics_company, tracking_number |
| `ship_details` | 发货明细 | shipment_id, order_line_id, color, size, qty |

### 关键逻辑

- **订单分批**: `order_lines.batch` 区分同客户不同批次
- **部分发货**: `order_lines.shipped_qty` 跟踪每个 color×size 已发数量
- **存储型合计**: `orders.total_qty` / `total_shipped` 是数据库列而非计算属性，避免 detached instance 问题
- **刷新合计**: `refresh_totals()` 在每次 `db.session.commit()` 前调用

## 当前产品

**2603人字拖**, 8色 (巧克力/深棕/芒果棕/米白/陶土棕/红/黄/黑), 6码 (36-41)

## 数据快照 (2026-05-22)

共 14 家客户：

| 客户 | 总订单 | 已发货 | 待发货 |
|------|--------|--------|--------|
| 拿版 | 3 | 3 | 0 |
| 足矣韩版女鞋 | 30 | 30 | 0 |
| 朱朱 | 18 | 18 | 0 |
| omi | 11 | 11 | 0 |
| 余宝藏 | 3 | 3 | 0 |
| 知足鞋店 | 32 | 30 | 2 |
| canis lupus | 22 | 12 | 10 |
| 4U | 30 | 12 | 18 |
| 私人衣橱 | 28 | 17 | 11 |
| 彤彤 | 66 | 39 | 27 |
| 晶晶工作室 | 54 | 36 | 18 |
| 树 | 46 | 0 | 46 |
| 丹姐 | 26 | 0 | 26 |
| UP2 | 30 | 0 | 30 |
| **合计** | **399** | **211** | **188** |

## 页面功能

### 首页仪表盘
- 4 张统计卡片: 客户数(可点击跳转)、订单数(可点击跳转)、已发货(可点击弹出全局矩阵)、待发货(可点击弹出全局矩阵)
- 矩阵弹窗: 所有客户汇总的 color×size 矩阵，含行列总计

### 订单管理
- 订单列表 + "矩阵总览" 展开按钮
- 每订单展示每个 color×size 的 "订X/发Y" 详情
- 发货操作: 逐 SKU 填发货数量，创建发货记录

### 客户管理
- 客户列表 + 每个客户的订单/发货矩阵

## 部署信息

| 项目 | 详情 |
|------|------|
| GitHub | `git@ssh.github.com:Xtttt/wholesale-erp.git` (端口 443) |
| 推送命令 | `GIT_SSH_COMMAND="ssh -p 443" git push` |
| PythonAnywhere | 用户名 Xtttt, 域名 Xtttt.pythonanywhere.com (未完成部署) |

## 开发注意事项

1. **数据库备份**: `erp.db` 是唯一数据源，务必定期备份
2. **颜色统一**: 使用中文全称 (巧克力/深棕/芒果棕/米白/陶土棕/红/黄/黑)
3. **尺码格式**: 字符串类型 "36"-"41"
4. **SSH 端口**: 沙箱环境端口 22 被封，须用 `ssh.github.com:443`
5. **PythonAnywhere**: 免费版需每 3 个月登录一次续期
6. **发货更新**: 务必同时更新 `ship_details`、`order_lines.shipped_qty`、`orders.total_shipped` 三处

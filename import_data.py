"""从腾讯文档批发总表导入数据到 ERP 系统"""
import sys
sys.path.insert(0, '/workspace/wholesale-erp')

from app import app, db
from models import Customer, Product, ProductColor, ProductSize, Order, OrderLine, Shipment, ShipDetail
from datetime import datetime

COLORS_LIST = ['巧克力', '深棕', '芒果棕', '米白', '陶土棕', '红', '黄', '黑']
SIZES_LIST = ['36', '37', '38', '39', '40', '41']

# ============ 原始数据 ============
# 每个客户：{unit_price, orders: {color: {size: qty}}, shipped: {color: {size: qty}}, ship_date}

CUSTOMER_DATA = {
    'omi': {
        'unit_price': 55,
        'orders': {'巧克力': {36:1,37:2}, '米白': {36:2,37:1}, '陶土棕': {36:3,37:1,38:1}},
        'shipped': {'巧克力': {36:1,37:2}, '米白': {36:2,37:1}, '陶土棕': {36:3,37:1,38:1}},
        'ship_date': '2026-04-01',
    },
    '彤彤': {
        'unit_price': 0,
        'orders': {
            '巧克力': {36:3,37:3,38:3,39:2}, '米白': {36:3,37:3,38:3,39:2},
            '陶土棕': {36:3,37:3,38:3,39:2}, '红': {36:3,37:3,38:3,39:2},
            '黄': {36:3,37:3,38:3,39:2}, '黑': {36:3,37:3,38:3,39:2},
        },
        'shipped': {'陶土棕': {36:3,37:3,38:3,39:2}, '黄': {36:3,37:3,38:3,39:2}},
        'ship_date': '2026-04-15',
    },
    '朱朱': {
        'unit_price': 55,
        'orders': {
            '巧克力': {36:2,37:3,38:2,39:1},
            '米白': {36:3,37:3,38:2,39:1},
            '陶土棕': {38:1},
        },
        'shipped': {
            '巧克力': {36:2,37:3,38:2,39:1},
            '米白': {36:3,37:3,38:2,39:1},
            '陶土棕': {38:1},
        },
        'ship_date': '2026-04-27',
    },
    '足矣韩版女鞋': {
        'unit_price': 39,
        'orders': {
            '巧克力': {36:1,37:1,38:1,39:1,40:1},
            '芒果棕': {36:2,37:2,38:2,39:2,40:2},
            '米白': {36:1,37:1,38:1,39:1,40:1},
            '陶土棕': {36:1,37:1,38:1,39:1,40:1},
            '红': {36:1,37:1,38:1,39:1,40:1},
        },
        'shipped': {
            '巧克力': {36:1,37:1,38:1,39:1,40:1},
            '芒果棕': {36:2,37:2,38:2,39:2,40:2},
            '米白': {36:1,37:1,38:1,39:1,40:1},
            '陶土棕': {36:1,37:1,38:1,39:1,40:1},
            '红': {36:1,37:1,38:1,39:1,40:1},
        },
        'ship_date': '2026-04-20',
    },
    '余宝藏': {
        'unit_price': 0,
        'orders': {'巧克力': {37:1}, '米白': {37:1}, '红': {37:1}},
        'shipped': {},
        'ship_date': None,
    },
    '晶晶工作室': {
        'unit_price': 0,
        'orders': {
            '巧克力': {36:15,37:5,38:10,39:2,40:3},
            '米白': {36:2,37:4,38:1},
            '红': {37:1,38:1},
            '黄': {36:1,37:1},
            '黑': {36:1,37:3,38:1,39:1,40:2},
        },
        'shipped': {'米白': {37:1}, '红': {37:1}, '黄': {37:1}, '黑': {37:1}},
        'ship_date': '2026-05-01',
    },
    '拿版': {
        'unit_price': 55,
        'orders': {'巧克力': {38:1}, '芒果棕': {37:1}, '米白': {36:1}},
        'shipped': {'巧克力': {38:1}, '芒果棕': {37:1}, '米白': {36:1}},
        'ship_date': '2026-04-10',
    },
    '4U': {
        'unit_price': 0,
        'orders': {
            '巧克力': {36:2,37:2},
            '米白': {36:3,37:4,38:2},
            '陶土棕': {36:1,38:1},
            '黄': {36:3,38:2,39:1,40:1},
            '黑': {36:2,37:1,38:3,40:1},
        },
        'shipped': {
            '巧克力': {36:2,37:1},
            '陶土棕': {36:1,38:1},
            '黄': {36:3,38:2,39:1,40:1},
            '黑': {36:1,37:1},
        },
        'ship_date': '2026-05-05',
    },
    'canis lupus': {
        'unit_price': 55,
        'orders': {
            '巧克力': {36:1,37:3,38:1,39:1,40:2},
            '黑': {36:1,37:3,38:2,40:1},
        },
        'shipped': {
            '巧克力': {36:1,37:3,38:1,39:1,40:1},
            '黑': {36:1,37:2,38:1,40:1},
        },
        'ship_date': '2026-05-10',
    },
    '私人衣橱': {
        'unit_price': 0,
        'orders': {
            '巧克力': {36:2,37:2,38:2},
            '米白': {36:2,37:3,38:2},
            '红': {36:5,37:8,38:5,39:1},
            '黑': {36:7,37:10,38:8,39:1},
        },
        'shipped': {},
        'ship_date': None,
    },
    '树': {
        'unit_price': 0,
        'orders': {
            '巧克力': {36:2,37:6,38:3,39:2,40:1},
            '米白': {36:2,37:2,38:2,39:2},
            '陶土棕': {36:2,37:2,38:2,39:2},
            '红': {36:1,37:1,38:1,39:1},
            '黄': {36:1,37:1,38:1,39:1},
            '黑': {36:2,37:2,38:2,39:2},
        },
        'shipped': {},
        'ship_date': None,
    },
    '知足鞋店': {
        'unit_price': 39,
        'orders': {
            '巧克力': {36:2,37:2,38:1,39:1},
            '深棕': {36:2,37:2,38:1,39:1},
            '芒果棕': {36:2,37:2,38:1,39:1},
            '米白': {36:2,37:2,38:1,39:1},
            '陶土棕': {36:2,37:2,38:1,39:1},
            '红': {38:1,39:1},
        },
        'shipped': {
            '巧克力': {36:2,37:2,38:1,39:1},
            '深棕': {36:2,37:2,38:1,39:1},
            '芒果棕': {36:2,37:2,38:1,39:1},
            '米白': {36:2,37:2,38:1,39:1},
            '陶土棕': {36:2,37:2,38:1,39:1},
        },
        'ship_date': '2026-05-12',
    },
}


def import_data():
    with app.app_context():
        # 确保产品存在
        product = Product.query.filter_by(name='2603人字拖').first()
        if not product:
            print("❌ 产品不存在，请先初始化")
            return

        colors = {c.name: c for c in product.colors.all()}
        sizes_set = {s.size_label for s in product.sizes.all()}

        total_imported = 0
        errors = []

        for customer_name, data in CUSTOMER_DATA.items():
            try:
                # 创建或获取客户
                customer = Customer.query.filter_by(name=customer_name).first()
                if not customer:
                    customer = Customer(
                        name=customer_name,
                        unit_price=data['unit_price'],
                    )
                    db.session.add(customer)
                    db.session.flush()
                else:
                    customer.unit_price = data['unit_price']

                # 生成订单号
                order_count = Order.query.count()
                order_number = f"WH-IMP-{order_count + 1:03d}"

                order = Order(
                    customer_id=customer.id,
                    product_id=product.id,
                    order_number=order_number,
                    unit_price=data['unit_price'],
                    status='pending',
                    notes=f'从腾讯文档导入 - {customer_name}',
                )
                db.session.add(order)
                db.session.flush()

                # 导入订单明细
                total_qty = 0
                for color_name, size_dict in data['orders'].items():
                    if color_name not in colors:
                        print(f"  ⚠️ 未知颜色 '{color_name}' in {customer_name}，跳过")
                        continue
                    for size_label, qty in size_dict.items():
                        size_label = str(size_label)
                        if size_label not in sizes_set:
                            print(f"  ⚠️ 未知尺码 '{size_label}' in {customer_name}，跳过")
                            continue
                        line = OrderLine(
                            order_id=order.id,
                            batch=1,
                            color=color_name,
                            size=size_label,
                            qty=qty,
                        )
                        db.session.add(line)
                        total_qty += qty

                order.refresh_totals()

                # 导入发货数据
                if data['shipped']:
                    ship_date = datetime.strptime(data['ship_date'], '%Y-%m-%d') if data['ship_date'] else datetime.utcnow()
                    shipment = Shipment(
                        order_id=order.id,
                        ship_date=ship_date,
                        notes=f'从腾讯文档导入 - {customer_name} 历史发货',
                    )
                    db.session.add(shipment)
                    db.session.flush()

                    total_shipped = 0
                    for color_name, size_dict in data['shipped'].items():
                        for size_label, ship_qty in size_dict.items():
                            size_label = str(size_label)
                            if ship_qty <= 0:
                                continue
                            # 找到对应的 order_line
                            order_line = OrderLine.query.filter_by(
                                order_id=order.id, color=color_name, size=size_label
                            ).first()
                            if not order_line:
                                print(f"  ⚠️ 找不到 {color_name} {size_label} 的订单行 ({customer_name})")
                                continue

                            detail = ShipDetail(
                                shipment_id=shipment.id,
                                order_line_id=order_line.id,
                                color=color_name,
                                size=size_label,
                                qty=ship_qty,
                            )
                            db.session.add(detail)
                            order_line.shipped_qty = ship_qty
                            total_shipped += ship_qty

                    order.refresh_totals()

                    # 更新订单状态
                    if order.total_pending <= 0:
                        order.status = 'completed'
                    else:
                        order.status = 'partial'

                elif order.total_qty == 0:
                    # 无订单数据，删除空订单
                    db.session.delete(order)
                    db.session.flush()
                    print(f"  ⏭️ 跳过空客户: {customer_name}")
                    continue

                db.session.commit()
                print(f"✅ {customer_name}: 订{order.total_qty}双, 发{order.total_shipped}双, 待{order.total_pending}双")
                total_imported += 1

            except Exception as e:
                db.session.rollback()
                errors.append(f"❌ {customer_name}: {e}")
                print(f"❌ {customer_name}: {e}")

        print(f"\n{'='*50}")
        print(f"导入完成：{total_imported}/{len(CUSTOMER_DATA)} 个客户")

        if errors:
            print(f"错误：{len(errors)} 个")
            for e in errors:
                print(f"  {e}")

        # 打印汇总
        all_orders = Order.query.all()
        total_qty = sum(o.total_qty for o in all_orders)
        total_shipped = sum(o.total_shipped for o in all_orders)
        total_pending = sum(o.total_pending for o in all_orders)
        print(f"\n📊 系统汇总: 总订{total_qty}双, 已发{total_shipped}双, 待发{total_pending}双")
        print(f"📊 腾讯文档: 2603人字拖 总订365双, 已发144双, 待发221双")


if __name__ == '__main__':
    import_data()

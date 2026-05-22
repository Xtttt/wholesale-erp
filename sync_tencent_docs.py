"""从腾讯文档最新数据同步到数据库"""
import sys
sys.path.insert(0, '/workspace/wholesale-erp')

from app import app, db
from models import Customer, Product, ProductColor, ProductSize, Order, OrderLine, Shipment, ShipDetail
from datetime import datetime

# ======== 腾讯文档最新数据 (2026-05-22) ========
# 格式: {customer_name: {unit_price, orders: {color: {size: qty}}, shipped: {color: {size: qty}}, ship_date}}
# 只包含有变化的客户，不变化的不列

UPDATES = {
    # === 余宝藏：ERP里已发0→腾讯文档已发3 ===
    '余宝藏': {
        'unit_price': None,  # 不修改单价
        'orders': {'巧克力': {37: 1}, '米白': {37: 1}, '红': {37: 1}},
        'shipped': {'巧克力': {37: 1}, '米白': {37: 1}, '红': {37: 1}},
        'ship_date': '2026-05-01',
    },
    # === canis lupus: ERP订15→腾讯文档订22 (+7), 已发12→12 ===
    'canis lupus': {
        'unit_price': 55,
        'orders': {
            '巧克力': {36: 1, 37: 5, 38: 1, 39: 3, 40: 2},
            '黑': {36: 2, 37: 4, 38: 3, 40: 1},
        },
        'shipped': {
            '巧克力': {36: 1, 37: 3, 38: 1, 39: 1, 40: 1},
            '黑': {36: 1, 37: 2, 38: 1, 40: 1},
        },
        'ship_date': '2026-05-10',
    },
    # === 4U: ERP已发14→腾讯文档已发12 ===
    # ⚠️ 腾讯文档含数据异常：红36发货1但订单无红36，已修正为红37发货1
    '4U': {
        'unit_price': None,
        'orders': {
            '巧克力': {36: 1, 37: 2, 38: 1},
            '米白': {36: 1, 37: 5, 38: 3},
            '陶土棕': {36: 1, 38: 1},
            '红': {37: 1, 39: 1},
            '黄': {36: 3, 39: 1, 40: 1},
            '黑': {36: 2, 37: 1, 38: 3, 40: 1},
        },
        'shipped': {
            '巧克力': {36: 1, 38: 1},
            '米白': {36: 1, 37: 3},
            '红': {37: 1, 39: 1},
            '黄': {39: 1, 40: 1},
            '黑': {36: 2},
        },
        'ship_date': '2026-05-05',
    },
    # === 私人衣橱: ERP订58→腾讯文档订27, 已发0→2 ===
    '私人衣橱': {
        'unit_price': None,
        'orders': {
            '米白': {36: 2, 37: 2, 38: 2},
            '红': {36: 2, 37: 4, 38: 3, 39: 1},
            '黑': {36: 2, 37: 4, 38: 4, 39: 1},
        },
        'shipped': {
            '红': {37: 1},
            '黑': {38: 1},
        },
        'ship_date': '2026-05-15',
    },
}

# === 新增客户 ===
NEW_CUSTOMERS = {
    '丹姐': {
        'unit_price': 39,
        'orders': {
            '米白': {36: 5, 37: 2, 38: 1},
            '陶土棕': {36: 4, 37: 2, 38: 1},
            '红': {36: 1, 37: 1, 38: 1},
            '黑': {36: 3, 37: 2, 38: 2, 40: 1},
        },
        'shipped': {},
        'ship_date': None,
    },
}


def sync_all():
    with app.app_context():
        product = Product.query.filter_by(name='2603人字拖').first()
        if not product:
            print("❌ 产品不存在")
            return

        colors_set = {c.name for c in product.colors.all()}
        sizes_set = {s.size_label for s in product.sizes.all()}

        # ====== 更新已有客户 ======
        for customer_name, data in UPDATES.items():
            customer = Customer.query.filter_by(name=customer_name).first()
            if not customer:
                print(f"❌ 客户 {customer_name} 不存在，跳过")
                continue

            # 更新单价（如果提供了）
            if data['unit_price'] is not None:
                customer.unit_price = data['unit_price']

            # 找到该客户的订单
            order = Order.query.filter_by(customer_id=customer.id).first()
            if not order:
                print(f"❌ {customer_name} 无订单，跳过")
                continue

            old_total = order.total_qty
            old_shipped = order.total_shipped

            # 删除旧数据
            shipments = Shipment.query.filter_by(order_id=order.id).all()
            for s in shipments:
                ShipDetail.query.filter_by(shipment_id=s.id).delete()
                db.session.delete(s)
            OrderLine.query.filter_by(order_id=order.id).delete()
            db.session.flush()

            # 重新导入订单行
            new_total = 0
            for color_name, size_dict in data['orders'].items():
                if color_name not in colors_set:
                    continue
                for size_label, qty in size_dict.items():
                    size_label = str(size_label)
                    if size_label not in sizes_set:
                        continue
                    line = OrderLine(order_id=order.id, batch=1, color=color_name, size=size_label, qty=qty)
                    db.session.add(line)
                    new_total += qty

            order.refresh_totals()

            # 重新导入发货
            new_shipped = 0
            if data['shipped']:
                ship_date = datetime.strptime(data['ship_date'], '%Y-%m-%d') if data['ship_date'] else datetime.utcnow()
                shipment = Shipment(order_id=order.id, ship_date=ship_date, notes=f'同步腾讯文档 - {customer_name}')
                db.session.add(shipment)
                db.session.flush()

                for color_name, size_dict in data['shipped'].items():
                    for size_label, ship_qty in size_dict.items():
                        size_label = str(size_label)
                        if ship_qty <= 0:
                            continue
                        order_line = OrderLine.query.filter_by(
                            order_id=order.id, color=color_name, size=size_label
                        ).first()
                        if not order_line:
                            print(f"  ⚠️ {customer_name}: 找不到 {color_name} {size_label}")
                            continue
                        detail = ShipDetail(shipment_id=shipment.id, order_line_id=order_line.id,
                                           color=color_name, size=size_label, qty=ship_qty)
                        db.session.add(detail)
                        order_line.shipped_qty = ship_qty
                        new_shipped += ship_qty

                order.refresh_totals()

            # 更新状态
            if order.total_pending <= 0:
                order.status = 'completed'
            elif order.total_shipped > 0:
                order.status = 'partial'
            else:
                order.status = 'pending'

            db.session.commit()
            print(f"✅ {customer_name}: 订{old_total}→{new_total}, 发{old_shipped}→{new_shipped}")

        # ====== 新增客户 ======
        for customer_name, data in NEW_CUSTOMERS.items():
            existing = Customer.query.filter_by(name=customer_name).first()
            if existing:
                print(f"⏭️ {customer_name} 已存在，跳过")
                continue

            customer = Customer(name=customer_name, unit_price=data['unit_price'])
            db.session.add(customer)
            db.session.flush()

            order_count = Order.query.count()
            order_number = f"WH-{datetime.utcnow().strftime('%Y%m%d')}-{order_count + 1:03d}"

            order = Order(
                customer_id=customer.id, product_id=product.id,
                order_number=order_number, unit_price=data['unit_price'],
                status='pending', notes=f'从腾讯文档同步 - {customer_name}',
            )
            db.session.add(order)
            db.session.flush()

            new_total = 0
            for color_name, size_dict in data['orders'].items():
                for size_label, qty in size_dict.items():
                    size_label = str(size_label)
                    line = OrderLine(order_id=order.id, batch=1, color=color_name, size=size_label, qty=qty)
                    db.session.add(line)
                    new_total += qty

            order.refresh_totals()

            if data['shipped']:
                # Would handle shipped data here if any
                pass

            db.session.commit()
            print(f"🆕 新增客户 {customer_name}: 订{new_total}双")

        # ====== 最终汇总 ======
        print(f"\n{'='*50}")
        all_orders = Order.query.all()
        t_qty = sum(o.total_qty for o in all_orders)
        t_ship = sum(o.total_shipped for o in all_orders)
        t_pend = sum(o.total_pending for o in all_orders)
        print(f"📊 系统汇总: 总订{t_qty}双, 已发{t_ship}双, 待发{t_pend}双")
        print(f"📊 腾讯文档: 总订433双, 已发193双, 待发240双")

        # 逐客户对比
        print(f"\n📋 逐客户明细:")
        for c in Customer.query.order_by(Customer.name).all():
            orders = Order.query.filter_by(customer_id=c.id).all()
            if orders:
                o = orders[0]
                print(f"  {c.name}: 订{o.total_qty} 发{o.total_shipped} 待{o.total_pending}")


if __name__ == '__main__':
    sync_all()

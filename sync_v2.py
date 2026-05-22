"""腾讯文档最新数据同步 — 2026-05-22 更新"""
import sys
sys.path.insert(0, '/workspace/wholesale-erp')
from app import app, db
from models import Customer, Product, Order, OrderLine, Shipment, ShipDetail
from datetime import datetime

# ======== 2026-05-22 腾讯文档最新数据 ========
# 只列出有变化和新增的客户
UPDATES = {
    # 4U: 黑36订单2→3，发货黄36+1,黑36-1
    '4U': {
        'unit_price': None,
        'orders': {
            '巧克力': {36:1,37:2,38:1},
            '米白': {36:1,37:5,38:3},
            '陶土棕': {36:1,38:1},
            '红': {37:1,39:1},
            '黄': {36:3,39:1,40:1},
            '黑': {36:3,37:1,38:3,40:1},
        },
        'shipped': {
            '巧克力': {36:1,38:1},
            '米白': {36:1,37:3},
            '红': {37:1,39:1},
            '黄': {36:1,39:1,40:1},
            '黑': {36:1},
        },
        'ship_date': '2026-05-05',
    },
    # 私人衣橱: 黑36订单2→3（27→28）
    '私人衣橱': {
        'unit_price': None,
        'orders': {
            '米白': {36:2,37:2,38:2},
            '红': {36:2,37:4,38:3,39:1},
            '黑': {36:3,37:4,38:4,39:1},
        },
        'shipped': {
            '红': {37:1},
            '黑': {38:1},
        },
        'ship_date': '2026-05-15',
    },
}

NEW_CUSTOMERS = {
    'UP2': {
        'unit_price': None,
        'orders': {
            '米白': {36:2,37:3,38:2},
            '红': {36:3,37:4,38:2},
            '黑': {36:4,37:6,38:4},
        },
        'shipped': {},
        'ship_date': None,
    },
}

def sync():
    with app.app_context():
        product = Product.query.filter_by(name='2603人字拖').first()
        sizes_set = {s.size_label for s in product.sizes.all()}

        # ====== 更新已有客户 ======
        for name, data in UPDATES.items():
            c = Customer.query.filter_by(name=name).first()
            if not c:
                print(f"❌ {name} 不存在"); continue
            order = Order.query.filter_by(customer_id=c.id).first()
            if not order:
                print(f"❌ {name} 无订单"); continue

            old_q = order.total_qty; old_s = order.total_shipped
            # 清除旧数据
            for s in Shipment.query.filter_by(order_id=order.id).all():
                ShipDetail.query.filter_by(shipment_id=s.id).delete()
                db.session.delete(s)
            OrderLine.query.filter_by(order_id=order.id).delete()
            db.session.flush()

            # 导入订单
            for co, sd in data['orders'].items():
                for sz, q in sd.items():
                    OrderLine(order_id=order.id, batch=1, color=co, size=str(sz), qty=q)
                    db.session.add(OrderLine(order_id=order.id, batch=1, color=co, size=str(sz), qty=q))
            db.session.flush()
            order.refresh_totals()

            # 导入发货
            if data['shipped']:
                sd_date = datetime.strptime(data['ship_date'], '%Y-%m-%d') if data['ship_date'] else datetime.utcnow()
                shipment = Shipment(order_id=order.id, ship_date=sd_date, notes=f'腾讯文档同步')
                db.session.add(shipment)
                db.session.flush()
                for co, sd_dict in data['shipped'].items():
                    for sz, sq in sd_dict.items():
                        sz = str(sz)
                        if sq <= 0: continue
                        ol = OrderLine.query.filter_by(order_id=order.id, color=co, size=sz).first()
                        if not ol: continue
                        ShipDetail(shipment_id=shipment.id, order_line_id=ol.id, color=co, size=sz, qty=sq)
                        db.session.add(ShipDetail(shipment_id=shipment.id, order_line_id=ol.id, color=co, size=sz, qty=sq))
                        ol.shipped_qty = sq
                order.refresh_totals()

            if order.total_pending <= 0: order.status = 'completed'
            elif order.total_shipped > 0: order.status = 'partial'
            else: order.status = 'pending'
            db.session.commit()
            print(f"✅ {name}: 订{old_q}→{order.total_qty}, 发{old_s}→{order.total_shipped}")

        # ====== 新增客户 ======
        for name, data in NEW_CUSTOMERS.items():
            if Customer.query.filter_by(name=name).first():
                print(f"⏭️ {name} 已存在"); continue

            c = Customer(name=name, unit_price=data['unit_price'] or 0)
            db.session.add(c); db.session.flush()

            n = Order.query.count()
            o = Order(customer_id=c.id, product_id=product.id,
                      order_number=f"WH-{datetime.utcnow().strftime('%Y%m%d')}-{n+1:03d}",
                      unit_price=data['unit_price'] or 0, status='pending',
                      notes=f'腾讯文档同步 - {name}')
            db.session.add(o); db.session.flush()

            total = 0
            for co, sd in data['orders'].items():
                for sz, q in sd.items():
                    OrderLine(order_id=o.id, batch=1, color=co, size=str(sz), qty=q)
                    db.session.add(OrderLine(order_id=o.id, batch=1, color=co, size=str(sz), qty=q))
                    total += q
            o.refresh_totals()
            db.session.commit()
            print(f"🆕 {name}: 订{total}双")

        # ====== 最终验证 ======
        print(f"\n{'='*55}")
        for c in Customer.query.order_by(Customer.name).all():
            orders = Order.query.filter_by(customer_id=c.id).all()
            if not orders: continue
            o = orders[0]
            st = '✅' if o.total_pending==0 else ('🔶' if o.total_shipped>0 else '🔴')
            print(f"  {c.name:12s} | 订{o.total_qty:3d} | 发{o.total_shipped:3d} | 待{o.total_pending:3d} | {st}")
        all_o = Order.query.all()
        tq = sum(o.total_qty for o in all_o)
        ts = sum(o.total_shipped for o in all_o)
        tp = sum(o.total_pending for o in all_o)
        print(f"  {'─'*50}")
        print(f"  合计         | 订{tq:3d} | 发{ts:3d} | 待{tp:3d}")

if __name__ == '__main__':
    sync()

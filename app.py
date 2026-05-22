"""批发订单管理系统 - Flask 应用主文件"""
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from config import Config
from models import db, Customer, Product, ProductColor, ProductSize, Order, OrderLine, Shipment, ShipDetail


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        _seed_default_data()

    return app


def _seed_default_data():
    """初始化默认产品数据"""
    if Product.query.count() == 0:
        product = Product(name='2603人字拖')
        db.session.add(product)
        db.session.flush()

        colors = [
            ('巧克力', '#8B4513'),
            ('深棕', '#5C3317'),
            ('芒果棕', '#C49B5A'),
            ('米白', '#F5F0E1'),
            ('陶土棕', '#B8744B'),
            ('红', '#D43030'),
            ('黄', '#E8C840'),
            ('黑', '#1A1A1A'),
        ]
        sizes = ['36', '37', '38', '39', '40', '41']

        for i, (name, hex_code) in enumerate(colors):
            db.session.add(ProductColor(product_id=product.id, name=name, hex_code=hex_code,
                                         sort_order=i))

        for i, size in enumerate(sizes):
            db.session.add(ProductSize(product_id=product.id, size_label=size,
                                        sort_order=i))

        db.session.commit()


app = create_app()


# ========== 首页仪表盘 ==========

@app.route('/')
def dashboard():
    customers_count = Customer.query.count()
    orders_total = Order.query.count()

    orders = Order.query.all()
    total_qty = sum(o.total_qty for o in orders)
    total_shipped = sum(o.total_shipped for o in orders)
    total_pending = sum(o.total_pending for o in orders)

    # 待处理订单
    pending_orders = [o for o in orders if o.total_pending > 0]
    pending_orders.sort(key=lambda o: o.created_at, reverse=True)

    return render_template('dashboard.html',
                           customers_count=customers_count,
                           orders_total=orders_total,
                           total_qty=total_qty,
                           total_shipped=total_shipped,
                           total_pending=total_pending,
                           pending_orders=pending_orders[:10])


# ========== 客户管理 ==========

@app.route('/customers')
def customer_list():
    customers = Customer.query.order_by(Customer.name).all()
    return render_template('customers.html', customers=customers)


@app.route('/customers/<int:customer_id>')
def customer_detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    orders = customer.orders.order_by(Order.created_at.desc()).all()
    return render_template('customer_detail.html', customer=customer, orders=orders)


@app.route('/customers/add', methods=['GET', 'POST'])
def customer_add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        unit_price = request.form.get('unit_price', '0')
        notes = request.form.get('notes', '').strip()

        if not name:
            flash('客户名不能为空', 'error')
            return redirect(url_for('customer_add'))

        if Customer.query.filter_by(name=name).first():
            flash(f'客户 "{name}" 已存在', 'error')
            return redirect(url_for('customer_add'))

        try:
            unit_price = float(unit_price)
        except ValueError:
            unit_price = 0.0

        customer = Customer(name=name, unit_price=unit_price, notes=notes)
        db.session.add(customer)
        db.session.commit()
        flash(f'客户 "{name}" 添加成功', 'success')
        return redirect(url_for('customer_list'))

    return render_template('customer_form.html', customer=None)


@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
def customer_edit(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        unit_price = request.form.get('unit_price', '0')
        notes = request.form.get('notes', '').strip()

        if not name:
            flash('客户名不能为空', 'error')
            return render_template('customer_form.html', customer=customer)

        existing = Customer.query.filter_by(name=name).first()
        if existing and existing.id != customer_id:
            flash(f'客户 "{name}" 已存在', 'error')
            return render_template('customer_form.html', customer=customer)

        try:
            unit_price = float(unit_price)
        except ValueError:
            unit_price = 0.0

        customer.name = name
        customer.unit_price = unit_price
        customer.notes = notes
        db.session.commit()
        flash(f'客户 "{name}" 更新成功', 'success')
        return redirect(url_for('customer_list'))

    return render_template('customer_form.html', customer=customer)


@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
def customer_delete(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    name = customer.name
    # 删除关联订单
    for order in customer.orders.all():
        _delete_order(order)
    db.session.delete(customer)
    db.session.commit()
    flash(f'客户 "{name}" 已删除', 'success')
    return redirect(url_for('customer_list'))


def _delete_order(order):
    """递归删除订单及其关联数据"""
    for shipment in order.shipments.all():
        for detail in shipment.details.all():
            db.session.delete(detail)
        db.session.delete(shipment)
    for line in order.lines.all():
        db.session.delete(line)
    db.session.delete(order)


# ========== 订单管理 ==========

@app.route('/orders')
def order_list():
    orders = Order.query.order_by(Order.created_at.desc()).all()

    # 全局发货矩阵（所有订单合计）
    product = Product.query.filter_by(is_active=True).first()
    colors = []
    sizes = []
    shipped_matrix = {}
    pending_matrix = {}
    order_matrix = {}
    if product:
        colors = product.colors.order_by(ProductColor.sort_order).all()
        sizes = product.sizes.order_by(ProductSize.sort_order).all()
    for o in orders:
        for line in o.lines.all():
            cs = shipped_matrix.setdefault(line.color, {})
            cs[line.size] = cs.get(line.size, 0) + line.shipped_qty
            cp = pending_matrix.setdefault(line.color, {})
            cp[line.size] = cp.get(line.size, 0) + line.pending_qty
            co = order_matrix.setdefault(line.color, {})
            co[line.size] = co.get(line.size, 0) + line.qty
    total_shipped = sum(sum(v.values()) for v in shipped_matrix.values())
    total_pending = sum(sum(v.values()) for v in pending_matrix.values())
    total_qty = sum(sum(v.values()) for v in order_matrix.values())

    return render_template('orders.html', orders=orders,
                           colors=colors, sizes=sizes,
                           shipped_matrix=shipped_matrix,
                           pending_matrix=pending_matrix,
                           order_matrix=order_matrix,
                           total_shipped=total_shipped,
                           total_pending=total_pending,
                           total_qty=total_qty)


@app.route('/orders/add', methods=['GET', 'POST'])
def order_add():
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).all()

    if not customers:
        flash('请先添加客户', 'error')
        return redirect(url_for('customer_list'))

    if request.method == 'POST':
        customer_id = request.form.get('customer_id', type=int)
        product_id = request.form.get('product_id', type=int)
        unit_price = request.form.get('unit_price', '0')
        notes = request.form.get('notes', '').strip()

        try:
            unit_price = float(unit_price)
        except ValueError:
            unit_price = 0.0

        customer = Customer.query.get(customer_id)
        if not customer:
            flash('请选择有效客户', 'error')
            return redirect(url_for('order_add'))

        # 生成订单号
        order_number = _generate_order_number()

        order = Order(
            customer_id=customer_id,
            product_id=product_id,
            order_number=order_number,
            unit_price=unit_price,
            notes=notes,
        )
        db.session.add(order)
        db.session.flush()

        # 解析尺码矩阵
        product = Product.query.get(product_id)
        colors = product.colors.order_by(ProductColor.sort_order).all()
        sizes = product.sizes.order_by(ProductSize.sort_order).all()

        total_lines = 0
        for color in colors:
            for size in sizes:
                field_name = f'qty_{color.id}_{size.size_label}'
                qty = request.form.get(field_name, type=int, default=0)
                if qty > 0:
                    line = OrderLine(
                        order_id=order.id,
                        batch=1,
                        color=color.name,
                        size=size.size_label,
                        qty=qty,
                    )
                    db.session.add(line)
                    total_lines += qty

        if total_lines == 0:
            db.session.rollback()
            flash('请至少输入一个数量', 'error')
            return redirect(url_for('order_add'))

        order.status = 'pending'
        order.refresh_totals()
        db.session.commit()
        flash(
            f'订单 {order_number} 创建成功，共 {total_lines} 双，客户：{customer.name}',
            'success')
        return redirect(url_for('order_detail', order_id=order.id))

    return render_template('order_form.html', customers=customers, products=products,
                           order=None, is_add_order=False)


@app.route('/orders/<int:order_id>')
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    product = order.product
    colors = product.colors.order_by(ProductColor.sort_order).all()
    sizes = product.sizes.order_by(ProductSize.sort_order).all()

    # 构建颜色×尺码矩阵（按批次分组）
    batches = {}
    for line in order.lines.order_by(OrderLine.batch, OrderLine.created_at).all():
        key = line.batch
        if key not in batches:
            batches[key] = {
                'batch': line.batch,
                'created_at': line.created_at.strftime('%Y-%m-%d %H:%M'),
                'lines': [],
                'total_qty': 0,
                'total_shipped': 0,
            }
        batches[key]['lines'].append(line)
        batches[key]['total_qty'] += line.qty
        batches[key]['total_shipped'] += line.shipped_qty

    # 发货历史
    shipments = order.shipments.order_by(Shipment.ship_date.desc()).all()

    # 已发货和待发货矩阵（用于弹出层）
    shipped_matrix = {}  # {color: {size: qty}}
    pending_matrix = {}
    order_matrix = {}     # {color: {size: qty}} 总订单
    for line in order.lines.all():
        color_ship = shipped_matrix.setdefault(line.color, {})
        color_ship[line.size] = color_ship.get(line.size, 0) + line.shipped_qty
        color_pend = pending_matrix.setdefault(line.color, {})
        color_pend[line.size] = color_pend.get(line.size, 0) + line.pending_qty
        color_ord = order_matrix.setdefault(line.color, {})
        color_ord[line.size] = color_ord.get(line.size, 0) + line.qty

    # 每个发货记录的明细矩阵
    shipment_matrices = []
    for shipment in shipments:
        sm = {'id': shipment.id, 'date': shipment.ship_date.strftime('%Y-%m-%d %H:%M'),
              'total': shipment.total_shipped, 'notes': shipment.notes,
              'logistics': f'{shipment.logistics_company} {shipment.tracking_number}'.strip(),
              'matrix': {}}
        for d in shipment.details.all():
            cm = sm['matrix'].setdefault(d.color, {})
            cm[d.size] = cm.get(d.size, 0) + d.qty
        shipment_matrices.append(sm)

    return render_template('order_detail.html', order=order, product=product,
                           colors=colors, sizes=sizes, batches=batches,
                           shipments=shipments, shipped_matrix=shipped_matrix,
                           pending_matrix=pending_matrix, order_matrix=order_matrix,
                           shipment_matrices=shipment_matrices)


@app.route('/orders/<int:order_id>/add-batch', methods=['GET', 'POST'])
def order_add_batch(order_id):
    """加单"""
    order = Order.query.get_or_404(order_id)
    product = order.product
    colors = product.colors.order_by(ProductColor.sort_order).all()
    sizes = product.sizes.order_by(ProductSize.sort_order).all()

    if request.method == 'POST':
        # 获取当前最大批次号
        max_batch = db.session.query(db.func.max(OrderLine.batch)) \
            .filter_by(order_id=order.id).scalar() or 1
        new_batch = max_batch + 1

        total_added = 0
        for color in colors:
            for size in sizes:
                field_name = f'qty_{color.id}_{size.size_label}'
                qty = request.form.get(field_name, type=int, default=0)
                if qty > 0:
                    line = OrderLine(
                        order_id=order.id,
                        batch=new_batch,
                        color=color.name,
                        size=size.size_label,
                        qty=qty,
                    )
                    db.session.add(line)
                    total_added += qty

        if total_added == 0:
            flash('请至少输入一个数量', 'error')
            return redirect(url_for('order_add_batch', order_id=order.id))

        if order.status == 'completed':
            order.status = 'partial'
        order.refresh_totals()
        order.updated_at = datetime.utcnow()
        db.session.commit()

        flash(f'加单成功！批次 #{new_batch}，新增 {total_added} 双', 'success')
        return redirect(url_for('order_detail', order_id=order.id))

    # 构建已有数据以便参考
    existing = {}
    for line in order.lines.all():
        key = (line.color, line.size)
        existing[key] = existing.get(key, 0) + line.qty

    return render_template('order_add_batch.html', order=order, product=product,
                           colors=colors, sizes=sizes, existing=existing)


# ========== 发货管理 ==========

@app.route('/orders/<int:order_id>/ship', methods=['GET', 'POST'])
def order_ship(order_id):
    """发货页面"""
    order = Order.query.get_or_404(order_id)
    product = order.product
    colors = product.colors.order_by(ProductColor.sort_order).all()
    sizes = product.sizes.order_by(ProductSize.sort_order).all()

    # 获取所有待发订单行
    pending_lines = [line for line in order.lines.all() if line.pending_qty > 0]

    if not pending_lines:
        flash('该订单已全部发出', 'info')
        return redirect(url_for('order_detail', order_id=order.id))

    if request.method == 'POST':
        ship_date_str = request.form.get('ship_date', '')
        notes = request.form.get('notes', '').strip()
        logistics_company = request.form.get('logistics_company', '').strip()
        tracking_number = request.form.get('tracking_number', '').strip()

        try:
            ship_date = datetime.strptime(ship_date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            ship_date = datetime.utcnow()

        shipment = Shipment(
            order_id=order.id,
            ship_date=ship_date,
            notes=notes,
            logistics_company=logistics_company,
            tracking_number=tracking_number,
        )
        db.session.add(shipment)
        db.session.flush()

        total_shipped = 0
        has_data = False
        for line in pending_lines:
            field_name = f'ship_{line.id}'
            ship_qty = request.form.get(field_name, type=int, default=0)
            if ship_qty > 0:
                has_data = True
                if ship_qty > line.pending_qty:
                    ship_qty = line.pending_qty

                detail = ShipDetail(
                    shipment_id=shipment.id,
                    order_line_id=line.id,
                    color=line.color,
                    size=line.size,
                    qty=ship_qty,
                )
                db.session.add(detail)
                line.shipped_qty += ship_qty
                total_shipped += ship_qty

        if not has_data:
            db.session.rollback()
            flash('请至少输入一个发货数量', 'error')
            return redirect(url_for('order_ship', order_id=order.id))

        # 更新订单状态
        order.refresh_totals()
        if order.total_pending <= 0:
            order.status = 'completed'
        else:
            order.status = 'partial'
        order.updated_at = datetime.utcnow()

        db.session.commit()
        flash(f'发货成功！本次共发出 {total_shipped} 双', 'success')
        return redirect(url_for('order_detail', order_id=order.id))

    return render_template('ship_form.html', order=order, product=product,
                           colors=colors, sizes=sizes, pending_lines=pending_lines,
                           now=datetime.utcnow())


@app.route('/orders/<int:order_id>/shipments/<int:shipment_id>')
def shipment_detail(order_id, shipment_id):
    """发货记录详情"""
    order = Order.query.get_or_404(order_id)
    shipment = Shipment.query.get_or_404(shipment_id)
    return render_template('shipment_detail.html', order=order, shipment=shipment)


@app.route('/orders/<int:order_id>/shipments/<int:shipment_id>/logistics', methods=['POST'])
def shipment_update_logistics(order_id, shipment_id):
    """补填物流信息"""
    shipment = Shipment.query.get_or_404(shipment_id)
    shipment.logistics_company = request.form.get('logistics_company', '').strip()
    shipment.tracking_number = request.form.get('tracking_number', '').strip()
    db.session.commit()
    flash('物流信息已更新', 'success')
    return redirect(url_for('order_detail', order_id=order_id))


# ========== 产品配置 ==========

@app.route('/products')
def product_list():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('products.html', products=products)


@app.route('/products/add', methods=['GET', 'POST'])
def product_add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('产品名不能为空', 'error')
            return redirect(url_for('product_add'))

        if Product.query.filter_by(name=name).first():
            flash(f'产品 "{name}" 已存在', 'error')
            return redirect(url_for('product_add'))

        product = Product(name=name)

        # 处理图片上传
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                product.image = filename

        db.session.add(product)
        db.session.flush()

        # 颜色
        color_names = request.form.getlist('color_name[]')
        color_hexes = request.form.getlist('color_hex[]')
        for i, (cn, ch) in enumerate(zip(color_names, color_hexes)):
            if cn.strip():
                db.session.add(ProductColor(
                    product_id=product.id,
                    name=cn.strip(),
                    hex_code=ch.strip() or '#CCCCCC',
                    sort_order=i,
                ))

        # 尺码
        size_labels = request.form.get('size_labels', '')
        for i, s in enumerate(size_labels.replace('，', ',').split(',')):
            s = s.strip()
            if s:
                db.session.add(ProductSize(
                    product_id=product.id,
                    size_label=s,
                    sort_order=i,
                ))

        db.session.commit()
        flash(f'产品 "{name}" 添加成功', 'success')
        return redirect(url_for('product_list'))

    return render_template('product_form.html', product=None)


@app.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
def product_edit(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('产品名不能为空', 'error')
            return render_template('product_form.html', product=product)

        product.name = name

        # 图片
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                product.image = filename

        # 颜色（删旧加新）
        ProductColor.query.filter_by(product_id=product.id).delete()
        color_names = request.form.getlist('color_name[]')
        color_hexes = request.form.getlist('color_hex[]')
        for i, (cn, ch) in enumerate(zip(color_names, color_hexes)):
            if cn.strip():
                db.session.add(ProductColor(
                    product_id=product.id,
                    name=cn.strip(),
                    hex_code=ch.strip() or '#CCCCCC',
                    sort_order=i,
                ))

        # 尺码（删旧加新）
        ProductSize.query.filter_by(product_id=product.id).delete()
        size_labels = request.form.get('size_labels', '')
        for i, s in enumerate(size_labels.replace('，', ',').split(',')):
            s = s.strip()
            if s:
                db.session.add(ProductSize(
                    product_id=product.id,
                    size_label=s,
                    sort_order=i,
                ))

        db.session.commit()
        flash(f'产品 "{name}" 更新成功', 'success')
        return redirect(url_for('product_list'))

    return render_template('product_form.html', product=product)


# ========== API ==========

@app.route('/api/customer/<int:customer_id>/price')
def api_customer_price(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return jsonify({'unit_price': customer.unit_price})


@app.route('/api/product/<int:product_id>/config')
def api_product_config(product_id):
    product = Product.query.get_or_404(product_id)
    colors = product.colors.order_by(ProductColor.sort_order).all()
    sizes = product.sizes.order_by(ProductSize.sort_order).all()
    return jsonify({
        'colors': [{'id': c.id, 'name': c.name, 'hex_code': c.hex_code} for c in colors],
        'sizes': [s.size_label for s in sizes],
    })


# ========== 辅助函数 ==========

def _generate_order_number():
    """生成订单号: WH-年月日-序号"""
    today = datetime.utcnow().strftime('%Y%m%d')
    prefix = f'WH-{today}'
    count = Order.query.filter(Order.order_number.like(f'{prefix}%')).count()
    return f'{prefix}-{count + 1:03d}'


# ========== 启动 ==========

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)

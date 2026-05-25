"""数据库模型 - 批发订单管理系统"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Customer(db.Model):
    """客户表"""
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='customer', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'unit_price': self.unit_price,
            'notes': self.notes,
            'created_at': self.created_at.strftime('%Y-%m-%d'),
            'order_count': self.orders.count(),
        }


class Product(db.Model):
    """产品/款式表"""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # 如: 2603人字拖
    image = db.Column(db.String(255), default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    colors = db.relationship('ProductColor', backref='product', lazy='dynamic',
                             cascade='all, delete-orphan')
    sizes = db.relationship('ProductSize', backref='product', lazy='dynamic',
                            cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='product', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image': self.image,
            'is_active': self.is_active,
            'colors': [c.to_dict() for c in self.colors.all()],
            'sizes': [s.size_label for s in self.get_sorted_sizes()],
        }

    def get_sorted_colors(self):
        return self.colors.order_by(ProductColor.sort_order).all()

    def get_sorted_sizes(self):
        return self.sizes.order_by(ProductSize.sort_order).all()


class ProductColor(db.Model):
    """产品颜色配置"""
    __tablename__ = 'product_colors'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)  # 如: 巧克力
    hex_code = db.Column(db.String(7), default='#CCCCCC')  # 如: #8B4513
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'hex_code': self.hex_code,
        }


class ProductSize(db.Model):
    """产品尺码配置"""
    __tablename__ = 'product_sizes'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    size_label = db.Column(db.String(10), nullable=False)  # 如: 36, 37, 38
    sort_order = db.Column(db.Integer, default=0)


class Order(db.Model):
    """订单表"""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    total_qty = db.Column(db.Integer, default=0)
    total_shipped = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending / partial / completed
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lines = db.relationship('OrderLine', backref='order', lazy='dynamic',
                            cascade='all, delete-orphan')
    shipments = db.relationship('Shipment', backref='order', lazy='dynamic',
                                cascade='all, delete-orphan')

    @property
    def total_pending(self):
        return self.total_qty - self.total_shipped

    @property
    def batch_count(self):
        """加单批次数"""
        batches = set(line.batch for line in self.lines.all())
        return len(batches)

    def refresh_totals(self):
        """刷新统计数据"""
        self.total_qty = sum(line.qty for line in self.lines.all())
        self.total_shipped = sum(line.shipped_qty for line in self.lines.all())

    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'customer_name': self.customer.name,
            'product_name': self.product.name,
            'unit_price': self.unit_price,
            'status': self.status,
            'total_qty': self.total_qty,
            'total_shipped': self.total_shipped,
            'total_pending': self.total_pending,
            'batch_count': self.batch_count,
            'notes': self.notes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


class OrderLine(db.Model):
    """订单明细（核心：支持加单批次）"""
    __tablename__ = 'order_lines'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    batch = db.Column(db.Integer, default=1)  # 批次号：1=首批,2=第一次加单...
    color = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(10), nullable=False)
    qty = db.Column(db.Integer, default=0)  # 本批次订购数量
    shipped_qty = db.Column(db.Integer, default=0)  # 累计已发
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def pending_qty(self):
        return self.qty - self.shipped_qty


class Shipment(db.Model):
    """发货记录"""
    __tablename__ = 'shipments'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    ship_date = db.Column(db.DateTime, default=datetime.utcnow)
    logistics_company = db.Column(db.String(50), default='')
    tracking_number = db.Column(db.String(50), default='')
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    details = db.relationship('ShipDetail', backref='shipment', lazy='dynamic',
                              cascade='all, delete-orphan')

    @property
    def total_shipped(self):
        return sum(d.qty for d in self.details.all())

    @property
    def is_overship(self):
        """是否包含超发"""
        return self.over_qty > 0

    @property
    def over_qty(self):
        """超发数量"""
        total = 0
        for d in self.details.all():
            line = OrderLine.query.get(d.order_line_id)
            if line and line.shipped_qty > line.qty:
                # 计算该行本次贡献的超发量
                overship = max(0, line.shipped_qty - line.qty)
                total += min(d.qty, overship)
        return total

    def to_dict(self):
        return {
            'id': self.id,
            'ship_date': self.ship_date.strftime('%Y-%m-%d %H:%M'),
            'total_shipped': self.total_shipped,
            'logistics_company': self.logistics_company,
            'tracking_number': self.tracking_number,
            'notes': self.notes,
            'details': [d.to_dict() for d in self.details.all()],
        }


class ShipDetail(db.Model):
    """发货明细"""
    __tablename__ = 'ship_details'

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipments.id'), nullable=False)
    order_line_id = db.Column(db.Integer, db.ForeignKey('order_lines.id'), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(10), nullable=False)
    qty = db.Column(db.Integer, default=0)  # 本次发货数量

    order_line = db.relationship('OrderLine')

    def to_dict(self):
        return {
            'id': self.id,
            'color': self.color,
            'size': self.size,
            'qty': self.qty,
        }

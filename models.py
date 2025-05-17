from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address1 = db.Column(db.String(200))
    address2 = db.Column(db.String(200))
    gstin = db.Column(db.String(100))
    bills = db.relationship('Bill', backref='customer', cascade="all, delete-orphan", lazy=True)
    payments = db.relationship('Payment', backref='customer', cascade="all, delete-orphan", lazy=True)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(20))
    address = db.Column(db.String(200))
    gstin = db.Column(db.String(100))
    purchases = db.relationship('Purchase', backref='supplier', lazy=True)
    payments = db.relationship('SupplierPayment', back_populates='supplier', cascade="all, delete-orphan")

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    hsn_code = db.Column(db.String(100))
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    is_interstate = db.Column(db.Boolean, default=False)
    gst_rate = db.Column(db.Float, nullable=False)
    cgst = db.Column(db.Float, nullable=False)
    sgst = db.Column(db.Float, nullable=False)
    igst = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    grand_total = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('BillItem', backref='bill', cascade="all, delete-orphan", lazy=True)

    def __repr__(self):
        return f'<Bill {self.id}>'

class BillItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bill.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    qty_type = db.Column(db.String(10), nullable=False)  # fixed: added length
    subtotal = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_no = db.Column(db.String(100), nullable=False)  # fixed: added length
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    is_interstate = db.Column(db.Boolean, default=False)
    gst_rate = db.Column(db.Float, nullable=False)
    cgst = db.Column(db.Float, nullable=False)
    sgst = db.Column(db.Float, nullable=False)
    igst = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    grand_total = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('PurchaseItem', backref='purchase', lazy=True)

    def __repr__(self):
        return f'<Purchase {self.id}>'

class PurchaseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payment_gateway = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))

class SupplierPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    payment_gateway = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    supplier = db.relationship('Supplier', back_populates='payments')

from flask import Flask, render_template, request, redirect, url_for, make_response
from models import db, Customer, Supplier, Product, Bill, BillItem, Purchase, PurchaseItem, Payment, SupplierPayment
from datetime import datetime
from faker import Faker
import random
from sqlalchemy import func, extract
from datetime import date, timedelta
import pdfkit
import os

fake = Faker()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://avnadmin:AVNS_3MFk0LeCjUtGdP0kAbL@mysql-375f5a66-billing-system2025.g.aivencloud.com:18966/defaultdb"
# app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'ssl': {'ssl_ca': '/path/to/ca.pem'}
    }
}
db.init_app(app)

with app.app_context():
    db.create_all()

def calculate_gst(total, gst_rate, is_interstate):
    if is_interstate:
        igst = round(total * gst_rate)
        cgst = sgst = 0
    else:
        igst = 0
        cgst = sgst = round(total * (gst_rate / 2))
    grand_total = round(total + igst + cgst + sgst)
    return cgst, sgst, igst, grand_total

def generate_bill_number():
    last_bill = Bill.query.order_by(Bill.bill_number.desc()).first()
    return (last_bill.bill_number + 1) if last_bill else 1

def create_dummy_data():
    with app.app_context():
        # Create 20 dummy customers
        for _ in range(20):
            customer = Customer(
                name=fake.name(),
                phone=fake.phone_number(),
                address1=fake.street_address(),
                address2=fake.city(),
                gstin=fake.bothify(text='##AAAA####A1Z#')  # Random format
            )
            db.session.add(customer)

        db.session.commit()

        # Ensure we have at least 10 products in the DB
        if not Product.query.first():
            for _ in range(10):
                product = Product(
                    name=fake.word().capitalize(),
                    hsn_code=str(random.randint(1001, 9999)),
                    price=random.randint(100, 1000),
                    stock=random.randint(10, 100)
                )
                db.session.add(product)
            db.session.commit()

        customers = Customer.query.all()
        products = Product.query.all()

        # Create 100 dummy bills
        for _ in range(100):
            customer = random.choice(customers)
            is_interstate = random.choice([True, False])
            gst_rate = random.choice([5, 12, 18, 28]) / 100.0

            selected_products = random.sample(products, random.randint(1, 4))
            total = 0
            bill_items = []

            for product in selected_products:
                qty = random.randint(1, 5)
                price = product.price
                subtotal = price * qty
                total += subtotal
                bill_items.append((product.id, qty, price, subtotal))

            # GST calculation
            if is_interstate:
                igst = round(total * gst_rate)
                cgst = sgst = 0
            else:
                igst = 0
                cgst = sgst = round(total * (gst_rate / 2))
            grand_total = round(total + cgst + sgst + igst)

            bill = Bill(
                customer_id=customer.id,
                is_interstate=is_interstate,
                gst_rate=gst_rate,
                cgst=cgst,
                sgst=sgst,
                igst=igst,
                total_amount=total,
                grand_total=grand_total
            )
            db.session.add(bill)
            db.session.commit()

            for product_id, qty, price, subtotal in bill_items:
                item = BillItem(
                    bill_id=bill.id,
                    product_id=product_id,
                    quantity=qty,
                    price=price,
                    subtotal=subtotal,
                    qty_type='nos'
                )
                db.session.add(item)

            db.session.commit()

        print("20 customers and 100 bills created successfully.")

@app.route('/')
def index():
    today = date.today()
    start_date = today.replace(day=1)
    if today.month == 12:
        end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    total_customers = Customer.query.count()
    total_bills = Bill.query.count()
    monthly_sales = db.session.query(func.sum(Bill.grand_total))\
        .filter(Bill.created_at >= start_date, Bill.created_at <= end_date)\
        .scalar() or 0
    low_stock_count = Product.query.filter(Product.stock < 5).count()
    recent_bills = Bill.query.order_by(Bill.created_at.desc()).limit(5).all()
    recent_customers = Customer.query.order_by(Customer.id.desc()).limit(5).all()

    monthly_sales_data = db.session.query(
        extract('month', Bill.created_at).label('month'),
        func.sum(Bill.grand_total).label('total')
    ).filter(
        extract('year', Bill.created_at) == today.year
    ).group_by('month').order_by('month').all()

    # Prepare chart labels and values
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    chart_labels = [month_names[int(month)-1] for month, _ in monthly_sales_data]
    chart_data = [float(total) for _, total in monthly_sales_data]

    return render_template('index.html',
        total_customers=total_customers,
        total_bills=total_bills,
        monthly_sales=monthly_sales,
        low_stock_count=low_stock_count,
        recent_bills=recent_bills,
        recent_customers=recent_customers,
        chart_labels=chart_labels,
        chart_data=chart_data
    )

@app.route('/generate_dummy_data')
def generate_dummy():
    create_dummy_data()
    print("Success")
    return url_for("index")

# ------------------- Customer Routes -------------------
@app.route('/customers')
def customers():
    customers = Customer.query.all()
    return render_template('customers.html', customers=customers)

@app.route('/add_customer', methods=['POST'])
def add_customer():
    customer = Customer(
        name=request.form['name'],
        phone=request.form['phone'],
        address1=request.form['address1'],
        address2=request.form['address2'],
        gstin=request.form['gstin']
    )
    db.session.add(customer)
    db.session.commit()
    return redirect(url_for('customers'))

@app.route('/edit_customer/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        customer.name = request.form['name']
        customer.phone = request.form['phone']
        customer.address1 = request.form['address1']
        customer.address2 = request.form['address2']
        customer.gstin = request.form['gstin']
        db.session.commit()
        return redirect(url_for('customers'))

@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('customers'))

@app.route("/customers/<int:customer_id>/view_bills")
def customer_bills(customer_id):
    customer = Customer.query.get_or_404(customer_id)    
    bills = Bill.query.filter_by(customer_id=customer.id).all()
    return render_template('customer_view_bills.html', customer=customer, bills=bills)

@app.route("/customers/<int:customer_id>/ledger", methods=['GET', 'POST'])
def customer_ledger(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        gateway = request.form['gateway']
        amount = float(request.form['amount'])
        date = request.form['date']

        payment = Payment(
            customer_id=customer.id,
            payment_gateway=gateway,
            amount=amount,
            date=datetime.strptime(date, '%Y-%m-%d').date()  # ensure .date()
        )
        db.session.add(payment)
        db.session.commit()
        return redirect(url_for('customer_ledger', customer_id=customer.id))

    entries = []

    for bill in customer.bills:
        bill_date = bill.created_at.date() if isinstance(bill.created_at, datetime) else bill.created_at
        entries.append({
            "date": bill_date,
            "description": f"Bill {bill.bill_number}",
            "debit": bill.grand_total,
            "credit": 0
        })

    for payment in customer.payments:
        pay_date = payment.date.date() if isinstance(payment.date, datetime) else payment.date
        entries.append({
            "date": pay_date,
            "description": f"Payment via {payment.payment_gateway}",
            "debit": 0,
            "credit": payment.amount
        })

    # Sort by date (all now consistent types)
    entries.sort(key=lambda x: x["date"])

    # Calculate running balance
    balance = 0
    for entry in entries:
        balance += entry["credit"] - entry["debit"]
        entry["balance"] = balance

    return render_template("ledger.html", customer=customer, entries=entries, total_balance=balance)
@app.route("/customers/<int:customer_id>/ledger/pdf")
def customer_ledger_pdf(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    entries = []
    for bill in customer.bills:
        entries.append({"date": bill.created_at.date(), "description": f"Bill #{bill.bill_number}", "debit": bill.grand_total, "credit": 0})
    for payment in customer.payments:
        entries.append({"date": payment.date, "description": f"Payment via {payment.payment_gateway}", "debit": 0, "credit": payment.amount})
    
    entries.sort(key=lambda x: x["date"])
    balance = 0
    for entry in entries:
        balance += entry["credit"] - entry["debit"]
        entry["balance"] = balance
    
    rendered = render_template("ledger_pdf.html", customer=customer, entries=entries, total_balance=balance)
    
    config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')
    pdf = pdfkit.from_string(rendered, False, configuration=config)
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=ledger_{customer.id}.pdf'
    return response

@app.route("/customers/gst_ledger")
def gst_ledger():
    bills = Bill.query.all()

    detailed_bills = []
    bill_total = cgst = sgst = igst = total = 0

    for bill in bills:
        items_by_type = {'kgs': {'qty': 0, 'amount': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0},
                         'nos': {'qty': 0, 'amount': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0}}

        for item in bill.items:
            qty_type = item.qty_type or 'Unknown'
            if qty_type not in items_by_type:
                items_by_type[qty_type] = {'qty': 0, 'amount': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0}

            subtotal = item.price * item.quantity
            items_by_type[qty_type]["qty"] += item.quantity
            items_by_type[qty_type]["amount"] += subtotal
            items_by_type[qty_type]["cgst"] += subtotal * (bill.gst_rate / 2) if not bill.is_interstate else 0
            items_by_type[qty_type]["sgst"] += subtotal * (bill.gst_rate / 2) if not bill.is_interstate else 0
            items_by_type[qty_type]["igst"] += subtotal * bill.gst_rate if bill.is_interstate else 0

        total_qty_kgs = items_by_type['kgs']['qty']
        total_qty_nos = items_by_type['nos']['qty']
        total_amount_kgs = items_by_type['kgs']['amount']
        total_amount_nos = items_by_type['nos']['amount']
        total_cgst = items_by_type['kgs']['cgst'] + items_by_type['nos']['cgst']
        total_sgst = items_by_type['kgs']['sgst'] + items_by_type['nos']['sgst']
        total_igst = items_by_type['kgs']['igst'] + items_by_type['nos']['igst']
        
        grand_total = total_amount_kgs + total_amount_nos + total_cgst + total_sgst + total_igst

        detailed_bills.append({
            "bill_id": bill.bill_number,
            "customer": bill.customer.name,
            "date": bill.created_at.date() if bill.created_at else '',
            "total_qty_kgs": total_qty_kgs,
            "total_qty_nos": total_qty_nos,
            "gst_rate": bill.gst_rate,
            "total_amount_kgs": total_amount_kgs,
            "total_amount_nos": total_amount_nos,
            "cgst": total_cgst,
            "sgst": total_sgst,
            "igst": total_igst,
            "grand_total": grand_total
        })

        bill_total += total_amount_kgs + total_amount_nos
        cgst += total_cgst
        sgst += total_sgst
        igst += total_igst
        total += grand_total

    return render_template(
        'gst_ledger.html',
        bills=detailed_bills,
        bill_total=bill_total,
        cgst=cgst,
        sgst=sgst,
        igst=igst,
        total=total
    )

# ------------------- Supplier Routes -------------------
@app.route('/suppliers')
def suppliers():
    suppliers = Supplier.query.all()
    return render_template('suppliers.html', suppliers=suppliers)

@app.route('/add_supplier', methods=['POST'])
def add_supplier():
    supplier = Supplier(
        name=request.form['name'],
        contact=request.form['contact'],
        address=request.form['address'],
        gstin=request.form['gstin']
    )
    db.session.add(supplier)
    db.session.commit()
    return redirect(url_for('suppliers'))

@app.route('/edit_supplier/<int:supplier_id>', methods=['GET', 'POST'])
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == 'POST':
        supplier.name = request.form['name']
        supplier.contact = request.form['contact']
        supplier.address = request.form['address']
        supplier.gstin = request.form['gstin']
        db.session.commit()
        return redirect(url_for('suppliers'))

@app.route('/delete_supplier/<int:supplier_id>', methods=['POST'])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    Purchase.query.filter_by(supplier_id=supplier.id).delete()
    db.session.delete(supplier)
    db.session.commit()
    return redirect(url_for('suppliers'))

@app.route("/suppliers/<int:supplier_id>/view_pills")
def supplier_purchases(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    purchases = Purchase.query.filter_by(supplier_id=supplier.id).all()
    return render_template('supplier_view_purchases.html', supplier=supplier, purchases=purchases)

@app.route("/suppliers/<int:supplier_id>/ledger", methods=['GET', 'POST'])
def supplier_ledger(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)

    if request.method == 'POST':
        gateway = request.form['gateway']
        amount = float(request.form['amount'])
        date = request.form['date']

        payment = SupplierPayment(
            supplier_id=supplier.id,
            payment_gateway=gateway,
            amount=amount,
            date=datetime.strptime(date, '%Y-%m-%d').date()
        )
        db.session.add(payment)
        db.session.commit()
        return redirect(url_for('supplier_ledger', supplier_id=supplier.id))

    entries = []

    for purchase in supplier.purchases:
        pur_date = purchase.created_at.date() if isinstance(purchase.created_at, datetime) else purchase.created_at
        entries.append({
            "date": pur_date,
            "description": f"Purchase #{purchase.id}",
            "debit": purchase.grand_total,
            "credit": 0
        })

    for payment in supplier.payments:
        pay_date = payment.date.date() if isinstance(payment.date, datetime) else payment.date
        entries.append({
            "date": pay_date,
            "description": f"Payment via {payment.payment_gateway}",
            "debit": 0,
            "credit": payment.amount
        })

    entries.sort(key=lambda x: x["date"])

    balance = 0
    for entry in entries:
        balance += entry["credit"] - entry["debit"]
        entry["balance"] = balance

    return render_template("supplier_ledger.html", supplier=supplier, entries=entries, total_balance=balance)

@app.route("/suppliers/<int:supplier_id>/ledger/pdf")
def supplier_ledger_pdf(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    entries = []
    
    for purchase in supplier.purchases:
        entries.append({
            "date": purchase.created_at.date() if isinstance(purchase.created_at, datetime) else purchase.created_at,
            "description": f"Purchase #{purchase.id}",
            "debit": purchase.total_amount,
            "credit": 0
        })
    
    for payment in supplier.payments:
        entries.append({
            "date": payment.date.date() if isinstance(payment.date, datetime) else payment.date,
            "description": f"Payment via {payment.payment_gateway}",
            "debit": 0,
            "credit": payment.amount
        })
    
    entries.sort(key=lambda x: x["date"])
    
    balance = 0
    for entry in entries:
        balance += entry["credit"] - entry["debit"]
        entry["balance"] = balance
    
    rendered = render_template("supplier_ledger_pdf.html", supplier=supplier, entries=entries, total_balance=balance)
    
    config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')
    pdf = pdfkit.from_string(rendered, False, configuration=config)
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=supplier_ledger_{supplier.id}.pdf'
    return response

# ------------------- Bill Routes -------------------
@app.route('/bills')
def bills():
    bills = Bill.query.all()
    return render_template('bills.html', bills=bills)

@app.route('/create_bill', methods=['GET', 'POST'])
def create_bill():
    if request.method == 'POST':
        customer_id = int(request.form['customer_id'])
        is_interstate = request.form.get('is_interstate') == 'yes'
        gst_rate = float(request.form['gst_rate']) / 100
        qty_types = request.form.getlist('qty_type')
        product_names = request.form.getlist('product_name')
        hsn_codes = request.form.getlist('hsn_code')
        prices = request.form.getlist('price')
        quantities = request.form.getlist('quantity')

        total = 0
        bill_items = []

        for name, hsn, price, qty,qty_type in zip(product_names, hsn_codes, prices, quantities,qty_types):
            price = float(price)
            qty = int(qty)
            subtotal = price * qty
            total += subtotal

            product = Product.query.filter_by(name=name).first()
            if not product:
                product = Product(name=name, hsn_code=hsn, price=price, stock=0)
                db.session.add(product)
                db.session.commit()

            bill_items.append((product.id, qty, price, subtotal, qty_type))
        cgst, sgst, igst, grand_total = calculate_gst(total, gst_rate, is_interstate)
        bill = Bill(
            bill_number=generate_bill_number(),
            customer_id=customer_id,
            is_interstate=is_interstate,
            gst_rate=gst_rate,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            total_amount=total,
            grand_total=grand_total
        )
        db.session.add(bill)
        db.session.commit()

        for product_id, qty, price, subtotal, qty_type in bill_items:
            item = BillItem(
                bill_id=bill.id,
                product_id=product_id,
                quantity=qty,
                qty_type=qty_type,
                price=price,
                subtotal=subtotal
            )
            db.session.add(item)

        db.session.commit()
        return redirect(url_for('bills'))

    customers = Customer.query.all()
    products = Product.query.all()
    return render_template('add_bill.html', customers=customers, products=products)

@app.route('/bill/<int:bill_id>', methods=['GET'])
def view_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    bill_items = BillItem.query.filter_by(bill_id=bill_id).all()
    return render_template('view_bill.html', bill=bill, items=bill_items)

@app.route('/edit_bill/<int:bill_id>', methods=['GET', 'POST'])
def edit_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    bill_items = BillItem.query.filter_by(bill_id=bill_id).all()
    if request.method == 'POST':
        BillItem.query.filter_by(bill_id=bill.id).delete()
        customer_id = int(request.form['customer_id'])
        is_interstate = request.form.get('is_interstate') == 'yes'
        gst_rate = float(request.form['gst_rate']) / 100  # gst_rate from form
        qty_types = request.form.getlist('qty_type')
        product_names = request.form.getlist('product_name')
        hsn_codes = request.form.getlist('hsn_code')
        prices = request.form.getlist('price')
        quantities = request.form.getlist('quantity')

        total = 0
        bill_items = []

        for name, hsn, price, qty,qty_type in zip(product_names, hsn_codes, prices, quantities,qty_types):
            price = float(price)
            qty = int(qty)
            subtotal = price * qty
            total += subtotal

            product = Product.query.filter_by(name=name).first()
            if not product:
                product = Product(name=name, hsn_code=hsn, price=price, stock=0)
                db.session.add(product)
                db.session.commit()

            bill_items.append((product.id, qty, price, subtotal,qty_type))

        cgst, sgst, igst, grand_total = calculate_gst(total, gst_rate, is_interstate)
        grand_total = round(grand_total)

        bill.customer_id = customer_id
        bill.is_interstate = is_interstate
        bill.gst_rate = gst_rate
        bill.cgst = cgst
        bill.sgst = sgst
        bill.igst = igst
        bill.total_amount = total
        bill.grand_total = grand_total
        db.session.commit()

        for product_id, qty, price, subtotal, qty_type in bill_items:
            item = BillItem(
                bill_id=bill.id,
                product_id=product_id,
                quantity=qty,
                qty_type=qty_type,
                price=price,
                subtotal=subtotal,
            )
            db.session.add(item)

        db.session.commit()
        return redirect(url_for('bills'))

    customers = Customer.query.all()
    products = Product.query.all()
    return render_template('edit_bill.html', bill=bill, customers=customers, products=products, bill_items=bill_items)

@app.route('/delete_bill/<int:bill_id>', methods=['POST'])
def delete_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    BillItem.query.filter_by(bill_id=bill.id).delete()
    db.session.delete(bill)
    db.session.commit()
    return redirect(url_for('bills'))

@app.route("/bill/<int:bill_id>/pdf")
def bill_pdf(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    items = BillItem.query.filter_by(bill_id=bill.id).all()
    slno = 0
    rendered = render_template("bill_pdf.html", bill=bill, items=items, slno=slno)
    # config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')

    config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')
    pdf = pdfkit.from_string(rendered, False, configuration=config)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=bill_{bill.bill_number}.pdf'
    return response
# ------------------- Purchase Routes -------------------
@app.route('/purchases')
def purchases():
    purchases = Purchase.query.all()
    return render_template('purchases.html', purchases=purchases)

@app.route('/create_purchase', methods=['GET', 'POST'])
def create_purchase():
    if request.method == 'POST':
        supplier_id = int(request.form['supplier_id'])
        is_interstate = request.form.get('is_interstate') == 'yes'
        gst_rate = float(request.form['gst_rate']) / 100  # gst_rate from form
        bill_no = request.form['bill_no']
        product_names = request.form.getlist('product_name')
        hsn_codes = request.form.getlist('hsn_code')
        prices = request.form.getlist('price')
        quantities = request.form.getlist('quantity')

        total = 0
        purchase_items = []

        for name, hsn, price, qty in zip(product_names, hsn_codes, prices, quantities):
            price = float(price)
            qty = int(qty)
            subtotal = price * qty
            total += subtotal

            product = Product.query.filter_by(name=name).first()
            if not product:
                product = Product(name=name, hsn_code=hsn, price=price, stock=qty)
                db.session.add(product)
                db.session.commit()
            else:
                product.stock += qty
                db.session.commit()

            purchase_items.append((product.id, qty, price, subtotal))

        cgst, sgst, igst, grand_total = calculate_gst(total, gst_rate, is_interstate)

        purchase = Purchase(
            supplier_id=supplier_id,
            is_interstate=is_interstate,
            gst_rate=gst_rate,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            total_amount=total,
            grand_total=grand_total, 
            bill_no=bill_no,
        )
        db.session.add(purchase)
        db.session.commit()

        for product_id, qty, price, subtotal in purchase_items:
            item = PurchaseItem(
                purchase_id=purchase.id,
                product_id=product_id,
                quantity=qty,
                price=price,
                subtotal=subtotal
            )
            db.session.add(item)

        db.session.commit()
        return redirect(url_for('purchases'))

    suppliers = Supplier.query.all()
    products = Product.query.all()
    return render_template('add_purchase.html', suppliers=suppliers, products=products)

@app.route('/purchase/<int:purchase_id>', methods=['GET'])
def view_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    purchase_items = PurchaseItem.query.filter_by(purchase_id=purchase_id).all()
    return render_template('view_purchase.html', purchase=purchase, items=purchase_items)

@app.route('/edit_purchase/<int:purchase_id>', methods=['GET', 'POST'])
def edit_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    purchase_items = PurchaseItem.query.filter_by(purchase_id=purchase_id).all()

    if request.method == 'POST':
        PurchaseItem.query.filter_by(purchase_id=purchase.id).delete()
        supplier_id = int(request.form['supplier_id'])
        is_interstate = request.form.get('is_interstate') == 'yes'
        gst_rate = float(request.form['gst_rate']) / 100
        bill_no = request.form['bill_no']
        product_names = request.form.getlist('product_name')
        hsn_codes = request.form.getlist('hsn_code')
        prices = request.form.getlist('price')
        quantities = request.form.getlist('quantity')

        total = 0
        purchase_items = []

        for name, hsn, price, qty in zip(product_names, hsn_codes, prices, quantities):
            price = float(price)
            qty = int(qty)
            subtotal = price * qty
            total += subtotal

            product = Product.query.filter_by(name=name).first()
            if not product:
                product = Product(name=name, hsn_code=hsn, price=price, stock=qty)
                db.session.add(product)
                db.session.commit()
            else:
                product.stock += qty
                db.session.commit()

            purchase_items.append((product.id, qty, price, subtotal))

        cgst, sgst, igst, grand_total = calculate_gst(total, gst_rate, is_interstate)

        purchase.supplier_id = supplier_id
        purchase.is_interstate = is_interstate
        purchase.gst_rate = gst_rate
        purchase.cgst = cgst
        purchase.sgst = sgst
        purchase.igst = igst
        purchase.total_amount = total
        purchase.grand_total = grand_total
        purchase.bill_no = bill_no
        db.session.commit()

        db.session.commit()

        # Add new purchase items
        for product_id, qty, price, subtotal in purchase_items:
            item = PurchaseItem(
                purchase_id=purchase.id,
                product_id=product_id,
                quantity=qty,
                price=price,
                subtotal=subtotal
            )
            db.session.add(item)

        db.session.commit()
        return redirect(url_for('purchases'))

    suppliers = Supplier.query.all()
    products = Product.query.all()
    return render_template('edit_purchase.html', purchase=purchase, suppliers=suppliers, products=products, purchase_items=purchase_items)

@app.route('/delete_purchase/<int:purchase_id>', methods=['GET','POST'])
def delete_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    PurchaseItem.query.filter_by(purchase_id=purchase.id).delete()
    db.session.delete(purchase)
    db.session.commit()
    return redirect(url_for('purchases'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)),debug=True)

from flask import Flask, render_template, url_for, request, redirect, flash, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.wsgi import FileWrapper
import io
import xlsxwriter
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'Inventory'  
db = SQLAlchemy(app)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(50), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return self.product_name


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    warehouse_location = db.Column(db.String(100), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    dated_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return self.warehouse_location


class ProductMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    from_location = db.Column(db.String(100))
    to_location = db.Column(db.String(100))
    product_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(50), nullable=False)
    product_qty = db.Column(db.Integer, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return 'Movement ' + str(self.id)


@app.route("/")
@app.route("/index")
def index():
    data = get_summary()
    return render_template("index.html", Summary=data)


@app.route("/product/", methods=['GET', 'POST'])
def product():
    if request.method == 'POST':
        if 'edit_product' in request.form:
            product_id = request.form['edit_product']
            exist = Product.query.filter_by(id=product_id).first()
            product_name = request.form['product_name']
            product_movements = ProductMovement.query.filter_by(product_name=exist.product_name).all()
            if product_movements:
                for item in product_movements:
                    item.product_name = product_name
            exist.product_name = product_name
            exist.date_updated = datetime.utcnow()
            flash(f"'{exist.product_name}' is successfully updated!", "success")
        elif 'product_name' in request.form:
            product_name = request.form['product_name']
            if Product.query.filter_by(product_name=product_name).first():
                flash(f"'{product_name}' already exists in the data!", "warning")
            else:
                new_product = Product(product_name=product_name)
                db.session.add(new_product)
                flash(f"'{product_name}' is successfully added!", "success")
        db.session.commit()
        return redirect(url_for("product"))
   
    all_products = get_product_data()
    return render_template("product.html", Products=all_products)


@app.route("/location", methods=['GET', 'POST'])
def location():
    if request.method == 'POST':
        if 'edit_location' in request.form:
            location_id = request.form['edit_location']
            exist = Product.query.filter_by(id=location_id).first()
            location_name = request.form['location_name']
            from_movements = ProductMovement.query.filter_by(from_location=exist.warehouse_location).all()
            if from_movements:
                for item in from_movements:
                    item.from_location = location_name
            to_movements = ProductMovement.query.filter_by(to_location=exist.warehouse_location).all()
            if to_movements:
                for item in to_movements:
                    item.from_location = location_name
            exist.warehouse_location = location_name
            exist.date_updated = datetime.utcnow()
            flash(f"'{exist.warehouse_location}' is successfully updated!", "info")
        elif 'location_name' in request.form:
            location_name = request.form['location_name']
            if Location.query.filter_by(warehouse_location=location_name).first():
                flash(f"'{location_name}' already exists in the data!", "warning")
            else:
                new_location = Location(warehouse_location=location_name)
                db.session.add(new_location)
                flash(f"'{location_name}' warehouse is successfully added!", "success")
        db.session.commit()
        return redirect(url_for("location"))

    all_location = get_warehouse_data()
    return render_template("location.html", Locations=all_location)


@app.route("/movement", methods=['GET', 'POST'])
def movement():
    if request.method == 'POST':
        if 'edit_movement' in request.form:
            editable = True
            movement_id = request.form['edit_movement']
            new_qty = request.form["product_quantity"]
            movement = ProductMovement.query.filter_by(id=movement_id).first()
            movement_product = movement.product_name
            # To check exported & imported items
            movement_to_location = movement.from_location
            movement_from_location = movement.to_location
            export_movement = ProductMovement.query.filter_by(product_name=movement_product).filter_by(from_location=movement_from_location).count()
            import_movement = ProductMovement.query.filter_by(product_name=movement_product).filter_by(to_location=movement_to_location).count()
            if export_movement > 0 :
                exported_items = get_exported(movement_product, movement_from_location)
                if exported_items:
                    exported_qty=0
                    for item in exported_items:
                        exported_qty += item.product_qty
                    if exported_qty > int(new_qty):   
                        editable = False
                        flash("Product movement can not be updated!", "warning")
            if import_movement > 0 :
                imported_items = get_imported(movement_product, movement_to_location)
                if imported_items:
                    imported_qty = 0
                    for item in imported_items:
                        imported_qty += item.product_qty       
                    if imported_qty < int(new_qty):
                        editable = False
                        flash("Product movement can not be updated!", "warning")
            if editable:
                movement.product_qty = new_qty
                movement.date_updated = datetime.utcnow()
                flash("Product quantity is successfully updated!", "success")
        else:
            valid = True
            product_name = None
            product_quantity = None
            from_location = request.form['from_location']
            to_location = request.form['to_location']
            if from_location != 'Select warehouse' or to_location != 'Select warehouse':
                if from_location == to_location:
                    valid = False
                    flash('From and To location can not be same!', 'danger')
            else:
                flash("From and To locations were not selected!", 'danger')
                valid = False

            if request.form['product_name'] == 'Select product':
                flash('No product was selected!', 'danger')
                valid = False
            else: 
                product_name = request.form['product_name'] 
                if request.form['product_quantity'] != None:
                    if int(request.form['product_quantity']) > 0:
                        product_quantity = request.form['product_quantity']
                        if from_location != 'Select warehouse':
                            total_items = get_total(product_name, from_location)
                            if total_items == 0:
                                flash(f"Stock for '{product_name}' is not currently available at {from_location}", 'info')
                                valid = False
                            elif int(product_quantity) > total_items:
                                flash(f"Only {total_items} '{product_name}s' are available at {from_location}!", 'info')
                                valid = False
                    else:
                        flash('Invalid amount of quantity was added!', 'danger')
                        valid = False
               
            if valid:
                product_selected = Product.query.filter_by(product_name=product_name).first()
                new_movement = ProductMovement()
                new_movement.product_id = product_selected.id
                new_movement.product_name = product_selected.product_name
                if from_location != 'Select warehouse':
                    new_movement.from_location = from_location
                if to_location != 'Select warehouse':
                    new_movement.to_location = to_location
                new_movement.product_qty = product_quantity
                db.session.add(new_movement)
                flash(f"Product movement for '{new_movement.product_name}' is successfully added!", 'success')
        db.session.commit()
        return redirect(url_for('movement'))
    products = Product.query.all()
    locations = Location.query.all()
    movements = ProductMovement.query.all()
    return render_template('movements.html', products=products, locations=locations, Movements=movements)


@app.route("/download", methods=['GET', 'POST'])
def export_report():
    timestamp = datetime.utcnow()
    summary = get_summary()
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    bold = workbook.add_format({'bold': 1})
    worksheet.write('A1', 'Product', bold)
    worksheet.write('B1', 'Location', bold)
    worksheet.write('C1', 'Available Qty', bold)
    row = 1
    for item in summary:
        if item['available_quantity'] == 0:
            continue
        worksheet.write  (row, 0, item['product'])
        worksheet.write  (row, 1, item['location'])
        worksheet.write (row, 2, item['available_quantity'])
        row += 1
    workbook.close()
    output.seek(0)
    data = FileWrapper(output)   
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", direct_passthrough=True)
    

def get_total(product, location):
    imported = 0
    exported = 0
    imported_items = get_imported(product, location)
    if imported_items:
        for item in imported_items:
            imported += item.product_qty
    exported_items = get_exported(product, location)
    if exported_items:
        for item in exported_items:
            exported += item.product_qty
        print(exported)
    total = imported - exported
    return total


def get_imported(product, location):
    product = {'product_name': product}
    location = {'warehouse_location': location}
    imported = ProductMovement.query.filter_by(product_name=product.get('product_name')).filter_by(
        to_location=location.get('warehouse_location')).all()
    return imported

def get_exported(product, location):
    product = {'product_name': product}
    location = {'warehouse_location': location}
    exported = ProductMovement.query.filter_by(product_name=product.get('product_name')).filter_by(
        from_location=location.get('warehouse_location')).all()
    return exported


def get_product_data():
    products = Product.query.all()
    locations = Location.query.all()
    product_data = []
    for product in products:
        imported = 0
        exported = 0
        data = {}
        for location in locations:
            imported_items = get_imported(product.product_name, location.warehouse_location)
            if imported_items:
                for item in imported_items:
                    imported += item.product_qty
            exported_items = get_exported(product.product_name, location.warehouse_location)
            if exported_items:
                for item in exported_items:
                    exported += item.product_qty
            print(exported)
        total = imported - exported
        data['id'] = product.id
        data['product_name'] = product.product_name
        data['product_qty'] = total
        product_data.append(data)
    return product_data


def get_warehouse_data():
    products = Product.query.all()
    locations = Location.query.all()
    warehouse_data = []
    for location in locations:
        data= {}
        p_list = []
        for product in products:
            total = get_total(product.product_name,location.warehouse_location)
            if total > 0:
                p_list.append(product.product_name)
        product_list = ', '.join(p_list)
        data['id']= location.id
        data['warehouse_location'] = location.warehouse_location
        data['product_list']= product_list
        warehouse_data.append(data)
    return warehouse_data


def get_summary():
    summary = []
    products = Product.query.all()
    locations = Location.query.all()
    for product in products:
        for location in locations:
            data = {}
            prod_name = product.product_name
            loc_name = location.warehouse_location
            total = get_total(prod_name, loc_name)
            data['product'] = prod_name
            data['location'] = loc_name
            data['available_quantity'] = total
            summary.append(data)
    return summary

  
if __name__ == "__main__":
    db.create_all()
    app.run(debug=True)
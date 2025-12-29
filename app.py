import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import requests
from config import Config
from models import db, User, InventoryItem, Customer, Sale, SaleItem, Communication, DiseaseReport, Notification, WeatherData
import google.generativeai as genai
from PIL import Image
import io
import base64

app = Flask(__name__)
app.config.from_object(Config)

# Force PostgreSQL URL format for Render
if os.environ.get('RENDER'):
    database_url = app.config['SQLALCHEMY_DATABASE_URI']
    if database_url and database_url.startswith('postgres://'):
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace('postgres://', 'postgresql://', 1)

db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure Cohere
cohere_api_key = app.config['COHERE_API_KEY']

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Create database tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.user_type == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        elif current_user.user_type == 'agrovet':
            return redirect(url_for('agrovet_dashboard'))
        elif current_user.user_type == 'extension_officer':
            return redirect(url_for('officer_dashboard'))
        elif current_user.user_type == 'learning_institution':
            return redirect(url_for('institution_dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        user_type = request.form.get('user_type')
        phone_number = request.form.get('phone_number')
        location = request.form.get('location')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        user = User(
            email=email,
            full_name=full_name,
            user_type=user_type,
            phone_number=phone_number,
            location=location
        )
        user.set_password(password)
        
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{email}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                user.profile_picture = filename
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
    disease_reports = DiseaseReport.query.filter_by(farmer_id=current_user.id).order_by(DiseaseReport.created_at.desc()).limit(10).all()
    
    return render_template('farmer/dashboard.html', notifications=notifications, disease_reports=disease_reports)

@app.route('/farmer/detect-disease', methods=['GET', 'POST'])
@login_required
def detect_disease():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'plant_image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        file = request.files['plant_image']
        description = request.form.get('description', '')
        
        if file and allowed_file(file.filename):
            filename = secure_filename(f"plant_{current_user.id}_{datetime.utcnow().timestamp()}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                headers = {
                    'Authorization': f'Bearer {cohere_api_key}',
                    'Content-Type': 'application/json',
                }
                
                chat_payload = {
                    'model': 'c4ai-aya-expanse-8b',
                    'message': f"As an agricultural expert, analyze this plant health situation: {description}. Provide possible disease names, treatment recommendations, and prevention tips.",
                    'temperature': 0.7,
                    'max_tokens': 600
                }
                
                response = requests.post('https://api.cohere.ai/v1/chat', json=chat_payload, headers=headers)
                result = response.json()
                
                if response.status_code == 200 and 'text' in result:
                    analysis = result['text']
                else:
                    analysis = "Unable to analyze plant health at the moment. Please consult with an agricultural officer."
                
                report = DiseaseReport(
                    farmer_id=current_user.id,
                    plant_image=filename,
                    plant_description=description,
                    treatment_recommendation=analysis,
                    latitude=current_user.latitude,
                    longitude=current_user.longitude,
                    location=current_user.location
                )
                db.session.add(report)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'analysis': analysis,
                    'report_id': report.id
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
    
    return render_template('farmer/detect_disease.html')

@app.route('/farmer/weather')
@login_required
def farmer_weather():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    location = request.args.get('location', current_user.location or 'Nairobi')
    
    try:
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={app.config['OPENWEATHER_API_KEY']}&units=metric"
        response = requests.get(weather_url)
        weather_data = response.json()
        
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={location}&appid={app.config['OPENWEATHER_API_KEY']}&units=metric"
        forecast_response = requests.get(forecast_url)
        forecast_data = forecast_response.json()
        
        return render_template('farmer/weather.html', weather=weather_data, forecast=forecast_data)
    except Exception as e:
        flash(f'Error fetching weather data: {str(e)}', 'error')
        return render_template('farmer/weather.html', weather=None, forecast=None)

@app.route('/farmer/agrovets')
@login_required
def farmer_agrovets():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    agrovets = User.query.filter_by(user_type='agrovet', is_active=True).all()
    return render_template('farmer/agrovets.html', agrovets=agrovets)

@app.route('/agrovet/dashboard')
@login_required
def agrovet_dashboard():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    total_products = InventoryItem.query.filter_by(agrovet_id=current_user.id).count()
    low_stock_items = InventoryItem.query.filter_by(agrovet_id=current_user.id).filter(InventoryItem.quantity <= InventoryItem.reorder_level).count()
    total_customers = Customer.query.filter_by(agrovet_id=current_user.id).count()
    
    today = datetime.utcnow().date()
    today_sales = Sale.query.filter_by(agrovet_id=current_user.id).filter(db.func.date(Sale.sale_date) == today).all()
    today_revenue = sum(sale.total_amount for sale in today_sales)
    
    recent_sales = Sale.query.filter_by(agrovet_id=current_user.id).order_by(Sale.sale_date.desc()).limit(10).all()
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('agrovet/dashboard.html', 
                         total_products=total_products,
                         low_stock_items=low_stock_items,
                         total_customers=total_customers,
                         today_revenue=today_revenue,
                         recent_sales=recent_sales,
                         notifications=notifications)

@app.route('/agrovet/inventory')
@login_required
def agrovet_inventory():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    items = InventoryItem.query.filter_by(agrovet_id=current_user.id).all()
    return render_template('agrovet/inventory.html', items=items)

@app.route('/agrovet/inventory/add', methods=['GET', 'POST'])
@login_required
def add_inventory():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        item = InventoryItem(
            agrovet_id=current_user.id,
            product_name=request.form.get('product_name'),
            category=request.form.get('category'),
            description=request.form.get('description'),
            quantity=int(request.form.get('quantity', 0)),
            unit=request.form.get('unit'),
            price=float(request.form.get('price')),
            cost_price=float(request.form.get('cost_price', 0)),
            reorder_level=int(request.form.get('reorder_level', 10)),
            supplier=request.form.get('supplier'),
            sku=request.form.get('sku')
        )
        
        db.session.add(item)
        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('agrovet_inventory'))
    
    return render_template('agrovet/add_inventory.html')

@app.route('/agrovet/inventory/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_inventory(item_id):
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    item = InventoryItem.query.get_or_404(item_id)
    
    if item.agrovet_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('agrovet_inventory'))
    
    if request.method == 'POST':
        item.product_name = request.form.get('product_name')
        item.category = request.form.get('category')
        item.description = request.form.get('description')
        item.quantity = int(request.form.get('quantity', 0))
        item.unit = request.form.get('unit')
        item.price = float(request.form.get('price'))
        item.cost_price = float(request.form.get('cost_price', 0))
        item.reorder_level = int(request.form.get('reorder_level', 10))
        item.supplier = request.form.get('supplier')
        item.sku = request.form.get('sku')
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('agrovet_inventory'))
    
    return render_template('agrovet/edit_inventory.html', item=item)

@app.route('/agrovet/inventory/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_inventory(item_id):
    if current_user.user_type != 'agrovet':
        return jsonify({'error': 'Access denied'}), 403
    
    item = InventoryItem.query.get_or_404(item_id)
    
    if item.agrovet_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/agrovet/pos')
@login_required
def agrovet_pos():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    items = InventoryItem.query.filter_by(agrovet_id=current_user.id).filter(InventoryItem.quantity > 0).all()
    customers = Customer.query.filter_by(agrovet_id=current_user.id).all()
    return render_template('agrovet/pos.html', items=items, customers=customers)

@app.route('/agrovet/pos/checkout', methods=['POST'])
@login_required
def pos_checkout():
    if current_user.user_type != 'agrovet':
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    cart_items = data.get('items', [])
    customer_id = data.get('customer_id')
    payment_method = data.get('payment_method', 'cash')
    
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400
    
    total_amount = 0
    receipt_number = f"RCP{current_user.id}{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    sale = Sale(
        agrovet_id=current_user.id,
        customer_id=customer_id if customer_id else None,
        total_amount=0,
        payment_method=payment_method,
        receipt_number=receipt_number
    )
    db.session.add(sale)
    db.session.flush()
    
    for cart_item in cart_items:
        item = InventoryItem.query.get(cart_item['id'])
        if not item or item.agrovet_id != current_user.id:
            continue
        
        quantity = cart_item['quantity']
        if item.quantity < quantity:
            return jsonify({'error': f'Insufficient stock for {item.product_name}'}), 400
        
        subtotal = item.price * quantity
        total_amount += subtotal
        
        sale_item = SaleItem(
            sale_id=sale.id,
            product_name=item.product_name,
            quantity=quantity,
            unit_price=item.price,
            subtotal=subtotal
        )
        db.session.add(sale_item)
        
        item.quantity -= quantity
    
    sale.total_amount = total_amount
    
    if customer_id:
        customer = Customer.query.get(customer_id)
        if customer:
            customer.total_purchases += total_amount
            customer.last_purchase = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'receipt_number': receipt_number,
        'total_amount': total_amount,
        'sale_id': sale.id
    })

@app.route('/agrovet/crm')
@login_required
def agrovet_crm():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    customers = Customer.query.filter_by(agrovet_id=current_user.id).order_by(Customer.created_at.desc()).all()
    return render_template('agrovet/crm.html', customers=customers)

@app.route('/agrovet/crm/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        customer = Customer(
            agrovet_id=current_user.id,
            name=request.form.get('name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address=request.form.get('address'),
            customer_type=request.form.get('customer_type'),
            notes=request.form.get('notes')
        )
        
        db.session.add(customer)
        db.session.commit()
        
        flash('Customer added successfully!', 'success')
        return redirect(url_for('agrovet_crm'))
    
    return render_template('agrovet/add_customer.html')

@app.route('/agrovet/crm/view/<int:customer_id>')
@login_required
def view_customer(customer_id):
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    customer = Customer.query.get_or_404(customer_id)
    
    if customer.agrovet_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('agrovet_crm'))
    
    communications = Communication.query.filter_by(customer_id=customer_id).order_by(Communication.date.desc()).all()
    purchases = Sale.query.filter_by(customer_id=customer_id).order_by(Sale.sale_date.desc()).all()
    
    return render_template('agrovet/view_customer.html', customer=customer, communications=communications, purchases=purchases)

@app.route('/agrovet/crm/communication/<int:customer_id>', methods=['POST'])
@login_required
def add_communication(customer_id):
    if current_user.user_type != 'agrovet':
        return jsonify({'error': 'Access denied'}), 403
    
    customer = Customer.query.get_or_404(customer_id)
    
    if customer.agrovet_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    communication = Communication(
        customer_id=customer_id,
        communication_type=request.form.get('communication_type'),
        subject=request.form.get('subject'),
        message=request.form.get('message'),
        follow_up_date=datetime.strptime(request.form.get('follow_up_date'), '%Y-%m-%d') if request.form.get('follow_up_date') else None
    )
    
    db.session.add(communication)
    db.session.commit()
    
    flash('Communication log added successfully!', 'success')
    return redirect(url_for('view_customer', customer_id=customer_id))

@app.route('/officer/dashboard')
@login_required
def officer_dashboard():
    if current_user.user_type != 'extension_officer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    all_disease_reports = DiseaseReport.query.order_by(DiseaseReport.created_at.desc()).limit(50).all()
    farmers = User.query.filter_by(user_type='farmer').all()
    
    return render_template('officer/dashboard.html', disease_reports=all_disease_reports, farmers=farmers)

@app.route('/institution/dashboard')
@login_required
def institution_dashboard():
    if current_user.user_type != 'learning_institution':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    return render_template('institution/dashboard.html')

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json()
    message = data.get('message', '')
    
    if not message:
        return jsonify({'success': False, 'error': 'No message provided'})
    
    try:
        headers = {
            'Authorization': f'Bearer {cohere_api_key}',
            'Content-Type': 'application/json',
        }
        
        chat_payload = {
            'model': 'c4ai-aya-expanse-8b',
            'message': message,
            'temperature': 0.7,
            'max_tokens': 500,
            'preamble': 'You are a helpful agricultural assistant specializing in farming, crops, livestock, and agricultural practices. Provide practical, concise advice to farmers.'
        }
        
        response = requests.post('https://api.cohere.ai/v1/chat', json=chat_payload, headers=headers)
        result = response.json()
        
        if response.status_code == 200 and 'text' in result:
            ai_response = result['text']
        else:
            error_msg = result.get('message', 'Unknown error from Cohere API')
            return jsonify({
                'success': False,
                'error': f'Cohere API error: {error_msg}'
            })
        
        return jsonify({
            'success': True,
            'response': ai_response
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Chat service error: {str(e)}'
        })

@app.route('/test-api')
def test_api():
    try:
        headers = {
            'Authorization': f'Bearer {cohere_api_key}',
            'Content-Type': 'application/json',
        }
        
        test_payload = {
            'model': 'c4ai-aya-expanse-8b',
            'message': 'Please respond with "API test successful" if you are working.',
            'temperature': 0.7,
            'max_tokens': 20
        }
        
        response = requests.post('https://api.cohere.ai/v1/chat', json=test_payload, headers=headers)
        result = response.json()
        
        if response.status_code == 200 and 'text' in result:
            test_response = result['text']
            return f"Cohere API is working! Response: {test_response}"
        else:
            error_msg = result.get('message', 'Unknown error')
            return f"Cohere API error: {response.status_code} - {error_msg}"
            
    except Exception as e:
        return f"Cohere API Error: {str(e)}"

@app.route('/list-models')
def list_models():
    try:
        headers = {
            'Authorization': f'Bearer {cohere_api_key}',
            'Content-Type': 'application/json',
        }
        
        response = requests.get('https://api.cohere.ai/v1/models', headers=headers)
        result = response.json()
        
        if response.status_code == 200:
            models = result.get('models', [])
            model_list = "\n".join([f"- {model['name']}" for model in models])
            return f"Available Cohere models:\n{model_list}"
        else:
            return f"Error fetching models: {response.status_code} - {result}"
            
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/favicon.ico')
def favicon():
    return '', 404

@app.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'success': True})

@app.template_filter('datetime')
def format_datetime(value):
    if value is None:
        return ""
    return value.strftime('%Y-%m-%d %H:%M')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
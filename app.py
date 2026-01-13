import os
import json
import uuid
import math
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc, or_, and_, func, case
import requests
from models import db, User, InventoryItem, Customer, Sale, SaleItem, Communication, DiseaseReport, Notification, WeatherData, CommunityPost, PostAnswer, PostFollow, PostUpvote, AnswerUpvote, Cart, Order, Review, ProductReview, Message, AdminLog, SystemSetting, Banner, FAQ, Payment, MpesaTransaction
import google.generativeai as genai
from PIL import Image
import io
import base64
import secrets

app = Flask(__name__)
app.config.from_object('config.Config')

# Initialize extensions
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

# Create necessary directories
os.makedirs('uploads/products', exist_ok=True)
os.makedirs('uploads/profiles', exist_ok=True)
os.makedirs('uploads/posts', exist_ok=True)
os.makedirs('static/images', exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename, allowed_extensions=None):
    if allowed_extensions is None:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_file(file, folder='uploads'):
    if file and file.filename != '':
        filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return filename
    return None

def create_notification(user_id, title, message, notification_type='info', link=None, related_id=None):
    """Create a notification for a user"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
        related_id=related_id,
        is_read=False
    )
    db.session.add(notification)
    db.session.commit()
    return notification

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in kilometers"""
    if None in [lat1, lon1, lat2, lon2]:
        return None
    
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize database
with app.app_context():
    db.create_all()
    # Create admin user if not exists
    if not User.query.filter_by(email='admin@agriconnect.com').first():
        admin = User(
            email='admin@agriconnect.com',
            full_name='System Administrator',
            user_type='admin',
            is_admin=True,
            is_verified=True
        )
        admin.set_password('Admin@123')
        db.session.add(admin)
        db.session.commit()

# ==================== BASIC ROUTES ====================

@app.route('/')
def index():
    """Homepage"""
    # Get featured products
    featured_products = InventoryItem.query.filter_by(
        is_featured=True, 
        is_active=True
    ).order_by(desc(InventoryItem.created_at)).limit(8).all()
    
    # Get active banners
    banners = Banner.query.filter_by(is_active=True).order_by(Banner.position).all()
    
    # Get recent community posts
    recent_posts = CommunityPost.query.order_by(desc(CommunityPost.created_at)).limit(6).all()
    
    # Get top-rated agrovets
    top_agrovets = User.query.filter_by(
        user_type='agrovet', 
        is_active=True
    ).order_by(desc(User.rating)).limit(6).all()
    
    return render_template('index.html',
                         featured_products=featured_products,
                         banners=banners,
                         recent_posts=recent_posts,
                         top_agrovets=top_agrovets)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        user_type = request.form.get('user_type')
        phone_number = request.form.get('phone_number')
        location = request.form.get('location')
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        # Create user
        user = User(
            email=email,
            full_name=full_name,
            user_type=user_type,
            phone_number=phone_number,
            location=location
        )
        user.set_password(password)
        
        # Handle profile picture
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                filename = save_file(file, 'uploads/profiles')
                if filename:
                    user.profile_picture = filename
        
        # Additional fields for agrovets
        if user_type == 'agrovet':
            user.business_name = request.form.get('business_name')
            user.business_description = request.form.get('business_description')
            user.business_hours = request.form.get('business_hours')
            user.address = request.form.get('address')
        
        db.session.add(user)
        
        # Create cart for user
        cart = Cart(user_id=user.id)
        db.session.add(cart)
        
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account is deactivated. Please contact support.', 'danger')
                return redirect(url_for('login'))
            
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            flash(f'Welcome back, {user.full_name}!', 'success')
            
            # Redirect based on user type
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            elif user.user_type == 'farmer':
                return redirect(url_for('farmer_dashboard'))
            elif user.user_type == 'agrovet':
                return redirect(url_for('agrovet_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ==================== FARMER DASHBOARD ====================

@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    """Farmer dashboard"""
    if current_user.user_type != 'farmer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Get recent notifications
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Notification.created_at)).limit(10).all()
    
    # Get recent orders
    recent_orders = Order.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Order.created_at)).limit(5).all()
    
    # Get disease reports
    disease_reports = DiseaseReport.query.filter_by(
        farmer_id=current_user.id
    ).order_by(desc(DiseaseReport.created_at)).limit(5).all()
    
    # Get nearby agrovets
    nearby_agrovets = []
    if current_user.latitude and current_user.longitude:
        agrovets = User.query.filter_by(user_type='agrovet', is_active=True).all()
        for agrovet in agrovets:
            if agrovet.latitude and agrovet.longitude:
                distance = calculate_distance(
                    current_user.latitude, current_user.longitude,
                    agrovet.latitude, agrovet.longitude
                )
                if distance and distance <= 50:  # Within 50km
                    nearby_agrovets.append({
                        'agrovet': agrovet,
                        'distance': round(distance, 1)
                    })
        nearby_agrovets.sort(key=lambda x: x['distance'])
        nearby_agrovets = nearby_agrovets[:5]
    
    return render_template('farmer/dashboard.html',
                         notifications=notifications,
                         recent_orders=recent_orders,
                         disease_reports=disease_reports,
                         nearby_agrovets=nearby_agrovets)

@app.route('/farmer/detect-disease', methods=['GET', 'POST'])
@login_required
def detect_disease():
    """Disease detection for farmers"""
    if current_user.user_type != 'farmer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'plant_image' not in request.files:
            flash('No image uploaded', 'danger')
            return redirect(url_for('detect_disease'))
        
        file = request.files['plant_image']
        description = request.form.get('description', '')
        
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(url_for('detect_disease'))
        
        if file and allowed_file(file.filename):
            filename = save_file(file, 'uploads/disease')
            
            # Create disease report
            report = DiseaseReport(
                farmer_id=current_user.id,
                plant_image=filename,
                plant_description=description,
                location=current_user.location,
                latitude=current_user.latitude,
                longitude=current_user.longitude,
                status='pending'
            )
            
            db.session.add(report)
            db.session.commit()
            
            flash('Disease report submitted successfully. Analysis pending.', 'success')
            return redirect(url_for('farmer_dashboard'))
    
    return render_template('farmer/detect_disease.html')

@app.route('/farmer/weather')
@login_required
def farmer_weather():
    """Weather information for farmers"""
    if current_user.user_type != 'farmer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    location = request.args.get('location', current_user.location or 'Nairobi')
    
    try:
        # Get weather data (simplified - in production, use actual API)
        weather_data = {
            'location': location,
            'temperature': 25,
            'humidity': 65,
            'description': 'Partly Cloudy',
            'recommendations': 'Good day for planting. Consider irrigation if no rain.'
        }
        
        return render_template('farmer/weather.html', weather=weather_data)
    except Exception as e:
        flash(f'Error fetching weather data: {str(e)}', 'danger')
        return render_template('farmer/weather.html', weather=None)

# ==================== AGROVET DASHBOARD ====================

@app.route('/agrovet/dashboard')
@login_required
def agrovet_dashboard():
    """Agrovet dashboard"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Dashboard statistics
    total_products = InventoryItem.query.filter_by(agrovet_id=current_user.id).count()
    low_stock_items = InventoryItem.query.filter_by(
        agrovet_id=current_user.id
    ).filter(InventoryItem.quantity <= InventoryItem.reorder_level).count()
    total_customers = Customer.query.filter_by(agrovet_id=current_user.id).count()
    
    today = datetime.utcnow().date()
    today_sales = Sale.query.filter(
        Sale.agrovet_id == current_user.id,
        func.date(Sale.sale_date) == today
    ).all()
    today_revenue = sum(sale.total_amount for sale in today_sales)
    
    recent_orders = Order.query.filter_by(
        agrovet_id=current_user.id
    ).order_by(desc(Order.created_at)).limit(10).all()
    
    recent_messages = Message.query.filter_by(
        receiver_id=current_user.id
    ).order_by(desc(Message.created_at)).limit(5).all()
    
    return render_template('agrovet/dashboard.html',
                         total_products=total_products,
                         low_stock_items=low_stock_items,
                         total_customers=total_customers,
                         today_revenue=today_revenue,
                         recent_orders=recent_orders,
                         recent_messages=recent_messages)

@app.route('/agrovet/products')
@login_required
def agrovet_products():
    """Agrovet product management"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')
    
    query = InventoryItem.query.filter_by(agrovet_id=current_user.id)
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    if status == 'in_stock':
        query = query.filter(InventoryItem.quantity > 0)
    elif status == 'out_of_stock':
        query = query.filter(InventoryItem.quantity == 0)
    elif status == 'low_stock':
        query = query.filter(InventoryItem.quantity <= InventoryItem.reorder_level)
    
    if search:
        query = query.filter(or_(
            InventoryItem.product_name.ilike(f'%{search}%'),
            InventoryItem.description.ilike(f'%{search}%'),
            InventoryItem.sku.ilike(f'%{search}%')
        ))
    
    products = query.order_by(desc(InventoryItem.created_at)).all()
    
    categories = db.session.query(InventoryItem.category).filter_by(
        agrovet_id=current_user.id
    ).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('agrovet/products.html',
                         products=products,
                         categories=categories,
                         current_category=category,
                         search=search,
                         status=status)

@app.route('/agrovet/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    """Add new product"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            product = InventoryItem(
                agrovet_id=current_user.id,
                product_name=request.form.get('product_name'),
                category=request.form.get('category'),
                subcategory=request.form.get('subcategory'),
                description=request.form.get('description'),
                quantity=int(request.form.get('quantity', 0)),
                unit=request.form.get('unit'),
                price=float(request.form.get('price', 0)),
                cost_price=float(request.form.get('cost_price', 0)),
                discount_price=float(request.form.get('discount_price', 0)) or None,
                reorder_level=int(request.form.get('reorder_level', 10)),
                supplier=request.form.get('supplier'),
                sku=request.form.get('sku') or f"SKU-{uuid.uuid4().hex[:8].upper()}",
                barcode=request.form.get('barcode'),
                is_featured=bool(request.form.get('is_featured'))
            )
            
            # Handle image upload
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '':
                    filename = save_file(file, 'uploads/products')
                    if filename:
                        product.image = filename
            
            db.session.add(product)
            db.session.commit()
            
            flash('Product added successfully!', 'success')
            return redirect(url_for('agrovet_products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding product: {str(e)}', 'danger')
    
    return render_template('agrovet/add_product.html')

@app.route('/agrovet/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Edit product"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    product = InventoryItem.query.get_or_404(product_id)
    
    if product.agrovet_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('agrovet_products'))
    
    if request.method == 'POST':
        try:
            product.product_name = request.form.get('product_name')
            product.category = request.form.get('category')
            product.subcategory = request.form.get('subcategory')
            product.description = request.form.get('description')
            product.quantity = int(request.form.get('quantity', 0))
            product.unit = request.form.get('unit')
            product.price = float(request.form.get('price', 0))
            product.cost_price = float(request.form.get('cost_price', 0))
            product.discount_price = float(request.form.get('discount_price', 0)) or None
            product.reorder_level = int(request.form.get('reorder_level', 10))
            product.supplier = request.form.get('supplier')
            product.sku = request.form.get('sku')
            product.barcode = request.form.get('barcode')
            product.is_featured = bool(request.form.get('is_featured'))
            product.is_active = bool(request.form.get('is_active'))
            
            # Handle image upload
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '':
                    # Remove old image if exists
                    if product.image and os.path.exists(f'uploads/products/{product.image}'):
                        os.remove(f'uploads/products/{product.image}')
                    
                    filename = save_file(file, 'uploads/products')
                    if filename:
                        product.image = filename
            
            db.session.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('agrovet_products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'danger')
    
    return render_template('agrovet/edit_product.html', product=product)

@app.route('/agrovet/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete product"""
    if current_user.user_type != 'agrovet':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    product = InventoryItem.query.get_or_404(product_id)
    
    if product.agrovet_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        # Remove image if exists
        if product.image and os.path.exists(f'uploads/products/{product.image}'):
            os.remove(f'uploads/products/{product.image}')
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/agrovet/orders')
@login_required
def agrovet_orders():
    """Agrovet order management"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    
    query = Order.query.filter_by(agrovet_id=current_user.id)
    
    if status != 'all':
        query = query.filter_by(order_status=status)
    
    if search:
        query = query.filter(or_(
            Order.order_number.ilike(f'%{search}%'),
            Order.user.has(User.full_name.ilike(f'%{search}%')),
            Order.user.has(User.email.ilike(f'%{search}%'))
        ))
    
    orders = query.order_by(desc(Order.created_at)).all()
    
    return render_template('agrovet/orders.html', orders=orders, status=status, search=search)

@app.route('/agrovet/orders/<int:order_id>')
@login_required
def view_order(order_id):
    """View order details"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    order = Order.query.get_or_404(order_id)
    
    if order.agrovet_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('agrovet_orders'))
    
    return render_template('agrovet/view_order.html', order=order)

@app.route('/agrovet/orders/update-status/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    """Update order status"""
    if current_user.user_type != 'agrovet':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    order = Order.query.get_or_404(order_id)
    
    if order.agrovet_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    new_status = request.json.get('status')
    
    if new_status not in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400
    
    order.order_status = new_status
    order.updated_at = datetime.utcnow()
    
    # Create notification for customer
    create_notification(
        user_id=order.user_id,
        title=f'Order Status Updated',
        message=f'Your order #{order.order_number} status has been updated to {new_status}.',
        notification_type='info',
        link=f'/orders/{order.id}',
        related_id=order.id
    )
    
    db.session.commit()
    
    return jsonify({'success': True, 'new_status': new_status})

# ==================== E-COMMERCE ROUTES ====================

@app.route('/marketplace')
def marketplace():
    """Marketplace - Browse all products"""
    category = request.args.get('category', 'all')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    location = request.args.get('location', '')
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'newest')
    
    query = InventoryItem.query.filter_by(is_active=True)
    
    # Apply filters
    if category != 'all' and category:
        query = query.filter_by(category=category)
    
    if min_price is not None:
        query = query.filter(InventoryItem.current_price >= min_price)
    
    if max_price is not None:
        query = query.filter(InventoryItem.current_price <= max_price)
    
    if location:
        query = query.join(User).filter(
            User.location.ilike(f'%{location}%'),
            User.user_type == 'agrovet',
            User.is_active == True
        )
    
    if search:
        query = query.filter(or_(
            InventoryItem.product_name.ilike(f'%{search}%'),
            InventoryItem.description.ilike(f'%{search}%'),
            InventoryItem.category.ilike(f'%{search}%'),
            InventoryItem.agrovet.has(User.business_name.ilike(f'%{search}%'))
        ))
    
    # Apply sorting
    if sort == 'price_low':
        query = query.order_by(InventoryItem.current_price)
    elif sort == 'price_high':
        query = query.order_by(desc(InventoryItem.current_price))
    elif sort == 'rating':
        query = query.order_by(desc(InventoryItem.rating))
    elif sort == 'popular':
        query = query.order_by(desc(InventoryItem.total_reviews))
    else:  # newest
        query = query.order_by(desc(InventoryItem.created_at))
    
    products = query.paginate(page=request.args.get('page', 1, type=int), per_page=12)
    
    # Get categories
    categories = db.session.query(InventoryItem.category).filter_by(
        is_active=True
    ).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('marketplace.html',
                         products=products,
                         categories=categories,
                         current_category=category,
                         search=search,
                         location=location,
                         min_price=min_price,
                         max_price=max_price,
                         sort=sort)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Product detail page"""
    product = InventoryItem.query.get_or_404(product_id)
    
    if not product.is_active:
        flash('This product is not available', 'warning')
        return redirect(url_for('marketplace'))
    
    # Get related products
    related_products = InventoryItem.query.filter(
        InventoryItem.category == product.category,
        InventoryItem.id != product.id,
        InventoryItem.is_active == True
    ).limit(4).all()
    
    # Get product reviews
    reviews = ProductReview.query.filter_by(product_id=product_id).order_by(
        desc(ProductReview.created_at)
    ).all()
    
    # Get agrovet details
    agrovet = User.query.get(product.agrovet_id)
    
    return render_template('product_detail.html',
                         product=product,
                         related_products=related_products,
                         reviews=reviews,
                         agrovet=agrovet)

@app.route('/agrovet/<int:agrovet_id>')
def agrovet_detail(agrovet_id):
    """Agrovet detail page"""
    agrovet = User.query.get_or_404(agrovet_id)
    
    if agrovet.user_type != 'agrovet' or not agrovet.is_active:
        flash('Agrovet not found', 'danger')
        return redirect(url_for('marketplace'))
    
    # Get agrovet products
    products = InventoryItem.query.filter_by(
        agrovet_id=agrovet_id,
        is_active=True
    ).order_by(desc(InventoryItem.created_at)).all()
    
    # Get agrovet reviews
    reviews = Review.query.filter_by(agrovet_id=agrovet_id).order_by(
        desc(Review.created_at)
    ).all()
    
    # Calculate distance if user is logged in and has location
    distance = None
    if current_user.is_authenticated and current_user.latitude and current_user.longitude:
        if agrovet.latitude and agrovet.longitude:
            distance = calculate_distance(
                current_user.latitude, current_user.longitude,
                agrovet.latitude, agrovet.longitude
            )
    
    return render_template('agrovet_detail.html',
                         agrovet=agrovet,
                         products=products,
                         reviews=reviews,
                         distance=distance)

@app.route('/cart')
@login_required
def view_cart():
    """View shopping cart"""
    cart = current_user.cart
    
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    
    cart_items = []
    total_price = 0
    
    for item in cart.cart_items:
        product = InventoryItem.query.get(item.product_id)
        if product and product.is_active:
            item_total = product.current_price * item.quantity
            total_price += item_total
            
            cart_items.append({
                'product': product,
                'quantity': item.quantity,
                'total': item_total
            })
    
    return render_template('cart.html',
                         cart_items=cart_items,
                         total_price=total_price)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    """Add product to cart"""
    product = InventoryItem.query.get_or_404(product_id)
    
    if not product.is_active or product.quantity <= 0:
        return jsonify({'success': False, 'error': 'Product not available'}), 400
    
    cart = current_user.cart
    
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    
    # Check if product is already in cart
    existing_item = db.session.query(cart_items).filter_by(
        cart_id=cart.id,
        product_id=product_id
    ).first()
    
    if existing_item:
        # Update quantity
        new_quantity = existing_item.quantity + 1
        if new_quantity > product.quantity:
            return jsonify({'success': False, 'error': 'Not enough stock'}), 400
        
        db.session.execute(
            cart_items.update().where(
                (cart_items.c.cart_id == cart.id) &
                (cart_items.c.product_id == product_id)
            ).values(quantity=new_quantity)
        )
    else:
        # Add new item
        db.session.execute(
            cart_items.insert().values(
                cart_id=cart.id,
                product_id=product_id,
                quantity=1
            )
        )
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Product added to cart'})

@app.route('/cart/update/<int:product_id>', methods=['POST'])
@login_required
def update_cart_item(product_id):
    """Update cart item quantity"""
    quantity = request.json.get('quantity', 1)
    
    if quantity < 1:
        return jsonify({'success': False, 'error': 'Invalid quantity'}), 400
    
    product = InventoryItem.query.get_or_404(product_id)
    
    if quantity > product.quantity:
        return jsonify({'success': False, 'error': 'Not enough stock'}), 400
    
    cart = current_user.cart
    
    if not cart:
        return jsonify({'success': False, 'error': 'Cart not found'}), 404
    
    db.session.execute(
        cart_items.update().where(
            (cart_items.c.cart_id == cart.id) &
            (cart_items.c.product_id == product_id)
        ).values(quantity=quantity)
    )
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/cart/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_from_cart(product_id):
    """Remove product from cart"""
    cart = current_user.cart
    
    if not cart:
        return jsonify({'success': False, 'error': 'Cart not found'}), 404
    
    db.session.execute(
        cart_items.delete().where(
            (cart_items.c.cart_id == cart.id) &
            (cart_items.c.product_id == product_id)
        )
    )
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Checkout process"""
    cart = current_user.cart
    
    if not cart or len(cart.cart_items) == 0:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('view_cart'))
    
    # Group products by agrovet
    agrovet_carts = {}
    
    for item in cart.cart_items:
        product = InventoryItem.query.get(item.product_id)
        if not product or not product.is_active:
            continue
        
        if product.agrovet_id not in agrovet_carts:
            agrovet = User.query.get(product.agrovet_id)
            agrovet_carts[product.agrovet_id] = {
                'agrovet': agrovet,
                'items': [],
                'subtotal': 0
            }
        
        item_total = product.current_price * item.quantity
        agrovet_carts[product.agrovet_id]['items'].append({
            'product': product,
            'quantity': item.quantity,
            'total': item_total
        })
        agrovet_carts[product.agrovet_id]['subtotal'] += item_total
    
    if request.method == 'POST':
        try:
            shipping_address = request.form.get('shipping_address')
            payment_method = request.form.get('payment_method')
            notes = request.form.get('notes')
            
            if not shipping_address:
                flash('Shipping address is required', 'danger')
                return redirect(url_for('checkout'))
            
            orders = []
            
            # Create separate order for each agrovet
            for agrovet_id, cart_data in agrovet_carts.items():
                order = Order(
                    order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
                    user_id=current_user.id,
                    agrovet_id=agrovet_id,
                    total_amount=cart_data['subtotal'],
                    shipping_address=shipping_address,
                    billing_address=request.form.get('billing_address', shipping_address),
                    payment_method=payment_method,
                    notes=notes
                )
                
                db.session.add(order)
                db.session.flush()  # Get order ID
                
                # Add order items
                for item in cart_data['items']:
                    product = item['product']
                    
                    # Check stock again
                    if item['quantity'] > product.quantity:
                        db.session.rollback()
                        flash(f'Not enough stock for {product.product_name}', 'danger')
                        return redirect(url_for('checkout'))
                    
                    # Reduce stock
                    product.quantity -= item['quantity']
                    
                    # Add to order items
                    db.session.execute(
                        order_items.insert().values(
                            order_id=order.id,
                            product_id=product.id,
                            quantity=item['quantity'],
                            unit_price=product.current_price,
                            subtotal=item['total']
                        )
                    )
                
                orders.append(order)
                
                # Create notification for agrovet
                create_notification(
                    user_id=agrovet_id,
                    title='New Order Received',
                    message=f'You have received a new order #{order.order_number} from {current_user.full_name}.',
                    notification_type='success',
                    link=f'/agrovet/orders/{order.id}',
                    related_id=order.id
                )
            
            # Clear cart
            db.session.execute(
                cart_items.delete().where(cart_items.c.cart_id == cart.id)
            )
            
            db.session.commit()
            
            flash('Order placed successfully!', 'success')
            
            # Redirect to payment if needed
            if payment_method == 'mpesa':
                return redirect(url_for('process_mpesa_payment', order_id=orders[0].id))
            else:
                return redirect(url_for('order_confirmation', order_id=orders[0].id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing order: {str(e)}', 'danger')
    
    return render_template('checkout.html', agrovet_carts=agrovet_carts)

@app.route('/orders')
@login_required
def my_orders():
    """User order history"""
    orders = Order.query.filter_by(user_id=current_user.id).order_by(
        desc(Order.created_at)
    ).all()
    
    return render_template('orders.html', orders=orders)

@app.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    """Order details"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('my_orders'))
    
    return render_template('order_detail.html', order=order)

# ==================== MESSAGING SYSTEM ====================

@app.route('/messages')
@login_required
def messages():
    """User messages"""
    conversation_id = request.args.get('conversation_id', type=int)
    
    # Get conversations
    conversations = Message.query.filter(
        or_(
            Message.sender_id == current_user.id,
            Message.receiver_id == current_user.id
        )
    ).order_by(desc(Message.created_at)).all()
    
    # Group by other user
    conversation_dict = {}
    for msg in conversations:
        other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        other_user = User.query.get(other_id)
        
        if other_id not in conversation_dict:
            conversation_dict[other_id] = {
                'user': other_user,
                'last_message': msg,
                'unread_count': 0
            }
        
        if msg.receiver_id == current_user.id and not msg.is_read:
            conversation_dict[other_id]['unread_count'] += 1
    
    conversations_list = list(conversation_dict.values())
    conversations_list.sort(key=lambda x: x['last_message'].created_at, reverse=True)
    
    # Get messages for specific conversation
    conversation_messages = []
    other_user = None
    
    if conversation_id:
        other_user = User.query.get(conversation_id)
        if other_user:
            conversation_messages = Message.query.filter(
                or_(
                    and_(Message.sender_id == current_user.id, Message.receiver_id == conversation_id),
                    and_(Message.sender_id == conversation_id, Message.receiver_id == current_user.id)
                )
            ).order_by(Message.created_at).all()
            
            # Mark messages as read
            for msg in conversation_messages:
                if msg.receiver_id == current_user.id and not msg.is_read:
                    msg.is_read = True
            db.session.commit()
    
    return render_template('messages.html',
                         conversations=conversations_list,
                         conversation_messages=conversation_messages,
                         other_user=other_user)

@app.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    """Send a message"""
    receiver_id = request.json.get('receiver_id')
    content = request.json.get('content')
    product_id = request.json.get('product_id', type=int)
    order_id = request.json.get('order_id', type=int)
    
    if not receiver_id or not content:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'success': False, 'error': 'Receiver not found'}), 404
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        product_id=product_id,
        order_id=order_id
    )
    
    db.session.add(message)
    db.session.commit()
    
    # Create notification for receiver
    create_notification(
        user_id=receiver_id,
        title='New Message',
        message=f'You have received a new message from {current_user.full_name}.',
        notification_type='info',
        link=f'/messages?conversation_id={current_user.id}',
        related_id=message.id
    )
    
    return jsonify({'success': True, 'message_id': message.id})

@app.route('/messages/contact-agrovet/<int:agrovet_id>', methods=['POST'])
@login_required
def contact_agrovet(agrovet_id):
    """Contact agrovet directly"""
    agrovet = User.query.get_or_404(agrovet_id)
    
    if agrovet.user_type != 'agrovet':
        return jsonify({'success': False, 'error': 'User is not an agrovet'}), 400
    
    content = request.json.get('content')
    product_id = request.json.get('product_id', type=int)
    
    if not content:
        return jsonify({'success': False, 'error': 'Message content is required'}), 400
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=agrovet_id,
        content=content,
        product_id=product_id
    )
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Message sent successfully'})

# ==================== COMMUNITY ROUTES ====================

@app.route('/community')
def community_home():
    """Community homepage"""
    category = request.args.get('category', 'all')
    post_type = request.args.get('type', 'all')
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'newest')
    
    query = CommunityPost.query
    
    # Apply filters
    if category != 'all' and category:
        query = query.filter_by(category=category)
    
    if post_type != 'all' and post_type:
        query = query.filter_by(post_type=post_type)
    
    if search:
        query = query.filter(or_(
            CommunityPost.title.ilike(f'%{search}%'),
            CommunityPost.content.ilike(f'%{search}%'),
            CommunityPost.tags.ilike(f'%{search}%')
        ))
    
    # Apply sorting
    if sort == 'popular':
        query = query.order_by(desc(CommunityPost.views))
    elif sort == 'most_answered':
        subquery = db.session.query(
            PostAnswer.post_id,
            func.count('*').label('answer_count')
        ).group_by(PostAnswer.post_id).subquery()
        
        query = query.outerjoin(subquery, CommunityPost.id == subquery.c.post_id).order_by(
            desc(subquery.c.answer_count),
            desc(CommunityPost.created_at)
        )
    else:  # newest
        query = query.order_by(desc(CommunityPost.created_at))
    
    posts = query.paginate(page=request.args.get('page', 1, type=int), per_page=15)
    
    # Get categories
    categories = db.session.query(CommunityPost.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('community/home.html',
                         posts=posts,
                         categories=categories,
                         current_category=category,
                         current_type=post_type,
                         search=search,
                         sort=sort)

@app.route('/community/create', methods=['GET', 'POST'])
@login_required
def create_community_post():
    """Create community post"""
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        post_type = request.form.get('post_type', 'question')
        category = request.form.get('category', 'general')
        tags = request.form.get('tags', '')
        
        if not title or not content:
            flash('Title and content are required', 'danger')
            return redirect(url_for('create_community_post'))
        
        post = CommunityPost(
            user_id=current_user.id,
            title=title,
            content=content,
            post_type=post_type,
            category=category,
            tags=tags
        )
        
        db.session.add(post)
        
        # Auto-follow own post
        follow = PostFollow(post=post, user_id=current_user.id)
        db.session.add(follow)
        
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('view_community_post', post_id=post.id))
    
    return render_template('community/create_post.html')

@app.route('/community/post/<int:post_id>')
def view_community_post(post_id):
    """View community post"""
    post = CommunityPost.query.get_or_404(post_id)
    
    # Increment view count
    post.views += 1
    
    # Check if user is following
    is_following = False
    if current_user.is_authenticated:
        is_following = PostFollow.query.filter_by(
            post_id=post_id,
            user_id=current_user.id
        ).first() is not None
    
    # Check if user has upvoted
    has_upvoted = False
    if current_user.is_authenticated:
        has_upvoted = PostUpvote.query.filter_by(
            post_id=post_id,
            user_id=current_user.id
        ).first() is not None
    
    # Get answers
    answers = PostAnswer.query.filter_by(post_id=post_id).order_by(
        desc(PostAnswer.is_accepted),
        desc(PostAnswer.created_at)
    ).all()
    
    # Check answer upvotes
    answer_upvotes = {}
    if current_user.is_authenticated:
        for answer in answers:
            answer_upvotes[answer.id] = AnswerUpvote.query.filter_by(
                answer_id=answer.id,
                user_id=current_user.id
            ).first() is not None
    
    db.session.commit()
    
    return render_template('community/view_post.html',
                         post=post,
                         answers=answers,
                         is_following=is_following,
                         has_upvoted=has_upvoted,
                         answer_upvotes=answer_upvotes)

@app.route('/community/post/<int:post_id>/answer', methods=['POST'])
@login_required
def add_post_answer(post_id):
    """Add answer to post"""
    post = CommunityPost.query.get_or_404(post_id)
    
    content = request.form.get('content')
    
    if not content:
        flash('Answer content is required', 'danger')
        return redirect(url_for('view_community_post', post_id=post_id))
    
    answer = PostAnswer(
        post_id=post_id,
        user_id=current_user.id,
        content=content
    )
    
    db.session.add(answer)
    
    # Notify post author if not the same user
    if post.user_id != current_user.id:
        create_notification(
            user_id=post.user_id,
            title='New Answer on Your Post',
            message=f'{current_user.full_name} answered your post: "{post.title}"',
            notification_type='info',
            link=f'/community/post/{post_id}',
            related_id=post_id
        )
    
    # Notify followers
    followers = PostFollow.query.filter_by(post_id=post_id).all()
    for follower in followers:
        if follower.user_id != current_user.id and follower.user_id != post.user_id:
            create_notification(
                user_id=follower.user_id,
                title='New Answer on Post You Follow',
                message=f'{current_user.full_name} answered a post you follow: "{post.title}"',
                notification_type='info',
                link=f'/community/post/{post_id}',
                related_id=post_id
            )
    
    db.session.commit()
    
    flash('Answer posted successfully!', 'success')
    return redirect(url_for('view_community_post', post_id=post_id))

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login"""
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email, is_admin=True).first()
        
        if user and user.check_password(password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'danger')
    
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    # Statistics
    total_users = User.query.count()
    total_farmers = User.query.filter_by(user_type='farmer').count()
    total_agrovets = User.query.filter_by(user_type='agrovet').count()
    total_products = InventoryItem.query.count()
    total_orders = Order.query.count()
    
    # Recent users
    recent_users = User.query.order_by(desc(User.created_at)).limit(10).all()
    
    # Recent orders
    recent_orders = Order.query.order_by(desc(Order.created_at)).limit(10).all()
    
    # Active users (last 24 hours)
    active_users = User.query.filter(
        User.last_login >= datetime.utcnow() - timedelta(hours=24)
    ).count()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_farmers=total_farmers,
                         total_agrovets=total_agrovets,
                         total_products=total_products,
                         total_orders=total_orders,
                         active_users=active_users,
                         recent_users=recent_users,
                         recent_orders=recent_orders)

@app.route('/admin/users')
@admin_required
def admin_users():
    """Admin user management"""
    user_type = request.args.get('type', 'all')
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    
    query = User.query
    
    if user_type != 'all':
        query = query.filter_by(user_type=user_type)
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    if search:
        query = query.filter(or_(
            User.email.ilike(f'%{search}%'),
            User.full_name.ilike(f'%{search}%'),
            User.phone_number.ilike(f'%{search}%')
        ))
    
    users = query.order_by(desc(User.created_at)).all()
    
    return render_template('admin/users.html',
                         users=users,
                         user_type=user_type,
                         status=status,
                         search=search)

@app.route('/admin/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    
    user.is_active = not user.is_active
    db.session.commit()
    
    action = 'activated' if user.is_active else 'deactivated'
    flash(f'User {action} successfully', 'success')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/make-admin', methods=['POST'])
@admin_required
def make_user_admin(user_id):
    """Make user admin"""
    user = User.query.get_or_404(user_id)
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    action = 'added to' if user.is_admin else 'removed from'
    flash(f'User {action} administrators', 'success')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/products')
@admin_required
def admin_products():
    """Admin product management"""
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    
    query = InventoryItem.query
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    elif status == 'low_stock':
        query = query.filter(InventoryItem.quantity <= InventoryItem.reorder_level)
    elif status == 'out_of_stock':
        query = query.filter(InventoryItem.quantity == 0)
    
    if search:
        query = query.filter(or_(
            InventoryItem.product_name.ilike(f'%{search}%'),
            InventoryItem.sku.ilike(f'%{search}%'),
            InventoryItem.agrovet.has(User.business_name.ilike(f'%{search}%'))
        ))
    
    products = query.order_by(desc(InventoryItem.created_at)).all()
    
    return render_template('admin/products.html',
                         products=products,
                         status=status,
                         search=search)

@app.route('/admin/orders')
@admin_required
def admin_orders():
    """Admin order management"""
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    
    query = Order.query
    
    if status != 'all':
        query = query.filter_by(order_status=status)
    
    if search:
        query = query.filter(or_(
            Order.order_number.ilike(f'%{search}%'),
            Order.user.has(User.full_name.ilike(f'%{search}%')),
            Order.agrovet.has(User.business_name.ilike(f'%{search}%'))
        ))
    
    orders = query.order_by(desc(Order.created_at)).all()
    
    return render_template('admin/orders.html',
                         orders=orders,
                         status=status,
                         search=search)

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    """Admin system settings"""
    if request.method == 'POST':
        for key in request.form:
            if key.startswith('setting_'):
                setting_key = key.replace('setting_', '')
                value = request.form.get(key)
                
                setting = SystemSetting.query.filter_by(key=setting_key).first()
                if setting:
                    setting.value = value
                else:
                    setting = SystemSetting(key=setting_key, value=value)
                    db.session.add(setting)
        
        db.session.commit()
        flash('Settings updated successfully', 'success')
    
    settings = SystemSetting.query.all()
    return render_template('admin/settings.html', settings=settings)

# ==================== UTILITY ROUTES ====================

@app.route('/search')
def search():
    """Global search"""
    query = request.args.get('q', '')
    
    if not query:
        return redirect(url_for('index'))
    
    # Search products
    products = InventoryItem.query.filter(
        InventoryItem.is_active == True,
        or_(
            InventoryItem.product_name.ilike(f'%{query}%'),
            InventoryItem.description.ilike(f'%{query}%'),
            InventoryItem.category.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    # Search agrovets
    agrovets = User.query.filter(
        User.user_type == 'agrovet',
        User.is_active == True,
        or_(
            User.business_name.ilike(f'%{query}%'),
            User.full_name.ilike(f'%{query}%'),
            User.location.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    # Search community posts
    posts = CommunityPost.query.filter(
        or_(
            CommunityPost.title.ilike(f'%{query}%'),
            CommunityPost.content.ilike(f'%{query}%'),
            CommunityPost.tags.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    return render_template('search.html',
                         query=query,
                         products=products,
                         agrovets=agrovets,
                         posts=posts)

@app.route('/profile')
@login_required
def profile():
    """User profile"""
    # Get user statistics
    order_stats = current_user.order_stats
    community_stats = current_user.community_stats
    
    # Get recent activity
    recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(
        desc(Order.created_at)
    ).limit(5).all()
    
    recent_posts = CommunityPost.query.filter_by(user_id=current_user.id).order_by(
        desc(CommunityPost.created_at)
    ).limit(5).all()
    
    return render_template('profile.html',
                         order_stats=order_stats,
                         community_stats=community_stats,
                         recent_orders=recent_orders,
                         recent_posts=recent_posts)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.phone_number = request.form.get('phone_number')
        current_user.location = request.form.get('location')
        current_user.address = request.form.get('address')
        
        # Update latitude/longitude if location changed
        # In production, use geocoding API here
        
        # Handle profile picture
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                filename = save_file(file, 'uploads/profiles')
                if filename:
                    # Delete old profile picture if exists
                    if current_user.profile_picture and current_user.profile_picture != 'default-avatar.png':
                        old_path = f'uploads/profiles/{current_user.profile_picture}'
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    current_user.profile_picture = filename
        
        # Update agrovet business info
        if current_user.user_type == 'agrovet':
            current_user.business_name = request.form.get('business_name')
            current_user.business_description = request.form.get('business_description')
            current_user.business_hours = request.form.get('business_hours')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html')

@app.route('/notifications')
@login_required
def notifications():
    """User notifications"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Notification.created_at)).all()
    
    # Mark all as read
    for notification in notifications:
        if not notification.is_read:
            notification.is_read = True
    
    db.session.commit()
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/clear', methods=['POST'])
@login_required
def clear_notifications():
    """Clear all notifications"""
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    
    return jsonify({'success': True})

# ==================== FILE UPLOADS ====================

@app.route('/uploads/<path:filename>')
def uploaded_files(filename):
    """Serve uploaded files"""
    return send_from_directory('uploads', filename)

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

# ==================== HELPER FUNCTIONS ====================

def init_app():
    """Initialize the application"""
    with app.app_context():
        db.create_all()
        
        # Create default admin user
        if not User.query.filter_by(email='admin@agriconnect.com').first():
            admin = User(
                email='admin@agriconnect.com',
                full_name='System Administrator',
                user_type='admin',
                is_admin=True,
                is_verified=True
            )
            admin.set_password('Admin@123')
            db.session.add(admin)
            
            # Create default settings
            default_settings = [
                ('site_name', 'AgriConnect', 'Website name'),
                ('site_description', 'Connecting Farmers and Agrovets', 'Website description'),
                ('contact_email', 'support@agriconnect.com', 'Contact email'),
                ('contact_phone', '+254 700 000 000', 'Contact phone'),
                ('currency', 'KES', 'Default currency'),
                ('tax_rate', '0.16', 'Tax rate (16% VAT)'),
                ('shipping_fee', '200', 'Default shipping fee'),
                ('free_shipping_threshold', '5000', 'Minimum order for free shipping'),
            ]
            
            for key, value, description in default_settings:
                setting = SystemSetting(key=key, value=value, description=description)
                db.session.add(setting)
            
            db.session.commit()

if __name__ == '__main__':
    init_app()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

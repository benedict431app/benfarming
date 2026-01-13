import os
import uuid
import math
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc, or_, and_, func, text
from sqlalchemy.exc import OperationalError
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
from models import db
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Create necessary directories
os.makedirs('uploads/products', exist_ok=True)
os.makedirs('uploads/profiles', exist_ok=True)

# ==================== DATABASE INITIALIZATION ====================

def init_database():
    """Initialize the SQLite database"""
    with app.app_context():
        try:
            print(f"📊 Initializing SQLite database: {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully")
            
            from models import User, Cart, SystemSetting
            
            # Create default admin user if not exists
            if not User.query.filter_by(email='admin@agriconnect.com').first():
                admin = User(
                    email='admin@agriconnect.com',
                    full_name='System Administrator',
                    user_type='admin',
                    is_admin=True,
                    is_verified=True,
                    is_active=True,
                    profile_picture='default-avatar.png'
                )
                admin.set_password('Admin@123')
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin user created: admin@agriconnect.com / Admin@123")
            
            # Create default system settings
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
                if not SystemSetting.query.filter_by(key=key).first():
                    setting = SystemSetting(key=key, value=value, description=description)
                    db.session.add(setting)
            
            db.session.commit()
            print("✅ Database initialization complete!")
            
            # Add some sample data for testing
            add_sample_data()
            
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

def add_sample_data():
    """Add sample data for testing"""
    from models import User, InventoryItem
    
    # Check if we already have sample data
    if User.query.filter_by(user_type='farmer').count() == 0:
        # Create sample farmer
        farmer = User(
            email='farmer@example.com',
            full_name='John Farmer',
            user_type='farmer',
            phone_number='+254712345678',
            location='Nairobi',
            is_active=True,
            profile_picture='default-avatar.png'
        )
        farmer.set_password('Farmer@123')
        db.session.add(farmer)
        
        # Create sample agrovet
        agrovet = User(
            email='agrovet@example.com',
            full_name='Green Agro Supplies',
            user_type='agrovet',
            phone_number='+254723456789',
            location='Nakuru',
            business_name='Green Agro Supplies',
            business_description='Your trusted agricultural supplier',
            is_active=True,
            profile_picture='default-avatar.png'
        )
        agrovet.set_password('Agrovet@123')
        db.session.add(agrovet)
        
        db.session.commit()
        
        # Create sample products
        sample_products = [
            {
                'agrovet_id': agrovet.id,
                'product_name': 'Maize Seeds (Hybrid)',
                'category': 'Seeds',
                'description': 'High-yield hybrid maize seeds, 1kg pack',
                'quantity': 100,
                'price': 450.00,
                'unit': 'kg',
                'is_active': True
            },
            {
                'agrovet_id': agrovet.id,
                'product_name': 'NPK Fertilizer',
                'category': 'Fertilizers',
                'description': 'Balanced NPK fertilizer 50kg bag',
                'quantity': 50,
                'price': 3500.00,
                'unit': 'bag',
                'is_active': True
            },
            {
                'agrovet_id': agrovet.id,
                'product_name': 'Pesticide Spray',
                'category': 'Chemicals',
                'description': 'Broad-spectrum pesticide 1 liter',
                'quantity': 80,
                'price': 850.00,
                'unit': 'liter',
                'is_active': True
            },
            {
                'agrovet_id': agrovet.id,
                'product_name': 'Garden Hoe',
                'category': 'Tools',
                'description': 'Stainless steel garden hoe',
                'quantity': 30,
                'price': 750.00,
                'unit': 'piece',
                'is_active': True
            }
        ]
        
        for product_data in sample_products:
            product = InventoryItem(**product_data)
            db.session.add(product)
        
        db.session.commit()
        print("✅ Sample data added successfully")

# ==================== BASIC ROUTES ====================

@app.route('/')
def index():
    """Homepage"""
    try:
        from models import InventoryItem, CommunityPost
        
        # Get featured products
        featured_products = InventoryItem.query.filter_by(
            is_active=True
        ).order_by(desc(InventoryItem.created_at)).limit(8).all()
        
        # Get recent community posts
        recent_posts = CommunityPost.query.order_by(desc(CommunityPost.created_at)).limit(6).all()
        
        return render_template('index.html',
                             featured_products=featured_products,
                             recent_posts=recent_posts)
    except Exception as e:
        print(f"Error loading homepage: {e}")
        # If database error, show setup page
        return render_template('setup.html')

@app.route('/setup')
def setup():
    """Setup page for initial database setup"""
    return render_template('setup.html')

@app.route('/init', methods=['POST'])
def init_system():
    """Initialize the system (for manual setup)"""
    try:
        if init_database():
            flash('System initialized successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('System initialization failed', 'danger')
            return redirect(url_for('setup'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('setup'))

# ==================== USER AUTHENTICATION ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    from models import User, Cart
    
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            full_name = request.form.get('full_name')
            user_type = request.form.get('user_type')
            phone_number = request.form.get('phone_number')
            location = request.form.get('location')
            
            # Validation
            if not email or not password or not full_name or not user_type:
                flash('All fields are required', 'danger')
                return redirect(url_for('register'))
            
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
                location=location,
                is_active=True,
                profile_picture='default-avatar.png'
            )
            user.set_password(password)
            
            # Additional fields for agrovets
            if user_type == 'agrovet':
                user.business_name = request.form.get('business_name', '')
                user.business_description = request.form.get('business_description', '')
            
            db.session.add(user)
            db.session.commit()
            
            # Create cart for user
            cart = Cart(user_id=user.id)
            db.session.add(cart)
            db.session.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration error: {str(e)}', 'danger')
            return redirect(url_for('register'))
    
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    from models import User
    
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
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
                
        except Exception as e:
            flash(f'Login error: {str(e)}', 'danger')
    
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
    
    from models import Notification, Order, CommunityPost
    
    # Get recent notifications
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Notification.created_at)).limit(10).all()
    
    # Get recent orders
    recent_orders = Order.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Order.created_at)).limit(5).all()
    
    # Get recent community posts
    recent_posts = CommunityPost.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(CommunityPost.created_at)).limit(5).all()
    
    return render_template('farmer/dashboard.html',
                         notifications=notifications,
                         recent_orders=recent_orders,
                         recent_posts=recent_posts)

# ==================== AGROVET DASHBOARD ====================

@app.route('/agrovet/dashboard')
@login_required
def agrovet_dashboard():
    """Agrovet dashboard"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    from models import InventoryItem, Order, Notification
    
    # Dashboard statistics
    total_products = InventoryItem.query.filter_by(agrovet_id=current_user.id).count()
    
    today = datetime.utcnow().date()
    today_orders = Order.query.filter(
        Order.agrovet_id == current_user.id,
        func.date(Order.created_at) == today
    ).all()
    today_revenue = sum(order.total_amount for order in today_orders)
    
    recent_orders = Order.query.filter_by(
        agrovet_id=current_user.id
    ).order_by(desc(Order.created_at)).limit(10).all()
    
    # Get recent notifications
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Notification.created_at)).limit(10).all()
    
    return render_template('agrovet/dashboard.html',
                         total_products=total_products,
                         today_revenue=today_revenue,
                         recent_orders=recent_orders,
                         notifications=notifications)

# ==================== MARKETPLACE ====================

@app.route('/marketplace')
def marketplace():
    """Marketplace - Browse all products"""
    from models import InventoryItem
    
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    
    query = InventoryItem.query.filter_by(is_active=True)
    
    if category != 'all' and category:
        query = query.filter_by(category=category)
    
    if search:
        query = query.filter(or_(
            InventoryItem.product_name.ilike(f'%{search}%'),
            InventoryItem.description.ilike(f'%{search}%'),
            InventoryItem.category.ilike(f'%{search}%')
        ))
    
    products = query.order_by(desc(InventoryItem.created_at)).all()
    
    # Get categories
    categories = db.session.query(InventoryItem.category).filter_by(
        is_active=True
    ).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('marketplace.html',
                         products=products,
                         categories=categories,
                         current_category=category,
                         search=search)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Product detail page"""
    from models import InventoryItem, User
    
    product = InventoryItem.query.get_or_404(product_id)
    
    if not product.is_active:
        flash('This product is not available', 'warning')
        return redirect(url_for('marketplace'))
    
    # Get agrovet details
    agrovet = User.query.get(product.agrovet_id)
    
    # Get related products
    related_products = InventoryItem.query.filter(
        InventoryItem.category == product.category,
        InventoryItem.id != product.id,
        InventoryItem.is_active == True
    ).limit(4).all()
    
    return render_template('product_detail.html',
                         product=product,
                         agrovet=agrovet,
                         related_products=related_products)

# ==================== CART & ORDERS ====================

@app.route('/cart')
@login_required
def view_cart():
    """View shopping cart"""
    from models import Cart, CartItem
    
    cart = current_user.cart
    
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    
    cart_items = CartItem.query.filter_by(cart_id=cart.id).all()
    
    total_price = 0
    for item in cart_items:
        if item.product and item.product.is_active:
            total_price += item.product.price * item.quantity
    
    return render_template('cart.html',
                         cart_items=cart_items,
                         total_price=total_price)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    """Add product to cart"""
    from models import InventoryItem, Cart, CartItem
    
    product = InventoryItem.query.get_or_404(product_id)
    
    if not product.is_active or product.quantity <= 0:
        return jsonify({'success': False, 'error': 'Product not available'}), 400
    
    cart = current_user.cart
    
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    
    # Check if product is already in cart
    existing_item = CartItem.query.filter_by(
        cart_id=cart.id,
        product_id=product_id
    ).first()
    
    if existing_item:
        # Update quantity
        new_quantity = existing_item.quantity + 1
        if new_quantity > product.quantity:
            return jsonify({'success': False, 'error': 'Not enough stock'}), 400
        
        existing_item.quantity = new_quantity
    else:
        # Add new item
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            quantity=1
        )
        db.session.add(cart_item)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Product added to cart'})

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login"""
    from models import User
    
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.is_admin and user.check_password(password):
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
    from models import User, InventoryItem, Order
    
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
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_farmers=total_farmers,
                         total_agrovets=total_agrovets,
                         total_products=total_products,
                         total_orders=total_orders,
                         recent_users=recent_users,
                         recent_orders=recent_orders)

@app.route('/admin/users')
@admin_required
def admin_users():
    """Admin user management"""
    from models import User
    
    search = request.args.get('search', '')
    
    query = User.query
    
    if search:
        query = query.filter(or_(
            User.email.ilike(f'%{search}%'),
            User.full_name.ilike(f'%{search}%')
        ))
    
    users = query.order_by(desc(User.created_at)).all()
    
    return render_template('admin/users.html',
                         users=users,
                         search=search)

# ==================== COMMUNITY ====================

@app.route('/community')
def community_home():
    """Community homepage"""
    from models import CommunityPost
    
    search = request.args.get('search', '')
    
    query = CommunityPost.query
    
    if search:
        query = query.filter(or_(
            CommunityPost.title.ilike(f'%{search}%'),
            CommunityPost.content.ilike(f'%{search}%')
        ))
    
    posts = query.order_by(desc(CommunityPost.created_at)).all()
    
    return render_template('community/home.html',
                         posts=posts,
                         search=search)

@app.route('/community/create', methods=['GET', 'POST'])
@login_required
def create_community_post():
    """Create community post"""
    from models import CommunityPost, PostFollow
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        post_type = request.form.get('post_type', 'question')
        category = request.form.get('category', 'general')
        
        if not title or not content:
            flash('Title and content are required', 'danger')
            return redirect(url_for('create_community_post'))
        
        post = CommunityPost(
            user_id=current_user.id,
            title=title,
            content=content,
            post_type=post_type,
            category=category
        )
        
        db.session.add(post)
        db.session.commit()
        
        # Auto-follow own post
        follow = PostFollow(post=post, user_id=current_user.id)
        db.session.add(follow)
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('view_community_post', post_id=post.id))
    
    return render_template('community/create_post.html')

# ==================== PROFILE ====================

@app.route('/profile')
@login_required
def profile():
    """User profile"""
    from models import Order, CommunityPost, PostAnswer
    
    # Get user statistics
    total_orders = Order.query.filter_by(user_id=current_user.id).count()
    total_posts = CommunityPost.query.filter_by(user_id=current_user.id).count()
    total_answers = PostAnswer.query.filter_by(user_id=current_user.id).count()
    
    # Get recent activity
    recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(
        desc(Order.created_at)
    ).limit(5).all()
    
    recent_posts = CommunityPost.query.filter_by(user_id=current_user.id).order_by(
        desc(CommunityPost.created_at)
    ).limit(5).all()
    
    return render_template('profile.html',
                         total_orders=total_orders,
                         total_posts=total_posts,
                         total_answers=total_answers,
                         recent_orders=recent_orders,
                         recent_posts=recent_posts)

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ==================== FILE UPLOADS ====================

@app.route('/uploads/<path:filename>')
def uploaded_files(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==================== APPLICATION STARTUP ====================

def startup():
    """Application startup procedure"""
    print("🚀 Starting AgriConnect Application...")
    
    # Create upload directories
    os.makedirs('uploads/products', exist_ok=True)
    os.makedirs('uploads/profiles', exist_ok=True)
    
    # Initialize database
    print("🔧 Initializing database...")
    init_database()
    print("✅ Application started successfully!")

# ==================== MAIN ====================

if __name__ == '__main__':
    # Run startup procedure
    startup()
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Run the app
    print(f"🌐 Server running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
else:
    # For Gunicorn on Render
    startup()

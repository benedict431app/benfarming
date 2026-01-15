import os
import uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc, or_, func
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
os.makedirs('uploads', exist_ok=True)
os.makedirs('uploads/profiles', exist_ok=True)
os.makedirs('static/images', exist_ok=True)

# ==================== DATABASE INITIALIZATION ====================

def init_database():
    """Initialize the SQLite database"""
    with app.app_context():
        try:
            print(f"📊 Initializing SQLite database...")
            
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
                    is_active=True
                )
                admin.set_password('Admin@123')
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin user created: admin@agriconnect.com / Admin@123")
            
            # Create cart for admin
            if not Cart.query.filter_by(user_id=1).first():
                cart = Cart(user_id=1)
                db.session.add(cart)
            
            db.session.commit()
            print("✅ Database initialization complete!")
            
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

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
        # If database error, reinitialize
        init_database()
        return render_template('welcome.html')

@app.route('/welcome')
def welcome():
    """Welcome page for first-time visitors"""
    return render_template('welcome.html')

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
            
            # Handle profile picture
            profile_picture = 'default-avatar.png'
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename != '':
                    if allowed_file(file.filename):
                        filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename)
                        file.save(filepath)
                        profile_picture = filename
            
            # Create user
            user = User(
                email=email,
                full_name=full_name,
                user_type=user_type,
                phone_number=phone_number,
                location=location,
                is_active=True,
                profile_picture=profile_picture
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
            print(f"Registration error: {e}")
            flash(f'Registration error: Please try again', 'danger')
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
            print(f"Login error: {e}")
            flash(f'Login error: Please try again', 'danger')
    
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Helper function for file uploads
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== PROFILE ROUTES ====================

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

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        try:
            current_user.full_name = request.form.get('full_name')
            current_user.phone_number = request.form.get('phone_number')
            current_user.location = request.form.get('location')
            current_user.address = request.form.get('address')
            
            # Handle profile picture
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename != '':
                    if allowed_file(file.filename):
                        # Delete old profile picture if exists
                        if current_user.profile_picture and current_user.profile_picture != 'default-avatar.png':
                            old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', current_user.profile_picture)
                            if os.path.exists(old_path):
                                os.remove(old_path)
                        
                        # Save new profile picture
                        filename = secure_filename(f"{current_user.id}_{uuid.uuid4().hex}_{file.filename}")
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename)
                        file.save(filepath)
                        current_user.profile_picture = filename
            
            # Update agrovet business info
            if current_user.user_type == 'agrovet':
                current_user.business_name = request.form.get('business_name')
                current_user.business_description = request.form.get('business_description')
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Profile update error: {e}")
            flash('Error updating profile. Please try again.', 'danger')
    
    return render_template('edit_profile.html')

# ==================== FILE SERVING ====================

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/static/images/<path:filename>')
def static_image(filename):
    """Serve static images"""
    return send_from_directory('static/images', filename)

# ==================== FARMER DASHBOARD ====================

@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    """Farmer dashboard"""
    if current_user.user_type != 'farmer' and not current_user.is_admin:
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
    if current_user.user_type != 'agrovet' and not current_user.is_admin:
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

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ==================== APPLICATION STARTUP ====================

def startup():
    """Application startup procedure"""
    print("🚀 Starting AgriConnect Application...")
    
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

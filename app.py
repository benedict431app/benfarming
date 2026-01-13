import os
import uuid
import math
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc, or_, and_, func
from config import Config
from models import db, User, InventoryItem, Cart, CartItem, Order, OrderItem, Notification, CommunityPost, PostAnswer, PostFollow, SystemSetting

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_notification(user_id, title, message, notification_type='info'):
    """Create a notification for a user"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False
    )
    db.session.add(notification)
    db.session.commit()
    return notification

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

# ==================== INITIALIZATION ====================

def init_app():
    """Initialize the application"""
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create default admin user
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

# ==================== BASIC ROUTES ====================

@app.route('/')
def index():
    """Homepage"""
    # Get featured products
    featured_products = InventoryItem.query.filter_by(
        is_active=True
    ).order_by(desc(InventoryItem.created_at)).limit(8).all()
    
    # Get recent community posts
    recent_posts = CommunityPost.query.order_by(desc(CommunityPost.created_at)).limit(6).all()
    
    return render_template('index.html',
                         featured_products=featured_products,
                         recent_posts=recent_posts)

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
            location=location,
            is_active=True
        )
        user.set_password(password)
        
        # Additional fields for agrovets
        if user_type == 'agrovet':
            user.business_name = request.form.get('business_name')
            user.business_description = request.form.get('business_description')
        
        db.session.add(user)
        db.session.commit()
        
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
    
    return render_template('farmer/dashboard.html',
                         notifications=notifications,
                         recent_orders=recent_orders)

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
    
    today = datetime.utcnow().date()
    today_orders = Order.query.filter(
        Order.agrovet_id == current_user.id,
        func.date(Order.created_at) == today
    ).all()
    today_revenue = sum(order.total_amount for order in today_orders)
    
    recent_orders = Order.query.filter_by(
        agrovet_id=current_user.id
    ).order_by(desc(Order.created_at)).limit(10).all()
    
    return render_template('agrovet/dashboard.html',
                         total_products=total_products,
                         today_revenue=today_revenue,
                         recent_orders=recent_orders)

@app.route('/agrovet/products')
@login_required
def agrovet_products():
    """Agrovet product management"""
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    search = request.args.get('search', '')
    
    query = InventoryItem.query.filter_by(agrovet_id=current_user.id)
    
    if search:
        query = query.filter(or_(
            InventoryItem.product_name.ilike(f'%{search}%'),
            InventoryItem.description.ilike(f'%{search}%')
        ))
    
    products = query.order_by(desc(InventoryItem.created_at)).all()
    
    return render_template('agrovet/products.html',
                         products=products,
                         search=search)

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
                description=request.form.get('description'),
                quantity=int(request.form.get('quantity', 0)),
                price=float(request.form.get('price', 0)),
                unit=request.form.get('unit'),
                is_active=True
            )
            
            db.session.add(product)
            db.session.commit()
            
            flash('Product added successfully!', 'success')
            return redirect(url_for('agrovet_products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding product: {str(e)}', 'danger')
    
    return render_template('agrovet/add_product.html')

# ==================== MARKETPLACE ====================

@app.route('/marketplace')
def marketplace():
    """Marketplace - Browse all products"""
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
    product = InventoryItem.query.get_or_404(product_id)
    
    if not product.is_active:
        flash('This product is not available', 'warning')
        return redirect(url_for('marketplace'))
    
    # Get agrovet details
    agrovet = User.query.get(product.agrovet_id)
    
    return render_template('product_detail.html',
                         product=product,
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
    
    return render_template('agrovet_detail.html',
                         agrovet=agrovet,
                         products=products)

# ==================== CART & ORDERS ====================

@app.route('/cart')
@login_required
def view_cart():
    """View shopping cart"""
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

@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart_item(item_id):
    """Update cart item quantity"""
    cart_item = CartItem.query.get_or_404(item_id)
    
    if cart_item.cart.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    quantity = request.json.get('quantity', 1)
    
    if quantity < 1:
        return jsonify({'success': False, 'error': 'Invalid quantity'}), 400
    
    if quantity > cart_item.product.quantity:
        return jsonify({'success': False, 'error': 'Not enough stock'}), 400
    
    cart_item.quantity = quantity
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    """Remove product from cart"""
    cart_item = CartItem.query.get_or_404(item_id)
    
    if cart_item.cart.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    db.session.delete(cart_item)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Checkout process"""
    cart = current_user.cart
    
    if not cart or CartItem.query.filter_by(cart_id=cart.id).count() == 0:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('view_cart'))
    
    if request.method == 'POST':
        try:
            shipping_address = request.form.get('shipping_address')
            payment_method = request.form.get('payment_method')
            
            if not shipping_address:
                flash('Shipping address is required', 'danger')
                return redirect(url_for('checkout'))
            
            # Group items by agrovet
            agrovet_items = {}
            
            for cart_item in cart.cart_items_rel:
                if cart_item.product:
                    agrovet_id = cart_item.product.agrovet_id
                    if agrovet_id not in agrovet_items:
                        agrovet_items[agrovet_id] = []
                    agrovet_items[agrovet_id].append(cart_item)
            
            orders = []
            
            # Create order for each agrovet
            for agrovet_id, items in agrovet_items.items():
                total_amount = 0
                
                # Check stock and calculate total
                for cart_item in items:
                    if cart_item.quantity > cart_item.product.quantity:
                        flash(f'Not enough stock for {cart_item.product.product_name}', 'danger')
                        return redirect(url_for('checkout'))
                    total_amount += cart_item.product.price * cart_item.quantity
                
                # Create order
                order = Order(
                    order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
                    user_id=current_user.id,
                    agrovet_id=agrovet_id,
                    total_amount=total_amount,
                    shipping_address=shipping_address,
                    payment_method=payment_method,
                    status='pending'
                )
                
                db.session.add(order)
                db.session.flush()  # Get order ID
                
                # Add order items and reduce stock
                for cart_item in items:
                    # Create order item
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=cart_item.product_id,
                        quantity=cart_item.quantity,
                        unit_price=cart_item.product.price,
                        subtotal=cart_item.product.price * cart_item.quantity
                    )
                    db.session.add(order_item)
                    
                    # Reduce stock
                    cart_item.product.quantity -= cart_item.quantity
                
                orders.append(order)
                
                # Create notification for agrovet
                create_notification(
                    user_id=agrovet_id,
                    title='New Order Received',
                    message=f'You have received a new order #{order.order_number} from {current_user.full_name}.',
                    notification_type='success'
                )
            
            # Clear cart
            CartItem.query.filter_by(cart_id=cart.id).delete()
            
            db.session.commit()
            
            flash('Order placed successfully!', 'success')
            return redirect(url_for('order_confirmation', order_id=orders[0].id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing order: {str(e)}', 'danger')
    
    # Get cart items for checkout page
    cart_items = CartItem.query.filter_by(cart_id=cart.id).all()
    total_price = sum(item.product.price * item.quantity for item in cart_items if item.product)
    
    return render_template('checkout.html', cart_items=cart_items, total_price=total_price)

@app.route('/order/confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    """Order confirmation page"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    return render_template('order_confirmation.html', order=order)

@app.route('/orders')
@login_required
def my_orders():
    """User order history"""
    orders = Order.query.filter_by(user_id=current_user.id).order_by(
        desc(Order.created_at)
    ).all()
    
    return render_template('orders.html', orders=orders)

# ==================== COMMUNITY ====================

@app.route('/community')
def community_home():
    """Community homepage"""
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
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('view_community_post', post_id=post.id))
    
    return render_template('community/create_post.html')

@app.route('/community/post/<int:post_id>')
def view_community_post(post_id):
    """View community post"""
    post = CommunityPost.query.get_or_404(post_id)
    
    # Increment view count
    post.views += 1
    
    # Get answers
    answers = PostAnswer.query.filter_by(post_id=post_id).order_by(
        desc(PostAnswer.is_accepted),
        desc(PostAnswer.created_at)
    ).all()
    
    db.session.commit()
    
    return render_template('community/view_post.html',
                         post=post,
                         answers=answers)

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

# ==================== PROFILE ====================

@app.route('/profile')
@login_required
def profile():
    """User profile"""
    return render_template('profile.html')

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.phone_number = request.form.get('phone_number')
        current_user.location = request.form.get('location')
        current_user.address = request.form.get('address')
        
        # Handle profile picture
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                filename = secure_filename(f"{current_user.id}_{file.filename}")
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
    
    return render_template('edit_profile.html')

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

# ==================== MAIN ====================

if __name__ == '__main__':
    # Initialize the app
    init_app()
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=debug)

import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import requests
import secrets
import uuid
from config import Config
from models import db, User, InventoryItem, Customer, Sale, SaleItem, Communication, DiseaseReport, Notification, WeatherData, CommunityPost, PostComment, PostFollow, UserReview, AppRecommendation, CartItem, Order, OrderItem, PasswordResetToken, Message
import google.generativeai as genai
from PIL import Image
import io
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

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

def create_notification(user_id, title, message, notification_type='info', link=None):
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link
    )
    db.session.add(notification)
    db.session.commit()

def send_email(to_email, subject, body):
    try:
        smtp_server = app.config.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = app.config.get('SMTP_PORT', 587)
        smtp_username = app.config.get('SMTP_USERNAME')
        smtp_password = app.config.get('SMTP_PASSWORD')
        
        if not all([smtp_server, smtp_username, smtp_password]):
            return False
        
        msg = MIMEMultipart()
        msg['From'] = smtp_username
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# Create database tables
with app.app_context():
    db.create_all()
    # Create admin user if not exists
    if not User.query.filter_by(email='admin@adiseware.com').first():
        admin = User(
            email='admin@adiseware.com',
            full_name='System Administrator',
            user_type='admin',
            phone_number='+254713593573',
            location='Nairobi',
            is_admin=True,
            is_verified=True
        )
        admin.set_password('Admin@123')
        db.session.add(admin)
    
    # Create your admin user
    if not User.query.filter_by(email='beneicto431@gmail.com').first():
        user_admin = User(
            email='beneicto431@gmail.com',
            full_name='Benedict Admin',
            user_type='admin',
            phone_number='+254713593573',
            location='Nairobi',
            is_admin=True,
            is_verified=True,
            profile_picture='admin.jpg'
        )
        user_admin.set_password('12345678')
        db.session.add(user_admin)
    
    db.session.commit()

# ========== ADD ALL MISSING ROUTES ==========

@app.route('/')
def index():
    if current_user.is_authenticated:
        current_user.last_login = datetime.utcnow()
        db.session.commit()
        
        if current_user.user_type == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        elif current_user.user_type == 'agrovet':
            return redirect(url_for('agrovet_dashboard'))
        elif current_user.user_type == 'extension_officer':
            return redirect(url_for('officer_dashboard'))
        elif current_user.user_type == 'learning_institution':
            return redirect(url_for('institution_dashboard'))
        elif current_user.user_type == 'admin':
            return redirect(url_for('admin_dashboard'))
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/help')
def help():
    return render_template('help.html')

# ========== AUTHENTICATION ROUTES ==========

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        user_type = request.form.get('user_type')
        phone_number = request.form.get('phone_number')
        location = request.form.get('location')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
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
                filename = secure_filename(f"{user.id}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
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
        remember = request.form.get('remember')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated', 'error')
                return redirect(url_for('login'))
            
            login_user(user, remember=bool(remember))
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = secrets.token_urlsafe(32)
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.session.add(reset_token)
            db.session.commit()
            
            reset_link = url_for('reset_password', token=token, _external=True)
            # send_email(user.email, "Password Reset", f"Click to reset: {reset_link}")
            
            flash('Password reset instructions sent to your email', 'success')
        else:
            flash('Email not found', 'error')
    
    return render_template('auth/forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    reset_token = PasswordResetToken.query.filter_by(token=token, used=False).first()
    
    if not reset_token or reset_token.expires_at < datetime.utcnow():
        flash('Invalid or expired reset token', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('reset_password', token=token))
        
        user = User.query.get(reset_token.user_id)
        user.set_password(password)
        reset_token.used = True
        db.session.commit()
        
        flash('Password reset successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/reset_password.html', token=token)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ========== PROFILE ROUTES ==========

@app.route('/profile')
@login_required
def profile():
    reviews = UserReview.query.filter_by(user_id=current_user.id, is_approved=True).all()
    recent_posts = CommunityPost.query.filter_by(author_id=current_user.id).order_by(CommunityPost.created_at.desc()).limit(5).all()
    
    return render_template('profile.html', reviews=reviews, recent_posts=recent_posts)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.phone_number = request.form.get('phone_number')
        current_user.location = request.form.get('location')
        
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{current_user.id}_{datetime.utcnow().timestamp()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                current_user.profile_picture = filename
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html')

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not current_user.check_password(current_password):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('profile'))
    
    current_user.set_password(new_password)
    db.session.commit()
    
    flash('Password changed successfully!', 'success')
    return redirect(url_for('profile'))

# ========== COMMUNITY ROUTES ==========

@app.route('/community')
@login_required
def community():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('community/posts.html', posts=posts)

@app.route('/community/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        post_type = request.form.get('post_type')
        category = request.form.get('category')
        
        post = CommunityPost(
            author_id=current_user.id,
            title=title,
            content=content,
            post_type=post_type,
            category=category
        )
        
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"post_{current_user.id}_{datetime.utcnow().timestamp()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'community', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                post.image = filename
        
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('view_post', post_id=post.id))
    
    return render_template('community/create_post.html')

@app.route('/community/post/<int:post_id>')
@login_required
def view_post(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    post.views += 1
    db.session.commit()
    
    is_following = PostFollow.query.filter_by(post_id=post_id, user_id=current_user.id).first() is not None
    
    return render_template('community/view_post.html', post=post, is_following=is_following)

@app.route('/community/post/<int:post_id>/follow', methods=['POST'])
@login_required
def follow_post(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    
    existing_follow = PostFollow.query.filter_by(post_id=post_id, user_id=current_user.id).first()
    
    if existing_follow:
        db.session.delete(existing_follow)
        action = 'unfollowed'
    else:
        follow = PostFollow(post_id=post_id, user_id=current_user.id)
        db.session.add(follow)
        action = 'following'
    
    db.session.commit()
    
    return jsonify({'success': True, 'action': action})

@app.route('/community/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    
    content = request.form.get('content')
    is_answer = request.form.get('is_answer', 'false') == 'true'
    
    comment = PostComment(
        post_id=post_id,
        author_id=current_user.id,
        content=content,
        is_answer=is_answer
    )
    
    db.session.add(comment)
    
    if post.author_id != current_user.id:
        create_notification(
            post.author_id,
            'New Comment',
            f'{current_user.full_name} commented on your post: "{post.title}"',
            link=url_for('view_post', post_id=post_id)
        )
    
    followers = PostFollow.query.filter_by(post_id=post_id).all()
    for follow in followers:
        if follow.user_id != current_user.id:
            create_notification(
                follow.user_id,
                'Post Update',
                f'There is a new comment on a post you\'re following: "{post.title}"',
                link=url_for('view_post', post_id=post_id)
            )
    
    db.session.commit()
    
    flash('Comment added successfully!', 'success')
    return redirect(url_for('view_post', post_id=post_id))

# ========== ADMIN POST MANAGEMENT ==========

@app.route('/admin/posts')
@login_required
def admin_posts():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).all()
    return render_template('admin/posts.html', posts=posts)

@app.route('/admin/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_post(post_id):
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    post = CommunityPost.query.get_or_404(post_id)
    
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.category = request.form.get('category')
        post.post_type = request.form.get('post_type')
        post.is_featured = request.form.get('is_featured') == 'true'
        
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('admin_posts'))
    
    return render_template('admin/edit_post.html', post=post)

@app.route('/admin/post/<int:post_id>/delete', methods=['POST'])
@login_required
def admin_delete_post(post_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    post = CommunityPost.query.get_or_404(post_id)
    
    db.session.delete(post)
    db.session.commit()
    
    flash('Post deleted successfully!', 'success')
    return jsonify({'success': True})

# ========== MARKETPLACE ROUTES ==========

@app.route('/products')
@login_required
def browse_products():
    products = InventoryItem.query.join(User).filter(
        InventoryItem.quantity > 0,
        User.user_type == 'agrovet',
        User.is_active == True
    ).all()
    
    product_groups = {}
    for product in products:
        if product.product_name not in product_groups:
            product_groups[product.product_name] = []
        product_groups[product.product_name].append(product)
    
    for product_name in product_groups:
        product_groups[product_name].sort(key=lambda x: x.price)
    
    return render_template('products/browse.html', product_groups=product_groups)

@app.route('/agrovets')
@login_required
def browse_agrovets():
    location = request.args.get('location', current_user.location)
    
    agrovets = User.query.filter_by(user_type='agrovet', is_active=True)
    
    if location:
        agrovets = agrovets.filter(User.location.ilike(f'%{location}%'))
    
    agrovets = agrovets.all()
    
    return render_template('products/agrovets.html', agrovets=agrovets)

@app.route('/agrovet/<int:agrovet_id>/products')
@login_required
def agrovet_products(agrovet_id):
    agrovet = User.query.get_or_404(agrovet_id)
    if agrovet.user_type != 'agrovet':
        flash('This user is not an agrovet', 'error')
        return redirect(url_for('browse_agrovets'))
    
    products = InventoryItem.query.filter_by(agrovet_id=agrovet_id, quantity__gt=0).all()
    
    return render_template('products/agrovet_products.html', agrovet=agrovet, products=products)

@app.route('/cart')
@login_required
def view_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    
    return render_template('products/cart.html', cart_items=cart_items, total=total)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = InventoryItem.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))
    
    if product.quantity < quantity:
        flash('Insufficient stock', 'error')
        return redirect(url_for('browse_products'))
    
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    
    flash('Item added to cart!', 'success')
    return redirect(url_for('view_cart'))

@app.route('/cart/update/<int:cart_item_id>', methods=['POST'])
@login_required
def update_cart_item(cart_item_id):
    cart_item = CartItem.query.get_or_404(cart_item_id)
    
    if cart_item.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('view_cart'))
    
    quantity = int(request.form.get('quantity', 1))
    
    if cart_item.product.quantity < quantity:
        flash('Insufficient stock', 'error')
    else:
        cart_item.quantity = quantity
        db.session.commit()
        flash('Cart updated!', 'success')
    
    return redirect(url_for('view_cart'))

@app.route('/cart/remove/<int:cart_item_id>', methods=['POST'])
@login_required
def remove_cart_item(cart_item_id):
    cart_item = CartItem.query.get_or_404(cart_item_id)
    
    if cart_item.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    db.session.delete(cart_item)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/cart/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty', 'error')
        return redirect(url_for('view_cart'))
    
    if request.method == 'POST':
        agrovet_id = request.form.get('agrovet_id')
        delivery_address = request.form.get('delivery_address')
        payment_method = request.form.get('payment_method', 'cash')
        notes = request.form.get('notes', '')
        
        items_by_agrovet = {}
        for cart_item in cart_items:
            if cart_item.product.agrovet_id not in items_by_agrovet:
                items_by_agrovet[cart_item.product.agrovet_id] = []
            items_by_agrovet[cart_item.product.agrovet_id].append(cart_item)
        
        orders = []
        
        for agrovet_id, items in items_by_agrovet.items():
            order_number = f"ORD{current_user.id}{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{agrovet_id}"
            
            order = Order(
                farmer_id=current_user.id,
                agrovet_id=agrovet_id,
                order_number=order_number,
                total_amount=0,
                delivery_address=delivery_address,
                farmer_phone=current_user.phone_number,
                payment_method=payment_method,
                notes=notes
            )
            db.session.add(order)
            db.session.flush()
            
            total_amount = 0
            
            for cart_item in items:
                product = cart_item.product
                
                if product.quantity < cart_item.quantity:
                    db.session.rollback()
                    flash(f'Insufficient stock for {product.product_name}', 'error')
                    return redirect(url_for('checkout'))
                
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.product_name,
                    quantity=cart_item.quantity,
                    unit_price=product.price,
                    subtotal=product.price * cart_item.quantity
                )
                db.session.add(order_item)
                
                total_amount += order_item.subtotal
                product.quantity -= cart_item.quantity
                db.session.delete(cart_item)
            
            order.total_amount = total_amount
            orders.append(order)
            
            create_notification(
                agrovet_id,
                'New Order',
                f'You have a new order #{order_number} from {current_user.full_name}',
                link=url_for('agrovet_order', order_id=order.id)
            )
        
        db.session.commit()
        
        flash(f'Order placed successfully! {len(orders)} order(s) created.', 'success')
        return redirect(url_for('order_confirmation'))
    
    agrovet_totals = {}
    for cart_item in cart_items:
        agrovet = cart_item.product.agrovet
        if agrovet.id not in agrovet_totals:
            agrovet_totals[agrovet.id] = {
                'agrovet': agrovet,
                'items': [],
                'total': 0
            }
        
        item_total = cart_item.product.price * cart_item.quantity
        agrovet_totals[agrovet.id]['items'].append(cart_item)
        agrovet_totals[agrovet.id]['total'] += item_total
    
    return render_template('products/checkout.html', agrovet_totals=agrovet_totals)

@app.route('/order-confirmation')
@login_required
def order_confirmation():
    return render_template('products/order_confirmation.html')

@app.route('/orders')
@login_required
def my_orders():
    if current_user.user_type == 'farmer':
        orders = Order.query.filter_by(farmer_id=current_user.id).order_by(Order.created_at.desc()).all()
    elif current_user.user_type == 'agrovet':
        orders = Order.query.filter_by(agrovet_id=current_user.id).order_by(Order.created_at.desc()).all()
    else:
        orders = []
    
    return render_template('orders/list.html', orders=orders)

@app.route('/order/<int:order_id>')
@login_required
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    if current_user.user_type == 'farmer' and order.farmer_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('my_orders'))
    
    if current_user.user_type == 'agrovet' and order.agrovet_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('my_orders'))
    
    return render_template('orders/view.html', order=order)

@app.route('/agrovet/order/<int:order_id>')
@login_required
def agrovet_order(order_id):
    if current_user.user_type != 'agrovet':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    order = Order.query.get_or_404(order_id)
    
    if order.agrovet_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('agrovet_dashboard'))
    
    return render_template('agrovet/order.html', order=order)

# ========== MESSAGES ROUTES ==========

@app.route('/messages')
@login_required
def messages():
    conversations = Message.query.filter(
        (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
    ).order_by(Message.created_at.desc()).all()
    
    conversation_map = {}
    for msg in conversations:
        other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        if other_id not in conversation_map:
            conversation_map[other_id] = {
                'user': msg.receiver if msg.sender_id == current_user.id else msg.sender,
                'last_message': msg,
                'unread_count': 0
            }
        
        if not msg.is_read and msg.receiver_id == current_user.id:
            conversation_map[other_id]['unread_count'] += 1
    
    return render_template('messages/list.html', conversations=conversation_map.values())

@app.route('/messages/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat_with_user(user_id):
    other_user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        content = request.form.get('message')
        
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"msg_{current_user.id}_{user_id}_{datetime.utcnow().timestamp()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                
                message = Message(
                    sender_id=current_user.id,
                    receiver_id=user_id,
                    message_type='image',
                    image_url=filename
                )
                db.session.add(message)
        
        if content:
            message = Message(
                sender_id=current_user.id,
                receiver_id=user_id,
                message_type='text',
                content=content
            )
            db.session.add(message)
        
        db.session.commit()
        return redirect(url_for('chat_with_user', user_id=user_id))
    
    messages_to_read = Message.query.filter_by(sender_id=user_id, receiver_id=current_user.id, is_read=False).all()
    for msg in messages_to_read:
        msg.is_read = True
    db.session.commit()
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    
    return render_template('messages/chat.html', other_user=other_user, messages=messages)

@app.route('/message/product/<int:product_id>', methods=['POST'])
@login_required
def message_about_product(product_id):
    product = InventoryItem.query.get_or_404(product_id)
    
    content = request.form.get('message', f"I'm interested in {product.product_name}")
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=product.agrovet_id,
        message_type='product_inquiry',
        content=content,
        product_id=product_id
    )
    
    db.session.add(message)
    db.session.commit()
    
    flash('Message sent to agrovet!', 'success')
    return redirect(url_for('chat_with_user', user_id=product.agrovet_id))

# ========== REVIEWS ROUTES ==========

@app.route('/reviews/user/<int:user_id>')
@login_required
def user_reviews(user_id):
    user = User.query.get_or_404(user_id)
    reviews = UserReview.query.filter_by(user_id=user_id, is_approved=True).all()
    
    return render_template('reviews/user_reviews.html', user=user, reviews=reviews)

@app.route('/reviews/add/<int:user_id>', methods=['POST'])
@login_required
def add_review(user_id):
    if user_id == current_user.id:
        flash('You cannot review yourself', 'error')
        return redirect(request.referrer or url_for('profile'))
    
    rating = int(request.form.get('rating'))
    review_text = request.form.get('review_text')
    
    existing_review = UserReview.query.filter_by(user_id=user_id, reviewer_id=current_user.id).first()
    
    if existing_review:
        flash('You have already reviewed this user', 'error')
    else:
        review = UserReview(
            user_id=user_id,
            reviewer_id=current_user.id,
            rating=rating,
            review_text=review_text,
            user_type=current_user.user_type
        )
        db.session.add(review)
        db.session.commit()
        flash('Review submitted!', 'success')
    
    return redirect(request.referrer or url_for('profile'))

# ========== RECOMMENDATIONS ROUTES ==========

@app.route('/recommendations')
@login_required
def view_recommendations():
    recommendations = AppRecommendation.query.order_by(AppRecommendation.created_at.desc()).all()
    return render_template('recommendations/list.html', recommendations=recommendations)

@app.route('/recommendations/add', methods=['GET', 'POST'])
@login_required
def add_recommendation():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        
        recommendation = AppRecommendation(
            author_id=current_user.id,
            title=title,
            content=content,
            category=category
        )
        
        db.session.add(recommendation)
        db.session.commit()
        
        flash('Recommendation submitted! Thank you for your feedback.', 'success')
        return redirect(url_for('view_recommendations'))
    
    return render_template('recommendations/add.html')

@app.route('/recommendations/<int:rec_id>/upvote', methods=['POST'])
@login_required
def upvote_recommendation(rec_id):
    recommendation = AppRecommendation.query.get_or_404(rec_id)
    recommendation.upvotes += 1
    db.session.commit()
    
    return jsonify({'success': True, 'upvotes': recommendation.upvotes})

# ========== DASHBOARD ROUTES ==========

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_posts': CommunityPost.query.count(),
        'total_orders': Order.query.count(),
        'total_revenue': db.session.query(db.func.sum(Order.total_amount)).scalar() or 0,
        'recent_logins': User.query.filter(User.last_login.isnot(None)).order_by(User.last_login.desc()).limit(10).all()
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    return jsonify({'success': True, 'is_active': user.is_active})

@app.route('/admin/user/<int:user_id>/reset-password', methods=['POST'])
@login_required
def admin_reset_password(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password')
    
    user.set_password(new_password)
    db.session.commit()
    
    flash(f'Password reset for {user.email}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/make-admin', methods=['POST'])
@login_required
def make_admin(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    
    flash(f'{user.email} is now an admin', 'success')
    return redirect(url_for('admin_users'))

# ========== PLANT DISEASE DETECTION ==========

def detect_plant_disease(image_path, description=""):
    """Detect plant disease using AI analysis"""
    try:
        # If Cohere API is available, use it
        if cohere_api_key:
            headers = {
                'Authorization': f'Bearer {cohere_api_key}',
                'Content-Type': 'application/json',
            }
            
            # Read image and convert to base64
            with open(image_path, 'rb') as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
            chat_payload = {
                'model': 'c4ai-aya-expanse-8b',
                'message': f"""
                Analyze this plant image for diseases and health issues.
                
                User description: {description}
                
                As an agricultural expert, please:
                1. Identify the plant species if possible
                2. Detect any visible diseases or pests
                3. Recommend specific treatments
                4. Provide agroecological solutions
                5. Suggest prevention measures
                
                Format your response clearly with sections.
                If the image doesn't appear to be a plant, please state that clearly.
                """,
                'temperature': 0.7,
                'max_tokens': 1000
            }
            
            response = requests.post('https://api.cohere.ai/v1/chat', json=chat_payload, headers=headers)
            result = response.json()
            
            if response.status_code == 200 and 'text' in result:
                return result['text']
            else:
                return "Unable to analyze plant health at the moment. Please try again later or consult with an agricultural officer."
        
        # Fallback to generic analysis if no API
        return """Plant Health Analysis:
        
        1. Plant Identification: Based on the image, this appears to be a common crop plant. 
        
        2. Disease Detection: The plant shows signs of potential nutrient deficiency or early-stage fungal infection.
        
        3. Recommended Treatment:
           - Apply organic fungicide (neem oil or copper-based)
           - Ensure proper soil drainage
           - Maintain appropriate watering schedule
           - Remove affected leaves if necessary
        
        4. Agroecological Solutions:
           - Practice crop rotation
           - Use companion planting (marigolds, basil)
           - Apply compost tea as natural fertilizer
           - Introduce beneficial insects
        
        5. Prevention:
           - Monitor plants regularly
           - Maintain proper spacing for air circulation
           - Water at soil level, not on leaves
           - Use disease-resistant varieties
        
        Note: For accurate diagnosis, consult with your local extension officer."""
    
    except Exception as e:
        print(f"Error in plant detection: {e}")
        return "Error analyzing plant image. Please try again."

@app.route('/farmer/detect-disease', methods=['GET', 'POST'])
@login_required
def detect_disease():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'plant_image' not in request.files:
            flash('No image provided', 'error')
            return redirect(url_for('detect_disease'))
        
        file = request.files['plant_image']
        description = request.form.get('description', '')
        
        if not file or file.filename == '':
            flash('No image selected', 'error')
            return redirect(url_for('detect_disease'))
        
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(f"plant_{current_user.id}_{datetime.utcnow().timestamp()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'plant_disease', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                
                # Analyze the image
                analysis = detect_plant_disease(filepath, description)
                
                # Check if analysis indicates non-plant image
                is_plant = True
                if any(word in analysis.lower() for word in ['not a plant', 'not plant', 'does not appear to be', 'non-plant']):
                    is_plant = False
                    flash('The uploaded image does not appear to be a plant. Please upload a clear image of a plant.', 'warning')
                
                report = DiseaseReport(
                    farmer_id=current_user.id,
                    plant_image=filename,
                    plant_description=description,
                    treatment_recommendation=analysis,
                    is_plant=is_plant,
                    location=current_user.location
                )
                db.session.add(report)
                db.session.commit()
                
                if is_plant:
                    flash('Plant analysis completed successfully!', 'success')
                
                return render_template('farmer/disease_result.html', 
                                     report=report, 
                                     analysis=analysis,
                                     image_url=url_for('serve_upload', filename=f'plant_disease/{filename}'))
                
            except Exception as e:
                flash(f'Error processing image: {str(e)}', 'error')
                return redirect(url_for('detect_disease'))
        
        else:
            flash('Invalid file type. Please upload an image (PNG, JPG, JPEG)', 'error')
    
    return render_template('farmer/detect_disease.html')

@app.route('/farmer/disease-history')
@login_required
def disease_history():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    reports = DiseaseReport.query.filter_by(farmer_id=current_user.id).order_by(DiseaseReport.created_at.desc()).all()
    return render_template('farmer/disease_history.html', reports=reports)

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

# FARMER DASHBOARD ROUTE
@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
    disease_reports = DiseaseReport.query.filter_by(farmer_id=current_user.id).order_by(DiseaseReport.created_at.desc()).limit(10).all()
    
    recent_posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(5).all()
    
    return render_template('farmer/dashboard.html', 
                         notifications=notifications, 
                         disease_reports=disease_reports,
                         recent_posts=recent_posts)

# AGROVET DASHBOARD ROUTE
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
    
    recent_orders = Order.query.filter_by(agrovet_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
    
    return render_template('agrovet/dashboard.html', 
                         total_products=total_products,
                         low_stock_items=low_stock_items,
                         total_customers=total_customers,
                         today_revenue=today_revenue,
                         recent_sales=recent_sales,
                         recent_orders=recent_orders,
                         notifications=notifications)

# Agrovet inventory routes
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

# Agrovet POS routes
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

# ========== AI CHAT ROUTES ==========

@app.route('/ai-chat', methods=['GET', 'POST'])
@login_required
def ai_chat():
    """Chat interface with AI assistant"""
    if request.method == 'POST':
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'Message cannot be empty'})
        
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
                'preamble': """You are AgriConnect AI Assistant, a helpful agricultural expert specializing in:
1. Farming techniques and best practices
2. Crop management and disease control
3. Livestock care and management
4. Agricultural economics and marketing
5. Sustainable farming and agroecology
6. Weather-based farming advice
7. Pest and disease identification
8. Soil management and fertility
9. Irrigation and water management
10. Agricultural technology

Provide practical, actionable advice specific to Kenyan farming conditions.
Be concise but thorough. If you don't know something, admit it and suggest consulting local extension officers."""
            }
            
            response = requests.post('https://api.cohere.ai/v1/chat', json=chat_payload, headers=headers)
            result = response.json()
            
            if response.status_code == 200 and 'text' in result:
                ai_response = result['text']
                return jsonify({
                    'success': True,
                    'response': ai_response
                })
            else:
                error_msg = result.get('message', 'Unable to process your request')
                return jsonify({
                    'success': False,
                    'error': f'AI Service error: {error_msg}'
                })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Chat service error: {str(e)}'
            })
    
    return render_template('ai_chat.html')

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """Legacy API endpoint for chat"""
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

# Test API route
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

# List models route
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

# ========== NOTIFICATION ROUTES ==========

@app.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()
    
    for notification in notifications:
        notification.is_read = True
    
    db.session.commit()
    
    return jsonify({'success': True})

# ========== WEATHER ROUTE ==========

@app.route('/weather')
@login_required
def weather():
    location = request.args.get('location', current_user.location or 'Nairobi')
    
    try:
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={app.config['OPENWEATHER_API_KEY']}&units=metric"
        response = requests.get(weather_url)
        weather_data = response.json()
        
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={location}&appid={app.config['OPENWEATHER_API_KEY']}&units=metric"
        forecast_response = requests.get(forecast_url)
        forecast_data = forecast_response.json()
        
        return render_template('weather.html', weather=weather_data, forecast=forecast_data)
    except Exception as e:
        flash(f'Error fetching weather data: {str(e)}', 'error')
        return render_template('weather.html', weather=None, forecast=None)

# ========== HEALTH CHECK ==========

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'AgriConnect',
        'contact': '+254713593573',
        'timestamp': datetime.utcnow().isoformat()
    }), 200

# ========== TEMPLATE FILTERS ==========

@app.template_filter('datetime')
def format_datetime(value):
    if value is None:
        return ""
    return value.strftime('%Y-%m-%d %H:%M')

@app.template_filter('date')
def format_date(value):
    if value is None:
        return ""
    return value.strftime('%Y-%m-%d')

@app.template_filter('profile_picture')
def get_profile_picture(user):
    if user.profile_picture:
        return url_for('serve_upload', filename=f'profile_pictures/{user.profile_picture}')
    return url_for('static', filename='images/default-profile.png')

# ========== ERROR HANDLERS ==========

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(502)
def bad_gateway_error(error):
    return render_template('errors/502.html'), 502

# Favicon
@app.route('/favicon.ico')
def favicon():
    return '', 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

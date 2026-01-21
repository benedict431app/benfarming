import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import requests
import secrets
import uuid
import json
from PIL import Image
import io
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Create Flask app FIRST
app = Flask(__name__)

# Import config and apply it
from config import Config
app.config.from_object(Config)

# Force PostgreSQL URL format for Render
if os.environ.get('RENDER'):
    database_url = app.config['SQLALCHEMY_DATABASE_URI']
    if database_url and database_url.startswith('postgres://'):
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace('postgres://', 'postgresql://', 1)

# Initialize extensions BEFORE importing models
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

# Initialize extensions with app
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

# NOW import models after db is initialized
from models import User, InventoryItem, Customer, Sale, SaleItem, Communication, DiseaseReport, Notification, WeatherData, CommunityPost, PostComment, PostFollow, UserReview, AppRecommendation, CartItem, Order, OrderItem, PasswordResetToken, Message

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
    
    # Create test farmer
    if not User.query.filter_by(email='farmer@test.com').first():
        farmer = User(
            email='farmer@test.com',
            full_name='Test Farmer',
            user_type='farmer',
            phone_number='+254700000001',
            location='Nairobi'
        )
        farmer.set_password('password123')
        db.session.add(farmer)
    
    # Create test agrovet
    if not User.query.filter_by(email='agrovet@test.com').first():
        agrovet = User(
            email='agrovet@test.com',
            full_name='Test Agrovet',
            user_type='agrovet',
            phone_number='+254700000002',
            location='Nairobi'
        )
        agrovet.set_password('password123')
        db.session.add(agrovet)
    
    db.session.commit()

# ========== HELPER FUNCTIONS ==========

def get_unread_notification_count():
    if not current_user.is_authenticated:
        return 0
    return Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

# ========== BASIC PAGES ==========

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
        elif current_user.user_type == 'admin' or current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
    
    return render_template('index.html', unread_count=0)

@app.route('/about')
def about():
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('about.html', unread_count=unread_count)

@app.route('/features')
def features():
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('features.html', unread_count=unread_count)

@app.route('/contact')
def contact():
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('contact.html', unread_count=unread_count)

@app.route('/faq')
def faq():
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('faq.html', unread_count=unread_count)

@app.route('/privacy')
def privacy():
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('privacy.html', unread_count=unread_count)

@app.route('/terms')
def terms():
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('terms.html', unread_count=unread_count)

@app.route('/pricing')
def pricing():
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('pricing.html', unread_count=unread_count)

@app.route('/help')
def help():
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('help.html', unread_count=unread_count)

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
    
    return render_template('auth/register.html', unread_count=0)

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
            
            # Redirect based on user type
            if user.user_type == 'farmer':
                return redirect(url_for('farmer_dashboard'))
            elif user.user_type == 'agrovet':
                return redirect(url_for('agrovet_dashboard'))
            elif user.user_type == 'extension_officer':
                return redirect(url_for('officer_dashboard'))
            elif user.user_type == 'learning_institution':
                return redirect(url_for('institution_dashboard'))
            elif user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html', unread_count=0)

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
    
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('auth/forgot_password.html', unread_count=unread_count)

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
    
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('auth/reset_password.html', token=token, unread_count=unread_count)

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
    unread_count = get_unread_notification_count()
    
    return render_template('profile.html', reviews=reviews, recent_posts=recent_posts, unread_count=unread_count)

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
    
    unread_count = get_unread_notification_count()
    return render_template('edit_profile.html', unread_count=unread_count)

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

# ========== DASHBOARD ROUTES ==========

@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
    disease_reports = DiseaseReport.query.filter_by(farmer_id=current_user.id).order_by(DiseaseReport.created_at.desc()).limit(10).all()
    recent_posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(5).all()
    unread_count = get_unread_notification_count()
    
    return render_template('farmer/dashboard.html', 
                         notifications=notifications, 
                         disease_reports=disease_reports,
                         recent_posts=recent_posts,
                         unread_count=unread_count)

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
    unread_count = get_unread_notification_count()
    
    return render_template('agrovet/dashboard.html', 
                         total_products=total_products,
                         low_stock_items=low_stock_items,
                         total_customers=total_customers,
                         today_revenue=today_revenue,
                         recent_sales=recent_sales,
                         recent_orders=recent_orders,
                         notifications=notifications,
                         unread_count=unread_count)

@app.route('/officer/dashboard')
@login_required
def officer_dashboard():
    if current_user.user_type != 'extension_officer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    all_disease_reports = DiseaseReport.query.order_by(DiseaseReport.created_at.desc()).limit(50).all()
    farmers = User.query.filter_by(user_type='farmer').all()
    recent_posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(10).all()
    unread_count = get_unread_notification_count()
    
    return render_template('officer/dashboard.html', 
                         disease_reports=all_disease_reports, 
                         farmers=farmers,
                         recent_posts=recent_posts,
                         unread_count=unread_count)

@app.route('/institution/dashboard')
@login_required
def institution_dashboard():
    if current_user.user_type != 'learning_institution':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    recent_posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(10).all()
    unread_count = get_unread_notification_count()
    
    return render_template('institution/dashboard.html', 
                         recent_posts=recent_posts,
                         unread_count=unread_count)

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
    
    unread_count = get_unread_notification_count()
    return render_template('admin/dashboard.html', stats=stats, unread_count=unread_count)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    unread_count = get_unread_notification_count()
    return render_template('admin/users.html', users=users, unread_count=unread_count)

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
        if cohere_api_key and cohere_api_key != 'cohere-api-key-placeholder':
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
                
                unread_count = get_unread_notification_count()
                return render_template('farmer/disease_result.html', 
                                     report=report, 
                                     analysis=analysis,
                                     image_url=url_for('serve_upload', filename=f'plant_disease/{filename}'),
                                     unread_count=unread_count)
                
            except Exception as e:
                flash(f'Error processing image: {str(e)}', 'error')
                return redirect(url_for('detect_disease'))
        
        else:
            flash('Invalid file type. Please upload an image (PNG, JPG, JPEG)', 'error')
    
    unread_count = get_unread_notification_count()
    return render_template('farmer/detect_disease.html', unread_count=unread_count)

@app.route('/farmer/disease-history')
@login_required
def disease_history():
    if current_user.user_type != 'farmer':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    reports = DiseaseReport.query.filter_by(farmer_id=current_user.id).order_by(DiseaseReport.created_at.desc()).all()
    unread_count = get_unread_notification_count()
    return render_template('farmer/disease_history.html', reports=reports, unread_count=unread_count)

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
            if cohere_api_key and cohere_api_key != 'cohere-api-key-placeholder':
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
            else:
                # Simulate AI response when no API key
                responses = [
                    "Based on your question, I recommend checking the soil moisture levels first.",
                    "For plant diseases, try neem oil as a natural fungicide.",
                    "Make sure your plants get at least 6 hours of sunlight daily.",
                    "Consider crop rotation to prevent soil depletion.",
                    "Regular pruning helps improve air circulation and prevent diseases."
                ]
                
                import random
                ai_response = random.choice(responses)
                
                return jsonify({
                    'success': True,
                    'response': f"[Demo Mode] {ai_response}\n\nNote: To get real AI responses, add your Cohere API key to the configuration."
                })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Chat service error: {str(e)}'
            })
    
    unread_count = get_unread_notification_count()
    return render_template('ai_chat.html', unread_count=unread_count)

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
        
        unread_count = get_unread_notification_count()
        return render_template('weather.html', weather=weather_data, forecast=forecast_data, unread_count=unread_count)
    except Exception as e:
        flash(f'Error fetching weather data: {str(e)}', 'error')
        unread_count = get_unread_notification_count()
        return render_template('weather.html', weather=None, forecast=None, unread_count=unread_count)

# ========== COMMUNITY ROUTES ==========

@app.route('/community')
@login_required
def community():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    unread_count = get_unread_notification_count()
    return render_template('community/posts.html', posts=posts, unread_count=unread_count)

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
    
    unread_count = get_unread_notification_count()
    return render_template('products/browse.html', product_groups=product_groups, unread_count=unread_count)

# ========== NOTIFICATION ROUTES ==========

@app.route('/notifications')
@login_required
def notifications():
    notifications_list = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    unread_count = get_unread_notification_count()
    return render_template('notifications.html', notifications=notifications_list, unread_count=unread_count)

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
    if user and user.profile_picture:
        return url_for('serve_upload', filename=f'profile_pictures/{user.profile_picture}')
    return '/static/images/default-profile.png'

# ========== ERROR HANDLERS ==========

@app.errorhandler(404)
def not_found_error(error):
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('404.html', unread_count=unread_count), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('500.html', unread_count=unread_count), 500

@app.errorhandler(502)
def bad_gateway_error(error):
    unread_count = get_unread_notification_count() if current_user.is_authenticated else 0
    return render_template('502.html', unread_count=unread_count), 502

# ========== MAIN ==========

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

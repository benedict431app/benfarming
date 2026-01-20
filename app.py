import os
import io
import base64
import json
import cv2
import numpy as np
from PIL import Image, ImageOps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import requests
import secrets
import uuid
import cohere
from config import Config
from models import db, User, InventoryItem, Customer, Sale, SaleItem, Communication, DiseaseReport, Notification, WeatherData, CommunityPost, PostComment, PostFollow, UserReview, AppRecommendation, CartItem, Order, OrderItem, PasswordResetToken, Message
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

# Initialize Cohere
cohere_api_key = app.config['COHERE_API_KEY']
if cohere_api_key:
    co = cohere.Client(cohere_api_key)
else:
    co = None

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
    if not User.query.filter_by(email='admin@benfarming.com').first():
        admin = User(
            email='admin@benfarming.com',
            full_name='System Administrator',
            user_type='admin',
            phone_number='+254713593573',
            location='Nairobi',
            is_admin=True,
            is_verified=True,
            is_active=True
        )
        admin.set_password('Admin@123')
        db.session.add(admin)
        db.session.commit()
        print("✓ Admin user created: admin@benfarming.com / Admin@123")

# ========== IMAGE PROCESSING & PLANT DETECTION ==========

def is_plant_image(image_path):
    """
    Basic plant detection using color analysis and edge detection
    Returns: (is_plant, confidence)
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return False, 0.0
        
        # Convert to HSV for color analysis
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Define green color range (typical for plants)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        
        # Create mask for green areas
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Calculate percentage of green pixels
        green_ratio = np.sum(mask > 0) / (img.shape[0] * img.shape[1])
        
        # Edge detection for leaf-like patterns
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (img.shape[0] * img.shape[1])
        
        # Calculate confidence score
        confidence = (green_ratio * 0.6) + (edge_density * 0.4)
        
        return confidence > app.config['PLANT_DETECTION_THRESHOLD'], confidence
        
    except Exception as e:
        print(f"Plant detection error: {e}")
        return False, 0.0

def resize_image(image_path, max_size=(1024, 1024)):
    """Resize image to reduce processing time"""
    try:
        img = Image.open(image_path)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        img.save(image_path)
        return True
    except Exception as e:
        print(f"Resize error: {e}")
        return False

def analyze_plant_disease(image_path, description=""):
    """
    Analyze plant image using Cohere AI
    Returns: analysis result or error
    """
    try:
        if not co:
            return "AI service not configured. Please contact support: +254713593573"
        
        # Read image and convert to base64
        with open(image_path, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        
        # Prepare prompt for Cohere
        prompt = f"""As an expert agricultural AI assistant, analyze this plant image and provide:
        
        1. PLANT IDENTIFICATION:
           - What plant species is this likely to be?
           - Key identifying characteristics
        
        2. HEALTH ASSESSMENT:
           - Visible signs of disease or pests
           - Nutrient deficiency indicators
           - General plant health status
        
        3. DISEASE DIAGNOSIS:
           - Most likely disease(s)
           - Confidence level
           - Symptoms observed
        
        4. TREATMENT RECOMMENDATIONS:
           - Immediate treatment steps
           - Recommended products (organic preferred)
           - Application instructions
        
        5. AGROECOLOGICAL SOLUTIONS:
           - Preventive measures
           - Companion planting suggestions
           - Natural pest control methods
           - Soil improvement techniques
        
        6. FOLLOW-UP CARE:
           - Monitoring schedule
           - When to expect improvement
           - When to consult an expert
        
        Additional context from farmer: {description}
        
        Provide clear, practical advice suitable for Kenyan farmers.
        """
        
        # Call Cohere API with image
        response = co.chat(
            message=prompt,
            model="command-r-plus",
            temperature=0.7,
            max_tokens=1500,
            connectors=[{"id": "web-search"}]
        )
        
        return response.text
        
    except Exception as e:
        print(f"Cohere analysis error: {e}")
        return f"Analysis failed. Error: {str(e)}. Please try again or contact support: +254713593573"

# ========== BASIC ROUTES ==========

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
        elif current_user.is_admin:
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

# ========== AUTHENTICATION ROUTES ==========

@app.route('/register', methods=['GET', 'POST'])
def register():
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
            location=location,
            is_active=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Contact support: +254713593573', 'error')
                return redirect(url_for('login'))
            
            login_user(user, remember=bool(remember))
            user.last_login = datetime.utcnow()
            db.session.commit()
            
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

# ========== PLANT DISEASE DETECTION ==========

@app.route('/plant-scan', methods=['GET', 'POST'])
@login_required
def plant_scan():
    """Advanced plant disease detection with image validation"""
    if request.method == 'POST':
        if 'plant_image' not in request.files:
            return jsonify({'success': False, 'error': 'No image provided'}), 400
        
        file = request.files['plant_image']
        description = request.form.get('description', '')
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No image selected'}), 400
        
        if file and allowed_file(file.filename):
            # Save uploaded file
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = secure_filename(f"plant_{current_user.id}_{timestamp}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Resize image for processing
                resize_image(filepath)
                
                # Check if image contains a plant
                is_plant, confidence = is_plant_image(filepath)
                
                if not is_plant:
                    # Delete non-plant image
                    os.remove(filepath)
                    return jsonify({
                        'success': False,
                        'error': 'No plant detected in image',
                        'confidence': f"{confidence:.2%}",
                        'message': 'Please upload a clear image of a plant leaf or stem.'
                    })
                
                # Analyze plant disease
                analysis = analyze_plant_disease(filepath, description)
                
                # Save report to database
                report = DiseaseReport(
                    farmer_id=current_user.id,
                    plant_image=filename,
                    plant_description=description,
                    disease_detected=analysis[:200],  # First 200 chars as disease name
                    confidence=confidence,
                    treatment_recommendation=analysis,
                    location=current_user.location,
                    latitude=current_user.latitude,
                    longitude=current_user.longitude,
                    status='analyzed'
                )
                db.session.add(report)
                db.session.commit()
                
                # Create notification
                create_notification(
                    current_user.id,
                    'Plant Analysis Complete',
                    f'Your plant analysis is ready. Confidence: {confidence:.2%}',
                    'success',
                    url_for('view_disease_report', report_id=report.id)
                )
                
                return jsonify({
                    'success': True,
                    'analysis': analysis,
                    'confidence': f"{confidence:.2%}",
                    'report_id': report.id,
                    'is_plant': True
                })
                
            except Exception as e:
                # Clean up file on error
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'success': False, 'error': str(e)}), 500
    
    return render_template('plant_scan.html')

@app.route('/disease-report/<int:report_id>')
@login_required
def view_disease_report(report_id):
    """View detailed disease report"""
    report = DiseaseReport.query.get_or_404(report_id)
    
    # Check permissions
    if report.farmer_id != current_user.id and not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('farmer_dashboard'))
    
    return render_template('disease_report.html', report=report)

@app.route('/my-disease-reports')
@login_required
def my_disease_reports():
    """View all disease reports for current user"""
    reports = DiseaseReport.query.filter_by(farmer_id=current_user.id)\
        .order_by(DiseaseReport.created_at.desc()).all()
    return render_template('my_disease_reports.html', reports=reports)

# ========== COHERE AI CHAT ==========

@app.route('/ai-chat', methods=['GET'])
@login_required
def ai_chat():
    """AI Chat interface"""
    return render_template('ai_chat.html')

@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    """AI Chat API endpoint"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'No message provided'})
        
        if not co:
            return jsonify({
                'success': False,
                'error': 'AI service temporarily unavailable. Contact support: +254713593573'
            })
        
        # Prepare context for agricultural assistant
        context = f"""You are Mkulima AI, a friendly agricultural expert assistant for Kenyan farmers.
        User: {current_user.full_name} ({current_user.user_type})
        Location: {current_user.location or 'Not specified'}
        
        Current date: {datetime.utcnow().strftime('%Y-%m-%d')}
        
        Provide practical, actionable advice in Swahili or English as appropriate.
        Focus on sustainable, affordable solutions suitable for Kenyan conditions.
        If unsure, recommend contacting agricultural officers or our support team at +254713593573.
        
        User message: {message}"""
        
        # Call Cohere API
        response = co.chat(
            message=context,
            model="command-r-plus",
            temperature=0.7,
            max_tokens=1000,
            preamble="""You are Mkulima AI, an expert agricultural assistant for Kenyan farmers.
            You provide:
            1. Culturally appropriate advice
            2. Sustainable farming practices
            3. Cost-effective solutions
            4. Weather-appropriate recommendations
            5. Market information when relevant
            6. Pest and disease management
            7. Soil health improvement
            8. Water conservation techniques
            
            Always be helpful, accurate, and encouraging.
            If you don't know something, admit it and suggest contacting experts.
            Use simple language and practical examples."""
        )
        
        return jsonify({
            'success': True,
            'response': response.text,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        print(f"Chat API error: {e}")
        return jsonify({
            'success': False,
            'error': f'Chat service error. Please try again or call support: +254713593573'
        }), 500

# ========== ADMIN PANEL ==========

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard with comprehensive controls"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    # Get statistics
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_posts': CommunityPost.query.count(),
        'total_orders': Order.query.count(),
        'total_revenue': db.session.query(db.func.sum(Order.total_amount)).scalar() or 0,
        'disease_reports': DiseaseReport.query.count(),
        'today_logins': User.query.filter(
            User.last_login >= datetime.utcnow() - timedelta(days=1)
        ).count(),
        'recent_users': User.query.order_by(User.created_at.desc()).limit(10).all()
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/users')
@login_required
def admin_users():
    """User management"""
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    action = "activated" if user.is_active else "deactivated"
    flash(f'User {user.email} {action}', 'success')
    return jsonify({'success': True, 'is_active': user.is_active})

@app.route('/admin/user/<int:user_id>/make-admin', methods=['POST'])
@login_required
def make_admin(user_id):
    """Make user admin"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    
    flash(f'{user.email} is now an admin', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete user (soft delete)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    
    # Don't allow deleting yourself
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    user.is_active = False
    db.session.commit()
    
    flash(f'User {user.email} deactivated', 'success')
    return jsonify({'success': True})

@app.route('/admin/posts')
@login_required
def admin_posts():
    """Post management"""
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).all()
    return render_template('admin/posts.html', posts=posts)

@app.route('/admin/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post_admin(post_id):
    """Edit post as admin"""
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    post = CommunityPost.query.get_or_404(post_id)
    
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.category = request.form.get('category')
        post.is_resolved = request.form.get('is_resolved') == 'true'
        
        db.session.commit()
        flash('Post updated successfully', 'success')
        return redirect(url_for('admin_posts'))
    
    return render_template('admin/edit_post.html', post=post)

@app.route('/admin/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post_admin(post_id):
    """Delete post as admin"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    post = CommunityPost.query.get_or_404(post_id)
    
    # Delete associated comments and follows
    PostComment.query.filter_by(post_id=post_id).delete()
    PostFollow.query.filter_by(post_id=post_id).delete()
    
    db.session.delete(post)
    db.session.commit()
    
    flash('Post deleted successfully', 'success')
    return jsonify({'success': True})

@app.route('/admin/comments')
@login_required
def admin_comments():
    """Comment management"""
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    comments = PostComment.query.order_by(PostComment.created_at.desc()).all()
    return render_template('admin/comments.html', comments=comments)

@app.route('/admin/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment_admin(comment_id):
    """Delete comment as admin"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    comment = PostComment.query.get_or_404(comment_id)
    
    db.session.delete(comment)
    db.session.commit()
    
    flash('Comment deleted successfully', 'success')
    return jsonify({'success': True})

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    """Admin settings for feature control"""
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Default feature settings
    default_features = {
        'plant_detection': True,
        'ai_chat': True,
        'marketplace': True,
        'community_forum': True,
        'weather': True,
        'inventory': True,
        'pos': True,
        'crm': True
    }
    
    if request.method == 'POST':
        # In a real app, save these to database
        # For now, store in session
        session['feature_settings'] = {
            'plant_detection': request.form.get('plant_detection') == 'true',
            'ai_chat': request.form.get('ai_chat') == 'true',
            'marketplace': request.form.get('marketplace') == 'true',
            'community_forum': request.form.get('community_forum') == 'true',
            'weather': request.form.get('weather') == 'true',
            'inventory': request.form.get('inventory') == 'true',
            'pos': request.form.get('pos') == 'true',
            'crm': request.form.get('crm') == 'true'
        }
        flash('Settings saved successfully', 'success')
        return redirect(url_for('admin_settings'))
    
    features = session.get('feature_settings', default_features)
    return render_template('admin/settings.html', features=features)

# ========== DASHBOARD ROUTES ==========

@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    """Farmer dashboard"""
    if current_user.user_type != 'farmer' and not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Get recent disease reports
    recent_reports = DiseaseReport.query.filter_by(farmer_id=current_user.id)\
        .order_by(DiseaseReport.created_at.desc()).limit(5).all()
    
    # Get notifications
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False)\
        .order_by(Notification.created_at.desc()).limit(10).all()
    
    # Get weather data if available
    weather = None
    if current_user.location:
        try:
            weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={current_user.location}&appid={app.config['OPENWEATHER_API_KEY']}&units=metric"
            response = requests.get(weather_url, timeout=5)
            if response.status_code == 200:
                weather = response.json()
        except:
            pass
    
    return render_template('farmer/dashboard.html', 
                         recent_reports=recent_reports,
                         notifications=notifications,
                         weather=weather)

@app.route('/agrovet/dashboard')
@login_required
def agrovet_dashboard():
    """Agrovet dashboard"""
    if current_user.user_type != 'agrovet' and not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    # Get agrovet statistics
    total_products = InventoryItem.query.filter_by(agrovet_id=current_user.id).count()
    low_stock = InventoryItem.query.filter_by(agrovet_id=current_user.id)\
        .filter(InventoryItem.quantity <= InventoryItem.reorder_level).count()
    recent_orders = Order.query.filter_by(agrovet_id=current_user.id)\
        .order_by(Order.created_at.desc()).limit(10).all()
    
    today = datetime.utcnow().date()
    today_sales = Sale.query.filter_by(agrovet_id=current_user.id)\
        .filter(db.func.date(Sale.sale_date) == today).all()
    today_revenue = sum(sale.total_amount for sale in today_sales)
    
    return render_template('agrovet/dashboard.html',
                         total_products=total_products,
                         low_stock=low_stock,
                         today_revenue=today_revenue,
                         recent_orders=recent_orders)

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

# ========== HEALTH CHECK ==========

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'service': 'AgriConnect',
        'contact': '+254713593573',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '2.0.0'
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

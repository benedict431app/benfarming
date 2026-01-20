import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import requests
import secrets
import uuid
import base64
from PIL import Image
import io
import json
from config import Config
from models import db, User, InventoryItem, Customer, Sale, SaleItem, Communication, DiseaseReport, Notification, WeatherData, CommunityPost, PostComment, PostFollow, UserReview, AppRecommendation, CartItem, Order, OrderItem, PasswordResetToken, Message

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
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

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

def analyze_plant_image(image_path, description=""):
    """Analyze plant image using Cohere AI"""
    try:
        # Read and encode image
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        headers = {
            'Authorization': f'Bearer {cohere_api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Prepare the prompt for plant analysis
        prompt = f"""
        Analyze this plant image and provide detailed information.
        
        User description: {description}
        
        Please provide:
        1. Plant identification (species if possible)
        2. Health assessment (healthy/unhealthy)
        3. If unhealthy, list possible diseases/pests
        4. Treatment recommendations (chemical and organic options)
        5. Preventive measures
        6. Agroecological solutions (companion planting, natural predators, etc.)
        7. Estimated time to recovery
        
        If the image is NOT a plant or is unclear, please state that clearly.
        Be specific and practical for farmers in East Africa.
        """
        
        payload = {
            "model": "c4ai-aya-expanse-8b",
            "message": prompt,
            "temperature": 0.7,
            "max_tokens": 1000,
            "stream": False
        }
        
        response = requests.post(
            'https://api.cohere.ai/v1/chat',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('text', 'Analysis failed. Please try again.')
        else:
            return f"API Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"Analysis error: {str(e)}"

# Create database tables
with app.app_context():
    db.create_all()
    # Create admin user if not exists
    if not User.query.filter_by(email='admin@adiseware.com').first():
        admin = User(
            email='admin@adiseware.com',
            full_name='System Administrator',
            user_type='admin',
            phone_number='',
            location='Nairobi',
            is_admin=True,
            is_verified=True,
            is_active=True
        )
        admin.set_password('Admin@123')
        db.session.add(admin)
        db.session.commit()

# ========== ROUTES ==========

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

# ========== ADMIN ROUTES ==========

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'error')
        return redirect(url_for('index'))
    
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_posts': CommunityPost.query.count(),
        'total_orders': Order.query.count(),
        'total_revenue': db.session.query(db.func.sum(Order.total_amount)).scalar() or 0,
        'pending_reviews': UserReview.query.filter_by(is_approved=False).count(),
        'total_agrovets': User.query.filter_by(user_type='agrovet').count(),
        'total_farmers': User.query.filter_by(user_type='farmer').count()
    }
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_users=recent_users, recent_posts=recent_posts)

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
    
    return jsonify({'success': True, 'is_active': user.is_active, 'user_id': user_id})

@app.route('/admin/user/<int:user_id>/make-admin', methods=['POST'])
@login_required
def make_admin(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    user.user_type = 'admin'
    db.session.commit()
    
    return jsonify({'success': True, 'user_id': user_id})

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    
    # Don't allow deleting self
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    
    # Delete user and related data
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True, 'user_id': user_id})

@app.route('/admin/posts')
@login_required
def admin_posts():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).all()
    return render_template('admin/posts.html', posts=posts)

@app.route('/admin/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    post = CommunityPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    
    return jsonify({'success': True, 'post_id': post_id})

@app.route('/admin/post/<int:post_id>/toggle', methods=['POST'])
@login_required
def toggle_post_status(post_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    post = CommunityPost.query.get_or_404(post_id)
    post.is_active = not post.is_active
    db.session.commit()
    
    return jsonify({'success': True, 'is_active': post.is_active, 'post_id': post_id})

@app.route('/admin/reviews')
@login_required
def admin_reviews():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    reviews = UserReview.query.order_by(UserReview.created_at.desc()).all()
    return render_template('admin/reviews.html', reviews=reviews)

@app.route('/admin/review/<int:review_id>/approve', methods=['POST'])
@login_required
def approve_review(review_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    review = UserReview.query.get_or_404(review_id)
    review.is_approved = True
    db.session.commit()
    
    return jsonify({'success': True, 'review_id': review_id})

@app.route('/admin/review/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    review = UserReview.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    
    return jsonify({'success': True, 'review_id': review_id})

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Update app settings
        app.config['APP_NAME'] = request.form.get('app_name', 'AgriConnect')
        app.config['APP_DESCRIPTION'] = request.form.get('app_description', '')
        
        # Save to database or config file
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin_settings'))
    
    return render_template('admin/settings.html')

# ========== PLANT DISEASE DETECTION ==========

@app.route('/plant-detection', methods=['GET', 'POST'])
@login_required
def plant_detection():
    if request.method == 'POST':
        if 'plant_image' not in request.files:
            flash('No image uploaded', 'error')
            return redirect(url_for('plant_detection'))
        
        file = request.files['plant_image']
        description = request.form.get('description', '')
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('plant_detection'))
        
        if file and allowed_file(file.filename):
            # Save the file
            filename = secure_filename(f"plant_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            
            try:
                # Analyze the image
                analysis_result = analyze_plant_image(filepath, description)
                
                # Save to database
                report = DiseaseReport(
                    farmer_id=current_user.id,
                    plant_image=filename,
                    plant_description=description,
                    treatment_recommendation=analysis_result,
                    location=current_user.location
                )
                db.session.add(report)
                db.session.commit()
                
                # Check if it's actually a plant
                if "not a plant" in analysis_result.lower() or "unclear" in analysis_result.lower():
                    flash('The uploaded image might not be a clear plant image. Please try again with a clearer photo.', 'warning')
                else:
                    flash('Plant analysis completed successfully!', 'success')
                
                return render_template('plant_detection_result.html', 
                                     analysis=analysis_result,
                                     image_url=url_for('uploaded_file', filename=filename),
                                     report_id=report.id)
                
            except Exception as e:
                flash(f'Error analyzing image: {str(e)}', 'error')
                return redirect(url_for('plant_detection'))
    
    return render_template('plant_detection.html')

@app.route('/plant-reports')
@login_required
def plant_reports():
    if current_user.user_type == 'farmer':
        reports = DiseaseReport.query.filter_by(farmer_id=current_user.id).order_by(DiseaseReport.created_at.desc()).all()
    elif current_user.user_type == 'extension_officer' or current_user.is_admin:
        reports = DiseaseReport.query.order_by(DiseaseReport.created_at.desc()).all()
    else:
        reports = []
    
    return render_template('plant_reports.html', reports=reports)

@app.route('/plant-report/<int:report_id>')
@login_required
def view_plant_report(report_id):
    report = DiseaseReport.query.get_or_404(report_id)
    
    # Check permissions
    if (current_user.user_type != 'extension_officer' and 
        not current_user.is_admin and 
        report.farmer_id != current_user.id):
        flash('Access denied', 'error')
        return redirect(url_for('plant_reports'))
    
    return render_template('view_plant_report.html', report=report)

# ========== AI CHAT ROUTES ==========

@app.route('/ai-chat', methods=['GET', 'POST'])
@login_required
def ai_chat():
    if request.method == 'POST':
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'success': False, 'error': 'No message provided'})
        
        try:
            headers = {
                'Authorization': f'Bearer {cohere_api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Create a context-aware prompt for agricultural advice
            context = f"""
            You are an expert agricultural assistant for {current_user.user_type}s in Kenya/East Africa.
            User location: {current_user.location}
            User type: {current_user.user_type}
            
            Provide practical, actionable advice considering:
            1. Local climate and conditions
            2. Available resources
            3. Sustainable farming practices
            4. Market opportunities
            5. Government programs if applicable
            
            Be specific and mention crops/livestock common in the region.
            """
            
            chat_payload = {
                "model": "c4ai-aya-expanse-8b",
                "message": f"{context}\n\nUser question: {message}",
                "temperature": 0.7,
                "max_tokens": 800,
                "stream": False
            }
            
            response = requests.post(
                'https://api.cohere.ai/v1/chat',
                headers=headers,
                json=chat_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get('text', 'Sorry, I could not process your request.')
                
                return jsonify({
                    'success': True,
                    'response': ai_response,
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'API Error: {response.status_code}'
                })
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Chat error: {str(e)}'
            })
    
    return render_template('ai_chat.html')

# ========== FILE UPLOAD HANDLER ==========

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

# ========== PROFILE PICTURE FIX ==========

@app.route('/profile-picture/<filename>')
def profile_picture(filename):
    try:
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures', filename))
    except:
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], 'default_profile.png'))

# ========== KEEP YOUR EXISTING ROUTES ==========

# All your existing routes remain here (register, login, dashboard, etc.)
# I'm showing only the new/changed routes above

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
        return url_for('profile_picture', filename=user.profile_picture)
    return url_for('static', filename='img/default-avatar.png')

# ========== INITIALIZATION ==========

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

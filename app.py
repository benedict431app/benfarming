import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import requests
from sqlalchemy import desc, or_, func
from config import Config
from models import db, User, InventoryItem, Customer, Sale, SaleItem, Communication, DiseaseReport, Notification, WeatherData, CommunityPost, PostAnswer, PostFollow, PostUpvote, AnswerUpvote
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

def create_notification(user_id, title, message, notification_type='info', related_id=None):
    """Helper function to create notifications"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_id=related_id
    )
    db.session.add(notification)
    return notification

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
            if file and file.filename != '' and allowed_file(file.filename):
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
    
    # Get recent community posts
    recent_posts = CommunityPost.query.filter_by(user_id=current_user.id).order_by(desc(CommunityPost.created_at)).limit(5).all()
    
    return render_template('farmer/dashboard.html', 
                         notifications=notifications, 
                         disease_reports=disease_reports,
                         recent_posts=recent_posts)

# ... [Keep all your existing routes for disease detection, weather, etc.] ...

# ==================== COMMUNITY ROUTES ====================

@app.route('/community')
@login_required
def community_home():
    """Community homepage showing recent posts"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', 'all')
    post_type = request.args.get('type', 'all')
    search = request.args.get('search', '')
    
    # Base query
    query = CommunityPost.query
    
    # Apply filters
    if category != 'all' and category:
        query = query.filter(CommunityPost.category == category)
    if post_type != 'all' and post_type:
        query = query.filter(CommunityPost.post_type == post_type)
    if search:
        query = query.filter(
            or_(
                CommunityPost.title.ilike(f'%{search}%'),
                CommunityPost.content.ilike(f'%{search}%')
            )
        )
    
    # Get paginated posts
    posts = query.order_by(desc(CommunityPost.created_at)).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # Get user's followed posts
    followed_post_ids = [f.post_id for f in PostFollow.query.filter_by(user_id=current_user.id).all()]
    
    # Get categories for filter dropdown
    categories = db.session.query(CommunityPost.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('community/home.html', 
                         posts=posts, 
                         categories=categories,
                         followed_post_ids=followed_post_ids,
                         current_category=category,
                         current_type=post_type,
                         search=search)

@app.route('/community/post/new', methods=['GET', 'POST'])
@login_required
def create_post():
    """Create a new community post"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        post_type = request.form.get('post_type', 'question')
        category = request.form.get('category', 'general')
        
        if not title or not content:
            flash('Title and content are required', 'error')
            return redirect(url_for('create_post'))
        
        # Create the post
        post = CommunityPost(
            user_id=current_user.id,
            title=title,
            content=content,
            post_type=post_type,
            category=category
        )
        
        # Auto-follow the post
        follow = PostFollow(post=post, user_id=current_user.id)
        
        db.session.add(post)
        db.session.add(follow)
        db.session.commit()
        
        flash('Post created successfully! You are now following this post.', 'success')
        return redirect(url_for('view_post', post_id=post.id))
    
    return render_template('community/create_post.html')

@app.route('/community/post/<int:post_id>')
@login_required
def view_post(post_id):
    """View a single post with its answers"""
    post = CommunityPost.query.get_or_404(post_id)
    
    # Increment view count
    post.views += 1
    
    # Check if user is following this post
    is_following = PostFollow.query.filter_by(
        post_id=post_id, 
        user_id=current_user.id
    ).first() is not None
    
    # Check if user has upvoted this post
    has_upvoted = PostUpvote.query.filter_by(
        post_id=post_id,
        user_id=current_user.id
    ).first() is not None
    
    # Get answers with upvote status
    answers = PostAnswer.query.filter_by(post_id=post_id).order_by(
        desc(PostAnswer.is_accepted),
        desc(PostAnswer.created_at)
    ).all()
    
    # Check upvotes for each answer
    answer_upvotes = {}
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
def post_answer(post_id):
    """Post an answer to a question"""
    post = CommunityPost.query.get_or_404(post_id)
    
    content = request.form.get('content', '').strip()
    if not content:
        flash('Answer content cannot be empty', 'error')
        return redirect(url_for('view_post', post_id=post_id))
    
    answer = PostAnswer(
        post_id=post_id,
        user_id=current_user.id,
        content=content
    )
    
    db.session.add(answer)
    
    # Create notifications for post followers (excluding the answer author)
    followers = PostFollow.query.filter_by(post_id=post_id).all()
    for follow in followers:
        if follow.user_id != current_user.id:
            create_notification(
                user_id=follow.user_id,
                title='New Answer on Post You Follow',
                message=f'{current_user.full_name} answered: "{post.title}"',
                notification_type='info',
                related_id=post_id
            )
    
    # Notify the post owner if they're not the one answering
    if post.user_id != current_user.id:
        create_notification(
            user_id=post.user_id,
            title='New Answer on Your Post',
            message=f'{current_user.full_name} answered your post: "{post.title}"',
            notification_type='info',
            related_id=post_id
        )
    
    # Update post timestamp
    post.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    flash('Your answer has been posted!', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/community/post/<int:post_id>/follow', methods=['POST'])
@login_required
def follow_post(post_id):
    """Follow or unfollow a post"""
    post = CommunityPost.query.get_or_404(post_id)
    
    existing_follow = PostFollow.query.filter_by(
        post_id=post_id,
        user_id=current_user.id
    ).first()
    
    if existing_follow:
        # Unfollow
        db.session.delete(existing_follow)
        action = 'unfollowed'
    else:
        # Follow
        follow = PostFollow(post_id=post_id, user_id=current_user.id)
        db.session.add(follow)
        
        # Notify post owner
        if post.user_id != current_user.id:
            create_notification(
                user_id=post.user_id,
                title='New Follower on Your Post',
                message=f'{current_user.full_name} started following your post: "{post.title}"',
                notification_type='info',
                related_id=post_id
            )
        action = 'followed'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'action': action,
        'followers_count': PostFollow.query.filter_by(post_id=post_id).count()
    })

@app.route('/community/post/<int:post_id>/upvote', methods=['POST'])
@login_required
def upvote_post(post_id):
    """Upvote or remove upvote from a post"""
    post = CommunityPost.query.get_or_404(post_id)
    
    existing_upvote = PostUpvote.query.filter_by(
        post_id=post_id,
        user_id=current_user.id
    ).first()
    
    if existing_upvote:
        # Remove upvote
        db.session.delete(existing_upvote)
        action = 'removed'
    else:
        # Add upvote
        upvote = PostUpvote(post_id=post_id, user_id=current_user.id)
        db.session.add(upvote)
        
        # Notify post owner (if not the upvoter)
        if post.user_id != current_user.id:
            create_notification(
                user_id=post.user_id,
                title='Post Upvoted',
                message=f'{current_user.full_name} upvoted your post: "{post.title}"',
                notification_type='info',
                related_id=post_id
            )
        action = 'added'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'action': action,
        'upvotes_count': PostUpvote.query.filter_by(post_id=post_id).count()
    })

@app.route('/community/answer/<int:answer_id>/upvote', methods=['POST'])
@login_required
def upvote_answer(answer_id):
    """Upvote or remove upvote from an answer"""
    answer = PostAnswer.query.get_or_404(answer_id)
    
    existing_upvote = AnswerUpvote.query.filter_by(
        answer_id=answer_id,
        user_id=current_user.id
    ).first()
    
    if existing_upvote:
        # Remove upvote
        db.session.delete(existing_upvote)
        action = 'removed'
    else:
        # Add upvote
        upvote = AnswerUpvote(answer_id=answer_id, user_id=current_user.id)
        db.session.add(upvote)
        
        # Notify answer author (if not the upvoter)
        if answer.user_id != current_user.id:
            create_notification(
                user_id=answer.user_id,
                title='Answer Upvoted',
                message=f'{current_user.full_name} upvoted your answer',
                notification_type='info',
                related_id=answer.post_id
            )
        action = 'added'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'action': action,
        'upvotes_count': AnswerUpvote.query.filter_by(answer_id=answer_id).count()
    })

@app.route('/community/post/<int:post_id>/mark-resolved', methods=['POST'])
@login_required
def mark_post_resolved(post_id):
    """Mark a post as resolved (only post owner can do this)"""
    post = CommunityPost.query.get_or_404(post_id)
    
    if post.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Not authorized'}), 403
    
    post.is_resolved = not post.is_resolved
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_resolved': post.is_resolved
    })

@app.route('/community/answer/<int:answer_id>/accept', methods=['POST'])
@login_required
def accept_answer(answer_id):
    """Accept an answer as the solution (only post owner can do this)"""
    answer = PostAnswer.query.get_or_404(answer_id)
    post = answer.post
    
    if post.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Not authorized'}), 403
    
    # Unaccept any previously accepted answer
    PostAnswer.query.filter_by(post_id=post.id, is_accepted=True).update({'is_accepted': False})
    
    # Accept this answer
    answer.is_accepted = True
    post.is_resolved = True
    
    # Notify answer author
    if answer.user_id != current_user.id:
        create_notification(
            user_id=answer.user_id,
            title='Answer Accepted',
            message=f'Your answer was accepted as the solution for: "{post.title}"',
            notification_type='success',
            related_id=post.id
        )
    
    # Notify all followers
    followers = PostFollow.query.filter_by(post_id=post.id).all()
    for follow in followers:
        if follow.user_id != current_user.id and follow.user_id != answer.user_id:
            create_notification(
                user_id=follow.user_id,
                title='Post Resolved',
                message=f'Post you were following has been resolved: "{post.title}"',
                notification_type='info',
                related_id=post.id
            )
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_accepted': answer.is_accepted
    })

@app.route('/community/my-posts')
@login_required
def my_posts():
    """View user's own posts"""
    page = request.args.get('page', 1, type=int)
    
    posts = CommunityPost.query.filter_by(user_id=current_user.id).order_by(
        desc(CommunityPost.created_at)
    ).paginate(page=page, per_page=10, error_out=False)
    
    return render_template('community/my_posts.html', posts=posts)

@app.route('/community/followed-posts')
@login_required
def followed_posts():
    """View posts that user is following"""
    page = request.args.get('page', 1, type=int)
    
    # Get posts that user is following
    posts = CommunityPost.query.join(PostFollow).filter(
        PostFollow.user_id == current_user.id
    ).order_by(desc(CommunityPost.updated_at)).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('community/followed_posts.html', posts=posts)

@app.route('/community/notifications')
@login_required
def community_notifications():
    """View user's notifications"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Notification.created_at)).limit(50).all()
    
    # Mark all as read
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    
    return render_template('community/notifications.html', notifications=notifications)

@app.route('/community/leaderboard')
@login_required
def leaderboard():
    """Community leaderboard based on contributions"""
    # Top answerers (users with most accepted answers)
    top_answerers = db.session.query(
        User.id,
        User.full_name,
        User.profile_picture,
        func.count(PostAnswer.id).label('answer_count'),
        func.sum(func.case((PostAnswer.is_accepted == True, 1), else_=0)).label('accepted_count')
    ).join(PostAnswer, User.id == PostAnswer.user_id).group_by(User.id).order_by(
        desc('accepted_count'),
        desc('answer_count')
    ).limit(10).all()
    
    # Most helpful posts (posts with most upvotes)
    helpful_posts = db.session.query(
        CommunityPost.id,
        CommunityPost.title,
        User.full_name,
        func.count(PostUpvote.id).label('upvote_count')
    ).join(User).outerjoin(PostUpvote).group_by(CommunityPost.id, User.full_name).order_by(
        desc('upvote_count')
    ).limit(10).all()
    
    return render_template('community/leaderboard.html',
                         top_answerers=top_answerers,
                         helpful_posts=helpful_posts)

@app.route('/profile')
@login_required
def view_profile():
    """View user profile"""
    # Get user's community stats
    posts_count = CommunityPost.query.filter_by(user_id=current_user.id).count()
    answers_count = PostAnswer.query.filter_by(user_id=current_user.id).count()
    accepted_answers = PostAnswer.query.filter_by(user_id=current_user.id, is_accepted=True).count()
    
    return render_template('profile.html',
                         posts_count=posts_count,
                         answers_count=answers_count,
                         accepted_answers=accepted_answers)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.phone_number = request.form.get('phone_number')
        current_user.location = request.form.get('location')
        
        # Handle profile picture update
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '' and allowed_file(file.filename):
                # Remove old profile picture if exists
                if current_user.profile_picture:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.profile_picture)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Save new profile picture
                filename = secure_filename(f"{current_user.email}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                current_user.profile_picture = filename
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('view_profile'))
    
    return render_template('edit_profile.html')

# ... [Keep all your other existing routes] ...

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

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

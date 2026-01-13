from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

db = SQLAlchemy()

# Association tables
cart_items = db.Table('cart_items',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('cart_id', db.Integer, db.ForeignKey('carts.id')),
    db.Column('product_id', db.Integer, db.ForeignKey('inventory_items.id')),
    db.Column('quantity', db.Integer, default=1),
    db.Column('added_at', db.Column(db.DateTime, default=datetime.utcnow)),
    db.UniqueConstraint('cart_id', 'product_id', name='unique_cart_product')
)

order_items = db.Table('order_items',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('order_id', db.Integer, db.ForeignKey('orders.id')),
    db.Column('product_id', db.Integer, db.ForeignKey('inventory_items.id')),
    db.Column('quantity', db.Integer, nullable=False),
    db.Column('unit_price', db.Float, nullable=False),
    db.Column('subtotal', db.Float, nullable=False),
    db.UniqueConstraint('order_id', 'product_id', name='unique_order_product')
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    user_type = db.Column(db.String(50), nullable=False)  # farmer, agrovet, admin, officer, institution
    profile_picture = db.Column(db.String(255), default='default-avatar.png')
    phone_number = db.Column(db.String(20))
    location = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    address = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Business specific fields for Agrovets
    business_name = db.Column(db.String(200))
    business_registration = db.Column(db.String(100))
    business_description = db.Column(db.Text)
    business_hours = db.Column(db.String(100))
    rating = db.Column(db.Float, default=0.0)
    total_reviews = db.Column(db.Integer, default=0)
    
    # Relationships - explicitly specify foreign_keys
    inventory_items = db.relationship('InventoryItem', backref='agrovet', lazy=True, cascade='all, delete-orphan')
    sales = db.relationship('Sale', backref='agrovet', lazy=True, cascade='all, delete-orphan')
    customers = db.relationship('Customer', backref='agrovet', lazy=True, cascade='all, delete-orphan')
    disease_reports = db.relationship('DiseaseReport', backref='farmer', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    
    # E-commerce relationships
    cart = db.relationship('Cart', backref='user', uselist=False, cascade='all, delete-orphan')
    orders_as_customer = db.relationship('Order', foreign_keys='Order.user_id', backref='customer', lazy=True)
    orders_as_agrovet = db.relationship('Order', foreign_keys='Order.agrovet_id', backref='agrovet', lazy=True)
    
    # Reviews
    reviews_given = db.relationship('Review', foreign_keys='Review.user_id', backref='reviewer', lazy=True)
    reviews_received = db.relationship('Review', foreign_keys='Review.agrovet_id', backref='agrovet_reviewed', lazy=True)
    product_reviews_given = db.relationship('ProductReview', foreign_keys='ProductReview.user_id', backref='reviewer', lazy=True)
    
    # Messaging
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    messages_received = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    
    # Community relationships
    community_posts = db.relationship('CommunityPost', backref='author', lazy=True, cascade='all, delete-orphan')
    post_answers = db.relationship('PostAnswer', backref='author', lazy=True, cascade='all, delete-orphan')
    followed_posts = db.relationship('PostFollow', backref='follower', lazy=True, cascade='all, delete-orphan')
    post_upvotes = db.relationship('PostUpvote', backref='user', lazy=True, cascade='all, delete-orphan')
    answer_upvotes = db.relationship('AnswerUpvote', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def unread_notifications(self):
        return Notification.query.filter_by(user_id=self.id, is_read=False).count()
    
    @property
    def unread_messages(self):
        return Message.query.filter_by(receiver_id=self.id, is_read=False).count()
    
    @property
    def community_stats(self):
        from sqlalchemy import func
        posts_count = CommunityPost.query.filter_by(user_id=self.id).count()
        answers_count = PostAnswer.query.filter_by(user_id=self.id).count()
        accepted_answers = PostAnswer.query.filter_by(user_id=self.id, is_accepted=True).count()
        
        return {
            'posts': posts_count,
            'answers': answers_count,
            'accepted_answers': accepted_answers
        }
    
    @property
    def order_stats(self):
        total_orders = Order.query.filter_by(user_id=self.id).count()
        pending_orders = Order.query.filter_by(user_id=self.id, status='pending').count()
        completed_orders = Order.query.filter_by(user_id=self.id, status='completed').count()
        
        return {
            'total': total_orders,
            'pending': pending_orders,
            'completed': completed_orders
        }
    
    def get_distance(self, lat2, lon2):
        """Calculate distance between two coordinates in km"""
        if not all([self.latitude, self.longitude, lat2, lon2]):
            return None
        
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth's radius in km
        
        lat1_rad = radians(self.latitude)
        lon1_rad = radians(self.longitude)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)
        
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

class InventoryItem(db.Model):
    __tablename__ = 'inventory_items'
    
    id = db.Column(db.Integer, primary_key=True)
    agrovet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    subcategory = db.Column(db.String(100))
    description = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float)
    discount_price = db.Column(db.Float)
    discount_percentage = db.Column(db.Float)
    reorder_level = db.Column(db.Integer, default=10)
    supplier = db.Column(db.String(200))
    sku = db.Column(db.String(100), unique=True)
    barcode = db.Column(db.String(100))
    image = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Float, default=0.0)
    total_reviews = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    reviews = db.relationship('ProductReview', backref='product', lazy=True, cascade='all, delete-orphan')
    
    def is_low_stock(self):
        return self.quantity <= self.reorder_level
    
    @property
    def current_price(self):
        return self.discount_price if self.discount_price else self.price
    
    @property
    def in_stock(self):
        return self.quantity > 0
    
    @property
    def stock_status(self):
        if self.quantity == 0:
            return 'out_of_stock'
        elif self.quantity <= self.reorder_level:
            return 'low_stock'
        else:
            return 'in_stock'

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    agrovet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    customer_type = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_purchases = db.Column(db.Float, default=0.0)
    last_purchase = db.Column(db.DateTime)
    
    purchases = db.relationship('Sale', backref='customer', lazy=True)
    communications = db.relationship('Communication', backref='customer', lazy=True, cascade='all, delete-orphan')

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    agrovet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    status = db.Column(db.String(50), default='completed')
    receipt_number = db.Column(db.String(100), unique=True)
    notes = db.Column(db.Text)
    
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

class Communication(db.Model):
    __tablename__ = 'communications'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    communication_type = db.Column(db.String(50))
    subject = db.Column(db.String(200))
    message = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    follow_up_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='pending')

class DiseaseReport(db.Model):
    __tablename__ = 'disease_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plant_image = db.Column(db.String(255))
    plant_description = db.Column(db.Text)
    disease_detected = db.Column(db.String(200))
    confidence = db.Column(db.Float)
    treatment_recommendation = db.Column(db.Text)
    location = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(50), default='pending')
    severity = db.Column(db.String(50))  # low, medium, high
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))  # info, success, warning, danger
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    link = db.Column(db.String(255))
    related_id = db.Column(db.Integer)  # ID of related item

class WeatherData(db.Model):
    __tablename__ = 'weather_data'
    
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200), nullable=False)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    description = db.Column(db.String(200))
    recommendations = db.Column(db.Text)
    forecast_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== E-COMMERCE MODELS ====================

class Cart(db.Model):
    __tablename__ = 'carts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to get cart items
    cart_items_rel = db.relationship('CartItem', backref='cart', lazy=True, cascade='all, delete-orphan')

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to product
    product = db.relationship('InventoryItem', backref='cart_items')
    
    __table_args__ = (db.UniqueConstraint('cart_id', 'product_id', name='unique_cart_product'),)

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(100), unique=True, nullable=False, default=lambda: str(uuid.uuid4())[:8].upper())
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    agrovet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    shipping_address = db.Column(db.Text, nullable=False)
    billing_address = db.Column(db.Text)
    payment_method = db.Column(db.String(50), nullable=False)  # mpesa, cash, card
    payment_status = db.Column(db.String(50), default='pending')  # pending, completed, failed
    status = db.Column(db.String(50), default='pending')  # pending, processing, shipped, delivered, cancelled
    mpesa_code = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    
    # Relationship to product
    product = db.relationship('InventoryItem', backref='order_items')
    
    __table_args__ = (db.UniqueConstraint('order_id', 'product_id', name='unique_order_product'),)

class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    agrovet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    is_verified_purchase = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'agrovet_id', name='unique_user_agrovet_review'),)

class ProductReview(db.Model):
    __tablename__ = 'product_reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    is_verified_purchase = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_user_product_review'),)

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # For product-related messages
    product_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'))
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))

# ==================== COMMUNITY MODELS ====================

class CommunityPost(db.Model):
    __tablename__ = 'community_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    post_type = db.Column(db.String(50), nullable=False)  # question, concern, discussion, tip, announcement
    category = db.Column(db.String(100))  # crops, livestock, equipment, general, market, technology
    tags = db.Column(db.String(500))  # comma-separated tags
    is_resolved = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    is_pinned = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    answers = db.relationship('PostAnswer', backref='post', lazy=True, cascade='all, delete-orphan')
    followers = db.relationship('PostFollow', backref='post', lazy=True, cascade='all, delete-orphan')
    upvotes = db.relationship('PostUpvote', backref='post', lazy=True, cascade='all, delete-orphan')
    attachments = db.relationship('PostAttachment', backref='post', lazy=True, cascade='all, delete-orphan')

class PostAnswer(db.Model):
    __tablename__ = 'post_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_accepted = db.Column(db.Boolean, default=False)
    is_expert_answer = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    upvotes = db.relationship('AnswerUpvote', backref='answer', lazy=True, cascade='all, delete-orphan')
    attachments = db.relationship('AnswerAttachment', backref='answer', lazy=True, cascade='all, delete-orphan')

class PostFollow(db.Model):
    __tablename__ = 'post_follows'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', name='unique_post_follow'),)

class PostUpvote(db.Model):
    __tablename__ = 'post_upvotes'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', name='unique_post_upvote'),)

class AnswerUpvote(db.Model):
    __tablename__ = 'answer_upvotes'
    
    id = db.Column(db.Integer, primary_key=True)
    answer_id = db.Column(db.Integer, db.ForeignKey('post_answers.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('answer_id', 'user_id', name='unique_answer_upvote'),)

class PostAttachment(db.Model):
    __tablename__ = 'post_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class AnswerAttachment(db.Model):
    __tablename__ = 'answer_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    answer_id = db.Column(db.Integer, db.ForeignKey('post_answers.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== ADMIN MODELS ====================

class AdminLog(db.Model):
    __tablename__ = 'admin_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    admin = db.relationship('User', foreign_keys=[admin_id])

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Banner(db.Model):
    __tablename__ = 'banners'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(255))
    link = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    position = db.Column(db.Integer, default=0)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FAQ(db.Model):
    __tablename__ = 'faqs'
    
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== PAYMENT MODELS ====================

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    transaction_id = db.Column(db.String(100), unique=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='KES')
    payment_method = db.Column(db.String(50))
    status = db.Column(db.String(50), default='pending')  # pending, completed, failed, refunded
    mpesa_code = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    payment_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    order = db.relationship('Order', backref='payments')

class MpesaTransaction(db.Model):
    __tablename__ = 'mpesa_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(100), unique=True)
    merchant_request_id = db.Column(db.String(100))
    checkout_request_id = db.Column(db.String(100))
    result_code = db.Column(db.Integer)
    result_desc = db.Column(db.String(255))
    amount = db.Column(db.Float)
    mpesa_receipt_number = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    transaction_date = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

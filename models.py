from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    user_type = db.Column(db.String(50), nullable=False)  # farmer, agrovet, extension_officer, learning_institution, admin
    phone_number = db.Column(db.String(20))
    location = db.Column(db.String(100))
    profile_picture = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    inventory_items = db.relationship('InventoryItem', backref='agrovet', lazy=True, foreign_keys='InventoryItem.agrovet_id')
    farmer_orders = db.relationship('Order', backref='farmer', lazy=True, foreign_keys='Order.farmer_id')
    agrovet_orders = db.relationship('Order', backref='agrovet', lazy=True, foreign_keys='Order.agrovet_id')
    posts = db.relationship('CommunityPost', backref='author', lazy=True)
    sent_messages = db.relationship('Message', backref='sender', lazy=True, foreign_keys='Message.sender_id')
    received_messages = db.relationship('Message', backref='receiver', lazy=True, foreign_keys='Message.receiver_id')
    notifications = db.relationship('Notification', backref='user', lazy=True)
    reviews_received = db.relationship('UserReview', backref='user', lazy=True, foreign_keys='UserReview.user_id')
    reviews_given = db.relationship('UserReview', backref='reviewer', lazy=True, foreign_keys='UserReview.reviewer_id')
    disease_reports = db.relationship('DiseaseReport', backref='farmer', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)

class InventoryItem(db.Model):
    __tablename__ = 'inventory_items'
    
    id = db.Column(db.Integer, primary_key=True)
    agrovet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))  # seeds, fertilizers, pesticides, tools, etc.
    description = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(20))  # kg, liter, packet, etc.
    price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float)
    reorder_level = db.Column(db.Integer, default=10)
    supplier = db.Column(db.String(100))
    sku = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cart_items = db.relationship('CartItem', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    agrovet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    customer_type = db.Column(db.String(50))  # regular, wholesale, retail
    total_purchases = db.Column(db.Float, default=0)
    last_purchase = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    communications = db.relationship('Communication', backref='customer', lazy=True)
    sales = db.relationship('Sale', backref='customer', lazy=True)

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    agrovet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))  # cash, mpesa, card
    receipt_number = db.Column(db.String(50), unique=True)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    sale_items = db.relationship('SaleItem', backref='sale', lazy=True)

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

class Communication(db.Model):
    __tablename__ = 'communications'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    communication_type = db.Column(db.String(50))  # call, email, visit, message
    subject = db.Column(db.String(200))
    message = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    follow_up_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='pending')  # pending, completed, cancelled

class DiseaseReport(db.Model):
    __tablename__ = 'disease_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plant_image = db.Column(db.String(200))
    plant_description = db.Column(db.Text)
    treatment_recommendation = db.Column(db.Text)
    is_plant = db.Column(db.Boolean, default=True)
    location = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(50), default='pending')  # pending, reviewed, treated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DiseaseReport {self.id} by Farmer {self.farmer_id}>'

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default='info')  # info, warning, success, error
    link = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Notification {self.id} for User {self.user_id}>'

class WeatherData(db.Model):
    __tablename__ = 'weather_data'
    
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100), nullable=False)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    precipitation = db.Column(db.Float)
    wind_speed = db.Column(db.Float)
    weather_description = db.Column(db.String(200))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<WeatherData {self.id} for {self.location}>'

class CommunityPost(db.Model):
    __tablename__ = 'community_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    post_type = db.Column(db.String(50))  # question, discussion, tip, announcement
    category = db.Column(db.String(50))  # crops, livestock, marketing, etc.
    image = db.Column(db.String(200))
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    comments = db.relationship('PostComment', backref='post', lazy=True, cascade='all, delete-orphan')
    follows = db.relationship('PostFollow', backref='post', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CommunityPost {self.id} by User {self.author_id}>'

class PostComment(db.Model):
    __tablename__ = 'post_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_answer = db.Column(db.Boolean, default=False)
    likes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='comments')
    
    def __repr__(self):
        return f'<PostComment {self.id} on Post {self.post_id}>'

class PostFollow(db.Model):
    __tablename__ = 'post_follows'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', name='unique_post_follow'),)
    
    def __repr__(self):
        return f'<PostFollow User {self.user_id} following Post {self.post_id}>'

class UserReview(db.Model):
    __tablename__ = 'user_reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    review_text = db.Column(db.Text)
    user_type = db.Column(db.String(50))  # farmer, agrovet, etc.
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'reviewer_id', name='unique_user_review'),)
    
    def __repr__(self):
        return f'<UserReview {self.id} for User {self.user_id}>'

class AppRecommendation(db.Model):
    __tablename__ = 'app_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    upvotes = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='pending')  # pending, reviewed, implemented
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='recommendations')
    
    def __repr__(self):
        return f'<AppRecommendation {self.id} by User {self.author_id}>'

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='cart_items')
    
    def __repr__(self):
        return f'<CartItem {self.id} for User {self.user_id}>'

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    agrovet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    delivery_address = db.Column(db.Text)
    farmer_phone = db.Column(db.String(20))
    payment_method = db.Column(db.String(50), default='cash')
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default='pending')  # pending, confirmed, processing, shipped, delivered, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Order {self.order_number}>'

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'))
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    
    def __repr__(self):
        return f'<OrderItem {self.id} for Order {self.order_id}>'

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='reset_tokens')
    
    def __repr__(self):
        return f'<PasswordResetToken {self.token} for User {self.user_id}>'

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message_type = db.Column(db.String(50), default='text')  # text, image, product_inquiry
    content = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    product_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id'))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('InventoryItem', backref='inquiry_messages')
    
    def __repr__(self):
        return f'<Message {self.id} from {self.sender_id} to {self.receiver_id}>'

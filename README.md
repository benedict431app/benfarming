# Adiseware - Agricultural Management System

Welcome to **Adiseware**, a comprehensive agricultural management platform designed to empower farmers, agrovets, extension officers, and learning institutions through technology.

## 🌾 What Can You Do with Adiseware?

### For Farmers
- **🔬 Plant Disease Detection**: Upload photos of your plants and get instant AI-powered disease diagnosis with treatment recommendations
- **🌤️ Weather & Farming Tips**: Get location-based weather forecasts and farming recommendations
- **🏪 Find Suppliers**: Locate nearby agrovets with contact information and directions
- **💬 AI Assistant**: Chat with an agricultural AI assistant for instant farming advice

### For Agrovets
- **📦 Inventory Management**: Track all your products with low-stock alerts
- **💰 Point of Sale (POS)**: Complete sales system with cart, checkout, and receipt generation
- **👥 Customer Relationship Management (CRM)**: 
  - Maintain customer profiles with purchase history
  - Track all communications (calls, emails, meetings)
  - Set follow-up reminders
  - Analyze customer purchasing patterns

### For Extension Officers
- **📊 Disease Monitoring**: Track disease outbreaks across your region
- **👨‍🌾 Farmer Support**: View all farmer disease reports and provide advisory services
- **📈 Analytics**: Monitor agricultural trends and patterns

### For Learning Institutions
- **📚 Educational Resources**: Access agricultural research and training materials
- **🔬 Research Data**: Analyze agricultural data for academic purposes
- **👨‍🎓 Student Programs**: Manage research projects and field programs

## 🚀 Getting Started

The application is now running! Here's how to use it:

1. **Register an Account**
   - Click "Register" in the top menu
   - Choose your account type (Farmer, Agrovet, Extension Officer, or Learning Institution)
   - Upload a profile picture
   - Fill in your information

2. **Login**
   - Use your email and password to access your dashboard
   - Each user type has a customized dashboard with relevant features

3. **Explore Features**
   - Navigate using the menu bar at the top
   - Click the chat icon (bottom right) to access the AI assistant
   - Check the notification bell for important alerts

## ✨ Key Features

### 🎯 Core Capabilities
- **Multi-Role System**: 4 different user types with specialized dashboards
- **AI-Powered Analysis**: OpenAI GPT-4 Vision for plant disease detection
- **Real-Time Weather**: OpenWeather API integration for accurate forecasts
- **Smart Inventory**: Automatic low-stock alerts for agrovets
- **Complete CRM**: Track customer relationships and communications
- **Point of Sale**: Professional POS system with sales history
- **Accessibility**: WCAG 2.1 AA compliant for deaf and blind users

### 🔒 Security Features
- Secure password hashing
- Role-based access control
- Environment-based API key management
- Session management with Flask-Login

### 🎨 User Experience
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Keyboard Navigation**: Full keyboard accessibility
- **Screen Reader Support**: ARIA labels and semantic HTML
- **High Contrast**: Optimized for visibility
- **Modular Components**: Separate header, footer, and reusable templates

## 🛠️ Technical Stack

- **Backend**: Flask (Python 3.11)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Frontend**: Bootstrap 5, JavaScript, Jinja2
- **AI Services**: 
  - OpenAI GPT-4 Vision (plant disease detection)
  - Google Gemini AI (additional features)
  - Cohere (chat assistant)
- **External APIs**: 
  - OpenWeather (weather data)
  - Perenual (plant information)
  - Plant.id (alternative plant identification)
  - Weglot (multi-language translation)

## 📁 Project Structure

```
/
├── app.py                      # Main Flask application
├── models.py                   # Database models
├── config.py                   # Configuration
├── requirements.txt            # Dependencies
├── static/
│   ├── css/style.css          # Custom styles
│   ├── js/main.js             # JavaScript
│   └── uploads/               # User uploads
└── templates/
    ├── components/            # Reusable components
    ├── auth/                  # Login/Register
    ├── farmer/                # Farmer features
    ├── agrovet/               # Agrovet features
    ├── officer/               # Extension officer
    └── institution/           # Learning institution
```

## 🔑 API Keys Configuration

All API keys are securely stored as environment variables in Replit Secrets. The system uses:

1. **OPENAI_API_KEY** - Plant disease detection
2. **GEMINI_API_KEY** - Google AI features
3. **PERENUAL_API_KEY** - Plant information
4. **OPENWEATHER_API_KEY** - Weather forecasts
5. **PLANTID_API_KEY** - Alternative plant ID
6. **WEGLOT_API_KEY** - Translation services
7. **COHERE_API_KEY** - AI chat assistant

## 🎓 How to Use Specific Features

### Plant Disease Detection (Farmers)
1. Navigate to "Disease Detection" from your dashboard
2. Upload a clear photo of the affected plant
3. Optionally add a description of symptoms
4. Click "Analyze Plant"
5. View AI-generated diagnosis and treatment recommendations

### Inventory Management (Agrovets)
1. Go to "Inventory" from your dashboard
2. Click "Add Product" to add new items
3. Monitor the "Low Stock" badges
4. Edit or delete products as needed

### Point of Sale (Agrovets)
1. Navigate to "POS"
2. Click on products to add to cart
3. Adjust quantities using +/- buttons
4. Select customer (optional) and payment method
5. Click "Checkout" to complete sale

### CRM System (Agrovets)
1. Go to "CRM" to view all customers
2. Click "Add Customer" to register new customers
3. Click "View" on any customer to see:
   - Purchase history
   - Communication logs
   - Customer details
4. Add communication logs for calls, emails, meetings
5. Set follow-up dates for reminders

## 🌐 Accessibility Features

Adiseware follows W3C WCAG 2.1 AA guidelines:
- ✅ Screen reader compatible
- ✅ Keyboard navigation support
- ✅ ARIA labels on all interactive elements
- ✅ Semantic HTML structure
- ✅ High contrast mode support
- ✅ Skip-to-content links
- ✅ Focus indicators
- ✅ Form validation with clear messages

## 📱 Next Steps & Future Enhancements

### Upcoming Features
- Multi-language interface (Weglot integration pending)
- SMS/Email notifications for alerts
- Advanced analytics dashboards with charts
- Geolocation-based farmer mapping
- Mobile Progressive Web App (PWA)
- PDF report generation
- Marketplace for farmers to buy directly from agrovets

### Deployment
The application is ready for deployment. Consider using:
- **Gunicorn** as the production WSGI server
- **PostgreSQL** for the production database (already configured)
- Environment variables for all sensitive data (already implemented)

## 🆘 Support

### Common Tasks

**How to add a new user?**
- Click "Register" and fill in the form with your role type

**How to scan a plant for diseases?**
- Login as a Farmer → Disease Detection → Upload image

**How to manage inventory?**
- Login as Agrovet → Inventory → Add/Edit products

**How to use the POS system?**
- Login as Agrovet → POS → Click products → Checkout

**How to track customers?**
- Login as Agrovet → CRM → Add/View customers

## 📊 Database

The system uses PostgreSQL with the following main tables:
- **users** - All user accounts with roles
- **inventory_items** - Agrovet products
- **sales** - Transaction records
- **customers** - CRM customer data
- **communications** - Customer interaction logs
- **disease_reports** - Plant disease scans
- **notifications** - System alerts

## 🔐 Security Notes

- All passwords are hashed using Werkzeug security
- API keys are stored in environment variables
- Role-based access control prevents unauthorized access
- File uploads are validated and sanitized
- CSRF protection enabled
- Session management with secure cookies

## 📄 License

This project was created for agricultural empowerment. All rights reserved © 2025 Adiseware.

---

**Built with ❤️ for farmers and agricultural communities**

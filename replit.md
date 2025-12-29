# Adiseware - Agricultural Management System

## Overview
Adiseware is a comprehensive agricultural management platform designed to empower farmers, agrovets, extension officers, and learning institutions through technology. The system provides role-based dashboards with specialized features for each user group.

## Project Architecture

### Technology Stack
- **Backend**: Flask (Python 3.11)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Frontend**: Bootstrap 5, JavaScript, Jinja2 templates
- **AI Services**: OpenAI GPT-4 Vision, Google Gemini, Cohere Chat
- **External APIs**: OpenWeather, Perenual Plant API, Plant.id, Weglot Translation

### Key Features by User Group

#### Farmers
- **Plant Disease Detection**: Upload plant images for AI-powered disease diagnosis using OpenAI Vision API
- **Weather Recommendations**: Location-based weather forecasts and farming recommendations via OpenWeather API
- **Crop Information**: Access plant care guides and growing tips through Perenual API
- **Agrovet Marketplace**: Find nearby agricultural suppliers with contact information and location

#### Agrovets
- **Inventory Management**: Complete CRUD operations for product management with low-stock alerts
- **Point of Sale (POS)**: Interactive cart system with checkout, receipt generation, and sales history
- **Customer Relationship Management (CRM)**: 
  - Customer profiles with purchase history
  - Communication logs (calls, emails, meetings, notes)
  - Follow-up reminders for customer engagement
  - Sales analytics and customer insights

#### Extension Officers
- **Disease Outbreak Tracking**: Monitor farmer-reported disease cases across regions
- **Farmer Reports**: View and analyze disease detection reports from farmers
- **Advisory Management**: Provide agricultural guidance and support

#### Learning Institutions
- **Educational Resources**: Access agricultural research and training materials
- **Research Data**: Analyze agricultural trends and patterns
- **Student Programs**: Manage research projects and field programs

### Accessibility Features (W3C WCAG 2.1 AA Compliant)
- Semantic HTML with proper heading structure
- ARIA labels and landmarks for screen readers
- Keyboard navigation support
- Skip-to-content link for keyboard users
- Focus indicators with high contrast
- Alt text for all images
- Form validation with clear error messages
- Responsive design for all screen sizes

### AI Integration
- **Cohere Chat Assistant**: Agricultural support chatbot accessible from all dashboards
- **OpenAI GPT-4 Vision**: Plant disease detection and diagnosis
- **Google Gemini**: Additional AI capabilities for future features

## Project Structure

```
/
├── app.py                      # Main Flask application
├── config.py                   # Configuration and API keys
├── models.py                   # Database models
├── requirements.txt            # Python dependencies
├── static/
│   ├── css/
│   │   └── style.css          # Custom styles with accessibility features
│   ├── js/
│   │   └── main.js            # Client-side JavaScript
│   └── uploads/               # User-uploaded files (profile pics, plant images)
└── templates/
    ├── components/
    │   ├── base.html          # Base template with accessibility
    │   ├── header.html        # Navigation header
    │   └── footer.html        # Footer component
    ├── auth/
    │   ├── login.html         # Login page
    │   └── register.html      # Registration with profile upload
    ├── farmer/
    │   ├── dashboard.html     # Farmer main dashboard
    │   ├── detect_disease.html # Plant disease scanner
    │   ├── weather.html       # Weather and recommendations
    │   └── agrovets.html      # Agrovet marketplace
    ├── agrovet/
    │   ├── dashboard.html     # Agrovet main dashboard
    │   ├── inventory.html     # Inventory listing
    │   ├── add_inventory.html # Add product form
    │   ├── edit_inventory.html # Edit product form
    │   ├── pos.html           # Point of sale system
    │   ├── crm.html           # Customer listing
    │   ├── add_customer.html  # Add customer form
    │   └── view_customer.html # Customer details with CRM
    ├── officer/
    │   └── dashboard.html     # Extension officer dashboard
    └── institution/
        └── dashboard.html     # Learning institution dashboard
```

## Database Models

### Users
- Multi-role support: farmer, agrovet, extension_officer, learning_institution
- Profile information with location coordinates
- Email/password authentication with profile pictures

### Inventory (Agrovet)
- Product management with categories
- Stock tracking with reorder levels
- Cost and selling price management
- Low-stock alerts

### Sales & POS
- Complete transaction records
- Customer association
- Receipt generation
- Sales history and analytics

### CRM
- Customer profiles with contact information
- Purchase history tracking
- Communication logs with follow-ups
- Customer type categorization

### Disease Reports
- Plant image storage
- AI analysis results
- Treatment recommendations
- Location tracking for outbreak monitoring

### Notifications
- Real-time alerts for low stock, weather warnings
- Disease outbreak notifications
- Badge counter in header

## API Integration

All API keys are configured in `config.py`:
- OpenAI API: Plant disease detection
- Google Gemini: AI features
- Perenual: Plant information
- OpenWeather: Weather data
- Plant.id: Alternative plant identification
- Weglot: Multi-language translation
- Cohere: Chat assistant

## Running the Application

The application runs on port 5000 with the following workflow:
```bash
python app.py
```

Access the application at: http://localhost:5000

## Security Features
- Password hashing with Werkzeug
- Flask-Login session management
- Role-based access control
- CSRF protection
- File upload validation
- Environment variable for sensitive data

## Future Enhancements
- Multi-language UI with Weglot integration
- SMS/Email notifications via Twilio
- Advanced analytics dashboards
- Geolocation-based farmer mapping
- Mobile PWA for offline access
- PDF report generation
- Admin panel for system management

## Development Notes
- Database tables are auto-created on first run
- Debug mode enabled for development
- File uploads stored in `static/uploads/`
- Session secret should be changed for production
- Use production WSGI server (Gunicorn) for deployment

## Recent Changes (Nov 11, 2025)
- Initial project setup with modular Flask architecture
- Implemented all core features for MVP release
- Created accessible templates following W3C guidelines
- Integrated AI services (OpenAI, Gemini, Cohere)
- Built complete CRM system for agrovets
- Added POS system with cart functionality
- Implemented plant disease detection
- Created weather-based recommendations
- Set up role-based authentication

## User Preferences
- None yet (first session)

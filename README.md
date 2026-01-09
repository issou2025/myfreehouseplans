# MyFreeHousePlans - House Plan Catalog + Gumroad Sales

A production-ready Flask application for selling architectural house plans online.

## Features

- **Modern Flask Architecture**: Application factory pattern with Blueprint organization
- **Database Ready**: SQLite for development, PostgreSQL for production
- **Authentication System**: User registration, login, and admin access
- **SEO Optimized**: Clean URLs, meta tags, and sitemap support
- **Admin Dashboard**: Manage house plans, orders, and content
- **Render Deployment**: Pre-configured for seamless Render.com deployment

## Project Structure

```
myfreehouseplan/
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Configuration classes
│   ├── extensions.py        # Flask extensions
│   ├── models.py            # Database models
│   ├── forms.py             # WTForms forms
│   ├── seo.py               # SEO utilities
│   ├── routes/
│   │   ├── main.py          # Public routes
│   │   ├── admin.py         # Admin routes
│   │   └── auth.py          # Authentication routes
│   ├── templates/           # Jinja2 templates
│   └── static/              # CSS, JS, images
├── migrations/              # Database migrations
├── requirements.txt         # Python dependencies
├── render.yaml              # Render deployment config
├── wsgi.py                  # WSGI entry point
└── README.md
```

## Setup Instructions

### 1. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Environment Variables

Create a `.env` file in the root directory:

```
FLASK_APP=wsgi.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///myfreehouseplan.db
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@example.com
MAIL_PASSWORD=your-email-password
```

### 4. Initialize Database

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 5. Run Development Server

```bash
flask run
```

The application will be available at `http://127.0.0.1:5000`

## Deployment to Render

### Prerequisites
- GitHub account
- Render account
- PostgreSQL database on Render

### Steps

1. **Push code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin your-repo-url
   git push -u origin main
   ```

2. **Connect to Render**
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - Click "New" → "Blueprint"
   - Connect your GitHub repository
   - Render will automatically detect `render.yaml` and provision services

3. **Configure Environment Variables**
   - Set `SECRET_KEY` in Render dashboard
   - Database URL is automatically configured
   - Add any additional environment variables (MAIL_*, etc.)

4. **Deploy**
   - Render will automatically build and deploy
   - Your app will be live at `https://your-app-name.onrender.com`

## Production Checklist

Before going live, ensure:

- [ ] Set strong `SECRET_KEY` in production
- [ ] Configure real email server (SMTP settings)
- [ ] Set up PostgreSQL database
- [ ] Enable SSL/HTTPS (automatic on Render)
- [ ] Set `FLASK_ENV=production`
- [ ] Configure domain name (optional)
- [ ] Set up backup strategy for database
- [ ] Enable error logging and monitoring
- [ ] Test payment integration (if applicable)
- [ ] Review security headers

## Key Components

### Models
- **User**: Customer and admin authentication
- **HousePlan**: Architectural plan listings
- **Order**: Purchase tracking
- **Category**: Plan categorization

### Blueprints
- **main**: Public-facing pages (home, plans, contact)
- **auth**: User authentication (login, register, logout)
- **admin**: Administrative dashboard

### SEO Features
- Automatic meta tag generation
- SEO-friendly URLs with slugs
- Sitemap generation support
- Open Graph tags for social sharing

## Technology Stack

- **Backend**: Flask 3.0
- **Database**: SQLAlchemy with SQLite/PostgreSQL
- **Templates**: Jinja2
- **Forms**: Flask-WTF + WTForms
- **Auth**: Flask-Login
- **Migrations**: Flask-Migrate
- **Email**: Flask-Mail
- **WSGI Server**: Gunicorn

## License

Proprietary - All rights reserved

## Support

For questions or issues, contact: entreprise2rc@gmail.com

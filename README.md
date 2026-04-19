# Prodexa - Product Data Aggregator & Curator

Prodexa is a Flask-based web application that scrapes, curates, and manages product data from multiple e-commerce sources. It provides user authentication, personalized product management, and a intuitive dashboard for browsing and saving products.

## Features

- **Web Scraping**: Automated scraping from multiple e-commerce websites
- **Data Curation**: Intelligent data cleaning and standardization
- **User Authentication**: Secure user registration and login with password validation
- **Product Management**: Save, view, and manage products per user
- **Search & Filter**: Find products based on various criteria
- **Responsive UI**: Dynamic dashboard with product details views
- **PostgreSQL Database**: Reliable data persistence with Supabase

## Project Structure

```
prodexa/
├── app.py                          # Main Flask application
├── database.py                     # Database connection and operations
├── scraper.py                      # Web scraping logic
├── scraper_clean.py               # Data cleaning for scraped content
├── curator.py                      # Data curation and processing
├── requirements.txt               # Python dependencies
├── data/
│   └── products.csv               # Sample product data
├── sql/                           # SQL query files
│   ├── insert_product.sql
│   ├── get_all_products.sql
│   ├── get_products_by_user.sql
│   ├── insert_user.sql
│   ├── get_user_by_username.sql
│   ├── delete_product.sql
│   └── delete_product_by_user.sql
├── static/
│   ├── css/                       # Stylesheets
│   │   ├── style.css
│   │   ├── dashboard.css
│   │   ├── results.css
│   │   ├── productdetails.css
│   │   └── saved.css
│   ├── js/                        # JavaScript files
│   │   └── main.js
│   └── images/                    # Image assets
└── templates/                     # HTML templates
    ├── base.html                  # Base template
    ├── index.html                 # Home page
    ├── login.html                 # Login page
    ├── register.html              # Registration page
    ├── dashboard.html             # Main dashboard
    ├── results.html               # Search results
    ├── results_dynamic.html       # Dynamic results view
    ├── saved.html                 # Saved products
    ├── saved_dynamic.html         # Dynamic saved view
    ├── productdetails.html        # Product details
    └── productdetails_dynamic.html # Dynamic product details
```

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- PostgreSQL database (Supabase recommended)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd prodexa
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your configuration:
   ```
   FLASK_SECRET_KEY=your-secret-key-here
   DB_HOST=your-database-host
   DB_NAME=your-database-name
   DB_USER=your-database-user
   DB_PASSWORD=your-database-password
   ```

5. **Initialize the database**
   ```bash
   python database.py
   ```

## Usage

### Running the Application

```bash
# Activate virtual environment (if not already activated)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Start the Flask development server
flask run
```

The application will be accessible at `http://localhost:5000`

### Core Workflows

#### 1. User Registration
- Navigate to `/register`
- Username requirements: 3+ characters, alphanumeric + underscores
- Password requirements: 8+ characters, uppercase, lowercase, number, special character

#### 2. Product Scraping
```python
from scraper import scrape_all_sites
products = scrape_all_sites()
```

#### 3. Data Curation
```python
from curator import curate_data
cleaned_data = curate_data(products)
```

#### 4. Managing Products
- View all products in dashboard
- Search and filter results
- Save products to personal collection
- Delete saved products

## Database Schema

### Users Table
- `id`: Primary key
- `username`: Unique username
- `password_hash`: Hashed password
- `created_at`: Registration timestamp

### Products Table
- `id`: Primary key
- `name`: Product name
- `description`: Product description
- `price`: Product price
- `url`: Product link
- `source`: Website source
- `user_id`: User ID (for saved products)
- `created_at`: Creation timestamp

## API Endpoints

### Authentication
- `POST /register` - User registration
- `POST /login` - User login
- `GET /logout` - User logout

### Products
- `GET /` - Home page
- `GET /dashboard` - User dashboard (requires login)
- `GET /results` - Search results
- `GET /saved` - Saved products (requires login)
- `GET /product/<id>` - Product details
- `POST /save-product` - Save a product (AJAX)
- `POST /delete-product` - Delete a product (AJAX)

## Technologies Used

- **Backend**: Flask (Python web framework)
- **Database**: PostgreSQL (via Supabase)
- **Frontend**: HTML5, CSS3, JavaScript
- **Security**: Werkzeug password hashing
- **Data Processing**: Pandas, BeautifulSoup (for scraping)

## Configuration

Key configuration options in `app.py`:
- `FLASK_SECRET_KEY`: Session encryption key
- Database connection settings in `database.py`
- Scraper configurations in `scraper.py`

## Security Considerations

- Passwords are hashed using Werkzeug security utilities
- User authentication required for sensitive operations
- SQL queries are parameterized to prevent SQL injection
- CSRF protection enabled through Flask sessions
- Environment variables used for sensitive credentials

## Troubleshooting

### Database Connection Issues
- Verify database credentials in `.env`
- Check network connectivity to Supabase
- Ensure database is running and accessible

### Scraping Issues
- Check website URLs are accessible
- Verify HTML selectors are current
- Review scraper logs for errors

### Module Import Errors
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again
- Check Python version compatibility (3.8+)

### Deployment Notes
- This app uses Selenium and Chromium, so container hosting is the safest option.
- Render, Fly.io, or Railway Docker deployments are better fits than Vercel/serverless.
- If Railway fails to auto-detect the app, deploy it as a Docker service and make sure the host exposes the `PORT` environment variable.
- Keep `MAIL_SUPPRESS_SEND=true` in production until SMTP is configured.
- Set `DATABASE_URL` in production instead of relying on local `.env` values.

## Development

### Adding a New Data Source
1. Create scraper function in `scraper.py`
2. Add data cleaning logic in `scraper_clean.py`
3. Implement curation rules in `curator.py`
4. Test data flow end-to-end

### Customizing UI
- Modify CSS files in `static/css/`
- Update HTML templates in `templates/`
- JavaScript utilities in `static/js/main.js`

## Performance Tips

- Cache frequently accessed product lists
- Optimize database queries with proper indexing
- Implement pagination for large result sets
- Use asynchronous scraping for multiple sources

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Support

For issues, bugs, or feature requests, please create an issue in the repository.

## Future Enhancements

- [ ] Advanced filtering and sorting options
- [ ] Price tracking and alerts
- [ ] Export products to CSV/PDF
- [ ] Email notifications for saved items
- [ ] Mobile app version
- [ ] Admin dashboard for analytics
- [ ] API endpoints for external integrations
- [ ] Product recommendations using ML

---

**Last Updated**: April 2026

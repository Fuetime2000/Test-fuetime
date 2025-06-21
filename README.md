# Fuetime

A platform connecting clients with skilled professionals.

## Features

- User authentication and authorization
- Professional profiles with skills and reviews
- Real-time messaging
- Secure payment processing
- Multi-language support
- Admin dashboard
- File uploads
- Email notifications

## Prerequisites

- Python 3.11+
- PostgreSQL/MySQL (for production)
- Redis (for production caching and rate limiting)
- Node.js and npm (for frontend assets)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/fuetime.git
   cd fuetime
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Then edit the `.env` file with your configuration.

5. Initialize the database:
   ```bash
   flask db upgrade
   ```

6. Run the development server:
   ```bash
   flask run
   ```

## Configuration

Copy `.env.example` to `.env` and update the following variables:

- `FLASK_ENV`: Application environment (development, production)
- `SECRET_KEY`: Secret key for session management
- `DATABASE_URL`: Database connection URL
- `MAIL_*`: Email configuration
- `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`: Razorpay API credentials
- `REDIS_URL`: Redis connection URL (for production)

## Development

- Run tests: `pytest`
- Format code: `black .`
- Lint code: `flake8`

## Production Deployment

### Heroku

1. Create a new Heroku app
2. Set up the PostgreSQL add-on
3. Set up the Redis add-on
4. Set environment variables:
   ```bash
   heroku config:set FLASK_ENV=production
   heroku config:set SECRET_KEY=your-secret-key
   # Set other environment variables as needed
   ```
5. Deploy your code

### Docker

Build and run with Docker Compose:

```bash
docker-compose up --build
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please contact support@fuetime.example.com.

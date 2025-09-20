# SNFLegTracker

A comprehensive legislative tracking platform for monitoring bills and regulations at federal and state levels.

## Features

- **Bill Tracking**: Monitor legislation from Congress and state governments
- **AI-Powered Analysis**: Sentiment analysis and categorization using OpenAI and transformers
- **Real-time Updates**: Automated scraping and notifications
- **RESTful API**: FastAPI-based backend with comprehensive endpoints
- **Scalable Architecture**: Docker containerization with Redis and PostgreSQL

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL
- **Task Queue**: Celery with Redis
- **AI/ML**: OpenAI API, sentence-transformers
- **Data Processing**: pandas, BeautifulSoup4
- **Containerization**: Docker, docker-compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)

### Using Docker (Recommended)

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd SNFLegTracker
   ```

2. Create environment file:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. Start the services:
   ```bash
   docker-compose up -d
   ```

4. The API will be available at `http://localhost:8000`
   - API Documentation: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/api/v1/health`

### Local Development

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Start PostgreSQL and Redis (or use Docker):
   ```bash
   docker run -d --name snf-postgres -p 5432:5432 -e POSTGRES_DB=snflegtracker -e POSTGRES_USER=snflegtracker -e POSTGRES_PASSWORD=password postgres:15
   docker run -d --name snf-redis -p 6379:6379 redis:7-alpine
   ```

5. Run database migrations:
   ```bash
   alembic upgrade head
   ```

6. Start the application:
   ```bash
   uvicorn main:app --reload
   ```

7. Start Celery worker (in another terminal):
   ```bash
   celery -A services.tasks worker --loglevel=info
   ```

## API Endpoints

### Health
- `GET /api/v1/health` - Health check endpoint

### Bills
- `GET /api/v1/bills/` - List all bills
- `POST /api/v1/bills/` - Create a new bill
- `GET /api/v1/bills/{bill_id}` - Get specific bill details

## Project Structure

```
SNFLegTracker/
├── api/                    # API routes and dependencies
│   ├── routes/
│   └── dependencies/
├── models/                 # SQLAlchemy models and database config
│   ├── database.py
│   └── legislation.py
├── services/               # Business logic and services
│   ├── auth/
│   ├── legislation/
│   └── tasks.py           # Celery tasks
├── scrapers/              # Web scrapers for different sources
│   ├── federal/
│   └── state/
├── tests/                 # Test files
├── static/                # Static files
├── templates/             # Jinja2 templates (if needed)
├── docker-compose.yml     # Docker services configuration
├── Dockerfile             # Application container
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `OPENAI_API_KEY`: OpenAI API key for AI features
- `SECRET_KEY`: Application secret key

### Database

The application uses PostgreSQL with SQLAlchemy ORM. Database migrations are handled by Alembic.

### Background Tasks

Celery is used for background tasks like:
- Web scraping legislative data
- AI-powered bill analysis
- Periodic data updates

## Development

### Adding New Scrapers

1. Create a new scraper in `scrapers/federal/` or `scrapers/state/`
2. Implement the scraper class following the pattern in `congress_scraper.py`
3. Add the scraper to the Celery task in `services/tasks.py`

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

### Testing

```bash
pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[License information]
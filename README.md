# AI-SHAI Web Interface

Web interface for the AI-SHAI project.

## Features

- Authentification des membres
- Forum de discussion
- Gestion des cotisations avec paiement en ligne
- Espace documentaire sécurisé
- Planification des événements et réunions
- Administration et gestion des rôles
- Conformité RGPD

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Testing**: pytest, hypothesis

## Setup

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14 or higher
- pip and virtualenv

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-shai-web-interface
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Setup PostgreSQL database:
```bash
# Create database and user
createdb OPCP_db
createuser OPCP_user
# Grant privileges (run in psql)
GRANT ALL PRIVILEGES ON DATABASE OPCP_db TO OPCP_user;
```

6. Run database migrations:
```bash
alembic upgrade head
```

7. Start the development server:
```bash
uvicorn app.main:app --reload
```

The API will be available at http://ai-shai-web-interface:8000

API documentation: http://ai-shai-web-interface:8000/docs

## Project Structure

```
ai-shai-web-interface/
├── app/                    # Application code
│   ├── __init__.py
│   ├── main.py            # FastAPI application
│   ├── config.py          # Configuration
│   ├── database.py        # Database setup
│   └── logging_config.py  # Logging configuration
├── tests/                 # Test files
│   ├── __init__.py
│   ├── conftest.py        # Pytest fixtures
│   └── test_health.py     # Health check tests
├── migrations/            # Alembic migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/          # Migration files
├── static/                # Static files
├── templates/             # Email templates
├── storage/               # File storage
│   └── uploads/           # Uploaded documents
├── requirements.txt       # Python dependencies
├── alembic.ini           # Alembic configuration
├── .env.example          # Example environment variables
└── README.md             # This file
```

## Testing

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

Run property-based tests:
```bash
pytest -m property
```

## Development

### Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migration:
```bash
alembic downgrade -1
```

### Code Style

This project follows PEP 8 style guidelines.

## Database Field Encryption (optional)

Application-level, opt-in encryption of a small set of sensitive non-indexed
free-text columns (`forum_topics.title`, `forum_posts.content`,
`users.first_name`, `users.last_name`, `notifications.content`,
`events.description`, `tasks.description`). Disabled by default — data is stored
in plaintext until an administrator opts in.

How it works:
- An administrator enables the toggle and sets a password key on the admin
  **Configuration** page. The key is never stored; only a salted PBKDF2
  verification hash is persisted, so the app can validate the key but cannot
  recover it. The Fernet encryption key is derived from the password key.
- Changing the state of existing data is applied by the offline script
  `scripts/migrate_encryption.py` (`--enable` / `--disable`), which
  encrypts/decrypts all in-scope rows and only then flips
  `encryption_config.enabled`.
- Set `DB_ENCRYPTION_KEY` (see `.env.example`) to let the app decrypt after a
  restart without re-entering the key.

> ⚠️ If encryption is enabled and the password key (and the derived
> `DB_ENCRYPTION_KEY`) are lost, the encrypted data is **permanently
> unrecoverable** by design.

See `scripts/README.md` for the full workflow.

## License

Copyright © 2026 AI-SHAI PSMC

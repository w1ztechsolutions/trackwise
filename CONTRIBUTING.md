# Contributing to TrackWise

Thank you for your interest in contributing to TrackWise! This document provides guidelines for contributing to the project.

---

## 1. Getting Started

### 1.1 Prerequisites

- Python 3.12+
- PostgreSQL (or SQLite for development)
- pip
- Git

### 1.2 Fork and Clone

```bash
git clone https://github.com/your-username/trackwise.git
cd trackwise
```

### 1.3 Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 1.4 Configure Environment

```bash
cp .env.example .env
# Edit .env with your local database credentials
```

### 1.5 Run Migrations and Seed Data

```bash
flask db upgrade
flask shell
>>> from app.services.subscription_service import seed_default_plans
>>> seed_default_plans()
>>> exit()
```

---

## 2. Code Style

### 2.1 Python Style Guide

TrackWise follows **PEP 8** with these specifics:

- **Line length**: 100 characters maximum
- **Indentation**: 4 spaces (no tabs)
- **Imports**: Grouped and sorted with `isort`
- **Type hints**: Preferred but not required for all functions
- **Docstrings**: Required for all public methods and classes

### 2.2 Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | `snake_case` | `accounting_service.py` |
| Classes | `PascalCase` | `AccountingService` |
| Functions | `snake_case` | `create_journal_entry()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Private methods | `_leading_underscore` | `_post_payment_accounting()` |

### 2.3 Flask Patterns

- Use **Blueprints** for route organization (never add routes to `app.py`)
- Use the **service layer** for business logic (never put business logic in routes)
- All database queries must be **business-scoped** (filter by `g.business_id`)
- Use **Flask-WTF** for form validation
- Use **Flask-Login** for authentication

### 2.4 Accounting Rules

When working with the accounting engine:

- **Never** bypass the accounting engine
- **Never** store report values directly
- **Never** directly edit ledger balances
- Every transaction must balance: **Debit = Credit**
- Every table must include `business_id`

---

## 3. Project Structure

```
trackwise/
├── app/
│   ├── __init__.py              # Application factory
│   ├── models/                  # Database models
│   │   └── *.py
│   ├── services/                # Business logic layer
│   │   ├── accounting_service.py
│   │   ├── inventory_service.py
│   │   ├── production_service.py
│   │   └── reports/             # Report generators
│   ├── auth/                    # Authentication & RBAC
│   ├── dashboard/               # Dashboard routes
│   ├── inventory/               # Inventory routes
│   ├── purchases/               # Purchase/Bill routes
│   ├── sales/                   # Sales/Invoice routes
│   ├── expenses/                # Expense routes (deprecated, redirects to payments)
│   ├── reports/                 # Report routes
│   ├── settings/                # Settings routes
│   ├── production/              # Production routes
│   ├── api/                     # JSON API
│   ├── tasks/                   # Celery tasks
│   ├── celery_app.py            # Celery configuration
│   └── logging_config.py        # Structured logging
├── migrations/                  # Alembic migrations
├── static/                      # CSS, JS, images
├── templates/                   # Jinja2 templates
├── tests/                       # Test suite
├── config.py                    # Configuration classes
├── app.py                       # Legacy entrypoint (use `flask run`)
└── requirements.txt
```

---

## 4. Testing

### 4.1 Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_fifo.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html
```

### 4.2 Test Requirements

- All new features must include tests
- Tests use **SQLite in-memory database** by default
- Use **factory patterns** for test data (see `tests/conftest.py`)
- Test both **success paths** and **error cases**

### 4.3 Test Structure

```
tests/
├── conftest.py                  # Shared fixtures
├── test_fifo.py                 # FIFO inventory tests
├── test_accounting.py           # Accounting engine tests
├── test_reports.py              # Financial report tests
├── test_inventory_service.py    # Inventory service tests
├── test_production.py           # Production service tests
└── test_database.py             # Database configuration tests
```

---

## 5. Pull Request Process

### 5.1 Before Submitting

1. Ensure all tests pass: `pytest`
2. Run linting: `flake8 app/ tests/`
3. Update documentation if needed
4. Add entry to `CHANGELOG.md`

### 5.2 PR Description

Your PR description must include:

- **Summary**: What does this PR do?
- **Type**: Bug fix, feature, refactor, docs, etc.
- **Related Issues**: Link to any related issues
- **Testing**: How was this tested?
- **Screenshots**: For UI changes

### 5.3 Review Criteria

- Code follows style guidelines
- Tests are included and passing
- Documentation is updated
- No secrets or sensitive data committed
- Accounting integrity rules are maintained

---

## 6. Reporting Issues

### 6.1 Bug Reports

When reporting bugs, include:

1. **Steps to reproduce**
2. **Expected behavior**
3. **Actual behavior**
4. **Environment** (OS, Python version, database)
5. **Logs/error messages**

### 6.2 Feature Requests

When requesting features:

1. **Use case**: Who benefits and why?
2. **Proposed solution**: How should it work?
3. **Alternatives considered**: What other approaches were evaluated?

---

## 7. Community

- Be respectful and inclusive
- Welcome newcomers
- Provide constructive feedback
- Follow the code of conduct

---

## 8. License

By contributing, you agree that your contributions will be licensed under the project's proprietary license (W1zTech Solutions).




# JSON API Documentation

TrackWise provides a JSON API for programmatic access to data. All API endpoints require authentication via Flask-Login session cookies.

**Base URL:** `/api`

**Authentication:** Session-based. Include session cookies in requests. All endpoints return `401 Unauthorized` if not logged in.

**Rate Limiting:** 200 requests/day, 50 requests/hour per IP. Storage defaults to in-memory; use Redis in production.

---

## Table of Contents

1. [Products](#products)
2. [Suppliers](#suppliers)
3. [Accounting Verify](#accounting-verify)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [Multi-Tenancy](#multi-tenancy)

---

## Products

### GET /api/products

Retrieve a list of all products for the current business.

**Authentication:** Required

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "sku": "CB-001",
    "name": "Cement Block",
    "description": "Standard cement block",
    "unit_price": "1.50",
    "cost_price": "0.80",
    "stock_quantity": 500,
    "low_stock_threshold": 100,
    "category": "Building Materials"
  }
]
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Product ID |
| `sku` | String | Stock keeping unit |
| `name` | String | Product name |
| `description` | String | Product description |
| `unit_price` | String | Selling price (decimal string) |
| `cost_price` | String | Current cost price via FIFO (decimal string) |
| `stock_quantity` | Integer | Current stock level |
| `low_stock_threshold` | Integer | Alert threshold |
| `category` | String | Product category |

**Query Parameters:** None currently supported. All products for the authenticated user's business are returned.

---

## Suppliers

### GET /api/suppliers

Retrieve a list of all suppliers for the current business.

**Authentication:** Required

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "name": "ABC Suppliers Ltd"
  },
  {
    "id": 2,
    "name": "XYZ Trading Co"
  }
]
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Supplier ID |
| `name` | String | Supplier name |

**Query Parameters:** None currently supported.

---

## Accounting Verify

### GET /api/accounting/verify

Verify the integrity of the accounting system for the current business. Checks that all journal entries are balanced (debits = credits).

**Authentication:** Required

**Response:** `200 OK` (balanced) or `500 Internal Server Error` (unbalanced)

```json
{
  "balanced": true,
  "total_entries": 42,
  "total_lines": 84,
  "total_debits": "15420.00",
  "total_credits": "15420.00",
  "message": "All entries are balanced"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `balanced` | Boolean | `true` if all entries balance |
| `total_entries` | Integer | Number of journal entries |
| `total_lines` | Integer | Number of journal lines |
| `total_debits` | String | Sum of all debit amounts |
| `total_credits` | String | Sum of all credit amounts |
| `message` | String | Human-readable status |

**Error Response (500):**

```json
{
  "error": "Unbalanced entries detected",
  "details": {
    "unbalanced_entries": [3, 7, 12]
  }
}
```

**Use Cases:**
- Data integrity audits
- Post-migration validation
- Automated monitoring

---

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "Error message"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Bad request (missing/invalid parameters) |
| `401` | Unauthorized (not logged in) |
| `403` | Forbidden (insufficient permissions) |
| `404` | Not found |
| `429` | Too many requests (rate limited) |
| `500` | Internal server error |

---

## Rate Limiting

The API is rate-limited using Flask-Limiter:

- **Default:** 200 requests per day, 50 requests per hour
- **Storage:** In-memory (development) or Redis (production)

Rate limit headers are included in responses when Flask-Limiter is configured with header injection:

```
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 199
X-RateLimit-Reset: 1690000000
```

---

## Multi-Tenancy

All API responses are automatically scoped to the authenticated user's business. Users from one business cannot access data from another business.

**Implementation:** Queries are filtered by `current_user.business_id` via the `_business_id()` helper in `app/api/routes.py`.

---

## Future Endpoints

Planned API endpoints (not yet implemented):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/customers` | List customers |
| `GET` | `/api/invoices` | List invoices |
| `POST` | `/api/invoices` | Create invoice |
| `GET` | `/api/payments` | List payments |
| `POST` | `/api/payments` | Create payment |
| `GET` | `/api/reports/income-statement` | Income statement JSON |
| `GET` | `/api/reports/balance-sheet` | Balance sheet JSON |

For the full list of available web routes, see [README.md](README.md#api-endpoints).

---

## Authentication Details

TrackWise uses Flask-Login for session management. To call authenticated API endpoints:

1. **POST** to `/login` with email and password to obtain a session cookie.
2. Include the session cookie in subsequent API requests.
3. Session cookies are `HTTPOnly` and `SameSite=Lax`.

**Example login request:**

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "email=user@example.com&password=securepassword"
```

**Example authenticated request:**

```bash
curl -b cookies.txt http://localhost:5000/api/products
```

---

## CORS

Cross-Origin Resource Sharing (CORS) is not currently enabled for the JSON API. For browser-based integrations, consider:

1. Using a server-side proxy.
2. Enabling CORS via Flask-CORS (requires adding the dependency).
3. Using the web UI routes instead of the JSON API for same-origin access.

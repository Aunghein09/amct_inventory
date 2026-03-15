# AGENTS.md — Django + Supabase (Postgres) Inventory App

## 1) Project Goal

Build a single-business inventory management web app with:

- Separate login paths for admin (Django admin panel) and members (inventory UI)
- Products with cost and three selling prices (retail, wholesale, accessory)
- Stock movement ledger (receive / sell / adjust / transfer)
- Computed current stock (not stored directly)
- Role-based access (admin vs staff)
- Admin-editable stock moves with edit tracking
- Daily voucher system for sales reconciliation (with PNG/PDF export)
- Safe, maintainable data model

Primary stack:
- Django 5.2
- PostgreSQL (Supabase hosted) / SQLite for local dev
- Django templates

---

## 2) Core Architecture

Stock is always computed from:

SUM(stock_moves.qty_delta)

We DO NOT store `current_stock` as a mutable field.

This guarantees:
- Audit trail (edited_at / edited_by tracked on every change)
- Concurrency safety
- Easy debugging
- Data integrity

Stock moves are **editable by admin** through the Django admin panel.
Every edit records `edited_at` and `edited_by` for audit purposes.
Deletion of stock moves is not allowed.

---

## 3) Apps Structure

We use two Django apps inside one Django project.

### accounts app

Handles:
- Profile (display name extension of auth.User)
- Membership (user role: admin, manager, or staff)
- Django Group "Manager" for admin-panel permission management

### inventory app

Handles:
- Product
- Location
- StockMove
- DailyVoucher
- Inventory queries

---

## 4) Data Model

### 4.1 accounts

#### Profile
- user (OneToOne to auth.User)
- display_name

#### Membership
- user (OneToOne to auth.User)
- role: `admin` | `manager` | `staff`

Note: Organization model was removed. This is a single-business app.

Role sync (via post_save signal on Membership):
- admin → `is_staff=True`, `is_superuser=True`
- manager → `is_staff=True`, `is_superuser=False`, added to "Manager" group
- staff → `is_staff=False`, `is_superuser=False`

The "Manager" Django Group controls admin panel permissions.
Default Manager permissions: all inventory model permissions (product, location, stockmove).
Admin can adjust Manager group permissions via the Django admin panel.

---

### 4.2 inventory

#### Product

Fields:

- id (UUID)
- sku (unique)
- shop_code (optional)
- name
- size (choices: XS, S, M, L, XL, 2XL, 3XL, Custom)
- custom_size (text, used when size is Custom)
- image (ImageField, optional)
- cost (DecimalField)
- selling_price1 (DecimalField) → Retail price
- selling_price2 (DecimalField, optional) → Wholesale price
- accessory_price (DecimalField, optional) → Accessory price
- barcode (optional)
- is_active
- created_at
- updated_at

Important:
- Never use Float for money.
- Always use DecimalField.

Example:

models.DecimalField(max_digits=10, decimal_places=2)

---

#### Location

- name (unique)
- created_at
- updated_at

---

#### StockMove

- id (UUID)
- product (FK)
- location (nullable)
- qty_delta (decimal)
- reason (receive / sale / adjust / transfer_in / transfer_out)
- price_tier (retail / wholesale, blank for non-sale moves)
- note (optional)
- created_by (FK to user)
- created_at
- reference_id (optional invoice/order ID)
- edited_at (nullable, set on edit)
- edited_by (FK to user, nullable, set on edit)

Rules:

- Stock moves are editable by admin via the Django admin panel.
- Every edit records edited_at and edited_by.
- Deletion of stock moves is not allowed.
- Members cannot edit stock moves (read-only in member UI).

---

#### DailyVoucher

- id (UUID)
- date (unique — one voucher per day)
- payment_method (kpay / kbzBank / kpay_kbzBank / cash)
- payment_date (nullable — may differ from voucher date)
- subtotal (DecimalField — total sales revenue)
- accessory_total (DecimalField — total accessory deduction)
- grand_total (DecimalField — subtotal minus accessory_total)
- is_finalized (boolean, default True)
- finalized_by (FK to user)
- finalized_at (datetime)
- created_at (datetime)

Rules:

- One voucher per day maximum.
- Once finalized, the voucher is immutable (read-only in admin).
- Voucher snapshots totals at finalization time.
- Accessory deduction = sum(product.accessory_price × abs(qty)) for sale lines.
- Export as PNG (via html2canvas) or PDF (via browser print) available regardless of finalization status.

---

## 5) Stock Computation

Current stock per product:

SUM(stock_moves.qty_delta)

Current stock per product per location:

SUM(stock_moves.qty_delta) GROUP BY product, location

Computed via Django ORM aggregation in views.

---

## 6) Pricing Design

We support three selling prices:

- selling_price1 → Retail
- selling_price2 → Wholesale (optional)
- accessory_price → Accessory (optional)

This allows:
- Different customer types
- Basic margin tracking
- Future expansion to pricing tiers

---

## 7) Inventory Value & Profit Logic

Inventory valuation:

Current Stock × cost

Retail potential revenue:

Current Stock × selling_price1

Wholesale potential revenue:

Current Stock × selling_price2

Profit per unit:

selling_priceX - cost

---

## 8) Business Rules

- Stock changes only through StockMove
- Transfers must use transaction.atomic()
- Prevent negative stock at application level
- Validate selling_price ≥ cost (enforced in model clean)
- Stock moves editable by admin only; edits tracked with edited_at/edited_by
- Stock moves cannot be deleted

---

## 9) Login & Role Design

Login page has two tabs:
- **Member tab** (default): authenticates and redirects to `/` (inventory UI)
- **Admin tab**: authenticates and redirects to `/admin/` (Django admin panel)

Role separation:
- **Staff (member)**: can view dashboard (SKU, shop code, name, current stock) and own moves; can record receive and sale
- **Manager**: same as staff in inventory UI; can also access Django admin panel with permissions defined by the "Manager" group
- **Admin**: full access via Django admin panel (create/edit products, adjust stock, modify moves)
- Even if an admin logs in via the member tab, they only see member functions

Admin-only operations are managed through the Django admin panel:
- Create / edit products
- Stock adjustments
- Edit stock moves directly (tracked with edited_at / edited_by)
- Configure manager permissions (via Manager group permissions)

---

## 10) Definition of Done (MVP)

The system must allow:

- Login / logout (with admin/member tab separation)
- Create product (admin, via Django admin panel)
- Record stock receive (member + admin)
- Record stock sale (member + admin)
- View current inventory (dashboard)
- View movement history (with date filtering and summary)
- Stock adjustment (admin, via Django admin panel)
- Edit stock moves (admin, via Django admin panel)
- Daily voucher — sales reconciliation by date (admin, via Django admin panel)
- Daily voucher export as PNG or PDF
- Membership management (admin, via Django admin panel)

---

## 11) Long-Term Safety Principles

- Database is Postgres (Supabase) for production
- SQLite for local development
- Daily backups enabled (when production)
- All financial fields use Decimal
- All operations are atomic
- Stock move edits tracked (edited_at / edited_by)

---

## 12) Project Layout

```
config/          Django project settings + URL config
accounts/        profile, membership, role helpers, decorators
inventory/       product, location, stock ledger, forms, views, services
templates/       base, auth (login, no_membership), inventory UI pages
static/          static assets
```

Operational defaults:

- `DATABASE_URL` env var enables Supabase Postgres
- SQLite fallback for local bootstrap
- Stock moves editable by admin with edit tracking
- Current stock is computed via aggregation

Routes:

- `/accounts/login/` → tabbed login (member / admin)
- `/accounts/logout/`
- `/` → dashboard with computed stock (SKU, shop code, name, current stock)
- `/moves/` → movement history filtered to logged-in member, with date filter + summary
- `/moves/receive/` → record stock receive
- `/moves/sale/` → record stock sale
- `/moves/adjust/` → record stock adjustment (admin only)
- `/admin/` → Django admin panel
- `/admin/inventory/dashboard/` → inventory dashboard
- `/admin/inventory/daily-voucher/` → daily voucher (sales reconciliation)

---

## 13) Deployment (Google Cloud Run)

### Stack

- **Hosting**: Google Cloud Run (scales to zero, pay-per-request)
- **Static files**: WhiteNoise (served from Django, no Nginx required)
- **WSGI server**: Gunicorn
- **Container**: Dockerfile with Python 3.12-slim
- **CI/CD**: Cloud Build trigger connected to GitHub (auto-deploy on push to main)
- **Database**: Any Postgres via `DATABASE_URL` (Neon free tier or Supabase free tier)

### How auto-deploy works

1. Push code to `main` branch on GitHub
2. Cloud Build trigger fires automatically
3. `cloudbuild.yaml` builds Docker image → pushes to Artifact Registry → deploys to Cloud Run
4. Cloud Run serves the new version

### Environment variables (set in Cloud Run Console, not in .env)

| Variable | Example |
|---|---|
| `SECRET_KEY` | (strong random string, 50+ chars) |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `amct-inventory-xxx.run.app,yourdomain.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://amct-inventory-xxx.run.app,https://yourdomain.com` |
| `DATABASE_URL` | `postgres://user:pass@host:5432/dbname` |
| `DB_SSL_REQUIRE` | `True` |

### Production security (automatic when DEBUG=False)

- `SECURE_SSL_REDIRECT = True`
- `SECURE_PROXY_SSL_HEADER` set for Cloud Run HTTPS termination
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- HSTS enabled (1 year)

### Static files

WhiteNoise serves compressed, cache-busted static files directly from Django.
`collectstatic` runs at Docker build time (in Dockerfile).

### Media files (product images)

Media files are stored on the container filesystem (ephemeral).
They will be lost on each redeploy. For production with product images,
add `django-storages` + Google Cloud Storage as a follow-up.

### Initial GCP setup (one-time)

1. Create a GCP project
2. Enable Cloud Run, Cloud Build, and Artifact Registry APIs
3. Create an Artifact Registry Docker repository (`amct-inventory` in `asia-southeast1`)
4. Connect GitHub repo via Cloud Build trigger (trigger on push to `main`)
5. Set environment variables in the Cloud Run service configuration

---

End of AGENTS.md

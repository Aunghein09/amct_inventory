# AMCT Inventory (Django + Supabase Postgres)

Single-business inventory management app with role-based access, stock ledger, and daily voucher system.

## Stack

- Django 5.2
- PostgreSQL (Supabase-ready via `DATABASE_URL`) / SQLite for local dev
- Django templates

## Apps

- `accounts`
  - `Profile` (display name extension of auth.User)
  - `Membership` (`admin` / `manager` / `staff`)
- `inventory`
  - `Product` (SKU, shop code, sizes, cost, retail/wholesale/accessory pricing)
  - `Location`
  - `StockMove` (editable ledger with edit tracking)
  - `DailyVoucher` (sales reconciliation with PNG/PDF export)

## Core Rules

- Current stock is computed from `SUM(stock_moves.qty_delta)`.
- Stock moves are editable by admin; edits tracked with `edited_at` / `edited_by`.
- Negative stock is blocked at the application level.
- Product management via Django admin panel only.
- Members see dashboard (SKU, shop code, name, current stock) and their own moves.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # then edit SECRET_KEY, DATABASE_URL, etc.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

4. Open:
- App: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Supabase Setup

Set `DATABASE_URL` in `.env` to your Supabase Postgres connection string, then run:

```bash
python manage.py migrate
```

## Included Pages (MVP Skeleton)

- Login / logout
- Dashboard with computed current stock
- Product list + create product
- Record stock receive
- Record stock sale
- Stock movement history

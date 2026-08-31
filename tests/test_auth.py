"""
Tests for JWT authentication, multi-tenant isolation, and admin endpoints.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite DB with companies, users, and orders tables."""
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(200) NOT NULL UNIQUE,
                slug VARCHAR(100) NOT NULL UNIQUE,
                email_domain VARCHAR(200),
                segment VARCHAR(30),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """))
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(200) NOT NULL UNIQUE,
                password_hash VARCHAR(200) NOT NULL,
                full_name VARCHAR(200) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                company_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                order_id VARCHAR(30) NOT NULL,
                order_date DATE NOT NULL,
                ship_date DATE,
                ship_mode VARCHAR(50),
                customer_id VARCHAR(30),
                customer_name VARCHAR(100),
                segment VARCHAR(30),
                country VARCHAR(60),
                city VARCHAR(60),
                state VARCHAR(60),
                postal_code VARCHAR(10),
                region VARCHAR(20),
                product_id VARCHAR(30) NOT NULL,
                category VARCHAR(60),
                sub_category VARCHAR(60),
                product_name VARCHAR(250),
                sales DECIMAL(12,2) NOT NULL DEFAULT 0,
                quantity INT NOT NULL DEFAULT 0,
                discount DECIMAL(5,2) NOT NULL DEFAULT 0,
                profit DECIMAL(12,2) NOT NULL DEFAULT 0,
                company_id INTEGER DEFAULT 1,
                PRIMARY KEY (order_id, product_id)
            )
        """))

        # Seed companies
        conn.execute(text("""
            INSERT INTO companies (id, name, slug, email_domain, segment)
            VALUES (1, 'Company A', 'company-a', 'a.com', 'Consumer')
        """))
        conn.execute(text("""
            INSERT INTO companies (id, name, slug, email_domain, segment)
            VALUES (2, 'Company B', 'company-b', 'b.com', 'Corporate')
        """))

        # Seed users
        from passlib.hash import bcrypt
        admin_hash = bcrypt.hash("admin123")
        user_hash = bcrypt.hash("user123")
        user2_hash = bcrypt.hash("user2pass")

        conn.execute(text("""
            INSERT INTO users (email, password_hash, full_name, role, company_id)
            VALUES (:email, :hash, :name, :role, :cid)
        """), {"email": "admin@a.com", "hash": admin_hash, "name": "Admin A", "role": "admin", "cid": 1})

        conn.execute(text("""
            INSERT INTO users (email, password_hash, full_name, role, company_id)
            VALUES (:email, :hash, :name, :role, :cid)
        """), {"email": "user@a.com", "hash": user_hash, "name": "User A", "role": "user", "cid": 1})

        conn.execute(text("""
            INSERT INTO users (email, password_hash, full_name, role, company_id)
            VALUES (:email, :hash, :name, :role, :cid)
        """), {"email": "user@b.com", "hash": user2_hash, "name": "User B", "role": "user", "cid": 2})

        # Seed orders for both companies
        conn.execute(text("""
            INSERT INTO orders (order_id, order_date, product_id, category, sub_category, sales, quantity, profit, company_id, segment, country, city, state, region, product_name)
            VALUES ('ORD-001', '2024-01-15', 'P-001', 'Technology', 'Phones', 500.0, 2, 100.0, 1, 'Consumer', 'US', 'NYC', 'NY', 'East', 'Phone X')
        """))
        conn.execute(text("""
            INSERT INTO orders (order_id, order_date, product_id, category, sub_category, sales, quantity, profit, company_id, segment, country, city, state, region, product_name)
            VALUES ('ORD-002', '2024-01-16', 'P-002', 'Furniture', 'Chairs', 300.0, 1, 50.0, 1, 'Corporate', 'US', 'LA', 'CA', 'West', 'Chair Y')
        """))
        conn.execute(text("""
            INSERT INTO orders (order_id, order_date, product_id, category, sub_category, sales, quantity, profit, company_id, segment, country, city, state, region, product_name)
            VALUES ('ORD-003', '2024-01-17', 'P-003', 'Technology', 'Phones', 1000.0, 5, 200.0, 2, 'Consumer', 'US', 'CHI', 'IL', 'Central', 'Phone Z')
        """))

    return engine


@pytest.fixture
def mock_settings():
    ms = MagicMock()
    ms.SCHEDULER_ENABLED = False
    ms.JWT_SECRET_KEY = "test-secret-key"
    ms.JWT_ALGORITHM = "HS256"
    ms.JWT_EXPIRE_MINUTES = 480
    return ms


@pytest.fixture
def client(test_engine, mock_settings):
    """Create a FastAPI test client with auth-enabled DB."""
    # Clear lru_cache from any prior imports
    from src.tools import sql_tools
    if hasattr(sql_tools.get_db_engine, 'cache_clear'):
        sql_tools.get_db_engine.cache_clear()

    with patch("config.settings.settings", mock_settings), \
         patch("src.scheduler.start_scheduler", return_value=None), \
         patch("src.tools.sql_tools.get_db_engine", return_value=test_engine), \
         patch("src.auth.settings", mock_settings):
        from fastapi.testclient import TestClient

        from src.api import app
        yield TestClient(app)


@pytest.fixture
def admin_token(client):
    """Get JWT token for admin user."""
    response = client.post("/auth/login", data={
        "username": "admin@a.com",
        "password": "admin123",
    })
    return response.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_token(client):
    """Get JWT token for regular user (company 1)."""
    response = client.post("/auth/login", data={
        "username": "user@a.com",
        "password": "user123",
    })
    return response.json()["access_token"]


@pytest.fixture
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def company2_token(client):
    """Get JWT token for company 2 user."""
    response = client.post("/auth/login", data={
        "username": "user@b.com",
        "password": "user2pass",
    })
    return response.json()["access_token"]


@pytest.fixture
def company2_headers(company2_token):
    return {"Authorization": f"Bearer {company2_token}"}


# ══════════════════════════════════════════════════════════════════════════════
# AUTH TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestLogin:
    """Tests for POST /auth/login."""

    def test_login_success(self, client):
        response = client.post("/auth/login", data={
            "username": "admin@a.com",
            "password": "admin123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "admin@a.com"
        assert data["user"]["role"] == "admin"
        assert data["user"]["company_id"] == 1

    def test_login_wrong_password(self, client):
        response = client.post("/auth/login", data={
            "username": "admin@a.com",
            "password": "wrong",
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post("/auth/login", data={
            "username": "nobody@x.com",
            "password": "whatever",
        })
        assert response.status_code == 401

    def test_login_returns_company_info(self, client):
        response = client.post("/auth/login", data={
            "username": "user@b.com",
            "password": "user2pass",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["company_id"] == 2
        assert data["user"]["company_name"] == "Company B"


class TestAuthMe:
    """Tests for GET /auth/me."""

    def test_me_returns_user_info(self, client, admin_headers):
        response = client.get("/auth/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@a.com"
        assert data["role"] == "admin"
        assert data["company_id"] == 1

    def test_me_requires_token(self, client):
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_me_rejects_invalid_token(self, client):
        response = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Tests that endpoints require auth."""

    def test_runs_requires_auth(self, client):
        response = client.get("/runs")
        assert response.status_code == 401

    def test_reports_requires_auth(self, client):
        response = client.get("/reports")
        assert response.status_code == 401

    def test_db_stats_requires_auth(self, client):
        response = client.get("/db/stats")
        assert response.status_code == 401

    def test_run_sync_requires_auth(self, client):
        response = client.post("/run/sync", json={
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        })
        assert response.status_code == 401

    def test_health_is_public(self, client):
        with patch("src.tools.sql_tools.test_db_connection", return_value={
            "connected": True, "db_type": "sqlite", "message": "ok"
        }), patch("config.settings.settings") as ms:
            ms.SCHEDULER_ENABLED = False
            response = client.get("/health")
        assert response.status_code == 200


class TestRegister:
    """Tests for POST /auth/register."""

    def test_register_requires_admin(self, client, user_headers):
        response = client.post("/auth/register", headers=user_headers, json={
            "email": "new@a.com",
            "password": "pass123",
            "full_name": "New User",
            "company_id": 1,
        })
        assert response.status_code == 403

    def test_register_success(self, client, admin_headers):
        response = client.post("/auth/register", headers=admin_headers, json={
            "email": "new@a.com",
            "password": "pass123",
            "full_name": "New User",
            "company_id": 1,
        })
        assert response.status_code == 200
        assert response.json()["email"] == "new@a.com"

    def test_register_duplicate_email(self, client, admin_headers):
        response = client.post("/auth/register", headers=admin_headers, json={
            "email": "admin@a.com",
            "password": "pass123",
            "full_name": "Dup",
            "company_id": 1,
        })
        assert response.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-TENANT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestMultiTenant:
    """Tests for company data isolation."""

    def test_db_stats_returns_own_company_data(self, client, user_headers, company2_headers):
        r1 = client.get("/db/stats", headers=user_headers)
        r2 = client.get("/db/stats", headers=company2_headers)

        assert r1.status_code == 200
        assert r2.status_code == 200

        # Company 1 has 2 orders, Company 2 has 1
        assert r1.json()["total_orders"] == 2
        assert r2.json()["total_orders"] == 1

    def test_reports_isolated_by_company(self, client, user_headers, company2_headers, tmp_path):
        # Create company-specific report dirs
        reports_1 = tmp_path / "1"
        reports_1.mkdir()
        (reports_1 / "report_c1.md").write_text("# Company 1 Report")

        reports_2 = tmp_path / "2"
        reports_2.mkdir()
        (reports_2 / "report_c2.md").write_text("# Company 2 Report")

        with patch("src.api.Path") as mock_path_cls:
            def path_side_effect(p):
                if p == "data/reports/1":
                    return reports_1
                if p == "data/reports/2":
                    return reports_2
                return Path(p)
            mock_path_cls.side_effect = path_side_effect

            r1 = client.get("/reports", headers=user_headers)
            r2 = client.get("/reports", headers=company2_headers)

        assert len(r1.json()["reports"]) == 1
        assert r1.json()["reports"][0]["filename"] == "report_c1.md"
        assert len(r2.json()["reports"]) == 1
        assert r2.json()["reports"][0]["filename"] == "report_c2.md"

    def test_runs_filtered_by_company(self, client, user_headers, company2_headers, tmp_path):
        metrics_file = tmp_path / "pipeline_runs.jsonl"
        metrics_file.write_text(
            json.dumps({"run_id": "r1", "company_id": 1}) + "\n"
            + json.dumps({"run_id": "r2", "company_id": 2}) + "\n"
            + json.dumps({"run_id": "r3", "company_id": 1}) + "\n"
        )

        with patch("src.api.METRICS_PATH", metrics_file):
            r1 = client.get("/runs", headers=user_headers)
            r2 = client.get("/runs", headers=company2_headers)

        assert len(r1.json()["runs"]) == 2
        assert len(r2.json()["runs"]) == 1
        assert r2.json()["runs"][0]["run_id"] == "r2"


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminCompanies:
    """Tests for admin company management."""

    def test_list_companies_requires_admin(self, client, user_headers):
        response = client.get("/admin/companies", headers=user_headers)
        assert response.status_code == 403

    def test_list_companies(self, client, admin_headers):
        response = client.get("/admin/companies", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["companies"]) == 2

    def test_create_company(self, client, admin_headers):
        response = client.post("/admin/companies", headers=admin_headers, json={
            "name": "New Corp",
            "slug": "new-corp",
            "email_domain": "newcorp.com",
            "segment": "Consumer",
        })
        assert response.status_code == 200
        assert "New Corp" in response.json()["message"]

    def test_create_duplicate_slug(self, client, admin_headers):
        response = client.post("/admin/companies", headers=admin_headers, json={
            "name": "Another A",
            "slug": "company-a",
            "email_domain": "",
            "segment": "Consumer",
        })
        assert response.status_code == 400


class TestAdminUsers:
    """Tests for admin user management."""

    def test_list_users_requires_admin(self, client, user_headers):
        response = client.get("/admin/users", headers=user_headers)
        assert response.status_code == 403

    def test_list_users(self, client, admin_headers):
        response = client.get("/admin/users", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 3


class TestAdminUploadData:
    """Tests for CSV upload."""

    def test_upload_requires_admin(self, client, user_headers):
        response = client.post("/admin/upload-data", headers=user_headers)
        assert response.status_code == 403

    def test_upload_csv_success(self, client, admin_headers):
        csv_content = (
            "order_id,order_date,product_id,category,sub_category,sales,quantity,profit,segment,country,city,state,region,product_name\n"
            "ORD-100,2024-02-01,P-100,Tech,Phones,200,1,50,Consumer,US,NYC,NY,East,TestProd\n"
        )
        response = client.post(
            "/admin/upload-data?company_id=1",
            headers=admin_headers,
            files={"file": ("data.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["new_rows"] == 1

    def test_upload_csv_missing_columns(self, client, admin_headers):
        csv_content = "name,value\nfoo,123\n"
        response = client.post(
            "/admin/upload-data",
            headers=admin_headers,
            files={"file": ("bad.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 400
        assert "Missing required columns" in response.json()["detail"]


# ══════════════════════════════════════════════════════════════════════════════
# DB SYNC TESTS — direct SQL changes reflected via API
# ══════════════════════════════════════════════════════════════════════════════

class TestDbSync:
    """Verify that direct SQL changes are immediately visible through the API."""

    def test_direct_sql_company_visible_in_api(self, client, admin_headers, test_engine):
        """Company inserted via raw SQL should appear in GET /admin/companies."""
        with test_engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO companies (name, slug, email_domain)
                VALUES ('Direct SQL Co.', 'direct-sql', 'directsql.com')
            """))

        response = client.get("/admin/companies", headers=admin_headers)
        assert response.status_code == 200
        names = [c["name"] for c in response.json()["companies"]]
        assert "Direct SQL Co." in names

    def test_direct_sql_company_auto_increment(self, client, admin_headers, test_engine):
        """Company added via SQL gets next auto-increment id."""
        with test_engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO companies (name, slug, email_domain)
                VALUES ('AutoInc Co.', 'autoinc', 'autoinc.com')
            """))

        response = client.get("/admin/companies", headers=admin_headers)
        companies = response.json()["companies"]
        autoinc = [c for c in companies if c["slug"] == "autoinc"][0]
        assert autoinc["id"] > 2  # must be after the 2 seeded companies

    def test_admin_created_company_auto_increment(self, client, admin_headers):
        """Company created via API gets next auto-increment id after existing max."""
        response = client.post("/admin/companies", headers=admin_headers, json={
            "name": "API Created Co.", "slug": "api-created", "email_domain": "apicreated.com", "segment": "Corporate",
        })
        assert response.status_code == 200

        response = client.get("/admin/companies", headers=admin_headers)
        companies = response.json()["companies"]
        api_co = [c for c in companies if c["slug"] == "api-created"][0]
        max_other = max(c["id"] for c in companies if c["slug"] != "api-created")
        assert api_co["id"] > max_other

    def test_direct_sql_orders_visible_in_stats(self, client, admin_headers, test_engine):
        """Orders inserted via raw SQL should appear in DB stats."""
        with test_engine.connect() as conn:
            before = conn.execute(text(
                "SELECT COUNT(*) FROM orders WHERE company_id = 1"
            )).scalar()

        with test_engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO orders (order_id, order_date, product_id, category, sub_category,
                    sales, quantity, profit, company_id, segment, country, city, state, region, product_name)
                VALUES ('ORD-SYNC-1', '2024-03-01', 'P-SYNC', 'Technology', 'Phones',
                    750.0, 3, 150.0, 1, 'Consumer', 'US', 'NYC', 'NY', 'East', 'SyncPhone')
            """))

        with test_engine.connect() as conn:
            after = conn.execute(text(
                "SELECT COUNT(*) FROM orders WHERE company_id = 1"
            )).scalar()

        assert after == before + 1

    def test_direct_sql_user_can_login(self, client, test_engine):
        """User inserted via raw SQL should be able to login."""
        from passlib.hash import bcrypt
        pw_hash = bcrypt.hash("directpass")
        with test_engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO users (email, password_hash, full_name, role, company_id)
                VALUES (:email, :hash, :name, :role, :cid)
            """), {"email": "direct@a.com", "hash": pw_hash, "name": "Direct User", "role": "user", "cid": 1})

        response = client.post("/auth/login", data={
            "username": "direct@a.com",
            "password": "directpass",
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

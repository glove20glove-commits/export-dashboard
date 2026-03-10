import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "trade_data.db"))


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracked_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT NOT NULL,
                item_type TEXT NOT NULL DEFAULT 'HS',
                region_type TEXT NOT NULL DEFAULT '3',
                region_name TEXT,
                label TEXT,
                stock_code TEXT,
                stock_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trade_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL REFERENCES tracked_items(id) ON DELETE CASCADE,
                year TEXT NOT NULL,
                month TEXT NOT NULL,
                export_amt INTEGER DEFAULT 0,
                export_rate REAL,
                import_amt INTEGER DEFAULT 0,
                import_rate REAL,
                balance INTEGER DEFAULT 0,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(item_id, year, month)
            );

            CREATE INDEX IF NOT EXISTS idx_trade_data_item_date
            ON trade_data(item_id, year, month);

            CREATE TABLE IF NOT EXISTS quarterly_revenue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL REFERENCES tracked_items(id) ON DELETE CASCADE,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                year TEXT NOT NULL,
                quarter TEXT NOT NULL,
                revenue REAL DEFAULT 0,
                UNIQUE(item_id, year, quarter)
            );

            CREATE TABLE IF NOT EXISTS stock_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL REFERENCES tracked_items(id) ON DELETE CASCADE,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                year TEXT NOT NULL,
                month TEXT NOT NULL,
                close_price INTEGER DEFAULT 0,
                UNIQUE(item_id, year, month)
            );

            -- 회사 탐방 관리 테이블
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                stock_code TEXT,
                sector TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_code)
            );

            CREATE TABLE IF NOT EXISTS company_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                visit_date TEXT NOT NULL,
                visit_time TEXT,
                purpose TEXT,
                attendees TEXT,
                status TEXT NOT NULL DEFAULT 'scheduled',
                summary TEXT,
                alarm_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_visits_date ON company_visits(visit_date);

            CREATE TABLE IF NOT EXISTS visit_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                visit_id INTEGER REFERENCES company_visits(id) ON DELETE SET NULL,
                filename TEXT NOT NULL,
                mime_type TEXT,
                file_data BLOB,
                file_size INTEGER DEFAULT 0,
                description TEXT,
                text_content TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS company_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                event_date TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                alarm_date TEXT,
                alarm_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_events_alarm ON company_events(alarm_date, alarm_sent);

            CREATE TABLE IF NOT EXISTS company_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                report_date TEXT NOT NULL,
                source TEXT,
                title TEXT,
                summary TEXT,
                target_price INTEGER,
                rating TEXT,
                original_filename TEXT,
                original_file BLOB,
                mime_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS company_consensus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                stock_code TEXT NOT NULL,
                period_type TEXT NOT NULL,
                period TEXT NOT NULL,
                revenue REAL,
                operating_profit REAL,
                net_income REAL,
                eps REAL,
                per REAL,
                is_estimate INTEGER DEFAULT 0,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, period_type, period)
            );
            -- 관광 데이터 테이블
            CREATE TABLE IF NOT EXISTS tourism_countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nat_cd TEXT NOT NULL UNIQUE,
                nat_nm TEXT NOT NULL,
                tar_cd TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tourism_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_id INTEGER NOT NULL REFERENCES tourism_countries(id) ON DELETE CASCADE,
                year TEXT NOT NULL,
                month TEXT NOT NULL,
                visitors INTEGER DEFAULT 0,
                prev_visitors INTEGER DEFAULT 0,
                change_rate REAL DEFAULT 0,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(country_id, year, month)
            );
            CREATE INDEX IF NOT EXISTS idx_tourism_data_country_date
            ON tourism_data(country_id, year, month);

            -- 국민연금 사업장 인원 테이블
            CREATE TABLE IF NOT EXISTS nps_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seq TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                biz_no TEXT,
                current_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS nps_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES nps_companies(id) ON DELETE CASCADE,
                year TEXT NOT NULL,
                month TEXT NOT NULL,
                subscribers INTEGER DEFAULT 0,
                new_hires INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, year, month)
            );
            CREATE INDEX IF NOT EXISTS idx_nps_data_company_date
            ON nps_data(company_id, year, month);

            -- 유튜브 채널 모니터링 테이블
            CREATE TABLE IF NOT EXISTS youtube_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL UNIQUE,
                channel_name TEXT,
                channel_url TEXT,
                last_checked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS youtube_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_db_id INTEGER NOT NULL REFERENCES youtube_channels(id) ON DELETE CASCADE,
                video_id TEXT NOT NULL UNIQUE,
                title TEXT,
                description TEXT,
                summary TEXT,
                thumbnail_url TEXT,
                published_at TEXT,
                url TEXT,
                notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_youtube_videos_channel
            ON youtube_videos(channel_db_id, published_at);

            -- 시장 지표 테이블
            CREATE TABLE IF NOT EXISTS market_indices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                year TEXT NOT NULL,
                month TEXT NOT NULL,
                close_price REAL DEFAULT 0,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, year, month)
            );

            CREATE TABLE IF NOT EXISTS market_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                year TEXT NOT NULL,
                month TEXT NOT NULL,
                export_amt INTEGER DEFAULT 0,
                export_rate REAL DEFAULT 0,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, year, month)
            );
        """)
        # Migration: add text_content column if missing
        try:
            conn.execute("SELECT text_content FROM visit_materials LIMIT 1")
        except Exception:
            conn.execute("ALTER TABLE visit_materials ADD COLUMN text_content TEXT")


# --- tracked_items CRUD ---

def add_item(item_code, item_type="HS", region_type="3", region_name=None, label=None, stock_code=None, stock_name=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tracked_items (item_code, item_type, region_type, region_name, label, stock_code, stock_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (item_code, item_type, region_type, region_name, label, stock_code, stock_name),
        )
        return cur.lastrowid


def get_items():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tracked_items ORDER BY id").fetchall()]


def get_item(item_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tracked_items WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None


def delete_item(item_id):
    with get_db() as conn:
        conn.execute("DELETE FROM trade_data WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM tracked_items WHERE id = ?", (item_id,))


# --- trade_data CRUD ---

def upsert_trade_data(item_id, year, month, export_amt, export_rate, import_amt, import_rate, balance):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO trade_data (item_id, year, month, export_amt, export_rate, import_amt, import_rate, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id, year, month) DO UPDATE SET
                export_amt = excluded.export_amt,
                export_rate = excluded.export_rate,
                import_amt = excluded.import_amt,
                import_rate = excluded.import_rate,
                balance = excluded.balance,
                fetched_at = CURRENT_TIMESTAMP
        """, (item_id, year, month, export_amt, export_rate, import_amt, import_rate, balance))


def get_trade_data(item_id, year_from=None, year_to=None):
    with get_db() as conn:
        query = "SELECT * FROM trade_data WHERE item_id = ?"
        params = [item_id]
        if year_from:
            query += " AND (year || '-' || month) >= ?"
            params.append(year_from)
        if year_to:
            query += " AND (year || '-' || month) <= ?"
            params.append(year_to)
        query += " ORDER BY year, month"
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_yearly_summary(item_id):
    with get_db() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT year,
                   SUM(export_amt) as total_export,
                   SUM(import_amt) as total_import,
                   SUM(balance) as total_balance,
                   ROUND(AVG(export_amt)) as avg_export,
                   ROUND(AVG(import_amt)) as avg_import,
                   COUNT(*) as month_count
            FROM trade_data WHERE item_id = ?
            GROUP BY year ORDER BY year
        """, (item_id,)).fetchall()]


def get_latest_month(item_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT year, month FROM trade_data WHERE item_id = ? ORDER BY year DESC, month DESC LIMIT 1",
            (item_id,),
        ).fetchone()
        return dict(row) if row else None


# --- stock_prices CRUD ---

def upsert_stock_price(item_id, stock_code, stock_name, year, month, close_price):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO stock_prices (item_id, stock_code, stock_name, year, month, close_price)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id, year, month) DO UPDATE SET
                close_price = excluded.close_price,
                stock_code = excluded.stock_code,
                stock_name = excluded.stock_name
        """, (item_id, stock_code, stock_name, year, month, close_price))


def get_stock_prices(item_id, year_from=None, year_to=None):
    with get_db() as conn:
        query = "SELECT * FROM stock_prices WHERE item_id = ?"
        params = [item_id]
        if year_from:
            query += " AND (year || '-' || month) >= ?"
            params.append(year_from)
        if year_to:
            query += " AND (year || '-' || month) <= ?"
            params.append(year_to)
        query += " ORDER BY year, month"
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_stock_info(item_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT stock_code, stock_name FROM stock_prices WHERE item_id = ? LIMIT 1",
            (item_id,),
        ).fetchone()
        return dict(row) if row else None


# --- quarterly_revenue CRUD ---

def upsert_quarterly_revenue(item_id, stock_code, stock_name, year, quarter, revenue):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO quarterly_revenue (item_id, stock_code, stock_name, year, quarter, revenue)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id, year, quarter) DO UPDATE SET
                revenue = excluded.revenue,
                stock_code = excluded.stock_code,
                stock_name = excluded.stock_name
        """, (item_id, stock_code, stock_name, year, quarter, revenue))


def get_quarterly_revenue(item_id, year_from=None, year_to=None):
    with get_db() as conn:
        query = "SELECT * FROM quarterly_revenue WHERE item_id = ?"
        params = [item_id]
        if year_from:
            query += " AND year >= ?"
            params.append(year_from)
        if year_to:
            query += " AND year <= ?"
            params.append(year_to)
        query += " ORDER BY year, quarter"
        return [dict(r) for r in conn.execute(query, params).fetchall()]


# --- companies CRUD ---

def add_company(name, stock_code=None, sector=None, notes=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO companies (name, stock_code, sector, notes) VALUES (?, ?, ?, ?)",
            (name, stock_code, sector, notes),
        )
        return cur.lastrowid


def get_companies():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM companies ORDER BY created_at DESC").fetchall()]


def get_company(company_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        return dict(row) if row else None


def update_company(company_id, name=None, stock_code=None, sector=None, notes=None):
    with get_db() as conn:
        fields, params = [], []
        if name is not None:
            fields.append("name = ?"); params.append(name)
        if stock_code is not None:
            fields.append("stock_code = ?"); params.append(stock_code)
        if sector is not None:
            fields.append("sector = ?"); params.append(sector)
        if notes is not None:
            fields.append("notes = ?"); params.append(notes)
        if not fields:
            return
        params.append(company_id)
        conn.execute(f"UPDATE companies SET {', '.join(fields)} WHERE id = ?", params)


def delete_company(company_id):
    with get_db() as conn:
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))


# --- company_visits CRUD ---

def add_visit(company_id, visit_date, visit_time=None, purpose=None, attendees=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO company_visits (company_id, visit_date, visit_time, purpose, attendees) VALUES (?, ?, ?, ?, ?)",
            (company_id, visit_date, visit_time, purpose, attendees),
        )
        return cur.lastrowid


def get_visits(company_id):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM company_visits WHERE company_id = ? ORDER BY visit_date DESC", (company_id,)
        ).fetchall()]


def get_all_visits():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT v.id, v.company_id, v.visit_date, v.visit_time, v.purpose, v.status, v.summary,
                   c.name as company_name, c.stock_code
            FROM company_visits v JOIN companies c ON v.company_id = c.id
            ORDER BY v.visit_date DESC
        """).fetchall()]


def get_upcoming_visits(limit=10):
    with get_db() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT v.*, c.name as company_name, c.stock_code
            FROM company_visits v JOIN companies c ON v.company_id = c.id
            WHERE v.visit_date >= date('now') AND v.status = 'scheduled'
            ORDER BY v.visit_date ASC LIMIT ?
        """, (limit,)).fetchall()]


def update_visit(visit_id, **kwargs):
    with get_db() as conn:
        fields, params = [], []
        for k in ("visit_date", "visit_time", "purpose", "attendees", "status", "summary"):
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?"); params.append(kwargs[k])
        if not fields:
            return
        params.append(visit_id)
        conn.execute(f"UPDATE company_visits SET {', '.join(fields)} WHERE id = ?", params)


def delete_visit(visit_id):
    with get_db() as conn:
        conn.execute("DELETE FROM company_visits WHERE id = ?", (visit_id,))


def get_pending_visit_alarms(date_str):
    with get_db() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT v.*, c.name as company_name
            FROM company_visits v JOIN companies c ON v.company_id = c.id
            WHERE v.visit_date = ? AND v.alarm_sent = 0 AND v.status = 'scheduled'
        """, (date_str,)).fetchall()]


def mark_visit_alarm_sent(visit_id):
    with get_db() as conn:
        conn.execute("UPDATE company_visits SET alarm_sent = 1 WHERE id = ?", (visit_id,))


# --- visit_materials CRUD ---

def add_visit_material(company_id, visit_id, filename, mime_type, file_data, file_size, description=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO visit_materials (company_id, visit_id, filename, mime_type, file_data, file_size, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (company_id, visit_id, filename, mime_type, file_data, file_size, description),
        )
        return cur.lastrowid


def add_text_material(company_id, title, text_content, visit_id=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO visit_materials (company_id, visit_id, filename, mime_type, file_size, description, text_content) VALUES (?, ?, ?, 'text/plain', 0, ?, ?)",
            (company_id, visit_id, title or "텍스트 메모", title, text_content),
        )
        return cur.lastrowid


def get_visit_materials(company_id):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, company_id, visit_id, filename, mime_type, file_size, description, text_content, uploaded_at FROM visit_materials WHERE company_id = ? ORDER BY uploaded_at DESC",
            (company_id,),
        ).fetchall()]


def get_visit_material(material_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM visit_materials WHERE id = ?", (material_id,)).fetchone()
        return dict(row) if row else None


def delete_visit_material(material_id):
    with get_db() as conn:
        conn.execute("DELETE FROM visit_materials WHERE id = ?", (material_id,))


# --- company_events CRUD ---

def add_event(company_id, event_date, event_type, title, description=None, alarm_date=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO company_events (company_id, event_date, event_type, title, description, alarm_date) VALUES (?, ?, ?, ?, ?, ?)",
            (company_id, event_date, event_type, title, description, alarm_date),
        )
        return cur.lastrowid


def get_events(company_id):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM company_events WHERE company_id = ? ORDER BY event_date DESC", (company_id,)
        ).fetchall()]


def get_all_events():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT e.id, e.company_id, e.event_date, e.event_type, e.title, e.description,
                   e.alarm_date, c.name as company_name
            FROM company_events e JOIN companies c ON e.company_id = c.id
            ORDER BY e.event_date DESC
        """).fetchall()]


def update_event(event_id, **kwargs):
    with get_db() as conn:
        fields, params = [], []
        for k in ("event_date", "event_type", "title", "description", "alarm_date"):
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?"); params.append(kwargs[k])
        if not fields:
            return
        params.append(event_id)
        conn.execute(f"UPDATE company_events SET {', '.join(fields)} WHERE id = ?", params)


def delete_event(event_id):
    with get_db() as conn:
        conn.execute("DELETE FROM company_events WHERE id = ?", (event_id,))


def get_pending_event_alarms(date_str):
    with get_db() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT e.*, c.name as company_name
            FROM company_events e JOIN companies c ON e.company_id = c.id
            WHERE e.alarm_date = ? AND e.alarm_sent = 0
        """, (date_str,)).fetchall()]


def mark_event_alarm_sent(event_id):
    with get_db() as conn:
        conn.execute("UPDATE company_events SET alarm_sent = 1 WHERE id = ?", (event_id,))


# --- company_reports CRUD ---

def add_report(company_id, report_date, source=None, title=None, summary=None, target_price=None, rating=None, original_filename=None, original_file=None, mime_type=None):
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO company_reports
            (company_id, report_date, source, title, summary, target_price, rating, original_filename, original_file, mime_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (company_id, report_date, source, title, summary, target_price, rating, original_filename, original_file, mime_type),
        )
        return cur.lastrowid


def get_reports(company_id):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, company_id, report_date, source, title, summary, target_price, rating, original_filename, mime_type, created_at FROM company_reports WHERE company_id = ? ORDER BY report_date DESC",
            (company_id,),
        ).fetchall()]


def get_report(report_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM company_reports WHERE id = ?", (report_id,)).fetchone()
        return dict(row) if row else None


def update_report(report_id, summary=None, target_price=None, rating=None):
    with get_db() as conn:
        fields, params = [], []
        if summary is not None:
            fields.append("summary = ?"); params.append(summary)
        if target_price is not None:
            fields.append("target_price = ?"); params.append(target_price)
        if rating is not None:
            fields.append("rating = ?"); params.append(rating)
        if not fields:
            return
        params.append(report_id)
        conn.execute(f"UPDATE company_reports SET {', '.join(fields)} WHERE id = ?", params)


def delete_report(report_id):
    with get_db() as conn:
        conn.execute("DELETE FROM company_reports WHERE id = ?", (report_id,))


# --- company_consensus CRUD ---

def upsert_consensus(company_id, stock_code, period_type, period, revenue=None, operating_profit=None, net_income=None, eps=None, per=None, is_estimate=0):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO company_consensus (company_id, stock_code, period_type, period, revenue, operating_profit, net_income, eps, per, is_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, period_type, period) DO UPDATE SET
                revenue = excluded.revenue,
                operating_profit = excluded.operating_profit,
                net_income = excluded.net_income,
                eps = excluded.eps,
                per = excluded.per,
                is_estimate = excluded.is_estimate,
                fetched_at = CURRENT_TIMESTAMP
        """, (company_id, stock_code, period_type, period, revenue, operating_profit, net_income, eps, per, is_estimate))


def get_consensus(company_id):
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM company_consensus WHERE company_id = ? ORDER BY period_type, period",
            (company_id,),
        ).fetchall()]


# --- tourism_countries / tourism_data CRUD ---

def add_tourism_country(nat_cd, nat_nm, tar_cd=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO tourism_countries (nat_cd, nat_nm, tar_cd) VALUES (?, ?, ?)",
            (nat_cd, nat_nm, tar_cd),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM tourism_countries WHERE nat_cd = ?", (nat_cd,)).fetchone()
        return row["id"] if row else None


def get_tourism_countries():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tourism_countries ORDER BY id").fetchall()]


def get_tourism_country(country_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tourism_countries WHERE id = ?", (country_id,)).fetchone()
        return dict(row) if row else None


def delete_tourism_country(country_id):
    with get_db() as conn:
        conn.execute("DELETE FROM tourism_data WHERE country_id = ?", (country_id,))
        conn.execute("DELETE FROM tourism_countries WHERE id = ?", (country_id,))


def upsert_tourism_data(country_id, year, month, visitors, prev_visitors=0, change_rate=0):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO tourism_data (country_id, year, month, visitors, prev_visitors, change_rate)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(country_id, year, month) DO UPDATE SET
                visitors = excluded.visitors,
                prev_visitors = excluded.prev_visitors,
                change_rate = excluded.change_rate,
                fetched_at = CURRENT_TIMESTAMP
        """, (country_id, year, month, visitors, prev_visitors, change_rate))


def get_tourism_data(country_id, year_from=None, year_to=None):
    with get_db() as conn:
        sql = "SELECT * FROM tourism_data WHERE country_id = ?"
        params = [country_id]
        if year_from:
            sql += " AND year >= ?"
            params.append(str(year_from))
        if year_to:
            sql += " AND year <= ?"
            params.append(str(year_to))
        sql += " ORDER BY year, month"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# --- nps_companies / nps_data CRUD ---

def add_nps_company(seq, name, biz_no=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO nps_companies (seq, name, biz_no) VALUES (?, ?, ?)",
            (seq, name, biz_no),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM nps_companies WHERE seq = ?", (seq,)).fetchone()
        return row["id"] if row else None


def get_nps_companies():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM nps_companies ORDER BY id").fetchall()]


def get_nps_company(company_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM nps_companies WHERE id = ?", (company_id,)).fetchone()
        return dict(row) if row else None


def update_nps_company(company_id, current_count=None):
    with get_db() as conn:
        if current_count is not None:
            conn.execute(
                "UPDATE nps_companies SET current_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (current_count, company_id),
            )


def delete_nps_company(company_id):
    with get_db() as conn:
        conn.execute("DELETE FROM nps_data WHERE company_id = ?", (company_id,))
        conn.execute("DELETE FROM nps_companies WHERE id = ?", (company_id,))


def upsert_nps_data(company_id, year, month, subscribers=0, new_hires=0, losses=0):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO nps_data (company_id, year, month, subscribers, new_hires, losses)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, year, month) DO UPDATE SET
                subscribers = excluded.subscribers,
                new_hires = excluded.new_hires,
                losses = excluded.losses,
                fetched_at = CURRENT_TIMESTAMP
        """, (company_id, year, month, subscribers, new_hires, losses))


def get_nps_data(company_id, year_from=None, year_to=None):
    with get_db() as conn:
        sql = "SELECT * FROM nps_data WHERE company_id = ?"
        params = [company_id]
        if year_from:
            sql += " AND year >= ?"
            params.append(str(year_from))
        if year_to:
            sql += " AND year <= ?"
            params.append(str(year_to))
        sql += " ORDER BY year, month"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_nps_overview():
    """Get latest data for all tracked NPS companies."""
    companies = get_nps_companies()
    result = []
    for c in companies:
        data = get_nps_data(c["id"])
        if data:
            latest = data[-1]
            # Calculate month-over-month change
            prev_month = data[-2] if len(data) >= 2 else None
            mom_change = latest["subscribers"] - prev_month["subscribers"] if prev_month else 0
            # Calculate year-over-year change
            yoy_row = None
            for d in data:
                if d["year"] == str(int(latest["year"]) - 1) and d["month"] == latest["month"]:
                    yoy_row = d
                    break
            yoy_change = latest["subscribers"] - yoy_row["subscribers"] if yoy_row else 0
            result.append({
                "id": c["id"], "seq": c["seq"], "name": c["name"],
                "year": latest["year"], "month": latest["month"],
                "subscribers": latest["subscribers"],
                "new_hires": latest["new_hires"], "losses": latest["losses"],
                "mom_change": mom_change, "yoy_change": yoy_change,
                "total_months": len(data),
            })
        else:
            result.append({
                "id": c["id"], "seq": c["seq"], "name": c["name"],
                "year": "", "month": "", "subscribers": 0,
                "new_hires": 0, "losses": 0,
                "mom_change": 0, "yoy_change": 0, "total_months": 0,
            })
    return result


def get_tourism_total(year_from=None, year_to=None):
    """Get monthly total visitors summed across all tracked countries."""
    with get_db() as conn:
        sql = """
            SELECT year, month, SUM(visitors) as visitors, SUM(prev_visitors) as prev_visitors
            FROM tourism_data
        """
        params = []
        clauses = []
        if year_from:
            clauses.append("year >= ?")
            params.append(str(year_from))
        if year_to:
            clauses.append("year <= ?")
            params.append(str(year_to))
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " GROUP BY year, month ORDER BY year, month"
        rows = []
        for r in conn.execute(sql, params).fetchall():
            d = dict(r)
            prev = d["prev_visitors"]
            curr = d["visitors"]
            d["change_rate"] = round((curr - prev) / prev * 100, 1) if prev else 0
            rows.append(d)
        return rows


# --- market_indices / market_exports CRUD ---

def upsert_market_index(code, name, year, month, close_price):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO market_indices (code, name, year, month, close_price)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code, year, month) DO UPDATE SET
                close_price = excluded.close_price,
                name = excluded.name,
                fetched_at = CURRENT_TIMESTAMP
        """, (code, name, year, month, close_price))


def get_market_index(code, year_from=None, year_to=None):
    with get_db() as conn:
        sql = "SELECT * FROM market_indices WHERE code = ?"
        params = [code]
        if year_from:
            sql += " AND year >= ?"
            params.append(str(year_from))
        if year_to:
            sql += " AND year <= ?"
            params.append(str(year_to))
        sql += " ORDER BY year, month"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def upsert_market_export(category, year, month, export_amt, export_rate=0):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO market_exports (category, year, month, export_amt, export_rate)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(category, year, month) DO UPDATE SET
                export_amt = excluded.export_amt,
                export_rate = excluded.export_rate,
                fetched_at = CURRENT_TIMESTAMP
        """, (category, year, month, export_amt, export_rate))


def get_market_export(category, year_from=None, year_to=None):
    with get_db() as conn:
        sql = "SELECT * FROM market_exports WHERE category = ?"
        params = [category]
        if year_from:
            sql += " AND year >= ?"
            params.append(str(year_from))
        if year_to:
            sql += " AND year <= ?"
            params.append(str(year_to))
        sql += " ORDER BY year, month"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# --- youtube_channels / youtube_videos CRUD ---

def add_youtube_channel(channel_id, channel_name=None, channel_url=None):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO youtube_channels (channel_id, channel_name, channel_url) VALUES (?, ?, ?)",
            (channel_id, channel_name, channel_url),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM youtube_channels WHERE channel_id = ?", (channel_id,)).fetchone()
        return row["id"] if row else None


def get_youtube_channels():
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM youtube_channels ORDER BY created_at DESC"
        ).fetchall()]


def get_youtube_channel(db_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM youtube_channels WHERE id = ?", (db_id,)).fetchone()
        return dict(row) if row else None


def update_youtube_channel(db_id, channel_name=None, last_checked_at=None):
    with get_db() as conn:
        fields, params = [], []
        if channel_name is not None:
            fields.append("channel_name = ?"); params.append(channel_name)
        if last_checked_at is not None:
            fields.append("last_checked_at = ?"); params.append(last_checked_at)
        if not fields:
            return
        params.append(db_id)
        conn.execute(f"UPDATE youtube_channels SET {', '.join(fields)} WHERE id = ?", params)


def delete_youtube_channel(db_id):
    with get_db() as conn:
        conn.execute("DELETE FROM youtube_channels WHERE id = ?", (db_id,))


def upsert_youtube_video(channel_db_id, video_id, title, description=None, summary=None,
                          thumbnail_url=None, published_at=None, url=None):
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO youtube_videos
                (channel_db_id, video_id, title, description, summary, thumbnail_url, published_at, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                summary = CASE WHEN excluded.summary IS NOT NULL THEN excluded.summary ELSE summary END,
                thumbnail_url = excluded.thumbnail_url,
                published_at = excluded.published_at,
                url = excluded.url
        """, (channel_db_id, video_id, title, description, summary, thumbnail_url, published_at, url))
        return cur.lastrowid


def get_youtube_videos(channel_db_id=None, limit=50, unnotified_only=False):
    with get_db() as conn:
        sql = """
            SELECT v.*, c.channel_name, c.channel_id
            FROM youtube_videos v
            JOIN youtube_channels c ON v.channel_db_id = c.id
        """
        params = []
        clauses = []
        if channel_db_id is not None:
            clauses.append("v.channel_db_id = ?"); params.append(channel_db_id)
        if unnotified_only:
            clauses.append("v.notified = 0")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY v.published_at DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def mark_youtube_video_notified(video_id):
    with get_db() as conn:
        conn.execute("UPDATE youtube_videos SET notified = 1 WHERE video_id = ?", (video_id,))


def update_youtube_video_summary(video_id, summary):
    with get_db() as conn:
        conn.execute("UPDATE youtube_videos SET summary = ? WHERE video_id = ?", (summary, video_id))


def get_known_video_ids(channel_db_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT video_id FROM youtube_videos WHERE channel_db_id = ?", (channel_db_id,)
        ).fetchall()
        return {r["video_id"] for r in rows}

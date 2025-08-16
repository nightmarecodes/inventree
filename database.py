import os
import sqlite3
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DB_FILE = "inventree.db"

def execute_query(query, params=(), fetch=None):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        if fetch == 'one':
            return cursor.fetchone()
        if fetch == 'all':
            return cursor.fetchall()

def setup_database():
    execute_query(
        '''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            stock INTEGER NOT NULL,
            low_stock INTEGER NOT NULL,
            purchase_price REAL DEFAULT 0.0,
            sale_price REAL DEFAULT 0.0,
            supplier TEXT DEFAULT '',
            location TEXT NOT NULL DEFAULT ''
        )
        '''
    )
    execute_query(
        '''
        CREATE TABLE IF NOT EXISTS history_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            item_name TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT
        )
        '''
    )
    execute_query(
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY NOT NULL, value TEXT)"
    )
    try:
        execute_query(
            "ALTER TABLE inventory ADD COLUMN location TEXT NOT NULL DEFAULT 'N/A'"
        )
    except sqlite3.OperationalError:
        pass

def log_change(item_name, action, details=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_query(
        "INSERT INTO history_log (timestamp, item_name, action, details) VALUES (?, ?, ?, ?)",
        (timestamp, item_name, action, details)
    )

def get_setting(key):
    result = execute_query(
        "SELECT value FROM settings WHERE key = ?", (key,), fetch='one'
    )
    return result[0] if result else ""

def save_setting(key, value):
    execute_query(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
    )

def fetch_inventory(sort_column, sort_direction, search_query=""):
    query = (
        "SELECT name, stock, low_stock, purchase_price, sale_price, supplier, location FROM inventory"
    )
    params = ()
    if search_query:
        query += (
            " WHERE name LIKE ? OR location LIKE ? OR supplier LIKE ?"
        )
        params = (
            f'%{search_query}%',
            f'%{search_query}%',
            f'%{search_query}%'
        )
    query += f" ORDER BY {sort_column} {sort_direction}"
    return execute_query(query, params, fetch='all')

def fetch_item_by_name(name):
    return execute_query(
        "SELECT * FROM inventory WHERE name = ?", (name,), fetch='one'
    )

def insert_new_item(values):
    try:
        execute_query(
            "INSERT INTO inventory (name, stock, low_stock, purchase_price, sale_price, supplier, location) VALUES (?, ?, ?, ?, ?, ?, ?)",
            values
        )
        return True
    except sqlite3.IntegrityError:
        return False

def add_stock_to_item(name, new_total_stock, new_average_price):
    execute_query(
        "UPDATE inventory SET stock = ?, purchase_price = ? WHERE name = ?",
        (new_total_stock, new_average_price, name)
    )

def update_item_details(name, stock, low_stock, purchase_price, sale_price, supplier, location):
    execute_query(
        "UPDATE inventory SET stock=?, low_stock=?, purchase_price=?, sale_price=?, supplier=?, location=? WHERE name=?",
        (stock, low_stock, purchase_price, sale_price, supplier, location, name)
    )

def delete_item_by_name(name):
    execute_query(
        "DELETE FROM inventory WHERE name = ?", (name,)
    )

def fetch_history_log():
    return execute_query(
        "SELECT timestamp, item_name, action, details FROM history_log ORDER BY timestamp DESC",
        fetch='all'
    )

def fetch_dashboard_stats():
    total_items = execute_query(
        "SELECT COUNT(*) FROM inventory", fetch='one'
    )[0]
    total_value = execute_query(
        "SELECT SUM(stock * purchase_price) FROM inventory", fetch='one'
    )[0] or 0.0
    low_stock_count = execute_query(
        "SELECT COUNT(*) FROM inventory WHERE stock <= low_stock", fetch='one'
    )[0]
    return total_items, total_value, low_stock_count

def fetch_low_stock_for_email():
    critical = execute_query(
        "SELECT name, stock, low_stock FROM inventory WHERE stock <= low_stock",
        fetch='all'
    )
    warning = execute_query(
        "SELECT name, stock, low_stock FROM inventory WHERE stock > low_stock AND stock <= low_stock * 1.1 AND low_stock > 0",
        fetch='all'
    )
    return critical, warning

def send_low_stock_email():
    sender_email = os.environ.get('INVENTREE_EMAIL_USER')
    password = os.environ.get('INVENTREE_EMAIL_PASS')
    recipient_email = get_setting("recipient_email")
    if not sender_email or not password or not recipient_email:
        return (
            False,
            "Email not sent: Please ensure sender/password are in the .env file and a recipient is set in Settings."
        )
    critical_items, warning_items = fetch_low_stock_for_email()
    if not critical_items and not warning_items:
        return (True, "No low stock items to report.")
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Inventree - Low Stock Alert"
    msg['From'] = sender_email
    msg['To'] = recipient_email
    html_body = (
        "<html><body><h2>Inventree Stock Alert</h2><p>The following items require your attention.</p>"
    )
    if critical_items:
        html_body += (
            "<h3>Critically Low Stock</h3>"
            "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse;'>"
            "<tr><th>Item Name</th><th>Current Stock</th><th>Low Stock Level</th></tr>"
        )
        for item in critical_items:
            html_body += f"<tr><td>{item[0]}</td><td>{item[1]}</td><td>{item[2]}</td></tr>"
        html_body += "</table>"
    if warning_items:
        html_body += (
            "<h3>Stock Warning</h3>"
            "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse;'>"
            "<tr><th>Item Name</th><th>Current Stock</th><th>Low Stock Level</th></tr>"
        )
        for item in warning_items:
            html_body += f"<tr><td>{item[0]}</td><td>{item[1]}</td><td>{item[2]}</td></tr>"
        html_body += "</table>"
    html_body += "<br><p><i>This is an automated message from Inventree.</i></p></body></html>"
    msg.attach(MIMEText(html_body, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        return (True, f"Low stock alert email sent successfully to {recipient_email}")
    except Exception as e:
        return (False, f"Failed to send email: {e}")

def update_stock_level(name, new_stock):
    execute_query(
        "UPDATE inventory SET stock = ? WHERE name = ?", (new_stock, name)
    )
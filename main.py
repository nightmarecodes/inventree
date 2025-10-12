import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from tkinter import filedialog
import csv
from datetime import datetime
from dotenv import load_dotenv
import database  # Import our database module

# Load environment variables at the very start
load_dotenv()


class InventreeApp(ttk.Window):
    def __init__(self, themename="flatly"):
        super().__init__(themename=themename)
        self.title("Inventree")
        self.geometry("1200x800")

        self.sort_column = "name"
        self.sort_direction = "asc"

        # Initialize database and build UI
        database.setup_database()
        self._build_ui()
        self.refresh_data()


    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill='both', expand=True)

        self._create_top_frame(main_frame)
        self._create_tree_frame(main_frame)
        self._create_dashboard_frame(main_frame)
        self._create_bottom_frame(main_frame)

    def _create_top_frame(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill='x', pady=(0, 15))

        # --- Item Details / Add Stock ---
        details_frame = ttk.Labelframe(top_frame, text="Item Details / Add New Stock", padding=10)
        details_frame.pack(side='left', fill='x', expand=True)

        labels = [
            "Item Name:", "Supplier:", "Location:",
            "Stock to Add/Set:", "Low Stock Level:",
            "Purchase Price (₹):", "Sale Price (₹):"
        ]
        entry_keys = [
            'item', 'supplier', 'location',
            'stock', 'low_stock', 'purchase_price', 'sale_price'
        ]

        self.entries = {}

        for i, (label_text, key) in enumerate(zip(labels, entry_keys)):
            ttk.Label(details_frame, text=label_text).grid(
                row=i, column=0, padx=5, pady=5, sticky='w'
            )
            entry = ttk.Entry(details_frame, width=30)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky='w')
            self.entries[key] = entry

        # --- Actions Frame ---
        actions_frame = ttk.Labelframe(top_frame, text="Actions", padding=10)
        actions_frame.pack(side='left', fill='y', padx=(10, 0))

        ttk.Label(actions_frame, text="Search:").pack(padx=5, anchor='w')

        self.search_entry = ttk.Entry(actions_frame, width=25)
        self.search_entry.pack(padx=5, pady=(0, 10), fill='x')
        self.search_entry.bind("<KeyRelease>", self.search_items)

        # --- Buttons ---
        buttons_frame = ttk.Frame(actions_frame)
        buttons_frame.pack(pady=5)

        btn_config = [
            ("Add/Update Stock", self.add_item, 'success.TButton'),
            ("Update Details", self.update_item, 'info.TButton'),
            ("Delete Item", self.delete_item, 'danger.TButton'),
            ("Record Sale", self.open_sale_dialog, 'primary.TButton'),
            ("Clear Form", self.clear_fields, None)
        ]

        for text, command, style in btn_config:
            ttk.Button(
                buttons_frame, text=text, command=command, style=style
            ).pack(fill='x', pady=2)

    def _create_tree_frame(self, parent):
        tree_frame = ttk.Labelframe(parent, text="Inventory", padding=10)
        tree_frame.pack(fill='both', expand=True)

        columns = (
            'name', 'stock', 'low_stock',
            'purchase_price', 'sale_price',
            'supplier', 'location'
        )

        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        for col in columns:
            self.tree.heading(
                col, text=col.replace('_', ' ').title(),
                command=lambda c=col: self.sort_by_column(c)
            )

        self.tree.column('name', width=250)
        self.tree.column('supplier', width=150)
        self.tree.column('location', width=150)

        for col in ['stock', 'low_stock', 'purchase_price', 'sale_price']:
            self.tree.column(col, width=100, anchor='center')

        self.tree.tag_configure('low_stock_tag', background='#dc3545', foreground='white')
        self.tree.bind('<<TreeviewSelect>>', self.populate_fields_on_select)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

    def _create_dashboard_frame(self, parent):
        dashboard_frame = ttk.Labelframe(parent, text="Dashboard", padding=10)
        dashboard_frame.pack(fill='x', pady=(10, 0))

        self.total_items_var = tk.StringVar()
        self.total_value_var = tk.StringVar()
        self.low_stock_var = tk.StringVar()

        ttk.Label(dashboard_frame, textvariable=self.total_items_var, font=("-weight bold")).pack(side='left', padx=10)
        ttk.Label(dashboard_frame, textvariable=self.total_value_var, font=("-weight bold")).pack(side='left', padx=10)
        ttk.Label(dashboard_frame, textvariable=self.low_stock_var, font=("-weight bold")).pack(side='left', padx=10)

    def _create_bottom_frame(self, parent):
        bottom_frame = ttk.Frame(parent, padding=(0, 10, 0, 0))
        bottom_frame.pack(fill='x')

        ttk.Button(
            bottom_frame, text="Settings",
            command=self.open_settings_window, style='secondary.TButton'
        ).pack(side='left')

        ttk.Button(
            bottom_frame, text="View History Log",
            command=self.open_history_window, style='secondary.TButton'
        ).pack(side='left', padx=5)

        right_bottom_frame = ttk.Frame(bottom_frame)
        right_bottom_frame.pack(side='right')

        ttk.Button(
            right_bottom_frame, text="Download Template",
            command=self.download_template, style='secondary.TButton'
        ).pack(side='left', padx=5)

        ttk.Button(
            right_bottom_frame, text="Import from CSV",
            command=self.import_from_csv, style='primary.TButton'
        ).pack(side='left', padx=5)

        ttk.Button(
            right_bottom_frame, text="Export to CSV",
            command=self.export_to_csv, style='secondary.TButton'
        ).pack(side='left')


    def import_from_csv(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Select CSV File to Import"
        )

        if not filepath:
            return

        required_headers = {'Item Name', 'Stock', 'Purchase Price', 'Location'}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = set(reader.fieldnames)

                if not required_headers.issubset(headers):
                    Messagebox.show_error(
                        f"CSV is missing required headers.\nRequired: {', '.join(required_headers)}",
                        title="Import Error"
                    )
                    return

                all_rows = list(reader)

            items_to_add = []
            skipped_count = 0
            error_count = 0

            existing_items = {
                row[0] for row in database.fetch_inventory(self.sort_column, self.sort_direction)
            }

            for row in all_rows:
                name = row.get('Item Name', '').strip()

                if not name or not row.get('Stock') or not row.get('Purchase Price') or not row.get('Location'):
                    error_count += 1
                    continue

                if name in existing_items:
                    skipped_count += 1
                    continue

                try:
                    stock = int(row['Stock'])
                    purchase_price = float(row['Purchase Price'])
                    low_stock = int(row.get('Low Stock Level') or 1)
                    sale_price = float(row.get('Sale Price') or purchase_price)
                    supplier = row.get('Supplier', '')
                    location = row.get('Location', '')

                    items_to_add.append(
                        (name, stock, low_stock, purchase_price, sale_price, supplier, location)
                    )

                except (ValueError, TypeError):
                    error_count += 1
                    continue

            if items_to_add:
                database.insert_many_items(items_to_add)
                for item in items_to_add:
                    database.log_change(item[0], 'CREATED', f"Item imported from CSV with stock {item[1]}.")

            Messagebox.show_info(
                f"Import Complete!\n\nSuccessfully Added: {len(items_to_add)}\n"
                f"Skipped (Duplicates): {skipped_count}\n"
                f"Errors (Invalid Rows): {error_count}",
                title="Import Summary"
            )

            self.refresh_data()

        except Exception as e:
            Messagebox.show_error(f"An error occurred during import: {e}", title="Import Error")

    def export_to_csv(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV files", "*.csv")]
        )

        if not filepath:
            return

        rows = database.fetch_inventory(self.sort_column, self.sort_direction)

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Item Name', 'Current Stock', 'Low Stock Level',
                    'Purchase Price', 'Sale Price', 'Supplier', 'Location'
                ])
                writer.writerows(rows)

            Messagebox.show_info("Exported successfully!", "Success")

        except Exception as e:
            Messagebox.show_error(f"An error occurred: {e}", "Error")


    def open_sale_dialog(self):
        selected_item_id = self.tree.focus()
        if not selected_item_id:
            Messagebox.show_warning("Please select an item to sell.", title="Selection Error")
            return

        item_values = self.tree.item(selected_item_id, 'values')
        item_name = item_values[0]
        current_stock = int(item_values[1])
        low_stock = int(item_values[2])

        sale_dialog = tk.Toplevel(self)
        sale_dialog.title("Record Sale")
        sale_dialog.geometry("350x150")
        sale_dialog.transient(self)
        sale_dialog.grab_set()

        dialog_frame = ttk.Frame(sale_dialog, padding=15)
        dialog_frame.pack(fill='both', expand=True)

        ttk.Label(dialog_frame, text=f"Selling Item: {item_name}").pack(pady=5)
        ttk.Label(dialog_frame, text=f"(Current Stock: {current_stock})").pack()

        entry_frame = ttk.Frame(dialog_frame)
        entry_frame.pack(pady=10)

        ttk.Label(entry_frame, text="Quantity to Sell:").pack(side='left', padx=5)
        qty_entry = ttk.Entry(entry_frame, width=10)
        qty_entry.pack(side='left')
        qty_entry.focus()

        def process_sale():
            try:
                qty_to_sell = int(qty_entry.get())

                if qty_to_sell <= 0:
                    Messagebox.show_error("Quantity must be a positive number.", parent=sale_dialog)
                    return

                if qty_to_sell > current_stock:
                    Messagebox.show_error("Insufficient stock to complete sale.", parent=sale_dialog)
                    return

            except ValueError:
                Messagebox.show_error("Please enter a valid number.", parent=sale_dialog)
                return

            new_stock = current_stock - qty_to_sell
            database.update_stock_level(item_name, new_stock)
            database.log_change(item_name, 'SOLD', f"{qty_to_sell} units sold. Stock: {current_stock} -> {new_stock}.")

            sale_dialog.destroy()
            self.refresh_data()

            Messagebox.show_info(f"{qty_to_sell} units of '{item_name}' sold successfully.")
            self.check_and_notify(current_stock, new_stock, low_stock)

        button_frame = ttk.Frame(dialog_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Confirm Sale", command=process_sale, style="success.TButton").pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=sale_dialog.destroy).pack(side='left')


    def populate_treeview(self, rows):
        self.tree.delete(*self.tree.get_children())

        for row in rows:
            name, stock, low_stock, purchase_price, sale_price, supplier, location = row
            formatted_row = (
                name, stock, low_stock,
                f"{purchase_price:.2f}", f"{sale_price:.2f}",
                supplier, location
            )

            tags = ('low_stock_tag',) if stock <= low_stock else ()
            self.tree.insert('', 'end', values=formatted_row, tags=tags)

    def refresh_data(self):
        rows = database.fetch_inventory(self.sort_column, self.sort_direction, self.search_entry.get())
        self.populate_treeview(rows)
        self.update_dashboard()

    def sort_by_column(self, column):
        if self.sort_column == column:
            self.sort_direction = "desc" if self.sort_direction == "asc" else "asc"
        else:
            self.sort_column = column
            self.sort_direction = "asc"

        self.refresh_data()

    def search_items(self, event=None):
        self.refresh_data()

    def add_item(self):
        vals = {key: entry.get() for key, entry in self.entries.items()}

        if not all(vals.get(k) for k in ['item', 'stock', 'purchase_price', 'location']):
            Messagebox.show_error(
                "Name, Stock to Add, Purchase Price, and Location are required.",
                title="Input Error"
            )
            return

        try:
            stock_to_add = int(vals['stock'])
            purchase_price_new = float(vals['purchase_price'])
        except ValueError:
            Messagebox.show_error("Stock and Price must be valid numbers.", title="Input Error")
            return

        existing_item = database.fetch_item_by_name(vals['item'])

        if existing_item:
            _, _, current_stock, _, current_avg_price, _, _, _ = existing_item
            new_stock = current_stock + stock_to_add

            new_avg_price = (
                (current_stock * current_avg_price) + (stock_to_add * purchase_price_new)
            ) / new_stock

            database.add_stock_to_item(vals['item'], new_stock, new_avg_price)
            database.log_change(
                vals['item'], 'STOCK ADDED',
                f"{stock_to_add} units added. Stock: {current_stock} -> {new_stock}."
            )

            Messagebox.show_info(f"Updated stock for '{vals['item']}'.", title="Stock Updated")
            self.check_and_notify(current_stock, new_stock, int(vals['low_stock'] or current_stock))

        else:
            low_stock = int(vals['low_stock'] or 1)
            sale_price = float(vals['sale_price'] or purchase_price_new)

            new_item_vals = (
                vals['item'], stock_to_add, low_stock,
                purchase_price_new, sale_price, vals['supplier'], vals['location']
            )

            if database.insert_new_item(new_item_vals):
                database.log_change(vals['item'], 'CREATED', f"Item created with stock {stock_to_add}.")
                Messagebox.show_info(f"New item '{vals['item']}' added.", title="Item Added")
                self.check_and_notify(float('inf'), stock_to_add, low_stock)
            else:
                Messagebox.show_error(
                    f"An item with the name '{vals['item']}' already exists.",
                    title="Error"
                )

        self.clear_fields()
        self.refresh_data()

    def update_item(self):
        selected_item = self.tree.focus()
        if not selected_item:
            Messagebox.show_warning("Please select an item to update.", title="Selection Error")
            return

        old_values = self.tree.item(selected_item, 'values')
        original_name = old_values[0]
        old_stock = int(old_values[1])

        vals = {key: entry.get() for key, entry in self.entries.items()}

        if not vals['purchase_price'] or not vals['location']:
            Messagebox.show_error("Purchase Price and Location cannot be empty.", title="Input Error")
            return

        try:
            new_stock = int(vals['stock'])
            new_low_stock = int(vals['low_stock'])
            new_purchase_price = float(vals['purchase_price'])
            new_sale_price = float(vals['sale_price'] or 0.0)
        except ValueError:
            Messagebox.show_error("Stock and Price fields must be valid numbers.", title="Input Error")
            return

        details = []

        if old_stock != new_stock:
            details.append(f"Stock: {old_stock} -> {new_stock}")
        if int(old_values[2]) != new_low_stock:
            details.append(f"Low Stock: {old_values[2]} -> {new_low_stock}")
        if float(old_values[3]) != new_purchase_price:
            details.append(f"Purchase Price: {old_values[3]} -> {new_purchase_price:.2f}")
        if float(old_values[4]) != new_sale_price:
            details.append(f"Sale Price: {old_values[4]} -> {new_sale_price:.2f}")
        if old_values[5] != vals['supplier']:
            details.append(f"Supplier: '{old_values[5]}' -> '{vals['supplier']}'")
        if old_values[6] != vals['location']:
            details.append(f"Location: '{old_values[6]}' -> '{vals['location']}'")

        if details:
            database.log_change(original_name, 'UPDATED', "; ".join(details))

        database.update_item_details(
            original_name, new_stock, new_low_stock,
            new_purchase_price, new_sale_price,
            vals['supplier'], vals['location']
        )

        self.clear_fields()
        self.refresh_data()

        Messagebox.show_info(f"'{original_name}' updated.", "Success")
        self.check_and_notify(old_stock, new_stock, new_low_stock)

    def delete_item(self):
        selected_item = self.tree.focus()
        if not selected_item:
            Messagebox.show_warning("Please select an item to delete.", title="Selection Error")
            return

        item_name = self.tree.item(selected_item, 'values')[0]

        if Messagebox.yesno(
            f"Are you sure you want to delete '{item_name}'?",
            title="Confirm Delete"
        ) != 'Yes':
            return

        database.log_change(item_name, 'DELETED', "Item removed from inventory.")
        database.delete_item_by_name(item_name)

        self.clear_fields()
        self.refresh_data()

    def populate_fields_on_select(self, event):
        selected_item = self.tree.focus()
        if not selected_item:
            return

        self.clear_fields(clear_selection=False)
        item_values = self.tree.item(selected_item, 'values')

        entry_map = [
            'item', 'stock', 'low_stock',
            'purchase_price', 'sale_price',
            'supplier', 'location'
        ]

        for i, key in enumerate(entry_map):
            self.entries[key].insert(0, item_values[i])

        self.entries['item'].config(state='readonly')

    def clear_fields(self, clear_selection=True):
        self.entries['item'].config(state='normal')

        for entry in self.entries.values():
            entry.delete(0, 'end')

        self.search_entry.delete(0, 'end')

        if clear_selection:
            for selected_item in self.tree.selection():
                self.tree.selection_remove(selected_item)

        self.entries['item'].focus()

    def open_history_window(self):
        history_window = tk.Toplevel(self)
        history_window.title("History Log")
        history_window.geometry("900x500")
        history_window.grab_set()

        log_tree = ttk.Treeview(
            history_window,
            columns=('timestamp', 'item_name', 'action', 'details'),
            show='headings'
        )

        for col in log_tree['columns']:
            log_tree.heading(col, text=col.replace('_', ' ').title())

        log_tree.pack(fill='both', expand=True, padx=10, pady=10)

        rows = database.fetch_history_log()
        for row in rows:
            log_tree.insert('', 'end', values=row)

    def open_settings_window(self):
        settings_window = tk.Toplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("500x150")
        settings_window.grab_set()

        frame = ttk.Frame(settings_window, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Recipient Email:").grid(row=0, column=0, sticky='w')
        email_entry = ttk.Entry(frame, width=40)
        email_entry.grid(row=0, column=1, padx=5)

        email_entry.insert(0, database.get_setting("recipient_email"))

        def save():
            database.save_setting("recipient_email", email_entry.get())
            settings_window.destroy()

        ttk.Button(frame, text="Save", command=save, style='success.TButton').grid(row=1, column=1, sticky='e', pady=10)

 
    def check_and_notify(self, old_stock, new_stock, low_stock_level):
        if new_stock <= low_stock_level and old_stock > low_stock_level:
            success, message = database.send_low_stock_email()
            print(message)
            if not success:
                Messagebox.show_error(message, title="Email Notification Error")



if __name__ == "__main__":
    app = InventreeApp(themename="flatly")
    app.mainloop()

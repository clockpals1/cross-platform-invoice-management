# ---------------------------------------------
# BuildSmart Invoice System
# (c) 2025 Sunday AyoMI (Clockpals)
# All rights reserved. Signature: Sunday / Clockpals
# ---------------------------------------------

import sys
import os
import sqlite3
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QTextEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QSplitter
)
from PySide6.QtCore import Qt
from fpdf import FPDF

DB_PATH = "database/invoices.db"
OUTPUT_DIR = "output"
LOGO_PATH = "logo.png"

os.makedirs("database", exist_ok=True)
os.makedirs("output", exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Add missing columns if not present
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE,
                client_name TEXT,
                client_address TEXT,
                client_number TEXT,
                description TEXT,
                items TEXT,
                subtotal REAL,
                tax REAL,
                total REAL,
                email TEXT,
                company_name TEXT,
                company_address TEXT,
                company_contact TEXT,
                date_added TEXT,
                date TEXT
            )
        ''')
        # Try to add columns if they don't exist (for upgrades)
        for col, typ in [
            ("date_added", "TEXT"),
            ("date", "TEXT"),
            ("client_address", "TEXT"),
            ("client_number", "TEXT")
        ]:
            try:
                cursor.execute(f"ALTER TABLE invoices ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
        conn.commit()

class InvoiceForm(QDialog):
    def __init__(self, parent=None, prefill=None, edit_mode=False):
        super().__init__(parent)
        self.setWindowTitle("Edit Invoice" if edit_mode else "New Invoice")
        self.setMinimumSize(800, 700)
        self.prefill = prefill or {}
        self.edit_mode = edit_mode
        main_layout = QVBoxLayout()
        # Company Info
        self.company_name = QLineEdit(self.prefill.get("company_name", "BuildSmart Construction Inc."))
        self.company_address = QLineEdit(self.prefill.get("company_address", "123 Innovation Blvd, Suite 500"))
        self.company_contact = QLineEdit(self.prefill.get("company_contact", "Toronto, ON M1X 1A1 | (416) 555-0199 | info@buildsmart.ca"))
        for w, ph in [(self.company_name, "Company Name"),
                      (self.company_address, "Company Address"),
                      (self.company_contact, "Contact Info")]:
            w.setPlaceholderText(ph)
            main_layout.addWidget(w)
        # Invoice Info
        self.invoice_number = QLineEdit(self.prefill.get("invoice_number", ""))
        self.invoice_number.setPlaceholderText("Invoice Number")
        if edit_mode:
            self.invoice_number.setReadOnly(True)
        main_layout.addWidget(self.invoice_number)
        self.client_name = QLineEdit(self.prefill.get("client_name", ""))
        self.client_name.setPlaceholderText("Client Name")
        main_layout.addWidget(self.client_name)
        # Optional client address and number
        self.client_address = QLineEdit(self.prefill.get("client_address", ""))
        self.client_address.setPlaceholderText("Client Address (optional)")
        main_layout.addWidget(self.client_address)
        self.client_number = QLineEdit(self.prefill.get("client_number", ""))
        self.client_number.setPlaceholderText("Client Number (optional)")
        main_layout.addWidget(self.client_number)
        self.description = QTextEdit(self.prefill.get("description", ""))
        self.description.setPlaceholderText("Project Description")
        main_layout.addWidget(self.description)
        # Items Table
        self.table = QTableWidget(5, 3)
        self.table.setHorizontalHeaderLabels(["Description", "Qty", "Unit Price"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        main_layout.addWidget(self.table)
        # Add Item (+) Button
        add_item_btn = QPushButton("+ Add Item")
        add_item_btn.clicked.connect(self.add_item_row)
        main_layout.addWidget(add_item_btn)
        # Tax Rate and Total Display
        self.tax_input = QLineEdit(str(self.prefill.get("tax_rate", "0")))
        self.tax_input.setPlaceholderText("Tax Rate (%)")
        self.tax_input.textChanged.connect(self.update_total)
        main_layout.addWidget(self.tax_input)
        self.total_display = QLineEdit()
        self.total_display.setReadOnly(True)
        main_layout.addWidget(self.total_display)
        # Client Email
        self.email = QLineEdit(self.prefill.get("email", ""))
        self.email.setPlaceholderText("Client Email")
        main_layout.addWidget(self.email)
        # Date
        self.date = QLineEdit(self.prefill.get("date", datetime.date.today().strftime('%Y-%m-%d')))
        self.date.setPlaceholderText("Invoice Date (YYYY-MM-DD)")
        main_layout.addWidget(self.date)
        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save & Generate PDF" if not edit_mode else "Update & Generate PDF")
        self.save_button.clicked.connect(self.save_invoice)
        button_layout.addWidget(self.save_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        # Prefill items if any
        if "items" in self.prefill:
            items = eval(self.prefill["items"])
            self.table.setRowCount(len(items))
            for row, (desc, qty, price) in enumerate(items):
                self.table.setItem(row, 0, QTableWidgetItem(desc))
                self.table.setItem(row, 1, QTableWidgetItem(str(qty)))
                self.table.setItem(row, 2, QTableWidgetItem(str(price)))
        self.update_total()

    def add_item_row(self):
        self.table.insertRow(self.table.rowCount())

    def calculate_totals(self):
        subtotal = 0.0
        items = []
        for row in range(self.table.rowCount()):
            desc_item = self.table.item(row, 0)
            qty_item = self.table.item(row, 1)
            price_item = self.table.item(row, 2)
            if desc_item and qty_item and price_item:
                try:
                    qty = float(qty_item.text())
                    price = float(price_item.text())
                    total = qty * price
                    subtotal += total
                    items.append((desc_item.text(), qty, price))
                except ValueError:
                    continue

        try:
            tax_rate = float(self.tax_input.text() or 0)
        except ValueError:
            tax_rate = 0
        tax = subtotal * (tax_rate / 100)
        total = subtotal + tax
        return items, subtotal, tax, total

    def update_total(self):
        _, subtotal, tax, total = self.calculate_totals()
        self.total_display.setText(f"Total: ${total:.2f}")

    def save_invoice(self):
        number = self.invoice_number.text().strip()
        name = self.client_name.text().strip()
        client_address = self.client_address.text().strip()
        client_number = self.client_number.text().strip()
        desc = self.description.toPlainText().strip()
        email = self.email.text().strip()
        date = self.date.text().strip() or datetime.date.today().strftime('%Y-%m-%d')

        if not all([number, name, desc]):
            QMessageBox.warning(self, "Missing Info", "Please fill all required fields (Invoice Number, Client Name, Description).")
            return

        items, subtotal, tax, total = self.calculate_totals()
        if not items:
            QMessageBox.warning(self, "Missing Items", "Please add at least one valid item.")
            return
        items_str = str(items)

        company_name = self.company_name.text().strip()
        company_address = self.company_address.text().strip()
        company_contact = self.company_contact.text().strip()

        if self.edit_mode:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE invoices SET client_name=?, client_address=?, client_number=?, description=?, items=?, subtotal=?, tax=?, total=?, email=?, company_name=?, company_address=?, company_contact=?, date_added=?
                    WHERE invoice_number=?
                """, (name, client_address, client_number, desc, items_str, subtotal, tax, total, email, company_name, company_address, company_contact, date, number))
                conn.commit()
            self.generate_pdf(number, name, client_address, client_number, desc, items, subtotal, tax, total, company_name, company_address, company_contact, date)
            QMessageBox.information(self, "Updated", f"Invoice {number} updated successfully.")
            self.accept()
        else:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("INSERT INTO invoices (invoice_number, client_name, client_address, client_number, description, items, subtotal, tax, total, email, company_name, company_address, company_contact, date_added, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (number, name, client_address, client_number, desc, items_str, subtotal, tax, total, email, company_name, company_address, company_contact, now, date))
                    conn.commit()
                self.generate_pdf(number, name, client_address, client_number, desc, items, subtotal, tax, total, company_name, company_address, company_contact, date)
                QMessageBox.information(self, "Saved", f"Invoice {number} saved successfully.")
                self.accept()
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Duplicate", "Invoice number already exists.")

    def generate_pdf(self, number, name, client_address, client_number, desc, items, subtotal, tax, total, comp_name, comp_addr, comp_contact, date):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(32, 100, 106)
        pdf.cell(0, 10, comp_name, ln=1)
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, "Experts in earning trusts", ln=1)
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 6, comp_addr, ln=1)
        pdf.cell(0, 6, comp_contact, ln=1)
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 24)
        pdf.set_text_color(0, 136, 136)
        pdf.cell(0, 12, "INVOICE", ln=1, align='R')
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 6, f"INVOICE: {number}", ln=1, align='R')
        pdf.cell(0, 6, f"DATE: {date}", ln=1, align='R')
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, f"TO: {name}", ln=1)
        if client_address:
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 6, f"Address: {client_address}", ln=1)
        if client_number:
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 6, f"Number: {client_number}", ln=1)
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 6, self.email.text(), ln=1)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, f"FOR: {desc}", ln=1)
        pdf.ln(2)
        pdf.set_fill_color(230, 242, 242)
        pdf.set_text_color(32, 100, 106)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(80, 10, "DESCRIPTION", 1, 0, 'L', True)
        pdf.cell(30, 10, "QTY", 1, 0, 'C', True)
        pdf.cell(40, 10, "RATE", 1, 0, 'R', True)
        pdf.cell(40, 10, "AMOUNT", 1, 1, 'R', True)
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(34, 34, 34)
        for item, qty, price in items:
            total_item = qty * price
            pdf.cell(80, 10, str(item), 1)
            pdf.cell(30, 10, str(qty), 1, 0, 'C')
            pdf.cell(40, 10, f"${price:.2f}", 1, 0, 'R')
            pdf.cell(40, 10, f"${total_item:.2f}", 1, 1, 'R')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(150, 10, "Subtotal", 1)
        pdf.cell(40, 10, f"${subtotal:.2f}", 1, 1, 'R')
        pdf.cell(150, 10, "Tax", 1)
        pdf.cell(40, 10, f"${tax:.2f}", 1, 1, 'R')
        pdf.cell(150, 10, "Total", 1)
        pdf.cell(40, 10, f"${total:.2f}", 1, 1, 'R')
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 10, "THANK YOU FOR YOUR BUSINESS!", ln=1)
        pdf.output(os.path.join(OUTPUT_DIR, f"invoice_{number}.pdf"))

class InvoiceViewer(QDialog):
    def __init__(self, invoice_data, parent=None, dashboard_reload_callback=None):
        super().__init__(parent)
        self.setWindowTitle(f"Invoice Details - {invoice_data['invoice_number']}")
        self.setMinimumSize(700, 800)
        self.invoice_data = invoice_data
        self.dashboard_reload_callback = dashboard_reload_callback

        layout = QVBoxLayout()

        # Invoice Preview (HTML for professional look)
        from PySide6.QtWidgets import QTextEdit
        preview = QTextEdit()
        preview.setReadOnly(True)
        items_html = ""
        for desc, qty, price in eval(invoice_data['items']):
            total = qty * price
            items_html += f"<tr><td>{desc}</td><td align='center'>{qty}</td><td align='right'>${price:.2f}</td><td align='right'>${total:.2f}</td></tr>"
        # Add client address and number if present
        client_address_html = f"<br>{invoice_data.get('client_address','')}" if invoice_data.get('client_address') else ''
        client_number_html = f"<br>{invoice_data.get('client_number','')}" if invoice_data.get('client_number') else ''
        html = f"""
        <div style='font-family: Arial; color: #222;'>
        <table width='100%'><tr>
        <td><h2 style='color:#20646a;margin-bottom:0'>{invoice_data['company_name']}</h2>
        <span style='font-size:11px;font-style:italic;'>Experts in earning trusts</span><br>
        <span style='font-size:13px'>{invoice_data['company_address']}<br>{invoice_data['company_contact']}</span></td>
        <td align='right'><span style='font-size:32px;color:#008080;font-weight:bold;'>INVOICE</span><br><br>
        <b>INVOICE:</b> {invoice_data['invoice_number']}<br>
        <b>DATE:</b> {invoice_data.get('date', '')}
        </td></tr></table>
        <br>
        <table width='100%'><tr>
        <td valign='top'><b>TO:</b><br>{invoice_data['client_name']}{client_address_html}{client_number_html}<br>{invoice_data['email']}</td>
        <td valign='top'><b>FOR:</b><br>{invoice_data['description']}</td>
        </tr></table>
        <br>
        <table width='100%' border='1' cellspacing='0' cellpadding='4' style='border-collapse:collapse;'>
        <tr style='background:#e6f2f2;'><th align='left'>DESCRIPTION</th><th>QTY</th><th>RATE</th><th>AMOUNT</th></tr>
        {items_html}
        <tr><td colspan='3' align='right'><b>Subtotal</b></td><td align='right'>${invoice_data['subtotal']:.2f}</td></tr>
        <tr><td colspan='3' align='right'><b>Tax</b></td><td align='right'>${invoice_data['tax']:.2f}</td></tr>
        <tr><td colspan='3' align='right'><b>Total</b></td><td align='right'>${invoice_data['total']:.2f}</td></tr>
        </table>
        <br><br>
        <b>THANK YOU FOR YOUR BUSINESS!</b>
        </div>
        """
        preview.setHtml(html)
        layout.addWidget(preview)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.print_btn = QPushButton("Print / Export PDF")
        self.print_btn.clicked.connect(self.print_invoice)
        btn_layout.addWidget(self.print_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self.edit_invoice)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_invoice)
        btn_layout.addWidget(self.delete_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def print_invoice(self):
        # PDF output formatted to match the HTML preview
        items = eval(self.invoice_data['items'])
        number = self.invoice_data['invoice_number']
        name = self.invoice_data['client_name']
        desc = self.invoice_data['description']
        subtotal = self.invoice_data['subtotal']
        tax = self.invoice_data['tax']
        total = self.invoice_data['total']
        comp_name = self.invoice_data['company_name']
        comp_addr = self.invoice_data['company_address']
        comp_contact = self.invoice_data['company_contact']
        date = self.invoice_data.get('date', '')
        client_address = self.invoice_data.get('client_address', '')
        client_number = self.invoice_data.get('client_number', '')
        email = self.invoice_data.get('email', '')
        pdf = FPDF()
        pdf.add_page()
        # Header - Company Name
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(32, 100, 106)
        pdf.cell(0, 10, comp_name, ln=1)
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, "Experts in earning trusts", ln=1)
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 6, comp_addr, ln=1)
        pdf.cell(0, 6, comp_contact, ln=1)
        pdf.ln(2)
        # Invoice Header
        pdf.set_font("Arial", 'B', 24)
        pdf.set_text_color(0, 136, 136)
        pdf.cell(0, 12, "INVOICE", ln=1, align='R')
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 6, f"INVOICE: {number}", ln=1, align='R')
        pdf.cell(0, 6, f"DATE: {date}", ln=1, align='R')
        pdf.ln(2)
        # To/For
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, f"TO: {name}", ln=1)
        pdf.set_font("Arial", '', 12)
        if client_address:
            pdf.cell(0, 6, f"Address: {client_address}", ln=1)
        if client_number:
            pdf.cell(0, 6, f"Number: {client_number}", ln=1)
        if email:
            pdf.cell(0, 6, email, ln=1)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, f"FOR: {desc}", ln=1)
        pdf.ln(2)
        # Table header (colored)
        pdf.set_fill_color(230, 242, 242)
        pdf.set_text_color(32, 100, 106)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(80, 10, "DESCRIPTION", 1, 0, 'L', True)
        pdf.cell(30, 10, "QTY", 1, 0, 'C', True)
        pdf.cell(40, 10, "RATE", 1, 0, 'R', True)
        pdf.cell(40, 10, "AMOUNT", 1, 1, 'R', True)
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(34, 34, 34)
        for item, qty, price in items:
            total_item = qty * price
            pdf.cell(80, 10, str(item), 1)
            pdf.cell(30, 10, str(qty), 1, 0, 'C')
            pdf.cell(40, 10, f"${price:.2f}", 1, 0, 'R')
            pdf.cell(40, 10, f"${total_item:.2f}", 1, 1, 'R')
        # Subtotal, Tax, Total
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(150, 10, "Subtotal", 1)
        pdf.cell(40, 10, f"${subtotal:.2f}", 1, 1, 'R')
        pdf.cell(150, 10, "Tax", 1)
        pdf.cell(40, 10, f"${tax:.2f}", 1, 1, 'R')
        pdf.cell(150, 10, "Total", 1)
        pdf.cell(40, 10, f"${total:.2f}", 1, 1, 'R')
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 10, "THANK YOU FOR YOUR BUSINESS!", ln=1)
        pdf.output(os.path.join(OUTPUT_DIR, f"invoice_{number}_preview.pdf"))
        QMessageBox.information(self, "Exported", f"Invoice PDF exported as invoice_{number}_preview.pdf in output folder.")

    def edit_invoice(self):
        form = InvoiceForm(self, prefill=self.invoice_data, edit_mode=True)
        if form.exec() == QDialog.Accepted:
            if self.dashboard_reload_callback:
                self.dashboard_reload_callback()
            self.accept()

    def delete_invoice(self):
        reply = QMessageBox.question(self, "Delete", "Are you sure you want to delete this invoice?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM invoices WHERE id = ?", (self.invoice_data['id'],))
                conn.commit()
            QMessageBox.information(self, "Deleted", "Invoice deleted.")
            if self.dashboard_reload_callback:
                self.dashboard_reload_callback()
            self.accept()

class InvoiceForm(QDialog):
    def __init__(self, parent=None, prefill=None, edit_mode=False):
        super().__init__(parent)
        self.setWindowTitle("Edit Invoice" if edit_mode else "New Invoice")
        self.setMinimumSize(800, 700)
        self.prefill = prefill or {}
        self.edit_mode = edit_mode
        main_layout = QVBoxLayout()
        # Company Info
        self.company_name = QLineEdit(self.prefill.get("company_name", "BuildSmart Construction Inc."))
        self.company_address = QLineEdit(self.prefill.get("company_address", "123 Innovation Blvd, Suite 500"))
        self.company_contact = QLineEdit(self.prefill.get("company_contact", "Toronto, ON M1X 1A1 | (416) 555-0199 | info@buildsmart.ca"))
        for w, ph in [(self.company_name, "Company Name"),
                      (self.company_address, "Company Address"),
                      (self.company_contact, "Contact Info")]:
            w.setPlaceholderText(ph)
            main_layout.addWidget(w)
        # Invoice Info
        self.invoice_number = QLineEdit(self.prefill.get("invoice_number", ""))
        self.invoice_number.setPlaceholderText("Invoice Number")
        if edit_mode:
            self.invoice_number.setReadOnly(True)
        main_layout.addWidget(self.invoice_number)
        self.client_name = QLineEdit(self.prefill.get("client_name", ""))
        self.client_name.setPlaceholderText("Client Name")
        main_layout.addWidget(self.client_name)
        # Optional client address and number
        self.client_address = QLineEdit(self.prefill.get("client_address", ""))
        self.client_address.setPlaceholderText("Client Address (optional)")
        main_layout.addWidget(self.client_address)
        self.client_number = QLineEdit(self.prefill.get("client_number", ""))
        self.client_number.setPlaceholderText("Client Number (optional)")
        main_layout.addWidget(self.client_number)
        self.description = QTextEdit(self.prefill.get("description", ""))
        self.description.setPlaceholderText("Project Description")
        main_layout.addWidget(self.description)
        # Items Table
        self.table = QTableWidget(5, 3)
        self.table.setHorizontalHeaderLabels(["Description", "Qty", "Unit Price"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        main_layout.addWidget(self.table)
        # Add Item (+) Button
        add_item_btn = QPushButton("+ Add Item")
        add_item_btn.clicked.connect(self.add_item_row)
        main_layout.addWidget(add_item_btn)
        # Tax Rate and Total Display
        self.tax_input = QLineEdit(str(self.prefill.get("tax_rate", "0")))
        self.tax_input.setPlaceholderText("Tax Rate (%)")
        self.tax_input.textChanged.connect(self.update_total)
        main_layout.addWidget(self.tax_input)
        self.total_display = QLineEdit()
        self.total_display.setReadOnly(True)
        main_layout.addWidget(self.total_display)
        # Client Email
        self.email = QLineEdit(self.prefill.get("email", ""))
        self.email.setPlaceholderText("Client Email")
        main_layout.addWidget(self.email)
        # Date
        self.date = QLineEdit(self.prefill.get("date", datetime.date.today().strftime('%Y-%m-%d')))
        self.date.setPlaceholderText("Invoice Date (YYYY-MM-DD)")
        main_layout.addWidget(self.date)
        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save & Generate PDF" if not edit_mode else "Update & Generate PDF")
        self.save_button.clicked.connect(self.save_invoice)
        button_layout.addWidget(self.save_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        # Prefill items if any
        if "items" in self.prefill:
            items = eval(self.prefill["items"])
            self.table.setRowCount(len(items))
            for row, (desc, qty, price) in enumerate(items):
                self.table.setItem(row, 0, QTableWidgetItem(desc))
                self.table.setItem(row, 1, QTableWidgetItem(str(qty)))
                self.table.setItem(row, 2, QTableWidgetItem(str(price)))
        self.update_total()

    def add_item_row(self):
        self.table.insertRow(self.table.rowCount())

    def calculate_totals(self):
        subtotal = 0.0
        items = []
        for row in range(self.table.rowCount()):
            desc_item = self.table.item(row, 0)
            qty_item = self.table.item(row, 1)
            price_item = self.table.item(row, 2)
            if desc_item and qty_item and price_item:
                try:
                    qty = float(qty_item.text())
                    price = float(price_item.text())
                    total = qty * price
                    subtotal += total
                    items.append((desc_item.text(), qty, price))
                except ValueError:
                    continue

        try:
            tax_rate = float(self.tax_input.text() or 0)
        except ValueError:
            tax_rate = 0
        tax = subtotal * (tax_rate / 100)
        total = subtotal + tax
        return items, subtotal, tax, total

    def update_total(self):
        _, subtotal, tax, total = self.calculate_totals()
        self.total_display.setText(f"Total: ${total:.2f}")

    def save_invoice(self):
        number = self.invoice_number.text().strip()
        name = self.client_name.text().strip()
        client_address = self.client_address.text().strip()
        client_number = self.client_number.text().strip()
        desc = self.description.toPlainText().strip()
        email = self.email.text().strip()
        date = self.date.text().strip() or datetime.date.today().strftime('%Y-%m-%d')

        if not all([number, name, desc]):
            QMessageBox.warning(self, "Missing Info", "Please fill all required fields (Invoice Number, Client Name, Description).")
            return

        items, subtotal, tax, total = self.calculate_totals()
        if not items:
            QMessageBox.warning(self, "Missing Items", "Please add at least one valid item.")
            return
        items_str = str(items)

        company_name = self.company_name.text().strip()
        company_address = self.company_address.text().strip()
        company_contact = self.company_contact.text().strip()

        if self.edit_mode:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE invoices SET client_name=?, client_address=?, client_number=?, description=?, items=?, subtotal=?, tax=?, total=?, email=?, company_name=?, company_address=?, company_contact=?, date_added=?
                    WHERE invoice_number=?
                """, (name, client_address, client_number, desc, items_str, subtotal, tax, total, email, company_name, company_address, company_contact, date, number))
                conn.commit()
            self.generate_pdf(number, name, client_address, client_number, desc, items, subtotal, tax, total, company_name, company_address, company_contact, date)
            QMessageBox.information(self, "Updated", f"Invoice {number} updated successfully.")
            self.accept()
        else:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("INSERT INTO invoices (invoice_number, client_name, client_address, client_number, description, items, subtotal, tax, total, email, company_name, company_address, company_contact, date_added, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (number, name, client_address, client_number, desc, items_str, subtotal, tax, total, email, company_name, company_address, company_contact, now, date))
                    conn.commit()
                self.generate_pdf(number, name, client_address, client_number, desc, items, subtotal, tax, total, company_name, company_address, company_contact, date)
                QMessageBox.information(self, "Saved", f"Invoice {number} saved successfully.")
                self.accept()
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Duplicate", "Invoice number already exists.")

    def generate_pdf(self, number, name, client_address, client_number, desc, items, subtotal, tax, total, comp_name, comp_addr, comp_contact, date):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(32, 100, 106)
        pdf.cell(0, 10, comp_name, ln=1)
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, "Experts in earning trusts", ln=1)
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 6, comp_addr, ln=1)
        pdf.cell(0, 6, comp_contact, ln=1)
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 24)
        pdf.set_text_color(0, 136, 136)
        pdf.cell(0, 12, "INVOICE", ln=1, align='R')
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 6, f"INVOICE: {number}", ln=1, align='R')
        pdf.cell(0, 6, f"DATE: {date}", ln=1, align='R')
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, f"TO: {name}", ln=1)
        if client_address:
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 6, f"Address: {client_address}", ln=1)
        if client_number:
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 6, f"Number: {client_number}", ln=1)
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 6, self.email.text(), ln=1)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, f"FOR: {desc}", ln=1)
        pdf.ln(2)
        pdf.set_fill_color(230, 242, 242)
        pdf.set_text_color(32, 100, 106)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(80, 10, "DESCRIPTION", 1, 0, 'L', True)
        pdf.cell(30, 10, "QTY", 1, 0, 'C', True)
        pdf.cell(40, 10, "RATE", 1, 0, 'R', True)
        pdf.cell(40, 10, "AMOUNT", 1, 1, 'R', True)
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(34, 34, 34)
        for item, qty, price in items:
            total_item = qty * price
            pdf.cell(80, 10, str(item), 1)
            pdf.cell(30, 10, str(qty), 1, 0, 'C')
            pdf.cell(40, 10, f"${price:.2f}", 1, 0, 'R')
            pdf.cell(40, 10, f"${total_item:.2f}", 1, 1, 'R')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(150, 10, "Subtotal", 1)
        pdf.cell(40, 10, f"${subtotal:.2f}", 1, 1, 'R')
        pdf.cell(150, 10, "Tax", 1)
        pdf.cell(40, 10, f"${tax:.2f}", 1, 1, 'R')
        pdf.cell(150, 10, "Total", 1)
        pdf.cell(40, 10, f"${total:.2f}", 1, 1, 'R')
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(34, 34, 34)
        pdf.cell(0, 10, "THANK YOU FOR YOUR BUSINESS!", ln=1)
        pdf.output(os.path.join(OUTPUT_DIR, f"invoice_{number}.pdf"))

class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(900, 700)
        layout = QVBoxLayout()
        header_label = QLabel("<h1>Invoice Dashboard</h1>")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        # Search bar and buttons
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Invoice Number or Client Name")
        search_layout.addWidget(self.search_input)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.load_data)
        search_layout.addWidget(self.search_button)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_data)
        search_layout.addWidget(self.refresh_button)
        self.new_invoice_button = QPushButton("New Invoice")
        self.new_invoice_button.clicked.connect(self.open_new_invoice)
        search_layout.addWidget(self.new_invoice_button)
        layout.addLayout(search_layout)
        # Invoice table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Invoice Number", "Client Name", "Total", "Email", "Date Added", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.cellDoubleClicked.connect(self.open_invoice_details)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_data()

    def load_data(self):
        filter_text = self.search_input.text().strip().lower()
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if filter_text:
                cursor.execute("""
                    SELECT id, invoice_number, client_name, total, email, date_added, id
                    FROM invoices
                    WHERE LOWER(invoice_number) LIKE ? OR LOWER(client_name) LIKE ?
                    ORDER BY id DESC
                """, (f"%{filter_text}%", f"%{filter_text}%"))
            else:
                cursor.execute("""
                    SELECT id, invoice_number, client_name, total, email, date_added, id
                    FROM invoices
                    ORDER BY id DESC
                """)
            rows = cursor.fetchall()

        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, val in enumerate(row):
                if col_idx == 6:  # Actions column
                    action_widget = QWidget()
                    hbox = QHBoxLayout()
                    btn_view = QPushButton("View")
                    btn_view.clicked.connect(lambda _, r=row: self.open_invoice_details(row_idx, 0, r[0]))
                    btn_edit = QPushButton("Edit")
                    btn_edit.clicked.connect(lambda _, r=row: self.edit_invoice(r[0]))
                    btn_delete = QPushButton("Delete")
                    btn_delete.clicked.connect(lambda _, r=row: self.delete_invoice(r[0]))
                    hbox.addWidget(btn_view)
                    hbox.addWidget(btn_edit)
                    hbox.addWidget(btn_delete)
                    hbox.setContentsMargins(0, 0, 0, 0)
                    action_widget.setLayout(hbox)
                    self.table.setCellWidget(row_idx, col_idx, action_widget)
                else:
                    item = QTableWidgetItem(str(val))
                    if col_idx == 3:  # Total column currency formatting
                        item.setText(f"${val:.2f}")
                    if col_idx == 5 and val:
                        # Date Added column, show date and time
                        try:
                            dt = datetime.datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
                            item.setText(dt.strftime('%Y-%m-%d %H:%M:%S'))
                        except Exception:
                            item.setText(str(val))
                    self.table.setItem(row_idx, col_idx, item)

    def open_invoice_details(self, row, column, invoice_id=None):
        if invoice_id is None:
            invoice_id = int(self.table.item(row, 0).text())
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
            data = cursor.fetchone()
            if not data:
                QMessageBox.warning(self, "Not Found", "Invoice not found in database.")
                return
            invoice_data = {
                "id": data[0],
                "invoice_number": data[1],
                "client_name": data[2],
                "description": data[3],
                "items": data[4],
                "subtotal": data[5],
                "tax": data[6],
                "total": data[7],
                "email": data[8],
                "company_name": data[9],
                "company_address": data[10],
                "company_contact": data[11]
            }
        viewer = InvoiceViewer(invoice_data, self, dashboard_reload_callback=self.load_data)
        viewer.exec()

    def open_new_invoice(self):
        form = InvoiceForm(self)
        if form.exec() == QDialog.Accepted:
            self.load_data()

    def edit_invoice(self, invoice_id):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
            data = cursor.fetchone()
            if not data:
                QMessageBox.warning(self, "Not Found", "Invoice not found in database.")
                return
            invoice_data = {
                "id": data[0],
                "invoice_number": data[1],
                "client_name": data[2],
                "description": data[3],
                "items": data[4],
                "subtotal": data[5],
                "tax": data[6],
                "total": data[7],
                "email": data[8],
                "company_name": data[9],
                "company_address": data[10],
                "company_contact": data[11]
            }
        form = InvoiceForm(self, prefill=invoice_data, edit_mode=True)
        if form.exec() == QDialog.Accepted:
            self.load_data()

    def delete_invoice(self, invoice_id):
        reply = QMessageBox.question(self, "Delete", "Are you sure you want to delete this invoice?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
                conn.commit()
            QMessageBox.information(self, "Deleted", "Invoice deleted.")
            self.load_data()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BuildSmart Invoice System - Dashboard")
        self.setMinimumSize(900, 700)

        self.dashboard = DashboardWidget()
        self.setCentralWidget(self.dashboard)

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

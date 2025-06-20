# BuildSmart Invoice System

(c) 2025 Sunday AyoMI (Clockpals)

## About
BuildSmart Invoice System is a professional, cross-platform desktop application for managing, generating, and exporting invoices. It is built with Python, PySide6 (Qt for Python), and FPDF for PDF generation. The app is suitable for small businesses and freelancers who need a simple, robust, and modern invoicing solution.

## Features
- Create, edit, and delete invoices
- Add unlimited items per invoice
- Optional client address and client number fields
- Professional invoice preview and PDF export
- Dashboard with search and filtering
- Data stored in a local SQLite database (no internet required)
- Cross-platform: Windows and Mac (see below for packaging)

## How to Use
1. **Install Requirements**
   - Install Python 3.8+
   - Install dependencies:
     ```
     pip install -r requirements.txt
     ```
2. **Run the App**
   - On Windows/Mac/Linux:
     ```
     python main.py
     ```
3. **Create Invoices**
   - Click "New Invoice" on the dashboard
   - Fill in company, client, and item details
   - Add more items with the "+ Add Item" button
   - Save to generate a PDF and store in the output folder
4. **Edit/Delete Invoices**
   - Use the dashboard to view, edit, or delete any invoice

## Packaging (Windows)
- To build a standalone .exe:
  ```
  pip install pyinstaller
  pyinstaller --noconfirm --onefile --windowed main.py
  ```
- The executable will be in the `dist` folder.

## Packaging (Mac)
- On a Mac, use PyInstaller or py2app:
  ```
  pip install pyinstaller
  pyinstaller --noconfirm --onefile --windowed main.py
  ```
- For a .dmg, use `create-dmg` or similar tools after building.

## Notes
- All data is stored locally in `database/invoices.db`.
- PDFs are saved in the `output` folder.
- The app will create required folders on first run.

---
**Signature:** Sunday / Clockpals

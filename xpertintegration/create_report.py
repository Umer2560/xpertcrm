import frappe

def create_report():
    report_name = "Unpaid Sales Invoices"
    if not frappe.db.exists("Report", report_name):
        doc = frappe.get_doc({
            "doctype": "Report",
            "report_name": report_name,
            "ref_doctype": "Sales Invoice",
            "report_type": "Script Report",
            "is_standard": "Yes",
            "module": "xpertintegration"
        })
        doc.insert(ignore_permissions=True)
        print(f"Report '{report_name}' created successfully.")
    else:
        print(f"Report '{report_name}' already exists.")

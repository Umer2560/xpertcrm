import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "invoice_id",
            "label": _("Invoice ID"),
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 150
        },
        {
            "fieldname": "customer",
            "label": _("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "width": 150
        },
        {
            "fieldname": "customer_name",
            "label": _("Customer Name"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "posting_date",
            "label": _("Posting Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "due_date",
            "label": _("Due Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "days_overdue",
            "label": _("Days Overdue"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "grand_total",
            "label": _("Grand Total"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120
        },
        {
            "fieldname": "outstanding_amount",
            "label": _("Outstanding Amount"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120
        },
        {
            "fieldname": "currency",
            "label": _("Currency"),
            "fieldtype": "Data",
            "hidden": 1
        },
        {
            "fieldname": "project",
            "label": _("Project"),
            "fieldtype": "Link",
            "options": "Project",
            "width": 120
        },
        {
            "fieldname": "has_draft_payment",
            "label": _("Has Draft Payment"),
            "fieldtype": "Data",
            "width": 140
        }
    ]

def get_data(filters):
    if not filters: filters = {}
    conditions = get_conditions(filters)
    
    query = f"""
        SELECT
            si.name as invoice_id,
            si.customer,
            si.customer_name,
            si.posting_date,
            si.due_date,
            DATEDIFF(CURDATE(), si.due_date) as days_overdue,
            si.grand_total,
            si.outstanding_amount,
            si.currency,
            si.project,
            IF(
                (
                    SELECT pe.name 
                    FROM `tabPayment Entry Reference` per 
                    JOIN `tabPayment Entry` pe ON pe.name = per.parent 
                    WHERE per.reference_doctype = 'Sales Invoice' 
                      AND per.reference_name = si.name 
                      AND pe.docstatus = 0 
                    LIMIT 1
                ) IS NOT NULL, 
                'Yes', 'No'
            ) as has_draft_payment
        FROM 
            `tabSales Invoice` si
        WHERE 
            si.docstatus = 1 
            AND si.status NOT IN ('Paid', 'Cancelled')
            AND si.outstanding_amount > 0
            {conditions}
        ORDER BY 
            si.due_date ASC
    """
    
    return frappe.db.sql(query, filters, as_dict=1)

def get_conditions(filters):
    conditions = ""
    if filters.get("customer"):
        conditions += " AND si.customer = %(customer)s"
    if filters.get("project"):
        conditions += " AND si.project = %(project)s"
    if filters.get("exclude_draft_payments"):
        conditions += " AND (SELECT pe.name FROM `tabPayment Entry Reference` per JOIN `tabPayment Entry` pe ON pe.name = per.parent WHERE per.reference_doctype = 'Sales Invoice' AND per.reference_name = si.name AND pe.docstatus = 0 LIMIT 1) IS NULL"
    return conditions

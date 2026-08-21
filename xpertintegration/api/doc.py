import json
import frappe
from frappe import _
from frappe.model.document import get_controller
from crm.api.doc import get_data as original_get_data

@frappe.whitelist()
def custom_get_data(
	doctype: str,
	filters: dict = None,
	order_by: str = "modified desc",
	page_length: int = 20,
	page_length_count: int = 20,
	column_field: str | None = None,
	title_field: str | None = None,
	columns: str | list | None = None,
	rows: str | list | None = None,
	kanban_columns: str | list | None = None,
	kanban_fields: str | list | None = None,
	view: str | dict | None = None,
	default_filters: dict | None = None,
):
	"""Override for crm.api.doc.get_data to support Customer and Subscription and custom columns safely."""
	_list = get_controller(doctype)
	if not hasattr(_list, "default_list_data") and (not columns or not rows):
		if doctype == "Customer":
			if not columns:
				columns = json.dumps([
					{"label": _("Name"), "type": "Data", "key": "name", "width": "12rem"},
					{"label": _("Customer Name"), "type": "Data", "key": "customer_name", "width": "15rem"},
					{"label": _("Customer Group"), "type": "Link", "key": "customer_group", "width": "12rem"},
					{"label": _("Territory"), "type": "Link", "key": "territory", "width": "12rem"},
					{"label": _("Mobile No"), "type": "Data", "key": "mobile_no", "width": "11rem"},
					{"label": _("Email ID"), "type": "Data", "key": "email_id", "width": "13rem"},
					{"label": _("Company Code"), "type": "Data", "key": "custom_company_code", "width": "12rem"},
					{"label": _("Last Modified"), "type": "Datetime", "key": "modified", "width": "10rem"},
				])
			if not rows:
				rows = json.dumps(["name", "customer_name", "customer_group", "territory", "mobile_no", "email_id", "custom_company_code", "modified"])
		elif doctype == "Subscription":
			if not columns:
				columns = json.dumps([
					{"label": _("Subscription ID"), "type": "Data", "key": "name", "width": "14rem"},
					{"label": _("Party"), "type": "Link", "key": "party", "width": "14rem"},
					{"label": _("Status"), "type": "Select", "key": "status", "width": "10rem"},
					{"label": _("Start Date"), "type": "Date", "key": "start_date", "width": "10rem"},
					{"label": _("End Date"), "type": "Date", "key": "end_date", "width": "10rem"},
					{"label": _("Custom Cost"), "type": "Currency", "key": "custom_cost", "width": "11rem"},
					{"label": _("Custom Amount Paid"), "type": "Currency", "key": "custom_amount_paid", "width": "13rem"},
					{"label": _("Last Modified"), "type": "Datetime", "key": "modified", "width": "10rem"},
				])
			if not rows:
				rows = json.dumps(["name", "party", "status", "start_date", "end_date", "custom_cost", "custom_amount_paid", "modified"])
		else:
			if not columns:
				columns = json.dumps([
					{"label": _("Name"), "type": "Data", "key": "name", "width": "16rem"},
					{"label": _("Last Modified"), "type": "Datetime", "key": "modified", "width": "8rem"},
				])
			if not rows:
				rows = json.dumps(["name", "modified"])

	return original_get_data(
		doctype=doctype,
		filters=filters,
		order_by=order_by,
		page_length=page_length,
		page_length_count=page_length_count,
		column_field=column_field,
		title_field=title_field,
		columns=columns,
		rows=rows,
		kanban_columns=kanban_columns,
		kanban_fields=kanban_fields,
		view=view,
		default_filters=default_filters,
	)

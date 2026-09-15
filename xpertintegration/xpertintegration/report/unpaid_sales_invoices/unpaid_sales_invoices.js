frappe.query_reports["Unpaid Sales Invoices"] = {
	"filters": [
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Project"
		},
		{
			"fieldname": "exclude_draft_payments",
			"label": __("Exclude Draft Payments"),
			"fieldtype": "Check",
			"default": 1
		}
	],
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname == "days_overdue" && data && data.days_overdue > 0) {
			value = "<span style='color:red'>" + value + "</span>";
		}
		if (column.fieldname == "has_draft_payment" && data && data.has_draft_payment == "Yes") {
			value = "<span style='color:green'>" + value + "</span>";
		}
		return value;
	}
};

frappe.ui.form.on('CRM Deal', {
	refresh: function(frm) {
		make_fields_editable_on_won(frm);
		add_rerun_billing_button(frm);
	},
	status: function(frm) {
		make_fields_editable_on_won(frm);
		add_rerun_billing_button(frm);
	},
	custom_sale_price: function(frm) {
		add_rerun_billing_button(frm);
	},
	custom_paid_amount: function(frm) {
		add_rerun_billing_button(frm);
	}
});

function make_fields_editable_on_won(frm) {
	if (frm.doc.status === 'Won') {
		frm.set_df_property('custom_paid_amount', 'read_only', 0);
		frm.set_df_property('custom_sale_price', 'read_only', 0);
	}
}

function add_rerun_billing_button(frm) {
	if (frm.is_new() || frm.doc.status !== 'Won') {
		frm.remove_custom_button(__('Re-run Billing Process'));
		return;
	}

	frappe.call({
		method: 'xpertintegration.api.integration.check_deal_billing_status',
		args: { deal_name: frm.doc.name },
		callback: function(r) {
			frm.remove_custom_button(__('Re-run Billing Process'));
			if (r.message && r.message.should_show_rerun) {
				var sale_price = flt(frm.doc.custom_sale_price || frm.doc.custom_amount);
				var paid_amount = flt(frm.doc.custom_paid_amount);

				frm.add_custom_button(__('Re-run Billing Process'), function() {
					frappe.confirm(
						__('This will cancel existing Subscriptions, Sales Invoices, and Payment Entries for this deal and re-create them with Sale Price {0} and Paid Amount {1}. Are you sure you want to continue?', [format_currency(sale_price), format_currency(paid_amount)]),
						function() {
							frappe.call({
								method: 'xpertintegration.api.integration.rerun_deal_subscription_process',
								args: {
									deal_name: frm.doc.name
								},
								freeze: true,
								freeze_message: __('Re-running Subscription, Sales Invoice, and Payment Entry creation...'),
								callback: function(res) {
									if (res.message) {
										frappe.msgprint({
											title: __('Billing Process Re-run Completed'),
											indicator: 'green',
											message: res.message
										});
										frm.reload_doc();
									}
								}
							});
						}
					);
				}).addClass('btn-warning');
			}
		}
	});
}

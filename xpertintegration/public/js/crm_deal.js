frappe.ui.form.on('CRM Deal', {
	refresh: function (frm) {
		make_fields_editable_on_won(frm);
		add_rerun_billing_button(frm);

		if (frm.doc.custom_fetch_company) {
			frm.add_custom_button(__('Fetch Company Data'), function () {
				trigger_fetch_company_details(frm);
			}, __('Actions'));
		}
	},
	status: function (frm) {
		make_fields_editable_on_won(frm);
		add_rerun_billing_button(frm);
	},
	custom_sale_price: function (frm) {
		add_rerun_billing_button(frm);
	},
	custom_paid_amount: function (frm) {
		add_rerun_billing_button(frm);
	},
	custom_fetch_company: function (frm) {
		frm.toggle_display(['custom_company_code', 'custom_project', 'deal_owner', 'custom_activation_start_date', 'custom_activation_end_date', 'status'], !!frm.doc.custom_fetch_company);
		if (frm.doc.custom_fetch_company) {
			frappe.show_alert({
				message: __('Enter Company Code and Project, then click "Fetch Company Data" or Save.'),
				indicator: 'blue'
			});
		}
	}
});

function trigger_fetch_company_details(frm) {
	if (!frm.doc.custom_company_code || !frm.doc.custom_project) {
		frappe.msgprint(__('Please enter both Company Code and Project before fetching details.'));
		return;
	}

	frappe.call({
		method: 'xpertintegration.api.integration.fetch_company_details_from_project',
		args: {
			company_code: frm.doc.custom_company_code,
			custom_company_code: frm.doc.custom_company_code,
			project: frm.doc.custom_project,
		},
		freeze: true,
		freeze_message: __('Fetching Company Details from Project...'),
		callback: function (r) {
			if (r && r.message && r.message.status === 'success') {
				frappe.show_alert({
					message: r.message.message || __('Company details fetched successfully!'),
					indicator: 'green'
				});
				var data = r.message.data || {};
				const fieldAliases = {
					sub_domain: 'custom_sub_domain',
					username: 'custom_username',
					password: 'custom_password',
					plan: 'custom_plan',
					project: 'custom_project',
					city: 'custom_city',
					mobile: 'mobile_no',
					company_name: 'organization',
					company: 'organization'
				};

				for (const [key, val] of Object.entries(data)) {
					if (val === null || val === undefined) continue;
					const targetKey = fieldAliases[key] || key;
					if (key === 'custom_addons_table' && Array.isArray(val)) {
						frm.set_value('custom_addons_table', val);
					} else if (typeof val !== 'object' && frm.fields_dict[targetKey]) {
						frm.set_value(targetKey, val);
					}
				}
				if (data.organization || data.company_name || data.name || data.company) {
					frm.set_value('organization', data.organization || data.company_name || data.name || data.company);
				}

				if (!frm.is_new()) {
					frm.save();
				}
			}
		}
	});
}

function make_fields_editable_on_won(frm) {
	if (frm.doc.status === 'Won' && !frm.is_new()) {
		frappe.call({
			method: 'xpertintegration.api.integration.check_deal_billing_status',
			args: { deal_name: frm.doc.name },
			callback: function (r) {
				var editable = (r.message && r.message.should_show_rerun) ? 0 : 1;

				const financial_fields = [
					'custom_paid_amount',
					'custom_sale_price',
					'custom_reference_number',
					'custom_payment_date'
				];

				frm.meta.fields.forEach(function (df) {
					if (!df.fieldname) return;
					if (financial_fields.includes(df.fieldname)) {
						frm.set_df_property(df.fieldname, 'read_only', editable);
					} else {
						frm.set_df_property(df.fieldname, 'read_only', 1);
					}
				});
			}
		});
	} else {
		frm.meta.fields.forEach(function (df) {
			if (!df.fieldname) return;
			frm.set_df_property(df.fieldname, 'read_only', df.read_only || 0);
		});
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
		callback: function (r) {
			frm.remove_custom_button(__('Re-run Billing Process'));
			if (r.message && r.message.should_show_rerun) {
				var sale_price = flt(frm.doc.custom_sale_price || frm.doc.custom_amount);
				var paid_amount = flt(frm.doc.custom_paid_amount);

				frm.add_custom_button(__('Re-run Billing Process'), function () {
					frappe.confirm(
						__('This will cancel existing Subscriptions, Sales Invoices, and Payment Entries for this deal and re-create them with Sale Price {0} and Paid Amount {1}. Are you sure you want to continue?', [format_currency(sale_price), format_currency(paid_amount)]),
						function () {
							frappe.call({
								method: 'xpertintegration.api.integration.rerun_deal_subscription_process',
								args: {
									deal_name: frm.doc.name
								},
								freeze: true,
								freeze_message: __('Re-running Subscription, Sales Invoice, and Payment Entry creation...'),
								callback: function (res) {
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

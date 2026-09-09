frappe.pages['sales-invoice-payment-entry'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Sales Invoice Payment Entry',
		single_column: true
	});

	frappe.require('sales_invoice_payment_entry.css');
	wrapper.sales_invoice_payment_page = new SalesInvoicePaymentEntryPage(wrapper);
};

class SalesInvoicePaymentEntryPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper).find('.layout-main-section');
		this.page = wrapper.page;
		this.active_tab = 'pending'; // 'pending' | 'drafts'
		this.current_page = 1;
		this.page_size = 10;
		this.pending_data = [];
		this.drafts_data = [];
		this.controls = {};
		this.filter_controls = {};
		this.filters = {
			customer: null,
			project: null,
			search_term: null,
			status: null
		};

		this.init_layout();
		this.load_data();
	}

	init_layout() {
		this.wrapper.html(`
			<div class="sales-invoice-payment-wrapper">
				<!-- Header Stats Cards -->
				<div class="uip-stats-row">
					<div class="uip-stat-card">
						<div class="uip-stat-icon">
							<i class="fa fa-file-text-o"></i>
						</div>
						<div>
							<div class="uip-stat-value" id="uip-stat-count">0</div>
							<div class="uip-stat-label" id="uip-stat-count-label">Pending Invoices</div>
						</div>
					</div>

					<div class="uip-stat-card uip-stat-alert">
						<div class="uip-stat-icon">
							<i class="fa fa-money"></i>
						</div>
						<div>
							<div class="uip-stat-value" id="uip-stat-amount">PKR 0.00</div>
							<div class="uip-stat-label" id="uip-stat-amount-label">Total Outstanding</div>
						</div>
					</div>
				</div>

				<!-- Navigation Tabs -->
				<ul class="nav nav-tabs uip-nav-tabs mb-4" id="uip-nav-tabs">
					<li class="nav-item">
						<a class="nav-link active" id="tab-pending-btn" data-tab="pending" href="javascript:void(0)">
							<i class="fa fa-file-text-o mr-1"></i> Pending Invoices
							<span class="badge badge-pill badge-primary ml-1" id="uip-badge-pending-count">0</span>
						</a>
					</li>
					<li class="nav-item">
						<a class="nav-link" id="tab-drafts-btn" data-tab="drafts" href="javascript:void(0)">
							<i class="fa fa-pencil-square-o mr-1"></i> Draft Payment Entries
							<span class="badge badge-pill badge-warning text-dark ml-1" id="uip-badge-drafts-count">0</span>
						</a>
					</li>
				</ul>

				<!-- Filter Card -->
				<div class="uip-filter-card mb-4 p-3 bg-white border rounded-lg shadow-sm" style="border-radius: 12px;">
					<div class="form-row align-items-end">
						<div class="col-md-3 col-sm-6 mb-2">
							<label class="uip-filter-label">
								<i class="fa fa-building-o mr-1 text-muted"></i> Customer / Company
							</label>
							<div id="uip-filter-customer"></div>
						</div>

						<div class="col-md-3 col-sm-6 mb-2">
							<label class="uip-filter-label">
								<i class="fa fa-folder-open mr-1 text-muted"></i> Project
							</label>
							<div id="uip-filter-project"></div>
						</div>

						<div class="col-md-2 col-sm-6 mb-2" id="uip-filter-status-col">
							<label class="uip-filter-label">
								<i class="fa fa-info-circle mr-1 text-muted"></i> Status
							</label>
							<select id="uip-filter-status" class="form-control" style="height: 28px; border-radius: 8px; margin-bottom: 0.5rem">
								<option value="">All</option>
								<option value="Unpaid">Unpaid</option>
								<option value="Overdue">Overdue</option>
								<option value="Partially Paid">Partially Paid</option>
								<option value="Paid">Paid</option>
								<option value="Cancelled">Cancelled</option>
							</select>
						</div>

						<div class="col-md-3 col-sm-6 mb-2">
							<label class="uip-filter-label">
								<i class="fa fa-search mr-1 text-muted"></i> Search Invoice / Customer
							</label>
							<input type="text" id="uip-filter-search" class="form-control" placeholder="Search name or ID..." style="height: 28px; border-radius: 8px; margin-bottom: 0.5rem" />
						</div>

						<div class="col-md-1 col-sm-12 text-right mb-2">
							<button class="btn btn-sm btn-light border btn-reset-filters" style="height: 28px; border-radius: 8px; font-weight: 600; width: 100%; padding: 0; margin-bottom: 0.5rem">
								<i class="fa fa-refresh"></i> Reset
							</button>
						</div>
					</div>
				</div>

				<!-- Card Body Container -->
				<div id="uip-body">
					<div class="text-center py-5 text-muted">
						<i class="fa fa-spinner fa-spin fa-2x mb-2"></i>
						<div>Loading data...</div>
					</div>
				</div>
			</div>
		`);

		this.setup_tabs();
		this.setup_filters();
	}

	setup_tabs() {
		let me = this;
		this.wrapper.find('#uip-nav-tabs .nav-link').off('click').on('click', function (e) {
			e.preventDefault();
			let selected_tab = $(this).attr('data-tab');
			if (selected_tab !== me.active_tab) {
				me.active_tab = selected_tab;
				me.wrapper.find('#uip-nav-tabs .nav-link').removeClass('active');
				$(this).addClass('active');
				if (me.active_tab === 'pending') {
					me.wrapper.find('#uip-filter-status-col').show();
				} else {
					me.wrapper.find('#uip-filter-status-col').hide();
				}
				me.current_page = 1;
				me.update_stats();
				me.render_page();
			}
		});
	}

	setup_filters() {
		let me = this;

		// Customer Link Control
		let cust_control = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Customer',
				fieldname: 'customer',
				placeholder: 'Select Customer...',
				change: () => {
					let val = cust_control.get_value();
					if (val !== me.filters.customer) {
						me.filters.customer = val;
						me.load_data();
					}
				}
			},
			parent: this.wrapper.find('#uip-filter-customer'),
			only_input: true
		});
		cust_control.make_input();
		this.filter_controls.customer = cust_control;

		// Project Link Control
		let proj_control = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Project',
				fieldname: 'project',
				placeholder: 'Select Project...',
				change: () => {
					let val = proj_control.get_value();
					if (val !== me.filters.project) {
						me.filters.project = val;
						me.load_data();
					}
				}
			},
			parent: this.wrapper.find('#uip-filter-project'),
			only_input: true
		});
		proj_control.make_input();
		this.filter_controls.project = proj_control;

		// Status Select Filter
		let status_select = this.wrapper.find('#uip-filter-status');
		status_select.off('change').on('change', function () {
			me.filters.status = $(this).val();
			me.load_data();
		});

		// Search Input Filter
		let search_input = this.wrapper.find('#uip-filter-search');
		let timer = null;
		search_input.on('keyup input', function () {
			clearTimeout(timer);
			timer = setTimeout(() => {
				me.filters.search_term = $(this).val();
				me.load_data();
			}, 400);
		});

		// Reset Button
		this.wrapper.find('.btn-reset-filters').off('click').on('click', function () {
			me.filters = { customer: null, project: null, search_term: null, status: null };
			cust_control.set_value('');
			proj_control.set_value('');
			status_select.val('');
			search_input.val('');
			me.load_data();
		});
	}

	load_data() {
		let me = this;

		frappe.call({
			method: 'xpertintegration.xpertintegration.page.sales_invoice_payment_entry.sales_invoice_payment_entry.get_unlinked_sales_invoices',
			args: {
				customer: me.filters.customer,
				project: me.filters.project,
				search_term: me.filters.search_term,
				status: me.filters.status
			},
			callback: (r) => {
				me.pending_data = r.message || [];
				me.wrapper.find('#uip-badge-pending-count').text(me.pending_data.length);

				// Load Drafts
				frappe.call({
					method: 'xpertintegration.xpertintegration.page.sales_invoice_payment_entry.sales_invoice_payment_entry.get_draft_payment_entries',
					args: {
						customer: me.filters.customer,
						project: me.filters.project,
						search_term: me.filters.search_term
					},
					callback: (r2) => {
						me.drafts_data = r2.message || [];
						me.wrapper.find('#uip-badge-drafts-count').text(me.drafts_data.length);

						me.update_stats();
						me.render_page();
					}
				});
			}
		});
	}

	update_stats() {
		let is_pending = (this.active_tab === 'pending');
		let dataset = is_pending ? this.pending_data : this.drafts_data;
		let total_count = dataset.length;

		let total_amount = dataset.reduce((acc, row) => {
			let amt = is_pending ? (row.outstanding_amount || 0) : (row.paid_amount || 0);
			return acc + amt;
		}, 0);

		let currency = (dataset[0] && dataset[0].currency) || frappe.boot.sysdefaults.currency || 'PKR';

		this.wrapper.find('#uip-stat-count').text(total_count);
		this.wrapper.find('#uip-stat-count-label').text(is_pending ? 'Pending Invoices' : 'Draft Payment Entries');
		this.wrapper.find('#uip-stat-amount').text(format_currency(total_amount, currency));
		this.wrapper.find('#uip-stat-amount-label').text(is_pending ? 'Total Outstanding' : 'Total Draft Amount');
	}

	render_page() {
		let is_pending = (this.active_tab === 'pending');
		let dataset = is_pending ? this.pending_data : this.drafts_data;

		let start = (this.current_page - 1) * this.page_size;
		let end = start + this.page_size;
		let page_data = dataset.slice(start, end);
		let total_pages = Math.ceil(dataset.length / this.page_size);

		this.controls = {};

		let template_name = is_pending ? 'sales_invoice_payment_entry' : 'sales_invoice_payment_entry_drafts';

		let html = frappe.render_template(template_name, {
			data: page_data,
			current_page: this.current_page,
			total_pages: total_pages,
			total_records: dataset.length
		});

		this.wrapper.find('#uip-body').html(html);

		if (is_pending) {
			this.bind_pending_card_controls();
		} else {
			this.bind_drafts_card_controls();
		}

		this.bind_pagination();
	}

	bind_pending_card_controls() {
		let me = this;

		this.wrapper.find('.uip-card').each(function () {
			let card = $(this);
			let name = card.attr('data-name');
			me.controls[name] = {};

			// Mode of Payment Control
			let mop_wrapper = card.find('.uip-mop-control');
			let mop_control = frappe.ui.form.make_control({
				df: {
					fieldtype: 'Link',
					options: 'Mode of Payment',
					fieldname: 'mode_of_payment',
					placeholder: 'Select Mode of Payment...',
					hidden: 0
				},
				parent: mop_wrapper,
				only_input: true
			});
			mop_control.make_input();
			me.controls[name].mop = mop_control;

			// Account Paid To Control
			let apt_wrapper = card.find('.uip-apt-control');
			let apt_control = frappe.ui.form.make_control({
				df: {
					fieldtype: 'Link',
					options: 'Account',
					fieldname: 'account_paid_to',
					placeholder: 'Select Bank/Cash Account...',
					hidden: 0,
					get_query: function () {
						return {
							filters: {
								is_group: 0,
								account_type: ['in', ['Bank', 'Cash']]
							}
						};
					}
				},
				parent: apt_wrapper,
				only_input: true
			});
			apt_control.make_input();
			me.controls[name].apt = apt_control;

			// Payment Proof Attach Control
			let proof_wrapper = card.find('.uip-proof-control');
			let proof_control = frappe.ui.form.make_control({
				df: {
					fieldtype: 'Attach',
					fieldname: 'payment_proof',
					placeholder: 'Upload Payment Proof...',
					hidden: 0
				},
				parent: proof_wrapper,
				only_input: true
			});
			proof_control.make_input();
			me.controls[name].proof = proof_control;
		});

		// Switch to Draft Button Click
		this.wrapper.find('.uip-btn-switch-draft').off('click').on('click', function () {
			me.active_tab = 'drafts';
			me.wrapper.find('#uip-nav-tabs .nav-link').removeClass('active');
			me.wrapper.find('#tab-drafts-btn').addClass('active');
			me.current_page = 1;
			me.update_stats();
			me.render_page();
		});

		// Submit Button Click (Create Draft)
		this.wrapper.find('.uip-btn-submit').off('click').on('click', function () {
			let btn = $(this);
			let name = btn.attr('data-name');
			let card = btn.closest('.uip-card');

			let paid_amount = card.find('.uip-amount-input').val();
			let payment_date = card.find('.uip-date-input').val();
			let reference_number = card.find('.uip-ref-input').val();
			let remarks = card.find('.uip-remarks-input').val();

			let mode_of_payment = me.controls[name] && me.controls[name].mop ? me.controls[name].mop.get_value() : null;
			let account_paid_to = me.controls[name] && me.controls[name].apt ? me.controls[name].apt.get_value() : null;
			let payment_proof = me.controls[name] && me.controls[name].proof ? me.controls[name].proof.get_value() : null;

			if (!paid_amount || flt(paid_amount) <= 0) {
				frappe.msgprint(__('Please enter a valid Payment Amount greater than 0.'));
				return;
			}

			if (!payment_date) {
				frappe.msgprint(__('Please select a valid Payment Date.'));
				return;
			}

			btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin mr-1"></i> Creating Draft...');

			frappe.call({
				method: 'xpertintegration.xpertintegration.page.sales_invoice_payment_entry.sales_invoice_payment_entry.create_payment_entry_for_invoice',
				args: {
					sales_invoice: name,
					paid_amount: paid_amount,
					payment_date: payment_date,
					reference_number: reference_number,
					payment_proof: payment_proof,
					mode_of_payment: mode_of_payment,
					account_paid_to: account_paid_to,
					remarks: remarks
				},
				callback: (r) => {
					btn.prop('disabled', false).html('<i class="fa fa-save mr-1"></i> Create Draft Payment Entry');
					if (!r.exc && r.message && r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: 'green'
						}, 5);
						me.load_data();
					}
				},
				error: () => {
					btn.prop('disabled', false).html('<i class="fa fa-save mr-1"></i> Create Draft Payment Entry');
				}
			});
		});
	}

	bind_drafts_card_controls() {
		let me = this;
		let start = (this.current_page - 1) * this.page_size;
		let page_data = this.drafts_data.slice(start, start + this.page_size);

		this.wrapper.find('.uip-card-draft').each(function (idx) {
			let card = $(this);
			let name = card.attr('data-name');
			let row_data = page_data.find(d => d.name === name) || {};

			me.controls[name] = {};

			// Mode of Payment Control
			let mop_wrapper = card.find('.uip-mop-control');
			let mop_control = frappe.ui.form.make_control({
				df: {
					fieldtype: 'Link',
					options: 'Mode of Payment',
					fieldname: 'mode_of_payment',
					placeholder: 'Select Mode of Payment...',
					hidden: 0
				},
				parent: mop_wrapper,
				only_input: true
			});
			mop_control.make_input();
			if (row_data.mode_of_payment) {
				mop_control.set_value(row_data.mode_of_payment);
			}
			me.controls[name].mop = mop_control;

			// Account Paid To Control
			let apt_wrapper = card.find('.uip-apt-control');
			let apt_control = frappe.ui.form.make_control({
				df: {
					fieldtype: 'Link',
					options: 'Account',
					fieldname: 'account_paid_to',
					placeholder: 'Select Bank/Cash Account...',
					hidden: 0,
					get_query: function () {
						return {
							filters: {
								is_group: 0,
								account_type: ['in', ['Bank', 'Cash']]
							}
						};
					}
				},
				parent: apt_wrapper,
				only_input: true
			});
			apt_control.make_input();
			if (row_data.account_paid_to) {
				apt_control.set_value(row_data.account_paid_to);
			}
			me.controls[name].apt = apt_control;

			// Payment Proof Attach Control
			let proof_wrapper = card.find('.uip-proof-control');
			let proof_control = frappe.ui.form.make_control({
				df: {
					fieldtype: 'Attach',
					fieldname: 'payment_proof',
					placeholder: 'Upload Payment Proof...',
					hidden: 0
				},
				parent: proof_wrapper,
				only_input: true
			});
			proof_control.make_input();
			if (row_data.payment_proof) {
				proof_control.set_value(row_data.payment_proof);
			}
			me.controls[name].proof = proof_control;
		});

		// Update Draft Click
		this.wrapper.find('.uip-btn-update-draft').off('click').on('click', function () {
			let btn = $(this);
			let name = btn.attr('data-name');
			let card = btn.closest('.uip-card');

			let paid_amount = card.find('.uip-amount-input').val();
			let payment_date = card.find('.uip-date-input').val();
			let reference_number = card.find('.uip-ref-input').val();
			let remarks = card.find('.uip-remarks-input').val();

			let mode_of_payment = me.controls[name] && me.controls[name].mop ? me.controls[name].mop.get_value() : null;
			let account_paid_to = me.controls[name] && me.controls[name].apt ? me.controls[name].apt.get_value() : null;
			let payment_proof = me.controls[name] && me.controls[name].proof ? me.controls[name].proof.get_value() : null;

			btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin mr-1"></i> Saving...');

			frappe.call({
				method: 'xpertintegration.xpertintegration.page.sales_invoice_payment_entry.sales_invoice_payment_entry.update_draft_payment_entry',
				args: {
					payment_entry: name,
					paid_amount: paid_amount,
					payment_date: payment_date,
					reference_number: reference_number,
					payment_proof: payment_proof,
					mode_of_payment: mode_of_payment,
					account_paid_to: account_paid_to,
					remarks: remarks
				},
				callback: (r) => {
					btn.prop('disabled', false).html('<i class="fa fa-save mr-1"></i> Update Draft');
					if (!r.exc && r.message && r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: 'green'
						}, 5);
						me.load_data();
					}
				},
				error: () => {
					btn.prop('disabled', false).html('<i class="fa fa-save mr-1"></i> Update Draft');
				}
			});
		});

		// Submit Draft Click
		this.wrapper.find('.uip-btn-submit-draft').off('click').on('click', function () {
			let btn = $(this);
			let name = btn.attr('data-name');

			frappe.confirm(
				__('Are you sure you want to submit Payment Entry <b>{0}</b>?', [name]),
				() => {
					btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin mr-1"></i> Submitting...');

					frappe.call({
						method: 'xpertintegration.xpertintegration.page.sales_invoice_payment_entry.sales_invoice_payment_entry.submit_draft_payment_entry',
						args: { payment_entry: name },
						callback: (r) => {
							btn.prop('disabled', false).html('<i class="fa fa-check-circle mr-1"></i> Submit Payment');
							if (!r.exc && r.message && r.message.success) {
								frappe.show_alert({
									message: r.message.message,
									indicator: 'green'
								}, 5);
								me.load_data();
							}
						},
						error: () => {
							btn.prop('disabled', false).html('<i class="fa fa-check-circle mr-1"></i> Submit Payment');
						}
					});
				}
			);
		});

		// Delete Draft Click
		this.wrapper.find('.uip-btn-delete-draft').off('click').on('click', function () {
			let btn = $(this);
			let name = btn.attr('data-name');

			frappe.confirm(
				__('Are you sure you want to delete Draft Payment Entry <b>{0}</b>?', [name]),
				() => {
					btn.prop('disabled', true);

					frappe.call({
						method: 'xpertintegration.xpertintegration.page.sales_invoice_payment_entry.sales_invoice_payment_entry.delete_draft_payment_entry',
						args: { payment_entry: name },
						callback: (r) => {
							btn.prop('disabled', false);
							if (!r.exc && r.message && r.message.success) {
								frappe.show_alert({
									message: r.message.message,
									indicator: 'orange'
								}, 5);
								me.load_data();
							}
						},
						error: () => {
							btn.prop('disabled', false);
						}
					});
				}
			);
		});
	}

	bind_pagination() {
		let dataset = (this.active_tab === 'pending') ? this.pending_data : this.drafts_data;

		this.wrapper.find('.btn-prev').off('click').on('click', () => {
			if (this.current_page > 1) {
				this.current_page--;
				this.render_page();
			}
		});

		this.wrapper.find('.btn-next').off('click').on('click', () => {
			let total_pages = Math.ceil(dataset.length / this.page_size);
			if (this.current_page < total_pages) {
				this.current_page++;
				this.render_page();
			}
		});
	}
}

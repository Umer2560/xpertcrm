frappe.pages['payment-verification'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Payment Verification',
		single_column: true
	});

	frappe.require('payment_verification.css');

	wrapper.payment_verification_page = new PaymentVerificationPage(wrapper);
}

class PaymentVerificationPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper).find('.layout-main-section');
		this.page = wrapper.page;
		this.current_page = 1;
		this.page_size = 10;
		this.all_data = [];
		this.controls = {};
		this.filter_controls = {};
		this.filters = {
			payment_type: 'All',
			customer: null,
			project: null,
			crm_deal: null,
			payment_entry: null
		};

		this.init_layout();
		this.load_data();
	}

	init_layout() {
		this.wrapper.html(`
			<div class="payment-verification-wrapper">
				<div class="pv-filter-card mb-4 p-3 bg-white border rounded-lg shadow-sm" style="border-radius: 12px;">
					<div class="form-row align-items-center">
						<div class="col-md-3 col-sm-6 mb-2">
							<label class="pv-filter-label">
								<i class="fa fa-list-alt mr-1 text-muted"></i> Payment Type
							</label>
							<select id="pv-filter-payment-type" class="form-control pv-filter-select">
								<option value="All" selected>All</option>
								<option value="Deal Invoice Payment">Deal Invoice Payment</option>
								<option value="Sales Invoice Payment">Sales Invoice Payment</option>
							</select>
						</div>

						<div class="col-md-3 col-sm-6 mb-2">
							<label class="pv-filter-label">
								<i class="fa fa-building-o mr-1 text-muted"></i> Company Code/Company Name
							</label>
							<div id="pv-filter-customer"></div>
						</div>

						<div class="col-md-3 col-sm-6 mb-2">
							<label class="pv-filter-label">
								<i class="fa fa-folder-open mr-1 text-muted"></i> Project
							</label>
							<div id="pv-filter-project"></div>
						</div>

						<div class="col-md-3 col-sm-6 mb-2" id="pv-filter-crm-deal-col" style="display: none;">
							<label class="pv-filter-label">
								<i class="fa fa-handshake-o mr-1 text-muted"></i> CRM Deal
							</label>
							<div id="pv-filter-crm-deal"></div>
						</div>

						<div class="col-md-3 col-sm-6 mb-2" id="pv-filter-payment-entry-col" style="display: none;">
							<label class="pv-filter-label">
								<i class="fa fa-file-text-o mr-1 text-muted"></i> Payment Entry
							</label>
							<div id="pv-filter-payment-entry"></div>
						</div>

						<div class="col-md-2 col-sm-12 text-right mb-2 ml-auto">
							<button class="btn btn-sm btn-light border btn-reset-filters" style="margin-top: 18px; border-radius: 8px; font-weight: 600;">
								<i class="fa fa-refresh mr-1"></i> Reset
							</button>
						</div>
					</div>
				</div>

				<div class="pv-header-row">
					<div class="pv-col-details">Details</div>
					<div class="pv-col-attachment text-center">Attachment</div>
					<div class="pv-col-action">Verification</div>
				</div>

				<div id="payment-verification-body">
					<div class="text-center py-5 text-muted">
						<i class="fa fa-spinner fa-spin fa-2x mb-2"></i>
						<div>Loading records...</div>
					</div>
				</div>
			</div>
		`);

		this.setup_filters();
	}

	setup_filters() {
		let me = this;

		// Select for Payment Type
		let select_pt = this.wrapper.find('#pv-filter-payment-type');
		select_pt.off('change').on('change', function() {
			me.filters.payment_type = $(this).val();
			if (me.filters.payment_type === 'Deal Invoice Payment') {
				me.filters.payment_entry = null;
				if (me.filter_controls.payment_entry) {
					me.filter_controls.payment_entry.set_value('');
				}
				me.wrapper.find('#pv-filter-crm-deal-col').show();
				me.wrapper.find('#pv-filter-payment-entry-col').hide();
			} else if (me.filters.payment_type === 'Sales Invoice Payment') {
				me.filters.crm_deal = null;
				if (me.filter_controls.crm_deal) {
					me.filter_controls.crm_deal.set_value('');
				}
				me.wrapper.find('#pv-filter-crm-deal-col').hide();
				me.wrapper.find('#pv-filter-payment-entry-col').show();
			} else {
				// "All" selected
				me.filters.crm_deal = null;
				me.filters.payment_entry = null;
				if (me.filter_controls.crm_deal) {
					me.filter_controls.crm_deal.set_value('');
				}
				if (me.filter_controls.payment_entry) {
					me.filter_controls.payment_entry.set_value('');
				}
				me.wrapper.find('#pv-filter-crm-deal-col').hide();
				me.wrapper.find('#pv-filter-payment-entry-col').hide();
			}
			me.load_data();
		});

		// Customer (Company Code/Company Name) Link Control
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
			parent: this.wrapper.find('#pv-filter-customer'),
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
			parent: this.wrapper.find('#pv-filter-project'),
			only_input: true
		});
		proj_control.make_input();
		this.filter_controls.project = proj_control;

		// CRM Deal Link Control
		let deal_control = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'CRM Deal',
				fieldname: 'crm_deal',
				placeholder: 'Filter by CRM Deal...',
				get_query: () => ({ filters: { custom_payment_status: 'Verify Payment', status: ['in', ['In Trial', 'In Trail']] } }),
				change: () => {
					let val = deal_control.get_value();
					if (val !== me.filters.crm_deal) {
						me.filters.crm_deal = val;
						me.load_data();
					}
				}
			},
			parent: this.wrapper.find('#pv-filter-crm-deal'),
			only_input: true
		});
		deal_control.make_input();
		this.filter_controls.crm_deal = deal_control;

		// Payment Entry Link Control
		let pe_control = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				options: 'Payment Entry',
				fieldname: 'payment_entry',
				placeholder: 'Filter by Payment Entry...',
				get_query: () => ({ filters: { docstatus: 0 } }),
				change: () => {
					let val = pe_control.get_value();
					if (val !== me.filters.payment_entry) {
						me.filters.payment_entry = val;
						me.load_data();
					}
				}
			},
			parent: this.wrapper.find('#pv-filter-payment-entry'),
			only_input: true
		});
		pe_control.make_input();
		this.filter_controls.payment_entry = pe_control;

		// Reset Button
		this.wrapper.find('.btn-reset-filters').off('click').on('click', function() {
			me.filters = {
				payment_type: 'All',
				customer: null,
				project: null,
				crm_deal: null,
				payment_entry: null
			};
			select_pt.val('All');
			cust_control.set_value('');
			proj_control.set_value('');
			deal_control.set_value('');
			pe_control.set_value('');
			me.wrapper.find('#pv-filter-crm-deal-col').hide();
			me.wrapper.find('#pv-filter-payment-entry-col').hide();
			me.load_data();
		});
	}

	load_data() {
		frappe.call({
			method: 'xpertintegration.xpertintegration.page.payment_verification.payment_verification.get_pending_verification_records',
			args: {
				payment_type: this.filters.payment_type,
				customer: this.filters.customer,
				project: this.filters.project,
				crm_deal: this.filters.crm_deal,
				payment_entry: this.filters.payment_entry
			},
			callback: (r) => {
				this.all_data = r.message || [];
				this.current_page = 1;
				this.render_page();
			}
		});
	}

	render_page() {
		let start = (this.current_page - 1) * this.page_size;
		let end = start + this.page_size;
		let page_data = this.all_data.slice(start, end);
		let total_pages = Math.ceil(this.all_data.length / this.page_size);
		
		this.controls = {};

		let html = frappe.render_template('payment_verification', { 
			data: page_data,
			current_page: this.current_page,
			total_pages: total_pages,
			total_records: this.all_data.length
		});

		this.wrapper.find('#payment-verification-body').html(html);
		this.bind_events();
	}

	bind_events() {
		let me = this;
		
		this.wrapper.find('.proof-image').off('click').on('click', function() {
			let url = $(this).data('url');
			let d = new frappe.ui.Dialog({
				title: 'Payment Proof',
				fields: [
					{
						fieldtype: 'HTML',
						fieldname: 'image_html',
						options: `<div class="text-center" style="padding: 10px; background: #f8f9fa; border-radius: 8px;">
									<img src="${url}" style="max-width: 100%; max-height: 65vh; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />
								  </div>`
					}
				],
				size: 'large'
			});
			d.show();
		});

		this.wrapper.find('.pv-card').each(function() {
			let card = $(this);
			let name = card.attr('data-name');
			me.controls[name] = {};
			
			// Mode of Payment Control
			let mop_wrapper = card.find('.pv-mode-of-payment-control');
			let mop_value = mop_wrapper.data('value') || 'Wire Transfer';
			let mop_control = frappe.ui.form.make_control({
				df: {
					fieldtype: 'Link',
					options: 'Mode of Payment',
					fieldname: 'mode_of_payment',
					label: 'Mode of Payment',
					hidden: 0
				},
				parent: mop_wrapper,
				only_input: true,
			});
			mop_control.make_input();
			if (mop_value) {
				mop_control.set_value(mop_value);
			}
			me.controls[name].mop = mop_control;

			// Account Paid To Control
			let apt_wrapper = card.find('.pv-account-paid-to-control');
			let apt_value = apt_wrapper.data('value');
			let apt_control = frappe.ui.form.make_control({
				df: {
					fieldtype: 'Link',
					options: 'Account',
					fieldname: 'account_paid_to',
					label: 'Account Paid To',
					hidden: 0,
					get_query: function() {
						return {
							filters: {
								is_group: 0,
								account_type: ['in', ['Bank', 'Cash']]
							}
						};
					}
				},
				parent: apt_wrapper,
				only_input: true,
			});
			apt_control.make_input();
			if (apt_value) {
				apt_control.set_value(apt_value);
			}
			me.controls[name].apt = apt_control;
		});

		this.wrapper.find('.action-select').off('change').on('change', function() {
			let val = $(this).val();
			let remarks_input = $(this).siblings('.remarks-input');
			if (['Cancelled', 'Unpaid'].includes(val)) {
				remarks_input.show();
			} else {
				remarks_input.hide();
			}
		});

		this.wrapper.find('.btn-save').off('click').on('click', function() {
			let btn = $(this);
			let name = btn.attr('data-name');
			let record_type = btn.attr('data-record-type') || me.filters.payment_type;
			let tr = btn.closest('.pv-card');
			let status = tr.find('.action-select').val();
			let remarks = tr.find('.remarks-input').val();
			let reference_number = tr.find('.reference-number-input').val();
			let amount_received = tr.find('.amount-received-input').val();
			
			let mode_of_payment = me.controls[name] && me.controls[name].mop ? me.controls[name].mop.get_value() : null;
			let account_paid_to = me.controls[name] && me.controls[name].apt ? me.controls[name].apt.get_value() : null;

			if (!status) {
				frappe.msgprint('Please select an action');
				return;
			}

			if (['Cancelled', 'Unpaid'].includes(status) && !remarks) {
				frappe.msgprint('Please provide remarks for ' + status);
				return;
			}

			me.call_update_status(record_type, name, status, remarks, amount_received, mode_of_payment, account_paid_to, reference_number);
		});

		// Pagination Events
		this.wrapper.find('.btn-prev').off('click').on('click', () => {
			if (this.current_page > 1) {
				this.current_page--;
				this.render_page();
			}
		});

		this.wrapper.find('.btn-next').off('click').on('click', () => {
			let total_pages = Math.ceil(this.all_data.length / this.page_size);
			if (this.current_page < total_pages) {
				this.current_page++;
				this.render_page();
			}
		});
	}

	call_update_status(record_type, name, status, remarks, amount_received, mode_of_payment, account_paid_to, reference_number) {
		frappe.call({
			method: 'xpertintegration.xpertintegration.page.payment_verification.payment_verification.update_verification_record',
			args: {
				record_type: record_type,
				name: name,
				status: status,
				remarks: remarks,
				amount_received: amount_received,
				mode_of_payment: mode_of_payment,
				account_paid_to: account_paid_to,
				reference_number: reference_number
			},
			callback: (r) => {
				if (!r.exc) {
					frappe.show_alert({message: 'Saved Successfully', indicator: 'green'});
					this.load_data();
				}
			}
		});
	}
}
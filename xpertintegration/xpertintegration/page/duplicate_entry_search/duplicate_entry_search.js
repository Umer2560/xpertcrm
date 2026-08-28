frappe.templates['duplicate_entry_search'] = frappe.templates['duplicate_entry_search'] || `
{% if (clusters && clusters.length) { %}
<div class="dup-summary-banner">
    <div class="dup-summary-text">
        <i class="fa fa-clone mr-2"></i> Found <strong>{{ total_clusters }}</strong> duplicate group(s) in {{ doctype }}
    </div>
    <div class="dup-summary-badge">
        Matching criterion: {{ match_by_label }}
    </div>
</div>

<div class="dup-clusters-container">
    {% for (var c = 0; c < clusters.length; c++) { var cluster = clusters[c]; %}
    <div class="dup-cluster-card" data-cluster-id="{{ cluster.cluster_id }}" data-master-id="{{ cluster.recommended_master }}" data-active-mode="merge">
        <div class="dup-cluster-header">
            <div class="dup-cluster-key">
                <i class="fa fa-object-group text-primary mr-1"></i>
                {{ cluster.display_key }}
                <span class="dup-type-tag {{ cluster.match_by }}">{{ cluster.match_type }}</span>
            </div>
            
            <div class="d-flex align-items-center">
                <div class="dup-mode-switcher mr-3">
                    <button type="button" class="dup-mode-btn mode-merge active" data-cluster-id="{{ cluster.cluster_id }}" data-mode="merge">
                        <i class="fa fa-code-fork mr-1"></i> Merge Mode
                    </button>
                    <button type="button" class="dup-mode-btn mode-delete" data-cluster-id="{{ cluster.cluster_id }}" data-mode="delete">
                        <i class="fa fa-trash mr-1"></i> Delete Mode
                    </button>
                </div>
                <div class="badge badge-pill badge-danger" style="font-size: 0.85rem; padding: 6px 12px;">
                    {{ cluster.total_count }} Duplicates
                </div>
            </div>
        </div>

        <div class="dup-quick-toolbar">
            <div class="toolbar-mode-info">
                <span class="merge-toolbar-text"><i class="fa fa-info-circle text-primary mr-1"></i> Select 1 <strong>Main Document</strong> and choose secondary records to merge into it:</span>
                <span class="delete-toolbar-text d-none"><i class="fa fa-exclamation-triangle text-danger mr-1"></i> Select records you wish to <strong>Permanently Delete</strong>:</span>
            </div>
            <div class="toolbar-quick-actions">
                <a href="javascript:void(0);" class="btn-quick-select-all mr-3" data-cluster-id="{{ cluster.cluster_id }}">
                    <i class="fa fa-check-square-o"></i> Select All
                </a>
                <a href="javascript:void(0);" class="btn-quick-deselect-all text-muted" data-cluster-id="{{ cluster.cluster_id }}">
                    <i class="fa fa-square-o"></i> Deselect All
                </a>
            </div>
        </div>

        <div class="dup-records-grid">
            {% for (var r = 0; r < cluster.records.length; r++) { var rec = cluster.records[r]; %}
            <div class="dup-record-item {% if (rec.name === cluster.recommended_master) { %}is-master{% } %}" data-rec-id="{{ rec.name }}">
                {% if (rec.name === cluster.recommended_master) { %}
                <div class="dup-master-badge">Main Document</div>
                {% } %}

                <div class="dup-record-title">
                    <a href="/app/{{ doctype.toLowerCase().replace(/ /g, '-') }}/{{ rec.name }}" target="_blank" class="text-dark">
                        {{ rec.display_title || rec.name }}
                    </a>
                </div>

                <div class="dup-record-detail text-muted mb-1">
                    <i class="fa fa-id-card-o"></i> <strong>ID:</strong> {{ rec.name }}
                </div>

                {% if (rec.mobile_no || rec.phone) { %}
                <div class="dup-record-detail">
                    <i class="fa fa-phone"></i> {{ rec.mobile_no || rec.phone }}
                </div>
                {% } %}

                {% if (rec.email || rec.email_id) { %}
                <div class="dup-record-detail">
                    <i class="fa fa-envelope-o"></i> {{ rec.email || rec.email_id }}
                </div>
                {% } %}

                {% if (rec.creation) { %}
                <div class="dup-record-detail">
                    <i class="fa fa-calendar"></i> Created: {{ String(rec.creation).split(" ")[0] }}
                </div>
                {% } %}

                {% if (rec.owner) { %}
                <div class="dup-record-detail">
                    <i class="fa fa-user"></i> Owner: {{ rec.owner }}
                </div>
                {% } %}

                <div class="dup-controls-section">
                    <!-- MERGE MODE CONTROLS -->
                    <div class="merge-controls-wrapper">
                        <label class="dup-radio-label mb-1">
                            <input type="radio" name="master_select_{{ cluster.cluster_id }}" value="{{ rec.name }}" {% if (rec.name === cluster.recommended_master) { %}checked{% } %} class="master-radio-input">
                            Main Document
                        </label>
                        <label class="dup-checkbox-label merge-checkbox merge-check-wrapper {% if (rec.name === cluster.recommended_master) { %}d-none{% } %}">
                            <input type="checkbox" value="{{ rec.name }}" checked class="merge-checkbox-input">
                            Merge this record
                        </label>
                    </div>

                    <!-- DELETE MODE CONTROLS -->
                    <div class="delete-controls-wrapper d-none">
                        <label class="dup-checkbox-label delete-checkbox">
                            <input type="checkbox" value="{{ rec.name }}" class="delete-checkbox-input">
                            Delete this record
                        </label>
                    </div>
                </div>
            </div>
            {% } %}
        </div>

        <div class="dup-cluster-footer">
            <div class="selection-counter-text text-muted font-weight-bold" style="font-size: 0.85rem;">
                <span class="merge-count-text">Ready to merge selected records into Main Document.</span>
                <span class="delete-count-text d-none">0 record(s) selected for deletion.</span>
            </div>

            <div class="action-buttons-group">
                <button class="btn btn-merge-selected" data-cluster-id="{{ cluster.cluster_id }}">
                    <i class="fa fa-code-fork mr-1"></i> Merge Selected Records
                </button>
                <button class="btn btn-delete-selected d-none" data-cluster-id="{{ cluster.cluster_id }}">
                    <i class="fa fa-trash mr-1"></i> Delete Selected Records
                </button>
            </div>
        </div>
    </div>
    {% } %}
</div>
{% } else { %}
<div class="empty-state bg-white border rounded-lg p-5">
    <i class="fa fa-check-circle-o text-success" style="font-size: 3.5rem;"></i>
    <h4 class="mt-3 font-weight-bold text-dark">No Duplicate Entries Found!</h4>
    <p class="text-muted">All records in <strong>{{ doctype }}</strong> are unique based on the selected filter criterion ({{ match_by_label }}).</p>
</div>
{% } %}
`;

frappe.pages['duplicate-entry-search'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Duplicate Entry Search & Cleaner',
		single_column: true
	});

	frappe.require('duplicate_entry_search.css');
	wrapper.duplicate_entry_search_page = new DuplicateEntrySearchPage(wrapper);
};

class DuplicateEntrySearchPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper).find('.layout-main-section');
		this.page = wrapper.page;
		this.filters = {
			doctype: 'CRM Lead',
			match_by: 'mobile'
		};
		this.all_clusters = [];

		this.init_layout();
		this.load_data();
	}

	init_layout() {
		this.wrapper.html(`
			<div class="dup-search-wrapper">
				<div class="dup-filter-card mb-4">
					<div class="dup-filter-title">
						<i class="fa fa-filter text-primary"></i> Search & Filter Settings
					</div>
					<div class="form-row align-items-center">
						<div class="col-md-4 col-sm-6 mb-2">
							<label class="dup-filter-label">
								<i class="fa fa-database mr-1 text-muted"></i> Select Target DocType
							</label>
							<select id="dup-filter-doctype" class="form-control dup-filter-select">
								<option value="CRM Lead" selected>CRM Lead</option>
								<option value="Customer">Customer</option>
								<option value="Contact">Contact</option>
								<option value="CRM Deal">CRM Deal</option>
							</select>
						</div>

						<div class="col-md-4 col-sm-6 mb-2">
							<label class="dup-filter-label">
								<i class="fa fa-search mr-1 text-muted"></i> Match Criteria
							</label>
							<select id="dup-filter-match-by" class="form-control dup-filter-select">
								<option value="mobile" selected>📱 Mobile Number (2-Stage Tail Match)</option>
								<option value="email">📧 Email Address (Trimmed/Case-Insensitive)</option>
								<option value="both">⚡ Both (Mobile Number or Email)</option>
							</select>
						</div>

						<div class="col-md-4 col-sm-12 text-right mb-2 ml-auto">
							<button class="btn btn-primary font-weight-bold btn-refresh-dup" style="margin-top: 24px; border-radius: 8px; padding: 9px 20px;">
								<i class="fa fa-refresh mr-1"></i> Scan for Duplicates
							</button>
						</div>
					</div>
				</div>

				<div id="dup-results-body">
					<div class="text-center py-5 text-muted">
						<i class="fa fa-spinner fa-spin fa-2x mb-2"></i>
						<div>Scanning system for duplicate entries...</div>
					</div>
				</div>
			</div>
		`);

		this.setup_filters();
	}

	setup_filters() {
		let me = this;

		this.wrapper.find('#dup-filter-doctype').off('change').on('change', function () {
			me.filters.doctype = $(this).val();
			me.load_data();
		});

		this.wrapper.find('#dup-filter-match-by').off('change').on('change', function () {
			me.filters.match_by = $(this).val();
			me.load_data();
		});

		this.wrapper.find('.btn-refresh-dup').off('click').on('click', function () {
			me.load_data();
		});
	}

	load_data() {
		this.wrapper.find('#dup-results-body').html(`
			<div class="text-center py-5 text-muted bg-white border rounded-lg">
				<i class="fa fa-spinner fa-spin fa-2x mb-2 text-primary"></i>
				<div class="font-weight-bold">Scanning ${this.filters.doctype} for duplicates...</div>
			</div>
		`);

		frappe.call({
			method: 'xpertintegration.xpertintegration.page.duplicate_entry_search.duplicate_entry_search.get_duplicate_clusters',
			args: {
				doctype: this.filters.doctype,
				match_by: this.filters.match_by
			},
			callback: (r) => {
				let data = r.message || {};
				this.all_clusters = data.clusters || [];
				this.render_clusters(data);
			}
		});
	}

	render_clusters(data) {
		let match_labels = {
			'mobile': 'Mobile Number (Last 7 & 10 Digits)',
			'email': 'Email Address',
			'both': 'Mobile Number or Email'
		};

		let template_name = 'duplicate_entry_search';

		let html = frappe.render_template(template_name, {
			clusters: this.all_clusters,
			total_clusters: data.total_clusters || 0,
			doctype: this.filters.doctype,
			match_by_label: match_labels[this.filters.match_by] || this.filters.match_by
		});

		this.wrapper.find('#dup-results-body').html(html);
		this.bind_events();
	}

	bind_events() {
		let me = this;

		// Mode Switcher Toggle (Merge Mode vs Delete Mode)
		this.wrapper.find('.dup-mode-btn').off('click').on('click', function () {
			let btn = $(this);
			let card = btn.closest('.dup-cluster-card');
			let mode = btn.attr('data-mode');

			card.find('.dup-mode-btn').removeClass('active');
			btn.addClass('active');

			card.attr('data-active-mode', mode);

			if (mode === 'merge') {
				card.find('.merge-toolbar-text').removeClass('d-none');
				card.find('.delete-toolbar-text').addClass('d-none');

				card.find('.merge-controls-wrapper').removeClass('d-none');
				card.find('.delete-controls-wrapper').addClass('d-none');

				card.find('.merge-count-text').removeClass('d-none');
				card.find('.delete-count-text').addClass('d-none');

				card.find('.btn-merge-selected').removeClass('d-none');
				card.find('.btn-delete-selected').addClass('d-none');
			} else {
				card.find('.merge-toolbar-text').addClass('d-none');
				card.find('.delete-toolbar-text').removeClass('d-none');

				card.find('.merge-controls-wrapper').addClass('d-none');
				card.find('.delete-controls-wrapper').removeClass('d-none');

				card.find('.merge-count-text').addClass('d-none');
				card.find('.delete-count-text').removeClass('d-none');

				card.find('.btn-merge-selected').addClass('d-none');
				card.find('.btn-delete-selected').removeClass('d-none');
			}
			me.update_cluster_counts(card);
		});

		// Master Radio selection change handler
		this.wrapper.find('.master-radio-input').off('change').on('change', function () {
			let selected_master = $(this).val();
			let card = $(this).closest('.dup-cluster-card');
			
			card.attr('data-master-id', selected_master);
			card.find('.dup-record-item').removeClass('is-master');
			card.find('.dup-master-badge').remove();

			let selected_item = card.find(`.dup-record-item[data-rec-id="${selected_master}"]`);
			selected_item.addClass('is-master');
			selected_item.prepend('<div class="dup-master-badge">Main Document</div>');

			// Hide and uncheck merge checkbox for new Master record, show for others
			card.find('.dup-record-item').each(function () {
				let rec_id = $(this).attr('data-rec-id');
				let check_wrapper = $(this).find('.merge-check-wrapper');
				let checkbox = check_wrapper.find('.merge-checkbox-input');
				if (rec_id === selected_master) {
					check_wrapper.addClass('d-none');
					checkbox.prop('checked', false);
				} else {
					check_wrapper.removeClass('d-none');
					checkbox.prop('checked', true);
				}
			});

			me.update_cluster_counts(card);
		});

		// Merge Checkbox Change
		this.wrapper.find('.merge-checkbox-input').off('change').on('change', function () {
			let card = $(this).closest('.dup-cluster-card');
			me.update_cluster_counts(card);
		});

		// Delete Checkbox Change
		this.wrapper.find('.delete-checkbox-input').off('change').on('change', function () {
			let checkbox = $(this);
			let item = checkbox.closest('.dup-record-item');
			let card = checkbox.closest('.dup-cluster-card');

			if (checkbox.is(':checked')) {
				item.addClass('marked-for-delete');
			} else {
				item.removeClass('marked-for-delete');
			}

			me.update_cluster_counts(card);
		});

		// Quick Select All Toolbar Handler
		this.wrapper.find('.btn-quick-select-all').off('click').on('click', function () {
			let card = $(this).closest('.dup-cluster-card');
			let mode = card.attr('data-active-mode') || 'merge';

			if (mode === 'merge') {
				let master_id = card.attr('data-master-id');
				card.find('.dup-record-item').each(function () {
					let rec_id = $(this).attr('data-rec-id');
					if (rec_id !== master_id) {
						$(this).find('.merge-checkbox-input').prop('checked', true);
					}
				});
			} else {
				card.find('.dup-record-item').addClass('marked-for-delete');
				card.find('.delete-checkbox-input').prop('checked', true);
			}
			me.update_cluster_counts(card);
		});

		// Quick Deselect All Toolbar Handler
		this.wrapper.find('.btn-quick-deselect-all').off('click').on('click', function () {
			let card = $(this).closest('.dup-cluster-card');
			let mode = card.attr('data-active-mode') || 'merge';

			if (mode === 'merge') {
				card.find('.merge-checkbox-input').prop('checked', false);
			} else {
				card.find('.dup-record-item').removeClass('marked-for-delete');
				card.find('.delete-checkbox-input').prop('checked', false);
			}
			me.update_cluster_counts(card);
		});

		// Merge Button handler
		this.wrapper.find('.btn-merge-selected').off('click').on('click', function () {
			let btn = $(this);
			let card = btn.closest('.dup-cluster-card');
			let master_doc = card.attr('data-master-id');

			let duplicate_docs = [];
			card.find('.merge-checkbox-input:checked').each(function () {
				let val = $(this).val();
				if (val && val !== master_doc) {
					duplicate_docs.push(val);
				}
			});

			if (duplicate_docs.length === 0) {
				frappe.msgprint(__('Please select at least 1 secondary document to merge into the Main Document.'));
				return;
			}

			frappe.confirm(
				__('<b>Confirm Record Merge</b><br>Are you sure you want to merge <b>{0}</b> selected secondary record(s) into Main Document <b>{1}</b>?<br><br><small class="text-muted">Linked logs, communications, and activities will be consolidated into {1}.</small>', [
					duplicate_docs.length,
					master_doc
				]),
				() => {
					me.execute_merge(master_doc, duplicate_docs);
				}
			);
		});

		// Delete Button handler
		this.wrapper.find('.btn-delete-selected').off('click').on('click', function () {
			let btn = $(this);
			let card = btn.closest('.dup-cluster-card');

			let docs_to_delete = [];
			card.find('.delete-checkbox-input:checked').each(function () {
				let val = $(this).val();
				if (val) {
					docs_to_delete.push(val);
				}
			});

			if (docs_to_delete.length === 0) {
				frappe.msgprint(__('Please select at least 1 document to delete.'));
				return;
			}

			frappe.confirm(
				__('<b>⚠️ Confirm Document Deletion</b><br>Are you sure you want to permanently DELETE <b>{0}</b> selected record(s) from <b>{1}</b>?<br><br><strong class="text-danger">This action cannot be undone.</strong>', [
					docs_to_delete.length,
					me.filters.doctype
				]),
				() => {
					me.execute_delete(docs_to_delete);
				}
			);
		});

		// Initial count update for all cards
		this.wrapper.find('.dup-cluster-card').each(function () {
			me.update_cluster_counts($(this));
		});
	}

	update_cluster_counts(card) {
		let mode = card.attr('data-active-mode') || 'merge';
		if (mode === 'merge') {
			let checked_count = card.find('.merge-checkbox-input:checked').length;
			let master_id = card.attr('data-master-id');
			card.find('.merge-count-text').html(`Ready to merge <strong>${checked_count}</strong> secondary record(s) into <strong>${master_id}</strong>.`);
			card.find('.btn-merge-selected').html(`<i class="fa fa-code-fork mr-1"></i> Merge ${checked_count} Selected Records`);
		} else {
			let checked_count = card.find('.delete-checkbox-input:checked').length;
			card.find('.delete-count-text').html(`<strong>${checked_count}</strong> record(s) selected for deletion.`);
			card.find('.btn-delete-selected').html(`<i class="fa fa-trash mr-1"></i> Delete ${checked_count} Selected Records`);
		}
	}

	execute_merge(master_doc, duplicate_docs) {
		frappe.call({
			method: 'xpertintegration.xpertintegration.page.duplicate_entry_search.duplicate_entry_search.merge_duplicate_records',
			args: {
				doctype: this.filters.doctype,
				master_doc: master_doc,
				duplicate_docs: duplicate_docs
			},
			freeze: true,
			freeze_message: __('Merging duplicate entries into {0}...', [master_doc]),
			callback: (r) => {
				if (!r.exc && r.message) {
					frappe.show_alert({
						message: r.message.message || __('Merge Completed Successfully'),
						indicator: 'green'
					});
					this.load_data();
				}
			}
		});
	}

	execute_delete(docs_to_delete) {
		frappe.call({
			method: 'xpertintegration.xpertintegration.page.duplicate_entry_search.duplicate_entry_search.delete_duplicate_records',
			args: {
				doctype: this.filters.doctype,
				docs_to_delete: docs_to_delete
			},
			freeze: true,
			freeze_message: __('Deleting {0} record(s)...', [docs_to_delete.length]),
			callback: (r) => {
				if (!r.exc && r.message) {
					frappe.show_alert({
						message: r.message.message || __('Selected Records Deleted Successfully'),
						indicator: 'green'
					});
					this.load_data();
				}
			}
		});
	}
}

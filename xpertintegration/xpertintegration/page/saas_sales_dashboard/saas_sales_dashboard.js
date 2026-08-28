frappe.pages['saas-sales-dashboard'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'SaaS Business & Sales',
        single_column: true
    });

    page.set_title_sub('Subscriptions • Revenue • Renewals • Sales Performance');

    // page.add_inner_button(__('Email Report'), function () {
    //     open_email_dialog();
    // });

    frappe.dom.set_style(`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .saas-dashboard { font-family:'Inter',sans-serif; padding:20px; }

        /* ── Filters ── */
        .saas-filters {
            display:flex; gap:12px; margin-bottom:24px;
            background:#fff; padding:14px 20px;
            border-radius:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,.05);
            flex-wrap:wrap; align-items:center;
        }
        .saas-filters label { font-size:12px; font-weight:600; color:#6b7280; text-transform:uppercase; letter-spacing:.5px; }
        .saas-filter-group { display:flex; flex-direction:column; gap:4px; }
        .saas-filters select {
            padding:8px 12px; border:1px solid #e5e7eb; border-radius:8px;
            font-size:13px; outline:none; background:#f9fafb; color:#374151;
            transition:border-color .2s; cursor:pointer;
        }
        .saas-filters select:hover, .saas-filters select:focus { border-color:#6366f1; background:#fff; }
        .saas-filter-actions { display:flex; gap:8px; margin-left:auto; align-items:flex-end; }
        .saas-btn {
            padding:9px 18px; border-radius:8px; font-size:13px; font-weight:600;
            cursor:pointer; border:none; transition:all .2s;
        }
        .saas-btn-primary { background:#6366f1; color:#fff; }
        .saas-btn-primary:hover { background:#4f46e5; transform:translateY(-1px); box-shadow:0 4px 12px rgba(99,102,241,.3); }
        .saas-btn-ghost { background:#f3f4f6; color:#374151; }
        .saas-btn-ghost:hover { background:#e5e7eb; }

        /* ── KPI Grid ── */
        .saas-kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:18px; margin-bottom:24px; }

        /* ── Pipeline Grid ── */
        .saas-pipeline-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:18px; margin-top:8px; }
        .saas-pipeline-card {
            background:#f8fafc; border-radius:14px; padding:18px;
            border:1px solid #e2e8f0; transition:all .25s ease; cursor:pointer;
        }
        .saas-pipeline-card:hover { border-color:#6366f1; background:#fff; box-shadow:0 8px 16px -2px rgba(99,102,241,.1); transform:translateY(-2px); }
        .saas-pipeline-card-header { display:flex; align-items:center; gap:12px; margin-bottom:16px; }
        .saas-pipeline-card-icon {
            width:42px; height:42px; border-radius:10px; display:flex;
            align-items:center; justify-content:center; font-size:18px; flex-shrink:0;
        }
        .saas-pipeline-card-title { font-size:14px; font-weight:700; color:#1e293b; }
        .saas-pipeline-card-sub { font-size:11px; color:#64748b; }

        .saas-pipeline-metrics { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; }
        .metric-box {
            background:#fff; border:1px solid #e2e8f0; border-radius:10px;
            padding:10px 8px; text-align:center; transition:all .2s;
        }
        .metric-box.highlighted { background:#eef2ff; border-color:#c7d2fe; }
        .metric-label { display:block; font-size:10px; font-weight:700; text-transform:uppercase; color:#64748b; margin-bottom:4px; letter-spacing:.4px; }
        .metric-box.highlighted .metric-label { color:#4f46e5; }
        .metric-value { display:block; font-size:20px; font-weight:800; color:#0f172a; line-height:1.2; }
        .metric-box.highlighted .metric-value { color:#3730a3; }
        .saas-kpi-card {
            background:#fff; border-radius:16px; padding:20px;
            box-shadow:0 4px 6px -1px rgba(0,0,0,.05);
            transition:transform .25s ease, box-shadow .25s ease;
            position:relative; overflow:hidden; border:1px solid rgba(0,0,0,.03);
        }
        .saas-kpi-card:hover { transform:translateY(-4px); box-shadow:0 16px 24px -4px rgba(0,0,0,.1); }
        .saas-kpi-card::before {
            content:''; position:absolute; top:0; left:0; width:100%; height:4px;
        }
        .kpi-color-blue::before   { background:linear-gradient(90deg,#3b82f6,#60a5fa); }
        .kpi-color-green::before  { background:linear-gradient(90deg,#10b981,#34d399); }
        .kpi-color-purple::before { background:linear-gradient(90deg,#8b5cf6,#a78bfa); }
        .kpi-color-amber::before  { background:linear-gradient(90deg,#f59e0b,#fbbf24); }
        .kpi-color-red::before    { background:linear-gradient(90deg,#ef4444,#f87171); }

        .saas-kpi-icon {
            width:40px; height:40px; border-radius:10px; display:flex;
            align-items:center; justify-content:center; margin-bottom:14px;
            font-size:18px;
        }
        .icon-blue   { background:#eff6ff; color:#3b82f6; }
        .icon-green  { background:#ecfdf5; color:#10b981; }
        .icon-purple { background:#f5f3ff; color:#8b5cf6; }
        .icon-amber  { background:#fffbeb; color:#f59e0b; }
        .icon-red    { background:#fef2f2; color:#ef4444; }

        .saas-kpi-title { font-size:12px; text-transform:uppercase; font-weight:600; color:#6b7280; letter-spacing:.6px; margin-bottom:8px; }
        .saas-kpi-value { font-size:28px; font-weight:700; color:#111827; margin-bottom:8px; line-height:1; }
        .saas-kpi-trend { font-size:12px; font-weight:600; padding:3px 8px; border-radius:20px; display:inline-flex; align-items:center; gap:4px; margin-bottom:12px; }
        .trend-up   { background:#dcfce7; color:#166534; }
        .trend-down { background:#fee2e2; color:#991b1b; }
        .trend-flat { background:#f3f4f6; color:#4b5563; }
        .saas-kpi-details { font-size:12px; color:#6b7280; line-height:1.8; border-top:1px solid #f3f4f6; padding-top:10px; margin-top:4px; }
        .saas-kpi-details strong { color:#374151; font-weight:600; }

        /* ── Sections ── */
        .saas-section {
            background:#fff; border-radius:16px; padding:24px;
            box-shadow:0 4px 6px -1px rgba(0,0,0,.05); margin-bottom:24px;
        }
        .saas-section-title {
            font-size:16px; font-weight:700; color:#111827;
            margin-bottom:18px; display:flex; justify-content:space-between; align-items:center;
        }
        .saas-section-subtitle { font-size:12px; font-weight:400; color:#9ca3af; }

        /* ── Two-col layout ── */
        .grid-2-col { display:grid; grid-template-columns:2fr 1fr; gap:24px; margin-bottom:24px; }

        /* ── Tables ── */
        .table-modern { width:100%; border-collapse:collapse; }
        .table-modern th {
            padding:10px 14px; background:#f9fafb;
            font-size:11px; font-weight:700; color:#6b7280;
            text-transform:uppercase; letter-spacing:.5px;
            border-bottom:2px solid #e5e7eb; cursor:pointer; white-space:nowrap;
        }
        .table-modern th:hover { color:#6366f1; }
        .table-modern td { padding:11px 14px; border-bottom:1px solid #f3f4f6; font-size:13px; color:#374151; }
        .table-modern tbody tr:last-child td { border-bottom:none; }
        .table-modern tbody tr:hover { background:#fafafa; }
        .badge-rank {
            width:26px; height:26px; border-radius:50%; background:#6366f1;
            color:#fff; font-size:11px; font-weight:700; display:inline-flex;
            align-items:center; justify-content:center;
        }
        .badge-rank.gold   { background:linear-gradient(135deg,#f59e0b,#fbbf24); }
        .badge-rank.silver { background:linear-gradient(135deg,#6b7280,#9ca3af); }
        .badge-rank.bronze { background:linear-gradient(135deg,#92400e,#b45309); }

        /* ── Alerts ── */
        .alert-panel { display:flex; flex-direction:column; gap:10px; }
        .alert-card {
            padding:12px 14px; border-left:4px solid #f59e0b;
            background:#fffbeb; border-radius:8px; cursor:pointer; transition:all .2s;
        }
        .alert-card:hover { transform:translateX(3px); }
        .alert-card.critical { border-left-color:#ef4444; background:#fef2f2; }
        .alert-card.info     { border-left-color:#3b82f6; background:#eff6ff; }
        .alert-title { font-weight:600; font-size:13px; color:#111827; margin-bottom:3px; }
        .alert-desc  { font-size:12px; color:#6b7280; line-height:1.5; }

        /* ── Skeleton loader ── */
        .skeleton { background:linear-gradient(90deg,#f3f4f6 25%,#e5e7eb 50%,#f3f4f6 75%); background-size:400% 100%; animation:shimmer 1.4s ease infinite; border-radius:6px; }
        @keyframes shimmer { 0%{background-position:100% 0} 100%{background-position:-100% 0} }
        .skeleton-kpi-value { height:36px; width:70%; margin-bottom:10px; }
        .skeleton-kpi-line  { height:12px; width:90%; margin-bottom:6px; }

        /* ── Dark Theme Support ── */
        [data-theme="dark"] .saas-dashboard { background-color:#0f172a; color:#f8fafc; }

        [data-theme="dark"] .saas-filters {
            background:#1e293b; border:1px solid #334155;
            box-shadow:0 4px 6px -1px rgba(0,0,0,.3);
        }
        [data-theme="dark"] .saas-filters label { color:#94a3b8; }
        [data-theme="dark"] .saas-filters select {
            border-color:#334155; background:#0f172a; color:#f8fafc;
        }
        [data-theme="dark"] .saas-filters select:hover,
        [data-theme="dark"] .saas-filters select:focus {
            border-color:#818cf8; background:#1e293b;
        }
        [data-theme="dark"] .saas-btn-ghost { background:#334155; color:#f8fafc; }
        [data-theme="dark"] .saas-btn-ghost:hover { background:#475569; }
        [data-theme="dark"] #btn-email { background:#312e81 !important; color:#c7d2fe !important; }

        [data-theme="dark"] .saas-kpi-card {
            background:#1e293b; border:1px solid #334155;
            box-shadow:0 4px 6px -1px rgba(0,0,0,.3);
        }
        [data-theme="dark"] .saas-kpi-card:hover { box-shadow:0 16px 24px -4px rgba(0,0,0,.5); }
        [data-theme="dark"] .saas-kpi-title { color:#94a3b8; }
        [data-theme="dark"] .saas-kpi-value { color:#f8fafc; }
        [data-theme="dark"] .saas-kpi-details { color:#94a3b8; border-top-color:#334155; }
        [data-theme="dark"] .saas-kpi-details strong { color:#f1f5f9; }

        [data-theme="dark"] .icon-blue   { background:rgba(59,130,246,0.2); color:#60a5fa; }
        [data-theme="dark"] .icon-green  { background:rgba(16,185,129,0.2); color:#34d399; }
        [data-theme="dark"] .icon-purple { background:rgba(139,92,246,0.2); color:#a78bfa; }
        [data-theme="dark"] .icon-amber  { background:rgba(245,158,11,0.2); color:#fbbf24; }
        [data-theme="dark"] .icon-red    { background:rgba(239,68,68,0.2); color:#f87171; }

        [data-theme="dark"] .trend-up   { background:rgba(22,163,74,0.25); color:#4ade80; }
        [data-theme="dark"] .trend-down { background:rgba(220,38,38,0.25); color:#f87171; }
        [data-theme="dark"] .trend-flat { background:#334155; color:#94a3b8; }

        [data-theme="dark"] .saas-section {
            background:#1e293b; border:1px solid #334155;
            box-shadow:0 4px 6px -1px rgba(0,0,0,.3);
        }
        [data-theme="dark"] .saas-section-title { color:#f8fafc; }
        [data-theme="dark"] .saas-section-subtitle { color:#94a3b8; }
        [data-theme="dark"] #f-trend-group { background:#0f172a !important; color:#f8fafc !important; border-color:#334155 !important; }

        [data-theme="dark"] .saas-pipeline-card {
            background:#0f172a; border-color:#334155;
        }
        [data-theme="dark"] .saas-pipeline-card:hover {
            border-color:#818cf8; background:#1e293b; box-shadow:0 8px 16px -2px rgba(0,0,0,.4);
        }
        [data-theme="dark"] .saas-pipeline-card-title { color:#f8fafc; }
        [data-theme="dark"] .saas-pipeline-card-sub { color:#94a3b8; }

        [data-theme="dark"] .metric-box {
            background:#1e293b; border-color:#334155;
        }
        [data-theme="dark"] .metric-box.highlighted {
            background:rgba(99,102,241,0.15); border-color:rgba(99,102,241,0.4);
        }
        [data-theme="dark"] .metric-label { color:#94a3b8; }
        [data-theme="dark"] .metric-box.highlighted .metric-label { color:#a5b4fc; }
        [data-theme="dark"] .metric-value { color:#f8fafc; }
        [data-theme="dark"] .metric-box.highlighted .metric-value { color:#c7d2fe; }

        [data-theme="dark"] .table-modern th {
            background:#0f172a; color:#94a3b8; border-bottom-color:#334155;
        }
        [data-theme="dark"] .table-modern th:hover { color:#818cf8; }
        [data-theme="dark"] .table-modern td { border-bottom-color:#334155; color:#cbd5e1; }
        [data-theme="dark"] .table-modern td strong { color:#f8fafc; }
        [data-theme="dark"] .table-modern tbody tr:hover { background:#0f172a; }

        [data-theme="dark"] .alert-card {
            background:rgba(245,158,11,0.15); border-left-color:#f59e0b;
        }
        [data-theme="dark"] .alert-card.critical { background:rgba(239,68,68,0.15); border-left-color:#ef4444; }
        [data-theme="dark"] .alert-card.info     { background:rgba(59,130,246,0.15); border-left-color:#3b82f6; }
        [data-theme="dark"] .alert-title { color:#f8fafc; }
        [data-theme="dark"] .alert-desc  { color:#94a3b8; }
        [data-theme="dark"] #alert-count { background:rgba(220,38,38,0.3) !important; color:#f87171 !important; }

        [data-theme="dark"] .skeleton {
            background:linear-gradient(90deg,#1e293b 25%,#334155 50%,#1e293b 75%);
        }
    `);

    // ── HTML Scaffold ───────────────────────────────────────────────────────
    const html = `
    <div class="saas-dashboard">
        <!-- Filters -->
        <div class="saas-filters">
            <div class="saas-filter-group">
                <label>Period</label>
                <select id="f-period">
                    <option value="today">Today</option>
                    <option value="this_week">This Week</option>
                    <option value="last_30_days" selected>Last 30 Days</option>
                    <option value="this_month">This Month</option>
                    <option value="last_month">Last Month</option>
                    <option value="this_quarter">This Quarter</option>
                    <option value="this_year">This Year</option>
                </select>
            </div>
            <div class="saas-filter-group">
                <label>Product</label>
                <select id="f-product"><option value="all">All Products</option></select>
            </div>
            <div class="saas-filter-group">
                <label>User</label>
                <select id="f-team"><option value="all">All Users</option></select>
            </div>
            <div class="saas-filter-group">
                <label>Status</label>
                <select id="f-status">
                    <option value="all">All Statuses</option>
                </select>
            </div>
            <div class="saas-filter-actions">
                <button class="saas-btn saas-btn-ghost" id="btn-reset"><i class="fa fa-refresh"></i> Reset</button>
                <button class="saas-btn saas-btn-primary" id="btn-apply"><i class="fa fa-filter"></i> Apply Filters</button>
                <button class="saas-btn saas-btn-ghost" id="btn-email" style="background:#e0e7ff;color:#4338ca;"><i class="fa fa-envelope"></i> Email Report</button>
            </div>
        </div>

        <!-- KPI Cards -->
        <div class="saas-kpi-grid" id="kpi-grid">
            ${[
            { id: 'kpi-subs', color: 'blue', icon: '<i class="fa fa-file-text-o"></i>', title: 'New Subscriptions' },
            { id: 'kpi-new-rev', color: 'green', icon: '<i class="fa fa-money"></i>', title: 'First Payment Revenue' },
            { id: 'kpi-ren-rev', color: 'purple', icon: '<i class="fa fa-repeat"></i>', title: 'Renewal Revenue' },
            { id: 'kpi-total', color: 'amber', icon: '<i class="fa fa-bar-chart"></i>', title: 'Total Collection' },
            { id: 'kpi-churn', color: 'red', icon: '<i class="fa fa-exclamation-triangle"></i>', title: 'Not Renewed / Churned' },
        ].map(c => `
                <div class="saas-kpi-card kpi-color-${c.color}" id="${c.id}">
                    <div class="saas-kpi-icon icon-${c.color}">${c.icon}</div>
                    <div class="saas-kpi-title">${c.title}</div>
                    <div class="skeleton skeleton-kpi-value"></div>
                    <div class="skeleton skeleton-kpi-line"></div>
                    <div class="skeleton skeleton-kpi-line" style="width:60%"></div>
                </div>
            `).join('')}
        </div>

        <!-- Lead, Deal & Customer Acquisition Summary -->
        <div class="saas-section" style="margin-bottom:24px;">
            <div class="saas-section-title">
                <span><i class="fa fa-filter" style="color: #6366f1; margin-right: 8px;"></i> Pipeline & Acquisition Summary</span>
                <span class="saas-section-subtitle">Real-time Lead generation, Deal conversions, and Customer acquisitions</span>
            </div>
            <div class="saas-pipeline-grid" id="pipeline-metrics-grid">
                <div class="saas-pipeline-card" id="card-crm-lead">
                    <div class="saas-pipeline-card-header">
                        <div class="saas-pipeline-card-icon icon-blue"><i class="fa fa-user-plus"></i></div>
                        <div>
                            <div class="saas-pipeline-card-title">Leads Created</div>
                            <div class="saas-pipeline-card-sub">New prospective leads</div>
                        </div>
                    </div>
                    <div class="saas-pipeline-metrics">
                        <div class="metric-box">
                            <span class="metric-label">Today</span>
                            <span class="metric-value" id="m-leads-today">0</span>
                        </div>
                        <div class="metric-box">
                            <span class="metric-label">This Week</span>
                            <span class="metric-value" id="m-leads-week">0</span>
                        </div>
                        <div class="metric-box highlighted">
                            <span class="metric-label">This Month</span>
                            <span class="metric-value" id="m-leads-month">0</span>
                        </div>
                    </div>
                </div>

                <div class="saas-pipeline-card" id="card-crm-deal">
                    <div class="saas-pipeline-card-header">
                        <div class="saas-pipeline-card-icon icon-purple"><i class="fa fa-briefcase"></i></div>
                        <div>
                            <div class="saas-pipeline-card-title">Leads Converted to Deals</div>
                            <div class="saas-pipeline-card-sub">Leads qualified into active deals</div>
                        </div>
                    </div>
                    <div class="saas-pipeline-metrics">
                        <div class="metric-box">
                            <span class="metric-label">Today</span>
                            <span class="metric-value" id="m-deals-today">0</span>
                        </div>
                        <div class="metric-box">
                            <span class="metric-label">This Week</span>
                            <span class="metric-value" id="m-deals-week">0</span>
                        </div>
                        <div class="metric-box highlighted">
                            <span class="metric-label">This Month</span>
                            <span class="metric-value" id="m-deals-month">0</span>
                        </div>
                    </div>
                </div>

                <div class="saas-pipeline-card" id="card-customer">
                    <div class="saas-pipeline-card-header">
                        <div class="saas-pipeline-card-icon icon-green"><i class="fa fa-users"></i></div>
                        <div>
                            <div class="saas-pipeline-card-title">Customers Created</div>
                            <div class="saas-pipeline-card-sub">Onboarded paid & active accounts</div>
                        </div>
                    </div>
                    <div class="saas-pipeline-metrics">
                        <div class="metric-box">
                            <span class="metric-label">Today</span>
                            <span class="metric-value" id="m-cust-today">0</span>
                        </div>
                        <div class="metric-box">
                            <span class="metric-label">This Week</span>
                            <span class="metric-value" id="m-cust-week">0</span>
                        </div>
                        <div class="metric-box highlighted">
                            <span class="metric-label">This Month</span>
                            <span class="metric-value" id="m-cust-month">0</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Revenue Trend + Alerts -->
        <div class="grid-2-col">
            <div class="saas-section" style="margin-bottom:0">
                <div class="saas-section-title">
                    Revenue Trend
                    <span class="saas-section-subtitle">
                        <select id="f-trend-group" style="font-size:12px;padding:4px 8px;border:1px solid #e5e7eb;border-radius:6px;background:#f9fafb;">
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="monthly">Monthly</option>
                        </select>
                    </span>
                </div>
                <div id="chart-revenue"></div>
            </div>
            <div class="saas-section" style="margin-bottom:0">
                <div class="saas-section-title">
                    Requires Attention
                    <span class="badge badge-danger" id="alert-count" style="font-size:11px;padding:3px 8px;border-radius:12px;background:#fee2e2;color:#991b1b;">0</span>
                </div>
                <div class="alert-panel" id="alert-panel">
                    <div class="skeleton skeleton-kpi-line" style="height:56px;width:100%;border-radius:8px;"></div>
                    <div class="skeleton skeleton-kpi-line" style="height:56px;width:100%;border-radius:8px;"></div>
                </div>
            </div>
        </div>

        <!-- SaaS Product Performance -->
        <div class="saas-section">
            <div class="saas-section-title">SaaS Product Performance</div>
            <div class="table-responsive" id="product-table">
                <div class="skeleton" style="height:200px;border-radius:8px;"></div>
            </div>
        </div>

        <!-- User Performance -->
        <div class="saas-section">
            <div class="saas-section-title">User Leaderboard</div>
            <div class="table-responsive" id="sales-table">
                <div class="skeleton" style="height:200px;border-radius:8px;"></div>
            </div>
        </div>
    </div>`;

    $(page.main).empty().append(html);

    // ── State & Currency ────────────────────────────────────────────────────
    let currency = frappe.boot.sysdefaults.currency || 'USD';
    let revenueChart = null;

    function fmt_currency(val) {
        return format_currency(val, currency, 0);
    }

    function trend_badge(pct) {
        if (pct > 0) return `<span class="saas-kpi-trend trend-up"><i class="fa fa-arrow-up"></i> ${pct}%</span>`;
        if (pct < 0) return `<span class="saas-kpi-trend trend-down"><i class="fa fa-arrow-down"></i> ${Math.abs(pct)}%</span>`;
        return `<span class="saas-kpi-trend trend-flat"><i class="fa fa-minus"></i> 0%</span>`;
    }

    function get_filters() {
        return {
            period: $('#f-period').val() || 'last_30_days',
            product: $('#f-product').val() || 'all',
            team: $('#f-team').val() || 'all',
            status: $('#f-status').val() || 'all',
        };
    }

    // ── Populate filter dropdowns from server ───────────────────────────────
    frappe.call({
        method: 'xpertintegration.xpertintegration.page.saas_sales_dashboard.saas_sales_dashboard.get_filter_options',
        callback: r => {
            if (!r.message) return;
            const { projects, teams, statuses } = r.message;
            const $prod = $('#f-product');
            (projects || []).forEach(p => $prod.append(`<option value="${p}">${p}</option>`));
            const $team = $('#f-team');
            $team.empty().append('<option value="all">All Users</option>');
            (teams || []).forEach(t => {
                if (typeof t === 'object') {
                    $team.append(`<option value="${t.name}">${t.name}</option>`);
                } else {
                    $team.append(`<option value="${t}">${t}</option>`);
                }
            });
            const $status = $('#f-status');
            $status.empty().append('<option value="all">All Statuses</option>');
            (statuses || []).forEach(st => {
                $status.append(`<option value="${st}">${st}</option>`);
            });
        }
    });

    // ── KPI Render ──────────────────────────────────────────────────────────
    function render_kpis(d) {
        const s = d.subscriptions;
        $('#kpi-subs').html(`
            <div class="saas-kpi-icon icon-blue"><i class="fa fa-file-text-o"></i></div>
            <div class="saas-kpi-title">New Subscriptions</div>
            <div class="saas-kpi-value">${s.current}</div>
            ${trend_badge(s.change_pct)}
            <div class="saas-kpi-details">
                Today: <strong>${s.today}</strong><br>
                This Week: <strong>${s.this_week}</strong><br>
                This Period: <strong>${s.current}</strong>
            </div>
        `);

        const fp = d.first_payment;
        $('#kpi-new-rev').html(`
            <div class="saas-kpi-icon icon-green"><i class="fa fa-money"></i></div>
            <div class="saas-kpi-title">First Payment Revenue</div>
            <div class="saas-kpi-value">${fmt_currency(fp.revenue)}</div>
            ${trend_badge(fp.change_pct)}
            <div class="saas-kpi-details">
                New Paying Customers: <strong>${fp.paying_customers}</strong><br>
                Avg. First Payment: <strong>${fmt_currency(fp.avg_first_payment)}</strong><br>
                Conversion: <strong>${fp.conversion_pct}%</strong>
            </div>
        `);

        const rn = d.renewal;
        $('#kpi-ren-rev').html(`
            <div class="saas-kpi-icon icon-purple"><i class="fa fa-repeat"></i></div>
            <div class="saas-kpi-title">Renewal Revenue</div>
            <div class="saas-kpi-value">${fmt_currency(rn.revenue)}</div>
            ${trend_badge(rn.change_pct)}
            <div class="saas-kpi-details">
                Renewals: <strong>${rn.renewals}</strong><br>
                Renewal Rate: <strong>${rn.renewal_rate_pct}%</strong><br>
                Avg. Renewal Value: <strong>${fmt_currency(rn.avg_renewal_value)}</strong>
            </div>
        `);

        const tc = d.total_collection;
        $('#kpi-total').html(`
            <div class="saas-kpi-icon icon-amber"><i class="fa fa-bar-chart"></i></div>
            <div class="saas-kpi-title">Total Collection</div>
            <div class="saas-kpi-value">${fmt_currency(tc.revenue)}</div>
            ${trend_badge(tc.change_pct)}
            <div class="saas-kpi-details">
                New Customers: <strong>${fmt_currency(tc.new_revenue)}</strong><br>
                Renewals: <strong>${fmt_currency(tc.renewal_revenue)}</strong>
            </div>
        `);

        const ch = d.churn;
        const exp_lt_3 = ch.expired_lt_3 !== undefined ? ch.expired_lt_3 : (ch.expired_gt_3 || 0);
        const exp_lt_7 = ch.expired_lt_7 !== undefined ? ch.expired_lt_7 : (ch.expired_gt_7 || 0);
        $('#kpi-churn').html(`
            <div class="saas-kpi-icon icon-red"><i class="fa fa-exclamation-triangle"></i></div>
            <div class="saas-kpi-title">Not Renewed / Churned</div>
            <div class="saas-kpi-value">${ch.total}</div>
            ${trend_badge(ch.change_pct)}
            <div class="saas-kpi-details">
                Expired &lt; 3 Days: <strong>${exp_lt_3}</strong><br>
                Expired &lt; 7 Days: <strong>${exp_lt_7}</strong><br>
                Lost MRR: <strong>${fmt_currency(ch.lost_mrr)}</strong>
            </div>
        `);
    }

    // ── Revenue Trend Chart ─────────────────────────────────────────────────
    function render_trend(data) {
        const container = document.getElementById('chart-revenue');
        if (!container) return;
        if (revenueChart) {
            // Update existing chart
            revenueChart.update({
                labels: data.labels,
                datasets: [
                    { values: data.new_revenue },
                    { values: data.renewal_revenue },
                ]
            });
            return;
        }
        revenueChart = new frappe.Chart(container, {
            data: {
                labels: data.labels,
                datasets: [
                    { name: 'New Revenue', type: 'bar', values: data.new_revenue },
                    { name: 'Renewal Revenue', type: 'line', values: data.renewal_revenue },
                ]
            },
            type: 'axis-mixed',
            height: 280,
            colors: ['#6366f1', '#10b981'],
            tooltipOptions: {
                formatTooltipY: v => format_currency(v, currency, 0),
            }
        });
    }

    // ── Alerts ──────────────────────────────────────────────────────────────
    function render_alerts(alerts) {
        $('#alert-count').text(alerts.length);
        if (!alerts.length) {
            $('#alert-panel').html(`
                <div style="text-align:center;padding:30px;color:#9ca3af;font-size:13px;">
                    <i class="fa fa-check-circle" style="color:#10b981;font-size:16px;margin-right:6px;"></i> No critical alerts at this time.
                </div>
            `);
            return;
        }
        $('#alert-panel').html(alerts.map(a => `
            <div class="alert-card ${a.level || ''}" onclick="window.location.href='${a.link || '#'}'">
                <div class="alert-title">${a.title}</div>
                <div class="alert-desc">${a.desc}</div>
            </div>
        `).join(''));
    }

    // ── Product Table ────────────────────────────────────────────────────────
    function render_product_table(rows) {
        if (!rows || !rows.length) {
            $('#product-table').html('<p style="color:#9ca3af;text-align:center;padding:20px">No product data available.</p>');
            return;
        }
        const thead = `<thead><tr>
            <th>Product</th><th>New Subs</th><th>New Revenue</th>
            <th>Renewals</th><th>Renewal Rev</th><th>Active Subs</th>
            <th>Renewal Rate</th><th>Total Rev</th>
        </tr></thead>`;
        const tbody = rows.map(r => `<tr>
            <td><strong>${r.product}</strong></td>
            <td>${r.new_subs}</td>
            <td>${fmt_currency(r.new_revenue)}</td>
            <td>${r.renewals}</td>
            <td>${fmt_currency(r.renewal_revenue)}</td>
            <td>${r.active_subs}</td>
            <td>${r.renewal_rate}%</td>
            <td><strong>${fmt_currency(r.total_revenue)}</strong></td>
        </tr>`).join('');
        $('#product-table').html(`<table class="table-modern">${thead}<tbody>${tbody}</tbody></table>`);
    }

    // ── Sales Table ──────────────────────────────────────────────────────────
    function render_sales_table(rows) {
        if (!rows || !rows.length) {
            $('#sales-table').html('<p style="color:#9ca3af;text-align:center;padding:20px">No sales data available.</p>');
            return;
        }
        const thead = `<thead><tr>
            <th>Rank</th><th>User Name</th><th>Role Profile</th>
            <th>Leads</th><th>Paid Customers</th><th>Conversion</th>
            <th>Total Revenue</th><th>Commission</th>
        </tr></thead>`;
        const tbody = rows.map(r => {
            const rank_class = r.rank === 1 ? 'gold' : r.rank === 2 ? 'silver' : r.rank === 3 ? 'bronze' : '';
            return `<tr>
                <td><span class="badge-rank ${rank_class}">${r.rank}</span></td>
                <td><strong>${r.salesperson}</strong></td>
                <td>${r.team}</td>
                <td>${r.leads}</td>
                <td>${r.paid_customers}</td>
                <td>${r.conversion_pct}%</td>
                <td>${fmt_currency(r.total_revenue)}</td>
                <td>${fmt_currency(r.commission)}</td>
            </tr>`;
        }).join('');
        $('#sales-table').html(`<table class="table-modern">${thead}<tbody>${tbody}</tbody></table>`);
    }

    // ── Master refresh: call all APIs concurrently ──────────────────────────
    function refresh_dashboard() {
        const f = get_filters();
        const groupby = $('#f-trend-group').val() || 'daily';

        // Show skeleton on KPIs
        ['kpi-subs', 'kpi-new-rev', 'kpi-ren-rev', 'kpi-total', 'kpi-churn'].forEach(id => {
            $(`#${id}`).find('.saas-kpi-value,.saas-kpi-trend,.saas-kpi-details').remove();
            $(`#${id}`).append(`
                <div class="skeleton skeleton-kpi-value"></div>
                <div class="skeleton skeleton-kpi-line"></div>
                <div class="skeleton skeleton-kpi-line" style="width:60%"></div>
            `);
        });

        // KPIs
        frappe.call({
            method: 'xpertintegration.xpertintegration.page.saas_sales_dashboard.saas_sales_dashboard.get_top_kpis',
            args: { period: f.period, product: f.product, team: f.team, status: f.status },
            callback: r => { if (r.message) { currency = r.message.currency || currency; render_kpis(r.message); } }
        });

        // Revenue Trend
        frappe.call({
            method: 'xpertintegration.xpertintegration.page.saas_sales_dashboard.saas_sales_dashboard.get_revenue_trend',
            args: { period: f.period, product: f.product, team: f.team, groupby },
            callback: r => { if (r.message) render_trend(r.message); }
        });

        // Alerts
        frappe.call({
            method: 'xpertintegration.xpertintegration.page.saas_sales_dashboard.saas_sales_dashboard.get_management_alerts',
            args: { product: f.product, team: f.team },
            callback: r => { if (r.message) render_alerts(r.message); }
        });

        // Product Performance
        frappe.call({
            method: 'xpertintegration.xpertintegration.page.saas_sales_dashboard.saas_sales_dashboard.get_product_performance',
            args: { period: f.period, team: f.team },
            callback: r => { if (r.message) render_product_table(r.message); }
        });

        // Sales Leaderboard
        frappe.call({
            method: 'xpertintegration.xpertintegration.page.saas_sales_dashboard.saas_sales_dashboard.get_sales_performance',
            args: { period: f.period, product: f.product, team: f.team },
            callback: r => { if (r.message) render_sales_table(r.message); }
        });

        // Pipeline Conversion & Acquisition Metrics
        frappe.call({
            method: 'xpertintegration.xpertintegration.page.saas_sales_dashboard.saas_sales_dashboard.get_lead_conversion_metrics',
            args: { product: f.product, team: f.team, status: f.status },
            callback: r => {
                if (r.message) {
                    const m = r.message;
                    $('#m-leads-today').text(m.leads ? m.leads.today : 0);
                    $('#m-leads-week').text(m.leads ? m.leads.this_week : 0);
                    $('#m-leads-month').text(m.leads ? m.leads.this_month : 0);

                    $('#m-deals-today').text(m.deals ? m.deals.today : 0);
                    $('#m-deals-week').text(m.deals ? m.deals.this_week : 0);
                    $('#m-deals-month').text(m.deals ? m.deals.this_month : 0);

                    $('#m-cust-today').text(m.customers ? m.customers.today : 0);
                    $('#m-cust-week').text(m.customers ? m.customers.this_week : 0);
                    $('#m-cust-month').text(m.customers ? m.customers.this_month : 0);
                }
            }
        });
    }

    // ── Email Dialog & Event Bindings ───────────────────────────────────────
    function open_email_dialog() {
        const dialog = new frappe.ui.Dialog({
            title: __('Email SaaS KPI Report'),
            fields: [
                {
                    label: __('Recipients'),
                    fieldname: 'recipients',
                    fieldtype: 'Small Text',
                    reqd: 1,
                    default: frappe.session.user_email || frappe.session.user,
                    description: __('Enter recipient email addresses separated by commas.')
                },
                {
                    label: __('Optional Note / Executive Summary'),
                    fieldname: 'message',
                    fieldtype: 'Small Text',
                    description: __('Include a custom note with this report.')
                }
            ],
            primary_action_label: __('Send Email'),
            primary_action: function (values) {
                const f = get_filters();
                dialog.get_primary_btn().prop('disabled', true).text(__('Sending...'));

                frappe.call({
                    method: 'xpertintegration.xpertintegration.page.saas_sales_dashboard.saas_sales_dashboard.send_kpi_report_email',
                    args: {
                        recipients: values.recipients,
                        period: f.period,
                        product: f.product,
                        team: f.team,
                        status: f.status,
                        message: values.message || ''
                    },
                    callback: function (r) {
                        dialog.hide();
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __('KPI Report sent successfully!'),
                                indicator: 'green'
                            });
                        }
                    },
                    always: function () {
                        dialog.get_primary_btn().prop('disabled', false).text(__('Send Email'));
                    }
                });
            }
        });
        dialog.show();
    }

    $('#btn-apply').on('click', refresh_dashboard);
    $('#btn-email').on('click', open_email_dialog);

    $('#card-crm-lead').on('click', function () {
        frappe.set_route('List', 'CRM Lead');
    });

    $('#card-crm-deal').on('click', function () {
        frappe.set_route('List', 'CRM Deal');
    });

    $('#card-customer').on('click', function () {
        frappe.set_route('List', 'Customer');
    });

    let filterTimer = null;
    $('#f-period, #f-product, #f-team, #f-status').on('change blur', () => {
        clearTimeout(filterTimer);
        filterTimer = setTimeout(() => {
            refresh_dashboard();
        }, 150);
    });

    $('#btn-reset').on('click', () => {
        $('#f-period').val('last_30_days');
        $('#f-product').val('all');
        $('#f-team').val('all');
        $('#f-status').val('all');
        $('#f-trend-group').val('daily');
        refresh_dashboard();
    });

    $('#f-trend-group').on('change', () => {
        const f = get_filters();
        const groupby = $('#f-trend-group').val() || 'daily';
        frappe.call({
            method: 'xpertintegration.xpertintegration.page.saas_sales_dashboard.saas_sales_dashboard.get_revenue_trend',
            args: { period: f.period, product: f.product, team: f.team, groupby },
            callback: r => { if (r.message) render_trend(r.message); }
        });
    });

    // ── Initial Load ─────────────────────────────────────────────────────────
    refresh_dashboard();
};
# Design & Implement ERPNext SaaS Sales Management Dashboard

Act as a **Senior ERPNext/Frappe Developer, SaaS Revenue Analyst, and Enterprise UX Designer**.

We have an existing ERPNext-based system that manages subscriptions, customers, payments, renewals, leads, sales teams, sales ownership, and commissions for multiple SaaS products.

Current SaaS products include:

- NetWala
- Sale Desk
- MeshBill
- Other current/future SaaS products

We need to create a **custom ERPNext dashboard for Manager / Director level users**.

The dashboard should help management understand the current business position within a few seconds and then drill down into the details.

The dashboard must focus on:

1. New subscriptions
2. First-time payments
3. Renewal payments
4. Expired subscriptions
5. Failed/non-renewed customers
6. Revenue
7. SaaS/product-wise performance
8. Salesperson and sales-team performance
9. Sales commissions
10. Lead-to-paid-customer conversion
11. Trends and management alerts

---

# 1. DASHBOARD NAME

Use:

**SaaS Business & Sales Dashboard**

Subtitle:

**Subscriptions • Revenue • Renewals • Sales Performance**

---

# 2. USER LEVEL

The main users are:

- Director
- Business Manager
- Sales Manager
- Finance/Accounts Manager

The dashboard should therefore be **management oriented**, not an operational transaction screen.

Management should immediately be able to answer:

- How are we doing today?
- How much did we sell?
- Which SaaS product is performing best?
- Which SaaS product is losing customers?
- How many subscriptions are expiring?
- How many expired customers have not renewed?
- How much money came from new customers?
- How much money came from renewals?
- Which salesperson/team is performing best?
- Who is generating revenue versus only generating leads?
- What commissions are becoming payable?
- Are sales improving or declining?
- Where should management intervene?

---

# 3. GLOBAL DASHBOARD FILTERS

Create a compact filter bar at the top.

Filters:

### Date Period
Quick options:

- Today
- Yesterday
- Last 7 Days
- This Week
- Last Week
- This Month
- Last Month
- Last 30 Days
- This Quarter
- This Year
- Custom Date Range

### SaaS Product
Dropdown:

- All Products
- NetWala
- Sale Desk
- MeshBill
- dynamically load any additional SaaS product

### Sales Team

- All Teams
- individual team

### Salesperson

- All Salespersons
- individual salesperson

### Subscription Status

Optional:

- Active
- Trial
- Expiring
- Expired
- Cancelled

Filters should update all applicable dashboard cards/charts without reloading the complete page where possible.

Add:

**Reset Filters**

---

# 4. TOP EXECUTIVE KPI SECTION

Do not create 10–15 separate large KPI boxes.

Use approximately **5–6 compact management cards** with primary numbers and smaller supporting statistics inside each card.

---

## CARD 1 – SUBSCRIPTIONS

Large number:

### New Subscriptions
Example:

**37**

Small information underneath:

Today: 7  
This Week: 18  
This Month: 37

Also show:

▲ / ▼ percentage compared with previous equivalent period.

Example:

**+18.4% vs previous month**

---

## CARD 2 – NEW CUSTOMER REVENUE

Large figure:

### First Payment Revenue

Example:

**PKR 485,000**

Supporting information:

- New Paying Customers: 29
- Avg. First Payment: PKR 16,724
- Conversion from New Subscription: 78%

Clearly distinguish this from renewal revenue.

---

## CARD 3 – RENEWAL REVENUE

Large figure:

### Renewal Revenue

Example:

**PKR 1.82M**

Supporting:

- Renewals: 213
- Renewal Rate: 82%
- Avg. Renewal Value: PKR 8,545

Show trend versus previous period.

---

## CARD 4 – TOTAL COLLECTION

Large:

### Total Revenue Collected

Example:

**PKR 2.31M**

Small breakdown:

New Customers: PKR 485K  
Renewals: PKR 1.82M

And:

Collection Growth: +12.8%

---

## CARD 5 – EXPIRED / LOST SUBSCRIPTIONS

Main:

### Not Renewed

Example:

**46**

Small breakdown:

Expired > 3 Days: 12  
Expired > 7 Days: 19  
Expired > 30 Days: 15

Also calculate:

**Lost / At-Risk MRR**

Example:

PKR 184,500

Make this card visually alert-oriented without excessive use of bright red.

---

## CARD 6 – SALES TEAM

Main:

### Active Sales Performance

Example:

**29 New Paying Customers**

Supporting:

- Active Salespersons: 8
- Total Leads: 324
- Lead → Paid Conversion: 8.9%
- Commission Generated: PKR 118K

---

# 5. PRODUCT PERFORMANCE SECTION

Create a section:

## SaaS Product Performance

Show one row/card per SaaS product.

Example structure:

| Product | New Subs | New Revenue | Renewals | Renewal Revenue | Active Subs | Expired | Renewal Rate | Total Revenue |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NetWala | | | | | | | | |
| Sale Desk | | | | | | | | |
| MeshBill | | | | | | | | |

Do not hardcode products.

Products should be dynamically generated from the SaaS/Product master.

Allow sorting by:

- Total Revenue
- New Subscriptions
- Renewals
- Active Subscribers
- Renewal Rate
- Lost Customers

Clicking the SaaS product should drill down to the relevant subscription/customer list.

---

# 6. REVENUE TREND CHART

Create a wide chart:

## Revenue Trend

Default:

Last 30 days.

Allow:

- Daily
- Weekly
- Monthly

Use two series:

**New Customer Revenue**

and

**Renewal Revenue**

Also show optional third line:

**Total Revenue**

This is important because management needs to see whether growth is coming from new customer acquisition or retention.

Tooltip should show:

Date  
New Revenue  
Renewal Revenue  
Total

---

# 7. SUBSCRIPTION TREND

Create another chart:

## Subscription Movement

Show:

- New Subscriptions
- Renewed
- Expired
- Cancelled

Use daily/weekly/monthly grouping depending upon selected period.

This will visually identify whether new subscriptions are compensating for churn.

---

# 8. RENEWAL HEALTH / RETENTION

Create a management panel:

## Renewal Health

Show:

### Renewal Rate
Example:

**82.4%**

Additional breakdown:

- Renewed Before Expiry
- Renewed on Expiry Date
- Renewed within 3 Days
- Renewed within 7 Days
- Not Renewed after 7 Days
- Not Renewed after 30 Days

Include a funnel or horizontal bar visualization.

---

# 9. EXPIRED & NOT RENEWED ANALYTICS

This is a critical area.

Create a section:

## Expired & Not Renewed

Cards/tabs:

### Last 3 Days
Number of subscriptions expired and still unpaid.

### Last 7 Days
Number still unpaid.

### Last 30 Days
Number still unpaid.

For each period calculate:

- Number of Customers
- Number of Subscriptions
- Expected Renewal Value
- Assigned Salesperson
- SaaS Product

Also provide:

**View Customers**

Clicking should open a filtered ERPNext report/list.

Example:

`subscription_status = Expired`

and

`renewal_payment = Not Received`

and the selected aging period.

---

# 10. RENEWAL AGING

Create an aging chart similar to receivable aging:

## Renewal Aging

Buckets:

- 0–3 Days Expired
- 4–7 Days
- 8–15 Days
- 16–30 Days
- 31–60 Days
- 60+ Days

For each bucket show:

- Subscribers
- Expected Revenue
- % of total expired subscriptions

This should help the sales team prioritize recovery efforts.

---

# 11. PRODUCT REVENUE MIX

Create a donut/pie visualization:

## Revenue by SaaS Product

Example:

NetWala – 45%  
Sale Desk – 32%  
MeshBill – 18%  
Others – 5%

Allow switching between:

- Total Revenue
- New Revenue
- Renewal Revenue

---

# 12. SALES TEAM PERFORMANCE

Create a strong management section:

# Sales Performance

Show a leaderboard/table.

Columns:

- Rank
- Salesperson
- Team
- Leads Assigned
- Leads Contacted
- Qualified Leads
- New Subscriptions
- First Payments
- First Payment Revenue
- Renewals
- Renewal Revenue
- Total Revenue
- Conversion %
- Renewal %
- Commission Generated

Example:

| Rank | Salesperson | Leads | Paid Customers | Conversion | New Revenue | Renewal Revenue | Total | Commission |
|---|---|---:|---:|---:|---:|---:|---:|---:|

Allow sorting by every major metric.

Default ranking:

**Total Revenue**

---

# 13. SALES TEAM SUMMARY

Above the detailed salesperson table, display team-level cards.

Example:

### Team A
Revenue: PKR 850K  
New Customers: 42  
Conversion: 14.2%  
Commission: PKR 65K

### Team B
Revenue: PKR 720K  
New Customers: 35  
Conversion: 11.8%  
Commission: PKR 51K

Click team to filter salesperson performance.

---

# 14. SALES FUNNEL

Create:

## Sales Funnel

Stages should be based on our actual lead workflow.

Example:

Leads Assigned  
↓  
Contacted  
↓  
Qualified  
↓  
Demo / Trial  
↓  
Subscription Created  
↓  
First Payment Received

Show:

- count at each stage
- conversion %
- drop-off %

Example:

500 Leads  
320 Contacted – 64%  
180 Qualified – 56%  
110 Trials – 61%  
75 Subscriptions – 68%  
62 Paid – 83%

Also calculate:

### Overall Lead → Paid Conversion

---

# 15. LEAD SOURCE ANALYTICS

If lead source exists, add:

## Lead Source Performance

Examples:

- Facebook
- Google
- Referral
- WhatsApp
- Website
- Direct
- Existing Customer Referral
- Sales Outreach

Metrics:

- Leads
- Paying Customers
- Conversion Rate
- Revenue
- Average Customer Value

This will help management understand which marketing channels generate actual paying customers.

---

# 16. COMMISSION DASHBOARD

Create a section:

## Sales Commission

Top statistics:

**Commission Generated**

**Commission Approved**

**Commission Paid**

**Commission Pending**

Example:

Generated: PKR 185K  
Approved: PKR 150K  
Paid: PKR 112K  
Pending: PKR 73K

Detailed salesperson table:

- Salesperson
- New Sales Revenue
- Renewal Revenue
- Eligible Commission
- Approved Commission
- Paid Commission
- Pending Commission

Commission values must use the existing commission rules in the system.

Do not calculate commission independently if the application already maintains commission entries.

---

# 17. CUSTOMER LIFECYCLE ANALYTICS

Where data allows, show:

## Customer Lifecycle

Metrics:

- Trial Customers
- New Paying Customers
- Active Paid Customers
- Renewed Customers
- Expired Customers
- Cancelled Customers
- Reactivated Customers

Calculate:

### Customer Churn Rate

Formula conceptually:

Customers lost during period / Active customers at beginning of period

Also show:

### Reactivation Rate

Expired customers who later became active again.

---

# 18. MRR / RECURRING REVENUE

If subscription plans have recurring billing, calculate:

## Monthly Recurring Revenue

Show:

**Current MRR**

**New MRR**

**Renewed MRR**

**Lost MRR**

**Net MRR Change**

Example:

Current MRR: PKR 4.8M  
New MRR: +PKR 380K  
Expansion/Upgrade: +PKR 75K  
Lost MRR: -PKR 190K  
Net Change: +PKR 265K

Where packages are monthly/quarterly/yearly, normalize values correctly before calculating MRR.

---

# 19. PLAN / PACKAGE PERFORMANCE

Add:

## Top Selling Plans

Columns:

- SaaS Product
- Package
- New Sales
- Active Subscribers
- Renewal Rate
- Revenue
- Avg Revenue / Customer

This can help management identify which subscription package is most successful.

---

# 20. MANAGEMENT ALERTS

Create a compact panel:

# Requires Attention

Do not simply display static alerts.

Generate alerts based on data conditions.

Examples:

### 23 subscriptions expired during the last 3 days
Expected renewal value: PKR 115K

### Sale Desk renewal rate fell to 67%
Previous period: 81%

### Team B conversion fell by 18%

### 14 high-value subscriptions expire within the next 7 days

### PKR 73K sales commission pending approval

### NetWala generated 28% more new subscriptions this week

Each item should be clickable when possible.

---

# 21. UPCOMING RENEWALS

Although the main requirement is expired subscriptions, management also needs to see what is coming.

Create:

## Upcoming Renewals

Buckets:

- Today
- Next 3 Days
- Next 7 Days
- Next 30 Days

For each show:

- Number of subscriptions
- Expected value

Example:

Today  
17 subscriptions  
PKR 122K

Next 7 Days  
84 subscriptions  
PKR 715K

Click should open customer/subscription list.

---

# 22. RECENT SALES ACTIVITY

At the bottom, add a compact live activity area:

## Recent Activity

Examples:

**12:35 PM**  
Sale Desk subscription activated – PKR 12,000  
Salesperson: Ali

**12:17 PM**  
NetWala renewal received – PKR 8,500

**11:58 AM**  
MeshBill yearly subscription activated – PKR 36,000

Limit to approximately 10–15 most recent important events.

---

# 23. DATE LOGIC

Use clearly defined business logic.

### New Subscription

Count subscription according to the actual activation/creation business event used by our application.

Do not count:

- draft
- test
- cancelled
- duplicate

unless business rules indicate otherwise.

---

### First-Time Payment

A payment received from a customer/subscription where no previous successful subscription payment exists for that subscription/customer relationship.

This should be classified as:

**New Customer Revenue**

---

### Renewal Payment

A successful payment made for continuation/extension of an existing subscription.

Classify as:

**Renewal Revenue**

Do not include first payment in renewal revenue.

---

### Expired Not Renewed

Subscription where:

`subscription_end_date < today`

AND

there is no successful renewal extending the subscription beyond the previous expiry date.

---

# 24. IMPORTANT – DISTINGUISH CUSTOMERS AND SUBSCRIPTIONS

One customer may potentially have:

- more than one SaaS product
- multiple subscriptions
- different plans

Therefore do not mix:

**Customer Count**

with

**Subscription Count**

Where relevant, show both.

Example:

12 Customers  
15 Subscriptions

---

# 25. DRILL-DOWN

Every major KPI should support drill-down.

Examples:

Click:

**29 New Customers**

→ open filtered new customer/subscription report.

Click:

**46 Not Renewed**

→ show expired subscriptions.

Click:

**PKR 1.82M Renewal Revenue**

→ show underlying payment transactions.

Click salesperson:

→ open salesperson dashboard/profile filtered to selected dates.

Use ERPNext routes/query filters.

---

# 26. ERPNext / FRAPPE IMPLEMENTATION

Build this as a proper custom Frappe/ERPNext dashboard.

Prefer:

- Custom Workspace / Dashboard Page
- Frappe Page
- Server-side whitelisted methods
- Query Reports where suitable
- Frappe Charts
- existing ERPNext standard UI components
- reusable JavaScript components

Avoid placing heavy SQL queries directly in client-side code.

Use server-side aggregation.

---

# 27. PERFORMANCE

This dashboard may eventually contain thousands or hundreds of thousands of:

- payments
- subscriptions
- leads
- customers

Therefore optimize queries.

Use:

- proper SQL indexes
- aggregated queries
- date filtering
- group by operations
- caching where appropriate

Avoid calling the server separately for every dashboard card.

Prefer APIs such as:

`get_dashboard_summary(filters)`

`get_revenue_trend(filters)`

`get_subscription_analytics(filters)`

`get_sales_performance(filters)`

`get_renewal_analytics(filters)`

---

# 28. RESPONSIVE UX

Dashboard must work properly on:

- 1920×1080 desktop
- laptop screens
- tablet

Desktop is the priority.

Use a clean enterprise ERP visual style.

Avoid:

- oversized cards
- unnecessary empty spaces
- excessive gradients
- excessive colours
- decorative elements that do not provide information

Use colour with meaning:

Green:
Positive growth / active / renewed

Amber:
Expiring / requires attention

Red:
Expired / churn / declining

Blue:
Revenue / neutral business information

Purple or another subtle accent:
New subscriptions / acquisition

---

# 29. INFORMATION HIERARCHY

Page structure should approximately be:

### Header
SaaS Business & Sales Dashboard  
Filters

### Row 1
Executive KPI Cards

### Row 2
Revenue Trend – 2/3 width  
Revenue by SaaS Product – 1/3 width

### Row 3
Product Performance Table

### Row 4
Subscription Movement  
Renewal Health

### Row 5
Expired / Not Renewed  
Renewal Aging

### Row 6
Upcoming Renewals

### Row 7
Sales Team Performance

### Row 8
Sales Funnel  
Team Performance

### Row 9
Sales Commission

### Row 10
Management Alerts / Recent Activity

Maintain a compact layout so important information appears above the fold.

---

# 30. COMPARISON WITH PREVIOUS PERIOD

For important metrics calculate comparison automatically.

If filter = Today:

Compare with yesterday.

If = This Week:

Compare with previous week.

If = This Month:

Compare with previous month.

If = Custom Date Range:

Compare with immediately preceding equivalent date range.

Example:

**PKR 2.31M**
▲ 13.2%

Previous period: PKR 2.04M

---

# 31. MANAGEMENT TOOLTIP

For charts and KPIs, provide meaningful tooltips.

Example:

### Renewal Rate

`82.4% of subscriptions due for renewal during this period successfully renewed.`

This helps prevent misinterpretation.

---

# 32. EXPORT

Allow exporting management data where appropriate to:

- Excel
- CSV

Reports that should support export:

- Product Performance
- Expired Customers
- Upcoming Renewals
- Salesperson Performance
- Commission Report

---

# 33. PERMISSIONS

Respect ERPNext permissions.

Director:

Can see all SaaS products and teams.

Sales Manager:

Can see assigned teams/products according to permission rules.

Salesperson:

If this dashboard is later made available to them, they should only see their own leads/customers/commission.

Do not expose information by bypassing ERPNext permission controls.

---

# 34. FIRST STEP BEFORE DEVELOPMENT

Before writing code:

1. Review our existing ERPNext/Frappe application.
2. Identify relevant DocTypes for:
   - SaaS Product
   - Subscription
   - Subscription Plan
   - Customer
   - Payment
   - Lead
   - Salesperson
   - Sales Team
   - Commission
3. Identify actual field names.
4. Identify current subscription statuses and sales stages.
5. Identify how first payment and renewal payment are recorded.
6. Identify the relationship between leads, customers, subscriptions and salespersons.
7. Identify how commission ownership/rules are recorded.
8. Reuse existing DocTypes and fields wherever possible.
9. Do not create duplicate data structures unnecessarily.

Then prepare a short mapping such as:

`Dashboard Metric → DocType → Field → Calculation`

before implementation.

---

# 35. REQUIRED OUTPUT

Proceed in this order:

### Phase 1 – Existing System Review
Review existing DocTypes and field relationships.

### Phase 2 – Data Mapping
Prepare metric-to-field mapping.

### Phase 3 – Dashboard Wireframe
Create the proposed desktop layout and component structure.

### Phase 4 – Backend
Develop optimized server-side APIs/queries.

### Phase 5 – Frontend
Build the ERPNext dashboard interface.

### Phase 6 – Drilldowns
Connect cards, tables and charts to filtered ERPNext reports/lists.

### Phase 7 – Validation
Validate calculations against actual subscription and payment transactions.

### Phase 8 – UX Review
Review responsive design, spacing, readability and management usability.

---

# PRIMARY DESIGN PRINCIPLE

This dashboard is not intended to simply show as many statistics as possible.

The dashboard should help a Director answer four questions quickly:

**1. Are sales growing?**

**2. Are customers renewing?**

**3. Where are we losing revenue/customers?**

**4. Which product, salesperson and sales team is performing or underperforming?**

Design every KPI, chart and interaction around these management questions.
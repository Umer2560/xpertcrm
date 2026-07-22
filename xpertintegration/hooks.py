app_name = "xpertintegration"
app_title = "XpertIntegration"
app_publisher = "MM and contributors"
app_description = "XpertIntegration is an all-in-one communication and data synchronization platform designed to bridge the gaps between your digital tools. By centralizing messaging and automating seamless data transfers across disparate platforms, XpertIntegration eliminates silos, boosts productivity, and ensures your information is always exactly where you need it—whenever you need it."
app_email = "admin@example.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "xpertintegration",
# 		"logo": "/assets/xpertintegration/logo.png",
# 		"title": "XpertIntegration",
# 		"route": "/xpertintegration",
# 		"has_permission": "xpertintegration.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/xpertintegration/css/xpertintegration.css"
# app_include_js = "/assets/xpertintegration/js/xpertintegration.js"

# include js, css files in header of web template
# web_include_css = "/assets/xpertintegration/css/xpertintegration.css"
# web_include_js = "/assets/xpertintegration/js/xpertintegration.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "xpertintegration/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "xpertintegration/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "xpertintegration.utils.jinja_methods",
# 	"filters": "xpertintegration.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "xpertintegration.install.before_install"
# after_install = "xpertintegration.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "xpertintegration.uninstall.before_uninstall"
# after_uninstall = "xpertintegration.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "xpertintegration.utils.before_app_install"
# after_app_install = "xpertintegration.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "xpertintegration.utils.before_app_uninstall"
# after_app_uninstall = "xpertintegration.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "xpertintegration.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "xpertintegration.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Subscription Plan": {
        "after_insert": "xpertintegration.api.integration.send_subscription_data",
        "on_update": "xpertintegration.api.integration.send_subscription_data",
    },
    "CRM Lead": {
        "after_insert": "xpertintegration.api.integration.after_crm_lead_insert",
    },
    "CRM Deal": {
        "validate": "xpertintegration.api.integration.validate_crm_deal",
        "after_insert": "xpertintegration.api.integration.after_crm_deal_insert",
    },
    "Customer": {
        "before_insert": "xpertintegration.api.integration.before_customer_insert",
        "validate": "xpertintegration.api.integration.send_customer_data",
        "after_insert": "xpertintegration.api.integration.create_subscription_for_customer",
    },
    "Sales Invoice": {
        "before_insert": "xpertintegration.api.integration.before_sales_invoice_insert",
        "on_submit": "xpertintegration.api.integration.send_crm_invoice_data",
    },
    "Subscription": {
        "on_update": "xpertintegration.api.integration.send_subscription_status_data",
    },
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"xpertintegration.tasks.all"
# 	],
# 	"daily": [
# 		"xpertintegration.tasks.daily"
# 	],
# 	"hourly": [
# 		"xpertintegration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"xpertintegration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"xpertintegration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "xpertintegration.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "xpertintegration.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "xpertintegration.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "xpertintegration.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["xpertintegration.utils.before_request"]
# after_request = ["xpertintegration.utils.after_request"]

# Job Events
# ----------
# before_job = ["xpertintegration.utils.before_job"]
# after_job = ["xpertintegration.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"xpertintegration.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# Fixtures
# -----------
fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "XpertIntegration"]]},
]

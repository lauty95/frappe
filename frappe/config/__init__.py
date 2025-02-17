from __future__ import unicode_literals
import json
from six import iteritems
import frappe
from frappe import _
from frappe.desk.moduleview import (get_data, get_onboard_items, config_exists, get_module_link_items_from_list)

def get_modules_from_all_apps_for_user(user=None):
	if not user:
		user = frappe.session.user

	all_modules = get_modules_from_all_apps()
	global_blocked_modules = frappe.get_doc('User', 'Administrator').get_blocked_modules()
	user_blocked_modules = frappe.get_doc('User', user).get_blocked_modules()
	blocked_modules = global_blocked_modules + user_blocked_modules
	allowed_modules_list = [m for m in all_modules if m.get("module_name") not in blocked_modules]

	empty_tables_by_module = get_all_empty_tables_by_module()

	for module in allowed_modules_list:
		module_name = module.get("module_name")

		# Apply onboarding status
		if module_name in empty_tables_by_module:
			module["onboard_present"] = 1

		# Set defaults links
		module["links"] =  get_onboard_items(module["app"], frappe.scrub(module_name))[:5]

	return allowed_modules_list

def get_modules_from_all_apps():
	modules_list = []
	for app in frappe.get_installed_apps():
		modules_list += get_modules_from_app(app)
	return modules_list

def get_modules_from_app(app):
	active_domains = frappe.get_active_domains()
	exclude = [
		'Healthcare', 'Setup', 'Manufacturing', 'Restaurant', 'Hotels', 'Communication', 'E-commerce',
		'Core', 'Email', 'Geo', 'Desk', 'Printing', 'Contacts', 'Data Migration', 'Chat', 'Social',
		'ERPNext Integrations', 'Frappe Chat', 'Zenoti', 'unicommerce', 'Amazon', 'Argentina',
		'Custom', 'Portal', 'Ecommerce', 'Workflow', 'Ecommerce Integrations', 'shopify', 'Woocommerce', 'Tiendanube', 'Mercadolibre'
	]
	return [m for m in frappe.get_all('Module Def',
		filters={'app_name': app},
		fields=['module_name', 'app_name as app', 'restrict_to_domain']
	) if (m.get("restrict_to_domain") in active_domains and m.get('module_name') not in exclude) or (not m.get("restrict_to_domain") and m.get('module_name') not in exclude)]

def get_all_empty_tables_by_module():
	table_rows = frappe.qb.Field("table_rows")
	table_name = frappe.qb.Field("table_name")
	information_schema = frappe.qb.Schema("information_schema")

	empty_tables = (
		frappe.qb.from_(information_schema.tables)
		.select(table_name)
		.where(table_rows == 0)
	).run()

	empty_tables = {r[0] for r in empty_tables}

	results = frappe.get_all("DocType", fields=["name", "module"])
	empty_tables_by_module = {}

	for doctype, module in results:
		if "tab" + doctype in empty_tables:
			if module in empty_tables_by_module:
				empty_tables_by_module[module].append(doctype)
			else:
				empty_tables_by_module[module] = [doctype]
	return empty_tables_by_module

def is_domain(module):
	return module.get("category") == "Domains"

def is_module(module):
	return module.get("type") == "module"

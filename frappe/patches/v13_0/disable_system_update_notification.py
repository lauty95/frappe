from __future__ import unicode_literals
import frappe


def execute():
    frappe.reload_doc("core", "doctype", "system_settings")
    frappe.db.set_value('System Settings', None, "disable_system_update_notification", 1)

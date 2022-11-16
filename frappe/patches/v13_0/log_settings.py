from __future__ import unicode_literals
import frappe


def execute():
    frappe.db.set_value('Log Settings', None, "clear_error_log_after", 60)
    frappe.db.set_value('Log Settings', None, "clear_activity_log_after", 30)
    frappe.db.set_value('Log Settings', None, "clear_email_queue_after", 30)

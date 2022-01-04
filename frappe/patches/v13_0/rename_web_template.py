from __future__ import unicode_literals
import frappe


def execute():
    templates = [
        'Item Card Group', 'Product Card', 'Product Category Cards', 'Hero Slider', 'Primary Navbar', 'Section with Features', 'Section with Cards',
        'Section with Collapsible Content', 'Section with Image', 'Split Section with Image', 'Hero with Right Image', 'Section with Tabs', 'Section with CTA',
        'Full Width Image', 'Testimonial', 'Section with Small CTA', 'Section with Image Grid', 'Section with Embed', 'Slideshow', 'Standard Footer', 'Standard Navbar',
    ]
    frappe.db.delete("Web Template", {"name": ['in', templates]})
    frappe.db.commit()

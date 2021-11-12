from __future__ import unicode_literals, absolute_import
import frappe


def setear_fechas(doctype, dates=[], child_dates={}, related_doctype=''):
    """
    doctype (str): Quotation
    dates (list): ['transaction_date', 'valid_till']
    child_dates (dict): {'Payment Schedule': 'due_date'}
    related_doctype (str): 'Stock Ledger Entry'
    """
    import datetime

    def get_new_date(old_date):
        if not old_date:
            return

        old_time = None

        if type(old_date) == datetime.datetime:
            old_time = old_date.time()
            old_date = old_date.date()

        fecha_demo = datetime.date(2021, 7, 1)
        fecha_hoy = datetime.date.today()
        diff = (fecha_demo - old_date).days
        value = fecha_hoy - datetime.timedelta(days=diff)

        if old_time:
            return datetime.datetime.combine(value, old_time)

        return value

    docs = frappe.get_all(doctype, fields=['name'] + dates)

    for doc_data in docs:
        # Cambia las fechas al doctype en si
        for field_name in dates:
            value = get_new_date(doc_data[field_name])
            if value:
                frappe.db.set_value(doctype, doc_data['name'], field_name, value)

        # Cambia la fecha en los doctypes hijos, por ahora soporta cambiar un valor por doctype hijo
        for child_doctype, field in child_dates.items():
            children_docs = frappe.get_all(child_doctype, filters={'parent': doc_data['name']}, fields=['name', field])

            for children_doc in children_docs:
                value = get_new_date(children_doc[field])
                if value:
                    frappe.db.set_value(child_doctype, children_doc['name'], field, value)

        if related_doctype:
            relateds = frappe.get_all(related_doctype, filters={'voucher_no': doc_data['name']}, fields=['name', 'posting_date'])

            for related in relateds:
                value = get_new_date(related['posting_date'])
                if value:
                    frappe.db.set_value(related_doctype, related['name'], 'posting_date', value)

        frappe.db.commit()

        doc = frappe.get_doc(doctype, doc_data['name'])

        if doctype == 'Issue':
            try:
                update_issue(doc)
            except Exception as e:
                print(e)

        try:
            doc.set_status()
            frappe.db.set_value(doctype, doc_data['name'], 'status', doc.status)
            frappe.db.commit()
        except Exception as e:
            print(e)


def update_issue(doc):
    from erpnext.support.doctype.issue.issue import set_resolution_time, set_user_resolution_time
    set_resolution_time(issue=doc)
    set_user_resolution_time(issue=doc)
    doc.update_status()
    doc.save()
    frappe.db.commit()


def create_demo():
    import datetime

    try:
        year = datetime.date.today().year
        if not frappe.db.exists("Fiscal Year", year):
            fiscal_year = frappe.new_doc("Fiscal Year")
            fiscal_year.year = year
            fiscal_year.year_start_date = f"{year}-01-01"
            fiscal_year.year_end_date = f"{year}-12-31"
            fiscal_year.save()
            frappe.db.commit()

        fiscal_year = frappe.get_doc("Fiscal Year", year)
        global_defaults = frappe.get_single("Global Defaults")
        global_defaults.current_fiscal_year = fiscal_year.name
        global_defaults.save()
        frappe.db.commit()
    except Exception as e:
        print(str(e))

    # Stock
    setear_fechas('Stock Entry', dates=['posting_date'], related_doctype='Stock Ledger Entry')
    setear_fechas('Material Request', dates=['transaction_date', 'schedule_date'], child_dates={'Material Request Item': 'schedule_date'})
    setear_fechas('Stock Reconciliation', dates=['posting_date'])
    setear_fechas('Stock Reconciliation', dates=['posting_date'])
    setear_fechas('Landed Cost Voucher', dates=['posting_date'], child_dates={'Landed Cost Purchase Receipt': 'posting_date'})
    setear_fechas('Delivery Note', dates=['posting_date', 'lr_date'], related_doctype='Stock Ledger Entry')
    setear_fechas('Purchase Receipt', dates=['posting_date'], related_doctype='Stock Ledger Entry')
    setear_fechas('Delivery Trip', dates=['departure_time'], child_dates={'Delivery Stop': 'estimated_arrival'})
    setear_fechas('Batch', dates=['manufacturing_date'])
    setear_fechas('Serial No', dates=['warranty_expiry_date', 'amc_expiry_date'])
    setear_fechas('Item', dates=['end_of_life'])

    # Accounting
    setear_fechas('Sales Invoice', dates=['posting_date', 'due_date', 'po_date'], child_dates={'Payment Schedule': 'due_date', 'Sales Invoice Payment': 'clearance_date'}, related_doctype='GL Entry')
    setear_fechas('Journal Entry', dates=['posting_date', 'clearance_date', 'bill_date', 'bill_date', 'due_date'])
    setear_fechas('Purchase Invoice', dates=['posting_date', 'due_date', 'bill_date'], child_dates={'Payment Schedule': 'due_date'}, related_doctype='GL Entry')
    setear_fechas('Period Closing Voucher', dates=['transaction_date', 'posting_date'])
    setear_fechas('Accounting Period', dates=['start_date', 'end_date'])

    # Sales
    setear_fechas('Quotation', dates=['transaction_date', 'valid_till'], child_dates={'Payment Schedule': 'due_date'})
    setear_fechas('Sales Order', dates=['transaction_date', 'delivery_date', 'po_date'], child_dates={'Sales Order Item': 'delivery_date', 'Payment Schedule': 'due_date'})
    setear_fechas('Blanket Order', dates=['from_date', 'to_date'])
    setear_fechas('Installation Note', dates=['inst_date'])
    setear_fechas('Pricing Rule', dates=['valid_from', 'valid_upto'])

    #  Compras
    setear_fechas('Request for Quotation', dates=['transaction_date'], child_dates={'Request for Quotation Item': 'schedule_date'})
    setear_fechas('Supplier Quotation', dates=['transaction_date', 'valid_till'], child_dates={'Supplier Quotation Item': 'expected_delivery_date'})
    setear_fechas('Purchase Order', dates=['transaction_date', 'schedule_date', 'order_confirmation_date'], child_dates={'Purchase Order Item': 'schedule_date', 'Payment Schedule': 'due_date'})

    # CRM contact_date
    setear_fechas('Lead', dates=['contact_date', 'ends_on'])
    setear_fechas('Opportunity', dates=['transaction_date'])
    setear_fechas('Email Campaign', dates=['start_date', 'end_date'])
    setear_fechas('Social Media Post', dates=['scheduled_time'])
    setear_fechas('Contract', dates=['start_date'])

    #  Varios
    setear_fechas('ToDo', dates=['date'])

    # Support
    setear_fechas('Issue', dates=['opening_date', 'creation', 'resolution_date', 'first_responded_on', 'response_by', 'resolution_by'])

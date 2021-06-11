from __future__ import unicode_literals, absolute_import
import datetime
import frappe


def setear_fechas(doctype, dates=[], child_dates={}, related_doctype=''):
    """
    doctype (str): Quotation
    dates (list): ['transaction_date', 'valid_till']
    child_dates (dict): {'Payment Schedule': 'due_date'}
    related_doctype (str): 'Stock Ledger Entry'
    """

    def get_new_date(old_date):
        fecha_demo = datetime.date(2020, 12, 18)
        fecha_hoy = datetime.date.today()
        diff = (fecha_demo - old_date).days
        return fecha_hoy - datetime.timedelta(days=diff)

    docs = frappe.get_all(doctype, fields=['name'] + dates)

    for doc_data in docs:
        # Cambia las fechas al doctype en si
        for field_name in dates:
            value = get_new_date(doc_data[field_name])
            frappe.db.set_value(doctype, doc_data['name'], field_name, value)

        # Cambia la fecha en los doctypes hijos, por ahora soporta cambiar un valor por doctype hijo
        for child_doctype, field in child_dates.items():
            children_docs = frappe.get_all(child_doctype, filters={'parent': doc_data['name']}, fields=['name', field])

            for children_doc in children_docs:
                value = get_new_date(children_doc[field])
                frappe.db.set_value(child_doctype, children_doc['name'], field, value)

        if related_doctype:
            relateds = frappe.get_all(related_doctype, filters={'voucher_no': doc_data['name']}, fields=['name', 'posting_date'])

            for related in relateds:
                value = get_new_date(related['posting_date'])
                frappe.db.set_value(related_doctype, related['name'], 'posting_date', value)

        frappe.db.commit()

        doc = frappe.get_doc(doctype, doc_data['name'])
        try:
            doc.set_status()
            frappe.db.set_value(doctype, doc_data['name'], 'status', doc.status)
            frappe.db.commit()
        except Exception as e:
            print(e)


def setear_status():
    import frappe

    doctypes = [doctype['name'] for doctype in frappe.get_all('DocType', {'issingle': 0})]

    for doctype in doctypes:
        try:
            all_documents = [dt['name'] for dt in frappe.get_all(doctype)]
        except Exception:
            continue

        for dn in all_documents:
            doc = frappe.get_doc(doctype, dn)
            try:
                doc.set_status()
                frappe.db.set_value(doctype, dn, 'status', doc.status)
                frappe.db.commit()
            except Exception:
                break


def create_demo():
    # Stock
    setear_fechas('Stock Entry', dates=['posting_date'], related_doctype='Stock Ledger Entry')
    setear_fechas('Material Request', dates=['transaction_date', 'schedule_date'], child_dates={'Material Request Item': 'schedule_date'})
    setear_fechas('Stock Reconciliation', dates=['posting_date'])
    setear_fechas('Stock Reconciliation', dates=['posting_date'])
    setear_fechas('Landed Cost Voucher', dates=['posting_date'], child_dates={'Landed Cost Purchase Receipt': 'posting_date'})
    setear_fechas('Delivery Note', dates=['posting_date', 'lr_date'])
    setear_fechas('Delivery Trip', dates=['departure_time'])
    setear_fechas('Batch', dates=['manufacturing_date'])

    # Accounting
    setear_fechas('Sales Invoice', dates=['posting_date', 'due_date'], child_dates={'Payment Schedule': 'due_date'}, related_doctype='GL Entry')

    # Sales
    setear_fechas('Quotation', dates=['transaction_date', 'valid_till'], child_dates={'Payment Schedule': 'due_date'})

    # CRM
    setear_fechas('Opportunity', dates=['transaction_date'])
    setear_fechas('Email Campaign', dates=['start_date', 'end_date'])
    setear_fechas('Social Media Post', dates=['scheduled_time'])
    setear_fechas('Contract', dates=['start_date'])

    # Assets

    # Proyects

    # Support

    # WebSite

    setear_status()

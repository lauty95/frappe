# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from json.encoder import JSONEncoder
import datetime
import requests
from datetime import timedelta
from dateutil import parser

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.integrations.utils import create_payment_gateway, get_payment_gateway_controller
from frappe.utils import call_hook_method, validate_email_address


class Pagos360Settings(Document):

    supported_currencies = ["ARS"]

    def validate_transaction_currency(self, currency):
        if currency not in self.supported_currencies:
            frappe.throw(_("Please select another payment method. Pagos360 does not support transactions in currency '{0}'").format(currency))

    def validate(self):
        self.validate_recipients()
        create_payment_gateway("Pagos360")
        call_hook_method('payment_gateway_enabled', gateway="Pagos360")
        if not self.flags.ignore_mandatory:
            self.validate_pagos360_credentails()

    def validate_recipients(self):
        if self.recipients:
            for recipient in self.recipients.split(","):
                validate_email_address(recipient, True)

    def validate_pagos360_credentails(self):
        try:
            pagos360_settings = get_payment_gateway_controller("Pagos360")
            pago360 = Pagos360(pagos360_settings.get_password(fieldname="api_key", raise_exception=False) or self.api_key, pagos360_settings.sandbox)
            pago360.get_account()
        except Exception:
            frappe.throw(_("Invalid payment gateway credentials"))

    def get_payment_url(self, **kwargs):
        """
        Example response:

        {
            'status': 201,
            'response': {
                'id': 7851375,
                'type': 'payment_request',
                'state': 'pending',
                'created_at': '2021-09-28T11:57:50-03:00',
                'external_reference': 'ACC-PRQ-2021-00013-2',
                'payer_name': 'Megatone',
                'payer_email': 'franciscoproldan@gmail.com',
                'description': 'Payment Request for F-FACTA0040-00000001',
                'first_due_date': '2021-10-02T00:00:00-03:00',
                'first_total': 1210,
                'barcode': '29680000204000078513750012100021275000000000',
                'checkout_url': 'https://checkout.pagos360.com/payment-request/7386c98a-206c-11ec-bc5a-0e434aab092d',
                'barcode_url': 'https://api.pagos360.com/payment-request/barcode/7386c98a-206c-11ec-bc5a-0e434aab092d',
                'pdf_url': 'https://api.pagos360.com/payment-request/pdf/7386c98a-206c-11ec-bc5a-0e434aab092d',
                'back_url_success': 'http://127.0.0.1:8000',
                'back_url_pending': 'http://127.0.0.1:8000',
                'back_url_rejected': 'http://127.0.0.1:8000',
                'metadata': {'external_reference': 'ACC-PRQ-2021-00013-2'}
            }
        }

        """
        from frappe.utils import get_url

        pagos360_settings = get_payment_gateway_controller("Pagos360")
        pago360 = Pagos360(pagos360_settings.get_password(fieldname="api_key", raise_exception=False) or self.api_key, pagos360_settings.sandbox)

        payment_request = frappe.get_doc(kwargs["reference_doctype"], kwargs["reference_docname"])
        sales_invoice = frappe.get_doc(payment_request.reference_doctype, payment_request.reference_name)

        def get_due_date(sales_invoice):
            """
            """
            today = datetime.date.today()
            if sales_invoice.due_date > today:
                return sales_invoice.due_date.strftime("%d-%m-%Y")
            return (today + timedelta(days=4)).strftime("%d-%m-%Y")

        back_url = get_url()

        data = {
            "payment_request": {
                "description": kwargs["description"].decode("utf-8"),
                "first_due_date": get_due_date(sales_invoice),  # TODO logica de fecha
                "first_total": '{0:.2f}'.format(kwargs['amount']),
                "payer_name": kwargs["payer_name"].decode("utf-8"),
                "external_reference": kwargs["reference_docname"],
                "payer_email": kwargs['payer_email'],
                "back_url_success": back_url,
                "back_url_pending": back_url,
                "back_url_rejected": back_url,
                "metadata": {"external_reference": kwargs["reference_docname"]}
            }
        }

        result = pago360.create_payment_request(data)

        if result.get("status", 0) == 201:
            return result.get("response", {}).get('checkout_url')
        return None  # TODO en caso de falla

    def get_parts_from_payment_request(self, payment_request):
        if payment_request.reference_doctype != "Sales Invoice":
            return None, None, None

        sales_invoice = frappe.get_doc("Sales Invoice", payment_request.reference_name)

        if not sales_invoice.subscription:
            return sales_invoice, None, None

        subscription = frappe.get_doc("Subscription", sales_invoice.subscription)

        payment_gateway = subscription.get_payment_gateway()

        if getattr(payment_gateway, "gateway", "") != "Pagos360" or not subscription.adhesion_pagos360 or not frappe.get_value("Adhesion Pagos360", subscription.adhesion_pagos360, 'id_adhesion'):
            return sales_invoice, subscription, None

        adhesion = frappe.get_doc("Adhesion Pagos360", subscription.adhesion_pagos360)
        return sales_invoice, subscription, adhesion

    def on_payment_request_submission(self, data):
        from erpnext_argentina.pagos360 import pago360_log_error

        sales_invoice, subscription, adhesion = self.get_parts_from_payment_request(data)

        if sales_invoice and subscription and adhesion:
            try:
                self.solicitar_debito(subscription, adhesion, sales_invoice, data)
                # TODO - Ver si hacemos algo con la data del debito automatico
            except Exception:
                pago360_log_error("on_payment_request_submission", data.as_json(), exception=True)

        return True

    def get_due_date(self, pago360, sales_invoice):
        """
        Busca la primer fecha hábil a partir de los 3 días de la fecha de la factura.
        """
        posting_date_3_days = sales_invoice.posting_date + timedelta(days=4)
        data = {
            "next_business_day": {
                "date": posting_date_3_days.strftime("%d-%m-%Y"),
                "days": 1,
            }
        }
        response = pago360.get_next_business_day(data)

        if response["status"] == 200:
            return parser.parse(response["response"]).date()
        return posting_date_3_days

    def solicitar_debito(self, subscription, adhesion, sales_invoice, payment_request):
        from erpnext_argentina.pagos360 import pago360_log_error

        pagos360_settings = get_payment_gateway_controller("Pagos360")
        pago360 = Pagos360(pagos360_settings.get_password("api_key"), pagos360_settings.sandbox)

        # Object  NO  Objeto JSON que se puede utilizar para guardar atributos adicionales en la adhesión y poder sincronizar con tus sistemas de backend. Pagos360.com no utiliza este objeto.
        debit_request = {"metadata": {"external_reference": payment_request.name}}

        if adhesion.tipo == "Débito":
            nombre_objeto = "debit_request"
            method = pago360.create_cbu_debit_request

            try:
                due_date = self.get_due_date(pago360, sales_invoice)
            except Exception:
                due_date = sales_invoice.posting_date + timedelta(days=4)

            # Integer SI  ID de la Adhesión asociada a la Solicitud de Débito.
            debit_request.update({"adhesion_id": int(adhesion.id_adhesion)})
            # Date    SI  Fecha de vencimiento de la Solicitud de Débito. Formato: dd-mm-aaaa.
            debit_request.update({"first_due_date": due_date.strftime("%d-%m-%Y")})
            # Float   SI  Importe a cobrar. Formato: 00000000.00 (hasta 8 enteros y 2 decimales, utilizando punto “.” como separador decimal).
            debit_request.update({"first_total": '{0:.2f}'.format(payment_request.grand_total)})
            # Date    NO  Fecha de segundo vencimiento de la Solicitud de Débito. Formato: dd-mm-aaaa.
            # debit_request.update({"second_due_date": "01-01-2020"})
            # Float   NO  Importe a cobrar pasada la primera fecha de vencimiento. Formato: 00000000.00 (hasta 8 enteros y 2 decimales, utilizando punto “.” como separador decimal). Este campo será requerido si se esta enviando una fecha en second_due_date.
            # debit_request.update({"second_total": 0.0})
            # String  NO  Descripción o concepto de la Solicitud de Débito (hasta 255 caracteres).
            debit_request.update({"description": f"Suscripción {subscription.company}"})

        elif adhesion.tipo == "Crédito":
            nombre_objeto = "card_debit_request"
            method = pago360.create_card_debit_request
            # Integer SI  ID de la Adhesión asociada a la Solicitud de Débito en Tarjeta.
            debit_request.update({"card_adhesion_id": int(adhesion.id_adhesion)})
            # Integer SI  Mes en el que se ejecuta el Debito Automático. Formato: mm.
            # Integer SI  Año en el que se ejecuta el Debito Automático. Formato: aaaa.
            debit_request.update({"month": sales_invoice.posting_date.month, "year": sales_invoice.posting_date.year})
            # Float   SI  Importe a ser Debitado Automáticamente. Formato: 00000000.00 (hasta 8 enteros y 2 decimales, utilizando punto “.” como separador decimal).
            debit_request.update({"amount": '{0:.2f}'.format(payment_request.grand_total)})
            # String  NO  Descripción o concepto de la Solicitud de Débito (hasta 255 caracteres).
            debit_request.update({"description": f"Suscripción {subscription.company}"})

        result = method({nombre_objeto: debit_request})

        if result.get("status", 0) == 201:
            return result.get("response", {})

        pago360_log_error("El débito no se solicito", {"request": debit_request, "response": result}, exception=True)

    def send_notification_email(self, subject, msg):
        if not self.recipients:
            return

        frappe.sendmail(
            recipients=self.recipients.split(","),
            subject=subject,
            message=msg,
        )

        frappe.db.commit()


class Pagos360:

    base_url = 'https://api.pagos360.com/'
    base_sandbox_url = 'https://api.sandbox.pagos360.com/'
    mime_type = 'application/json'

    def __init__(self, api_key, sandbox):
        self.api_key = api_key
        self.headers = {'authorization': 'Bearer ' + self.api_key, 'Content-type': self.mime_type}
        self.sandbox = bool(sandbox)

    def get_base_url(self):
        if self.sandbox:
            return self.base_sandbox_url
        return self.base_url

    def get(self, uri, params=None):
        api_result = requests.get(self.get_base_url() + uri, params=params, headers=self.headers)
        return {"status": api_result.status_code, "response": api_result.json()}

    def post(self, uri, data=None, params=None):
        if data is not None:
            data = JSONEncoder().encode(data)

        api_result = requests.post(self.get_base_url() + uri, params=params, data=data, headers=self.headers)

        return {"status": api_result.status_code, "response": api_result.json()}

    def put(self, uri, data=None, params=None):
        if data is not None:
            data = JSONEncoder().encode(data)

        api_result = self.put(self.get_base_url() + uri, params=params, data=data, headers=self.headers)

        return {"status": api_result.status_code, "response": api_result.json()}

    def validate_date(self, date=None):
        if not date:
            return (datetime.datetime.today() - datetime.timedelta(days=1)).strftime("%d-%m-%Y")
        if type(date) != str:
            return date.strftime("%d-%m-%Y")
        return date

    def get_account(self):
        return self.get("account")

    def get_account_balance(self):
        return self.get("account/balances/")

    def get_collection_report(self, date=None):
        return self.get("report/collection/" + self.validate_date(date))

    def get_chargeback_report(self, date=None):
        return self.get("report/chargeback/" + self.validate_date(date))

    def get_settlement_report(self, date=None):
        return self.get("report/settlement/" + self.validate_date(date))

    def get_card_adhesion(self, id):
        return self.get("card-adhesion/" + str(id))

    def create_card_adhesion(self, data):
        return self.post("card-adhesion/", data)

    def cancel_card_adhesion(self, id):
        return self.put("card-adhesion/{}/cancel".format(id))

    def get_cbu_adhesion(self, id):
        return self.get("adhesion/" + str(id))

    def create_cbu_adhesion(self, data):
        return self.post("adhesion/", data)

    def cancel_cbu_adhesion(self, id):
        return self.put("adhesion/{}/cancel".format(id))

    def create_card_debit_request(self, data):
        return self.post("card-debit-request/", data)

    def get_card_debit_request(self, id):
        return self.get("card-debit-request/" + str(id))

    def cancel_card_debit_request(self, id):
        return self.get("card-debit-request/{}/cancel/".format(id))

    def create_cbu_debit_request(self, data):
        return self.post("debit-request/", data)

    def get_cbu_debit_request(self, id):
        return self.get("debit-request/" + str(id))

    def cancel_cbu_debit_request(self, id):
        return self.get("debit-request/{}/cancel/".format(id))

    def create_payment_request(self, data):
        return self.post("payment-request/", data)

    def get_payment_request(self, id):
        return self.get("payment-request/" + str(id))

    def get_next_business_day(self, data):
        if "next_business_day" not in data:
            data = {"next_business_day": data}
        return self.post("validator/next-business-day/", data)

# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from json.encoder import JSONEncoder
import datetime
import requests
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
            pago360 = Pagos360(pagos360_settings.api_key, pagos360_settings.sandbox)
            pago360.get_account()
        except Exception:
            frappe.throw(_("Invalid payment gateway credentials"))

    def get_recipients(self):
        return self.recipients.split(",")

    def get_parts_from_payment_request(self, payment_request):
        if payment_request.reference_doctype != "Sales Invoice":
            return None, None, None

        sales_invoice = frappe.get_doc("Sales Invoice", payment_request.reference_name)

        if not sales_invoice.subscription:
            return sales_invoice, None, None

        subscription = frappe.get_doc("Subscription", sales_invoice.subscription)

        payment_gateway = subscription.get_payment_gateway()

        if getattr(payment_gateway, "gateway", "") != "Pagos360" or not subscription.adhesion_pagos360 or not subscription.id_adhesion:
            return sales_invoice, subscription, None

        adhesion = frappe.get_doc("Adhesion Pagos360", subscription.adhesion_pagos360)
        return sales_invoice, subscription, adhesion

    def on_payment_request_submission(self, data):
        from erpnext_argentina.facturacion import pago360_log_error

        sales_invoice, subscription, adhesion = self.get_parts_from_payment_request(data)

        if not sales_invoice or not subscription or not adhesion:
            frappe.throw("La solicitud de pago {} por Pagos360 no pertenece a ninguna suscripcion, no es valida.".format(data.name))

        try:
            self.solicitar_debito(subscription, adhesion, sales_invoice, data)
        except Exception as e:
            pago360_log_error({"error": e, "metodo": "on_payment_request_submission"}, data, exception=True)

        # TODO - Ver si hacemos algo con la data del debito automatico
        return False

    def solicitar_debito(self, subscription, adhesion, sales_invoice, payment_request):
        from erpnext_argentina.facturacion import pago360_log_error
        pagos360_settings = get_payment_gateway_controller("Pagos360")
        pago360 = Pagos360(pagos360_settings.api_key, pagos360_settings.sandbox)

        # Object  NO  Objeto JSON que se puede utilizar para guardar atributos adicionales en la adhesión y poder sincronizar con tus sistemas de backend. Pagos360.com no utiliza este objeto.
        debit_request = {"metadata": {"external_reference": payment_request.name}}

        if adhesion.tipo == "Débito":
            nombre_objeto = "debit_request"
            method = pago360.create_cbu_debit_request

            # Integer SI  ID de la Adhesión asociada a la Solicitud de Débito.
            debit_request.update({"adhesion_id": int(subscription.id_adhesion)})
            # Date    SI  Fecha de vencimiento de la Solicitud de Débito. Formato: dd-mm-aaaa.
            debit_request.update({"first_due_date": sales_invoice.due_date.strftime("%d-%m-%Y")})
            # Float   SI  Importe a cobrar. Formato: 00000000.00 (hasta 8 enteros y 2 decimales, utilizando punto “.” como separador decimal).
            debit_request.update({"first_total": '{0:.2f}'.format(payment_request.grand_total)})
            # Date    NO  Fecha de segundo vencimiento de la Solicitud de Débito. Formato: dd-mm-aaaa.
            # debit_request.update({"second_due_date": "01-01-2020"})
            # Float   NO  Importe a cobrar pasada la primera fecha de vencimiento. Formato: 00000000.00 (hasta 8 enteros y 2 decimales, utilizando punto “.” como separador decimal). Este campo será requerido si se esta enviando una fecha en second_due_date.
            # debit_request.update({"second_total": 0.0})
            # String  NO  Descripción o concepto de la Solicitud de Débito (hasta 255 caracteres).
            debit_request.update({"description": 'Suscripción'})  # TODO

        elif adhesion.tipo == "Crédito":
            nombre_objeto = "card_debit_request"
            method = pago360.create_card_debit_request
            # Integer SI  ID de la Adhesión asociada a la Solicitud de Débito en Tarjeta.
            debit_request.update({"card_adhesion_id": int(subscription.id_adhesion)})
            # Integer SI  Mes en el que se ejecuta el Debito Automático. Formato: mm.
            # Integer SI  Año en el que se ejecuta el Debito Automático. Formato: aaaa.
            month = sales_invoice.posting_date.month if sales_invoice.posting_date.day <= 10 else sales_invoice.posting_date.month + 1
            year = sales_invoice.posting_date.year
            if month > 12:
                month = 1
                year = year + 1
            debit_request.update({"month": month, "year": year})
            # Float   SI  Importe a ser Debitado Automáticamente. Formato: 00000000.00 (hasta 8 enteros y 2 decimales, utilizando punto “.” como separador decimal).
            debit_request.update({"amount": '{0:.2f}'.format(payment_request.grand_total)})
            # String  NO  Descripción o concepto de la Solicitud de Débito (hasta 255 caracteres).
            debit_request.update({"description": "Suscripción"})  # TODO

        result = method({nombre_objeto: debit_request})

        if result.get("status", 0) == 201:
            return result.get("response", {})

        pago360_log_error({"error": "El débito no se solicito"}, result, exception=True)
        frappe.throw("El debito no se solicito: status {}".format(result.get("status", 0)))

    def send_notification_email(self, msg):
        """
        Envia los correos de notificacion
        msg: Mensaje del correo
        """
        if not self.recipients:
            return

        frappe.sendmail(
            recipients=self.get_recipients(),
            subject='Notificación DiamoERP Pagos360',  # TODO
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

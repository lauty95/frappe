# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from uuid import uuid4
import json
import frappe
from frappe.model.document import Document
from frappe.integrations.utils import create_payment_gateway, get_payment_gateway_controller
from frappe.utils import get_url, call_hook_method
from frappe import _
import mercadopago


class MercadopagoSettings(Document):

    supported_currencies = ["ARS", "USD"]

    def validate_transaction_currency(self, currency):
        if currency not in self.supported_currencies:
            frappe.throw(_("Please select another payment method. Mercadopago does not support transactions in currency '{0}'").format(currency))

    def validate(self):
        create_payment_gateway("Mercadopago")
        call_hook_method('payment_gateway_enabled', gateway="Mercadopago")
        if not self.token:
            self.token = str(uuid4())

    def get_payment_url(self, **kwargs):
        """
        Url para solicitudes de pago
        """
        if not self.access_token:
            frappe.throw("Debe realizar la autorización en la configuración de la pasarela")

        mp = mercadopago.SDK(self.access_token)
        payment_request = frappe.get_doc(kwargs["reference_doctype"], kwargs["reference_docname"])

        preference_data = {
            "items": [
                {
                    "id": kwargs["reference_docname"],
                    "title": kwargs["title"].decode("utf-8"),
                    "description": kwargs["description"].decode("utf-8"),
                    "quantity": 1,
                    "currency_id": kwargs["currency"].decode("utf-8"),
                    "unit_price": kwargs["amount"],
                }
            ],
            "back_urls": {
                "success": self.success_url or get_url(),
                "failure": self.failure_url or get_url(),
                "pending": self.pending_url or get_url()
            },
            "auto_return": "approved",
            "notification_url": get_url("/api/method/frappe.integrations.doctype.mercadopago_settings.mercadopago_settings.ipn"),  # ?source_news=webhook,
            "external_reference": payment_request.name,
            "payer": {
                "name": kwargs["payer_name"].decode("utf-8"),
                "email": kwargs.get("payer_email", "")
            }
        }
        preference_response = mp.preference().create(preference_data)
        preference = preference_response["response"]

        if self.sandbox:
            return preference['sandbox_init_point']
        return preference['init_point']


def crear_notificacion_mercadopago(payment):
    notificacion = frappe.get_doc({"doctype": "Notificacion Mercadopago", "payment_id": payment.get('id', 0)})

    payer = payment.get("payer", {})
    transaction_details = payment.get("transaction_details", {})

    notificacion.payment_external_reference = payment.get("external_reference", "")
    notificacion.payment_status = payment.get("status", "")
    notificacion.payment_status_detail = payment.get("status_detail", "")
    notificacion.payment_description = payment.get("description", "")
    notificacion.payment_date_created = payment.get("date_created", "")
    notificacion.payment_date_approved = payment.get("date_approved", "")

    notificacion.payment_currency_id = payment.get("currency_id", "")
    notificacion.payment_transaction_amount = payment.get("transaction_amount", 0)
    notificacion.payment_total_paid_amount = transaction_details.get("total_paid_amount", 0)
    notificacion.payment_net_received_amount = transaction_details.get("net_received_amount", 0)
    notificacion.payment_installments = payment.get("installments", 0)
    notificacion.payment_installment_amount = transaction_details.get("installment_amount", 0)

    notificacion.payer_id = payer.get("id", 0)
    notificacion.payer_email = payer.get("email", "")
    notificacion.payer_identification_type = payer.get("identification", {}).get("type", "")
    notificacion.payer_identification_number = payer.get("identification", {}).get("number", "")

    notificacion.data_json = json.dumps(payment)
    notificacion.save(ignore_permissions=True)
    frappe.db.commit()


def get_ipn_url() -> str:
    # La configuración debe cargarse de manera tardía.
    return f"https://{frappe.get_site_config().get('MP_IPN_DOMAIN', '')}"


@frappe.whitelist()
def get_auth_url_whitelisted(account_name):
    """
    Devuelve la URL para autorizar una cuenta.
    Args:
        account_name: Nombre de la cuenta.
    Returns:
        La URL para autorizarse o un mensaje de error en caso de que exista algún inconveniente.
    """
    account = get_payment_gateway_controller("Mercadopago")

    return {
        "success": True,
        "result": (
            f"{get_ipn_url()}/mp/autorizar/"
            f"?account_name={account_name}"
            "&auth_url=https://auth.mercadopago.com.ar"
            f"&token={account.token}"
            f"&version=13"
        ),
    }


@frappe.whitelist()
def update_config_data_whitelisted(account_name: str, token: str, user_id: str, access_token: str, refresh_token: str):
    """
    Actualiza la configuración de la cuenta.
    Esta función es llamada desde la IPN para cargar datos proporcionados por la API al momento de realizar la
    autorización.
    Args:
        account_name: Nombre de la cuenta.
        token: Token de seguridad.
        user_id: ID de la cuenta.
        access_token: Token de acceso.
        refresh_token: Token de refresco.
    """
    account = get_payment_gateway_controller("Mercadopago")

    if account.account_name != account_name or account.token != token:
        return

    account.user_id = user_id
    account.access_token = access_token
    account.refresh_token = refresh_token
    account.save()
    frappe.db.commit()


@frappe.whitelist()
def verify_whitelisted(account_name: str, token: str) -> bool:
    """
    Verifica si los datos pertenecen a una cuenta que existe.
    Esta función se llama desde la IPN para validar que los datos que tiene guardados son válidos.
    Args:
        account_name: Nombre de la cuenta.
        token: Token de seguridad.
    Returns:
        Booleano que indica si la cuenta existe.
    """
    account = get_payment_gateway_controller("Mercadopago")
    return account and account.account_name == account_name and account.token == token


@frappe.whitelist(allow_guest=True, xss_safe=True)
def ipn(**args):
    """
    /api/method/frappe.integrations.doctype.mercadopago_settings.mercadopago_settings.ipn?topic=payment&id=123456789
    """
    webhook_type = args['type']
    webhook_topic_id = args["data"]["id"]

    mercadopago_settings = get_payment_gateway_controller("Mercadopago")
    mp = mercadopago.SDK(mercadopago_settings.access_token)

    if webhook_type == "payment":
        payment = mp.payment().get(webhook_topic_id)['response']

        if payment['status'] == "approved" and payment["status_detail"] == "accredited":
            payment_request = frappe.get_doc("Payment Request", payment['external_reference'])
            payment_request.run_method("on_payment_authorized", "Completed")

        crear_notificacion_mercadopago(payment)

    return {
        "webhook_type": webhook_type,
        "webhook_topic_id": webhook_topic_id
    }

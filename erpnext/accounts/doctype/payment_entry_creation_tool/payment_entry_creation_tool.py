# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import publish_progress

# from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.erpnext_integrations.connectors.woocommerce_connection import change_status
import openpyxl
import requests
from io import BytesIO
from frappe.model.document import Document


class PaymentEntryCreationTool(Document):
    @frappe.whitelist()
    def create_payment_entries(self):
        order_ids_list = []
        if frappe.db.exists("File", {"file_url": self.sales_invoice_list}):
            file_doc = frappe.get_doc("File", {"file_url": self.sales_invoice_list})
            parts = file_doc.get_extension()
            extension = parts[1]

            if extension == ".xlsx":
                try:
                    content = file_doc.get_content()
                    workbook = openpyxl.load_workbook(BytesIO(content))
                    sheet = workbook.active
                    order_ids_list = [str(cell.value) for cell in sheet["A"][1:]]
                except Exception as e:
                    frappe.msgprint(
                        f"Error reading XLSX file: {str(e)}", "Invalid File"
                    )
                    return
            elif extension == ".csv":
                content = file_doc.get_content()
                order_ids_list = content.strip().split("\n")[1:]
            else:
                frappe.msgprint(
                    "The File extension should be CSV or XLSX type.", "Invalid File"
                )
                return
            frappe.msgprint("Payment Entry is Creating in the background")
            # create_payment_entries(self, order_ids_list)
            frappe.enqueue(
                method=create_payment_entries,
                self=self,
                order_ids_list=order_ids_list,
                queue="long",
                timeout=500000,
            )
            # frappe.enqueue(method=create_payment_entries, self=self, queue="long", timeout=500000, is_async=True)
            # frappe.enqueue(method=application_map_data, type=type, json_data=json_data, queue="default", timeout=36000, is_async=True, job_name=job_name,job_id=job_name,)

        else:
            frappe.msgprint("The File does not exist.", "Invalid File")
            return


def create_payment_entries(self, order_ids_list):
    for d in order_ids_list:
        if d and d != "None":
            if frappe.db.exists(
                "Sales Invoice",
                {"po_no": d, "docstatus": 1, "status": ["in", ["Unpaid", "Overdue"]]},
            ):
                try:
                    si = frappe.get_doc("Sales Invoice", {"po_no": d}).as_dict()
                    pe = change_status([si], "payment_entry")

                    self.append(
                        "invoices_detail",
                        {
                            "order_id": d,
                            "status": "Success",
                            "description": "Payment Entry Created Successfully",
                        },
                    )
                    self.save()
                    frappe.db.commit()
                except Exception as e:
                    self.append(
                        "invoices_detail",
                        {
                            "order_id": d,
                            "status": "Failed",
                            "description": e,  # "Payment Entry Creation Failed"
                        },
                    )
                    self.save()
                    frappe.db.commit()
            else:
                self.append(
                    "invoices_detail",
                    {
                        "order_id": d,
                        "status": "Failed",
                        "description": "Sales Invoice is Paid/Cancelled or does not Exist",
                    },
                )
    self.completed = 1
    self.save()
    frappe.db.commit()

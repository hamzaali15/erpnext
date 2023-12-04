# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils import nowdate
from frappe.model.document import Document

class PaymentEntryCreationTool(Document):
	@frappe.whitelist()
	def create_payment_entries(self):
		if frappe.db.exists('File', {'file_url': self.sales_invoice_list}):
			file_doc = frappe.get_doc("File", {"file_url": self.sales_invoice_list})
			parts = file_doc.get_extension()
			extension = parts[1]
			content = file_doc.get_content()
			order_ids_list = content.strip().split('\n')
			if extension not in ['.csv', '.xlsx']:
				frappe.msgprint('The File extension should be CSV or XLSX type.', 'Invalid File')
				return
			frappe.msgprint("Payment Entry is Creating in the background")
			frappe.enqueue(create_payment_entries, self=self, queue="long")
			# self.completed = 1
			#self.save()
			#frappe.db.commit()
		else:
			frappe.msgprint('The File does not exists.', 'Invalid File')
			return


def create_payment_entries(self):
	file_doc = frappe.get_doc("File", {"file_url": self.sales_invoice_list})
	content = file_doc.get_content()
	order_ids_list = content.strip().split('\n')
	for i, d in enumerate(order_ids_list):
		if i != 0:
			if frappe.db.exists("Sales Invoice", {"po_no": d, "docstatus": 1, "status": ["in", ["Unpaid", "Overdue"]]}):
				try:
					si = frappe.get_doc("Sales Invoice", {"po_no": d})
					pe = get_payment_entry("Sales Invoice", si.name)
					pe.po_no = d
					pe.set_missing_values()

					bank_account = pe.paid_to if pe.payment_type == "Receive" else pe.paid_from
					bank_account_type = frappe.db.get_value("Account", bank_account, "account_type")
					if bank_account_type == "Bank":
						if not pe.reference_no or not pe.reference_date:
						    pe.reference_no = si.name
						    pe.reference_date = nowdate()

					pe.insert(ignore_permissions=True)
					pe.save(ignore_permissions=True)
					pe.submit()
					frappe.db.commit()
					self.append("invoices_detail", {
						"order_id": d,
						"status": "Success",
						"description": "Payment Entry Created Successfully"
					})
					self.save()
					#self.db_update()
					#frappe.db.commit()
				except Exception as e:
					self.append("invoices_detail", {
						"order_id": d,
						"status": "Failed",
						"description": e  #"Payment Entry Creation Failed"
					})
					self.save()
					#self.db_update()
					#frappe.db.commit()
			else:
				self.append("invoices_detail", {
					"order_id": d,
					"status": "Failed",
					"description": "Sales Invoice is Paid/Cancelled or does not Exist"
				})
				#self.save()
				#self.db_update()
				#frappe.db.commit()
	self.completed = 1
	self.save()
	frappe.db.commit()

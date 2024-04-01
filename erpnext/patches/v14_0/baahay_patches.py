import frappe


def execute():
	syns_order_status()
	update_valuation_rate()


def syns_order_status():
	so_list = frappe.db.get_list("Sales Order", {"docstatus": 1, "woocommerce_id": ["!=", ""]}, ["woocommerce_id", "woocommerce_status"])
	for so in so_list:
		pi_list = frappe.db.get_list("Purchase Invoice", {"docstatus": 1, "s_code": so.woocommerce_id}, "name")
		for pi in pi_list:
			pi_doc = frappe.get_doc("Purchase Invoice", pi.name)
			pi_doc.db_set("order_status", so.woocommerce_status)


def update_valuation_rate():
	doc = []
	sle_list = frappe.get_list("Stock Ledger Entry", {"is_cancelled": 0, "valuation_rate": ["=", 0]}, ["name", "item_code", "valuation_rate", "voucher_type", "voucher_no", "voucher_detail_no"])
	for sle in sle_list:
		doctype = sle.voucher_type + " Item"
		if sle.voucher_type == "Purchase Receipt":
			doc = frappe.db.sql("""select poi.rate from `tab{0}` as pri
				join `tabPurchase Order Item` as poi on poi.parent=pri.purchase_order and pri.item_code=poi.item_code
				where pri.name='{1}'""".format(doctype, sle.voucher_detail_no), as_dict=True)
			if doc:
				rate = 0
				rate = doc[0].get("rate")
				ent = frappe.get_doc("Stock Ledger Entry", sle.name)
				ent.db_set("valuation_rate", rate)
		elif sle.voucher_type == "Delivery Note":
			doc = frappe.db.sql("""select dni.rate from `tab{0}` as dn
				join `tab{1}` as dni on dni.parent=dn.name
				where dn.name='{2}' and dni.name='{3}'""".format(sle.voucher_type, doctype, sle.voucher_no, sle.voucher_detail_no), as_dict=True)
			if doc:
				rate = 0
				rate = doc[0].get("rate")
				ent = frappe.get_doc("Stock Ledger Entry", sle.name)
				ent.db_set("valuation_rate", rate)
		elif sle.voucher_type == "Stock Reconciliation":
			doc = frappe.db.sql("""select valuation_rate from `tab{0}`
						where name='{1}'""".format(doctype, sle.voucher_detail_no), as_dict=True)
			if doc:
				rate = 0
				rate = doc[0].get("valuation_rate")
				ent = frappe.get_doc("Stock Ledger Entry", sle.name)
				ent.db_set("valuation_rate", rate)

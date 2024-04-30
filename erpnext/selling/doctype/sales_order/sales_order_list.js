frappe.listview_settings['Sales Order'] = {
	add_fields: ["base_grand_total", "customer_name", "currency", "delivery_date",
		"per_delivered", "per_billed", "woocommerce_status", "order_type", "name", "skip_delivery_note","woocommerce_id"],
	get_indicator: function (doc) {
		if(doc.woocommerce_status =="fulfilled_order"){
			return [__("Fulfilled Order"), "pink", "woocommerce_status,=,fulfilled_order"];
		} else if(doc.woocommerce_status=="wc-processing"){
			return [__("Pending Confirmation"), "yellow"]
		} else if(doc.woocommerce_status=="dvr-to-cstm"){
			return [__("Deliver to customer status"), "brown"]
		} else if (doc.woocommerce_status =="item_out_of_stock"){
			return [__("Item Out Of Stock"), "gray", "woocommerce_status,=,item_out_of_stock"];
		} else if (doc.woocommerce_status =="confirmed"){
			return [__("Confirmed"), "orange", "woocommerce_status,=,item_out_of_stock"];
		} else if (doc.woocommerce_status =="vanex"){
			return [__("Vanex"), "light-blue", "woocommerce_status,=,item_out_of_stock"];
		} else if (doc.woocommerce_status =="out_for_delivery"){
			return [__("Out For Delivery"), "cyan", "woocommerce_status,=,item_out_of_stock"];
		} else if (doc.woocommerce_status =="return_to_stock"){
			return [__("Return To Stock"), "light-gray", "woocommerce_status,=,item_out_of_stock"];
		} else if (doc.woocommerce_status =="delivered"){
			return [__("Delivered"), "purple", "woocommerce_status,=,item_out_of_stock"];
		} else if (doc.woocommerce_status =="user_returnd"){
			return [__("Returnd"), "red", "woocommerce_status,=,item_out_of_stock"];
		} else if (doc.woocommerce_status =="error"){
			return [__("Error"), "red", "woocommerce_status,=,error"];
		} else{
			return [doc.woocommerce_status, "blue"]
		}
	},
	onload: function(listview) {
		// Your CSS as text
		var styles = `button.btn.btn-default.icon-btn {display: none;}`;
		var styleSheet = document.createElement("style");
		styleSheet.innerText = styles;
		document.head.appendChild(styleSheet);
		var method = "erpnext.selling.doctype.sales_order.sales_order.close_or_unclose_sales_orders";
		if(frappe.user.has_role("System Manager") && false){
			listview.page.add_menu_item(__("Close"), function() {
				listview.call_for_selected_items(method, {"status": "Closed"});
			});
			listview.page.add_menu_item(__("R-open"), function() {
				listview.call_for_selected_items(method, {"status": "Submitted"});
			});
			listview.page.add_action_item(__("Sales Invoice"), ()=>{
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Sales Invoice");
			});
			listview.page.add_action_item(__("Delivery Note"), ()=>{
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Delivery Note");
			});
			listview.page.add_action_item(__("Advance Payment"), ()=>{
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Advance Payment");
			});
		}
	}
};

frappe.listview_settings['Item'] = {
	add_fields: ["item_name", "stock_uom", "item_group", "image", "variant_of",
		"has_variants", "end_of_life", "disabled"],
	filters: [["disabled", "=", "0"]],
	onload: function(listview) {
	//remove this condition if not required
			frappe.route_options = {
				//"has_variants": ["!=", "1"],
				"variant_of":["is","not set"],
			};
		
	},
	get_indicator: function(doc) {
		if (doc.disabled) {
			return [__("Disabled"), "grey", "disabled,=,Yes"];
		} else if (doc.end_of_life && doc.end_of_life < frappe.datetime.get_today()) {
			return [__("Expired"), "grey", "end_of_life,<,Today"];
		} else if (doc.has_variants) {
			return [__("Variable product"), "yellow", "has_variants,=,Yes"];
		} else if (doc.variant_of) {
			return [__("Variant"), "green", "variant_of,=," + doc.variant_of];
		} else if (!doc.has_variants) {
			return [__("Simple product"), "green", "has_variants,=,No"];
		} 
	},

	reports: [
		{
			name: 'Stock Summary',
			report_type: 'Page',
			route: 'stock-balance'
		},
		{
			name: 'Stock Ledger',
			report_type: 'Script Report'
		},
		{
			name: 'Stock Balance',
			report_type: 'Script Report'
		},
		{
			name: 'Stock Projected Qty',
			report_type: 'Script Report'
		}

	]
};

frappe.help.youtube_id["Item"] = "qXaEwld4_Ps";

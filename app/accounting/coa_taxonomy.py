COA_TAXONOMY = [
    {
        "major_category": "Revenue",
        "subtotal_code": "2999",
        "subcategories": [
            {
                "name": "Operating Revenue",
                "subtotal_code": "1999",
                "account_types": [
                    {
                        "name": "Sales Revenue",
                        "accounts": [
                            {"code": "1100", "name": "Product Sales", "type": "income"},
                            {"code": "1110", "name": "Service Revenue", "type": "income"},
                            {"code": "1120", "name": "Subscription Revenue", "type": "income"},
                        ]
                    },
                    {
                        "name": "Other Revenue",
                        "accounts": [
                            {"code": "1200", "name": "Sales Returns & Allowances", "type": "income"},
                            {"code": "1205", "name": "Sales Discounts", "type": "income"},
                        ]
                    }
                ]
            },
            {
                "name": "Non-Operating Revenue",
                "subtotal_code": "2199",
                "account_types": [
                    {
                        "name": "Interest & Investment",
                        "accounts": [
                            {"code": "2100", "name": "Interest Income", "type": "income"},
                            {"code": "2110", "name": "Dividend Income", "type": "income"},
                            {"code": "2120", "name": "Gain on Sale of Assets", "type": "income"},
                            {"code": "2130", "name": "Donations Received", "type": "income"},
                        ]
                    }
                ]
            }
        ]
    },
    {
        "major_category": "Expenses",
        "subtotal_code": "5999",
        "subcategories": [
            {
                "name": "Cost of Sales",
                "subtotal_code": "3999",
                "account_types": [
                    {
                        "name": "Direct Costs",
                        "accounts": [
                            {"code": "3100", "name": "Cost of Goods Sold", "type": "expense"},
                            {"code": "3110", "name": "Cost of Services", "type": "expense"},
                            {"code": "3120", "name": "Freight & Shipping — COGS", "type": "expense"},
                        ]
                    }
                ]
            },
            {
                "name": "Operating Expenses",
                "subtotal_code": "4999",
                "account_types": [
                    {
                        "name": "Selling & Distribution",
                        "accounts": [
                            {"code": "4100", "name": "Salaries & Wages — Sales", "type": "expense"},
                            {"code": "4110", "name": "Sales Commissions", "type": "expense"},
                            {"code": "4120", "name": "Marketing & Advertising", "type": "expense"},
                            {"code": "4130", "name": "Delivery & Logistics", "type": "expense"},
                        ]
                    },
                    {
                        "name": "General & Administrative",
                        "accounts": [
                            {"code": "4200", "name": "Salaries & Wages — Admin", "type": "expense"},
                            {"code": "4210", "name": "Office Rent", "type": "expense"},
                            {"code": "4220", "name": "Utilities", "type": "expense"},
                            {"code": "4230", "name": "Professional Fees", "type": "expense"},
                            {"code": "4240", "name": "Insurance", "type": "expense"},
                            {"code": "4250", "name": "Office Supplies", "type": "expense"},
                            {"code": "4260", "name": "Depreciation Expense", "type": "expense"},
                            {"code": "4270", "name": "Amortization Expense", "type": "expense"},
                        ]
                    }
                ]
            },
            {
                "name": "Finance Costs",
                "subtotal_code": "5099",
                "account_types": [
                    {
                        "name": "Interest & Banking",
                        "accounts": [
                            {"code": "5100", "name": "Interest Expense", "type": "expense"},
                            {"code": "5110", "name": "Bank Charges & Fees", "type": "expense"},
                            {"code": "5120", "name": "Foreign Exchange Loss", "type": "expense"},
                        ]
                    }
                ]
            },
            {
                "name": "Taxes",
                "subtotal_code": "5199",
                "account_types": [
                    {
                        "name": "Income Taxes",
                        "accounts": [
                            {"code": "5200", "name": "Income Tax Expense", "type": "expense"},
                            {"code": "5210", "name": "Withholding Tax", "type": "expense"},
                        ]
                    }
                ]
            }
        ]
    },
    {
        "major_category": "Assets",
        "subtotal_code": "7999",
        "subcategories": [
            {
                "name": "Non-Current Assets",
                "subtotal_code": "6999",
                "account_types": [
                    {
                        "name": "Property, Plant & Equipment",
                        "accounts": [
                            {"code": "6100", "name": "Land & Land Improvements", "type": "asset"},
                            {"code": "6110", "name": "Buildings", "type": "asset"},
                            {"code": "6120", "name": "Machinery & Equipment", "type": "asset"},
                            {"code": "6130", "name": "Vehicles", "type": "asset"},
                            {"code": "6140", "name": "Furniture & Fixtures", "type": "asset"},
                            {"code": "6190", "name": "Accumulated Depreciation — PPE", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Intangible Assets",
                        "accounts": [
                            {"code": "6200", "name": "Patents & Licenses", "type": "asset"},
                            {"code": "6210", "name": "Goodwill", "type": "asset"},
                            {"code": "6290", "name": "Accumulated Amortization — Intangibles", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Long-Term Investments",
                        "accounts": [
                            {"code": "6300", "name": "Long-Term Investments", "type": "asset"},
                            {"code": "6310", "name": "Investments in Subsidiaries", "type": "asset"},
                        ]
                    }
                ]
            },
            {
                "name": "Current Assets",
                "subtotal_code": "7899",
                "account_types": [
                    {
                        "name": "Cash & Bank",
                        "accounts": [
                            {"code": "7100", "name": "Cash on Hand", "type": "asset"},
                            {"code": "7110", "name": "Bank — Checking", "type": "asset"},
                            {"code": "7120", "name": "Bank — Savings", "type": "asset"},
                            {"code": "7130", "name": "Petty Cash", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Short-Term Investments",
                        "accounts": [
                            {"code": "7200", "name": "Short-Term Investments", "type": "asset"},
                            {"code": "7210", "name": "Marketable Securities", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Accounts Receivable",
                        "accounts": [
                            {"code": "7300", "name": "Accounts Receivable", "type": "asset"},
                            {"code": "7310", "name": "Allowance for Doubtful Debts", "type": "asset"},
                            {"code": "7320", "name": "Notes Receivable", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Inventory",
                        "accounts": [
                            {"code": "7400", "name": "Raw Materials Inventory", "type": "asset"},
                            {"code": "7410", "name": "Work-in-Progress Inventory", "type": "asset"},
                            {"code": "7420", "name": "Finished Goods Inventory", "type": "asset"},
                        ]
                    },
                    {
                        "name": "Prepayments",
                        "accounts": [
                            {"code": "7500", "name": "Prepaid Expenses", "type": "asset"},
                            {"code": "7510", "name": "Prepaid Insurance", "type": "asset"},
                            {"code": "7520", "name": "Prepaid Rent", "type": "asset"},
                        ]
                    }
                ]
            }
        ]
    },
    {
        "major_category": "Liabilities",
        "subtotal_code": "8999",
        "subcategories": [
            {
                "name": "Non-Current Liabilities",
                "subtotal_code": "8099",
                "account_types": [
                    {
                        "name": "Long-Term Debt",
                        "accounts": [
                            {"code": "8000", "name": "Long-Term Bank Loans", "type": "liability"},
                            {"code": "8010", "name": "Mortgage Payable", "type": "liability"},
                            {"code": "8020", "name": "Less: Current Portion of Long-Term Debt", "type": "liability"},
                        ]
                    }
                ]
            },
            {
                "name": "Current Liabilities",
                "subtotal_code": "8799",
                "account_types": [
                    {
                        "name": "Trade Payables",
                        "accounts": [
                            {"code": "8200", "name": "Accounts Payable", "type": "liability"},
                            {"code": "8210", "name": "Accrued Expenses", "type": "liability"},
                            {"code": "8220", "name": "Taxes Payable", "type": "liability"},
                            {"code": "8230", "name": "VAT Payable", "type": "liability"},
                        ]
                    },
                    {
                        "name": "Short-Term Debt",
                        "accounts": [
                            {"code": "8300", "name": "Short-Term Loans", "type": "liability"},
                            {"code": "8310", "name": "Current Portion of Long-Term Debt", "type": "liability"},
                        ]
                    },
                    {
                        "name": "Other Payables",
                        "accounts": [
                            {"code": "8400", "name": "Salaries & Wages Payable", "type": "liability"},
                            {"code": "8410", "name": "Dividends Payable", "type": "liability"},
                            {"code": "8420", "name": "Unearned Revenue", "type": "liability"},
                        ]
                    }
                ]
            }
        ]
    },
    {
        "major_category": "Equity",
        "subtotal_code": "9999",
        "subcategories": [
            {
                "name": "Owner's Equity",
                "subtotal_code": "9099",
                "account_types": [
                    {
                        "name": "Capital",
                        "accounts": [
                            {"code": "9100", "name": "Owner's Capital / Share Capital", "type": "equity"},
                            {"code": "9110", "name": "Additional Paid-In Capital", "type": "equity"},
                            {"code": "9120", "name": "Treasury Shares", "type": "equity"},
                        ]
                    },
                    {
                        "name": "Reserves & Retained Earnings",
                        "accounts": [
                            {"code": "9200", "name": "Retained Earnings", "type": "equity"},
                            {"code": "9210", "name": "Appropriated Reserves", "type": "equity"},
                        ]
                    }
                ]
            },
            {
                "name": "Current Period Earnings",
                "subtotal_code": "9399",
                "account_types": [
                    {
                        "name": "P&L Summary",
                        "accounts": [
                            {"code": "9300", "name": "Current Year Earnings", "type": "equity"},
                            {"code": "9310", "name": "Dividends Declared", "type": "equity"},
                        ]
                    }
                ]
            }
        ]
    }
]


def _find_leaf(taxonomy, code):
    for major in taxonomy:
        for sub in major.get("subcategories", []):
            for atype in sub.get("account_types", []):
                for acct in atype.get("accounts", []):
                    if acct["code"] == code:
                        return {
                            "code": acct["code"],
                            "name": acct["name"],
                            "type": acct["type"],
                            "major_category": major["major_category"],
                            "subcategory": sub["name"],
                            "account_type": atype["name"],
                            "major_subtotal_code": major.get("subtotal_code"),
                            "subcategory_subtotal_code": sub.get("subtotal_code"),
                        }
    return None


def build_coa_tree(selected_codes):
    selected_codes = set(selected_codes)
    leaves = []
    account_type_map = {}
    subcategory_map = {}
    major_map = {}

    for code in selected_codes:
        leaf = _find_leaf(COA_TAXONOMY, code)
        if not leaf:
            continue
        leaves.append(leaf)

        major_key = leaf["major_category"]
        sub_key = (major_key, leaf["subcategory"])
        atype_key = (major_key, leaf["subcategory"], leaf["account_type"])

        major_map.setdefault(major_key, {
            "subtotal_code": leaf["major_subtotal_code"],
            "subcategories": set(),
        })
        major_map[major_key]["subcategories"].add(leaf["subcategory"])

        subcategory_map.setdefault(sub_key, {
            "name": leaf["subcategory"],
            "subtotal_code": leaf["subcategory_subtotal_code"],
            "account_types": set(),
        })
        subcategory_map[sub_key]["account_types"].add(leaf["account_type"])

        account_type_map.setdefault(atype_key, {
            "name": leaf["account_type"],
            "type": leaf["type"],
            "leaves": [],
        })
        account_type_map[atype_key]["leaves"].append(leaf)

    subtotals = []
    code_to_name = {}
    used_codes = set()

    def next_available_xx99(xx_prefix, used):
        candidate = f"{xx_prefix}99"
        offset = 1
        while candidate in used:
            candidate = f"{xx_prefix + offset}99"
            offset += 1
        return candidate

    for atype_key, info in account_type_map.items():
        groups = {}
        for leaf in info["leaves"]:
            xx = leaf["code"][:2]
            groups.setdefault(xx, [])
            groups[xx].append(leaf)

        for xx, group_leaves in groups.items():
            if len(group_leaves) < 2:
                continue
            code = next_available_xx99(xx, used_codes)
            used_codes.add(code)
            code_to_name[code] = f"Total {info['name']}"
            subtotals.append({
                "code": code,
                "name": f"Total {info['name']}",
                "type": info["type"],
                "parent_code": None,
                "is_subtotal": True,
            })
            for leaf in group_leaves:
                leaf["_parent_code"] = code

    for atype_key, info in account_type_map.items():
        atype_subtotal_codes = [
            s["code"] for s in subtotals
            if s["name"] == f"Total {info['name']}"
        ]
        if not atype_subtotal_codes:
            continue
        sub_key = (atype_key[0], atype_key[1])
        sub_info = subcategory_map[sub_key]
        single_atype = len(sub_info["account_types"]) == 1
        if single_atype:
            sub_code = atype_subtotal_codes[0]
            parent_code = major_map[atype_key[0]]["subtotal_code"]
        else:
            sub_code = sub_info["subtotal_code"]
            parent_code = sub_code
        used_codes.add(sub_code)
        code_to_name.setdefault(sub_code, f"Total {sub_info['name']}")
        if not any(s["code"] == sub_code for s in subtotals):
            subtotals.append({
                "code": sub_code,
                "name": f"Total {sub_info['name']}",
                "type": info["type"],
                "parent_code": parent_code,
                "is_subtotal": True,
            })
        for code in atype_subtotal_codes:
            for s in subtotals:
                if s["code"] == code:
                    s["parent_code"] = parent_code
                    break

    for major_key, info in major_map.items():
        maj_code = info["subtotal_code"]
        used_codes.add(maj_code)
        code_to_name.setdefault(maj_code, f"Total {major_key}")
        if not any(s["code"] == maj_code for s in subtotals):
            subtotals.append({
                "code": maj_code,
                "name": f"Total {major_key}",
                "type": leaves[0]["type"] if leaves else "asset",
                "parent_code": None,
                "is_subtotal": True,
            })
        for sub_name in info["subcategories"]:
            sub_key = (major_key, sub_name)
            sub_info = subcategory_map.get(sub_key)
            if not sub_info:
                continue
            sub_code = sub_info["subtotal_code"]
            if not any(s["code"] == sub_code for s in subtotals):
                continue
            for s in subtotals:
                if s["code"] == sub_code:
                    s["parent_code"] = maj_code
                    break

    all_accounts = []
    for s in reversed(subtotals):
        all_accounts.append({
            "code": s["code"],
            "name": s["name"],
            "type": s["type"],
            "parent_code": s["parent_code"],
            "is_subtotal": True,
        })
    for leaf in leaves:
        all_accounts.append({
            "code": leaf["code"],
            "name": leaf["name"],
            "type": leaf["type"],
            "parent_code": leaf.get("_parent_code"),
            "is_subtotal": False,
        })

    return all_accounts

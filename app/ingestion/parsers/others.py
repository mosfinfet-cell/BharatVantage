"""
zomato.py — Zomato settlement report parser.
"""
from __future__ import annotations
import pandas as pd
from app.ingestion.parsers.base import BaseParser, ParseResult, find_col, safe_num, safe_date, strip_gst
from app.core.auth import hash_customer_id

COLUMN_ALIASES = {
    "order_id":     ["order_id", "orderid", "order id", "zomato order id"],
    "date":         ["order_date", "order date", "date", "created_at", "created at"],
    "gross_amount": ["order_total", "gross_amount", "order value", "subtotal", "gross order value"],
    "commission":   ["platform_fee", "commission", "zomato_fee", "platform commission"],
    "ad_spend":     ["zomato_ads", "ad_spend", "advertisement", "marketing charges", "ads"],
    "penalty":      ["cancellation_charges", "penalty", "deduction", "dispute_amount", "other charges"],
    "discount":     ["discount", "zomato_discount", "offer_discount", "promo"],
    "net_payout":   ["net_payout", "payout", "settlement_amount", "amount_credited", "net amount"],
    "customer_id":  ["customer_id", "user_id", "customer id", "user id"],
}

class ZomatoParser(BaseParser):
    source_type   = "zomato"
    data_category = "sales_aggregator"

    def parse(self, df, session_id, outlet_id, gst_rate=5.0, **kwargs):
        cols = list(df.columns)
        m = {f: find_col(cols, a) for f, a in COLUMN_ALIASES.items()}
        records, errors, warnings = [], [], []

        if not m.get("gross_amount"):
            warnings.append("Could not find gross amount column — check Zomato export format.")

        for idx, row in df.iterrows():
            try:
                gross = strip_gst(
                    float(safe_num(pd.Series([row[m["gross_amount"]]]))[0]) if m["gross_amount"] else 0.0,
                    gst_rate
                )
                rec = self._base_record(session_id, outlet_id)
                rec.update({
                    "channel":      "zomato",
                    "date":         safe_date(pd.Series([row[m["date"]]]))[0] if m["date"] else None,
                    "order_id":     str(row[m["order_id"]])[:100] if m["order_id"] else None,
                    "customer_id":  hash_customer_id(str(row[m["customer_id"]]) if m["customer_id"] else "", outlet_id),
                    "gross_amount": gross,
                    "commission":   float(safe_num(pd.Series([row[m["commission"]]]))[0]) if m["commission"] else 0.0,
                    "ad_spend":     float(safe_num(pd.Series([row[m["ad_spend"]]]))[0])   if m["ad_spend"]   else 0.0,
                    "penalty":      float(safe_num(pd.Series([row[m["penalty"]]]))[0])    if m["penalty"]    else 0.0,
                    "discount":     float(safe_num(pd.Series([row[m["discount"]]]))[0])   if m["discount"]   else 0.0,
                    "net_payout":   float(safe_num(pd.Series([row[m["net_payout"]]]))[0]) if m["net_payout"] else None,
                    "is_deduplicated": False,
                })
                records.append(rec)
            except Exception as e:
                errors.append(f"Row {idx}: {e}")
                if len(errors) > 20: break

        return ParseResult(self.source_type, self.data_category, records, len(df), errors, warnings)


"""
petpooja.py — Petpooja POS export parser.
Produces SalesRecord rows (data_category: sales_pos).
"""
PETPOOJA_ALIASES = {
    "order_id":   ["bill no", "bill number", "order id", "invoice no", "bill_no"],
    "date":       ["date", "bill date", "order date", "created", "transaction date"],
    "gross_amount": ["total", "bill total", "net total", "amount", "grand total", "net amount"],
    "item_name":  ["item name", "item", "dish", "product name", "menu item", "description"],
    "quantity":   ["qty", "quantity", "units", "count", "nos"],
    "unit_price": ["rate", "price", "unit price", "selling price", "mrp", "sp"],
    "customer_id":["customer", "customer name", "cust id", "guest name", "mobile"],
    "channel":    ["order type", "source", "channel", "platform", "type", "order source"],
}

class PetpoojaParser(BaseParser):
    source_type   = "petpooja"
    data_category = "sales_pos"

    def _map_channel(self, raw: str) -> str:
        v = str(raw).lower().strip()
        if "swiggy" in v: return "swiggy"
        if "zomato" in v: return "zomato"
        if any(k in v for k in ["dine", "in-house", "table", "walkin", "walk in"]): return "dine_in"
        if "takeaway" in v or "take away" in v: return "takeaway"
        return "dine_in"  # default for POS

    def parse(self, df, session_id, outlet_id, gst_rate=5.0, **kwargs):
        cols = list(df.columns)
        m = {f: find_col(cols, a) for f, a in PETPOOJA_ALIASES.items()}
        records, errors, warnings = [], [], []

        for idx, row in df.iterrows():
            try:
                gross_raw = float(safe_num(pd.Series([row[m["gross_amount"]]]))[0]) if m["gross_amount"] else 0.0
                gross = strip_gst(gross_raw, gst_rate)
                channel = self._map_channel(row[m["channel"]]) if m["channel"] else "dine_in"
                rec = self._base_record(session_id, outlet_id)
                rec.update({
                    "channel":      channel,
                    "date":         safe_date(pd.Series([row[m["date"]]]))[0] if m["date"] else None,
                    "order_id":     str(row[m["order_id"]])[:100] if m["order_id"] else None,
                    "customer_id":  hash_customer_id(str(row[m["customer_id"]]) if m["customer_id"] else "", outlet_id),
                    "gross_amount": gross,
                    "commission": 0.0, "ad_spend": 0.0, "penalty": 0.0, "discount": 0.0, "net_payout": gross,
                    "item_name":    str(row[m["item_name"]]) if m["item_name"] else None,
                    "quantity":     float(safe_num(pd.Series([row[m["quantity"]]]))[0]) if m["quantity"] else None,
                    "unit_price":   float(safe_num(pd.Series([row[m["unit_price"]]]))[0]) if m["unit_price"] else None,
                    "is_deduplicated": False,
                })
                records.append(rec)
            except Exception as e:
                errors.append(f"Row {idx}: {e}")
                if len(errors) > 20: break

        return ParseResult(self.source_type, self.data_category, records, len(df), errors, warnings)


"""
tally.py — Tally purchase/sales voucher parser.
Produces PurchaseRecord rows (data_category: purchases).
"""
TALLY_ALIASES = {
    "date":         ["voucher date", "date", "bill date", "invoice date"],
    "reference_id": ["voucher no", "voucher number", "ref no", "bill no", "invoice no"],
    "vendor_name":  ["party name", "party", "supplier", "vendor", "ledger name"],
    "item_name":    ["stock item", "item name", "item", "product", "goods", "material"],
    "quantity":     ["quantity", "qty", "units"],
    "unit":         ["unit", "uom", "unit of measure"],
    "unit_cost":    ["rate", "price", "unit price", "unit rate"],
    "total_cost":   ["amount", "total amount", "value", "net amount", "total value"],
    "category":     ["category", "group", "stock group", "item group"],
}

class TallyParser(BaseParser):
    source_type   = "tally"
    data_category = "purchases"

    def parse(self, df, session_id, outlet_id, gst_rate=5.0, **kwargs):
        cols = list(df.columns)
        m = {f: find_col(cols, a) for f, a in TALLY_ALIASES.items()}
        records, errors = [], []

        for idx, row in df.iterrows():
            try:
                qty  = float(safe_num(pd.Series([row[m["quantity"]]]))[0]) if m["quantity"] else None
                uc   = float(safe_num(pd.Series([row[m["unit_cost"]]]))[0]) if m["unit_cost"] else None
                tot  = float(safe_num(pd.Series([row[m["total_cost"]]]))[0]) if m["total_cost"] else None
                # Derive total from qty × unit_cost if total not present
                if tot is None and qty and uc:
                    tot = round(qty * uc, 2)
                rec = self._base_record(session_id, outlet_id)
                rec.update({
                    "date":               safe_date(pd.Series([row[m["date"]]]))[0] if m["date"] else None,
                    "reference_id":       str(row[m["reference_id"]])[:100] if m["reference_id"] else None,
                    "vendor_name":        str(row[m["vendor_name"]]) if m["vendor_name"] else None,
                    "ingredient_name":    str(row[m["item_name"]]) if m["item_name"] else None,
                    "category":           str(row[m["category"]]) if m["category"] else None,
                    "quantity_purchased": qty,
                    "unit":               str(row[m["unit"]]) if m["unit"] else None,
                    "unit_cost":          uc,
                    "total_cost":         tot,
                })
                records.append(rec)
            except Exception as e:
                errors.append(f"Row {idx}: {e}")
                if len(errors) > 20: break

        return ParseResult(self.source_type, self.data_category, records, len(df), errors)


"""
payroll.py — Payroll/labor sheet parser.
Produces LaborRecord rows (data_category: labor).
"""
PAYROLL_ALIASES = {
    "date":          ["date", "pay date", "month", "period", "salary date"],
    "period_from":   ["from", "period from", "start date", "from date"],
    "period_to":     ["to", "period to", "end date", "to date"],
    "employee_name": ["employee", "employee name", "staff", "name", "staff name"],
    "role":          ["designation", "role", "position", "department", "post"],
    "shift":         ["shift", "shift type"],
    "hours_worked":  ["hours", "hours worked", "working hours", "ot hours", "total hours"],
    "wage_per_hour": ["hourly rate", "wage per hour", "rate per hour"],
    "labor_cost":    ["net pay", "wage", "salary", "total wages", "amount paid",
                      "net wages", "basic pay", "gross pay", "total salary"],
}

class PayrollParser(BaseParser):
    source_type   = "payroll"
    data_category = "labor"

    def parse(self, df, session_id, outlet_id, gst_rate=5.0, **kwargs):
        cols = list(df.columns)
        m = {f: find_col(cols, a) for f, a in PAYROLL_ALIASES.items()}
        records, errors = [], []

        for idx, row in df.iterrows():
            try:
                labor = float(safe_num(pd.Series([row[m["labor_cost"]]]))[0]) if m["labor_cost"] else None
                if labor is None or labor == 0:
                    continue  # skip rows with no labor cost
                rec = self._base_record(session_id, outlet_id)
                rec.update({
                    "date":          safe_date(pd.Series([row[m["date"]]]))[0] if m["date"] else None,
                    "period_from":   safe_date(pd.Series([row[m["period_from"]]]))[0] if m["period_from"] else None,
                    "period_to":     safe_date(pd.Series([row[m["period_to"]]]))[0] if m["period_to"] else None,
                    "employee_name": str(row[m["employee_name"]]) if m["employee_name"] else None,
                    "role":          str(row[m["role"]]) if m["role"] else None,
                    "shift":         str(row[m["shift"]]) if m["shift"] else None,
                    "hours_worked":  float(safe_num(pd.Series([row[m["hours_worked"]]]))[0]) if m["hours_worked"] else None,
                    "wage_per_hour": float(safe_num(pd.Series([row[m["wage_per_hour"]]]))[0]) if m["wage_per_hour"] else None,
                    "labor_cost":    labor,
                })
                records.append(rec)
            except Exception as e:
                errors.append(f"Row {idx}: {e}")
                if len(errors) > 20: break

        return ParseResult(self.source_type, self.data_category, records, len(df), errors)


"""
generic.py — Generic CSV fallback parser.
Used when source cannot be identified or user selects "Other".
Produces SalesRecord rows best-effort.
"""
GENERIC_ALIASES = {
    "date":         ["date", "time", "created", "order_date", "transaction", "timestamp"],
    "gross_amount": ["revenue", "amount", "total", "sales", "price", "value", "net", "gross"],
    "customer_id":  ["customer", "client", "user", "buyer", "email"],
    "item_name":    ["product", "item", "sku", "name", "description"],
    "quantity":     ["quantity", "qty", "units", "count"],
}

class GenericParser(BaseParser):
    source_type   = "generic"
    data_category = "generic"

    def parse(self, df, session_id, outlet_id, gst_rate=0.0, **kwargs):
        cols = list(df.columns)
        m = {f: find_col(cols, a) for f, a in GENERIC_ALIASES.items()}
        records, errors = [], []

        for idx, row in df.iterrows():
            try:
                gross = float(safe_num(pd.Series([row[m["gross_amount"]]]))[0]) if m["gross_amount"] else 0.0
                rec = self._base_record(session_id, outlet_id)
                rec.update({
                    "channel":      "other",
                    "date":         safe_date(pd.Series([row[m["date"]]]))[0] if m["date"] else None,
                    "gross_amount": gross,
                    "customer_id":  hash_customer_id(str(row[m["customer_id"]]) if m["customer_id"] else "", outlet_id),
                    "item_name":    str(row[m["item_name"]]) if m["item_name"] else None,
                    "quantity":     float(safe_num(pd.Series([row[m["quantity"]]]))[0]) if m["quantity"] else None,
                    "commission": 0.0, "ad_spend": 0.0, "penalty": 0.0,
                    "discount": 0.0, "net_payout": gross,
                    "is_deduplicated": False,
                })
                records.append(rec)
            except Exception as e:
                errors.append(f"Row {idx}: {e}")
                if len(errors) > 20: break

        return ParseResult(self.source_type, self.data_category, records, len(df), errors)

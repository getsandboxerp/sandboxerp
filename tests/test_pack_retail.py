"""
tests.test_pack_retail
~~~~~~~~~~~~~~~~~~~~~~

Structural integrity tests for the retail industry pack.

Covers:
- Loader: retail pack loads correctly.
- meta: required fields, generic flag, odoo modules.
- products: categories, attributes, SKU prefixes, counts by profile.
- customers: segments, weights sum to 1, required fields.
- suppliers: profiles, category affinity, counts by profile.
- transactions: causal chain steps, volumes by profile.
- inventory: warehouse locations, reorder rules, initial stock.
- pos: premium flag, payment methods, sessions.
- advanced_inventory: premium flag, multi-warehouse, tracking.

:author: Hector Colina / Team360 <https://team360.cl>
"""

import pytest

from sandboxerp.packs.loader import load_industry_pack


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def retail():
    """Load retail.yaml once for all tests."""
    return load_industry_pack("retail", "cl")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class TestRetailLoader:
    def test_loads_as_dict(self, retail):
        assert isinstance(retail, dict)

    def test_is_generic(self, retail):
        assert retail["meta"]["generic"] is True

    def test_not_premium(self, retail):
        assert retail["meta"]["premium"] is False


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------

class TestRetailMeta:
    REQUIRED_FIELDS = ["code", "name", "layer", "generic", "premium", "odoo_modules"]

    def test_required_fields(self, retail):
        for field in self.REQUIRED_FIELDS:
            assert field in retail["meta"], f"Missing meta field: {field}"

    def test_code_is_retail(self, retail):
        assert retail["meta"]["code"] == "retail"

    def test_layer_is_3(self, retail):
        assert retail["meta"]["layer"] == 3

    def test_odoo_modules_install_order(self, retail):
        modules = retail["meta"]["odoo_modules"]["install_order"]
        assert "sale_management" in modules
        assert "purchase" in modules
        assert "stock" in modules
        assert "account" in modules

    def test_sale_stock_bridge_present(self, retail):
        modules = retail["meta"]["odoo_modules"]["install_order"]
        assert "sale_stock" in modules


# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------

class TestRetailProducts:
    REQUIRED_PROFILES = ["small", "medium", "enterprise", "benchmark"]
    REQUIRED_CATEGORIES = ["ELEC", "ROPA", "HOGAR", "ALIM", "DEPOR", "BELLEZA"]

    def test_product_type_is_storable(self, retail):
        assert retail["products"]["type"] == "product"

    def test_cost_method(self, retail):
        assert retail["products"]["cost_method"] == "average_price"

    def test_category_codes(self, retail):
        codes = {c["code"] for c in retail["products"]["categories"]}
        for code in self.REQUIRED_CATEGORIES:
            assert code in codes, f"Missing category: {code}"

    def test_category_has_price_range(self, retail):
        for cat in retail["products"]["categories"]:
            pr = cat["price_range"]
            assert len(pr) == 2
            assert pr[0] < pr[1]

    def test_category_has_margin(self, retail):
        for cat in retail["products"]["categories"]:
            assert 0 < cat["margin_pct"] < 1

    def test_attributes_have_values(self, retail):
        for attr in retail["products"]["attributes"]:
            assert len(attr["values"]) > 0

    def test_sku_prefix_for_all_categories(self, retail):
        prefixes = retail["products"]["sku_prefix_by_category"]
        for code in self.REQUIRED_CATEGORIES:
            assert code in prefixes

    def test_count_by_profile_ascending(self, retail):
        counts = retail["products"]["count_by_profile"]
        assert counts["small"] < counts["medium"]
        assert counts["medium"] < counts["enterprise"]
        assert counts["enterprise"] < counts["benchmark"]

    def test_all_profiles_present_in_counts(self, retail):
        counts = retail["products"]["count_by_profile"]
        for p in self.REQUIRED_PROFILES:
            assert p in counts


# ---------------------------------------------------------------------------
# customers
# ---------------------------------------------------------------------------

class TestRetailCustomers:
    def test_segments_exist(self, retail):
        assert len(retail["customers"]["segments"]) > 0

    def test_segment_required_fields(self, retail):
        for seg in retail["customers"]["segments"]:
            for field in ("code", "label", "b2b", "payment_term", "weight"):
                assert field in seg, f"Segment missing field: {field}"

    def test_weights_sum_to_one(self, retail):
        total = sum(s["weight"] for s in retail["customers"]["segments"])
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_has_b2c_segment(self, retail):
        b2c = [s for s in retail["customers"]["segments"] if not s["b2b"]]
        assert len(b2c) > 0

    def test_has_b2b_segment(self, retail):
        b2b = [s for s in retail["customers"]["segments"] if s["b2b"]]
        assert len(b2b) > 0

    def test_count_by_profile_ascending(self, retail):
        counts = retail["customers"]["count_by_profile"]
        assert counts["small"] < counts["medium"]
        assert counts["medium"] < counts["enterprise"]


# ---------------------------------------------------------------------------
# suppliers
# ---------------------------------------------------------------------------

class TestRetailSuppliers:
    def test_profiles_exist(self, retail):
        assert len(retail["suppliers"]["profiles"]) > 0

    def test_profile_required_fields(self, retail):
        for prof in retail["suppliers"]["profiles"]:
            for field in ("code", "label", "lead_time_days", "payment_term", "weight"):
                assert field in prof

    def test_lead_time_is_range(self, retail):
        for prof in retail["suppliers"]["profiles"]:
            lt = prof["lead_time_days"]
            assert len(lt) == 2
            assert lt[0] < lt[1]

    def test_category_affinity_keys_match_profiles(self, retail):
        profile_codes = {p["code"] for p in retail["suppliers"]["profiles"]}
        affinity_keys = set(retail["suppliers"]["category_affinity"].keys())
        assert affinity_keys == profile_codes

    def test_count_by_profile_ascending(self, retail):
        counts = retail["suppliers"]["count_by_profile"]
        assert counts["small"] < counts["medium"]
        assert counts["medium"] < counts["enterprise"]


# ---------------------------------------------------------------------------
# transactions
# ---------------------------------------------------------------------------

class TestRetailTransactions:
    REQUIRED_STEPS = [
        "purchase_order", "receipt", "vendor_bill", "vendor_payment",
        "sale_order", "delivery", "customer_invoice", "customer_payment",
    ]

    def test_chain_has_all_steps(self, retail):
        steps = {s["step"] for s in retail["transactions"]["chain"]}
        for step in self.REQUIRED_STEPS:
            assert step in steps, f"Missing chain step: {step}"

    def test_so_chains_by_profile_ascending(self, retail):
        chains = retail["transactions"]["so_chains_by_profile"]
        assert chains["small"] < chains["medium"]
        assert chains["medium"] < chains["enterprise"]

    def test_po_chains_by_profile_ascending(self, retail):
        chains = retail["transactions"]["po_chains_by_profile"]
        assert chains["small"] < chains["medium"]

    def test_payment_terms_defined(self, retail):
        terms = retail["transactions"]["payment_terms"]
        assert "immediate" in terms
        assert "30_days" in terms
        assert "60_days" in terms

    def test_immediate_payment_term_is_zero_days(self, retail):
        assert retail["transactions"]["payment_terms"]["immediate"]["days"] == 0


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------

class TestRetailInventory:
    REQUIRED_LOCATIONS = ["WH/Stock", "WH/Input", "WH/Output"]
    REQUIRED_TURNOVER_LEVELS = ["very_high", "high", "medium", "low"]

    def test_warehouse_name_present(self, retail):
        assert "name" in retail["inventory"]["warehouse"]

    def test_required_locations(self, retail):
        locations = retail["inventory"]["warehouse"]["locations"]
        for loc in self.REQUIRED_LOCATIONS:
            assert loc in locations

    def test_reorder_rules_turnover_levels(self, retail):
        rules = retail["inventory"]["reorder_rules"]
        for level in self.REQUIRED_TURNOVER_LEVELS:
            assert level in rules

    def test_reorder_min_less_than_max(self, retail):
        for level, rule in retail["inventory"]["reorder_rules"].items():
            assert rule["min_qty"] < rule["max_qty"], f"min >= max for {level}"

    def test_initial_stock_by_profile_ascending(self, retail):
        stock = retail["inventory"]["initial_stock_by_profile"]
        assert stock["small"] <= stock["medium"]
        assert stock["medium"] <= stock["enterprise"]


# ---------------------------------------------------------------------------
# pos (premium)
# ---------------------------------------------------------------------------

class TestRetailPOS:
    def test_pos_is_premium(self, retail):
        assert retail["pos"]["premium"] is True

    def test_pos_has_odoo_module(self, retail):
        assert "point_of_sale" in retail["pos"]["odoo_modules"]

    def test_pos_has_payment_methods(self, retail):
        assert len(retail["pos"]["payment_methods"]) > 0

    def test_pos_has_default_payment_method(self, retail):
        defaults = [m for m in retail["pos"]["payment_methods"] if m.get("default")]
        assert len(defaults) == 1

    def test_pos_return_rate_between_0_and_1(self, retail):
        rate = retail["pos"]["return_rate"]
        assert 0 <= rate <= 1

    def test_pos_sessions_by_profile_ascending(self, retail):
        sessions = retail["pos"]["sessions_by_profile"]
        assert sessions["small"] < sessions["medium"]
        assert sessions["medium"] < sessions["enterprise"]


# ---------------------------------------------------------------------------
# advanced_inventory (premium)
# ---------------------------------------------------------------------------

class TestRetailAdvancedInventory:
    def test_advanced_inventory_is_premium(self, retail):
        assert retail["advanced_inventory"]["premium"] is True

    def test_multi_warehouse_warehouses_ascending(self, retail):
        wh = retail["advanced_inventory"]["multi_warehouse"]["warehouses_by_profile"]
        assert wh["small"] <= wh["medium"]
        assert wh["medium"] <= wh["enterprise"]

    def test_tracking_categories_defined(self, retail):
        tracking = retail["advanced_inventory"]["tracking"]
        assert "lot_categories" in tracking
        assert "serial_categories" in tracking
        assert "none_categories" in tracking

    def test_inter_warehouse_volume_pct_valid(self, retail):
        pct = retail["advanced_inventory"]["inter_warehouse_transfers"]["volume_pct"]
        assert 0 < pct < 1

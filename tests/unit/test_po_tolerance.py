from invoice_processing.agent.tools import _tolerance_for_po_type
from invoice_processing.config import get_settings
from invoice_processing.erp_mock.enums import PurchaseOrderType


def test_each_po_type_maps_to_its_own_configured_tolerance():
    settings = get_settings()
    assert _tolerance_for_po_type(PurchaseOrderType.GOODS) == settings.agent_po_variance_tolerance_goods_pct
    assert (
        _tolerance_for_po_type(PurchaseOrderType.SERVICES)
        == settings.agent_po_variance_tolerance_services_pct
    )
    assert (
        _tolerance_for_po_type(PurchaseOrderType.INDIRECT)
        == settings.agent_po_variance_tolerance_indirect_pct
    )


def test_goods_is_the_tightest_tolerance_by_default_config():
    # Not a business rule per se, but the whole point of this feature is that goods
    # (precise, countable) should be held to a tighter tolerance than services/indirect
    # (more often estimated) -- assert the seed config actually reflects that ordering.
    goods = _tolerance_for_po_type(PurchaseOrderType.GOODS)
    services = _tolerance_for_po_type(PurchaseOrderType.SERVICES)
    indirect = _tolerance_for_po_type(PurchaseOrderType.INDIRECT)
    assert goods <= services <= indirect


def test_unrecognized_po_type_falls_back_to_the_tightest_tolerance():
    settings = get_settings()
    assert _tolerance_for_po_type("something_unexpected") == settings.agent_po_variance_tolerance_goods_pct

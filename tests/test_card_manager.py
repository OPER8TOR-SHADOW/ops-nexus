from gui.page_manager import PageManager
from gui.pages.card_manager import CardManagerPage, build_workflow_status


def test_build_workflow_status_defaults_to_pending():
    status = build_workflow_status({})

    assert status["imported"] is True
    assert status["images"] is False
    assert status["github"] is False
    assert status["inventory"] is False
    assert status["pricing"] is False
    assert status["ebay"] is False


def test_show_card_manager_passes_selected_set():
    class DummyContainer:
        pass

    page_manager = PageManager(DummyContainer())
    captured = {}

    def fake_show_page(page_class, *args, **kwargs):
        captured["page_class"] = page_class
        captured["kwargs"] = kwargs

    page_manager.show_page = fake_show_page

    page_manager.show_card_manager(selected_set="abc")

    assert captured["page_class"] is CardManagerPage
    assert captured["kwargs"]["selected_set"] == "abc"

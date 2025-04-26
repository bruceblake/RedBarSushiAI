import pytest

@pytest.mark.e2e
def test_update_menu(api_request):
    payload = {"test": 1}

    resp = api_request.post("/menu_update", data=payload)
    assert resp.status == 201


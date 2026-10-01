def test_nav_links_render(client):
    pages = {
        "/purchases/returns": b"Expenditure Returns",
        "/reports/budget-variance?period=2026-09": b"Budget vs Actual",
        "/reports/expenditure-returns": b"Expenditure Returns",
    }
    for url, marker in pages.items():
        response = client.get(url)
        assert response.status_code == 200, (url, response.status_code)
        assert marker in response.data, url


def test_sidebar_exposes_expenditure_returns(client):
    response = client.get("/reports/budget-variance?period=2026-09")
    assert response.status_code == 200
    assert b"/purchases/returns" in response.data
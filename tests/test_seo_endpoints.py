"""Basic SEO endpoint checks (robots + sitemap).

These tests are intentionally lightweight:
- They ensure the endpoints respond and have expected content patterns.
- They avoid asserting on exact URL lists because DB content varies.
"""


def test_robots_txt(client):
    resp = client.get('/robots.txt')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'User-agent:' in body
    assert 'Sitemap:' in body


def test_sitemap_xml(client):
    resp = client.get('/sitemap.xml')
    assert resp.status_code == 200
    assert resp.mimetype in ('application/xml', 'text/xml')
    body = resp.get_data(as_text=True)
    assert '<urlset' in body
    assert '<loc>' in body

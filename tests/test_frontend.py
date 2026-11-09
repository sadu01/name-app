from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IdCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.tags = set()

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        self.ids.update(value for key, value in attrs if key == "id")


def test_frontend_exposes_auth_controls_and_uses_memory_only_tokens():
    html = (ROOT / "frontend" / "index.html").read_text()
    script = (ROOT / "frontend" / "script.js").read_text()
    parser = IdCollector()
    parser.feed(html)

    assert {"loginForm", "registerForm", "logoutBtn", "currentUser"} <= parser.ids
    assert "form" in parser.tags
    assert "data-toggle-password" in html
    assert 'id="registerMobileNumber" name="mobile_number" type="tel"' in html
    assert 'maxlength="15"' in html
    assert 'pattern="\\+?[0-9]{1,15}"' in html
    assert "Object.fromEntries(new FormData(registerForm))" in script
    assert "Authorization" in script and "Bearer ${accessToken}" in script
    assert "credentials: 'include'" in script
    assert "window.location.hostname" in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "Number(blog.user_id) === Number(currentUser.id)" in script
    assert "user_id: Number(" not in script
    assert {"profilePanel", "mobileNumberForm", "profileMobileNumber"} <= parser.ids
    assert "method: 'PATCH'" in script
    assert "currentUser = await authenticatedRequest('/me')" in script
    assert 'id="registerMobileNumber" name="mobile_number" type="tel"' in html

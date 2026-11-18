"""A11Y-02 (server side) and the form components: every control has a label, and each error
is linked to its control by aria-describedby (plan 4.4)."""

import re

import pytest


@pytest.mark.django_db
def test_a11y_02_register_errors_are_linked_and_summarised(client):
    html = client.post("/register", {}).content.decode()
    assert 'class="error-summary"' in html and 'role="alert"' in html and "autofocus" in html
    for name in ("email", "first_name", "password1", "adult"):
        assert f'id="id_{name}_error"' in html, name
        control = re.search(rf'<(?:input|select)[^>]*name="{name}"[^>]*>', html).group(0)
        assert f"id_{name}_error" in control and 'aria-invalid="true"' in control, name
        assert f'href="#id_{name}"' in html, name
    fieldset = re.search(r"<fieldset[^>]*>", html).group(0)
    assert "id_role_error" in fieldset
    assert 'href="#id_role_0"' in html


@pytest.mark.django_db
def test_register_form_labels_every_control_and_groups_the_fields(client):
    html = client.get("/register").content.decode()
    ids = re.findall(r'<(?:input|select)[^>]*\bid="(id_[a-z0-9_]+)"', html)
    assert len(ids) >= 10
    for control_id in ids:
        assert f'for="{control_id}"' in html, control_id
    for group in ("Your account", "Your profile", "Before you start"):
        assert group in html
    assert "<legend" in html and "How will you use Campus Chefs?" in html
    assert 'class="btn btn-primary">Create account' in html
    assert 'aria-describedby="id_password1_helptext"' in html
    assert "12 to 128 characters" in html


@pytest.mark.django_db
def test_logout_is_a_nav_styled_post_button(client):
    from tests import factories as f

    client.force_login(f.user())
    html = client.get("/me").content.decode()
    form = html[html.index('action="/logout"') - 60 : html.index("Log out</button>")]
    assert 'method="post"' in form and 'class="nav-button"' in form
    assert 'aria-current="page"' in html[html.index('href="/me"') - 40 : html.index("My account</a>")]

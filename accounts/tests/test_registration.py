import pytest
from django.db import connection

from accounts.models import User
from meals.models import CookProfile
from tests import factories as f

PASSWORD = "a-long-test-password-1"
EMAIL = "new.student@larkspur.example"


def _data(**overrides):
    data = {
        "email": EMAIL,
        "first_name": "Rory",
        "last_name": "Vance",
        "campus": f.campus().pk,
        "classification": "junior",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "adult": "on",
        "role": "eat",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


@pytest.mark.django_db
def test_reg_01_valid_registration_stores_argon2id_and_never_the_plaintext(client):
    response = client.post("/register", _data())
    assert response.status_code == 302
    assert response["Location"] == "/me"
    user = User.objects.get(email=EMAIL)
    assert user.password.startswith("argon2$argon2id$")
    assert user.adult_attested_at is not None
    assert user.classification == "junior"
    assert int(client.session["_auth_user_id"]) == user.pk

    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM accounts_user WHERE id = %s", [user.pk])
        assert PASSWORD not in [str(v) for v in cursor.fetchone()]


@pytest.mark.django_db
def test_reg_01_blank_classification_is_stored_as_null(client):
    assert client.post("/register", _data(classification="")).status_code == 302
    assert User.objects.get(email=EMAIL).classification is None


@pytest.mark.django_db
def test_reg_02_password_confirmation_mismatch(client):
    response = client.post("/register", _data(password2="a-different-password-9"))
    assert response.status_code == 200
    assert "The two password fields didn’t match." in response.content.decode()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_reg_03_email_already_registered_case_insensitive(client):
    f.user(email="ava.r@larkspur.example")
    count = User.objects.count()
    response = client.post("/register", _data(email="AVA.R@Larkspur.example"))
    assert response.status_code == 200
    assert b"already registered" in response.content
    assert User.objects.count() == count


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("elevenchars", "too short"),
        ("password1234", "too common"),
        ("x7-" * 43, "too long"),  # 129 characters
    ],
)
def test_reg_04_password_validators(client, password, message):
    response = client.post("/register", _data(password1=password, password2=password))
    assert response.status_code == 200
    assert message in response.content.decode()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_reg_05_tampered_campus_id(client):
    response = client.post("/register", _data(campus=99999))
    assert response.status_code == 200
    assert b"Select a valid choice" in response.content
    assert not User.objects.exists()


@pytest.mark.django_db
def test_reg_06_cook_role_needs_food_safety_ack(client):
    response = client.post("/register", _data(role="cook"))
    assert response.status_code == 200
    assert b"food-safety acknowledgement" in response.content
    assert not User.objects.exists()

    assert client.post("/register", _data(role="cook", food_safety="on")).status_code == 302
    assert CookProfile.objects.filter(user__email=EMAIL).exists()


@pytest.mark.django_db
def test_reg_06_eat_role_creates_no_cook_profile(client):
    assert client.post("/register", _data(role="eat", food_safety="on")).status_code == 302
    assert User.objects.filter(email=EMAIL).exists()
    assert not CookProfile.objects.exists()


@pytest.mark.django_db
def test_reg_07_adult_attestation_required(client):
    response = client.post("/register", _data(adult=None))
    assert response.status_code == 200
    assert b"18 or older" in response.content
    assert not User.objects.exists()


@pytest.mark.django_db
def test_reg_08_registration_by_get_creates_nothing(client):
    response = client.get("/register", _data())
    assert response.status_code == 200
    assert not User.objects.exists()


@pytest.mark.django_db
def test_reg_09_apostrophe_name_stored_raw_and_escaped_once(client):
    assert client.post("/register", _data(first_name="Sean", last_name="O'Brien")).status_code == 302
    assert User.objects.get(email=EMAIL).last_name == "O'Brien"
    page = client.get("/me").content
    assert page.count(b"O&#x27;Brien") == 1
    assert b"O'Brien" not in page


@pytest.mark.django_db
def test_reg_10_legacy_personal_fields_ignored_and_absent(client):
    response = client.post("/register", _data(sex="F", age="19", transportation="car"))
    assert response.status_code == 302
    names = {field.name for field in User._meta.get_fields()}
    assert not names & {"sex", "gender", "age", "transportation", "car", "residence"}


@pytest.mark.django_db
def test_reg_11_registration_switch(client, settings):
    settings.CC_REGISTRATION_OPEN = True
    page = client.get("/register")
    assert page.status_code == 200
    assert b"Use made-up details." in page.content
    assert b'href="/register"' in client.get("/").content

    settings.CC_REGISTRATION_OPEN = False
    assert client.get("/register").status_code == 404
    assert client.post("/register", _data()).status_code == 404
    assert b'href="/register"' not in client.get("/").content
    assert b'href="/register"' not in client.get("/login").content
    assert not User.objects.exists()

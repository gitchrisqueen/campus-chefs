"""Phase 12: AI menu import (plan AI-01..AI-05). Fully mocked: no network, no API key, no SDK client."""

import ast
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from meals.models import ALLERGENS, DIETARY_TAGS, Course, MealType, MenuItem
from menuparse import service, views
from menuparse.schema import MenuDraft
from menuparse.service import MAX_MENU_CHARS, MenuParseError
from tests import factories as f

PASTE_URL = "/kitchen/import"
CONFIRM_URL = "/kitchen/import/confirm"
PASTED = "Sunday brunch: lemon pancakes with butter, and a fruit salad."  # synthetic


def dish(**overrides):
    data = {
        "name": "Lemon Pancakes",
        "description": "Fluffy pancakes with lemon and butter.",
        "meal_type": "breakfast",
        "course": "main",
        "allergens": ["milk", "egg", "wheat"],
        "dietary_tags": ["vegetarian"],
    }
    data.update(overrides)
    return data


def draft(*dishes):
    return MenuDraft.model_validate({"dishes": list(dishes) or [dish()]})


def fake_client(parsed=None, *, stop_reason="end_turn", side_effect=None):
    client = mock.Mock()
    response = SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed, _request_id="req_test_1")
    if side_effect is not None:
        client.messages.parse.side_effect = side_effect
    else:
        client.messages.parse.return_value = response
    return client


@pytest.fixture
def ai_on(settings):
    settings.CC_AI_ENABLED = True
    settings.CC_AI_MODEL = "test-model-id"


@pytest.fixture
def cook(db):
    return f.cook(first="Marcus", last="Bell", email="marcus.b@larkspur.example")


@pytest.fixture
def other_cook(db):
    return f.cook(first="Elena", last="Ortiz", email="elena.o@larkspur.example")


def formset_data(*dishes, confirm=True, deleted=()):
    data = {
        "form-TOTAL_FORMS": str(len(dishes)),
        "form-INITIAL_FORMS": str(len(dishes)),
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "20",
    }
    for i, d in enumerate(dishes):
        for key, value in d.items():
            data[f"form-{i}-{key}"] = value
        if i in deleted:
            data[f"form-{i}-DELETE"] = "on"
    if confirm:
        data["allergens_complete"] = "on"
    return data


# --- AI-01: the flag ---------------------------------------------------------------------


@pytest.mark.django_db
def test_ai_01_flag_off_returns_404_and_never_builds_a_client(client, cook, settings):
    settings.CC_AI_ENABLED = False
    client.force_login(cook.user)
    with mock.patch.object(service, "build_client") as build:
        assert client.get(PASTE_URL).status_code == 404
        assert client.post(PASTE_URL, {"text": PASTED}).status_code == 404
        assert client.post(CONFIRM_URL, formset_data(dish())).status_code == 404
    build.assert_not_called()
    assert not MenuItem.objects.exists()


@pytest.mark.django_db
def test_ai_01_flag_off_hides_every_mention_in_the_kitchen_and_privacy_page(client, cook, settings):
    client.force_login(cook.user)
    settings.CC_AI_ENABLED = False
    assert "Paste a menu" not in client.get("/kitchen").content.decode()
    assert "AI service" not in client.get("/privacy").content.decode()
    settings.CC_AI_ENABLED = True
    assert "Paste a menu" in client.get("/kitchen").content.decode()
    assert "AI service" in client.get("/privacy").content.decode()


def test_ai_01_the_sdk_is_imported_only_inside_build_client():
    """No module-level `anthropic` import in menuparse, so a flag-off request never loads the SDK."""
    for path in Path(service.__file__).parent.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            assert not any(n.split(".")[0] == "anthropic" for n in names), f"{path.name} imports anthropic at top"


def test_ai_01_missing_key_is_a_friendly_error_not_a_crash(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY_FILE", raising=False)
    with pytest.raises(MenuParseError) as caught:
        service.build_client()
    assert caught.value.reason == "no_api_key"


def test_ai_01_the_key_is_read_from_a_file(monkeypatch, tmp_path):
    key_file = tmp_path / "key"
    key_file.write_text("generated-at-runtime-" + "x" * 12 + "\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY_FILE", str(key_file))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = service.build_client()
    assert client.api_key == "generated-at-runtime-" + "x" * 12


# --- AI-02: an editable draft, nothing saved until confirmed ------------------------------


@pytest.mark.django_db
def test_ai_02_valid_draft_renders_an_editable_formset_and_saves_nothing(client, cook, ai_on):
    client.force_login(cook.user)
    parsed = draft(dish(), dish(name="Fruit Salad", meal_type="breakfast", course="side", allergens=[]))
    fake = fake_client(parsed)
    with mock.patch.object(service, "build_client", return_value=fake):
        response = client.post(PASTE_URL, {"text": PASTED})
    assert response.status_code == 200
    body = response.content.decode()
    assert 'name="form-0-name"' in body and 'value="Lemon Pancakes"' in body
    assert 'name="form-1-name"' in body and "Fruit Salad" in body
    assert 'action="/kitchen/import/confirm"' in body
    assert MenuItem.objects.count() == 0
    sent = fake.messages.parse.call_args.kwargs
    assert sent["messages"] == [{"role": "user", "content": PASTED}]
    assert sent["output_format"] is MenuDraft and sent["model"] == "test-model-id"


@pytest.mark.django_db
def test_ai_02_only_the_pasted_text_is_sent(client, cook, ai_on):
    client.force_login(cook.user)
    fake = fake_client(draft())
    with mock.patch.object(service, "build_client", return_value=fake):
        client.post(PASTE_URL, {"text": PASTED})
    sent = repr(fake.messages.parse.call_args)
    for private in (cook.user.email, cook.user.first_name, cook.user.last_name, cook.user.campus.name):
        assert private not in sent
    assert set(fake.messages.parse.call_args.kwargs) == {
        "model",
        "max_tokens",
        "system",
        "messages",
        "output_format",
        "output_config",
    }


@pytest.mark.django_db
def test_ai_02_confirming_saves_the_cooks_own_items(client, cook, other_cook, ai_on):
    client.force_login(cook.user)
    data = formset_data(dish(allergens="milk"), dish(name="Fruit Salad", course="side", allergens="egg"))
    response = client.post(CONFIRM_URL, data)
    assert response.status_code == 302 and response["Location"] == "/kitchen"
    items = MenuItem.objects.order_by("name")
    assert [i.name for i in items] == ["Fruit Salad", "Lemon Pancakes"]
    assert {i.cook_id for i in items} == {cook.pk}
    assert not MenuItem.objects.filter(cook=other_cook).exists()
    assert all(i.allergens_confirmed_at is not None for i in items)


@pytest.mark.django_db
def test_ai_02_a_dish_left_out_is_not_saved(client, cook, ai_on):
    client.force_login(cook.user)
    data = formset_data(dish(), dish(name="Fruit Salad", course="side"), deleted={1})
    assert client.post(CONFIRM_URL, data).status_code == 302
    assert list(MenuItem.objects.values_list("name", flat=True)) == ["Lemon Pancakes"]


# --- AI-03: refusal, error, invalid output -> friendly message and the manual form ---------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fake",
    [
        fake_client(None, stop_reason="refusal"),
        fake_client(None),  # the model's output did not parse
        fake_client(side_effect=ValidationError.from_exception_data("MenuDraft", [])),
        fake_client(side_effect=anthropic.APIConnectionError(request=httpx2.Request("POST", "https://example.test"))),
        fake_client(side_effect=anthropic.APITimeoutError(request=httpx2.Request("POST", "https://example.test"))),
        fake_client(side_effect=RuntimeError("boom with a raw secret-ish detail")),
        fake_client(SimpleNamespace(dishes=[]), stop_reason="end_turn"),
        fake_client(MenuDraft(dishes=[])),
    ],
    ids=["refusal", "unparsed", "validation", "connection", "timeout", "unexpected", "wrong-type", "empty"],
)
def test_ai_03_failure_shows_a_friendly_message_and_the_manual_link(client, cook, ai_on, fake):
    client.force_login(cook.user)
    with mock.patch.object(service, "build_client", return_value=fake):
        response = client.post(PASTE_URL, {"text": PASTED})
    assert response.status_code == 200
    body = response.content.decode()
    assert 'href="/kitchen/items/new"' in body
    assert "Traceback" not in body and "boom" not in body and "APIConnectionError" not in body
    assert "error-summary" in body
    assert MenuItem.objects.count() == 0


@pytest.mark.django_db
def test_ai_03_invalid_enum_values_from_the_model_are_rejected(client, cook, ai_on):
    """A model value outside the MenuItem choices never reaches the formset."""
    client.force_login(cook.user)
    bad = SimpleNamespace(
        stop_reason="end_turn",
        _request_id="req_test_2",
        parsed_output=mock.Mock(spec=MenuDraft),
    )
    bad.parsed_output.dishes = [dish(allergens=["latex"])]
    fake = mock.Mock()
    fake.messages.parse.return_value = bad
    with mock.patch.object(service, "build_client", return_value=fake):
        response = client.post(PASTE_URL, {"text": PASTED})
    assert 'href="/kitchen/items/new"' in response.content.decode()
    for bad_dish in (
        dish(allergens=["latex"]),
        dish(meal_type="brunch"),
        dish(course="dessert"),
        dish(dietary_tags=["keto"]),
    ):
        with pytest.raises(ValidationError):
            MenuDraft.model_validate({"dishes": [bad_dish]})
    with pytest.raises(ValidationError):
        MenuDraft.model_validate({"dishes": [dish(extra_field="x")]})
    with pytest.raises(ValidationError):
        MenuDraft.model_validate({"dishes": [dish(name="x" * 81)]})


def test_ai_03_the_schema_enums_match_the_menu_item_choices():
    fields = MenuDraft.model_json_schema()["$defs"]["DraftDish"]["properties"]
    assert set(fields["meal_type"]["enum"]) == set(MealType.values)
    assert set(fields["course"]["enum"]) == set(Course.values)
    assert set(fields["allergens"]["items"]["enum"]) == {v for v, _ in ALLERGENS}
    assert set(fields["dietary_tags"]["items"]["enum"]) == {v for v, _ in DIETARY_TAGS}


@pytest.mark.django_db
def test_ai_03_logs_ids_and_error_class_but_never_the_pasted_text(client, cook, ai_on, caplog):
    client.force_login(cook.user)
    secret_text = "Grandma Zelda's moon-rock stew with 12 secret herbs"
    error = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://example.test"))
    with mock.patch.object(service, "build_client", return_value=fake_client(side_effect=error)):
        with caplog.at_level(logging.INFO):
            client.post(PASTE_URL, {"text": secret_text})
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "APIConnectionError" in logged and "test-model-id" in logged
    assert "moon-rock" not in logged and "Zelda" not in logged


# --- AI-04: the length limit --------------------------------------------------------------


@pytest.mark.django_db
def test_ai_04_4001_characters_is_a_validation_error_and_no_api_call(client, cook, ai_on):
    client.force_login(cook.user)
    with mock.patch.object(service, "build_client") as build:
        response = client.post(PASTE_URL, {"text": "a" * (MAX_MENU_CHARS + 1)})
    assert response.status_code == 200
    assert "text" in response.context["form"].errors
    build.assert_not_called()


@pytest.mark.django_db
def test_ai_04_exactly_4000_characters_is_accepted_and_blank_is_not(client, cook, ai_on):
    client.force_login(cook.user)
    fake = fake_client(draft())
    with mock.patch.object(service, "build_client", return_value=fake):
        assert client.post(PASTE_URL, {"text": "a" * MAX_MENU_CHARS}).status_code == 200
        assert fake.messages.parse.call_count == 1
        response = client.post(PASTE_URL, {"text": "   "})
    assert "text" in response.context["form"].errors
    assert fake.messages.parse.call_count == 1


def test_ai_04_the_service_refuses_long_text_even_if_the_form_is_skipped():
    with mock.patch.object(service, "build_client") as build, pytest.raises(MenuParseError):
        service.parse_menu("a" * (MAX_MENU_CHARS + 1))
    build.assert_not_called()


# --- AI-05: the allergen confirmation -----------------------------------------------------


@pytest.mark.django_db
def test_ai_05_without_the_tick_nothing_is_saved_and_no_confirmation_time_is_set(client, cook, ai_on):
    client.force_login(cook.user)
    response = client.post(CONFIRM_URL, formset_data(dish(), confirm=False))
    assert response.status_code == 200
    assert "allergens_complete" in response.context["confirm_form"].errors
    assert MenuItem.objects.count() == 0


@pytest.mark.django_db
def test_ai_05_with_the_tick_allergens_confirmed_at_is_set(client, cook, ai_on):
    client.force_login(cook.user)
    assert client.post(CONFIRM_URL, formset_data(dish())).status_code == 302
    assert MenuItem.objects.get().allergens_confirmed_at is not None


@pytest.mark.django_db
def test_ai_05_an_invalid_dish_blocks_the_whole_save(client, cook, ai_on):
    client.force_login(cook.user)
    data = formset_data(dish(), dish(name="Fruit Salad", allergens="latex"))
    response = client.post(CONFIRM_URL, data)
    assert response.status_code == 200
    assert MenuItem.objects.count() == 0
    assert response.context["formset"].total_error_count() >= 1


@pytest.mark.django_db
def test_ai_05_duplicate_names_are_rejected_inside_the_draft_and_against_the_menu(client, cook, ai_on):
    client.force_login(cook.user)
    response = client.post(CONFIRM_URL, formset_data(dish(), dish(name="lemon pancakes")))
    assert response.status_code == 200 and MenuItem.objects.count() == 0
    f.menu_item(cook, "Lemon Pancakes")
    response = client.post(CONFIRM_URL, formset_data(dish()))
    assert response.status_code == 200 and MenuItem.objects.count() == 1


@pytest.mark.django_db
def test_ai_05_deleting_every_dish_is_an_error_not_an_empty_success(client, cook, ai_on):
    client.force_login(cook.user)
    response = client.post(CONFIRM_URL, formset_data(dish(), deleted={0}))
    assert response.status_code == 200 and MenuItem.objects.count() == 0


# --- Authorization, CSRF, method ----------------------------------------------------------


@pytest.mark.django_db
def test_ai_authz_anonymous_is_sent_to_login(client, ai_on):
    for method, url in [("get", PASTE_URL), ("post", PASTE_URL), ("post", CONFIRM_URL)]:
        response = getattr(client, method)(url)
        assert response.status_code == 302 and response["Location"].startswith("/login"), (method, url)


@pytest.mark.django_db
def test_ai_authz_a_diner_without_a_kitchen_gets_403_and_no_api_call(client, ai_on):
    client.force_login(f.user(first="Jordan", last="Kim"))
    with mock.patch.object(service, "build_client") as build:
        assert client.get(PASTE_URL).status_code == 403
        assert client.post(PASTE_URL, {"text": PASTED}).status_code == 403
        assert client.post(CONFIRM_URL, formset_data(dish())).status_code == 403
    build.assert_not_called()
    assert not MenuItem.objects.exists()


@pytest.mark.django_db
def test_ai_authz_a_cook_cannot_write_into_another_cooks_menu(client, cook, other_cook, ai_on):
    """The cook comes from the session, never from the request, so a posted `cook` field changes nothing."""
    client.force_login(cook.user)
    data = formset_data(dish())
    data["form-0-cook"] = str(other_cook.pk)
    data["cook"] = str(other_cook.pk)
    assert client.post(CONFIRM_URL, data).status_code == 302
    assert MenuItem.objects.get().cook_id == cook.pk
    assert not MenuItem.objects.filter(cook=other_cook).exists()


@pytest.mark.django_db
def test_ai_authz_confirm_is_post_only_and_csrf_protected(ai_on, cook):
    from django.test import Client

    strict = Client(enforce_csrf_checks=True)
    strict.force_login(cook.user)
    assert strict.get(CONFIRM_URL).status_code == 405
    assert strict.post(CONFIRM_URL, formset_data(dish())).status_code == 403
    assert strict.post(PASTE_URL, {"text": PASTED}).status_code == 403
    assert not MenuItem.objects.exists()


# --- Model output is untrusted --------------------------------------------------------------


@pytest.mark.django_db
def test_ai_hostile_model_output_is_escaped_on_the_review_page(client, cook, ai_on):
    client.force_login(cook.user)
    hostile = dish(
        name='<script>alert("x")</script>',
        description='"><img src=x onerror=alert(1)> & <b>bold</b>',
    )
    with mock.patch.object(service, "build_client", return_value=fake_client(draft(hostile))):
        response = client.post(PASTE_URL, {"text": PASTED})
    body = response.content.decode()
    assert "<script>alert" not in body and "<img src=x" not in body and "<b>bold</b>" not in body
    assert "&lt;script&gt;" in body and "&lt;img src=x" in body


@pytest.mark.django_db
def test_ai_hostile_text_saved_by_the_cook_is_escaped_on_the_kitchen_page(client, cook, ai_on):
    client.force_login(cook.user)
    data = formset_data(dish(name="<script>alert(1)</script>", description="<img src=x onerror=alert(1)>"))
    assert client.post(CONFIRM_URL, data).status_code == 302
    body = client.get("/kitchen").content.decode()
    assert "<script>alert(1)" not in body and "<img src=x" not in body


@pytest.mark.django_db
def test_ai_pasted_text_is_escaped_when_the_page_is_shown_again(client, cook, ai_on):
    client.force_login(cook.user)
    with mock.patch.object(service, "build_client", return_value=fake_client(None, stop_reason="refusal")):
        body = client.post(PASTE_URL, {"text": "<script>alert(1)</script>"}).content.decode()
    assert "<script>alert(1)" not in body and "&lt;script&gt;" in body


# --- Page content ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ai_import_page_says_the_text_is_sent_to_an_ai_service_and_to_check_allergens(client, cook, ai_on):
    client.force_login(cook.user)
    body = client.get(PASTE_URL).content.decode()
    assert "sent to an AI service" in body
    assert "allergens" in body
    assert "2008" not in body and 'class="eyebrow"' not in body and "·" not in body.split("</title>", 1)[1]
    assert body.count("btn-primary") == 1


@pytest.mark.django_db
def test_ai_07_import_page_names_the_provider_and_its_retention(client, cook, ai_on):
    client.force_login(cook.user)
    body = client.get(PASTE_URL).content.decode()
    assert "Anthropic" in body
    assert "does not store the pasted text" in body
    assert "may keep it for a limited time under its own terms" in body
    assert "It is not stored" not in body
    assert "This can take up to 20 seconds." in body


@pytest.mark.django_db
def test_ai_07_import_page_tells_the_cook_what_not_to_paste(client, cook, ai_on):
    client.force_login(cook.user)
    body = client.get(PASTE_URL).content.decode()
    assert "Paste dish names and descriptions only." in body
    assert "Do not include names, phone numbers, addresses or health details." in body


@pytest.mark.django_db
def test_ai_07_privacy_page_names_the_provider_and_its_retention_only_when_the_flag_is_on(client, settings):
    settings.CC_AI_ENABLED = False
    off = client.get("/privacy").content.decode()
    assert "Anthropic" not in off and "limited time" not in off
    settings.CC_AI_ENABLED = True
    on = client.get("/privacy").content.decode()
    assert "Anthropic" in on
    assert "This site does not store that text." in on
    assert "may keep it for a limited time under its own terms" in on
    assert "It is not stored" not in on
    assert "does not remove text already sent to Anthropic" in on


# --- AI-06: rate limit --------------------------------------------------------------------


def _post_n(client, fake, n):
    with mock.patch.object(service, "build_client", return_value=fake):
        return [client.post(PASTE_URL, {"text": PASTED}) for _ in range(n)]


@pytest.mark.django_db
def test_ai_06_rate_limit_blocks_api_call(client, cook, ai_on, caplog):
    client.force_login(cook.user)
    limit = views.DRAFT_LIMITS[0][2]
    assert limit == 5
    fake = fake_client(draft())
    with caplog.at_level(logging.WARNING):
        responses = _post_n(client, fake, limit + 1)
    assert all("form-0-name" in r.content.decode() for r in responses[:limit])
    assert fake.messages.parse.call_count == limit
    last = responses[-1]
    body = last.content.decode()
    assert last.status_code == 429
    assert "form-0-name" not in body
    assert "several drafts in a row" in body
    assert 'href="/kitchen/items/new"' in body
    assert "menu draft blocked: rate_limited" in " ".join(r.getMessage() for r in caplog.records)
    assert MenuItem.objects.count() == 0


@pytest.mark.django_db
def test_ai_06_the_daily_cap_blocks_api_call(client, cook, ai_on, monkeypatch):
    assert views.DRAFT_LIMITS[1][1:] == (24 * 60 * 60, 20)
    monkeypatch.setattr(views, "DRAFT_LIMITS", (("burst", 600, 100), ("daily", 86400, 3)))
    client.force_login(cook.user)
    fake = fake_client(draft())
    responses = _post_n(client, fake, 4)
    assert fake.messages.parse.call_count == 3
    assert responses[-1].status_code == 429 and "today" in responses[-1].content.decode()
    assert 'href="/kitchen/items/new"' in responses[-1].content.decode()


@pytest.mark.django_db
def test_ai_06_the_limit_is_per_user_and_invalid_or_blocked_posts_do_not_count(client, cook, other_cook, ai_on):
    client.force_login(cook.user)
    with mock.patch.object(service, "build_client") as build:
        for _ in range(10):  # invalid form: no API call and nothing counted
            client.post(PASTE_URL, {"text": "   "})
        build.assert_not_called()
    fake = fake_client(draft())
    _post_n(client, fake, 7)  # two blocked posts add nothing
    assert fake.messages.parse.call_count == 5
    client.force_login(other_cook.user)
    other = fake_client(draft())
    assert _post_n(client, other, 1)[0].status_code == 200
    assert other.messages.parse.call_count == 1


@pytest.mark.django_db
def test_ai_06_a_broken_counter_blocks_the_call(client, cook, ai_on):
    client.force_login(cook.user)
    fake = fake_client(draft())
    with mock.patch("core.ratelimit.caches", side_effect=RuntimeError("cache down")):
        response = _post_n(client, fake, 1)[0]
    assert response.status_code == 429
    fake.messages.parse.assert_not_called()


@pytest.mark.django_db
def test_ai_review_page_has_one_primary_button_and_no_middle_dots(client, cook, ai_on):
    client.force_login(cook.user)
    with mock.patch.object(service, "build_client", return_value=fake_client(draft())):
        body = client.post(PASTE_URL, {"text": PASTED}).content.decode()
    assert body.count("btn-primary") == 1
    assert "·" not in body.split("</title>", 1)[1] and 'class="eyebrow"' not in body
    assert "Nothing is saved until you confirm" in body


@pytest.mark.django_db
def test_ai_the_request_uses_a_short_timeout_and_no_retries(monkeypatch, tmp_path):
    key_file = tmp_path / "key"
    key_file.write_text("generated-at-runtime-" + "y" * 12, encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY_FILE", str(key_file))
    client = service.build_client()
    assert client.max_retries == 0 and client.timeout == service.REQUEST_TIMEOUT_SECONDS

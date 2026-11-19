import logging
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from meals.views import RACE_MESSAGE, cook_required

from .forms import ConfirmDraftForm, DraftFormSet, PasteMenuForm
from .schema import MenuDraft
from .service import MenuParseError, parse_menu

logger = logging.getLogger(__name__)

FAILURE_MESSAGES = {
    "refusal": "The AI service would not draft this menu. Add your dishes by hand instead.",
    "invalid_output": (
        "The AI service sent back a draft we could not use, so nothing was kept. Try again, or add your dishes by hand."
    ),
    "no_dishes": (
        "We could not find any dishes in that text. Try again with the dish names, or add your dishes by hand."
    ),
}
UNAVAILABLE_MESSAGE = "Drafting a menu is not available right now. Try again later, or add your dishes by hand."


def ai_import_enabled(view):
    """The feature flag. With it off the page does not exist (AI-01), for everyone."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not settings.CC_AI_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapper


def _paste_page(request, form, failure=""):
    return render(request, "menuparse/import.html", {"form": form, "failure": failure})


def _review_page(request, formset, confirm_form):
    return render(request, "menuparse/review.html", {"formset": formset, "confirm_form": confirm_form})


def _initial(draft: MenuDraft) -> list[dict]:
    return [dish.model_dump() for dish in draft.dishes]


@ai_import_enabled
@cook_required
@require_http_methods(["GET", "POST"])
def import_menu(request, cook):
    form = PasteMenuForm(request.POST if request.method == "POST" else None)
    if not (form.is_bound and form.is_valid()):
        return _paste_page(request, form)
    try:
        draft = parse_menu(form.cleaned_data["text"])
    except MenuParseError as error:
        return _paste_page(request, form, FAILURE_MESSAGES.get(error.reason, UNAVAILABLE_MESSAGE))
    # Nothing is saved here (AI-02): the draft only fills an unbound formset the cook must confirm.
    formset = DraftFormSet(initial=_initial(draft), form_kwargs={"cook": cook})
    return _review_page(request, formset, ConfirmDraftForm())


@ai_import_enabled
@cook_required
@require_POST
def import_confirm(request, cook):
    formset = DraftFormSet(request.POST, form_kwargs={"cook": cook})
    confirm_form = ConfirmDraftForm(request.POST)
    formset_ok, confirm_ok = formset.is_valid(), confirm_form.is_valid()  # evaluate both, so every error shows
    if formset_ok and confirm_ok:
        try:
            with transaction.atomic():
                items = [form.save() for form in formset.kept_forms()]
        except IntegrityError:
            formset._non_form_errors = formset.error_class([RACE_MESSAGE], error_class="nonform")
            return _review_page(request, formset, confirm_form)
        logger.info("menu draft saved: cook %s items %s", cook.pk, [item.pk for item in items])
        count = len(items)
        messages.success(request, f"{count} {'dish was' if count == 1 else 'dishes were'} added to your menu.")
        return redirect("kitchen")
    return _review_page(request, formset, confirm_form)

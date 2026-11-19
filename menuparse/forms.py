from django import forms

from meals.forms import MenuItemForm

from .schema import MAX_DISHES
from .service import MAX_MENU_CHARS


class MenuTextField(forms.CharField):
    def to_python(self, value):
        # A browser sends a line break as two characters; count it as one, as the cook sees it.
        return super().to_python(value.replace("\r\n", "\n") if isinstance(value, str) else value)


class PasteMenuForm(forms.Form):
    text = MenuTextField(
        label="Your menu",
        max_length=MAX_MENU_CHARS,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 10}),
        help_text=f"Up to {MAX_MENU_CHARS:,} characters: dish names and a line about each.",
        error_messages={
            "required": "Paste your menu first.",
            "max_length": f"Keep the menu to {MAX_MENU_CHARS:,} characters or fewer. You pasted %(show_value)d.",
        },
    )


class DraftDishForm(MenuItemForm):
    """One drafted dish. It reuses every MenuItemForm rule (choices, lengths, duplicate names), minus the
    per-dish allergen tick: the cook confirms the whole draft once, on the page."""

    allergens_complete = None  # removes the inherited field

    class Meta(MenuItemForm.Meta):
        fields = ["name", "meal_type", "course", "description", "allergens", "dietary_tags"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}
        labels = {}
        help_texts = {}


class BaseDraftFormSet(forms.BaseFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        if "DELETE" in form.fields:
            form.fields["DELETE"].label = "Leave this dish out"

    def kept_forms(self) -> list:
        return [form for form in self.forms if not self._should_delete_form(form)]

    def clean(self):
        super().clean()
        seen: set[tuple[str, str]] = set()
        for form in self.forms:
            if not form.is_valid() or self._should_delete_form(form):
                continue
            key = (form.cleaned_data["meal_type"], form.cleaned_data["name"].lower())
            if key in seen:
                form.add_error("name", "Another dish in this draft has the same name for this meal.")
            seen.add(key)
        if all(self._should_delete_form(form) for form in self.forms):
            raise forms.ValidationError("Keep at least one dish, or go back and paste a menu again.")


DraftFormSet = forms.formset_factory(
    DraftDishForm,
    formset=BaseDraftFormSet,
    extra=0,
    can_delete=True,
    max_num=MAX_DISHES,
    validate_max=True,
)


class ConfirmDraftForm(forms.Form):
    allergens_complete = forms.BooleanField(
        label="I checked the allergens and dietary tags on every dish, and each list is complete",
        error_messages={"required": "Confirm that you checked the allergens before saving."},
    )

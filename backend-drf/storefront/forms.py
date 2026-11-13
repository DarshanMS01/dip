import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

from products.models import Category, Product

User = get_user_model()

INPUT_CLASS = "form-input"
SELECT_CLASS = "form-input form-select"
TEXTAREA_CLASS = "form-input form-textarea"


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "you@example.com",
                "autocomplete": "email",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "Your password",
                "autocomplete": "current-password",
            }
        ),
    )


class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        label="Full name",
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASS, "placeholder": "e.g. Ananya Sharma", "autocomplete": "name"}
        ),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={"class": INPUT_CLASS, "placeholder": "you@example.com", "autocomplete": "email"}
        ),
    )
    phone = forms.CharField(
        max_length=15,
        label="Mobile number",
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "10-digit mobile number",
                "inputmode": "numeric",
                "autocomplete": "tel",
            }
        ),
    )
    address = forms.CharField(
        max_length=500,
        label="Complete delivery address",
        widget=forms.Textarea(
            attrs={
                "class": TEXTAREA_CLASS,
                "rows": 3,
                "placeholder": "House / flat number, building, street, area, landmark",
                "autocomplete": "street-address",
            }
        ),
    )
    city = forms.CharField(
        max_length=80,
        label="City",
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASS, "placeholder": "City", "autocomplete": "address-level2"}
        ),
    )
    state = forms.CharField(
        max_length=80,
        label="State",
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASS, "placeholder": "State", "autocomplete": "address-level1"}
        ),
    )
    pin_code = forms.CharField(
        max_length=6,
        label="PIN code",
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "6-digit PIN code",
                "inputmode": "numeric",
                "autocomplete": "postal-code",
            }
        ),
    )
    payment_method = forms.ChoiceField(
        label="Payment method",
        choices=[
            ("COD", "Cash on Delivery"),
            ("ONLINE", "Online Payment (Razorpay)"),
        ],
        initial="COD",
        widget=forms.RadioSelect(attrs={"class": "payment-radio"}),
    )
    notes = forms.CharField(
        max_length=300,
        required=False,
        label="Delivery notes (optional)",
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASS, "placeholder": "e.g. Call before delivery"}
        ),
    )

    def clean_phone(self):
        phone = re.sub(r"[\s-]", "", self.cleaned_data["phone"])
        if not re.fullmatch(r"[6-9]\d{9}", phone):
            raise forms.ValidationError(
                "Enter a valid 10-digit Indian mobile number starting with 6-9."
            )
        return phone

    def clean_pin_code(self):
        pin = re.sub(r"\s", "", self.cleaned_data["pin_code"])
        if not re.fullmatch(r"\d{6}", pin):
            raise forms.ValidationError("Enter a valid 6-digit PIN code.")
        return pin

    def clean_full_name(self):
        name = self.cleaned_data["full_name"].strip()
        if len(name.split()) < 2:
            raise forms.ValidationError("Please enter your first and last name.")
        return name


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "At least 8 characters",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "Repeat your password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "First name", "autocomplete": "given-name"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Last name", "autocomplete": "family-name"}
            ),
            "email": forms.EmailInput(
                attrs={"class": INPUT_CLASS, "placeholder": "you@example.com", "autocomplete": "email"}
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Mobile number (optional)",
                    "autocomplete": "tel",
                }
            ),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists. Try signing in."
            )
        return email

    def clean_phone(self):
        phone = re.sub(r"[\s-]", "", self.cleaned_data.get("phone", ""))
        if phone and not re.fullmatch(r"[6-9]\d{9}", phone):
            raise forms.ValidationError(
                "Enter a valid 10-digit Indian mobile number starting with 6-9."
            )
        return phone

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "phone": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "10-digit mobile number"}
            ),
        }

    def clean_phone(self):
        phone = re.sub(r"[\s-]", "", self.cleaned_data.get("phone", ""))
        if phone and not re.fullmatch(r"[6-9]\d{9}", phone):
            raise forms.ValidationError(
                "Enter a valid 10-digit Indian mobile number starting with 6-9."
            )
        return phone


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "brand",
            "price",
            "mrp",
            "stock",
            "description",
            "image",
            "tax_percent",
            "is_featured",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Product name"}),
            "category": forms.Select(attrs={"class": SELECT_CLASS}),
            "brand": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Brand (optional)"}),
            "price": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "min": "0", "step": "0.01"}
            ),
            "mrp": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "min": "0", "step": "0.01"}
            ),
            "stock": forms.NumberInput(attrs={"class": INPUT_CLASS, "min": "0"}),
            "description": forms.Textarea(
                attrs={
                    "class": TEXTAREA_CLASS,
                    "rows": 5,
                    "placeholder": "Describe the product, materials, features...",
                }
            ),
            "image": forms.ClearableFileInput(attrs={"class": "form-file"}),
            "tax_percent": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "min": "0", "step": "0.01"}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get("price")
        mrp = cleaned.get("mrp")
        if price is not None and price <= 0:
            self.add_error("price", "Price must be greater than zero.")
        if price is not None and mrp is not None and mrp < price:
            self.add_error("mrp", "MRP cannot be lower than the selling price.")
        return cleaned


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "icon", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Category name"}
            ),
            "icon": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Emoji, e.g. 🎧"}
            ),
            "description": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Short description"}
            ),
        }

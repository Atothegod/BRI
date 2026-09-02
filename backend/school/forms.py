import json
from functools import lru_cache
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction
from django.utils import timezone

from .models import Person, Student


CONTROL_CLASS = "form-control"
THAI_ADDRESS_DATA_PATH = Path(__file__).resolve().parent / "static" / "school" / "data" / "thai_addresses.min.json"
ADDRESS_PREFIXES = ("จังหวัด", "จ.", "อำเภอ", "อ.", "เขต", "ตำบล", "ต.", "แขวง")

REGION_OPTIONS = (
    {
        "value": "northern",
        "label": "เหนือ",
        "icon": "school/images/regions/northern.png",
    },
    {
        "value": "central",
        "label": "กลาง",
        "icon": "school/images/regions/central.png",
    },
    {
        "value": "eastern",
        "label": "ตะวันออก",
        "initial": "ตอ.",
    },
    {
        "value": "western",
        "label": "ตะวันตก",
        "initial": "ตก.",
    },
    {
        "value": "northeastern",
        "label": "อีสาน",
        "icon": "school/images/regions/northeastern.png",
    },
    {
        "value": "southern",
        "label": "ใต้",
        "icon": "school/images/regions/southern.png",
    },
)
REGION_CHOICES = tuple((item["value"], item["label"]) for item in REGION_OPTIONS)
GENDER_CHOICES = (
    ("male", "ชาย"),
    ("female", "หญิง"),
)


def normalize_address_text(value):
    return "".join(str(value or "").strip().lower().split())


def strip_address_prefix(value):
    normalized_value = normalize_address_text(value)
    for prefix in ADDRESS_PREFIXES:
        normalized_prefix = normalize_address_text(prefix)
        if normalized_value.startswith(normalized_prefix):
            return normalized_value[len(normalized_prefix) :]
    return normalized_value


def address_values_match(first_value, second_value):
    return (
        normalize_address_text(first_value) == normalize_address_text(second_value)
        or strip_address_prefix(first_value) == strip_address_prefix(second_value)
    )


@lru_cache(maxsize=1)
def load_thai_address_data():
    try:
        with THAI_ADDRESS_DATA_PATH.open(encoding="utf-8") as address_file:
            return json.load(address_file)
    except OSError:
        return []


class PersonForm(forms.Form):
    line_user_id = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.HiddenInput(),
    )
    line_display_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.HiddenInput(),
    )
    line_picture_url = forms.URLField(
        max_length=500,
        required=False,
        widget=forms.HiddenInput(),
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "given-name",
                "placeholder": "ชื่อจริง",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "family-name",
                "placeholder": "นามสกุล",
            }
        ),
    )
    nickname = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "nickname",
                "placeholder": "ชื่อเล่น",
            }
        ),
    )
    gender = forms.ChoiceField(choices=GENDER_CHOICES)
    date_of_birth = forms.DateField(
        input_formats=["%d/%m/%Y", "%d-%m-%Y", "%d%m%Y", "%Y-%m-%d"],
        widget=forms.DateInput(
            format="%d/%m/%Y",
            attrs={
                "class": CONTROL_CLASS,
                "type": "text",
                "inputmode": "numeric",
                "autocomplete": "bday",
                "maxlength": "10",
                "placeholder": "วว/ดด/ปปปป",
                "data-date-mask": "",
            },
        ),
    )
    phone = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "type": "tel",
                "inputmode": "tel",
                "autocomplete": "tel",
                "placeholder": "08X-XXX-XXXX",
            }
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "email",
                "placeholder": "name@example.com",
            }
        ),
    )
    occupation = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "organization-title",
                "placeholder": "อาชีพปัจจุบัน",
            }
        ),
    )
    region = forms.ChoiceField(choices=REGION_CHOICES)
    province = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "off",
                "aria-autocomplete": "list",
                "aria-controls": "province-suggestions",
                "aria-expanded": "false",
                "placeholder": "พิมพ์ชื่อจังหวัด",
                "role": "combobox",
                "spellcheck": "false",
                "data-address-province": "",
            }
        ),
    )
    district = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "off",
                "aria-autocomplete": "list",
                "aria-controls": "district-suggestions",
                "aria-expanded": "false",
                "placeholder": "พิมพ์ชื่ออำเภอ / เขต",
                "role": "combobox",
                "spellcheck": "false",
                "data-address-district": "",
            }
        ),
    )
    sub_district = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "off",
                "aria-autocomplete": "list",
                "aria-controls": "subdistrict-suggestions",
                "aria-expanded": "false",
                "placeholder": "พิมพ์ชื่อตำบล / แขวง",
                "role": "combobox",
                "spellcheck": "false",
                "data-address-subdistrict": "",
            }
        ),
    )
    address = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": CONTROL_CLASS,
                "rows": 3,
                "autocomplete": "street-address",
                "placeholder": "บ้านเลขที่ ถนน และรายละเอียดที่อยู่",
            }
        ),
    )
    is_pastor = forms.TypedChoiceField(
        choices=(("true", "ใช่"), ("false", "ไม่ใช่")),
        coerce=lambda value: value == "true",
    )
    has_studied_bri = forms.TypedChoiceField(
        choices=(("true", "เคย"), ("false", "ยังไม่เคย")),
        coerce=lambda value: value == "true",
    )
    facebook_link = forms.URLField(
        max_length=500,
        widget=forms.URLInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "url",
                "placeholder": "https://facebook.com/...",
            }
        ),
    )
    church = forms.CharField(
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "placeholder": "ชื่อคริสตจักร",
            }
        ),
    )
    serving_position = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "placeholder": "เช่น ศิษยาภิบาล ผู้ช่วยศิษยาภิบาล",
            }
        ),
    )
    mentor_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "placeholder": "ชื่อ - นามสกุลพี่เลี้ยง",
            }
        ),
    )
    believer_years = forms.IntegerField(
        min_value=0,
        max_value=120,
        widget=forms.NumberInput(
            attrs={
                "class": CONTROL_CLASS,
                "inputmode": "numeric",
                "placeholder": "จำนวนปี",
            }
        ),
    )
    goal = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": CONTROL_CLASS,
                "rows": 5,
                "placeholder": "เล่าเป้าหมายที่อยากได้รับจากการเรียนครั้งนี้",
            }
        ),
    )
    vision_calling = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": CONTROL_CLASS,
                "rows": 5,
                "placeholder": "เล่านิมิตและการทรงเรียกที่อยู่ในใจของคุณ",
            }
        ),
    )
    privacy_consent = forms.BooleanField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_of_birth"].widget.attrs["max"] = timezone.localdate().isoformat()
        for field_name in ("province", "district", "sub_district"):
            selected = self.data.get(self.add_prefix(field_name)) or self.initial.get(field_name)
            if selected:
                self.fields[field_name].widget.attrs["data-selected-value"] = selected

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data["date_of_birth"]
        if date_of_birth.year > 2400:
            date_of_birth = date_of_birth.replace(year=date_of_birth.year - 543)
        if date_of_birth > timezone.localdate():
            raise forms.ValidationError("วันเกิดต้องไม่เป็นวันที่ในอนาคต")
        return date_of_birth

    def clean(self):
        cleaned_data = super().clean()
        province_name = cleaned_data.get("province")
        district_name = cleaned_data.get("district")
        subdistrict_name = cleaned_data.get("sub_district")
        if not province_name or not district_name or not subdistrict_name:
            return cleaned_data

        address_data = load_thai_address_data()
        if not address_data:
            return cleaned_data

        province = next(
            (
                item
                for item in address_data
                if address_values_match(item["province"], province_name)
            ),
            None,
        )
        if not province:
            self.add_error("province", "กรุณาเลือกจังหวัดจากรายการ")
            return cleaned_data
        cleaned_data["province"] = province["province"]

        district = next(
            (
                item
                for item in province["districts"]
                if address_values_match(item["district"], district_name)
            ),
            None,
        )
        if not district:
            self.add_error("district", "กรุณาเลือกอำเภอ / เขตจากรายการ")
            return cleaned_data
        cleaned_data["district"] = district["district"]

        subdistrict = next(
            (
                item
                for item in district["subdistricts"]
                if address_values_match(item, subdistrict_name)
            ),
            "",
        )
        if not subdistrict:
            self.add_error("sub_district", "กรุณาเลือกตำบล / แขวงจากรายการ")
            return cleaned_data
        cleaned_data["sub_district"] = subdistrict
        return cleaned_data

    @transaction.atomic
    def save(self, line_profile=None):
        data = self.cleaned_data
        line_profile = line_profile or {}
        line_user_id = line_profile.get("line_user_id") or data["line_user_id"]
        line_display_name = line_profile.get("line_display_name") or data["line_display_name"]
        line_picture_url = line_profile.get("line_picture_url") or data["line_picture_url"]
        person_values = {
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "nickname": data["nickname"],
            "gender": data["gender"],
            "date_of_birth": data["date_of_birth"],
            "occupation": data["occupation"],
            "phone": data["phone"],
            "email": data["email"],
            "line_id": "",
            "line_display_name": line_display_name,
            "line_picture_url": line_picture_url,
            "line_connected_at": timezone.now() if line_user_id else None,
            "extra_data": {
                "region": data["region"],
                "province": data["province"],
                "district": data["district"],
                "sub_district": data["sub_district"],
                "address": data["address"],
                "is_pastor": data["is_pastor"],
                "has_studied_bri": data["has_studied_bri"],
                "facebook_link": data["facebook_link"],
                "church": data["church"],
                "serving_position": data["serving_position"],
                "mentor_name": data["mentor_name"],
                "believer_years": data["believer_years"],
                "goal": data["goal"],
                "vision_calling": data["vision_calling"],
                "privacy_consent": data["privacy_consent"],
            },
        }
        if line_user_id:
            person, _ = Person.objects.update_or_create(
                line_user_id=line_user_id,
                defaults=person_values,
            )
            return person

        return Person.objects.create(**person_values)


class TeacherLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="ชื่อผู้ใช้หรืออีเมล",
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "username",
                "placeholder": "teacher@example.com",
            }
        ),
    )


class TeacherSignupForm(UserCreationForm):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "email",
                "placeholder": "teacher@example.com",
            }
        )
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("username", "password1", "password2"):
            self.fields[field_name].widget.attrs.setdefault("class", CONTROL_CLASS)
        self.fields["username"].widget.attrs.setdefault("autocomplete", "username")
        self.fields["username"].widget.attrs.setdefault("placeholder", "teacher")
        self.fields["password1"].widget.attrs.setdefault("autocomplete", "new-password")
        self.fields["password2"].widget.attrs.setdefault("autocomplete", "new-password")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("มีบัญชีที่ใช้อีเมลนี้แล้ว")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = user.Role.TEACHER
        user.email = self.cleaned_data["email"]

        if commit:
            user.save()
        return user


class PaymentSlipUploadForm(forms.Form):
    line_user_id = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.HiddenInput(),
    )
    payment_slip = forms.ImageField(
        widget=forms.ClearableFileInput(
            attrs={
                "class": "file-input",
                "accept": "image/jpeg,image/png,image/webp",
                "data-upload-input": "",
            }
        )
    )

    def __init__(self, *args, line_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.line_profile = line_profile or {}

    def clean(self):
        cleaned_data = super().clean()
        line_user_id = self.line_profile.get("line_user_id", "").strip()

        if not line_user_id:
            raise forms.ValidationError("กรุณาเปิดหน้านี้ผ่าน LINE เพื่อให้ระบบรู้บัญชีของคุณ")

        try:
            self.student = Student.objects.select_related("person").get(
                person__line_user_id=line_user_id
            )
        except Student.DoesNotExist as exc:
            raise forms.ValidationError("ไม่พบข้อมูลนักศึกษาสำหรับ LINE account นี้") from exc

        cleaned_data["line_user_id"] = line_user_id
        return cleaned_data

    def save(self):
        self.student.payment_slip = self.cleaned_data["payment_slip"]
        self.student.is_paid = False
        self.student.save(update_fields=["payment_slip", "is_paid"])
        return self.student

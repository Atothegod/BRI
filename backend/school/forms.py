import json
from functools import lru_cache
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction
from django.utils import timezone

from .models import HomeworkSubmission, Person, Student
from .teacher_groups import ensure_default_teacher_group


CONTROL_CLASS = "form-control"
THAI_ADDRESS_DATA_PATH = Path(__file__).resolve().parent / "static" / "school" / "data" / "thai_addresses.min.json"
COUNTRY_DATA_PATH = Path(__file__).resolve().parent / "static" / "school" / "data" / "countries.min.json"
ADDRESS_PREFIXES = ("จังหวัด", "จ.", "อำเภอ", "อ.", "เขต", "ตำบล", "ต.", "แขวง")
LANGUAGE_CHOICES = (
    ("th", "ไทย"),
    ("en", "English"),
)

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
        "icon": "school/images/regions/eastern.png",
    },
    {
        "value": "western",
        "label": "ตะวันตก",
        "icon": "school/images/regions/western.png",
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


@lru_cache(maxsize=1)
def load_country_data():
    try:
        with COUNTRY_DATA_PATH.open(encoding="utf-8") as country_file:
            return json.load(country_file)
    except OSError:
        return []


def get_country_by_code(country_code):
    normalized_code = str(country_code or "").strip().upper()
    if not normalized_code:
        return None
    return next(
        (
            country
            for country in load_country_data()
            if country.get("code") == normalized_code
        ),
        None,
    )


def get_country_by_name(country_name):
    normalized_name = normalize_address_text(country_name)
    if not normalized_name:
        return None
    return next(
        (
            country
            for country in load_country_data()
            if normalize_address_text(country.get("name_en")) == normalized_name
            or normalize_address_text(country.get("name_th")) == normalized_name
        ),
        None,
    )


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
    preferred_language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        required=False,
        initial="th",
        widget=forms.HiddenInput(attrs={"data-language-input": ""}),
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "given-name",
                "placeholder": "ชื่อจริง",
                "data-i18n-placeholder": "first_name_placeholder",
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
                "data-i18n-placeholder": "last_name_placeholder",
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
                "data-i18n-placeholder": "nickname_placeholder",
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
                "data-i18n-placeholder": "birthdate_placeholder",
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
                "data-i18n-placeholder": "phone_placeholder",
            }
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "email",
                "placeholder": "name@example.com",
                "data-i18n-placeholder": "email_placeholder",
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
                "data-i18n-placeholder": "occupation_placeholder",
            }
        ),
    )
    country_code = forms.CharField(
        max_length=2,
        required=False,
        initial="TH",
        widget=forms.HiddenInput(attrs={"data-country-code": ""}),
    )
    country_name_en = forms.CharField(
        max_length=120,
        required=False,
        initial="Thailand",
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "country-name",
                "aria-autocomplete": "list",
                "aria-controls": "country-suggestions",
                "aria-expanded": "false",
                "placeholder": "Thailand",
                "required": "required",
                "role": "combobox",
                "spellcheck": "false",
                "data-country-search": "",
                "data-i18n-placeholder": "country_placeholder",
            }
        ),
    )
    country_name_th = forms.CharField(
        max_length=120,
        required=False,
        initial="ไทย",
        widget=forms.HiddenInput(attrs={"data-country-name-th": ""}),
    )
    region = forms.ChoiceField(choices=REGION_CHOICES, required=False)
    province = forms.CharField(
        max_length=100,
        required=False,
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
                "data-i18n-placeholder": "province_placeholder",
            }
        ),
    )
    district = forms.CharField(
        max_length=100,
        required=False,
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
                "data-i18n-placeholder": "district_placeholder",
            }
        ),
    )
    sub_district = forms.CharField(
        max_length=100,
        required=False,
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
                "data-i18n-placeholder": "subdistrict_placeholder",
            }
        ),
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": CONTROL_CLASS,
                "rows": 3,
                "autocomplete": "street-address",
                "placeholder": "บ้านเลขที่ ถนน และรายละเอียดที่อยู่",
                "data-i18n-placeholder": "thai_address_placeholder",
            }
        ),
    )
    address_line = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "address-line1",
                "placeholder": "Street address, building, room",
                "data-foreign-address-line": "",
                "data-i18n-placeholder": "foreign_address_placeholder",
            }
        ),
    )
    city = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "address-level2",
                "placeholder": "City",
                "data-foreign-city": "",
                "data-i18n-placeholder": "city_placeholder",
            }
        ),
    )
    state_province = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "address-level1",
                "placeholder": "State / Province",
                "data-foreign-state": "",
                "data-i18n-placeholder": "state_placeholder",
            }
        ),
    )
    postal_code = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "postal-code",
                "placeholder": "Postal code",
                "data-foreign-postal": "",
                "data-i18n-placeholder": "postal_placeholder",
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
                "data-i18n-placeholder": "facebook_placeholder",
            }
        ),
    )
    church = forms.CharField(
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "placeholder": "ชื่อคริสตจักร",
                "data-i18n-placeholder": "church_placeholder",
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
                "data-i18n-placeholder": "serving_position_placeholder",
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
                "data-i18n-placeholder": "mentor_name_placeholder",
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
                "data-i18n-placeholder": "believer_years_placeholder",
            }
        ),
    )
    goal = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": CONTROL_CLASS,
                "rows": 5,
                "placeholder": "เล่าเป้าหมายที่อยากได้รับจากการเรียนครั้งนี้",
                "data-i18n-placeholder": "goal_placeholder",
            }
        ),
    )
    vision_calling = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": CONTROL_CLASS,
                "rows": 5,
                "placeholder": "เล่านิมิตและการทรงเรียกที่อยู่ในใจของคุณ",
                "data-i18n-placeholder": "vision_placeholder",
            }
        ),
    )
    privacy_consent = forms.BooleanField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("preferred_language", "th")
            self.initial.setdefault("country_code", "TH")
            self.initial.setdefault("country_name_en", "ไทย")
            self.initial.setdefault("country_name_th", "ไทย")
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
        preferred_language = cleaned_data.get("preferred_language") or "th"
        if preferred_language not in dict(LANGUAGE_CHOICES):
            preferred_language = "th"
        cleaned_data["preferred_language"] = preferred_language

        country_code = cleaned_data.get("country_code")
        country_name_en = cleaned_data.get("country_name_en")
        country_name_th = cleaned_data.get("country_name_th")
        if not country_code and not country_name_en and not country_name_th:
            country_code = "TH"
        country = (
            get_country_by_code(country_code)
            or get_country_by_name(country_name_en)
            or get_country_by_name(country_name_th)
        )
        if not country:
            self.add_error("country_name_en", "กรุณาเลือกประเทศจากรายการ")
            return cleaned_data

        cleaned_data["country_code"] = country["code"]
        cleaned_data["country_name_en"] = country["name_en"]
        cleaned_data["country_name_th"] = country["name_th"]

        if country["code"] != "TH":
            if not cleaned_data.get("address_line"):
                self.add_error("address_line", "กรุณากรอกที่อยู่")
            if not cleaned_data.get("city"):
                self.add_error("city", "กรุณากรอกเมือง")
            return cleaned_data

        region = cleaned_data.get("region")
        province_name = cleaned_data.get("province")
        district_name = cleaned_data.get("district")
        subdistrict_name = cleaned_data.get("sub_district")
        address = cleaned_data.get("address")
        if not region:
            self.add_error("region", "กรุณาเลือกภูมิภาค")
        if not province_name:
            self.add_error("province", "กรุณากรอกจังหวัด")
        if not district_name:
            self.add_error("district", "กรุณากรอกอำเภอ / เขต")
        if not subdistrict_name:
            self.add_error("sub_district", "กรุณากรอกตำบล / แขวง")
        if not address:
            self.add_error("address", "กรุณากรอกที่อยู่ปัจจุบัน")
        if not region or not province_name or not district_name or not subdistrict_name or not address:
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
                "preferred_language": data["preferred_language"],
                "country_code": data["country_code"],
                "country_name_en": data["country_name_en"],
                "country_name_th": data["country_name_th"],
                "address_language": data["preferred_language"],
                "region": data["region"],
                "province": data["province"],
                "district": data["district"],
                "sub_district": data["sub_district"],
                "address": data["address"],
                "address_th": {
                    "region": data["region"],
                    "province": data["province"],
                    "district": data["district"],
                    "sub_district": data["sub_district"],
                    "address": data["address"],
                }
                if data["country_code"] == "TH"
                else {},
                "address_en": {
                    "address_line": data["address_line"],
                    "city": data["city"],
                    "state_province": data["state_province"],
                    "postal_code": data["postal_code"],
                    "country_code": data["country_code"],
                    "country_name_en": data["country_name_en"],
                }
                if data["country_code"] != "TH"
                else {},
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
    nickname = forms.CharField(
        max_length=100,
        label="ชื่อเล่น",
        widget=forms.TextInput(
            attrs={
                "class": CONTROL_CLASS,
                "autocomplete": "nickname",
                "placeholder": "เช่น อ.เอก",
            }
        ),
    )
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
        fields = ("username", "nickname", "email")

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
        user.nickname = self.cleaned_data["nickname"].strip()
        user.email = self.cleaned_data["email"]

        if commit:
            user.save()
            ensure_default_teacher_group(user)
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
            self.student = Student.objects.select_related("person", "group").get(
                person__line_user_id=line_user_id,
                person__status=Person.Status.PASSED,
            )
        except Student.DoesNotExist as exc:
            raise forms.ValidationError(
                "บัญชี LINE นี้ยังไม่ได้รับสถานะนักศึกษา จึงยังไม่สามารถแจ้งชำระเงินได้"
            ) from exc

        if self.student.is_paid:
            raise forms.ValidationError(
                "ระบบยืนยันการชำระเงินของคุณเรียบร้อยแล้ว ไม่ต้องส่งสลิปซ้ำ"
            )

        cleaned_data["line_user_id"] = line_user_id
        return cleaned_data

    def save(self):
        self.student.payment_slip = self.cleaned_data["payment_slip"]
        self.student.is_paid = False
        self.student.save(update_fields=["payment_slip", "is_paid"])
        return self.student


class HomeworkUploadForm(forms.Form):
    homework_file = forms.FileField(
        label="ไฟล์การบ้าน",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "student-file-input",
                "accept": ".pdf,.doc,.docx,.ppt,.pptx,.jpg,.jpeg,.png,.webp,.zip",
                "data-student-upload-input": "",
            }
        ),
    )
    student_note = forms.CharField(
        label="ข้อความถึงผู้สอน",
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "class": "student-textarea",
                "rows": 3,
                "placeholder": "เขียนหมายเหตุเพิ่มเติมได้ เช่น ลิงก์งาน หรือสิ่งที่อยากให้อาจารย์ดูเป็นพิเศษ",
            }
        ),
    )

    def save(self, student, assignment):
        submitted_at = timezone.now()
        status = (
            HomeworkSubmission.Status.LATE
            if assignment.due_date < timezone.localdate()
            else HomeworkSubmission.Status.SUBMITTED
        )
        submission, _ = HomeworkSubmission.objects.update_or_create(
            homework_assignment=assignment,
            student=student,
            defaults={
                "submission_file": self.cleaned_data["homework_file"],
                "student_note": self.cleaned_data["student_note"],
                "status": status,
                "submitted_at": submitted_at,
            },
        )
        return submission

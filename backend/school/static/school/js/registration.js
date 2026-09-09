(() => {
    "use strict";

    const app = document.querySelector("[data-registration-app]");
    const form = document.querySelector("[data-registration-form]");

    if (!app || !form) {
        return;
    }

    const panels = Array.from(form.querySelectorAll("[data-form-step]"));
    const stepButtons = Array.from(app.querySelectorAll("[data-step-jump]"));
    const nextButton = form.querySelector("[data-step-next]");
    const backButton = form.querySelector("[data-step-back]");
    const submitButton = form.querySelector("[data-submit-button]");
    const currentStepTexts = Array.from(app.querySelectorAll("[data-current-step]"));
    const progressLabels = Array.from(app.querySelectorAll("[data-progress-label]"));
    const progressBars = Array.from(app.querySelectorAll("[data-progress-bar]"));
    const progressTracks = Array.from(app.querySelectorAll("[data-progress-track]"));
    const sidebar = app.querySelector("[data-app-sidebar]");
    const menuBackdrop = app.querySelector("[data-menu-backdrop]");
    const menuOpenButton = app.querySelector("[data-menu-open]");
    const uploadInput = form.querySelector("[data-upload-input]");
    const fileLabel = form.querySelector("[data-file-label]");
    const provinceInput = form.querySelector("[data-address-province]");
    const districtInput = form.querySelector("[data-address-district]");
    const subdistrictInput = form.querySelector("[data-address-subdistrict]");
    const provinceSuggestions = form.querySelector("[data-address-province-suggestions]");
    const districtSuggestions = form.querySelector("[data-address-district-suggestions]");
    const subdistrictSuggestions = form.querySelector("[data-address-subdistrict-suggestions]");
    const dateInputs = Array.from(form.querySelectorAll("[data-date-mask]"));
    const languageInput = form.querySelector("[data-language-input]");
    const languageButtons = Array.from(app.querySelectorAll("[data-language-option]"));
    const countryInput = form.querySelector("[data-country-search]");
    const countryCodeInput = form.querySelector("[data-country-code]");
    const countryNameThInput = form.querySelector("[data-country-name-th]");
    const countrySuggestions = form.querySelector("[data-country-suggestions]");
    const thailandAddress = form.querySelector("[data-thailand-address]");
    const foreignAddress = form.querySelector("[data-foreign-address]");
    const foreignAddressLine = form.querySelector("[data-foreign-address-line]");
    const foreignCity = form.querySelector("[data-foreign-city]");
    const foreignState = form.querySelector("[data-foreign-state]");
    const foreignPostal = form.querySelector("[data-foreign-postal]");
    const addressDataUrl = form.dataset.addressDataUrl;
    const countryDataUrl = form.dataset.countryDataUrl;
    const thailandInputs = [
        ...Array.from(form.querySelectorAll("[data-thailand-required]")),
        provinceInput,
        districtInput,
        subdistrictInput,
        form.querySelector("[name='address']"),
    ].filter(Boolean);
    const foreignInputs = [
        foreignAddressLine,
        foreignCity,
        foreignState,
        foreignPostal,
    ].filter(Boolean);
    const totalSteps = panels.length;
    const hasSteps = totalSteps > 0;
    const translations = {
        th: {
            address_copy: "ข้อมูลพื้นที่ช่วยให้เราจัดกลุ่มการเรียนได้เหมาะสม",
            address_title: "ที่อยู่ปัจจุบัน",
            assurance_copy: "เมื่อกดส่ง ระบบจะบันทึกข้อมูลและตั้งสถานะเป็นดำเนินการ",
            assurance_title: "ตรวจสอบก่อนส่งได้เสมอ",
            back: "ย้อนกลับ",
            believer_years: "เป็นผู้เชื่อมาแล้ว",
            believer_years_placeholder: "จำนวนปี",
            birthdate_placeholder: "วว/ดด/ปปปป",
            brand_registration_aria: "BRI School of Fivefold หน้าสมัครเรียน",
            calling_copy: "ส่วนนี้ไม่มีคำตอบถูกผิด เขียนจากเรื่องราวจริงของคุณได้เลย",
            calling_title: "เป้าหมายและการทรงเรียก",
            church: "คริสตจักรที่ผูกพันตัว",
            church_copy: "เล่าบริบทการเติบโตฝ่ายวิญญาณของคุณ",
            church_placeholder: "ชื่อคริสตจักร",
            church_title: "ความเชื่อและการรับใช้",
            city: "เมือง",
            city_placeholder: "เมือง",
            close_menu: "ปิดเมนู",
            country: "ประเทศ",
            country_invalid: "กรุณาเลือกประเทศจากรายการ",
            country_placeholder: "ค้นหาประเทศ",
            date_hint: "พิมพ์ตัวเลข 8 หลัก เช่น 15012533",
            date_of_birth: "วันเดือนปีเกิด",
            district: "อำเภอ / เขต",
            district_invalid: "กรุณาเลือกอำเภอ / เขตจากรายการ",
            district_placeholder: "พิมพ์ชื่ออำเภอ / เขต",
            email: "อีเมล",
            email_placeholder: "name@example.com",
            facebook_hint: "ใส่ลิงก์โปรไฟล์เต็มเพื่อให้ทีมงานตรวจสอบได้",
            facebook_link: "Facebook ส่วนตัว",
            facebook_placeholder: "https://facebook.com/...",
            first_name: "ชื่อจริง",
            first_name_placeholder: "ชื่อจริง",
            foreign_address: "ที่อยู่",
            foreign_address_placeholder: "บ้านเลขที่ ถนน อาคาร ห้อง",
            gender: "เพศ",
            gender_female: "หญิง",
            gender_male: "ชาย",
            goal: "เป้าหมายในการสมัครเข้าเรียนครั้งนี้คืออะไร",
            goal_placeholder: "เล่าเป้าหมายที่อยากได้รับจากการเรียนครั้งนี้",
            has_studied_bri: "ท่านเคยเรียน BRI มาก่อนหรือไม่",
            hero_eyebrow: "ระบบรับสมัครนักเรียน",
            hero_title: "ใบสมัครเรียน",
            is_pastor: "ท่านเป็นศิษยาภิบาลหรือไม่",
            language_switch_aria: "เลือกภาษา",
            last_name: "นามสกุล",
            last_name_placeholder: "นามสกุล",
            mentor_name: "ชื่อพี่เลี้ยง",
            mentor_name_placeholder: "ชื่อ - นามสกุลพี่เลี้ยง",
            mobile_progress_title: "ลำดับการสมัคร",
            next: "ถัดไป",
            nickname: "ชื่อเล่น",
            nickname_placeholder: "ชื่อเล่น",
            no: "ไม่ใช่",
            occupation: "อาชีพ",
            occupation_placeholder: "อาชีพปัจจุบัน",
            online_application: "ใบสมัครออนไลน์",
            open_menu: "เปิดเมนูขั้นตอน",
            optional: "ไม่บังคับ",
            pastor_no_copy: "ไม่ได้ทำหน้าที่ศิษยาภิบาล",
            pastor_yes_copy: "เป็นศิษยาภิบาลอยู่ในปัจจุบัน",
            personal_copy: "กรอกข้อมูลที่ใช้ติดต่อคุณ",
            personal_title: "ข้อมูลส่วนตัว",
            phone: "เบอร์โทรศัพท์",
            phone_placeholder: "08X-XXX-XXXX",
            postal_code: "รหัสไปรษณีย์",
            postal_placeholder: "รหัสไปรษณีย์",
            privacy_consent: "ข้าพเจ้ารับรองว่าข้อมูลถูกต้อง และยินยอมให้ BRI ใช้ข้อมูลนี้เพื่อดำเนินการรับสมัครและติดต่อเกี่ยวกับการเรียน",
            progress_aria: "ความคืบหน้าการสมัคร",
            province: "จังหวัด",
            province_invalid: "กรุณาเลือกจังหวัดจากรายการ",
            province_placeholder: "พิมพ์ชื่อจังหวัด",
            region: "ภูมิภาค",
            region_central: "กลาง",
            region_eastern: "ตะวันออก",
            region_northeastern: "อีสาน",
            region_northern: "เหนือ",
            region_southern: "ใต้",
            region_western: "ตะวันตก",
            security_copy: "ใช้เพื่อการสมัครเรียนเท่านั้น",
            security_title: "ข้อมูลของคุณปลอดภัย",
            server_error_copy: "แก้ไขช่องที่แสดงข้อความสีแดง แล้วลองส่งใบสมัครอีกครั้ง",
            server_error_title: "ยังมีข้อมูลที่ต้องตรวจสอบ",
            serving_position: "ตำแหน่งงานรับใช้",
            serving_position_placeholder: "เช่น ศิษยาภิบาล ผู้ช่วยศิษยาภิบาล",
            sidebar_aria: "ขั้นตอนการสมัคร",
            sidebar_copy: "กรอกข้อมูลตามขั้นตอน ใช้เวลาประมาณ 8 นาที",
            sidebar_title: "เริ่มต้นการเดินทางของคุณ",
            state_placeholder: "รัฐ / จังหวัด",
            state_province: "รัฐ / จังหวัด",
            step_address: "ที่อยู่",
            step_calling: "เป้าหมาย",
            step_church: "คริสตจักร",
            step_personal: "ข้อมูลส่วนตัว",
            step_prefix: "ขั้นตอน",
            steps_aria: "ขั้นตอนการสมัคร",
            studied_no: "ยังไม่เคย",
            studied_no_copy: "นี่จะเป็นครั้งแรกของฉัน",
            studied_yes: "เคย",
            studied_yes_copy: "เคยเข้าร่วมหลักสูตรของ BRI",
            submit: "ส่งใบสมัคร",
            submitting: "กำลังส่ง...",
            sub_district: "ตำบล / แขวง",
            subdistrict_invalid: "กรุณาเลือกตำบล / แขวงจากรายการ",
            subdistrict_placeholder: "พิมพ์ชื่อตำบล / แขวง",
            thai_address: "ที่อยู่ปัจจุบัน",
            thai_address_hint: "ใช้ชื่อจังหวัด อำเภอ และตำบลภาษาไทยตามรายการทางการ",
            thai_address_placeholder: "บ้านเลขที่ ถนน และรายละเอียดที่อยู่",
            type_mismatch: "รูปแบบข้อมูลไม่ถูกต้อง",
            required: "กรุณากรอกข้อมูลส่วนนี้",
            vision_calling: "นิมิตและการทรงเรียกของคุณคืออะไร",
            vision_placeholder: "เล่านิมิตและการทรงเรียกที่อยู่ในใจของคุณ",
            years_suffix: "ปี",
            yes: "ใช่",
        },
        en: {
            address_copy: "Your location helps us place you in the right learning group.",
            address_title: "Current address",
            assurance_copy: "After submission, your application will be saved with an in-progress status.",
            assurance_title: "You can review before submitting",
            back: "Back",
            believer_years: "Years as a believer",
            believer_years_placeholder: "Number of years",
            birthdate_placeholder: "DD/MM/YYYY",
            brand_registration_aria: "BRI School of Fivefold registration page",
            calling_copy: "There is no right or wrong answer. Write from your real story.",
            calling_title: "Goals and calling",
            church: "Home church",
            church_copy: "Share the faith and ministry context you are growing in.",
            church_placeholder: "Church name",
            church_title: "Faith and ministry",
            city: "City",
            city_placeholder: "City",
            close_menu: "Close menu",
            country: "Country",
            country_invalid: "Please select a country from the list",
            country_placeholder: "Search country",
            date_hint: "Type 8 digits, for example 15011990",
            date_of_birth: "Date of birth",
            district: "District",
            district_invalid: "Please select a district from the list",
            district_placeholder: "Type district name",
            email: "Email",
            email_placeholder: "name@example.com",
            facebook_hint: "Use your full profile link so the team can review it.",
            facebook_link: "Personal Facebook",
            facebook_placeholder: "https://facebook.com/...",
            first_name: "First name",
            first_name_placeholder: "First name",
            foreign_address: "Address",
            foreign_address_placeholder: "Street address, building, room",
            gender: "Gender",
            gender_female: "Female",
            gender_male: "Male",
            goal: "What is your goal for applying this time?",
            goal_placeholder: "Share what you hope to receive from this program",
            has_studied_bri: "Have you studied with BRI before?",
            hero_eyebrow: "Student registration system",
            hero_title: "Application form",
            is_pastor: "Are you currently a pastor?",
            language_switch_aria: "Choose language",
            last_name: "Last name",
            last_name_placeholder: "Last name",
            mentor_name: "Mentor name",
            mentor_name_placeholder: "Mentor full name",
            mobile_progress_title: "Application steps",
            next: "Next",
            nickname: "Nickname",
            nickname_placeholder: "Nickname",
            no: "No",
            occupation: "Occupation",
            occupation_placeholder: "Current occupation",
            online_application: "Online application",
            open_menu: "Open steps menu",
            optional: "Optional",
            pastor_no_copy: "I am not serving as a pastor",
            pastor_yes_copy: "I am currently serving as a pastor",
            personal_copy: "Enter the details we can use to contact you.",
            personal_title: "Personal information",
            phone: "Phone number",
            phone_placeholder: "Phone number",
            postal_code: "Postal code",
            postal_placeholder: "Postal code",
            privacy_consent: "I confirm that this information is accurate and allow BRI to use it for registration and study-related contact.",
            progress_aria: "Application progress",
            province: "Province",
            province_invalid: "Please select a province from the list",
            province_placeholder: "Type province name",
            region: "Region",
            region_central: "Central",
            region_eastern: "Eastern",
            region_northeastern: "Northeastern",
            region_northern: "Northern",
            region_southern: "Southern",
            region_western: "Western",
            security_copy: "Used only for this application",
            security_title: "Your information is secure",
            server_error_copy: "Fix the fields marked in red, then submit again.",
            server_error_title: "Some information needs review",
            serving_position: "Ministry role",
            serving_position_placeholder: "Pastor, assistant pastor, ministry team",
            sidebar_aria: "Application steps",
            sidebar_copy: "Complete the steps in about 8 minutes.",
            sidebar_title: "Begin your journey",
            state_placeholder: "State / Province",
            state_province: "State / Province",
            step_address: "Address",
            step_calling: "Calling",
            step_church: "Church",
            step_personal: "Personal",
            step_prefix: "Step",
            steps_aria: "Application steps",
            studied_no: "Not yet",
            studied_no_copy: "This will be my first time",
            studied_yes: "Yes",
            studied_yes_copy: "I have joined a BRI course before",
            submit: "Submit application",
            submitting: "Submitting...",
            sub_district: "Subdistrict",
            subdistrict_invalid: "Please select a subdistrict from the list",
            subdistrict_placeholder: "Type subdistrict name",
            thai_address: "Current address",
            thai_address_hint: "For Thailand, please use official Thai province, district, and subdistrict names.",
            thai_address_placeholder: "House number, street, and address details",
            type_mismatch: "This format is not valid",
            required: "Please complete this field",
            vision_calling: "What is your vision and calling?",
            vision_placeholder: "Share the vision and calling you carry",
            years_suffix: "years",
            yes: "Yes",
        },
    };
    const storedLanguage = (() => {
        try {
            return window.localStorage.getItem("bri.registrationLanguage");
        } catch (error) {
            return "";
        }
    })();
    const isSupportedLanguage = (language) => Object.prototype.hasOwnProperty.call(translations, language);
    const formLanguage = languageInput && isSupportedLanguage(languageInput.value)
        ? languageInput.value
        : "";
    let currentStep = 1;
    let maxVisitedStep = 1;
    let currentLanguage = isSupportedLanguage(storedLanguage)
        ? storedLanguage
        : formLanguage
            ? formLanguage
            : "th";
    let countryData = [];

    const firstErrorPanel = panels.find((panel) => panel.querySelector(".has-error, .errorlist"));
    if (firstErrorPanel) {
        currentStep = Number(firstErrorPanel.dataset.formStep);
        maxVisitedStep = currentStep;
    }

    app.classList.add("is-enhanced", "reveal-enabled");

    const translate = (key) => translations[currentLanguage][key] || translations.th[key] || key;

    const getSelectedCountryCode = () => {
        if (countryCodeInput) {
            return countryCodeInput.value.trim().toUpperCase();
        }
        return (form.dataset.countryInitial || "TH").trim().toUpperCase();
    };

    const getSelectedCountry = () => {
        const code = getSelectedCountryCode();
        return countryData.find((country) => country.code === code) || null;
    };

    const syncCountryDisplay = () => {
        const country = getSelectedCountry();
        if (!country || !countryInput) {
            return;
        }
        countryInput.value = currentLanguage === "th" ? country.name_th : country.name_en;
        if (countryNameThInput) countryNameThInput.value = country.name_th;
    };

    const syncAddressMode = () => {
        const countryCode = getSelectedCountryCode();
        const hasCountry = Boolean(countryCode);
        const isThailand = countryCode === "TH";
        if (thailandAddress) thailandAddress.hidden = !hasCountry || !isThailand;
        if (foreignAddress) foreignAddress.hidden = !hasCountry || isThailand;

        thailandInputs.forEach((input) => {
            input.disabled = !hasCountry || !isThailand;
            input.required = hasCountry && isThailand;
            if (!hasCountry || !isThailand) {
                input.setCustomValidity("");
                clearClientError(input);
            }
        });
        foreignInputs.forEach((input) => {
            const required = input === foreignAddressLine || input === foreignCity;
            input.disabled = !hasCountry || isThailand;
            input.required = hasCountry && !isThailand && required;
            if (!hasCountry || isThailand) {
                input.setCustomValidity("");
                clearClientError(input);
            }
        });
    };

    const setLanguage = (language) => {
        currentLanguage = isSupportedLanguage(language) ? language : "th";
        if (languageInput) languageInput.value = currentLanguage;
        app.setAttribute("lang", currentLanguage);
        document.documentElement.lang = currentLanguage;

        try {
            window.localStorage.setItem("bri.registrationLanguage", currentLanguage);
        } catch (error) {
            // Ignore storage restrictions inside embedded LINE browsers.
        }

        languageButtons.forEach((button) => {
            const isSelected = button.dataset.languageOption === currentLanguage;
            button.classList.toggle("is-selected", isSelected);
            button.setAttribute("aria-pressed", String(isSelected));
        });

        app.querySelectorAll("[data-i18n]").forEach((item) => {
            item.textContent = translate(item.dataset.i18n);
        });
        app.querySelectorAll("[data-i18n-prefix]").forEach((item) => {
            item.textContent = translate(item.dataset.i18nPrefix);
        });
        app.querySelectorAll("[data-i18n-placeholder]").forEach((item) => {
            item.placeholder = translate(item.dataset.i18nPlaceholder);
        });
        app.querySelectorAll("[data-i18n-aria-label]").forEach((item) => {
            item.setAttribute("aria-label", translate(item.dataset.i18nAriaLabel));
        });

        panels.forEach((panel) => {
            panel.dataset.stepLabel = currentLanguage === "th"
                ? panel.dataset.stepLabelTh
                : panel.dataset.stepLabelEn;
        });

        syncCountryDisplay();
        syncAddressMode();
        if (hasSteps) {
            showStep(currentStep, { scroll: false });
        }
    };

    const setClientError = (group, message) => {
        if (!group) {
            return;
        }

        group.classList.add("has-error");
        let error = group.querySelector("[data-client-error]");
        if (!error) {
            error = document.createElement("p");
            error.className = "errorlist";
            error.dataset.clientError = "";
            error.setAttribute("role", "alert");
            group.appendChild(error);
        }
        error.textContent = message;
    };

    const clearClientError = (field) => {
        field.classList.remove("is-invalid");
        const group = field.closest(".field-group, .consent-control");
        if (!group) {
            return;
        }

        const error = group.querySelector("[data-client-error]");
        if (error) {
            error.remove();
        }
        if (!group.querySelector(".errorlist")) {
            group.classList.remove("has-error");
        }
    };

    const scrollToPanel = (panel) => {
        const mobileBar = app.querySelector(".mobile-app-bar");
        const mobileBarHeight = mobileBar && getComputedStyle(mobileBar).display !== "none"
            ? mobileBar.getBoundingClientRect().height
            : 0;
        const offset = mobileBarHeight + 16;
        const top = panel.getBoundingClientRect().top + window.scrollY - offset;
        window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    };

    const showStep = (step, options = {}) => {
        if (!hasSteps) {
            return;
        }
        const nextStep = Math.min(Math.max(step, 1), totalSteps);
        currentStep = nextStep;
        maxVisitedStep = Math.max(maxVisitedStep, nextStep);

        panels.forEach((panel) => {
            const isActive = Number(panel.dataset.formStep) === nextStep;
            panel.classList.toggle("is-active", isActive);
            panel.setAttribute("aria-hidden", String(!isActive));
            if (isActive) {
                panel.classList.add("is-visible");
            }
        });

        stepButtons.forEach((button) => {
            const buttonStep = Number(button.dataset.stepJump);
            const isActive = buttonStep === nextStep;
            button.classList.toggle("is-active", isActive);
            button.classList.toggle("is-complete", buttonStep < nextStep);
            button.setAttribute("aria-current", isActive ? "step" : "false");
            button.setAttribute("aria-disabled", String(buttonStep > maxVisitedStep));
        });

        const activePanel = panels[nextStep - 1];
        const label = activePanel ? activePanel.dataset.stepLabel : "";
        const percent = totalSteps > 1
            ? ((nextStep - 1) / (totalSteps - 1)) * 100
            : 100;

        currentStepTexts.forEach((item) => {
            item.textContent = String(nextStep);
        });
        progressLabels.forEach((item) => {
            item.textContent = label;
        });
        progressBars.forEach((item) => {
            item.style.width = `${percent}%`;
        });
        progressTracks.forEach((item) => {
            item.setAttribute("aria-valuenow", String(nextStep));
        });
        if (backButton) backButton.hidden = nextStep === 1;
        if (nextButton) nextButton.hidden = nextStep === totalSteps;
        if (submitButton) submitButton.hidden = nextStep !== totalSteps;

        if (options.scroll !== false && activePanel) {
            scrollToPanel(activePanel);
        }
        if (options.focus && activePanel) {
            const heading = activePanel.querySelector("h3");
            if (heading) {
                heading.setAttribute("tabindex", "-1");
                heading.focus({ preventScroll: true });
            }
        }
    };

    const validatePanel = (panel, interactive = true) => {
        if (!panel) {
            return true;
        }

        const fields = Array.from(
            panel.querySelectorAll("input:not([type='hidden']):not([type='file']), textarea, select")
        ).filter((field) => !field.disabled);
        let firstInvalid = null;

        fields.forEach((field) => {
            if (!field.checkValidity()) {
                field.classList.add("is-invalid");
                const group = field.closest(".field-group, .consent-control");
                const message = field.validity.customError
                    ? field.validationMessage
                    : field.validity.typeMismatch
                        ? translate("type_mismatch")
                        : translate("required");
                setClientError(group, message);
                firstInvalid = firstInvalid || field;
            }
        });

        if (!firstInvalid) {
            return true;
        }

        if (interactive) {
            const target = firstInvalid.closest(".field-group, .consent-control") || firstInvalid;
            target.scrollIntoView({ behavior: "smooth", block: "center" });
            firstInvalid.focus({ preventScroll: true });
        }
        return false;
    };

    const syncBodyLock = () => {
        const menuIsOpen = sidebar && sidebar.classList.contains("is-open");
        document.body.classList.toggle("is-overlay-open", Boolean(menuIsOpen));
    };

    const setMenu = (isOpen) => {
        if (!sidebar || !menuBackdrop || !menuOpenButton) {
            return;
        }
        sidebar.classList.toggle("is-open", isOpen);
        menuBackdrop.hidden = !isOpen;
        menuOpenButton.setAttribute("aria-expanded", String(isOpen));
        syncBodyLock();
        if (isOpen) {
            const closeButton = sidebar.querySelector("[data-menu-close]");
            if (closeButton) closeButton.focus({ preventScroll: true });
        } else {
            menuOpenButton.focus({ preventScroll: true });
        }
    };

    const formatDateDigits = (value) => {
        const digits = value.replace(/\D/g, "").slice(0, 8);
        if (digits.length <= 2) {
            return digits;
        }
        if (digits.length <= 4) {
            return `${digits.slice(0, 2)}/${digits.slice(2)}`;
        }
        return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
    };

    dateInputs.forEach((input) => {
        const syncDateInput = () => {
            input.value = formatDateDigits(input.value);
            clearClientError(input);
        };
        input.addEventListener("input", syncDateInput);
        input.addEventListener("paste", () => window.setTimeout(syncDateInput, 0));
    });

    const normalizeSearchText = (value, locale = "en") => (
        String(value || "").trim().toLocaleLowerCase(locale).replace(/\s+/g, "")
    );

    const setupCountryAutocomplete = (countries) => {
        if (!countryInput || !countryCodeInput || !countrySuggestions || !Array.isArray(countries)) {
            return;
        }

        countryData = countries;
        let matches = [];
        let activeIndex = -1;

        const displayName = (country) => currentLanguage === "th" ? country.name_th : country.name_en;
        const findCountry = (value) => {
            const normalizedValue = normalizeSearchText(value, currentLanguage);
            if (!normalizedValue) {
                return null;
            }
            return countryData.find((country) => (
                normalizeSearchText(country.code) === normalizedValue
                || normalizeSearchText(country.name_en) === normalizedValue
                || normalizeSearchText(country.name_th, "th-TH") === normalizedValue
            )) || null;
        };

        const hide = () => {
            countrySuggestions.hidden = true;
            countryInput.setAttribute("aria-expanded", "false");
            countryInput.removeAttribute("aria-activedescendant");
            activeIndex = -1;
        };

        const setActive = (index) => {
            if (!matches.length) {
                return;
            }
            activeIndex = (index + matches.length) % matches.length;
            Array.from(countrySuggestions.children).forEach((item, itemIndex) => {
                const isActive = itemIndex === activeIndex;
                item.classList.toggle("is-active", isActive);
                item.setAttribute("aria-selected", String(isActive));
            });
            countryInput.setAttribute("aria-activedescendant", `country-suggestion-${activeIndex}`);
        };

        const choose = (country) => {
            if (!country) {
                syncAddressMode();
                return;
            }
            countryCodeInput.value = country.code;
            countryInput.value = displayName(country);
            if (countryNameThInput) countryNameThInput.value = country.name_th;
            countryInput.setCustomValidity("");
            hide();
            syncAddressMode();
            clearClientError(countryInput);
        };

        const markPendingCountry = () => {
            if (countryCodeInput) countryCodeInput.value = "";
            if (countryNameThInput) countryNameThInput.value = "";
        };

        const validate = () => {
            const country = findCountry(countryInput.value);
            if (!countryInput.value.trim()) {
                markPendingCountry();
                countryInput.setCustomValidity("");
                return false;
            }
            if (country) {
                choose(country);
                return true;
            }
            markPendingCountry();
            countryInput.setCustomValidity(translate("country_invalid"));
            return false;
        };

        const render = () => {
            const query = normalizeSearchText(countryInput.value, currentLanguage);
            if (!query) {
                matches = [];
                countrySuggestions.replaceChildren();
                hide();
                return;
            }

            matches = countryData
                .filter((country) => (
                    normalizeSearchText(country.code).includes(query)
                    || normalizeSearchText(country.name_en).includes(query)
                    || normalizeSearchText(country.name_th, "th-TH").includes(query)
                ))
                .sort((first, second) => displayName(first).localeCompare(displayName(second), currentLanguage))
                .slice(0, 8);

            countrySuggestions.replaceChildren(
                ...matches.map((country, index) => {
                    const button = document.createElement("button");
                    button.className = "address-suggestion";
                    button.id = `country-suggestion-${index}`;
                    button.type = "button";
                    button.setAttribute("role", "option");
                    button.textContent = currentLanguage === "th"
                        ? `${country.name_th} · ${country.name_en}`
                        : `${country.name_en} · ${country.name_th}`;
                    button.addEventListener("mousedown", (event) => event.preventDefault());
                    button.addEventListener("click", () => choose(country));
                    return button;
                })
            );

            countrySuggestions.hidden = matches.length === 0;
            countryInput.setAttribute("aria-expanded", String(matches.length > 0));
            activeIndex = -1;
        };

        countryInput.addEventListener("input", () => {
            const exactCountry = findCountry(countryInput.value);
            if (exactCountry) {
                countryCodeInput.value = exactCountry.code;
                if (countryNameThInput) countryNameThInput.value = exactCountry.name_th;
                countryInput.setCustomValidity("");
                syncAddressMode();
            } else {
                markPendingCountry();
                countryInput.setCustomValidity(countryInput.value.trim() ? translate("country_invalid") : "");
            }
            render();
            clearClientError(countryInput);
        });
        countryInput.addEventListener("focus", render);
        countryInput.addEventListener("blur", () => {
            validate();
            window.setTimeout(hide, 120);
        });
        countryInput.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                hide();
                return;
            }
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                if (countrySuggestions.hidden) {
                    render();
                }
                if (matches.length) {
                    event.preventDefault();
                    setActive(activeIndex + (event.key === "ArrowDown" ? 1 : -1));
                }
                return;
            }
            if (event.key === "Enter" && activeIndex >= 0 && matches[activeIndex]) {
                event.preventDefault();
                choose(matches[activeIndex]);
            }
        });

        choose(
            getSelectedCountry()
            || findCountry(countryInput.value)
            || countryData.find((country) => country.code === "TH")
            || countryData[0]
        );
    };

    const setupAddressAutocomplete = (addressData) => {
        if (!provinceInput || !districtInput || !subdistrictInput || !Array.isArray(addressData)) {
            return;
        }

        const provinceMap = new Map(addressData.map((province) => [province.province, province]));
        const provinceNames = addressData.map((province) => province.province);
        const districtPlaceholder = () => translate("district_placeholder");
        const subdistrictPlaceholder = () => translate("subdistrict_placeholder");
        const initialProvince = provinceInput.dataset.selectedValue || provinceInput.value;
        const initialDistrict = districtInput.dataset.selectedValue || districtInput.value;
        const initialSubdistrict = subdistrictInput.dataset.selectedValue || subdistrictInput.value;

        const normalizeAddressText = (value) => value.trim().toLocaleLowerCase("th-TH").replace(/\s+/g, "");
        const addressPrefixes = ["จังหวัด", "จ.", "อำเภอ", "อ.", "เขต", "ตำบล", "ต.", "แขวง"];

        const stripAddressPrefix = (value) => {
            const normalizedValue = normalizeAddressText(value);
            const matchedPrefix = addressPrefixes.find((prefix) => (
                normalizedValue.startsWith(normalizeAddressText(prefix))
            ));
            return matchedPrefix
                ? normalizedValue.slice(normalizeAddressText(matchedPrefix).length)
                : normalizedValue;
        };

        const findExactValue = (values, value) => {
            const normalizedValue = normalizeAddressText(value);
            const prefixlessValue = stripAddressPrefix(value);
            return values.find((item) => (
                normalizeAddressText(item) === normalizedValue
                || stripAddressPrefix(item) === prefixlessValue
            )) || "";
        };

        const getSelectedProvince = () => provinceMap.get(provinceInput.value.trim()) || null;

        const getDistricts = () => {
            const province = getSelectedProvince();
            return province ? province.districts : [];
        };

        const getDistrictNames = () => getDistricts().map((item) => item.district);

        const getSelectedDistrict = () => {
            const exactDistrict = findExactValue(getDistrictNames(), districtInput.value);
            return exactDistrict
                ? getDistricts().find((item) => item.district === exactDistrict) || null
                : null;
        };

        const getSubdistrictNames = () => {
            const district = getSelectedDistrict();
            return district ? district.subdistricts : [];
        };

        let districtAutocomplete = null;
        let subdistrictAutocomplete = null;

        const disableInput = (input, placeholder) => {
            input.value = "";
            input.disabled = true;
            input.placeholder = placeholder;
            input.setCustomValidity("");
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
            clearClientError(input);
        };

        const enableInput = (input, placeholder) => {
            input.disabled = false;
            input.placeholder = placeholder;
            input.setAttribute("aria-expanded", "false");
        };

        const disableSubdistrict = () => {
            if (subdistrictAutocomplete) {
                subdistrictAutocomplete.hide();
            }
            disableInput(subdistrictInput, subdistrictPlaceholder());
        };

        const disableDistrict = () => {
            if (districtAutocomplete) {
                districtAutocomplete.hide();
            }
            disableInput(districtInput, districtPlaceholder());
            disableSubdistrict();
        };

        const handleProvinceSelected = (name, options = {}) => {
            provinceInput.value = name;
            provinceInput.setCustomValidity("");
            enableInput(districtInput, districtPlaceholder());
            if (options.resetChildren !== false) {
                districtInput.value = "";
                disableSubdistrict();
            }
            if (options.focusNext) {
                districtInput.focus({ preventScroll: true });
            }
        };

        const handleDistrictSelected = (name, options = {}) => {
            districtInput.value = name;
            districtInput.setCustomValidity("");
            enableInput(subdistrictInput, subdistrictPlaceholder());
            if (options.resetChildren !== false) {
                subdistrictInput.value = "";
            }
            if (options.focusNext) {
                subdistrictInput.focus({ preventScroll: true });
            }
        };

        const handleSubdistrictSelected = (name) => {
            subdistrictInput.value = name;
            subdistrictInput.setCustomValidity("");
        };

        const createAddressAutocomplete = ({
            input,
            suggestions,
            idPrefix,
            getValues,
            invalidMessageKey,
            onSelect,
            onInvalid,
        }) => {
            let matches = [];
            let activeIndex = -1;

            const hide = () => {
                if (!suggestions) {
                    return;
                }
                suggestions.hidden = true;
                input.setAttribute("aria-expanded", "false");
                input.removeAttribute("aria-activedescendant");
                activeIndex = -1;
            };

            const setActive = (index) => {
                if (!suggestions || !matches.length) {
                    return;
                }
                activeIndex = (index + matches.length) % matches.length;
                Array.from(suggestions.children).forEach((item, itemIndex) => {
                    const isActive = itemIndex === activeIndex;
                    item.classList.toggle("is-active", isActive);
                    item.setAttribute("aria-selected", String(isActive));
                });
                input.setAttribute("aria-activedescendant", `${idPrefix}-suggestion-${activeIndex}`);
            };

            const choose = (name, options = {}) => {
                input.value = name;
                input.setCustomValidity("");
                hide();
                onSelect(name, options);
                clearClientError(input);
            };

            const validateValue = () => {
                if (input.disabled) {
                    input.setCustomValidity("");
                    return "";
                }
                if (!input.value.trim()) {
                    input.setCustomValidity("");
                    return "";
                }
                const exactValue = findExactValue(getValues(), input.value);
                if (exactValue) {
                    input.value = exactValue;
                    input.setCustomValidity("");
                    return exactValue;
                }
                input.setCustomValidity(translate(invalidMessageKey));
                return "";
            };

            const render = () => {
                if (!suggestions || input.disabled) {
                    hide();
                    return;
                }

                const query = normalizeAddressText(input.value);
                if (!query) {
                    matches = [];
                    suggestions.replaceChildren();
                    hide();
                    return;
                }

                const prefixlessQuery = stripAddressPrefix(input.value);
                matches = getValues()
                    .filter((name) => (
                        normalizeAddressText(name).includes(query)
                        || stripAddressPrefix(name).includes(prefixlessQuery)
                    ))
                    .sort((first, second) => {
                        const firstStarts = normalizeAddressText(first).startsWith(query);
                        const secondStarts = normalizeAddressText(second).startsWith(query);
                        if (firstStarts !== secondStarts) {
                            return firstStarts ? -1 : 1;
                        }
                        const firstPrefixlessStarts = stripAddressPrefix(first).startsWith(prefixlessQuery);
                        const secondPrefixlessStarts = stripAddressPrefix(second).startsWith(prefixlessQuery);
                        if (firstPrefixlessStarts !== secondPrefixlessStarts) {
                            return firstPrefixlessStarts ? -1 : 1;
                        }
                        return first.localeCompare(second, "th");
                    })
                    .slice(0, 8);

                suggestions.replaceChildren(
                    ...matches.map((name, index) => {
                        const button = document.createElement("button");
                        button.className = "address-suggestion";
                        button.id = `${idPrefix}-suggestion-${index}`;
                        button.type = "button";
                        button.setAttribute("role", "option");
                        button.textContent = name;
                        button.addEventListener("mousedown", (event) => event.preventDefault());
                        button.addEventListener("click", () => choose(name, { focusNext: true }));
                        return button;
                    })
                );

                suggestions.hidden = matches.length === 0;
                input.setAttribute("aria-expanded", String(matches.length > 0));
                activeIndex = -1;
            };

            input.addEventListener("input", () => {
                const exactValue = validateValue();
                if (exactValue) {
                    choose(exactValue, { focusNext: false });
                    return;
                }
                if (input.value.trim()) {
                    onInvalid();
                    render();
                } else {
                    hide();
                    onInvalid();
                }
                clearClientError(input);
            });

            input.addEventListener("focus", render);
            input.addEventListener("blur", () => {
                validateValue();
                window.setTimeout(hide, 120);
            });
            input.addEventListener("keydown", (event) => {
                if (event.key === "Escape") {
                    hide();
                    return;
                }
                if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                    if (suggestions && suggestions.hidden) {
                        render();
                    }
                    if (matches.length) {
                        event.preventDefault();
                        setActive(activeIndex + (event.key === "ArrowDown" ? 1 : -1));
                    }
                    return;
                }
                if (event.key === "Enter" && activeIndex >= 0 && matches[activeIndex]) {
                    event.preventDefault();
                    choose(matches[activeIndex], { focusNext: true });
                }
            });

            return { hide, validate: validateValue };
        };

        const provinceAutocomplete = createAddressAutocomplete({
            input: provinceInput,
            suggestions: provinceSuggestions,
            idPrefix: "province",
            getValues: () => provinceNames,
            invalidMessageKey: "province_invalid",
            onSelect: handleProvinceSelected,
            onInvalid: disableDistrict,
        });

        districtAutocomplete = createAddressAutocomplete({
            input: districtInput,
            suggestions: districtSuggestions,
            idPrefix: "district",
            getValues: getDistrictNames,
            invalidMessageKey: "district_invalid",
            onSelect: handleDistrictSelected,
            onInvalid: disableSubdistrict,
        });

        subdistrictAutocomplete = createAddressAutocomplete({
            input: subdistrictInput,
            suggestions: subdistrictSuggestions,
            idPrefix: "subdistrict",
            getValues: getSubdistrictNames,
            invalidMessageKey: "subdistrict_invalid",
            onSelect: handleSubdistrictSelected,
            onInvalid: () => {},
        });

        disableDistrict();
        provinceInput.value = initialProvince;
        const exactProvince = provinceAutocomplete.validate();
        if (exactProvince) {
            handleProvinceSelected(exactProvince, { resetChildren: false });
            districtInput.value = initialDistrict;
            const exactDistrict = districtAutocomplete.validate();
            if (exactDistrict) {
                handleDistrictSelected(exactDistrict, { resetChildren: false });
                subdistrictInput.value = initialSubdistrict;
                subdistrictAutocomplete.validate();
            }
        }
        syncAddressMode();
    };

    setLanguage(currentLanguage);

    if (countryDataUrl && countryInput) {
        fetch(countryDataUrl, { credentials: "same-origin" })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Unable to load country data");
                }
                return response.json();
            })
            .then(setupCountryAutocomplete)
            .catch(() => syncAddressMode());
    } else {
        syncAddressMode();
    }

    if (addressDataUrl && provinceInput && districtInput && subdistrictInput) {
        fetch(addressDataUrl, { credentials: "same-origin" })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Unable to load Thai address data");
                }
                return response.json();
            })
            .then(setupAddressAutocomplete)
            .catch(() => {
                provinceInput.disabled = false;
                districtInput.disabled = false;
                subdistrictInput.disabled = false;
                syncAddressMode();
            });
    }

    if (hasSteps && nextButton) {
        nextButton.addEventListener("click", () => {
            const activePanel = panels[currentStep - 1];
            if (validatePanel(activePanel)) {
                showStep(currentStep + 1, { focus: true });
            }
        });
    }

    if (hasSteps && backButton) {
        backButton.addEventListener("click", () => showStep(currentStep - 1, { focus: true }));
    }

    stepButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const step = Number(button.dataset.stepJump);
            if (step <= maxVisitedStep) {
                showStep(step, { focus: true });
                if (sidebar && sidebar.classList.contains("is-open")) {
                    setMenu(false);
                }
            }
        });
    });

    languageButtons.forEach((button) => {
        button.addEventListener("click", () => setLanguage(button.dataset.languageOption));
    });

    form.addEventListener("input", (event) => clearClientError(event.target));
    form.addEventListener("change", (event) => clearClientError(event.target));

    form.addEventListener("submit", (event) => {
        for (const panel of panels) {
            if (!validatePanel(panel, false)) {
                event.preventDefault();
                const invalidStep = Number(panel.dataset.formStep);
                showStep(invalidStep, { focus: false });
                window.setTimeout(() => validatePanel(panel, true), 30);
                return;
            }
        }

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.setAttribute("aria-busy", "true");
            const label = submitButton.querySelector("span");
            if (label) label.textContent = translate("submitting");
        }
    });

    if (menuOpenButton) menuOpenButton.addEventListener("click", () => setMenu(true));
    if (menuBackdrop) menuBackdrop.addEventListener("click", () => setMenu(false));
    const menuCloseButton = app.querySelector("[data-menu-close]");
    if (menuCloseButton) menuCloseButton.addEventListener("click", () => setMenu(false));

    if (uploadInput && fileLabel) {
        uploadInput.addEventListener("change", () => {
            const file = uploadInput.files && uploadInput.files[0];
            fileLabel.textContent = file ? file.name : "เลือกรูปสลิป";
        });
    }

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") {
            return;
        }
        if (sidebar && sidebar.classList.contains("is-open")) {
            setMenu(false);
        }
    });

    const revealItems = Array.from(app.querySelectorAll("[data-reveal]"));
    if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        const observer = new IntersectionObserver(
            (entries, instance) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        instance.unobserve(entry.target);
                    }
                });
            },
            { rootMargin: "0px 0px -7% 0px", threshold: 0.08 }
        );
        revealItems.forEach((item) => observer.observe(item));
    } else {
        revealItems.forEach((item) => item.classList.add("is-visible"));
    }

    if (hasSteps) {
        showStep(currentStep, { scroll: false });
    }
})();

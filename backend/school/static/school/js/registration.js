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
    const addressDataUrl = form.dataset.addressDataUrl;
    const totalSteps = panels.length;
    const hasSteps = totalSteps > 0;
    let currentStep = 1;
    let maxVisitedStep = 1;

    const firstErrorPanel = panels.find((panel) => panel.querySelector(".has-error, .errorlist"));
    if (firstErrorPanel) {
        currentStep = Number(firstErrorPanel.dataset.formStep);
        maxVisitedStep = currentStep;
    }

    app.classList.add("is-enhanced", "reveal-enabled");

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
                        ? "รูปแบบข้อมูลไม่ถูกต้อง"
                        : "กรุณากรอกข้อมูลส่วนนี้";
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

    const setupAddressAutocomplete = (addressData) => {
        if (!provinceInput || !districtInput || !subdistrictInput || !Array.isArray(addressData)) {
            return;
        }

        const provinceMap = new Map(addressData.map((province) => [province.province, province]));
        const provinceNames = addressData.map((province) => province.province);
        const districtPlaceholder = "พิมพ์ชื่ออำเภอ / เขต";
        const subdistrictPlaceholder = "พิมพ์ชื่อตำบล / แขวง";
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
            disableInput(subdistrictInput, "เลือกอำเภอ / เขตก่อน");
        };

        const disableDistrict = () => {
            if (districtAutocomplete) {
                districtAutocomplete.hide();
            }
            disableInput(districtInput, "เลือกจังหวัดก่อน");
            disableSubdistrict();
        };

        const handleProvinceSelected = (name, options = {}) => {
            provinceInput.value = name;
            provinceInput.setCustomValidity("");
            enableInput(districtInput, districtPlaceholder);
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
            enableInput(subdistrictInput, subdistrictPlaceholder);
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
            invalidMessage,
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
                input.setCustomValidity(invalidMessage);
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
            invalidMessage: "กรุณาเลือกจังหวัดจากรายการ",
            onSelect: handleProvinceSelected,
            onInvalid: disableDistrict,
        });

        districtAutocomplete = createAddressAutocomplete({
            input: districtInput,
            suggestions: districtSuggestions,
            idPrefix: "district",
            getValues: getDistrictNames,
            invalidMessage: "กรุณาเลือกอำเภอ / เขตจากรายการ",
            onSelect: handleDistrictSelected,
            onInvalid: disableSubdistrict,
        });

        subdistrictAutocomplete = createAddressAutocomplete({
            input: subdistrictInput,
            suggestions: subdistrictSuggestions,
            idPrefix: "subdistrict",
            getValues: getSubdistrictNames,
            invalidMessage: "กรุณาเลือกตำบล / แขวงจากรายการ",
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
    };

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
            if (label) label.textContent = "กำลังส่ง...";
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

(() => {
    "use strict";

    const config = document.querySelector("[data-liff-config]");
    if (!config || !window.liff) {
        return;
    }
    const initialLiffState = new URL(window.location.href).searchParams.get("liff.state");

    const getCookie = (name) => {
        const cookies = document.cookie ? document.cookie.split(";") : [];
        for (const cookie of cookies) {
            const [key, ...valueParts] = cookie.trim().split("=");
            if (key === name) {
                return decodeURIComponent(valueParts.join("="));
            }
        }
        return "";
    };

    const updateLineFields = (profile) => {
        const userId = profile.line_user_id || profile.userId || "";
        const displayName = profile.line_display_name || profile.displayName || "";
        const pictureUrl = profile.line_picture_url || profile.pictureUrl || "";
        const userIdField = document.querySelector("input[name='line_user_id']");
        const displayNameField = document.querySelector("input[name='line_display_name']");
        const pictureUrlField = document.querySelector("input[name='line_picture_url']");

        if (userIdField && userId) userIdField.value = userId;
        if (displayNameField && displayName) displayNameField.value = displayName;
        if (pictureUrlField && pictureUrl) pictureUrlField.value = pictureUrl;
    };

    const redirectToLiffState = () => {
        if (!initialLiffState) {
            return false;
        }

        const state = initialLiffState.trim();
        if (!state || state === "/") {
            return false;
        }

        const relativeState = state.startsWith("/") ? state : `/${state}`;
        const targetUrl = new URL(relativeState, window.location.origin);
        if (targetUrl.origin !== window.location.origin) {
            return false;
        }

        const targetPath = `${targetUrl.pathname}${targetUrl.search}${targetUrl.hash}`;
        const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        if (targetPath && targetPath !== currentPath) {
            window.location.replace(targetPath);
            return true;
        }
        return false;
    };

    const syncLineProfile = async () => {
        const liffId = config.dataset.liffId;
        if (!liffId) {
            return;
        }

        await liff.init({
            liffId,
            withLoginOnExternalBrowser: true,
        });

        if (redirectToLiffState()) {
            return;
        }

        if (!liff.isLoggedIn()) {
            liff.login({ redirectUri: window.location.href });
            return;
        }

        const profile = await liff.getProfile();
        updateLineFields(profile);

        const response = await fetch(config.dataset.profileSyncUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({
                id_token: liff.getIDToken ? liff.getIDToken() : "",
                profile,
                context: liff.getContext ? liff.getContext() : null,
            }),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.message || "Unable to sync LINE profile");
        }

        updateLineFields(data.profile || {});

        if (config.dataset.reloadOnSync === "true" && config.dataset.lineKnown !== "true") {
            window.location.reload();
        }
    };

    const bindCloseButtons = () => {
        document.querySelectorAll("[data-liff-close]").forEach((button) => {
            button.addEventListener("click", (event) => {
                if (window.liff && liff.isInClient()) {
                    event.preventDefault();
                    liff.closeWindow();
                    return;
                }

                const fallbackUrl = button.getAttribute("href") || button.dataset.fallbackUrl;
                if (fallbackUrl) {
                    window.location.href = fallbackUrl;
                }
            });
        });
    };

    bindCloseButtons();
    syncLineProfile().catch((error) => {
        console.warn(error);
    });
})();

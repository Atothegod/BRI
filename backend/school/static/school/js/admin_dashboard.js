(() => {
    "use strict";

    const explorer = document.querySelector("[data-geo-explorer]");
    const dataNode = document.getElementById("geo-map-data");
    if (!explorer || !dataNode) return;

    const data = JSON.parse(dataNode.textContent);
    const stage = explorer.querySelector("[data-geo-stage]");
    const list = explorer.querySelector("[data-geo-ranking-list]");
    const title = explorer.querySelector("[data-geo-ranking-title]");
    const kicker = explorer.querySelector("[data-geo-ranking-kicker]");
    const tooltip = explorer.querySelector("[data-geo-tooltip]");
    const maxCount = (items) => Math.max(1, ...items.map((item) => item.count));
    const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
    })[character]);

    const regionShapes = {
        northern: "M183 25 C145 43 128 80 143 116 L178 143 217 117 226 66 207 31Z",
        northeastern: "M219 93 L261 77 306 98 321 139 293 169 233 157 199 132Z",
        central: "M173 136 L225 128 258 164 239 208 207 233 174 203 155 163Z",
        eastern: "M239 185 L286 173 308 201 280 231 244 225 218 207Z",
        western: "M142 121 L174 139 174 204 198 237 176 263 145 223 126 173Z",
        southern: "M193 229 L221 227 224 278 242 318 230 385 205 413 190 371 207 322 186 279Z",
    };
    const provincePoints = {
        "กรุงเทพมหานคร": [218, 215], "สมุทรปราการ": [226, 224], "นนทบุรี": [212, 207],
        "ปทุมธานี": [216, 196], "นครปฐม": [195, 211], "สมุทรสาคร": [202, 224],
        "เชียงใหม่": [172, 67], "เชียงราย": [196, 42], "ลำปาง": [201, 88], "พิษณุโลก": [210, 133],
        "นครสวรรค์": [194, 158], "พระนครศรีอยุธยา": [211, 184], "กาญจนบุรี": [159, 190],
        "ชลบุรี": [252, 224], "ระยอง": [270, 232], "จันทบุรี": [286, 246], "ปราจีนบุรี": [251, 195],
        "นครราชสีมา": [260, 168], "ขอนแก่น": [267, 130], "อุดรธานี": [270, 96], "อุบลราชธานี": [307, 151],
        "สุราษฎร์ธานี": [212, 302], "นครศรีธรรมราช": [223, 336], "สงขลา": [218, 383], "ภูเก็ต": [190, 327],
    };
    const countryPoints = {
        TH: [710, 270], LA: [704, 245], US: [170, 190], AU: [800, 385], NO: [495, 95],
        GB: [452, 150], FR: [465, 175], DE: [490, 158], CN: [690, 190], JP: [805, 190],
        KR: [775, 185], SG: [715, 315], MY: [705, 305], MM: [675, 250], KH: [720, 270],
        VN: [735, 250], IN: [625, 240], CA: [160, 115], NZ: [890, 410], PH: [775, 275],
    };

    const showTooltip = (event, label, count) => {
        tooltip.innerHTML = `<strong>${escapeHtml(label)}</strong><span>${count.toLocaleString("th-TH")} คน</span>`;
        tooltip.hidden = false;
        const bounds = explorer.getBoundingClientRect();
        const targetBounds = event.currentTarget.getBoundingClientRect();
        const clientX = event.clientX || targetBounds.left + targetBounds.width / 2;
        const clientY = event.clientY || targetBounds.top + targetBounds.height / 2;
        tooltip.style.left = `${clientX - bounds.left + 12}px`;
        tooltip.style.top = `${clientY - bounds.top + 12}px`;
    };
    const hideTooltip = () => { tooltip.hidden = true; };
    const bindMapItems = () => {
        stage.querySelectorAll("[data-map-label]").forEach((item) => {
            item.addEventListener("pointermove", (event) => showTooltip(
                event, item.dataset.mapLabel, Number(item.dataset.mapCount || 0),
            ));
            item.addEventListener("pointerleave", hideTooltip);
            item.addEventListener("focus", (event) => showTooltip(event, item.dataset.mapLabel, Number(item.dataset.mapCount || 0)));
            item.addEventListener("blur", hideTooltip);
        });
    };
    const renderRanking = (items) => {
        const maximum = maxCount(items);
        list.innerHTML = items.slice(0, 10).map((item, index) => `
            <div class="geo-rank-row">
                <span class="geo-rank-number">${String(index + 1).padStart(2, "0")}</span>
                <div><div><span>${escapeHtml(item.label)}</span><strong>${item.count.toLocaleString("th-TH")}</strong></div>
                <i style="--geo-value:${(item.count / maximum) * 100}%"></i></div>
            </div>`).join("") || '<p class="geo-empty">ยังไม่มีข้อมูล</p>';
    };
    const thailandBase = (fills = {}) => Object.entries(regionShapes).map(([key, path]) => (
        `<path class="thai-region" d="${path}" fill="${fills[key] || "#dbe7dc"}" data-region="${key}"/>`
    )).join("");

    const renderRegion = () => {
        const items = data.regions || [];
        const maximum = maxCount(items);
        const palette = ["#e8efe7", "#cbdcc9", "#a8c2aa", "#7fa084", "#55765d", "#264b38"];
        const fills = Object.fromEntries(items.map((item) => [item.value, palette[Math.min(5, Math.ceil(item.count / maximum * 5))]]));
        stage.innerHTML = `<svg class="thai-map" viewBox="90 10 250 420" role="img" aria-label="แผนที่ผู้สมัครแยกตามภูมิภาค">${thailandBase(fills)}${items.map((item) => {
            const path = regionShapes[item.value];
            return path ? `<path class="geo-hit" tabindex="0" d="${path}" data-map-label="${escapeHtml(item.label)}" data-map-count="${item.count}"/>` : "";
        }).join("")}</svg><div class="geo-map-caption">สีเข้มหมายถึงมีผู้สมัครมากกว่า · แตะพื้นที่เพื่อดูจำนวน</div>`;
        title.textContent = "ผู้สมัครแยกตามภูมิภาค"; kicker.textContent = "ประเทศไทย";
        renderRanking(items); bindMapItems();
    };
    const renderProvince = () => {
        const items = data.provinces || [];
        const maximum = maxCount(items);
        const markers = items.map((item, index) => {
            const point = provincePoints[item.label];
            if (!point) return "";
            const radius = 5 + Math.sqrt(item.count / maximum) * 13;
            return `<g class="province-marker" tabindex="0" data-map-label="${escapeHtml(item.label)}" data-map-count="${item.count}"><circle cx="${point[0]}" cy="${point[1]}" r="${radius}"/><text x="${point[0]}" y="${point[1] + 3}">${index + 1}</text></g>`;
        }).join("");
        stage.innerHTML = `<svg class="thai-map" viewBox="90 10 250 420" role="img" aria-label="แผนที่จังหวัดของผู้สมัคร">${thailandBase()}${markers}</svg><div class="geo-map-caption">ขนาดวงกลมแสดงจำนวนผู้สมัคร · หมายเลขตรงกับอันดับด้านขวา</div>`;
        title.textContent = "จังหวัดที่พบมาก"; kicker.textContent = `${items.length.toLocaleString("th-TH")} จังหวัดที่มีข้อมูล`;
        renderRanking(items); bindMapItems();
    };
    const renderCountry = () => {
        const items = data.countries || [];
        const maximum = maxCount(items);
        const markers = items.map((item) => {
            const point = countryPoints[item.code];
            if (!point) return "";
            const radius = 5 + Math.sqrt(item.count / maximum) * 15;
            return `<g class="country-marker" tabindex="0" data-map-label="${escapeHtml(item.label)}" data-map-count="${item.count}"><circle cx="${point[0]}" cy="${point[1]}" r="${radius}"/></g>`;
        }).join("");
        stage.innerHTML = `<svg class="world-map" viewBox="0 0 1000 500" role="img" aria-label="แผนที่ประเทศของผู้สมัคร"><g class="world-land"><path d="M55 105L170 55 280 90 300 155 240 190 205 275 145 255 115 180 55 160Z"/><path d="M250 280L310 300 335 390 300 475 270 400Z"/><path d="M420 105L535 75 620 115 600 180 535 188 520 260 470 245 445 180Z"/><path d="M535 205L615 205 650 320 595 420 535 345 505 265Z"/><path d="M610 100L825 75 935 140 900 250 820 285 745 245 670 280 625 205Z"/><path d="M765 340L875 330 930 405 855 450 770 415Z"/></g>${markers}</svg><div class="geo-map-caption">ขนาดวงกลมแสดงจำนวนผู้สมัครจากแต่ละประเทศ</div>`;
        title.textContent = "ประเทศของผู้สมัคร"; kicker.textContent = `${items.length.toLocaleString("th-TH")} ประเทศ`;
        renderRanking(items); bindMapItems();
    };
    const renderers = { region: renderRegion, province: renderProvince, country: renderCountry };
    explorer.querySelectorAll("[data-geo-mode]").forEach((button) => button.addEventListener("click", () => {
        explorer.querySelectorAll("[data-geo-mode]").forEach((candidate) => candidate.classList.toggle("is-active", candidate === button));
        renderers[button.dataset.geoMode]();
    }));
    renderRegion();
})();

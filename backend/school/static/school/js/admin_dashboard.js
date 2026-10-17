(() => {
    "use strict";
    const explorer = document.querySelector("[data-geo-explorer]");
    const source = document.getElementById("geo-map-data");
    if (!explorer || !source) return;
    const data = JSON.parse(source.textContent);
    const stage = explorer.querySelector("[data-geo-stage]");
    const list = explorer.querySelector("[data-geo-ranking-list]");
    const title = explorer.querySelector("[data-geo-ranking-title]");
    const kicker = explorer.querySelector("[data-geo-ranking-kicker]");
    let map;
    let thailandGeoJson;
    let worldGeoJson;

    const points = {
        region: { northern:[18.45,99.05],central:[14.45,100.45],eastern:[13.15,101.45],western:[14.45,98.75],northeastern:[16.1,103.1],southern:[8.15,99.35] },
        province: { "กรุงเทพมหานคร":[13.7563,100.5018],"สมุทรปราการ":[13.5991,100.5998],"นนทบุรี":[13.8621,100.5144],"ปทุมธานี":[14.0208,100.525],"นครปฐม":[13.8199,100.0622],"สมุทรสาคร":[13.5475,100.2744],"เชียงใหม่":[18.7883,98.9853],"เชียงราย":[19.9105,99.8406],"ลำปาง":[18.2888,99.4909],"พิษณุโลก":[16.8211,100.2659],"นครสวรรค์":[15.7047,100.1372],"พระนครศรีอยุธยา":[14.3532,100.5689],"กาญจนบุรี":[14.0228,99.5328],"ชลบุรี":[13.3611,100.9847],"ระยอง":[12.6814,101.2816],"จันทบุรี":[12.6113,102.1038],"ปราจีนบุรี":[14.0509,101.3723],"นครราชสีมา":[14.9799,102.0978],"ขอนแก่น":[16.4419,102.835],"อุดรธานี":[17.4138,102.787],"อุบลราชธานี":[15.2448,104.8473],"สุราษฎร์ธานี":[9.1382,99.3215],"นครศรีธรรมราช":[8.4304,99.9631],"สงขลา":[7.1898,100.5954],"ภูเก็ต":[7.8804,98.3923],"เพชรบุรี":[13.1119,99.939],"ราชบุรี":[13.5283,99.8134],"สุพรรณบุรี":[14.4745,100.1177],"ลพบุรี":[14.7995,100.6534],"สระบุรี":[14.5289,100.9101] },
        country: { TH:[15.87,100.99],LA:[19.86,102.49],US:[39.83,-98.58],AU:[-25.27,133.78],NO:[60.47,8.47],GB:[55.38,-3.44],FR:[46.23,2.21],DE:[51.17,10.45],CN:[35.86,104.2],JP:[36.2,138.25],KR:[35.91,127.77],SG:[1.35,103.82],MY:[4.21,101.98],MM:[21.92,95.96],KH:[12.57,104.99],VN:[14.06,108.28],IN:[20.59,78.96],CA:[56.13,-106.35],NZ:[-40.9,174.89],PH:[12.88,121.77] },
    };
    const escapeHtml = (value) => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"})[c]);
    const maximum = items => Math.max(1, ...items.map(item => item.count));

    const ranking = (items) => {
        const max = maximum(items);
        list.innerHTML = items.slice(0,10).map((item,index) => `<button type="button" class="geo-rank-row" data-rank-key="${escapeHtml(item.value || item.code || item.label)}"><span class="geo-rank-number">${String(index+1).padStart(2,"0")}</span><span class="geo-rank-content"><span><b>${escapeHtml(item.label)}</b><strong>${item.count.toLocaleString("th-TH")}</strong></span><i style="--geo-value:${item.count/max*100}%"></i></span></button>`).join("") || '<p class="geo-empty">ยังไม่มีข้อมูล</p>';
    };
    const createMap = mode => {
        if (!window.L) {
            stage.innerHTML = '<div class="geo-map-unavailable"><strong>โหลดแผนที่ไม่สำเร็จ</strong><span>ตรวจสอบอินเทอร์เน็ตแล้วรีเฟรชหน้าอีกครั้ง</span></div>';
            return false;
        }
        if (map) map.remove();
        stage.replaceChildren();
        map = L.map(stage,{zoomControl:false,attributionControl:true,scrollWheelZoom:false});
        L.control.zoom({position:"bottomright"}).addTo(map);
        map.setView(mode === "country" ? [20,30] : [13.4,101],mode === "country" ? 2 : 5);
        return true;
    };
    const render = mode => {
        const configs = {
            region:{items:data.regions || [],title:"ผู้สมัครแยกตามภูมิภาค",kicker:"ประเทศไทย"},
            province:{items:data.provinces || [],title:"จังหวัดที่พบมาก",kicker:"แผนที่ประเทศไทย"},
            country:{items:data.countries || [],title:"ประเทศของผู้สมัคร",kicker:"ภาพรวมทั่วโลก"},
        };
        const config = configs[mode]; title.textContent = config.title; kicker.textContent = config.kicker; ranking(config.items);
        if (!createMap(mode)) return;
        const max = maximum(config.items), markers = new Map(), bounds = [];
        if (mode === "country" && worldGeoJson) {
            const counts = new Map(config.items.map(item=>[item.code,item.count]));
            L.geoJSON(worldGeoJson,{style:feature=>({color:"#fff",weight:.7,fillColor:counts.has(feature.properties.ISO_A2) ? "#a9c5af" : "#e1e9e3",fillOpacity:1})}).addTo(map);
        } else if (thailandGeoJson) {
            const counts = new Map((data.provinces || []).map(item=>[item.label,item.count]));
            L.geoJSON(thailandGeoJson,{style:feature=>({color:"#fff",weight:1.2,fillColor:counts.has(feature.properties.ADM1_TH) ? "#b5d0ba" : "#dde8df",fillOpacity:1})}).addTo(map);
        }
        config.items.forEach(item => {
            const key = item.value || item.code || item.label, point = points[mode][key];
            if (!point) return;
            const radius = 9 + Math.sqrt(item.count/max) * (mode === "region" ? 29 : 21);
            const marker = L.circleMarker(point,{radius,color:"#fff",weight:3,fillColor:mode === "country" ? "#ad4e30" : "#28513a",fillOpacity:.9,className:"geo-leaflet-marker"}).addTo(map);
            marker.bindTooltip(`<div class="geo-popup"><small>${mode === "country" ? "ประเทศ" : mode === "province" ? "จังหวัด" : "ภูมิภาค"}</small><strong>${escapeHtml(item.label)}</strong><span>${item.count.toLocaleString("th-TH")} คน</span></div>`,{direction:"top",offset:[0,-radius/2],opacity:1,className:"geo-leaflet-tooltip"});
            marker.on("click",()=>marker.openTooltip()); markers.set(key,marker); bounds.push(point);
        });
        if (mode !== "country" && bounds.length) map.fitBounds(bounds,{padding:[55,55],maxZoom:6});
        list.querySelectorAll("[data-rank-key]").forEach(row => row.addEventListener("click",()=>{const marker=markers.get(row.dataset.rankKey);if(marker){map.flyTo(marker.getLatLng(),mode === "country" ? 4 : 8,{duration:.7});marker.openTooltip();}}));
        window.setTimeout(()=>map.invalidateSize(),50);
    };
    explorer.querySelectorAll("[data-geo-mode]").forEach(button => button.addEventListener("click",()=>{explorer.querySelectorAll("[data-geo-mode]").forEach(item=>item.classList.toggle("is-active",item===button));render(button.dataset.geoMode);}));
    Promise.all([
        fetch(explorer.dataset.thailandMapUrl).then(response=>response.json()),
        fetch(explorer.dataset.worldMapUrl).then(response=>response.json()),
    ]).then(([thailand,world])=>{thailandGeoJson=thailand;worldGeoJson=world;render("region");})
      .catch(()=>render("region"));
})();

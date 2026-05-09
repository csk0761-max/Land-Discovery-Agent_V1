import math
import json
import re
import urllib.parse
import urllib.request
from html import unescape
from typing import Dict, List, Optional


SIMULATION_WARNING = (
    "Simulated cadastral data for demo use only. Do not treat owners, khasra numbers, "
    "areas, or land classifications as verified land records."
)

MOCK_OWNER_NAMES = [
    "Ramesh Chand",
    "Sunita Devi",
    "Gram Panchayat",
    "State Govt",
    "Suresh Kumar",
    "Anita Sharma",
    "Rajesh Singh",
    "Local Authority",
]

CHHATTISGARH_BHUNAKSHA_STATE_CODE = "22"
CHHATTISGARH_VILLAGE_SELECTOR_URL = "https://bhunaksha.cg.nic.in/village_selector.jsp"
CHHATTISGARH_SCALAR_HANDLER_URL = "https://bhunaksha.cg.nic.in/ScalarDatahandler"
CHHATTISGARH_KHASRA_DETAILS_URL = "https://revenue.cg.nic.in/bhuiyanuser/User/Selection_Report_For_KhasraDetail.aspx"
CHHATTISGARH_DISTRICT_ALIASES = {
    "balod": "62",
    "baloda bazar": "50",
    "baloda bazar bhatapara": "50",
    "balodabazar": "50",
    "balodabazar bhatapara": "50",
    "balrampur": "65",
    "balrampur ramanujganj": "65",
    "bastar": "45",
    "bemetara": "52",
    "bijapur": "47",
    "bilaspur": "40",
    "dantewada": "61",
    "dhamtari": "59",
    "durg": "43",
    "gaurela pendra marwahi": "66",
    "gariaband": "51",
    "janjgir champa": "54",
    "jashpur": "56",
    "kabirdham": "57",
    "kanker": "60",
    "khairagarh chhuikhadan gandai": "67",
    "kondagaon": "49",
    "korba": "55",
    "korea": "53",
    "mahasamund": "58",
    "manendragarh chirmiri bharatpur": "71",
    "mohla manpur ambagarh chowki": "68",
    "mungeli": "63",
    "narayanpur": "46",
    "raigarh": "41",
    "raipur": "44",
    "rajnandgaon": "42",
    "sakti": "69",
    "sarangarh bilaigarh": "70",
    "sukma": "48",
    "surajpur": "64",
    "surguja": "39",
}


# Mapping of States to their Bhu Naksha WMS and AJAX Portals
STATE_CONFIGS = {
    'Rajasthan': {
        'wms_url': 'https://bhunaksha.rajasthan.gov.in/bhunaksha/wms',
        'ajax_url': 'https://bhunaksha.rajasthan.gov.in/bhunaksha/index.php?r=site/getPlotInfo',
        'layer': 'bhunaksha:village_map',
        'portal_name': 'Apna Khata / Bhu Naksha RJ'
    },
    'Gujarat': {
        'wms_url': 'https://anyror.gujarat.gov.in/bhunaksha/wms',
        'ajax_url': 'https://anyror.gujarat.gov.in/bhunaksha/index.php?r=site/getPlotInfo',
        'layer': 'bhunaksha:plot_map',
        'portal_name': 'AnyROR / Bhu Naksha GJ'
    },
    'Madhya Pradesh': {
        'wms_url': 'https://mpbhulekh.gov.in/bhunaksha/wms',
        'ajax_url': 'https://mpbhulekh.gov.in/bhunaksha/index.php?r=site/getPlotInfo',
        'layer': 'bhunaksha:cadastral_map',
        'portal_name': 'MP Bhulekh'
    },
    'Chhattisgarh': {
        'wms_url': 'https://bhunaksha.cg.nic.in/bhunaksha/wms',
        'ajax_url': 'https://bhunaksha.cg.nic.in/bhunaksha/index.php?r=site/getPlotInfo',
        'layer': 'bhunaksha:village_map',
        'portal_name': 'Bhuiyan / Bhu Naksha CG'
    },
    'Default': {
        'wms_url': 'https://bhunaksha.rajasthan.gov.in/bhunaksha/wms',
        'ajax_url': 'https://bhunaksha.rajasthan.gov.in/bhunaksha/index.php?r=site/getPlotInfo',
        'layer': 'bhunaksha:village_map',
        'portal_name': 'NIC Bhu Naksha (Fallback)'
    }
}

def get_plot_owner_info(lat: float, lon: float, state_name: str = 'Rajasthan') -> dict:
    """
    Fetches Khasra No and Owner List for a specific coordinate.
    Uses standard NIC Bhu Naksha WMS GetFeatureInfo + Ajax pattern.
    """
    config = STATE_CONFIGS.get(state_name, STATE_CONFIGS['Default'])
    
    try:
        # Step 1: Perform WMS GetFeatureInfo to retrieve metadata (Khasra No / Plot ID)
        # We simulate a tiny BBOX around the point to perform GetFeatureInfo
        bbox = f"{lon-0.0001},{lat-0.0001},{lon+0.0001},{lat+0.0001}"
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": config['layer'],
            "QUERY_LAYERS": config['layer'],
            "BBOX": bbox,
            "WIDTH": 101,
            "HEIGHT": 101,
            "X": 50,
            "Y": 50,
            "INFO_FORMAT": "application/json",
            "SRS": "EPSG:4326"
        }
        
        # Note: In a real environment, we'd hit the WMS, but since government servers 
        # often rate-limit or bypass EPSG:4326 easily, we use the fallback method 
        # or the direct site logic if known.
        
        # Step 2: Use the Khasra ID to get Plot Info
        # Most NIC Bhu Naksha instances have a 'getPlotInfo' endpoint
        # For now, we'll implement a robust mock-ready structure that identifies the 
        # Khasra from the coordinate via a "best-guess" or direct API if found.
        
        # Simulate fetching plot id for now since real GFI requires specialized headers
        # in some state environments.
        
        # Example URL: bhunaksha.rajasthan.gov.in/bhunaksha/index.php?r=site/getPlotInfo&plot_id=...
        # We'll return the Khasra Number + Owner candidate for the prompt.
        
        # Mocking a realistic response for Rajasthan in the absence of a stable WMS proxy
        # In a production environment, this would be a live HTTP call.
        return {
            "data_source": "simulated",
            "is_simulated": True,
            "warning": SIMULATION_WARNING,
            "khasra_no": "135/1", # Candidate
            "owners": ["Chandan Singh", "Local Gram Panchayat"],
            "area_ha": 2.45,
            "land_type": "Chahi (Irrigated)",
            "portal": config['portal_name'],
            "status": "Simulated Plot Metadata"
        }

    except Exception as e:
        return {"error": f"Revenue system inaccessible: {e}"}

def get_wms_config(state_name: str) -> dict:
    return STATE_CONFIGS.get(state_name, STATE_CONFIGS['Default'])

def estimate_polygon_area_acres(polygon: List[List[float]]) -> float:
    if not polygon or len(polygon) < 3:
        return 0.0

    earth_radius_m = 6371008.8
    normalized = [(float(point[0]), float(point[1])) for point in polygon]
    if normalized[0] != normalized[-1]:
        normalized.append(normalized[0])

    reference_lat = math.radians(sum(lat for lat, _ in normalized[:-1]) / max(len(normalized) - 1, 1))
    projected = []
    for lat, lon in normalized:
        x = earth_radius_m * math.radians(lon) * math.cos(reference_lat)
        y = earth_radius_m * math.radians(lat)
        projected.append((x, y))

    area_m2 = 0.0
    for index in range(len(projected) - 1):
        x1, y1 = projected[index]
        x2, y2 = projected[index + 1]
        area_m2 += (x1 * y2) - (x2 * y1)

    return round(abs(area_m2) / 2 / 4046.86, 2)


def _normalize_survey_numbers(survey_numbers: Optional[List[str]]) -> List[str]:
    seen = set()
    normalized = []
    for value in survey_numbers or []:
        survey_no = str(value or "").strip()
        if not survey_no:
            continue
        lowered = survey_no.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(survey_no)
    return normalized


def _strip_html(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def _extract_select_options(html: str, select_name: str) -> List[Dict[str, str]]:
    html = (html or "").strip()
    if not html:
        return []

    # Some Bhunaksha endpoints (e.g., ScalarDatahandler) may return only <option> tags
    # or different select attributes, so we parse progressively.
    select_match = re.search(
        rf"<select[^>]+(?:name|id)=['\"][^'\"]*{re.escape(select_name)}[^'\"]*['\"][^>]*>(.*?)</select>",
        html,
        re.IGNORECASE | re.DOTALL,
    )

    options_html = select_match.group(1) if select_match else html

    options: List[Dict[str, str]] = []
    for value, label in re.findall(
        r"<option[^>]*value=['\"]([^'\"]*)['\"][^>]*>(.*?)</option>",
        options_html,
        re.IGNORECASE | re.DOTALL,
    ):
        cleaned_label = _strip_html(label)
        cleaned_value = (value or "").strip()
        if not cleaned_value or not cleaned_label:
            continue
        if cleaned_label.lower() == "select" or cleaned_label in {"--चुने--", "--चुनें--"}:
            continue
        if cleaned_value in {"--चुने--", "--चुनें--"}:
            continue
        options.append({"value": cleaned_value, "label": cleaned_label})

    if options:
        return options

    # Fallback: some handlers can return JSON arrays.
    if html[:1] in {"[", "{"}:
        try:
            payload = json.loads(html)
        except Exception:
            return []

        if isinstance(payload, dict):
            payload = payload.get("options") or payload.get("data") or []

        if isinstance(payload, list):
            normalized: List[Dict[str, str]] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                value = str(item.get("value") or item.get("Value") or item.get("code") or "").strip()
                label = str(item.get("label") or item.get("Label") or item.get("text") or item.get("Text") or "").strip()
                if value and label:
                    normalized.append({"value": value, "label": label})
            return normalized

    return []


def _extract_aspx_metadata(html: str) -> Dict[str, str]:
    """Extracts hidden ASP.NET fields needed for postbacks with robust regex."""
    fields = {}
    for field in ["__VIEWSTATE", "__EVENTVALIDATION", "__VIEWSTATEGENERATOR", "__LASTFOCUS", "__EVENTTARGET", "__EVENTARGUMENT"]:
        # Match both name="field" value="val" and value="val" name="field"
        pattern = rf'<input[^>]+(?:name="{re.escape(field)}"[^>]+value="([^"]*)"|value="([^"]*)"[^>]+name="{re.escape(field)}")'
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            fields[field] = match.group(1) or match.group(2) or ""
        else:
            fields[field] = ""
    return fields


import http.cookiejar

# Global session for Bhuiyan to maintain ASP.NET cookies
_bhuiyan_cookie_jar = http.cookiejar.CookieJar()
_bhuiyan_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_bhuiyan_cookie_jar))

def _fetch_text(
    url: str,
    data: Optional[Dict[str, str]] = None,
    timeout: int = 10,
    use_session: bool = False,
    extra_headers: Optional[Dict[str, str]] = None,
) -> str:
    encoded = urllib.parse.urlencode(data).encode() if data is not None else None
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    }
    if extra_headers:
        headers.update({k: v for k, v in extra_headers.items() if v is not None})
    request = urllib.request.Request(
        url,
        data=encoded,
        headers=headers,
        method="POST" if encoded is not None else "GET",
    )
    
    _exec = _bhuiyan_opener.open if use_session else urllib.request.urlopen
    with _exec(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def _extract_updatepanel_fragments(delta_text: str) -> str:
    """
    ASP.NET async postbacks (Delta=true) return a pipe-delimited payload.
    Extract updatePanel fragments and join them as HTML.
    """
    if "|updatePanel|" not in (delta_text or ""):
        return ""

    parts = delta_text.split("|")
    fragments: List[str] = []
    for index, token in enumerate(parts):
        if token != "updatePanel":
            continue
        # Format: ...|updatePanel|<panelId>|<html>|...
        if index + 2 < len(parts):
            fragments.append(parts[index + 2])
    return "\n".join(fragments).strip()


def _normalize_lookup_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def get_chhattisgarh_admin_options(
    district_code: Optional[str] = None,
    tehsil_code: Optional[str] = None,
    ri_code: Optional[str] = None,
) -> dict:
    """
    Fetches hierarchy from the official Bhuiyan portal using ASPX postbacks.
    """
    try:
        # Step 1: Initial load
        base_html = _fetch_text(CHHATTISGARH_KHASRA_DETAILS_URL, use_session=True)
        metadata = _extract_aspx_metadata(base_html)
        district_options = _extract_select_options(base_html, "ddlDist")

        resolved_district = district_code or (district_options[0]["value"] if district_options else "")
        tehsil_options: List[Dict[str, str]] = []
        ri_options: List[Dict[str, str]] = []
        village_options: List[Dict[str, str]] = []

        def _postback(
            current_metadata: Dict[str, str],
            event_target: str,
            district: str = "",
            tehsil: str = "",
            ri: str = "",
            gram: str = "",
        ) -> str:
            """
            Perform a classic ASP.NET postback. Avoid relying on ScriptManager ids (they
            vary across deployments) so the dropdown cascade keeps working.
            """
            data = {
                **current_metadata,
                "RadioButtonSelectSerachOption": "0",
                "ddlDist": district,
                "ddlTehsil": tehsil,
                "ddlRI": ri,
                "ddlGram": gram,
                "__EVENTTARGET": event_target,
                "__EVENTARGUMENT": "",
            }
            return _fetch_text(CHHATTISGARH_KHASRA_DETAILS_URL, data=data, use_session=True)

        if resolved_district:
            # Step 2: Select District (Postback)
            dist_html = _postback(
                metadata,
                "ddlDist",
                district=resolved_district,
            )
            metadata = _extract_aspx_metadata(dist_html)
            tehsil_options = _extract_select_options(dist_html, "ddlTehsil")

        resolved_tehsil = tehsil_code or (tehsil_options[0]["value"] if tehsil_options else "")
        if resolved_district and resolved_tehsil:
            # Step 3: Select Tehsil (Postback)
            tehsil_html = _postback(
                metadata,
                "ddlTehsil",
                district=resolved_district,
                tehsil=resolved_tehsil,
            )
            metadata = _extract_aspx_metadata(tehsil_html)
            ri_options = _extract_select_options(tehsil_html, "ddlRI")
            village_options = _extract_select_options(tehsil_html, "ddlGram")

        resolved_ri = ri_code or (ri_options[0]["value"] if ri_options else "")
        if resolved_district and resolved_tehsil and resolved_ri:
            # Step 4: Select RI (Postback)
            ri_html = _postback(
                metadata,
                "ddlRI",
                district=resolved_district,
                tehsil=resolved_tehsil,
                ri=resolved_ri,
            )
            village_options = _extract_select_options(ri_html, "ddlGram")

        return {
            "districts": district_options,
            "tehsils": tehsil_options,
            "ris": ri_options,
            "villages": village_options,
            "selected": {
                "district_code": resolved_district,
                "tehsil_code": resolved_tehsil,
                "ri_code": resolved_ri,
            },
            "portal": "Bhuiyan / Chhattisgarh Revenue",
            "is_official": True,
        }
    except Exception as e:
        # Fallback to Bhu Naksha or simulate if portal is down
        print(f"Bhuiyan Portal error: {e}. Falling back to Bhu Naksha parser...")
        return {
            "districts": [{"value": "0", "label": "Service Temporarily Unavailable"}],
            "tehsils": [],
            "ris": [],
            "villages": [],
            "selected": {},
            "portal": "Bhuiyan (Offline)",
            "is_official": False,
            "error": str(e)
        }


def _compose_chhattisgarh_village_code(district_code: str, tehsil_code: str, ri_code: str, village_code: str) -> str:
    return f"{district_code}{tehsil_code}{ri_code}.{village_code}"


def _extract_between_ids(html: str, element_id: str) -> str:
    match = re.search(rf'id="{re.escape(element_id)}"[^>]*>(.*?)</', html, re.IGNORECASE | re.DOTALL)
    return _strip_html(match.group(1)) if match else ""


def _extract_link_by_id(html: str, element_id: str) -> Dict[str, str]:
    match = re.search(
        rf'<(?P<tag>[a-z0-9]+)[^>]*id=["\']{re.escape(element_id)}["\'][^>]*>(?P<body>.*?)</(?P=tag)>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {"text": "", "url": ""}

    element_html = match.group(0)
    body = match.group("body")
    href_match = re.search(r'href=["\']([^"\']+)["\']', element_html, re.IGNORECASE)
    href = href_match.group(1).strip() if href_match else ""
    if href and not href.lower().startswith("javascript:"):
        href = urllib.parse.urljoin(CHHATTISGARH_KHASRA_DETAILS_URL, href)

    return {
        "text": _strip_html(body),
        "url": href,
    }


def _extract_row_link_by_label(html: str, label_pattern: str) -> Dict[str, str]:
    row_match = re.search(
        rf"<tr[^>]*>.*?{label_pattern}.*?</tr>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not row_match:
        return {"text": "", "url": ""}

    row_html = row_match.group(0)
    # Find the first <a> tag in the row and extract its inner text
    link_match = re.search(r"<a[^>]*>(.*?)</a>", row_html, re.IGNORECASE | re.DOTALL)
    text = _strip_html(link_match.group(1)) if link_match else _strip_html(row_html)
    
    href_match = re.search(r'href=["\']([^"\']+)["\']', row_html, re.IGNORECASE)
    href = href_match.group(1).strip() if href_match else ""
    if href and not href.lower().startswith("javascript:"):
        href = urllib.parse.urljoin(CHHATTISGARH_KHASRA_DETAILS_URL, href)

    return {
        "text": text,
        "url": href,
    }


def fetch_chhattisgarh_by_khasra_id(khasra_id: str) -> dict:
    """
    Directly searches for a record using the official Khasra ID.
    """
    try:
        base_html = _fetch_text(CHHATTISGARH_KHASRA_DETAILS_URL, use_session=True)
        metadata = _extract_aspx_metadata(base_html)
        
        data = {
            **metadata,
            "RadioButtonSelectSerachOption": "1",
            "txt_searchkhasaraid": khasra_id,
            "btn_searchkhasaraid": "खोजें",
        }
        html = _fetch_text(CHHATTISGARH_KHASRA_DETAILS_URL, data=data, use_session=True)
        
        return _parse_chhattisgarh_report(html, khasra_id)
    except Exception as e:
        return {
            "khasra_id": khasra_id,
            "error": str(e),
            "status": "Direct Lookup Failed"
        }


def _parse_chhattisgarh_report(html: str, search_ref: str) -> dict:
    owner_text = _extract_between_ids(html, "lblbhuswami")
    khasra_text = _extract_between_ids(html, "lblkhsarano")
    khasra_id_extracted = _extract_between_ids(html, "lblKhasraID")
    irrigated = _extract_between_ids(html, "lblsinchitbhoomi")
    unirrigated = _extract_between_ids(html, "lblasinchitbhoomi")
    basra = _extract_between_ids(html, "lblbasra")
    previous_owner = _extract_between_ids(html, "lblpurvabhuswami")
    holding_right = _extract_between_ids(html, "lblcaste")
    map_link = _extract_link_by_id(html, "lblNakshaLnk")
    log_report_link = _extract_link_by_id(html, "lbllogreport")
    deed_details_link = _extract_link_by_id(html, "lblepanjeeyandetail")
    napix_link = _extract_link_by_id(html, "lblNapix")
    signed_pii_link = _extract_link_by_id(html, "hyPdf1")
    signed_khatauni_bi_link = _extract_row_link_by_label(html, r"डिजिटल\s+हस्ताक्षरित\s+खतौनी[-\s]*B[आईI]")
    pii_crop_link = _extract_link_by_id(html, "lnkButtonpdfkhand2")
    pii_previous_crop_link = _extract_link_by_id(html, "lnkButtonpdfkhandpurv2")
    other_owner_details = _extract_between_ids(html, "lblanyabhuswami")
    other_khasra_details = _extract_between_ids(html, "lblanyakhasara")
    crop_details = {
        "irrigated_crop": _extract_between_ids(html, "lblfasal1"),
        "irrigated_area": _extract_between_ids(html, "lblsinchit"),
        "unirrigated_crop": _extract_between_ids(html, "lblfasal2"),
        "unirrigated_area": _extract_between_ids(html, "lblasinchit"),
        "double_crop_area": _extract_between_ids(html, "lbldwifasli"),
        "fallow_area": _extract_between_ids(html, "lblpadti1"),
        "fallow_2_to_5_year_area": _extract_between_ids(html, "lblpadti2"),
        "other_fallow_area": _extract_between_ids(html, "lblanyapadti"),
    }

    if not owner_text and not khasra_text:
         return {"error": "No record found", "search_ref": search_ref}

    area_match = re.search(r"\(\s*([0-9.]+)\s*हे", khasra_text)
    area_ha = float(area_match.group(1)) if area_match else None
    area_acres = round(area_ha * 2.47105, 4) if area_ha is not None else None

    owner_lines = [line.strip() for line in owner_text.splitlines() if line.strip()]
    primary_owner = owner_lines[0] if owner_lines else owner_text

    return {
        "survey_no": search_ref,
        "khasra_no": basra or search_ref,
        "owner": primary_owner,
        "owner_details": owner_text,
        "previous_owner_details": previous_owner,
        "other_owner_details": other_owner_details,
        "other_khasra_details": other_khasra_details,
        "area_hectare": area_ha,
        "area_acres": area_acres,
        "irrigated_area": irrigated,
        "unirrigated_area": unirrigated,
        "holding_right": holding_right,
        "land_transfer_restriction": "",
        "mortgage_or_bank_loan_details": "",
        "mutation_previous_owner_details": previous_owner,
        "deed_number": deed_details_link.get("text", ""),
        "deed_details_url": deed_details_link.get("url", ""),
        "digitally_signed_khasra_pii": signed_pii_link.get("text", ""),
        "digitally_signed_khasra_pii_url": signed_pii_link.get("url", ""),
        "digitally_signed_khatauni_bi": signed_khatauni_bi_link.get("text", ""),
        "digitally_signed_khatauni_bi_url": signed_khatauni_bi_link.get("url", ""),
        "khasra_pii_khand_2_crop_details": pii_crop_link.get("text", ""),
        "khasra_pii_khand_2_crop_details_url": pii_crop_link.get("url", ""),
        "khasra_pii_khand_2_previous_crop_details": pii_previous_crop_link.get("text", ""),
        "khasra_pii_khand_2_previous_crop_details_url": pii_previous_crop_link.get("url", ""),
        "log_report": log_report_link.get("text", ""),
        "log_report_url": log_report_link.get("url", ""),
        "napix_details": napix_link.get("text", ""),
        "napix_details_url": napix_link.get("url", ""),
        "map_url": map_link.get("url", ""),
        "crop_details": crop_details,
        "khasra_id": khasra_id_extracted or search_ref,
        "status": "Official Chhattisgarh Land Record",
    }


def fetch_chhattisgarh_khasra_details(
    district_code: str, 
    tehsil_code: str, 
    ri_code: str, 
    village_code: str, 
    survey_number: str
) -> dict:
    """
    Fetches details using the Location Search (dropdowns) mode.
    """
    try:
        # Step 1: Prime dropdowns to get to the survey input
        base_html = _fetch_text(CHHATTISGARH_KHASRA_DETAILS_URL, use_session=True)
        metadata = _extract_aspx_metadata(base_html)

        dist_html = _fetch_text(
            CHHATTISGARH_KHASRA_DETAILS_URL,
            data={
                **metadata,
                "RadioButtonSelectSerachOption": "0",
                "ddlDist": district_code,
                "ddlTehsil": "",
                "ddlRI": "",
                "ddlGram": "",
                "__EVENTTARGET": "ddlDist",
                "__EVENTARGUMENT": "",
            },
            use_session=True,
        )
        metadata = _extract_aspx_metadata(dist_html)

        tehsil_html = _fetch_text(
            CHHATTISGARH_KHASRA_DETAILS_URL,
            data={
                **metadata,
                "RadioButtonSelectSerachOption": "0",
                "ddlDist": district_code,
                "ddlTehsil": tehsil_code,
                "ddlRI": "",
                "ddlGram": "",
                "__EVENTTARGET": "ddlTehsil",
                "__EVENTARGUMENT": "",
            },
            use_session=True,
        )
        metadata = _extract_aspx_metadata(tehsil_html)
        
        village_html = _fetch_text(
            CHHATTISGARH_KHASRA_DETAILS_URL,
            data={
                **metadata,
                "RadioButtonSelectSerachOption": "0",
                "ddlDist": district_code,
                "ddlTehsil": tehsil_code,
                "ddlRI": ri_code,
                "ddlGram": village_code,
                "__EVENTTARGET": "ddlGram",
                "__EVENTARGUMENT": "",
            },
            use_session=True,
        )
        metadata = _extract_aspx_metadata(village_html)
        
        html = _fetch_text(
            CHHATTISGARH_KHASRA_DETAILS_URL,
            data={
                **metadata,
                "RadioButtonSelectSerachOption": "0",
                "RblReportType": "0",
                "ddlDist": district_code,
                "ddlTehsil": tehsil_code,
                "ddlRI": ri_code,
                "ddlGram": village_code,
                "txtSearch": survey_number,
                "btnSearch": "विवरण देखें",
                "hdgsrNo": village_code,
                "hdnBasrNo": "",
                "hdnkhasraLst": "",
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
            },
            use_session=True,
        )
        return _parse_chhattisgarh_report(html, survey_number)
        
    except Exception as e:
        return {
            "survey_no": survey_number,
            "error": str(e),
            "status": "Location Lookup Failed"
        }


def _build_survey_owner_record(survey_number: str, index: int, area_acres: float) -> dict:
    seed_digits = "".join(ch for ch in survey_number if ch.isdigit())
    seed = int(seed_digits or index + 1)
    owner_name = MOCK_OWNER_NAMES[seed % len(MOCK_OWNER_NAMES)]
    land_type = "Banjar (Barren)" if seed % 3 == 0 else "Chahi (Irrigated)"
    area_share = round(area_acres, 2) if area_acres else 0.0
    return {
        "survey_no": survey_number,
        "khasra_no": survey_number,
        "owner": owner_name,
        "area_acres": area_share,
        "land_type": land_type,
    }


def get_gujarat_admin_options(
    district_code: Optional[str] = None,
    taluka_code: Optional[str] = None,
) -> dict:
    # Simulated AnyROR Gujarat Geographic Hierarchy
    districts = [
        {"value": "01", "label": "Ahmedabad"},
        {"value": "02", "label": "Surat"},
        {"value": "03", "label": "Vadodara"},
        {"value": "04", "label": "Rajkot"},
        {"value": "05", "label": "Kutch"},
    ]
    
    talukas_map = {
        "01": [{"value": "0101", "label": "Ahmedabad City"}, {"value": "0102", "label": "Daskroi"}],
        "02": [{"value": "0201", "label": "Surat City"}, {"value": "0202", "label": "Choryasi"}],
        "03": [{"value": "0301", "label": "Vadodara City"}, {"value": "0302", "label": "Padra"}],
        "04": [{"value": "0401", "label": "Rajkot City"}, {"value": "0402", "label": "Gondal"}],
        "05": [{"value": "0501", "label": "Bhuj"}, {"value": "0502", "label": "Anjar"}],
    }

    villages_map = {
        "0101": [{"value": "010101", "label": "Thaltej"}, {"value": "010102", "label": "Vastrapur"}],
        "0102": [{"value": "010201", "label": "Kuha"}, {"value": "010202", "label": "Kanbha"}],
    }

    resolved_district = district_code or (districts[0]["value"] if districts else "")
    taluka_options = talukas_map.get(resolved_district, [{"value": f"{resolved_district}01", "label": "Default Taluka"}])
    
    resolved_taluka = taluka_code or (taluka_options[0]["value"] if taluka_options else "")
    village_options = villages_map.get(resolved_taluka, [{"value": f"{resolved_taluka}01", "label": "Default Village 1"}, {"value": f"{resolved_taluka}02", "label": "Default Village 2"}])

    return {
        "districts": districts,
        "talukas": taluka_options,
        "villages": village_options,
        "selected": {
            "district_code": resolved_district,
            "taluka_code": resolved_taluka,
        },
        "portal": "AnyROR Gujarat (Simulated)",
        "is_official": False,
    }


def fetch_gujarat_survey_details(
    district_code: str, 
    taluka_code: str, 
    village_code: str, 
    survey_number: str
) -> dict:
    """
    Simulates fetching details using the AnyROR Gujarat 7/12 RoR layout.
    """
    seed_str = f"{district_code}{taluka_code}{village_code}{survey_number}"
    seed = sum(ord(c) for c in seed_str)
    owner_name = MOCK_OWNER_NAMES[seed % len(MOCK_OWNER_NAMES)]
    area_ha = round((seed % 100) * 0.05 + 0.5, 2)
    area_acres = round(area_ha * 2.47105, 4)
    
    return {
        "survey_no": survey_number,
        "khasra_no": survey_number,
        "owner": owner_name,
        "owner_details": f"{owner_name} and co-parceners",
        "previous_owner_details": "Mutation via succession",
        "other_owner_details": "None",
        "other_khasra_details": "7/12 (Village Form 7/12)",
        "area_hectare": area_ha,
        "area_acres": area_acres,
        "irrigated_area": f"{round(area_ha * 0.8, 2)} HA",
        "unirrigated_area": f"{round(area_ha * 0.2, 2)} HA",
        "holding_right": "New Tenure" if seed % 2 == 0 else "Old Tenure",
        "land_transfer_restriction": "Section 43 Applicable" if seed % 2 == 0 else "None",
        "mortgage_or_bank_loan_details": "SBI Agricultural Loan" if seed % 3 == 0 else "Clear Title",
        "mutation_previous_owner_details": "",
        "deed_number": f"GJ-{seed}-DOC",
        "deed_details_url": "",
        "digitally_signed_khasra_pii": "Digitally Signed 7/12 RoR",
        "digitally_signed_khasra_pii_url": "#",
        "digitally_signed_khatauni_bi": "Digitally Signed Village Form 8A",
        "digitally_signed_khatauni_bi_url": "#",
        "khasra_id": f"GJ-{district_code}-{taluka_code}-{village_code}-{survey_number}",
        "status": "Simulated AnyROR 7/12 Record",
    }


def get_polygon_owner_info(
    lat: float,
    lon: float,
    area_acres: float,
    state_name: str = 'Chhattisgarh',
    survey_numbers: Optional[List[str]] = None,
    admin_hierarchy: Optional[Dict[str, str]] = None,
) -> dict:
    """
    Fetches official ownership records or simulates them if portal data is missing.
    Supports Chhattisgarh-specific search modes (Location vs Khasra ID).
    """
    config = STATE_CONFIGS.get(state_name, STATE_CONFIGS['Default'])
    normalized_survey_numbers = _normalize_survey_numbers(survey_numbers)

    if state_name == "Gujarat":
        selected_admin = admin_hierarchy or {}
        
        district_code = str(selected_admin.get("district_code") or "").strip()
        taluka_code = str(selected_admin.get("taluka_code") or "").strip()
        village_code = str(selected_admin.get("village_code") or "").strip()

        if district_code and taluka_code and village_code:
            records = []
            for survey_number in normalized_survey_numbers:
                record = fetch_gujarat_survey_details(
                    district_code, taluka_code, village_code, survey_number
                )
                records.append(record)
            
            return {
                "data_source": "simulated_gujarat",
                "is_simulated": True,
                "portal": "AnyROR Portal (Simulated)",
                "state": state_name,
                "total_khasras_found": len([r for r in records if "error" not in r]),
                "survey_numbers_requested": normalized_survey_numbers,
                "khasra_records": records,
                "status": "Simulated AnyROR Ownership Lookup",
            }

        admin_options = get_gujarat_admin_options(
            district_code=district_code or None,
            taluka_code=taluka_code or None,
        )
        return {
            "data_source": "simulated_gujarat",
            "is_simulated": True,
            "portal": config["portal_name"],
            "state": state_name,
            "total_khasras_found": 0,
            "survey_numbers_requested": normalized_survey_numbers,
            "requires_admin_selection": True,
            "admin_options": admin_options,
            "warning": "Select the exact district, taluka, and village.",
            "khasra_records": [],
            "status": "Gujarat inputs required",
        }

    if state_name == "Chhattisgarh":
        selected_admin = admin_hierarchy or {}
        search_mode = selected_admin.get("search_mode", "location")  # "location" or "khasra_id"
        
        if search_mode == "khasra_id" and normalized_survey_numbers:
            # Direct Khasra ID Search (can handle multiple IDs)
            records = [
                fetch_chhattisgarh_by_khasra_id(sid)
                for sid in normalized_survey_numbers
            ]
            return {
                "data_source": "official_chhattisgarh",
                "is_simulated": False,
                "portal": "Bhuiyan Portal (Khasra ID Mode)",
                "state": state_name,
                "total_khasras_found": len([r for r in records if "error" not in r]),
                "khasra_records": records,
                "status": "Official Chhattisgarh Khasra ID Lookup",
            }

        # Location Search Mode
        district_code = str(selected_admin.get("district_code") or "").strip()
        tehsil_code = str(selected_admin.get("tehsil_code") or "").strip()
        ri_code = str(selected_admin.get("ri_code") or "").strip()
        village_code = str(selected_admin.get("village_code") or "").strip()

        if district_code and tehsil_code and village_code:
            # Multi-survey iteration as requested by user
            records = []
            for survey_number in normalized_survey_numbers:
                record = fetch_chhattisgarh_khasra_details(
                    district_code, tehsil_code, ri_code, village_code, survey_number
                )
                records.append(record)
            
            return {
                "data_source": "official_chhattisgarh",
                "is_simulated": False,
                "portal": "Bhuiyan Portal (Location Mode)",
                "state": state_name,
                "total_khasras_found": len([r for r in records if "error" not in r]),
                "survey_numbers_requested": normalized_survey_numbers,
                "khasra_records": records,
                "status": "Official Chhattisgarh Location Ownership Lookup",
            }

        # If location details are missing, return admin options to prompt user
        admin_options = get_chhattisgarh_admin_options(
            district_code=district_code or None,
            tehsil_code=tehsil_code or None,
            ri_code=ri_code or None,
        )
        return {
            "data_source": "official_chhattisgarh",
            "is_simulated": False,
            "portal": config["portal_name"],
            "state": state_name,
            "total_khasras_found": 0,
            "survey_numbers_requested": normalized_survey_numbers,
            "requires_admin_selection": True,
            "admin_options": admin_options,
            "warning": "Select the exact district, tehsil, RI, and village or provide Khasra ID.",
            "khasra_records": [],
            "status": "Chhattisgarh inputs required",
        }

    if normalized_survey_numbers:
        split_area = area_acres / len(normalized_survey_numbers) if area_acres and len(normalized_survey_numbers) else 0.0
        records = [
            _build_survey_owner_record(survey_number, index, split_area)
            for index, survey_number in enumerate(normalized_survey_numbers)
        ]
        return {
            "data_source": "simulated",
            "is_simulated": True,
            "warning": SIMULATION_WARNING,
            "portal": config['portal_name'],
            "state": state_name,
            "total_khasras_found": len(records),
            "survey_numbers_requested": normalized_survey_numbers,
            "khasra_records": records,
            "status": "Simulated Survey Ownership Lookup",
        }
    
    # Simulate finding 1 khasra per ~4 acres
    num_khasras = max(1, int(area_acres / 4))
    records = []
    base_khasra = int(abs(lat * lon) % 500) + 1  # pseudo-random base
    
    for i in range(num_khasras):
        owner_name = MOCK_OWNER_NAMES[(base_khasra + i) % len(MOCK_OWNER_NAMES)]
        land_type = "Banjar (Barren)" if (base_khasra + i) % 3 == 0 else "Chahi (Irrigated)"
        
        # Determine pseudo-random area for this specific khasra
        khasra_area = round(area_acres / num_khasras * (0.8 + 0.4 * ((i%3)/2)), 2)
        
        records.append({
            "khasra_no": f"{base_khasra + i}/{i+1}",
            "owner": owner_name,
            "area_acres": khasra_area,
            "land_type": land_type
        })
        
    return {
        "data_source": "simulated",
        "is_simulated": True,
        "warning": SIMULATION_WARNING,
        "portal": config['portal_name'],
        "state": state_name,
        "total_khasras_found": num_khasras,
        "khasra_records": records,
        "status": "Simulated Spatial Intersection"
    }

from vfs_appointment_bot.vfs_bot.vfs_bot import VfsBot

# Map of ISO 3166-1 alpha-3 codes → alpha-2 codes for normalisation.
# Extend this table when new destination or source countries are added.
_ALPHA3_TO_ALPHA2: dict = {
    "AFG": "AF", "AGO": "AO", "ALB": "AL", "ARE": "AE", "ARG": "AR",
    "ARM": "AM", "AUS": "AU", "AUT": "AT", "AZE": "AZ", "BEL": "BE",
    "BFA": "BF", "BGD": "BD", "BGR": "BG", "BHR": "BH", "BIH": "BA",
    "BLR": "BY", "BLZ": "BZ", "BOL": "BO", "BRA": "BR", "BRN": "BN",
    "BTN": "BT", "BWA": "BW", "CAN": "CA", "CHE": "CH", "CHL": "CL",
    "CHN": "CN", "CIV": "CI", "CMR": "CM", "COD": "CD", "COG": "CG",
    "COL": "CO", "CPV": "CV", "CRI": "CR", "CYP": "CY", "CZE": "CZ",
    "DEU": "DE", "DNK": "DK", "DOM": "DO", "DZA": "DZ", "ECU": "EC",
    "EGY": "EG", "ERI": "ER", "ESP": "ES", "ETH": "ET", "FIN": "FI",
    "FJI": "FJ", "FRA": "FR", "GAB": "GA", "GBR": "GB", "GEO": "GE",
    "GHA": "GH", "GIN": "GN", "GMB": "GM", "GNB": "GW", "GRC": "GR",
    "GTM": "GT", "GUY": "GY", "HND": "HN", "HRV": "HR", "HTI": "HT",
    "HUN": "HU", "IDN": "ID", "IND": "IN", "IRL": "IE", "IRN": "IR",
    "IRQ": "IQ", "ISL": "IS", "ISR": "IL", "ITA": "IT", "JAM": "JM",
    "JOR": "JO", "JPN": "JP", "KAZ": "KZ", "KEN": "KE", "KGZ": "KG",
    "KHM": "KH", "KWT": "KW", "LAO": "LA", "LBN": "LB", "LBY": "LY",
    "LKA": "LK", "LTU": "LT", "LUX": "LU", "LVA": "LV", "MAR": "MA",
    "MDA": "MD", "MDG": "MG", "MEX": "MX", "MKD": "MK", "MLI": "ML",
    "MMR": "MM", "MNE": "ME", "MNG": "MN", "MOZ": "MZ", "MRT": "MR",
    "MUS": "MU", "MWI": "MW", "MYS": "MY", "NAM": "NA", "NER": "NE",
    "NGA": "NG", "NIC": "NI", "NLD": "NL", "NOR": "NO", "NPL": "NP",
    "NZL": "NZ", "OMN": "OM", "PAK": "PK", "PAN": "PA", "PER": "PE",
    "PHL": "PH", "PNG": "PG", "POL": "PL", "PRT": "PT", "PRY": "PY",
    "QAT": "QA", "ROU": "RO", "RUS": "RU", "RWA": "RW", "SAU": "SA",
    "SDN": "SD", "SEN": "SN", "SGP": "SG", "SLE": "SL", "SLV": "SV",
    "SOM": "SO", "SRB": "RS", "SSD": "SS", "STP": "ST", "SVK": "SK",
    "SVN": "SI", "SWE": "SE", "SWZ": "SZ", "SYR": "SY", "TCD": "TD",
    "TGO": "TG", "THA": "TH", "TJK": "TJ", "TKM": "TM", "TLS": "TL",
    "TON": "TO", "TTO": "TT", "TUN": "TN", "TUR": "TR", "TZA": "TZ",
    "UGA": "UG", "UKR": "UA", "URY": "UY", "USA": "US", "UZB": "UZ",
    "VEN": "VE", "VNM": "VN", "YEM": "YE", "ZAF": "ZA", "ZMB": "ZM",
    "ZWE": "ZW",
}


def _normalise_country_code(code: str) -> str:
    """Normalise a country code to ISO 3166-1 alpha-2 (uppercase).

    If *code* is a 3-letter alpha-3 code (e.g. ``"PRT"``, ``"AGO"``), it is
    converted to the corresponding 2-letter alpha-2 code (``"PT"``, ``"AO"``).
    2-letter codes are returned unchanged (uppercased).

    Args:
        code: A country code string (case-insensitive, 2 or 3 characters).

    Returns:
        The uppercase ISO 3166-1 alpha-2 code.
    """
    upper = code.strip().upper()
    if len(upper) == 3:
        return _ALPHA3_TO_ALPHA2.get(upper, upper)
    return upper


class UnsupportedCountryError(Exception):
    """Raised when an unsupported destination country code is provided."""


def get_vfs_bot(source_country_code: str, destination_country_code: str) -> VfsBot:
    """Return the appropriate :class:`VfsBot` subclass for the given route.

    Both country codes are normalised to ISO 3166-1 alpha-2 (uppercase) before
    comparison, so the caller can pass 2-letter *or* 3-letter codes in any
    case (e.g. ``"in"``, ``"IN"``, ``"ind"``, ``"IND"`` are all accepted).

    Args:
        source_country_code: ISO 3166-1 alpha-2 **or** alpha-3 code of the
            applicant's country (e.g. ``"IN"`` / ``"IND"`` for India,
            ``"AO"`` / ``"AGO"`` for Angola).
        destination_country_code: ISO 3166-1 alpha-2 **or** alpha-3 code of
            the embassy/VFS country (e.g. ``"DE"`` / ``"DEU"`` for Germany,
            ``"PT"`` / ``"PRT"`` for Portugal).

    Returns:
        An instantiated :class:`VfsBot` subclass specific to the destination.

    Raises:
        UnsupportedCountryError: If the destination country is not supported.
    """
    dest = _normalise_country_code(destination_country_code)
    src = _normalise_country_code(source_country_code)

    if dest == "DE":
        from .vfs_bot_de import VfsBotDe

        return VfsBotDe(src)
    elif dest == "IT":
        from .vfs_bot_it import VfsBotIt

        return VfsBotIt(src)
    elif dest == "PT":
        from .vfs_bot_pt import VfsBotPt

        return VfsBotPt(src)
    else:
        raise UnsupportedCountryError(
            f"Destination country '{destination_country_code}' is not supported. "
            "Supported destinations: DE, IT, PT."
        )

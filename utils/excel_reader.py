import pandas as pd


REQUIRED_COLUMNS = ["countryco", "phonenumber"]
OPTIONAL_COLUMNS = ["id"]


def read_contacts_from_excel(file):
    """
    Read customer/contact data from an Excel file.

    Expected columns:
    - countryco
    - PhoneNumber

    Optional columns:
    - FirstName
    - LastName
    - ID
    """
    try:
        df = pd.read_excel(file, engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Unable to read Excel file: {exc}") from exc

    if df.empty:
        raise ValueError("Excel file is empty.")

    df.columns = [str(column).strip().lower() for column in df.columns]

    if "countryco" not in df.columns and "countrycode" in df.columns:
        df = df.rename(columns={"countrycode": "countryco"})

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            "Missing required column(s): " + ", ".join(missing_columns)
        )

    df = df.copy()

    df = df.dropna(subset=REQUIRED_COLUMNS)

    if "firstname" in df.columns:
        df["firstname"] = df["firstname"].apply(_clean_text_value)
    else:
        df["firstname"] = ""

    if "lastname" in df.columns:
        df["lastname"] = df["lastname"].apply(_clean_text_value)
    else:
        df["lastname"] = ""

    df["countryco"] = df["countryco"].apply(_clean_number_text)
    df["phonenumber"] = df["phonenumber"].apply(_clean_number_text)

    df = df[
        (df["countryco"] != "")
        & (df["phonenumber"] != "")
    ]

    if df.empty:
        raise ValueError("No valid contacts found in the Excel file.")

    contacts = []
    for _, row in df.iterrows():
        contact = {
            "first_name": row["firstname"],
            "last_name": row["lastname"],
            "name": _build_contact_name(row["firstname"], row["lastname"]),
            "country_code": row["countryco"],
            "phone_number": row["phonenumber"],
            "whatsapp_number": _format_whatsapp_number(
                row["countryco"], row["phonenumber"]
            ),
        }

        for column in df.columns:
            if column in {"firstname", "lastname", "countryco", "phonenumber"}:
                continue

            if pd.isna(row[column]):
                continue

            contact[column] = _clean_generic_value(row[column])

        if "id" in df.columns and pd.notna(row["id"]):
            contact["id"] = _clean_generic_value(row["id"])

        contacts.append(contact)

    return contacts


def _clean_text_value(value):
    return str(value).strip()


def _clean_generic_value(value):
    cleaned_value = str(value).strip()

    if cleaned_value.endswith(".0"):
        cleaned_value = cleaned_value[:-2]

    return cleaned_value


def _clean_number_text(value):
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    return value.replace(" ", "").replace("-", "")


def _format_whatsapp_number(country_code, phone_number):
    country_code = _clean_number_text(country_code).lstrip("+")
    phone_number = _clean_number_text(phone_number).lstrip("+")

    return f"+{country_code}{phone_number}"


def _build_contact_name(first_name, last_name):
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name

    return "Unnamed Contact"

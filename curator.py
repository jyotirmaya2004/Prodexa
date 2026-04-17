import pandas as pd
from datetime import datetime


# ------------------------------------
# Main Data Curation Function
# ------------------------------------
def curate_data(df):
    if df.empty:
        return df

    expected_columns = [
        "Source",
        "Source URL",
        "Search URL",
        "Product Name",
        "Price",
        "Description",
        "Image",
        "Link"
    ]

    for column in expected_columns:
        if column not in df.columns:
            df[column] = pd.NA

    df.replace(
        ["N/A", "", "None", None],
        pd.NA,
        inplace=True
    )

    df.dropna(
        subset=["Product Name", "Price"],
        inplace=True
    )

    df.drop_duplicates(
        subset=["Product Name", "Price", "Source"],
        inplace=True
    )

    df["Price"] = (
        df["Price"]
        .astype(str)
        .str.replace("\u20b9", "", regex=False)
        .str.replace("â‚¹", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.extract(r"(\d+)", expand=False)
    )

    df["Price"] = pd.to_numeric(
        df["Price"],
        errors="coerce"
    )

    df.dropna(subset=["Price"], inplace=True)

    df["Product Name"] = (
        df["Product Name"]
        .astype(str)
        .str.strip()
        .str.title()
    )

    ignore_words = [
        "Add To Compare",
        "Currently Unavailable",
        "Sponsored",
        "Assured"
    ]

    def clean_description(text):
        if pd.isna(text):
            return pd.NA

        cleaned_text = str(text)

        for word in ignore_words:
            cleaned_text = cleaned_text.replace(word, "")

        return cleaned_text.strip()

    df["Description"] = df["Description"].apply(clean_description)
    df["Source"] = df["Source"].astype(str).str.strip().str.title()
    df["Source URL"] = df["Source URL"].fillna(df["Link"])
    df["Search URL"] = df["Search URL"].fillna(df["Source URL"])
    df["Link"] = df["Link"].fillna(df["Source URL"])

    df["Brand"] = df["Product Name"].apply(
        lambda x: x.split()[0] if pd.notna(x) and x.split() else "Unknown"
    )

    df["Curated At"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    df.reset_index(drop=True, inplace=True)

    return df

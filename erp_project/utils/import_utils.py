def clean_row(row):
    return [col.strip() for col in row]


def is_header(row):
    return row[0].isupper()

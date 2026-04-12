def required_fields(data_list):
    return all(data_list)


def is_valid_email(email):
    return "@" in email and "." in email

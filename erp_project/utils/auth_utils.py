from django.contrib.auth import authenticate

def login_user(request, username, password):
    user = authenticate(request, username=username, password=password)
    return user


def validate_password(password, confirm_password):
    return password == confirm_password
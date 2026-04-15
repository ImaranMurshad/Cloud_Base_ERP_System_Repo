from django.contrib.auth.models import User
from .models import UserProfile  # optional if reusable

def register_user(data):
    full_name = data.get("full_name")
    email = data.get("email")
    username = data.get("username")
    password = data.get("password")
    confirm_password = data.get("confirm_password")
    question = data.get("question")
    answer = data.get("answer")

    if not all([full_name, email, username, password, confirm_password, question, answer]):
        return {"error": "All fields are required"}

    if password != confirm_password:
        return {"error": "Passwords do not match"}

    if User.objects.filter(username=username).exists():
        return {"error": "Username already exists"}

    if User.objects.filter(email=email).exists():
        return {"error": "Email already registered"}

    user = User.objects.create_user(
        username=username, password=password, email=email
    )

    UserProfile.objects.create(
        user=user,
        full_name=full_name,
        email=email,
        security_question=question,
        security_answer=answer,
    )

    return {"success": True, "user": user}
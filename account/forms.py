from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    ROLE_CHOICES = (
        (True, "Administrateur"),
        (False, "Utilisateur"),
    )

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        label="Rôle",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'profile_picture', 'role']

class CustomUserChangeForm(UserChangeForm):
    password = None  # Pour ne pas afficher le champ mot de passe dans la modification

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'profile_picture']




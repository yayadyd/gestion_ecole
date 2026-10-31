# creer_support.py
"""
Script à exécuter UNE FOIS avant livraison au client.
Crée un compte support (caché) avec des droits de superuser.

⚠️ SÉCURITÉ : le mot de passe est lu depuis une variable d'environnement.
   Définir SUPPORT_PASSWORD avant d'exécuter ce script.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_ecole.settings')

# ✅ FIX: on utilise une variable d'environnement lue par settings.py
# au lieu de modifier settings.DATABASES après import (fragile).
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".gestion_ecole_data")
os.makedirs(USER_DATA_DIR, exist_ok=True)
os.environ.setdefault('DJANGO_DB_NAME', os.path.join(USER_DATA_DIR, 'db.sqlite3'))

import django
django.setup()

from django.contrib.auth.models import User


# ============================================================
# COMPTE SUPPORT (CACHÉ)
# ============================================================
SUPPORT_USERNAME = os.environ.get('SUPPORT_USERNAME', 'systeme')
SUPPORT_PASSWORD = os.environ.get('SUPPORT_PASSWORD')  # ✅ FIX: pas de mot de passe en clair
SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', 'support@ton-entreprise.ml')


def creer_compte_support():
    if not SUPPORT_PASSWORD:
        print("❌ ERREUR : la variable d'environnement SUPPORT_PASSWORD n'est pas définie.")
        print("   Exemple : SUPPORT_PASSWORD='MonMotDePasseFort!' python creer_support.py")
        sys.exit(1)

    if len(SUPPORT_PASSWORD) < 12:
        print("❌ ERREUR : le mot de passe doit faire au moins 12 caractères.")
        sys.exit(1)

    user, created = User.objects.get_or_create(
        username=SUPPORT_USERNAME,
        defaults={'email': SUPPORT_EMAIL},
    )
    user.set_password(SUPPORT_PASSWORD)
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()

    if created:
        print(f"✅ Compte support créé : {SUPPORT_USERNAME}")
    else:
        print(f"✅ Compte support existant mis à jour : {SUPPORT_USERNAME}")

    print(f"\n🔑 Identifiants support :")
    print(f"   Utilisateur : {SUPPORT_USERNAME}")
    print(f"   Mot de passe : (celui défini dans SUPPORT_PASSWORD)")
    print(f"\n⚠️ NE JAMAIS PARTAGER CES IDENTIFIANTS AVEC LE CLIENT.")
    print(f"⚠️ Ce compte sera caché dans l'interface admin.")


if __name__ == '__main__':
    creer_compte_support()
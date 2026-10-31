# ecole/middleware.py
"""
Middleware de vérification de la licence et de redirection setup.
"""
import logging
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


class LicenceMiddleware:
    """Vérifie la validité de la licence à chaque requête."""

    URLS_EXEMPTEES = [
        '/licence/',
        '/login/',
        '/logout/',
        '/admin/',
        '/static/',
        '/media/',
        '/setup/',  # ✅ FIX: permettre l'accès au setup même si licence invalide
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        for url in self.URLS_EXEMPTEES:
            if path.startswith(url):
                return self.get_response(request)

        from .models import Licence

        try:
            licence = Licence.get_licence()
        except (OperationalError, ProgrammingError) as e:
            # On laisse passer UNIQUEMENT si la table n'existe pas encore
            # (migrations en cours, première installation). Toute autre erreur
            # de base (verrou, fichier illisible...) ne doit pas ouvrir l'accès.
            if 'no such table' not in str(e).lower() and 'does not exist' not in str(e).lower():
                raise
            logger.warning("Table Licence absente — accès laissé passer (migrations ?)")
            return self.get_response(request)

        # ✅ FIX: fail-closed. Toute autre erreur remonte (page 500) au lieu
        # d'ouvrir l'application sans licence.
        if not licence.empreinte_valide:
            return redirect('licence_machine_invalide')

        if not licence.est_valide:
            return redirect('licence_expiree')

        request.licence = licence
        return self.get_response(request)


class SetupRedirectMiddleware:
    """
    Redirige vers l'assistant de configuration tant que
    `EcoleInfo.setup_complete` est False.
    """

    URLS_EXEMPTEES = [
        '/setup/',       
        '/static/',
        '/media/',
        '/admin/',
        '/login/',
        '/logout/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # ✅ Laisser passer les URLs exemptées
        for url in self.URLS_EXEMPTEES:
            if path.startswith(url):
                return self.get_response(request)

        try:
            from .models import EcoleInfo
            ecole = EcoleInfo.get_solo()
            if not ecole.setup_complete:
                # ✅ Rediriger vers la page de la clé (au lieu de step1)
                return redirect('setup_cle')
        except (OperationalError, ProgrammingError):
            # Tables pas encore créées (migrations en cours)
            logger.warning("Table EcoleInfo indisponible — setup non vérifié")

        return self.get_response(request)

class ModuleAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .models import EcoleInfo
        
        try:
            ecole = EcoleInfo.get_solo()
            user = request.user
            
            # Le support a toujours accès à tout
            if user.is_authenticated and user.is_superuser and user.username == 'systeme':
                return self.get_response(request)

            # Bloquer le Lycée
            if request.path.startswith('/lycee/') and not ecole.activer_lycee:
                from django.contrib import messages
                from django.shortcuts import redirect
                messages.error(request, "Le module Lycée n'est pas activé.")
                return redirect('fondamental:dashboard') # ou 'dashboard'

            # Bloquer le Fondamental
            if request.path.startswith('/fondamental/') and not ecole.activer_fondamental:
                from django.contrib import messages
                from django.shortcuts import redirect
                messages.error(request, "Le module Fondamental n'est pas activé.")
                return redirect('lycee:dashboard') # ou 'dashboard'
                
        except Exception:
            pass # Si la base n'est pas prête, on laisse passer

        return self.get_response(request)
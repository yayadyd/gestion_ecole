"""
Django settings for gestion_ecole project.

Compatible avec :
- Mode développement (runserver)
- Mode packagé (PyInstaller --onefile ou --onedir)

Points clés :
- BASE_DIR gère sys._MEIPASS pour PyInstaller
- Les données (db.sqlite3, media) vont dans ~/.gestion_ecole_data/
- Les ressources statiques/lecture seule restent dans le bundle
"""
import os
import sys
from pathlib import Path

# =====================================================================
# DÉTECTION MODE PYINSTALLER
# =====================================================================
# sys.frozen est True quand l'app tourne depuis un exe PyInstaller
# sys._MEIPASS pointe vers le dossier temporaire d'extraction (--onefile)
#                    ou le dossier de l'exe (--onedir)
IS_FROZEN = getattr(sys, 'frozen', False)
IS_PYINSTALLER = IS_FROZEN and hasattr(sys, '_MEIPASS')


def get_base_dir():
    """Retourne le dossier racine du projet (dev) ou du bundle (packagé)."""
    if IS_PYINSTALLER:
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_user_data_dir():
    """
    Dossier persistant pour les données utilisateur.
    Toujours dans ~/.gestion_ecole_data/ (indépendant du bundle).
    """
    user_dir = Path.home() / ".gestion_ecole_data"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


# =====================================================================
# CHEMINS DE BASE
# =====================================================================
BASE_DIR = get_base_dir()
USER_DATA_DIR = get_user_data_dir()

# En mode packagé, on expose USER_DATA_DIR comme BASE_DIR pour les données
# mutables (db, media, logs). En dev, on reste dans le projet.
if IS_FROZEN:
    DATA_DIR = USER_DATA_DIR
else:
    DATA_DIR = BASE_DIR


# =====================================================================
# SÉCURITÉ
# =====================================================================
# En production packagée, la SECRET_KEY est lue depuis un fichier persistant.
# En dev, on peut la laisser en dur (mais changez-la !).
SECRET_KEY_FILE = USER_DATA_DIR / ".secret_key"


def get_secret_key():
    """Récupère ou génère une SECRET_KEY persistante."""
    env_key = os.environ.get('DJANGO_SECRET_KEY')
    if env_key:
        return env_key

    if SECRET_KEY_FILE.exists():
        try:
            return SECRET_KEY_FILE.read_text().strip()
        except Exception:
            pass

    # Génère une nouvelle clé et la persiste
    from django.core.management.utils import get_random_secret_key
    key = get_random_secret_key()
    try:
        SECRET_KEY_FILE.write_text(key)
    except Exception:
        pass
    return key


SECRET_KEY = get_secret_key()

# En mode packagé (production), DEBUG = False
# En développement, DEBUG = True
DEBUG = not IS_FROZEN

# Autoriser localhost uniquement (app desktop)
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']


# =====================================================================
# APPLICATIONS
# =====================================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'ecole',
]

# =====================================================================
# MIDDLEWARE
# =====================================================================
MIDDLEWARE = [
    # 1. Sécurité
    'django.middleware.security.SecurityMiddleware',
    
    # 2. WhiteNoise (juste après Security)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    
    # 3. Sessions (OBLIGATOIRE avant Authentication)
    'django.contrib.sessions.middleware.SessionMiddleware',
    
    # 4. Common (pour URL rewriting)
    'django.middleware.common.CommonMiddleware',
    
    # 5. CSRF
    'django.middleware.csrf.CsrfViewMiddleware',
    
    # 6. Authentication (APRÈS Sessions)
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    
    # 7. Messages (APRÈS Authentication)
    'django.contrib.messages.middleware.MessageMiddleware',
    
    # 8. Clickjacking
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # 9. Vos middlewares custom (À LA FIN)
    'ecole.middleware.LicenceMiddleware',
    'ecole.middleware.SetupRedirectMiddleware',
    'ecole.middleware.ModuleAccessMiddleware',
]
ROOT_URLCONF = 'gestion_ecole.urls'

# =====================================================================
# TEMPLATES
# =====================================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',  # templates globaux (optionnel)
            BASE_DIR / 'ecole' / 'templates',  # templates de l'app
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # ✅ Context processors custom
                'ecole.context_processors.annee_encours',
                'ecole.context_processors.trimestres',
                'ecole.context_processors.cycle_courant',
                'ecole.context_processors.licence_context',
                'ecole.context_processors.alertes_configuration',
                'ecole.context_processors.ecole_info', 
                'ecole.context_processors.stats_lycee_header',
                'ecole.context_processors.parametres_globaux',
            ],
            'libraries': {
                # ✅ Filtres custom (get_item, etc.)
                'custom_filters': 'ecole.templatetags.custom_filters',
            },
        },
    },
]

WSGI_APPLICATION = 'gestion_ecole.wsgi.application'


# =====================================================================
# BASE DE DONNÉES
# =====================================================================
# En dev : db.sqlite3 dans le projet
# En packagé : db.sqlite3 dans ~/.gestion_ecole_data/
DATABASE_PATH = os.environ.get('DJANGO_DB_NAME')

if not DATABASE_PATH:
    if IS_FROZEN:
        DATABASE_PATH = str(USER_DATA_DIR / 'db.sqlite3')
    else:
        DATABASE_PATH = str(BASE_DIR / 'db.sqlite3')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATABASE_PATH,
        'OPTIONS': {
            'timeout': 20,  # évite les "database is locked" en SQLite
        },
    }
}


# =====================================================================
# AUTHENTIFICATION
# =====================================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'


# =====================================================================
# INTERNATIONALISATION
# =====================================================================
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Bamako'
USE_I18N = True
USE_TZ = True

# =====================================================================
# FICHIERS STATIQUES ET MEDIA
# =====================================================================
STATIC_URL = '/static/'

# ✅ STATIC_ROOT pointe vers le bundle (PAS vers les données utilisateur)
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'ecole' / 'static',
]

# ✅ WhiteNoise : compression + cache
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ✅ WhiteNoise : servir les fichiers même si non trouvés par Django
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG   # En dev : recharge auto ; en prod : cache
# MEDIA : fichiers uploadés par l'utilisateur
MEDIA_URL = '/media/'
MEDIA_ROOT = USER_DATA_DIR / 'media'
# =====================================================================
# DIVERS
# =====================================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Sessions : durée de vie étendue (app desktop, pas de partage)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 jours
SESSION_SAVE_EVERY_REQUEST = True

# CSRF : fiable en local
CSRF_TRUSTED_ORIGINS = [
    'http://localhost',
    'http://127.0.0.1',
]

# Messages
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'secondary',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

# Fuseau horaire pour les PDF
USE_L10N = True
USE_THOUSAND_SEPARATOR = True


# =====================================================================
# LOGGING
# =====================================================================
LOG_DIR = USER_DATA_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'gestion_ecole.log'),
            'maxBytes': 5 * 1024 * 1024,  # 5 Mo
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'root': {
        'handlers': ['console', 'file'] if not IS_FROZEN else ['file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'] if not IS_FROZEN else ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'ecole': {
            'handlers': ['console', 'file'] if not IS_FROZEN else ['file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}


# =====================================================================
# CONFIGURATION SPÉCIFIQUE PYINSTALLER
# =====================================================================
if IS_FROZEN:
    # En mode packagé, on force DEBUG=False
    DEBUG = False

    # Empêcher Django de chercher des fichiers en dehors du bundle
    # (accélère le démarrage)
    import mimetypes
    mimetypes.init()

    # Cache des templates en mémoire (perf)
    TEMPLATES[0]['APP_DIRS'] = True
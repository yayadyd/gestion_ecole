# run_server.py
import os
import sys
from django.core.management import execute_from_command_line
from waitress import serve

if __name__ == '__main__':
    # 1. Configurer les paramètres Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_ecole.settings')
    
    # 2. Exécuter les migrations automatiquement
    execute_from_command_line(['manage.py', 'migrate', '--noinput'])
    
    # 3. Lancer le serveur avec Waitress (plus stable que runserver)
    from gestion_ecole.wsgi import application
    serve(application, host='127.0.0.1', port=8000, threads=4)
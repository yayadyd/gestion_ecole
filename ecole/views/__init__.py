"""Package de vues de l'application ecole.

Éclatement de l'ancien views.py (6 600 lignes) par domaine.
Chaque module est indépendant : aucune vue n'en appelle une autre.
"""
from .api import *
from .cartes import *
from .comptabilite import *
from .core import *
from .crud import *
from .cycle1 import *
from .cycle2 import *
from .documents import *
from .eleves import *
from .emploi_temps import *
from .matieres import *
from .paiements import *
from .resultats import *

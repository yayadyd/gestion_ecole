# ecole/views_erreurs.py
from django.shortcuts import render

def custom_404(request, exception):
    return render(request, 'erreurs/404.html', status=404)

def custom_500(request):
    return render(request, 'erreurs/500.html', status=500)

def custom_403(request, exception):
    return render(request, 'erreurs/403.html', status=403)
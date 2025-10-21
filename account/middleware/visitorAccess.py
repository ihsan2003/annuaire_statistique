# account/middleware.py

import logging
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger('visitor_access')


class VisitorAccessMiddleware:
    """
    Middleware pour gérer l'accès des visiteurs non authentifiés
    aux pages publiques du dashboard
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # URLs publiques définies dans settings
        self.public_urls = getattr(settings, 'PUBLIC_URLS', [])
        self.visitor_access_enabled = getattr(settings, 'VISITOR_ACCESS_ENABLED', False)
    
    def __call__(self, request):
        # Vérifier si l'accès visiteur est activé
        if not self.visitor_access_enabled:
            response = self.get_response(request)
            return response
        
        # Vérifier si l'utilisateur est déjà authentifié
        if request.user.is_authenticated:
            response = self.get_response(request)
            return response
        
        # Vérifier si l'URL demandée est publique
        path = request.path
        is_public = any(path.startswith(public_url) for public_url in self.public_urls)
        
        if is_public:
            # Marquer la requête comme visiteur
            request.is_visitor = True
            
            # Logger l'accès visiteur
            logger.info(f"Visitor access: {path} from {self.get_client_ip(request)}")
            
            response = self.get_response(request)
            return response
        
        # Pour les URLs non publiques, comportement normal de Django
        # (redirection vers login si nécessaire)
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        """Récupère l'adresse IP du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
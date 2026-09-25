"""Internationalization registry.

Locale JSON is served via GET /api/i18n/<locale> so the frontend can
swap strings at runtime without a reload.
"""
from typing import Dict

DEFAULT_LOCALE = "en"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "app.title": "Arithmetic Super App",
        "tabs.basic": "Basic",
        "tabs.scientific": "Scientific",
        "tabs.matrix": "Matrix",
        "tabs.ai": "AI",
        "tabs.history": "History",
        "tabs.live": "Live",
        "btn.calculate": "Calculate",
        "btn.solve": "Solve",
        "btn.send": "Send",
        "btn.join": "Join",
        "btn.leave": "Leave",
        "btn.login": "Login",
        "btn.logout": "Logout",
        "btn.install": "Install",
        "btn.upload": "Upload",
        "btn.refresh": "Refresh",
        "label.operation": "Operation",
        "label.a": "a",
        "label.b": "b",
        "label.x": "x",
        "label.result": "Result",
        "result.ready": "Ready.",
        "result.guest": "Guest",
        "history.login_required": "Login to see your history.",
        "history.empty": "No calculations yet.",
        "live.room": "Room name",
        "live.you": "Your display name",
        "live.not_connected": "Not connected.",
        "theme.light": "Light",
        "theme.dark": "Dark",
        "theme.auto": "Auto",
        "lang.label": "Language",
    },
    "sw": {
        "app.title": "Programu Kuu ya Hesabu",
        "tabs.basic": "Msingi",
        "tabs.scientific": "Kisayansi",
        "tabs.matrix": "Matrix",
        "tabs.ai": "AI",
        "tabs.history": "Historia",
        "tabs.live": "Moja kwa moja",
        "btn.calculate": "Hesabu",
        "btn.solve": "Tatua",
        "btn.send": "Tuma",
        "btn.join": "Jiunge",
        "btn.leave": "Toka",
        "btn.login": "Ingia",
        "btn.logout": "Toka",
        "btn.install": "Sakinisha",
        "btn.upload": "Pakia",
        "btn.refresh": "Sasisha",
        "label.operation": "Operesheni",
        "label.a": "a",
        "label.b": "b",
        "label.x": "x",
        "label.result": "Matokeo",
        "result.ready": "Tayari.",
        "result.guest": "Mgeni",
        "history.login_required": "Ingia ili kuona historia yako.",
        "history.empty": "Hakuna hesabu bado.",
        "live.room": "Jina la chumba",
        "live.you": "Jina lako la kuonyesha",
        "live.not_connected": "Haujajiunga.",
        "theme.light": "Nuru",
        "theme.dark": "Giza",
        "theme.auto": "Otomatiki",
        "lang.label": "Lugha",
    },
    "fr": {
        "app.title": "Super Application Arithmétique",
        "tabs.basic": "Basique",
        "tabs.scientific": "Scientifique",
        "tabs.matrix": "Matrice",
        "tabs.ai": "IA",
        "tabs.history": "Historique",
        "tabs.live": "Direct",
        "btn.calculate": "Calculer",
        "btn.solve": "Résoudre",
        "btn.send": "Envoyer",
        "btn.join": "Rejoindre",
        "btn.leave": "Quitter",
        "btn.login": "Connexion",
        "btn.logout": "Déconnexion",
        "btn.install": "Installer",
        "btn.upload": "Téléverser",
        "btn.refresh": "Actualiser",
        "label.operation": "Opération",
        "label.a": "a",
        "label.b": "b",
        "label.x": "x",
        "label.result": "Résultat",
        "result.ready": "Prêt.",
        "result.guest": "Invité",
        "history.login_required": "Connectez-vous pour voir votre historique.",
        "history.empty": "Aucun calcul pour l'instant.",
        "live.room": "Nom du salon",
        "live.you": "Votre nom d'affichage",
        "live.not_connected": "Non connecté.",
        "theme.light": "Clair",
        "theme.dark": "Sombre",
        "theme.auto": "Auto",
        "lang.label": "Langue",
    },
    "es": {
        "app.title": "Super App Aritmética",
        "tabs.basic": "Básico",
        "tabs.scientific": "Científico",
        "tabs.matrix": "Matriz",
        "tabs.ai": "IA",
        "tabs.history": "Historial",
        "tabs.live": "En vivo",
        "btn.calculate": "Calcular",
        "btn.solve": "Resolver",
        "btn.send": "Enviar",
        "btn.join": "Unirse",
        "btn.leave": "Salir",
        "btn.login": "Iniciar sesión",
        "btn.logout": "Cerrar sesión",
        "btn.install": "Instalar",
        "btn.upload": "Subir",
        "btn.refresh": "Actualizar",
        "label.operation": "Operación",
        "label.a": "a",
        "label.b": "b",
        "label.x": "x",
        "label.result": "Resultado",
        "result.ready": "Listo.",
        "result.guest": "Invitado",
        "history.login_required": "Inicia sesión para ver tu historial.",
        "history.empty": "Aún no hay cálculos.",
        "live.room": "Nombre de la sala",
        "live.you": "Tu nombre para mostrar",
        "live.not_connected": "No conectado.",
        "theme.light": "Claro",
        "theme.dark": "Oscuro",
        "theme.auto": "Auto",
        "lang.label": "Idioma",
    },
}


def supported_locales():
    return sorted(TRANSLATIONS.keys())


def pick_locale(accept_language: str) -> str:
    """Parse an Accept-Language header and return the best match."""
    if not accept_language:
        return DEFAULT_LOCALE
    parts = []
    for token in accept_language.split(","):
        token = token.strip()
        if not token:
            continue
        lang = token.split(";")[0].strip().lower()
        # Match "en-US" -> "en"
        base = lang.split("-")[0]
        parts.append(base)
    for p in parts:
        if p in TRANSLATIONS:
            return p
    return DEFAULT_LOCALE

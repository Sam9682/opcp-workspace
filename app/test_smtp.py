"""Script de test SMTP intégré à l'application

Ce script utilise la configuration de l'application pour tester l'envoi d'email.
"""
import sys
import os

# Ajouter le répertoire parent au path pour importer les modules de l'app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.email import email_service
from app.config import settings
from app.logging_config import logger


def test_smtp_connection():
    """Teste la connexion SMTP et affiche la configuration"""
    print("=" * 70)
    print("🧪 TEST SMTP OPCP")
    print("=" * 70)
    print()
    
    # Afficher la configuration
    print("📋 Configuration SMTP actuelle:")
    print(f"   Serveur:     {settings.SMTP_HOST}")
    print(f"   Port:        {settings.SMTP_PORT}")
    print(f"   Utilisateur: {settings.SMTP_USER}")
    print(f"   Expéditeur:  {settings.SMTP_FROM}")
    print(f"   Mot de passe: {'*' * len(settings.SMTP_PASSWORD) if settings.SMTP_PASSWORD else '(vide)'}")
    print()
    
    # Vérifier que la configuration est complète
    if not settings.SMTP_HOST or settings.SMTP_HOST == "localhost":
        print("⚠️  ATTENTION: SMTP_HOST n'est pas configuré (valeur: localhost)")
        print("   Configurez SMTP_HOST dans le fichier .env")
        return False
    
    if not settings.SMTP_USER:
        print("⚠️  ATTENTION: SMTP_USER n'est pas configuré")
        print("   Configurez SMTP_USER dans le fichier .env")
        return False
    
    if not settings.SMTP_PASSWORD:
        print("⚠️  ATTENTION: SMTP_PASSWORD n'est pas configuré")
        print("   Configurez SMTP_PASSWORD dans le fichier .env")
        return False
    
    return True


def send_test_email(to_email: str):
    """Envoie un email de test"""
    print(f"📧 Envoi d'un email de test à: {to_email}")
    print()
    
    subject = "Test SMTP OPCP"
    
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #6366f1;">🎉 Test SMTP OPCP</h2>
                <p>Bonjour,</p>
                <p>Ceci est un email de test pour vérifier la configuration SMTP de OPCP.</p>
                <div style="background-color: #f0fdf4; border-left: 4px solid #22c55e; padding: 15px; margin: 20px 0;">
                    <p style="margin: 0; color: #166534;">
                        ✅ <strong>Si vous recevez cet email, la configuration SMTP fonctionne correctement !</strong>
                    </p>
                </div>
                <h3 style="color: #6366f1;">Configuration utilisée:</h3>
                <ul style="background-color: #f8fafc; padding: 15px; border-radius: 5px;">
                    <li><strong>Serveur:</strong> {settings.SMTP_HOST}</li>
                    <li><strong>Port:</strong> {settings.SMTP_PORT}</li>
                    <li><strong>Utilisateur:</strong> {settings.SMTP_USER}</li>
                    <li><strong>Expéditeur:</strong> {settings.SMTP_FROM}</li>
                </ul>
                <p style="margin-top: 30px; color: #666; font-size: 14px;">
                    Cordialement,<br>
                    <strong>L'équipe OPCP</strong>
                </p>
            </div>
        </body>
    </html>
    """
    
    text_body = f"""
Bonjour,

Ceci est un email de test pour vérifier la configuration SMTP de OPCP.

✅ Si vous recevez cet email, la configuration SMTP fonctionne correctement !

Configuration utilisée:
- Serveur: {settings.SMTP_HOST}
- Port: {settings.SMTP_PORT}
- Utilisateur: {settings.SMTP_USER}
- Expéditeur: {settings.SMTP_FROM}

Cordialement,
L'équipe OPCP
    """
    
    print("🔄 Envoi en cours...")
    success = email_service.send_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body
    )
    
    print()
    if success:
        print("✅ Email envoyé avec succès !")
        print(f"📬 Vérifiez la boîte de réception de {to_email}")
        print("💡 N'oubliez pas de vérifier le dossier spam/courrier indésirable")
        return True
    else:
        print("❌ Échec de l'envoi de l'email")
        print("📋 Consultez les logs ci-dessus pour plus de détails")
        print()
        print("💡 Vérifications à faire:")
        print("   1. Les identifiants SMTP sont-ils corrects ?")
        print("   2. Le serveur SMTP est-il accessible ?")
        print("   3. Le port 587 est-il ouvert ?")
        print("   4. Le compte email existe-t-il ?")
        return False


def main():
    """Fonction principale"""
    # Vérifier la configuration
    if not test_smtp_connection():
        print()
        print("=" * 70)
        print("❌ Configuration SMTP incomplète")
        print("=" * 70)
        return 1
    
    # Demander l'email de destination
    print("📧 Email de destination:")
    to_email = input("   Entrez l'adresse email (ou appuyez sur Entrée pour lepetre@yahoo.fr): ").strip()
    
    if not to_email:
        to_email = "lepetre@yahoo.fr"
    
    print()
    
    # Envoyer l'email de test
    success = send_test_email(to_email)
    
    print()
    print("=" * 70)
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Test interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erreur inattendue: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

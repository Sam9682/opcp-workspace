"""Script de test pour l'envoi d'email via SMTP Gandi

Ce script teste la configuration SMTP et envoie un email de test.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

# Configuration SMTP Gandi
SMTP_HOST = "mail.gandi.net"
SMTP_PORT = 587
SMTP_USER = "sam@opcp-psmc.com"
SMTP_PASSWORD = "Asbaasba1234!"  # ⚠️ REMPLACER PAR LE VRAI MOT DE PASSE
SMTP_FROM = "noreply@opcp-psmc.com"

# Destinataire
TO_EMAIL = "lepetre@yahoo.fr"

def send_test_email():
    """Envoie un email de test"""
    try:
        print("🔄 Connexion au serveur SMTP Gandi...")
        print(f"   Serveur: {SMTP_HOST}:{SMTP_PORT}")
        print(f"   Utilisateur: {SMTP_USER}")
        
        # Créer le message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Test SMTP OPCP"
        msg['From'] = SMTP_FROM
        msg['To'] = TO_EMAIL
        
        # Corps du message en texte brut
        text_body = """
Bonjour,

Ceci est un email de test pour vérifier la configuration SMTP de OPCP.

Si vous recevez cet email, la configuration SMTP fonctionne correctement !

Configuration utilisée:
- Serveur: mail.gandi.net
- Port: 587
- Utilisateur: admin@opcp-psmc.com

Cordialement,
L'équipe OPCP
        """
        
        # Corps du message en HTML
        html_body = """
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
                <li><strong>Serveur:</strong> mail.gandi.net</li>
                <li><strong>Port:</strong> 587 (TLS)</li>
                <li><strong>Utilisateur:</strong> admin@opcp-psmc.com</li>
                <li><strong>Expéditeur:</strong> noreply@opcp-psmc.com</li>
            </ul>
            <p style="margin-top: 30px; color: #666; font-size: 14px;">
                Cordialement,<br>
                <strong>L'équipe OPCP</strong>
            </p>
        </div>
    </body>
</html>
        """
        
        # Attacher les deux versions
        part1 = MIMEText(text_body, 'plain', 'utf-8')
        part2 = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(part1)
        msg.attach(part2)
        
        # Connexion et envoi
        print("🔐 Authentification...")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.set_debuglevel(1)  # Afficher les détails de la communication
            print("🔒 Activation TLS...")
            server.starttls()
            print("🔑 Connexion avec les identifiants...")
            server.login(SMTP_USER, SMTP_PASSWORD)
            print(f"📧 Envoi de l'email à {TO_EMAIL}...")
            server.send_message(msg)
        
        print("\n✅ Email envoyé avec succès !")
        print(f"📬 Vérifiez la boîte de réception de {TO_EMAIL}")
        print("💡 N'oubliez pas de vérifier le dossier spam/courrier indésirable")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print("\n❌ Erreur d'authentification SMTP")
        print(f"   Détails: {str(e)}")
        print("\n💡 Vérifications à faire:")
        print("   1. Le mot de passe est-il correct ?")
        print("   2. Le compte admin@opcp-psmc.com existe-t-il sur Gandi ?")
        print("   3. L'authentification SMTP est-elle activée ?")
        return False
        
    except smtplib.SMTPConnectError as e:
        print("\n❌ Erreur de connexion au serveur SMTP")
        print(f"   Détails: {str(e)}")
        print("\n💡 Vérifications à faire:")
        print("   1. Le serveur mail.gandi.net est-il accessible ?")
        print("   2. Le port 587 est-il ouvert ?")
        print("   3. Votre pare-feu bloque-t-il la connexion ?")
        return False
        
    except smtplib.SMTPException as e:
        print("\n❌ Erreur SMTP")
        print(f"   Détails: {str(e)}")
        return False
        
    except Exception as e:
        print("\n❌ Erreur inattendue")
        print(f"   Type: {type(e).__name__}")
        print(f"   Détails: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TEST SMTP OPCP - Configuration Gandi")
    print("=" * 60)
    print()
    
    # Vérifier que le mot de passe a été modifié
    if SMTP_PASSWORD == "your-email-password":
        print("⚠️  ATTENTION: Vous devez remplacer 'your-email-password'")
        print("    par le vrai mot de passe dans ce script !")
        print()
        response = input("Voulez-vous continuer quand même ? (o/N): ")
        if response.lower() != 'o':
            print("❌ Test annulé")
            sys.exit(1)
    
    print()
    success = send_test_email()
    print()
    print("=" * 60)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

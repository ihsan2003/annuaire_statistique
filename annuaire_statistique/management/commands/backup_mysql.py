#!/usr/bin/env python
"""
Script de sauvegarde avancé pour base de données MySQL Django
Utilisation: python backup_mysql.py ou en tant que commande Django
"""

import os
import sys
import subprocess
import datetime
import logging
import smtplib
import gzip
import shutil
import platform
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'annuaire_statistique.settings')

try:
    import django
    from django.conf import settings
    from django.core.management.base import BaseCommand
    django.setup()
    IS_DJANGO = True
except ImportError:
    IS_DJANGO = False

class MySQLBackup:
    def __init__(self, config=None):
        self.config = config or self.get_default_config()
        self.setup_logging()
        
    def find_mysqldump(self):
        """Trouver le chemin de mysqldump selon l'OS"""
        system = platform.system()
        
        if system == 'Windows':
            # Chemins possibles sur Windows
            possible_paths = [
                'C:\\xampp\\mysql\\bin\\mysqldump.exe',
                'C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin\\mysqldump.exe',
                'C:\\Program Files\\MySQL\\MySQL Server 5.7\\bin\\mysqldump.exe',
                'C:\\wamp64\\bin\\mysql\\mysql8.0.21\\bin\\mysqldump.exe',
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    self.logger.info(f"mysqldump trouvé: {path}")
                    return path
            
            # Essayer dans le PATH
            try:
                result = subprocess.run(['where', 'mysqldump'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    path = result.stdout.strip().split('\n')[0]
                    self.logger.info(f"mysqldump trouvé dans PATH: {path}")
                    return path
            except:
                pass
        else:
            # Linux/Mac - essayer dans le PATH
            try:
                result = subprocess.run(['which', 'mysqldump'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                pass
        
        raise Exception("mysqldump introuvable. Vérifiez l'installation MySQL/MariaDB")
        
    def get_default_config(self):
        """Configuration par défaut"""
        
        # Répertoire de sauvegarde adapté au système
        if platform.system() == 'Windows':
            backup_dir = 'C:\\xampp\\backups\\mysql'
        else:
            backup_dir = '/var/backups/mysql'
            
        if IS_DJANGO:
            db_settings = settings.DATABASES['default']
            return {
                'db_name': db_settings['NAME'],
                'db_user': db_settings['USER'],
                'db_password': db_settings['PASSWORD'],
                'db_host': db_settings.get('HOST', 'localhost'),
                'db_port': db_settings.get('PORT', '3306'),
                'backup_dir': backup_dir,
                'max_backups': 30,  # Garder 30 sauvegardes
                'compress': True,
                'email_notifications': True,  # Désactivé par défaut
                'email_config': {
                    'smtp_server': 'smtp.gmail.com',
                    'smtp_port': 587,
                    'email_user': 'ihsanennaji15@gmail.com',
                    'email_password': 'qstvtkbxedbdksal',
                    'recipient': 'ihsanmeriem2007@gmail.com'
                }
            }
        else:
            # Configuration manuelle si pas Django
            return {
                'db_name': 'annuaire_statistique',
                'db_user': 'root',
                'db_password': 'Entraide@2025***',
                'db_host': 'localhost',
                'db_port': '3306',
                'backup_dir': backup_dir,
                'max_backups': 30,
                'compress': True,
                'email_notifications': False,  # DÉSACTIVER pour éviter l'erreur email
            }
    
    def setup_logging(self):
        """Configuration des logs"""
        log_dir = Path(self.config['backup_dir']) / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / 'backup.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def create_backup_dir(self):
        """Créer le répertoire de sauvegarde"""
        backup_path = Path(self.config['backup_dir'])
        backup_path.mkdir(parents=True, exist_ok=True)
        return backup_path
    
    def generate_backup_filename(self):
        """Générer le nom du fichier de sauvegarde"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        db_name = self.config['db_name']
        filename = f"{db_name}_backup_{timestamp}.sql"
        return filename
    
    def create_backup(self):
        """Créer la sauvegarde MySQL"""
        try:
            backup_dir = self.create_backup_dir()
            filename = self.generate_backup_filename()
            backup_path = backup_dir / filename
            
            self.logger.info(f"Début de la sauvegarde de {self.config['db_name']}")
            
            # Trouver mysqldump
            mysqldump_path = self.find_mysqldump()
            
            # Commande mysqldump avec chemin complet
            cmd = [
                mysqldump_path,  # Utiliser le chemin complet
                '--single-transaction',
                '--routines',
                '--triggers',
                '--lock-tables=false',
                f"--host={self.config['db_host']}",
                f"--port={self.config['db_port']}",
                f"--user={self.config['db_user']}",
            ]
            
            # Ajouter le mot de passe seulement s'il n'est pas vide
            if self.config['db_password']:
                cmd.append(f"--password={self.config['db_password']}")
            
            cmd.append(self.config['db_name'])
            
            self.logger.info(f"Commande: {' '.join(cmd[:8])}... [masqué pour sécurité]")
            
            # Exécuter mysqldump
            with open(backup_path, 'w', encoding='utf-8') as backup_file:
                result = subprocess.run(
                    cmd, 
                    stdout=backup_file, 
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            if result.returncode != 0:
                raise Exception(f"Erreur mysqldump: {result.stderr}")
            
            # Compression si activée
            if self.config['compress']:
                compressed_path = self.compress_backup(backup_path)
                backup_path.unlink()  # Supprimer le fichier non compressé
                backup_path = compressed_path
            
            # Vérifier la taille du fichier
            file_size = backup_path.stat().st_size
            self.logger.info(f"Sauvegarde créée: {backup_path} ({self.format_size(file_size)})")
            
            return backup_path
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde: {e}")
            raise
    
    def compress_backup(self, file_path):
        """Compresser le fichier de sauvegarde"""
        compressed_path = Path(str(file_path) + '.gz')
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        self.logger.info(f"Fichier compressé: {compressed_path}")
        return compressed_path
    
    def cleanup_old_backups(self):
        """Nettoyer les anciennes sauvegardes"""
        try:
            backup_dir = Path(self.config['backup_dir'])
            db_name = self.config['db_name']
            
            # Trouver tous les fichiers de sauvegarde
            pattern = f"{db_name}_backup_*.sql*"
            backup_files = list(backup_dir.glob(pattern))
            
            # Trier par date de modification (plus récent en premier)
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Supprimer les fichiers excédentaires
            files_to_delete = backup_files[self.config['max_backups']:]
            
            for file_path in files_to_delete:
                file_path.unlink()
                self.logger.info(f"Ancienne sauvegarde supprimée: {file_path}")
                
            self.logger.info(f"Nettoyage terminé. {len(files_to_delete)} fichiers supprimés")
            
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage: {e}")
    
    def send_notification(self, success, backup_path=None, error=None):
        """Envoyer une notification par email"""
        if not self.config['email_notifications']:
            self.logger.info("Notifications email désactivées")
            return
            
        try:
            email_config = self.config['email_config']
            
            msg = MIMEMultipart()
            msg['From'] = email_config['email_user']
            msg['To'] = email_config['recipient']
            
            if success:
                msg['Subject'] = f"✅ Sauvegarde MySQL réussie - {self.config['db_name']}"
                body = f"""
                Sauvegarde réussie !
                
                Base de données: {self.config['db_name']}
                Fichier: {backup_path}
                Taille: {self.format_size(backup_path.stat().st_size) if backup_path else 'N/A'}
                Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            else:
                msg['Subject'] = f"❌ Erreur sauvegarde MySQL - {self.config['db_name']}"
                body = f"""
                Erreur lors de la sauvegarde !
                
                Base de données: {self.config['db_name']}
                Erreur: {error}
                Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Connexion SMTP
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
            server.login(email_config['email_user'], email_config['email_password'])
            
            text = msg.as_string()
            server.sendmail(email_config['email_user'], email_config['recipient'], text)
            server.quit()
            
            self.logger.info("Notification email envoyée")
            
        except Exception as e:
            self.logger.error(f"Erreur envoi email: {e}")
    
    def format_size(self, size_bytes):
        """Formater la taille en unités lisibles"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"
    
    def run(self):
        """Exécuter la sauvegarde complète"""
        backup_path = None
        try:
            self.logger.info("=== DÉBUT DE LA SAUVEGARDE ===")
            
            # Créer la sauvegarde
            backup_path = self.create_backup()
            
            # Nettoyer les anciennes sauvegardes
            self.cleanup_old_backups()
            
            # Envoyer notification de succès
            self.send_notification(True, backup_path)
            
            self.logger.info("=== SAUVEGARDE TERMINÉE AVEC SUCCÈS ===")
            return True
            
        except Exception as e:
            self.logger.error(f"=== ERREUR DE SAUVEGARDE: {e} ===")
            self.send_notification(False, error=str(e))
            return False


# Commande Django Management
if IS_DJANGO:
    class Command(BaseCommand):
        help = 'Créer une sauvegarde de la base de données MySQL'
        
        def add_arguments(self, parser):
            parser.add_argument(
                '--compress',
                action='store_true',
                help='Compresser la sauvegarde',
            )
            parser.add_argument(
                '--max-backups',
                type=int,
                default=30,
                help='Nombre maximum de sauvegardes à conserver',
            )
        
        def handle(self, *args, **options):
            config = {
                'db_name': settings.DATABASES['default']['NAME'],
                'db_user': settings.DATABASES['default']['USER'],
                'db_password': settings.DATABASES['default']['PASSWORD'],
                'db_host': settings.DATABASES['default'].get('HOST', 'localhost'),
                'db_port': settings.DATABASES['default'].get('PORT', '3306'),
                'backup_dir': '/var/backups/mysql',
                'max_backups': options['max_backups'],
                'compress': options['compress'],
                'email_notifications': False,
            }
            
            backup = MySQLBackup(config)
            success = backup.run()
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS('Sauvegarde créée avec succès')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Erreur lors de la sauvegarde')
                )


# Utilisation en script standalone
if __name__ == '__main__':
    # Configuration personnalisée
    config = {
        'db_name': 'annuaire_statistique',
        'db_user': 'root',
        'db_password': 'Entraide@2025***',  # Mot de passe vide pour XAMPP par défaut
        'db_host': 'localhost',
        'db_port': '3306',
        'backup_dir': 'C:\\xampp\\backups\\mysql',
        'max_backups': 30,
        'compress': True,
        'email_notifications': True,  # DÉSACTIVER les notifications email
        'email_config': {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'email_user': 'ihsanennaji15@gmail.com',
            'email_password': 'qstvtkbxedbdksal',
            'recipient': 'ihsanmeriem2007@gmail.com'
        }
    }
    
    backup = MySQLBackup(config)
    backup.run()
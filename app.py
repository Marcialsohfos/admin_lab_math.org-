from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os
from functools import wraps
import requests

# Création de l'application Flask
# CORRECTION: Spécification explicite du dossier templates
app = Flask(__name__, 
            template_folder='templates',  # 👈 Correction cruciale
            static_folder='static')
CORS(app)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_12345')

# Correction impérative pour PostgreSQL sur Render
database_url = os.environ.get('DATABASE_URL', 'sqlite:///labmath_db.sqlite')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Créer le dossier uploads s'il n'existe pas
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialisation de la base de données
db = SQLAlchemy(app)

# Configuration pour l'API du site principal
SITE_URL = os.environ.get('SITE_URL', 'https://labmath-scsmaubmar-org.onrender.com')
API_KEY = os.environ.get('API_KEY', '')

# --- DÉCORATEUR SÉCURITÉ ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter pour accéder à cette page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- MODÈLES ---
class Activite(db.Model):
    __tablename__ = 'activites'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    contenu = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    auteur = db.Column(db.String(100))
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_modification = db.Column(db.DateTime, onupdate=datetime.utcnow)
    est_publie = db.Column(db.Boolean, default=True)
    sync_id = db.Column(db.String(100))

class Realisation(db.Model):
    __tablename__ = 'realisations'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    categorie = db.Column(db.String(100))
    date_realisation = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    sync_id = db.Column(db.String(100))

class Annonce(db.Model):
    __tablename__ = 'annonces'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    contenu = db.Column(db.Text)
    type_annonce = db.Column(db.String(50))
    date_debut = db.Column(db.DateTime)
    date_fin = db.Column(db.DateTime)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)
    sync_id = db.Column(db.String(100))

class Offre(db.Model):
    __tablename__ = 'offres'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_offre = db.Column(db.String(50))
    lieu = db.Column(db.String(100))
    date_limite = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)
    sync_id = db.Column(db.String(100))

# --- FONCTIONS DE SYNCHRONISATION ---
def sync_activite(activite):
    """Synchronise une activité avec le site principal"""
    if not API_KEY:
        return False, "API_KEY non configurée"
    
    try:
        headers = {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
        }
        
        data = {
            'id': str(activite.id),
            'titre': activite.titre,
            'description': activite.description or '',
            'contenu': activite.contenu or '',
            'image_url': activite.image_url or '',
            'auteur': activite.auteur or 'Admin',
            'date_creation': activite.date_creation.isoformat() if activite.date_creation else datetime.utcnow().isoformat(),
            'est_publie': activite.est_publie
        }
        
        api_url = f"{SITE_URL}/api/activites"
        if activite.sync_id:
            api_url = f"{api_url}/{activite.sync_id}"
        
        response = requests.post(api_url, headers=headers, json=data, timeout=5)
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result.get('success'):
                activite.sync_id = str(result.get('id', activite.id))
                db.session.commit()
                return True, "Synchronisation réussie"
        return False, f"Erreur HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        return False, "Timeout de connexion"
    except requests.exceptions.ConnectionError:
        return False, "Site principal inaccessible"
    except Exception as e:
        return False, f"Erreur: {str(e)}"

# --- ROUTES AUTHENTIFICATION ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        if username == admin_user and password == admin_pass:
            session['user_id'] = 1
            session['username'] = username
            flash('Connexion réussie!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Identifiants incorrects', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('login'))

# --- ROUTES DASHBOARD ---
@app.route('/dashboard')
@login_required
def dashboard():
    try:
        stats = {
            'activities_count': Activite.query.count(),
            'realisations_count': Realisation.query.count(),
            'annonces_count': Annonce.query.count(),
            'offres_count': Offre.query.count(),
            'activities_published': Activite.query.filter_by(est_publie=True).count(),
            'annonces_active': Annonce.query.filter_by(est_active=True).count(),
            'offres_active': Offre.query.filter_by(est_active=True).count(),
            'realisations_with_images': Realisation.query.filter(Realisation.image_url.isnot(None)).count()
        }
        
        # Vérification de la connexion au site principal
        site_connected = False
        site_message = ""
        if API_KEY:
            try:
                response = requests.get(f"{SITE_URL}/api/health", timeout=3)
                site_connected = response.status_code == 200
                site_message = "Connecté" if site_connected else "Non connecté"
            except:
                site_message = "Site inaccessible"
        else:
            site_message = "API_KEY non configurée"
        
        stats['site_connected'] = site_connected
        stats['site_message'] = site_message
        
        # Derniers éléments
        recent_activities = Activite.query.order_by(Activite.date_creation.desc()).limit(5).all()
        recent_annonces = Annonce.query.order_by(Annonce.date_creation.desc()).limit(5).all()
        
        return render_template('dashboard.html',  # 👈 Utilisation de dashboard.html
                              stats=stats, 
                              now=datetime.utcnow(),
                              site_url=SITE_URL,
                              recent_activities=recent_activities,
                              recent_annonces=recent_annonces)
    except Exception as e:
        flash(f'Erreur lors du chargement du dashboard: {str(e)}', 'danger')
        # CORRECTION: fallback vers un template simple si dashboard.html n'existe pas
        return render_template('simple_dashboard.html',  # 👈 Créez ce fichier
                              stats={'activities_count': 0, 'realisations_count': 0, 'annonces_count': 0, 'offres_count': 0},
                              now=datetime.utcnow(),
                              error=str(e))

# --- ROUTES ACTIVITÉS ---
@app.route('/activites')
@login_required
def activites():
    activites_list = Activite.query.order_by(Activite.date_creation.desc()).all()
    return render_template('activites.html', activites=activites_list)

@app.route('/activite/nouveau', methods=['GET', 'POST'])
@login_required
def nouvel_activite():
    if request.method == 'POST':
        try:
            nouvelle = Activite(
                titre=request.form.get('titre', ''),
                description=request.form.get('description', ''),
                contenu=request.form.get('contenu', ''),
                image_url=request.form.get('image_url', ''),
                auteur=session.get('username', 'Admin'),
                est_publie=request.form.get('est_publie') == 'true'
            )
            db.session.add(nouvelle)
            db.session.commit()
            
            if nouvelle.est_publie:
                success, message = sync_activite(nouvelle)
                if success:
                    flash('Activité créée et synchronisée avec le site!', 'success')
                else:
                    flash(f'Activité créée mais erreur de synchronisation: {message}', 'warning')
            else:
                flash('Activité créée!', 'success')
                
            return redirect(url_for('activites'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', action='nouveau', activite=None)

# --- ROUTES POUR LES AUTRES MODÈLES ---
# Ajoutez ici vos routes pour realisations, annonces, offres

# --- ROUTE DE TEST ---
@app.route('/test')
def test():
    return jsonify({
        'status': 'ok',
        'message': 'Admin LabMath fonctionne!',
        'database': str(app.config['SQLALCHEMY_DATABASE_URI']),
        'site_url': SITE_URL,
        'api_key_configured': bool(API_KEY),
        'template_folder': app.template_folder  # 👈 Utile pour le debug
    })

# --- GESTION DES ERREURS ---
@app.errorhandler(404)
def not_found(e):
    if 'user_id' in session:
        try:
            return render_template('404.html'), 404
        except:
            return "Page non trouvée - 404", 404
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    if 'user_id' in session:
        try:
            return render_template('500.html', error=str(e)), 500
        except:
            return f"Erreur interne: {str(e)}", 500
    return redirect(url_for('login'))

# --- INITIALISATION ---
with app.app_context():
    try:
        db.create_all()
        print("✅ Base de données initialisée avec succès")
        print(f"📁 Dossier templates: {app.template_folder}")
        # Vérifier que les templates existent
        import os
        templates_path = app.template_folder
        if os.path.exists(templates_path):
            files = os.listdir(templates_path)
            print(f"📄 Templates trouvés: {files}")
        else:
            print(f"⚠️  Dossier templates introuvable: {templates_path}")
    except Exception as e:
        print(f"❌ Erreur base de données: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)